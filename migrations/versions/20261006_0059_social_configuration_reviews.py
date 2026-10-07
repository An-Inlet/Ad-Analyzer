"""Exact no-DSA social configuration review and customer confirmation."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261006_0059"
down_revision: str | Sequence[str] | None = "20261006_0057"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "customer_social_configuration_reviews",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("integration_id", sa.Integer(), nullable=False),
        sa.Column("draft_id", sa.String(32), nullable=False),
        sa.Column("source_revision", sa.Integer(), nullable=False),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column("document", sa.JSON(), nullable=False),
        sa.Column(
            "created_by",
            sa.String(32),
            sa.ForeignKey("customer_users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("id", "workspace_id", name="uq_social_config_review_scope"),
        sa.ForeignKeyConstraint(
            ["account_id", "workspace_id", "integration_id"],
            [
                "advertising_accounts.id",
                "advertising_accounts.workspace_id",
                "advertising_accounts.connection_id",
            ],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["draft_id", "source_revision", "workspace_id"],
            [
                "customer_campaign_revisions.draft_id",
                "customer_campaign_revisions.revision",
                "customer_campaign_revisions.workspace_id",
            ],
            ondelete="RESTRICT",
        ),
    )
    op.create_table(
        "customer_social_configuration_approvals",
        sa.Column("review_id", sa.String(32), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("review_digest", sa.String(64), nullable=False),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column(
            "actor",
            sa.String(32),
            sa.ForeignKey("customer_users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["review_id", "workspace_id"],
            [
                "customer_social_configuration_reviews.id",
                "customer_social_configuration_reviews.workspace_id",
            ],
            ondelete="RESTRICT",
        ),
    )


def downgrade() -> None:
    op.drop_table("customer_social_configuration_approvals")
    op.drop_table("customer_social_configuration_reviews")
