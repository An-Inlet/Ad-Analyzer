"""automate deterministic recommendation generation

Revision ID: 20260816_0014
Revises: 20260815_0013
Create Date: 2026-08-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260816_0014"
down_revision: str | None = "20260815_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_COUNTS_WITH_RECOMMENDATIONS = (
    "accounts_analyzed >= 0 AND findings_count >= 0 "
    "AND high_severity_findings_count >= 0 "
    "AND recommendations_created_count >= 0 "
    "AND recommendations_deduplicated_count >= 0 "
    "AND outcome_campaign_count >= 0 "
    "AND attributed_journey_count >= 0 AND unattributed_journey_count >= 0"
)
_COUNTS_WITHOUT_RECOMMENDATIONS = (
    "accounts_analyzed >= 0 AND findings_count >= 0 "
    "AND high_severity_findings_count >= 0 AND outcome_campaign_count >= 0 "
    "AND attributed_journey_count >= 0 AND unattributed_journey_count >= 0"
)
_ACTIVE_RECOMMENDATION_STATUSES = (
    "deduplication_key IS NOT NULL AND status IN "
    "('pending_review', 'approved', 'executed_dry_run')"
)


def upgrade() -> None:
    op.add_column(
        "analysis_runs",
        sa.Column(
            "recommendations_created_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "analysis_runs",
        sa.Column(
            "recommendations_deduplicated_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.drop_constraint(
        "ck_analysis_runs_counts_nonnegative",
        "analysis_runs",
        type_="check",
    )
    op.create_check_constraint(
        "ck_analysis_runs_counts_nonnegative",
        "analysis_runs",
        _COUNTS_WITH_RECOMMENDATIONS,
    )

    op.add_column(
        "recommendations",
        sa.Column("source_analysis_run_id", sa.Integer()),
    )
    op.add_column(
        "recommendations",
        sa.Column("deduplication_key", sa.String(64)),
    )
    op.create_index(
        "ix_recommendations_workspace_deduplication",
        "recommendations",
        ["workspace_id", "deduplication_key"],
    )
    op.create_index(
        "uq_recommendations_active_deduplication",
        "recommendations",
        ["workspace_id", "deduplication_key"],
        unique=True,
        postgresql_where=sa.text(_ACTIVE_RECOMMENDATION_STATUSES),
        sqlite_where=sa.text(_ACTIVE_RECOMMENDATION_STATUSES),
    )
    op.create_index(
        "ix_recommendations_source_analysis_run",
        "recommendations",
        ["source_analysis_run_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_recommendations_source_analysis_run",
        table_name="recommendations",
    )
    op.drop_index(
        "uq_recommendations_active_deduplication",
        table_name="recommendations",
    )
    op.drop_index(
        "ix_recommendations_workspace_deduplication",
        table_name="recommendations",
    )
    op.drop_column("recommendations", "deduplication_key")
    op.drop_column("recommendations", "source_analysis_run_id")

    op.drop_constraint(
        "ck_analysis_runs_counts_nonnegative",
        "analysis_runs",
        type_="check",
    )
    op.create_check_constraint(
        "ck_analysis_runs_counts_nonnegative",
        "analysis_runs",
        _COUNTS_WITHOUT_RECOMMENDATIONS,
    )
    op.drop_column("analysis_runs", "recommendations_deduplicated_count")
    op.drop_column("analysis_runs", "recommendations_created_count")
