"""Transactional outbox.

Modules record events in the same transaction as their state change, and a background job
publishes them afterwards. This keeps cross-module side effects (notifications, payouts,
dispatch) reliable without distributed transactions.
"""

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, Text, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin, utcnow

log = logging.getLogger(__name__)

Handler = Callable[[dict[str, Any]], Awaitable[None]]
_handlers: dict[str, list[Handler]] = {}

MAX_ATTEMPTS = 10


class OutboxEvent(IdMixin, TimestampMixin, Base):
    __tablename__ = "outbox_events"

    topic: Mapped[str] = mapped_column(String(120), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)


def subscribe(topic: str) -> Callable[[Handler], Handler]:
    def decorator(fn: Handler) -> Handler:
        _handlers.setdefault(topic, []).append(fn)
        return fn

    return decorator


def enqueue(session: AsyncSession, topic: str, payload: dict[str, Any]) -> OutboxEvent:
    """Add an event to the caller's transaction; it becomes visible only when that commits."""
    event = OutboxEvent(topic=topic, payload=payload, attempts=0)
    session.add(event)
    return event


async def dispatch_pending(session: AsyncSession, batch_size: int = 100) -> int:
    """Deliver unpublished events to their subscribers. Returns how many were published."""
    stmt = (
        select(OutboxEvent)
        .where(OutboxEvent.published_at.is_(None), OutboxEvent.attempts < MAX_ATTEMPTS)
        .order_by(OutboxEvent.created_at)
        .limit(batch_size)
    )
    if session.get_bind().dialect.name == "postgresql":
        stmt = stmt.with_for_update(skip_locked=True)

    published = 0
    for event in (await session.scalars(stmt)).all():
        try:
            for handler in _handlers.get(event.topic, []):
                await handler(event.payload)
        except Exception as exc:
            event.attempts += 1
            event.last_error = repr(exc)
            log.warning("outbox handler failed for %s (%s)", event.topic, event.id)
        else:
            event.published_at = utcnow()
            published += 1
    await session.commit()
    return published
