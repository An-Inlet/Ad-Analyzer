"""add workspace analysis cadence runs

Revision ID: 20260808_0011
Revises: 20260808_0010
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260808_0011"
down_revision: str | None = "20260808_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_job_runs_id_workspace",
        "job_runs",
        ["id", "workspace_id"],
    )
    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("account_id", sa.Integer()),
        sa.Column("source_job_run_id", sa.Integer()),
        sa.Column("run_key", sa.String(160), nullable=False),
        sa.Column("cadence", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("schedule_policy_version", sa.String(16), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metric_date_from", sa.Date(), nullable=False),
        sa.Column("metric_date_to", sa.Date(), nullable=False),
        sa.Column("outcome_date_from", sa.Date(), nullable=False),
        sa.Column("outcome_date_to", sa.Date(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("accounts_analyzed", sa.Integer(), nullable=False),
        sa.Column("findings_count", sa.Integer(), nullable=False),
        sa.Column("high_severity_findings_count", sa.Integer(), nullable=False),
        sa.Column("outcome_analysis_ready", sa.Boolean(), nullable=False),
        sa.Column("outcome_campaign_count", sa.Integer(), nullable=False),
        sa.Column("attributed_journey_count", sa.Integer(), nullable=False),
        sa.Column("unattributed_journey_count", sa.Integer(), nullable=False),
        sa.Column("blocking_reasons", sa.JSON(), nullable=False),
        sa.Column("error_code", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id", "workspace_id"],
            ["advertising_accounts.id", "advertising_accounts.workspace_id"],
            name="fk_analysis_runs_account_workspace",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_job_run_id", "workspace_id"],
            ["job_runs.id", "job_runs.workspace_id"],
            name="fk_analysis_runs_source_job_workspace",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "run_key",
            name="uq_analysis_runs_workspace_key",
        ),
        sa.CheckConstraint(
            "metric_date_to >= metric_date_from",
            name="ck_analysis_runs_metric_window",
        ),
        sa.CheckConstraint(
            "outcome_date_to >= outcome_date_from",
            name="ck_analysis_runs_outcome_window",
        ),
        sa.CheckConstraint(
            "accounts_analyzed >= 0 AND findings_count >= 0 "
            "AND high_severity_findings_count >= 0 AND outcome_campaign_count >= 0 "
            "AND attributed_journey_count >= 0 AND unattributed_journey_count >= 0",
            name="ck_analysis_runs_counts_nonnegative",
        ),
        sa.CheckConstraint(
            "(cadence = 'post_sync' AND source_job_run_id IS NOT NULL "
            "AND account_id IS NOT NULL) OR "
            "(cadence IN ('nightly', 'weekly') AND source_job_run_id IS NULL "
            "AND account_id IS NULL)",
            name="ck_analysis_runs_cadence_scope",
        ),
        sa.CheckConstraint(
            "(status = 'running' AND finished_at IS NULL) OR "
            "(status IN ('succeeded', 'failed') AND finished_at IS NOT NULL)",
            name="ck_analysis_runs_status_finished",
        ),
        sa.CheckConstraint(
            "status = 'failed' OR error_code IS NULL",
            name="ck_analysis_runs_error_status",
        ),
    )
    op.create_index(
        "ix_analysis_runs_workspace_scheduled",
        "analysis_runs",
        ["workspace_id", "scheduled_for", "id"],
    )
    op.create_index(
        "ix_analysis_runs_status_scheduled",
        "analysis_runs",
        ["status", "scheduled_for"],
    )


def downgrade() -> None:
    op.drop_index("ix_analysis_runs_status_scheduled", table_name="analysis_runs")
    op.drop_index("ix_analysis_runs_workspace_scheduled", table_name="analysis_runs")
    op.drop_table("analysis_runs")
    op.drop_constraint(
        "uq_job_runs_id_workspace",
        "job_runs",
        type_="unique",
    )
