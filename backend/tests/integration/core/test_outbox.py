from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import outbox
from app.core.outbox import OutboxEvent, dispatch_pending, enqueue, subscribe


async def test_dispatch_delivers_and_marks_published(session: AsyncSession) -> None:
    received: list[dict[str, Any]] = []

    @subscribe("test.delivered")
    async def handler(payload: dict[str, Any]) -> None:
        received.append(payload)

    try:
        enqueue(session, "test.delivered", {"order_id": "o-1"})
        await session.commit()

        assert await dispatch_pending(session) == 1
        assert received == [{"order_id": "o-1"}]

        event = (await session.scalars(select(OutboxEvent))).one()
        assert event.published_at is not None
        assert await dispatch_pending(session) == 0
    finally:
        outbox._handlers.pop("test.delivered")


async def test_failed_handler_is_retried_later(session: AsyncSession) -> None:
    @subscribe("test.failing")
    async def handler(payload: dict[str, Any]) -> None:
        raise RuntimeError("provider down")

    try:
        enqueue(session, "test.failing", {})
        await session.commit()

        assert await dispatch_pending(session) == 0
        event = (await session.scalars(select(OutboxEvent))).one()
        assert event.published_at is None
        assert event.attempts == 1
        assert "provider down" in (event.last_error or "")
    finally:
        outbox._handlers.pop("test.failing")
