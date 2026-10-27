"""SQLAlchemy models owned by the logistics module.

Other modules reference these rows by id only, never through ORM relationships.
"""

from sqlalchemy import CheckConstraint, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin
from app.core.geo import geo_point_type


class PartnerShop(IdMixin, TimestampMixin, Base):
    """A shop where cooks hand over meals for collection.

    Minimal for now so cook-to-shop assignments have a real foreign key; the shop module
    (Phase 2, item 2) builds on this table.
    """

    __tablename__ = "partner_shops"
    __table_args__ = (
        CheckConstraint("status in ('active', 'inactive')", name="status"),
        Index("ix_partner_shops_geom", "geom", postgresql_using="gist"),
    )

    name: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(16), default="active")
    geom: Mapped[object] = mapped_column(geo_point_type())
