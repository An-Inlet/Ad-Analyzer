"""Resumable owned Meta child-performance windows."""

import sqlalchemy as sa
from alembic import op

revision = "20261006_0041"
down_revision = "20261006_0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "meta_detail_checkpoints",
        sa.Column("connection_id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("integration_id", sa.Integer(), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("window_start", sa.Date(), nullable=False),
        sa.Column("window_end", sa.Date(), nullable=False),
        sa.Column("phase", sa.String(24), nullable=False),
        sa.Column("cursor", sa.Text()),
        sa.Column("seen_cursors", sa.JSON(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("byte_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["connection_id", "workspace_id"],
            ["meta_connections.id", "meta_connections.workspace_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["account_id", "workspace_id"],
            ["advertising_accounts.id", "advertising_accounts.workspace_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["integration_id", "workspace_id"],
            ["workspace_integrations.id", "workspace_integrations.workspace_id"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "phase IN ('ads','adset_insights','ad_insights','complete')",
            name="ck_meta_detail_phase",
        ),
        sa.CheckConstraint("page_count >= 0 AND page_count <= 300", name="ck_meta_detail_pages"),
        sa.CheckConstraint("row_count >= 0 AND row_count <= 30000", name="ck_meta_detail_rows"),
        sa.CheckConstraint(
            "byte_count >= 0 AND byte_count <= 16000000", name="ck_meta_detail_bytes"
        ),
        sa.CheckConstraint("window_end >= window_start", name="ck_meta_detail_window"),
    )
    op.create_table(
        "meta_detail_staged_pages",
        sa.Column(
            "connection_id",
            sa.Integer(),
            sa.ForeignKey("meta_detail_checkpoints.connection_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("page_number", sa.Integer(), primary_key=True),
        sa.Column("payload", sa.JSON(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("meta_detail_staged_pages")
    op.drop_table("meta_detail_checkpoints")
