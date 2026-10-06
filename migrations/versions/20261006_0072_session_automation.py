"""Separate original-session automatic admissions; never reinterpret exact approval."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261006_0072"
down_revision: str | Sequence[str] | None = "20261006_0068"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "session_automation_runs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column(
            "actor_id",
            sa.String(),
            sa.ForeignKey("customer_users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("original_session_digest", sa.String(64), nullable=False),
        sa.Column("environment", sa.String(16), nullable=False),
        *[
            sa.Column(n, sa.String(32), nullable=False)
            for n in ("mandate_id", "consent_id", "ledger_id", "policy_family", "policy_id")
        ],
        *[sa.Column(n, sa.String(64), nullable=False) for n in ("mandate_digest", "policy_digest")],
        sa.Column("mandate_revision", sa.Integer(), nullable=False),
        sa.Column("policy_revision", sa.Integer(), nullable=False),
        *[
            sa.Column(n, sa.DateTime(timezone=True), nullable=False)
            for n in ("created_at", "expires_at", "next_due_at")
        ],
        sa.Column("stopped_at", sa.DateTime(timezone=True)),
        sa.Column(
            "stopped_by", sa.String(), sa.ForeignKey("customer_users.id", ondelete="RESTRICT")
        ),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("reason", sa.String(48), nullable=False),
        sa.UniqueConstraint("id", "workspace_id", name="uq_session_automation_scope"),
        sa.ForeignKeyConstraint(
            ["mandate_id", "workspace_id"],
            ["provider_execution_mandates.id", "provider_execution_mandates.workspace_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["mandate_id", "mandate_revision", "workspace_id"],
            [
                "provider_execution_revisions.mandate_id",
                "provider_execution_revisions.revision",
                "provider_execution_revisions.workspace_id",
            ],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["consent_id", "workspace_id"],
            ["provider_execution_consents.id", "provider_execution_consents.workspace_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["ledger_id", "workspace_id", "environment"],
            [
                "provider_period_ledgers.id",
                "provider_period_ledgers.workspace_id",
                "provider_period_ledgers.environment",
            ],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("environment IN ('contract_test','live')", name="ck_auto_environment"),
        sa.CheckConstraint(
            "mandate_revision > 0 AND policy_revision > 0", name="ck_auto_revisions"
        ),
        sa.CheckConstraint("expires_at > created_at", name="ck_auto_lifetime"),
    )
    op.create_table(
        "provider_automatic_decisions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column(
            "actor_id",
            sa.String(),
            sa.ForeignKey("customer_users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("environment", sa.String(16), nullable=False),
        *[
            sa.Column(n, sa.String(32), nullable=False)
            for n in (
                "session_run_id",
                "review_id",
                "ledger_id",
                "policy_family",
                "producer_family",
            )
        ],
        *[
            sa.Column(n, sa.String(64), nullable=False)
            for n in (
                "account_identity_digest",
                "policy_digest",
                "epoch_digest",
                "review_digest",
                "plan_digest",
                "candidate_digest",
                "evidence_digest",
            )
        ],
        sa.Column("budget_owner_key", sa.String(256), nullable=False),
        sa.Column("admitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("id", "workspace_id", name="uq_automatic_decision_scope"),
        sa.UniqueConstraint("review_id", name="uq_automatic_decision_review"),
        sa.UniqueConstraint(
            "workspace_id",
            "environment",
            "ledger_id",
            "account_identity_digest",
            "budget_owner_key",
            "policy_family",
            "epoch_digest",
            name="uq_automatic_semantic_epoch",
        ),
        sa.ForeignKeyConstraint(
            ["session_run_id", "workspace_id"],
            ["session_automation_runs.id", "session_automation_runs.workspace_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["review_id", "workspace_id"],
            ["provider_execution_reviews.id", "provider_execution_reviews.workspace_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["ledger_id", "workspace_id", "environment"],
            [
                "provider_period_ledgers.id",
                "provider_period_ledgers.workspace_id",
                "provider_period_ledgers.environment",
            ],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("environment IN ('contract_test','live')", name="ck_auto_decision_env"),
        sa.CheckConstraint("expires_at > admitted_at", name="ck_auto_decision_lifetime"),
    )
    op.add_column(
        "provider_execution_reviews",
        sa.Column(
            "automatic_authority_required", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    with op.batch_alter_table("provider_execution_runs") as batch:
        batch.add_column(
            sa.Column(
                "authority_kind",
                sa.String(32),
                nullable=False,
                server_default="customer_exact_approval",
            )
        )
        batch.add_column(
            sa.Column("automatic_decision_id", sa.String(32), server_default=sa.text("NULL"))
        )
        batch.create_foreign_key(
            "fk_provider_run_auto_scope",
            "provider_automatic_decisions",
            ["automatic_decision_id", "workspace_id"],
            ["id", "workspace_id"],
            ondelete="RESTRICT",
        )
        batch.create_check_constraint(
            "ck_provider_run_authority",
            "(authority_kind = 'customer_exact_approval' AND automatic_decision_id IS NULL) OR "
            "(authority_kind = 'mandate_automatic_decision' AND automatic_decision_id IS NOT NULL)",
        )


def downgrade() -> None:
    db = op.get_bind()
    if (
        any(
            db.scalar(sa.text(f"SELECT count(*) FROM {table}"))
            for table in ("session_automation_runs", "provider_automatic_decisions")
        )
        or db.scalar(
            sa.text(
                "SELECT count(*) FROM provider_execution_reviews WHERE automatic_authority_required"
            )
        )
        or db.scalar(
            sa.text(
                "SELECT count(*) FROM provider_execution_runs "
                "WHERE authority_kind != 'customer_exact_approval'"
            )
        )
    ):
        raise RuntimeError("automatic authority and semantic consumption cannot be discarded")
    with op.batch_alter_table("provider_execution_runs") as batch:
        batch.drop_constraint("ck_provider_run_authority", type_="check")
        batch.drop_constraint("fk_provider_run_auto_scope", type_="foreignkey")
        batch.drop_column("automatic_decision_id")
        batch.drop_column("authority_kind")
    op.drop_column("provider_execution_reviews", "automatic_authority_required")
    op.drop_table("provider_automatic_decisions")
    op.drop_table("session_automation_runs")
