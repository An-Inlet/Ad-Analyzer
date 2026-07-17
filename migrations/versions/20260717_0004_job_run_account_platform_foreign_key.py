"""scope job runs to account and platform

Revision ID: 20260717_0004
Revises: 20260717_0003
Create Date: 2026-07-17 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection

revision: str = "20260717_0004"
down_revision: str | None = "20260717_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def cleanup_legacy_cross_platform_job_runs(connection: Connection) -> None:
    """Detach legacy rows that cannot satisfy the account/platform relationship."""
    connection.execute(
        sa.text(
            """
            UPDATE job_runs AS job_run
            SET account_id = NULL
            WHERE job_run.account_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM advertising_accounts AS account
                  WHERE account.id = job_run.account_id
                    AND account.platform = job_run.platform
              )
            """
        )
    )


def upgrade() -> None:
    cleanup_legacy_cross_platform_job_runs(op.get_bind())
    op.drop_constraint("job_runs_account_id_fkey", "job_runs", type_="foreignkey")
    op.create_foreign_key(
        "fk_job_runs_account_platform",
        "job_runs",
        "advertising_accounts",
        ["account_id", "platform"],
        ["id", "platform"],
        ondelete="RESTRICT",
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
