"""add job run indexes for read-only sync status queries

Revision ID: 20260717_0003
Revises: 20260715_0002
Create Date: 2026-07-17 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260717_0003"
down_revision: str | None = "20260715_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_job_runs_account_platform_started_id",
        "job_runs",
        ["account_id", "platform", sa.text("started_at DESC"), sa.text("id DESC")],
        postgresql_where=sa.text("account_id IS NOT NULL"),
    )
    op.create_index(
        "ix_job_runs_account_platform_status_finished",
        "job_runs",
        ["account_id", "platform", "status", sa.text("finished_at DESC")],
        postgresql_where=sa.text("account_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_job_runs_account_platform_status_finished", table_name="job_runs")
    op.drop_index("ix_job_runs_account_platform_started_id", table_name="job_runs")
