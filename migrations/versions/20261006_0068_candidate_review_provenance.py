"""Minimal candidate-review provenance without retaining erased measurement payloads."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261006_0068"
down_revision: str | Sequence[str] | None = "20261006_0062"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "provider_execution_reviews",
        sa.Column(
            "candidate_provenance_required", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.create_table(
        "optimization_candidate_reviews",
        sa.Column("review_id", sa.String(32), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("candidate_result_id", sa.String(32)),
        sa.Column("candidate_workspace_id", sa.Integer()),
        sa.Column(
            "actor_id",
            sa.String(),
            sa.ForeignKey("customer_users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("original_session_digest", sa.String(64), nullable=False),
        sa.Column("environment", sa.String(16), nullable=False),
        *[
            sa.Column(name, sa.String(64), nullable=False)
            for name in (
                "candidate_digest",
                "input_digest",
                "selection_digest",
                "policy_digest",
                "evidence_digest",
                "source_digest",
                "review_digest",
                "plan_digest",
            )
        ],
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("review_id", "workspace_id", name="uq_candidate_review_scope"),
        sa.UniqueConstraint(
            "workspace_id", "candidate_digest", "review_digest", name="uq_candidate_review_decision"
        ),
        sa.ForeignKeyConstraint(
            ["review_id", "workspace_id"],
            ["provider_execution_reviews.id", "provider_execution_reviews.workspace_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_result_id", "candidate_workspace_id"],
            ["optimization_candidate_results.id", "optimization_candidate_results.workspace_id"],
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "(candidate_result_id IS NULL AND candidate_workspace_id IS NULL) OR "
            "(candidate_result_id IS NOT NULL AND candidate_workspace_id IS NOT NULL "
            "AND candidate_workspace_id = workspace_id)",
            name="ck_candidate_review_optional_scope",
        ),
        sa.CheckConstraint(
            "environment IN ('contract_test','live')", name="ck_candidate_review_environment"
        ),
    )


def downgrade() -> None:
    db = op.get_bind()
    if db.scalar(sa.text("SELECT count(*) FROM optimization_candidate_reviews")) or db.scalar(
        sa.text(
            "SELECT count(*) FROM provider_execution_reviews WHERE candidate_provenance_required"
        )
    ):
        raise RuntimeError("candidate review forward fences cannot be discarded")
    op.drop_table("optimization_candidate_reviews")
    op.drop_column("provider_execution_reviews", "candidate_provenance_required")
