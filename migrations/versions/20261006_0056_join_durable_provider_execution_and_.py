"""Join durable provider execution and privacy measurement histories

Revision ID: 20261006_0056
Revises: 20261006_0048, 20261006_0054
Create Date: 2026-10-06 04:29:41.779933

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = '20261006_0056'
down_revision: str | Sequence[str] | None = ('20261006_0048', '20261006_0054')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
