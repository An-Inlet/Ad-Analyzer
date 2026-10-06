"""Durable CRM account quota and encrypted acknowledged pagination."""

import sqlalchemy as sa
from alembic import op

revision = "20261006_0038"
down_revision = "20261006_0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customer_context_quotas",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("fence", sa.String(32)),
    )
    op.create_table(
        "customer_context_checkpoints",
        sa.Column(
            "connection_id",
            sa.String(32),
            sa.ForeignKey("customer_source_connections.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("grant_digest", sa.String(64), nullable=False),
        sa.Column("encrypted_progress", sa.Text(), nullable=False),
        sa.Column("state", sa.String(24), nullable=False),
        sa.Column("fence", sa.String(32)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("ack_digest", sa.String(64)),
    )


def downgrade() -> None:
    op.drop_table("customer_context_checkpoints")
    op.drop_table("customer_context_quotas")
