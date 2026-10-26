"""enable postgis for partner-shop geography

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-26
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")


def downgrade() -> None:
    # Deliberately a no-op. The postgis/postgis image installs the extension (plus topology and
    # tiger geocoder, which depend on it) at database creation, so this migration doesn't own it
    # and dropping it would fail or take unrelated objects with it.
    pass
