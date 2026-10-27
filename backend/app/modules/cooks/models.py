"""SQLAlchemy models owned by the cooks module.

Other modules reference these rows by id only, never through ORM relationships.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin, utcnow
from app.core.geo import geo_point_type


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    SUSPENDED = "suspended"
    REJECTED = "rejected"


STATUS_VALUES = ", ".join(f"'{s.value}'" for s in ApprovalStatus)


class CookProfile(IdMixin, TimestampMixin, Base):
    __tablename__ = "cook_profiles"
    __table_args__ = (CheckConstraint(f"approval_status in ({STATUS_VALUES})", name="status"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    display_name: Mapped[str] = mapped_column(String(80))
    bio: Mapped[str | None] = mapped_column(String(1000))
    approval_status: Mapped[str] = mapped_column(
        String(16), default=ApprovalStatus.PENDING.value, index=True
    )
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Kept after a resubmission so the admin can see why the cook was rejected last time.
    rejection_reason: Mapped[str | None] = mapped_column(String(500))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    suspension_reason: Mapped[str | None] = mapped_column(String(500))
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CookAddress(TimestampMixin, Base):
    """The cook's home address (ADR 0003). Read it only through cooks/address.py.

    Nothing customer-visible holds a foreign key to this table.
    """

    __tablename__ = "cook_addresses"
    __table_args__ = (Index("ix_cook_addresses_geom", "geom", postgresql_using="gist"),)

    cook_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cook_profiles.id", ondelete="CASCADE"), primary_key=True
    )
    line1: Mapped[str] = mapped_column(String(200))
    line2: Mapped[str | None] = mapped_column(String(200))
    city: Mapped[str] = mapped_column(String(80))
    pincode: Mapped[str] = mapped_column(String(6))
    geom: Mapped[object] = mapped_column(geo_point_type())


class CookShopAssignment(IdMixin, TimestampMixin, Base):
    """Which partner shop a cook hands meals over at. At most one active row per cook."""

    __tablename__ = "cook_shop_assignments"
    __table_args__ = (
        Index(
            "uq_cook_shop_assignments_active_cook",
            "cook_id",
            unique=True,
            postgresql_where=text("active"),
            sqlite_where=text("active"),
        ),
    )

    cook_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cook_profiles.id", ondelete="CASCADE"), index=True
    )
    # partner_shops belongs to logistics; the link is database-level only, so cooks never
    # imports logistics code (logistics depends on cooks, not the other way round).
    shop_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("partner_shops.id", ondelete="RESTRICT"), index=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
