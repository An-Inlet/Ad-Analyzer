"""Owned receipt assessments erased with their aggregate measurement publication."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261006_0057"
down_revision: str | Sequence[str] | None = "20261006_0056"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "action_outcome_assessments",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("attempt_id", sa.String(32), nullable=False),
        sa.Column("receipt_id", sa.String(32), nullable=False),
        sa.Column("receipt_sequence", sa.Integer(), nullable=False),
        sa.Column("receipt_digest", sa.String(64), nullable=False),
        sa.Column("projection_digest", sa.String(64), nullable=False),
        sa.Column("publication_id", sa.String(32), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("privacy_epoch", sa.Integer(), nullable=False),
        sa.Column("environment", sa.String(16), nullable=False),
        sa.Column("policy_id", sa.String(64), nullable=False),
        sa.Column("policy_digest", sa.String(64), nullable=False),
        sa.Column("input_digest", sa.String(64), nullable=False),
        sa.Column("assessment_digest", sa.String(64), nullable=False),
        sa.Column("assessment", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("id", "workspace_id", name="uq_outcome_assessment_owner"),
        sa.UniqueConstraint("workspace_id", "input_digest", name="uq_outcome_assessment_input"),
        sa.ForeignKeyConstraint(
            ["attempt_id", "workspace_id"],
            ["provider_execution_attempts.id", "provider_execution_attempts.workspace_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["receipt_id", "workspace_id"],
            ["provider_execution_receipts.id", "provider_execution_receipts.workspace_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["publication_id", "workspace_id"],
            [
                "commerce_measurement_publications.id",
                "commerce_measurement_publications.workspace_id",
            ],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "generation > 0 AND privacy_epoch > 0 AND receipt_sequence > 0",
            name="ck_outcome_assessment_fences",
        ),
        sa.CheckConstraint(
            "environment IN ('contract_test','live')", name="ck_outcome_assessment_environment"
        ),
    )


def downgrade() -> None:
    op.drop_table("action_outcome_assessments")
