"""Private media, immutable campaign revisions and explicit Meta grant generation."""

import sqlalchemy as sa
from alembic import op

revision = "20261006_0037"
down_revision = "20261006_0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "meta_connections",
        sa.Column("generation", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_table(
        "customer_media_objects",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("mime", sa.String(32), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "sha256", name="uq_media_workspace_content"),
    )
    op.create_table(
        "customer_campaign_drafts",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.UniqueConstraint("id", "workspace_id", name="uq_campaign_draft_scope"),
    )
    op.create_table(
        "customer_campaign_revisions",
        sa.Column("draft_id", sa.String(32), primary_key=True),
        sa.Column("revision", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("artifact", sa.JSON(), nullable=False),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_by", sa.String(32)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["draft_id", "workspace_id"],
            ["customer_campaign_drafts.id", "customer_campaign_drafts.workspace_id"],
            ondelete="CASCADE",
        ),
    )


def downgrade() -> None:
    op.drop_table("customer_campaign_revisions")
    op.drop_table("customer_campaign_drafts")
    op.drop_table("customer_media_objects")
    op.drop_column("meta_connections", "generation")
