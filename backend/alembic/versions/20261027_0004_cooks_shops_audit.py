"""cooks profiles addresses shop assignments audit log

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geography

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def point_4326() -> Geography:
    # Spatial indexes are created explicitly below (GiST), not by geoalchemy2.
    return Geography(geometry_type="POINT", srid=4326, spatial_index=False)


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("subject_type", sa.String(length=32), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(length=64), nullable=True),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("detail", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_log")),
    )
    op.create_index(op.f("ix_audit_log_actor_id"), "audit_log", ["actor_id"], unique=False)
    op.create_index(
        "ix_audit_log_subject_created_at",
        "audit_log",
        ["subject_type", "subject_id", "created_at"],
        unique=False,
    )
    op.create_table(
        "partner_shops",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("geom", point_4326(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status in ('active', 'inactive')", name=op.f("ck_partner_shops_status")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_partner_shops")),
    )
    op.create_index(
        "ix_partner_shops_geom", "partner_shops", ["geom"], unique=False, postgresql_using="gist"
    )
    op.create_table(
        "cook_profiles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("bio", sa.String(length=1000), nullable=True),
        sa.Column("approval_status", sa.String(length=16), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.String(length=500), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("suspension_reason", sa.String(length=500), nullable=True),
        sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "approval_status in ('pending', 'approved', 'suspended', 'rejected')",
            name=op.f("ck_cook_profiles_status"),
        ),
        sa.ForeignKeyConstraint(
            ["approved_by"],
            ["users.id"],
            name=op.f("fk_cook_profiles_approved_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_cook_profiles_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cook_profiles")),
        sa.UniqueConstraint("user_id", name=op.f("uq_cook_profiles_user_id")),
    )
    op.create_index(
        op.f("ix_cook_profiles_approval_status"), "cook_profiles", ["approval_status"], unique=False
    )
    op.create_table(
        "cook_addresses",
        sa.Column("cook_id", sa.Uuid(), nullable=False),
        sa.Column("line1", sa.String(length=200), nullable=False),
        sa.Column("line2", sa.String(length=200), nullable=True),
        sa.Column("city", sa.String(length=80), nullable=False),
        sa.Column("pincode", sa.String(length=6), nullable=False),
        sa.Column("geom", point_4326(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["cook_id"],
            ["cook_profiles.id"],
            name=op.f("fk_cook_addresses_cook_id_cook_profiles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("cook_id", name=op.f("pk_cook_addresses")),
    )
    op.create_index(
        "ix_cook_addresses_geom", "cook_addresses", ["geom"], unique=False, postgresql_using="gist"
    )
    op.create_table(
        "cook_shop_assignments",
        sa.Column("cook_id", sa.Uuid(), nullable=False),
        sa.Column("shop_id", sa.Uuid(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("assigned_by", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["assigned_by"],
            ["users.id"],
            name=op.f("fk_cook_shop_assignments_assigned_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["cook_id"],
            ["cook_profiles.id"],
            name=op.f("fk_cook_shop_assignments_cook_id_cook_profiles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["shop_id"],
            ["partner_shops.id"],
            name=op.f("fk_cook_shop_assignments_shop_id_partner_shops"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cook_shop_assignments")),
    )
    op.create_index(
        op.f("ix_cook_shop_assignments_cook_id"), "cook_shop_assignments", ["cook_id"], unique=False
    )
    op.create_index(
        op.f("ix_cook_shop_assignments_shop_id"), "cook_shop_assignments", ["shop_id"], unique=False
    )
    op.create_index(
        "uq_cook_shop_assignments_active_cook",
        "cook_shop_assignments",
        ["cook_id"],
        unique=True,
        postgresql_where=sa.text("active"),
        sqlite_where=sa.text("active"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_cook_shop_assignments_active_cook",
        table_name="cook_shop_assignments",
        postgresql_where=sa.text("active"),
        sqlite_where=sa.text("active"),
    )
    op.drop_index(op.f("ix_cook_shop_assignments_shop_id"), table_name="cook_shop_assignments")
    op.drop_index(op.f("ix_cook_shop_assignments_cook_id"), table_name="cook_shop_assignments")
    op.drop_table("cook_shop_assignments")
    op.drop_index("ix_cook_addresses_geom", table_name="cook_addresses", postgresql_using="gist")
    op.drop_table("cook_addresses")
    op.drop_index(op.f("ix_cook_profiles_approval_status"), table_name="cook_profiles")
    op.drop_table("cook_profiles")
    op.drop_index("ix_partner_shops_geom", table_name="partner_shops", postgresql_using="gist")
    op.drop_table("partner_shops")
    op.drop_index("ix_audit_log_subject_created_at", table_name="audit_log")
    op.drop_index(op.f("ix_audit_log_actor_id"), table_name="audit_log")
    op.drop_table("audit_log")
