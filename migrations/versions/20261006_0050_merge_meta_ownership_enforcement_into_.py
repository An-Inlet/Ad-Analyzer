"""Merge Meta ownership enforcement into integrated customer schema

Revision ID: 20261006_0050
Revises: 20261006_0047, 20261006_0049
Create Date: 2026-10-06 04:18:00.722705

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = '20261006_0050'
down_revision: str | Sequence[str] | None = ('20261006_0047', '20261006_0049')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
