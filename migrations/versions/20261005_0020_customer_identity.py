"""Add customer identity, shared revocable sessions and distinct memberships."""

import sqlalchemy as sa
from alembic import op

revision = "20261005_0020"
down_revision = "20260906_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customer_users",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("issuer", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(128), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.UniqueConstraint("issuer", "subject", name="uq_customer_identity"),
        sa.CheckConstraint("status IN ('active', 'suspended')", name="ck_customer_user_status"),
    )
    op.create_table(
        "customer_sessions",
        sa.Column("digest", sa.String(64), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(32),
            sa.ForeignKey("customer_users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("csrf_digest", sa.String(64), nullable=False),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),
        sa.Column("authenticated_at", sa.BigInteger(), nullable=False),
        sa.Column("revoked_at", sa.BigInteger()),
    )
    op.create_index("ix_customer_sessions_user_id", "customer_sessions", ["user_id"])
    op.create_index("ix_customer_sessions_expires_at", "customer_sessions", ["expires_at"])
    op.create_table(
        "customer_token_exchanges",
        sa.Column("digest", sa.String(64), primary_key=True),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),
    )
    op.create_index(
        "ix_customer_token_exchanges_expires_at", "customer_token_exchanges", ["expires_at"]
    )
    op.create_table(
        "customer_memberships",
        sa.Column(
            "user_id",
            sa.String(32),
            sa.ForeignKey("customer_users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.CheckConstraint("role IN ('owner','admin','analyst','viewer')", name="ck_customer_role"),
        sa.CheckConstraint(
            "status IN ('active','suspended')", name="ck_customer_membership_status"
        ),
    )


def downgrade() -> None:
    op.drop_table("customer_memberships")
    op.drop_table("customer_token_exchanges")
    op.drop_table("customer_sessions")
    op.drop_table("customer_users")
