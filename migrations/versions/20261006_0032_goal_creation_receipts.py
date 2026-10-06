"""Customer-scoped atomic goal creation receipts."""

import sqlalchemy as sa
from alembic import op

revision = "20261006_0032"
down_revision = "20261006_0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customer_goal_creations",
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(32), nullable=False),
        sa.Column("request_key", sa.String(128), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("goal_id", sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint("workspace_id", "user_id", "request_key"),
        sa.ForeignKeyConstraint(
            ["goal_id", "workspace_id"],
            ["customer_goals.id", "customer_goals.workspace_id"],
            ondelete="CASCADE",
        ),
    )


def downgrade() -> None:
    op.drop_table("customer_goal_creations")
