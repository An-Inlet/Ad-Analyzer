"""add the all-data-syncs master control

Revision ID: 20260821_0016
Revises: 20260820_0015
Create Date: 2026-08-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260821_0016"
down_revision: str | None = "20260820_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def platform_controls() -> sa.TableClause:
    return sa.table(
        "platform_automation_controls",
        sa.column("key", sa.String()),
        sa.column("enabled", sa.Boolean()),
        sa.column("updated_by", sa.String()),
    )


def upgrade() -> None:
    op.bulk_insert(
        platform_controls(),
        [
            {
                "key": "all_data_syncs",
                "enabled": True,
                "updated_by": "migration",
            }
        ],
    )


def downgrade() -> None:
    controls = platform_controls()
    op.execute(controls.delete().where(controls.c.key == "all_data_syncs"))
