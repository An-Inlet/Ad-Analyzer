"""Add owner-bound idempotent workspace signup receipts."""

import sqlalchemy as sa
from alembic import op

revision = "20261005_0021"
down_revision = "20261005_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customer_workspace_signups",
        sa.Column(
            "user_id",
            sa.String(32),
            sa.ForeignKey("customer_users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("key_digest", sa.String(64), primary_key=True),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("customer_workspace_signups")
