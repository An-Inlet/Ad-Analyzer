"""Non-emitting derived candidate read queue; erasable with source/privacy changes."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261006_0062"
down_revision: str | Sequence[str] | None = "20261006_0060"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "optimization_candidate_jobs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("environment", sa.String(16), nullable=False),
        sa.Column("publication_id", sa.String(32), nullable=False),
        sa.Column("attempt_id", sa.String(32)),
        sa.Column(
            "actor_id",
            sa.String(),
            sa.ForeignKey("customer_users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "auth_session_digest",
            sa.String(64),
            sa.ForeignKey("customer_sessions.digest", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("input_digest", sa.String(64), nullable=False),
        sa.Column("work", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("fence", sa.String(32)),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("id", "workspace_id", name="uq_candidate_job_owner"),
        sa.UniqueConstraint("workspace_id", "input_digest", name="uq_candidate_job_input"),
        sa.ForeignKeyConstraint(
            ["publication_id", "workspace_id"],
            [
                "commerce_measurement_publications.id",
                "commerce_measurement_publications.workspace_id",
            ],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id", "workspace_id"],
            ["provider_execution_attempts.id", "provider_execution_attempts.workspace_id"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "environment IN ('contract_test','live')", name="ck_candidate_environment"
        ),
        sa.CheckConstraint(
            "state IN ('pending','claimed','completed','blocked','canceled') AND attempts >= 0",
            name="ck_candidate_job_state",
        ),
    )
    op.create_table(
        "optimization_candidate_results",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("job_id", sa.String(32), nullable=False),
        sa.Column("input_digest", sa.String(64), nullable=False),
        sa.Column("policy_digest", sa.String(64), nullable=False),
        sa.Column("evidence_digest", sa.String(64), nullable=False),
        sa.Column("decision_digest", sa.String(64), nullable=False),
        sa.Column("decision", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("id", "workspace_id", name="uq_candidate_result_owner"),
        sa.UniqueConstraint("job_id", name="uq_candidate_result_job"),
        sa.ForeignKeyConstraint(
            ["job_id", "workspace_id"],
            ["optimization_candidate_jobs.id", "optimization_candidate_jobs.workspace_id"],
            ondelete="CASCADE",
        ),
    )


def downgrade() -> None:
    op.drop_table("optimization_candidate_results")
    op.drop_table("optimization_candidate_jobs")
