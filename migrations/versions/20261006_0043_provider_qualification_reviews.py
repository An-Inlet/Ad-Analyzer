"""provider_qualification_reviews

Revision ID: 20261006_0043
Revises: 20261006_0040
Create Date: 2026-10-06 03:18:10.290926

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261006_0043"
down_revision: str | Sequence[str] | None = "20261006_0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_campaign_revision_scope",
        "customer_campaign_revisions",
        ["draft_id", "revision", "workspace_id"],
    )
    op.create_table(
        "provider_qualifications",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("integration_id", sa.Integer(), nullable=False),
        sa.Column("draft_id", sa.String(length=32), nullable=False),
        sa.Column("source_revision", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=24), nullable=False),
        sa.Column("api_version", sa.String(length=16), nullable=False),
        sa.Column("binding_digest", sa.String(length=64), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id", "workspace_id", "integration_id"],
            [
                "advertising_accounts.id",
                "advertising_accounts.workspace_id",
                "advertising_accounts.connection_id",
            ],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["customer_users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["draft_id", "source_revision", "workspace_id"],
            [
                "customer_campaign_revisions.draft_id",
                "customer_campaign_revisions.revision",
                "customer_campaign_revisions.workspace_id",
            ],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "workspace_id", name="uq_provider_qualification_scope"),
    )
    op.create_table(
        "provider_reviews",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("qualification_id", sa.String(length=32), nullable=False),
        sa.Column("draft_id", sa.String(length=32), nullable=False),
        sa.Column("source_revision", sa.Integer(), nullable=False),
        sa.Column("review_digest", sa.String(length=64), nullable=False),
        sa.Column("plan_digest", sa.String(length=64), nullable=False),
        sa.Column("review", sa.JSON(), nullable=False),
        sa.Column("plan", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["customer_users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["draft_id", "source_revision", "workspace_id"],
            [
                "customer_campaign_revisions.draft_id",
                "customer_campaign_revisions.revision",
                "customer_campaign_revisions.workspace_id",
            ],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["qualification_id", "workspace_id"],
            ["provider_qualifications.id", "provider_qualifications.workspace_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "workspace_id", name="uq_provider_review_scope"),
        sa.UniqueConstraint("workspace_id", "plan_digest", name="uq_provider_review_plan"),
    )
    op.create_table(
        "provider_review_approvals",
        sa.Column("review_id", sa.String(length=32), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("review_digest", sa.String(length=64), nullable=False),
        sa.Column("plan_digest", sa.String(length=64), nullable=False),
        sa.Column("actor", sa.String(length=32), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor"], ["customer_users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["review_id", "workspace_id"],
            ["provider_reviews.id", "provider_reviews.workspace_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("review_id"),
    )


def downgrade() -> None:
    op.drop_table("provider_review_approvals")
    op.drop_table("provider_reviews")
    op.drop_table("provider_qualifications")
    op.drop_constraint("uq_campaign_revision_scope", "customer_campaign_revisions", type_="unique")
