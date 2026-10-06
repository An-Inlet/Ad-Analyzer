"""Retain sanitized original Google synchronous response evidence."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261006_0066"
down_revision: str | Sequence[str] | None = "20261006_0060"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "google_original_completions",
        sa.Column("attempt_id", sa.String(32), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("fence", sa.String(32), nullable=False),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column("document", sa.JSON(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["attempt_id", "workspace_id"],
            ["provider_execution_attempts.id", "provider_execution_attempts.workspace_id"],
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("fence", name="uq_google_completion_fence"),
    )


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM google_original_completions")):
        raise RuntimeError("original response evidence cannot be discarded")
    op.drop_table("google_original_completions")
