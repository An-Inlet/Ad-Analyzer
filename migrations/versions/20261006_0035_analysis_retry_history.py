"""Preserve sanitized failed-attempt history for scoped local analysis retries."""

import sqlalchemy as sa
from alembic import op

revision = "20261006_0035"
down_revision = "20261006_0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "analysis_runs", sa.Column("retry_history", sa.JSON(), nullable=False, server_default="[]")
    )
    op.alter_column("analysis_runs", "retry_history", server_default=None)
    op.add_column(
        "analysis_runs", sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0")
    )
    op.alter_column("analysis_runs", "retry_count", server_default=None)


def downgrade() -> None:
    op.drop_column("analysis_runs", "retry_count")
    op.drop_column("analysis_runs", "retry_history")
