"""Add optional workspace-scoped, read-only Meta connections and staged imports."""

import sqlalchemy as sa
from alembic import op

revision = "20260906_0019"
down_revision = "20260906_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "meta_connections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("account_id", sa.Integer(), nullable=False, unique=True),
        sa.Column("external_account_id", sa.String(32), nullable=False, unique=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("encrypted_credentials", sa.Text(), nullable=False),
        sa.Column("conversion_action_type", sa.String(64), nullable=True),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("covered_from", sa.Date(), nullable=True),
        sa.Column("covered_through", sa.Date(), nullable=True),
        sa.Column("window_start", sa.Date(), nullable=True),
        sa.Column("window_end", sa.Date(), nullable=True),
        sa.Column("phase", sa.String(16), nullable=False),
        sa.Column("cursor", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.ForeignKeyConstraint(
            ["account_id", "workspace_id"],
            ["advertising_accounts.id", "advertising_accounts.workspace_id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("id", "workspace_id", name="uq_meta_connection_workspace"),
        sa.CheckConstraint("status IN ('connected','reconnect_required')", name="ck_meta_status"),
        sa.CheckConstraint("phase IN ('campaigns','adsets','insights')", name="ck_meta_sync_phase"),
    )
    op.create_table(
        "meta_oauth_states",
        sa.Column("digest", sa.String(64), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("actor_digest", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "meta_pending_grants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("actor_digest", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("encrypted_credentials", sa.Text(), nullable=False),
        sa.Column("accounts", sa.JSON(), nullable=False),
        sa.Column("cursor", sa.Text(), nullable=True),
        sa.UniqueConstraint("workspace_id", "actor_digest", name="uq_meta_grant_actor"),
    )
    op.create_table(
        "meta_staged_metrics",
        sa.Column(
            "connection_id",
            sa.Integer(),
            sa.ForeignKey("meta_connections.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "campaign_id",
            sa.Integer(),
            sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("metric_date", sa.Date(), primary_key=True),
        sa.Column("impressions", sa.Integer(), nullable=False),
        sa.Column("clicks", sa.Integer(), nullable=False),
        sa.Column("cost_micros", sa.BigInteger(), nullable=False),
        sa.Column("conversions", sa.Numeric(18, 6), nullable=False),
        sa.Column("conversion_value_micros", sa.BigInteger(), nullable=False),
    )
    op.create_table(
        "meta_audits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("actor_role", sa.String(32), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("meta_audits")
    op.drop_table("meta_staged_metrics")
    op.drop_table("meta_pending_grants")
    op.drop_table("meta_oauth_states")
    op.drop_table("meta_connections")
