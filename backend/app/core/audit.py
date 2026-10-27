"""Append-only audit log for reads and decisions that need a trail (ADR 0003).

`record` adds the row to the caller's transaction, so it commits or rolls back with the
action it describes. `record_now` commits on a separate connection; use it for refusals,
where the request's own transaction is about to roll back with the error.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Index, String, Uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, utcnow


class Outcome(StrEnum):
    ALLOWED = "allowed"
    DENIED = "denied"
    NOT_FOUND = "not_found"


class AuditLog(IdMixin, Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_subject_created_at", "subject_type", "subject_id", "created_at"),
    )

    # Plain ids, not foreign keys: the trail outlives the rows it mentions.
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    action: Mapped[str] = mapped_column(String(64))
    subject_type: Mapped[str] = mapped_column(String(32))
    subject_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    purpose: Mapped[str | None] = mapped_column(String(64))
    outcome: Mapped[str] = mapped_column(String(16))
    detail: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


def _row(
    *,
    actor_id: uuid.UUID | None,
    action: str,
    subject_type: str,
    subject_id: uuid.UUID,
    outcome: Outcome,
    purpose: str | None,
    detail: str | None,
) -> AuditLog:
    return AuditLog(
        actor_id=actor_id,
        action=action,
        subject_type=subject_type,
        subject_id=subject_id,
        outcome=outcome.value,
        purpose=purpose,
        detail=detail,
        created_at=utcnow(),
    )


def record(
    db: AsyncSession,
    *,
    actor_id: uuid.UUID | None,
    action: str,
    subject_type: str,
    subject_id: uuid.UUID,
    outcome: Outcome = Outcome.ALLOWED,
    purpose: str | None = None,
    detail: str | None = None,
) -> None:
    db.add(
        _row(
            actor_id=actor_id,
            action=action,
            subject_type=subject_type,
            subject_id=subject_id,
            outcome=outcome,
            purpose=purpose,
            detail=detail,
        )
    )


async def record_now(
    db: AsyncSession,
    *,
    actor_id: uuid.UUID | None,
    action: str,
    subject_type: str,
    subject_id: uuid.UUID,
    outcome: Outcome,
    purpose: str | None = None,
    detail: str | None = None,
) -> None:
    async with AsyncSession(db.bind) as separate:
        separate.add(
            _row(
                actor_id=actor_id,
                action=action,
                subject_type=subject_type,
                subject_id=subject_id,
                outcome=outcome,
                purpose=purpose,
                detail=detail,
            )
        )
        await separate.commit()
