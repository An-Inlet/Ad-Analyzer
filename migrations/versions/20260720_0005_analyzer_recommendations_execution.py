"""analyzer recommendations and execution audit tables

Revision ID: 20260720_0005
Revises: 20260717_0004
Create Date: 2026-07-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260720_0005"
down_revision: str | None = "20260717_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recommendations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "platform",
            sa.Enum("google_ads", "meta_ads", name="advertising_platform", native_enum=False),
            nullable=False,
        ),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=True),
        sa.Column("recommendation_type", sa.String(96), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("supporting_metrics", sa.JSON(), nullable=False),
        sa.Column("planned_action", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending_review",
                "approved",
                "rejected",
                "expired",
                "executed_dry_run",
                name="recommendation_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id", "platform"],
            ["advertising_accounts.id", "advertising_accounts.platform"],
            name="fk_recommendations_account_platform",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_recommendations_account_status", "recommendations", ["account_id", "status"]
    )
    op.create_table(
        "recommendation_audits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "recommendation_id",
            sa.Integer(),
            sa.ForeignKey("recommendations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("actor", sa.String(128), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_recommendation_audits_recommendation",
        "recommendation_audits",
        ["recommendation_id", "created_at"],
    )
    op.create_table(
        "execution_audits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "recommendation_id",
            sa.Integer(),
            sa.ForeignKey("recommendations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "planned",
                "dry_run_succeeded",
                "dry_run_failed",
                "blocked",
                name="execution_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("dry_run", sa.Boolean(), nullable=False),
        sa.Column("validation_errors", sa.JSON(), nullable=False),
        sa.Column("rollback_instructions", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_execution_audits_idempotency_key"),
    )


def downgrade() -> None:
    op.drop_table("execution_audits")
    op.drop_index("ix_recommendation_audits_recommendation", table_name="recommendation_audits")
    op.drop_table("recommendation_audits")
    op.drop_index("ix_recommendations_account_status", table_name="recommendations")
    op.drop_table("recommendations")
