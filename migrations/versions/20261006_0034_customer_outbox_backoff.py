"""Durable analysis delivery backoff across scheduler restarts."""

import sqlalchemy as sa
from alembic import op

revision = "20261006_0034"
down_revision = "20261006_0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "google_customer_import_completions",
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("google_customer_import_completions", "next_attempt_at")
