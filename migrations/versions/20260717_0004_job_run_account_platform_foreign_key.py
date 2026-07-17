"""scope job runs to account and platform

Revision ID: 20260717_0004
Revises: 20260717_0003
Create Date: 2026-07-17 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260717_0004"
down_revision: str | None = "20260717_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("job_runs_account_id_fkey", "job_runs", type_="foreignkey")
    op.create_foreign_key(
        "fk_job_runs_account_platform",
        "job_runs",
        "advertising_accounts",
        ["account_id", "platform"],
        ["id", "platform"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_job_runs_account_platform", "job_runs", type_="foreignkey")
    op.create_foreign_key(
        "job_runs_account_id_fkey",
        "job_runs",
        "advertising_accounts",
        ["account_id"],
        ["id"],
        ondelete="SET NULL",
    )
