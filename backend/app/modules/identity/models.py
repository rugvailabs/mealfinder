"""SQLAlchemy models owned by the identity module.

Other modules reference these rows by id only, never through ORM relationships.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.auth import Role
from app.core.db import Base, IdMixin, TimestampMixin, utcnow

ROLE_VALUES = ", ".join(f"'{r.value}'" for r in Role)


def _now_column() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), default=utcnow)


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("status in ('active', 'suspended')", name="status"),)

    phone: Mapped[str] = mapped_column(String(16), unique=True)  # E.164
    name: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(16), default="active")


class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = (CheckConstraint(f"role in ({ROLE_VALUES})", name="role"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(16), primary_key=True)
    granted_at: Mapped[datetime] = _now_column()
    granted_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class OtpChallenge(IdMixin, Base):
    __tablename__ = "otp_challenges"
    __table_args__ = (Index("ix_otp_challenges_phone_created_at", "phone", "created_at"),)

    phone: Mapped[str] = mapped_column(String(16))
    code_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = _now_column()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuthSession(IdMixin, Base):
    """One signed-in device. Revoking it ends every token issued under it."""

    __tablename__ = "sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = _now_column()
    last_seen_at: Mapped[datetime] = _now_column()
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoke_reason: Mapped[str | None] = mapped_column(String(32))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    ip: Mapped[str | None] = mapped_column(String(45))


class RefreshToken(IdMixin, Base):
    """Single-use. Rotating marks it used; presenting a used token revokes the session."""

    __tablename__ = "refresh_tokens"

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = _now_column()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
