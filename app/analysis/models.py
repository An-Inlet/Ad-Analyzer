from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.ads.models import TimestampMixin
from app.analysis.enums import AnalysisCadence, AnalysisRunStatus
from app.database.session import Base

cadence_enum = Enum(
    AnalysisCadence,
    name="analysis_cadence",
    native_enum=False,
    values_callable=lambda enum_cls: [item.value for item in enum_cls],
)
run_status_enum = Enum(
    AnalysisRunStatus,
    name="analysis_run_status",
    native_enum=False,
    values_callable=lambda enum_cls: [item.value for item in enum_cls],
)


class AnalysisRun(TimestampMixin, Base):
    """Sanitized, aggregate-only audit record for one deterministic analysis run."""

    __tablename__ = "analysis_runs"
    __table_args__ = (
        UniqueConstraint("workspace_id", "run_key", name="uq_analysis_runs_workspace_key"),
        ForeignKeyConstraint(
            ["account_id", "workspace_id"],
            ["advertising_accounts.id", "advertising_accounts.workspace_id"],
            name="fk_analysis_runs_account_workspace",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["source_job_run_id", "workspace_id"],
            ["job_runs.id", "job_runs.workspace_id"],
            name="fk_analysis_runs_source_job_workspace",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "metric_date_to >= metric_date_from",
            name="ck_analysis_runs_metric_window",
        ),
        CheckConstraint(
            "outcome_date_to >= outcome_date_from",
            name="ck_analysis_runs_outcome_window",
        ),
        CheckConstraint(
            "accounts_analyzed >= 0 AND findings_count >= 0 "
            "AND high_severity_findings_count >= 0 "
            "AND recommendations_created_count >= 0 "
            "AND recommendations_deduplicated_count >= 0 "
            "AND outcome_campaign_count >= 0 "
            "AND attributed_journey_count >= 0 AND unattributed_journey_count >= 0",
            name="ck_analysis_runs_counts_nonnegative",
        ),
        CheckConstraint(
            "(cadence = 'post_sync' AND source_job_run_id IS NOT NULL "
            "AND account_id IS NOT NULL) OR "
            "(cadence IN ('nightly', 'weekly') AND source_job_run_id IS NULL "
            "AND account_id IS NULL)",
            name="ck_analysis_runs_cadence_scope",
        ),
        CheckConstraint(
            "(status = 'running' AND finished_at IS NULL) OR "
            "(status IN ('succeeded', 'failed') AND finished_at IS NOT NULL)",
            name="ck_analysis_runs_status_finished",
        ),
        CheckConstraint(
            "status = 'failed' OR error_code IS NULL",
            name="ck_analysis_runs_error_status",
        ),
        Index(
            "ix_analysis_runs_workspace_scheduled",
            "workspace_id",
            "scheduled_for",
            "id",
        ),
        Index("ix_analysis_runs_status_scheduled", "status", "scheduled_for"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[int | None] = mapped_column(Integer)
    source_job_run_id: Mapped[int | None] = mapped_column(Integer)
    run_key: Mapped[str] = mapped_column(String(160), nullable=False)
    cadence: Mapped[AnalysisCadence] = mapped_column(cadence_enum, nullable=False)
    status: Mapped[AnalysisRunStatus] = mapped_column(run_status_enum, nullable=False)
    schedule_policy_version: Mapped[str] = mapped_column(String(16), nullable=False, default="v1")
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metric_date_from: Mapped[date] = mapped_column(Date, nullable=False)
    metric_date_to: Mapped[date] = mapped_column(Date, nullable=False)
    outcome_date_from: Mapped[date] = mapped_column(Date, nullable=False)
    outcome_date_to: Mapped[date] = mapped_column(Date, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accounts_analyzed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    findings_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    high_severity_findings_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recommendations_created_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    recommendations_deduplicated_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    outcome_analysis_ready: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    outcome_campaign_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    attributed_journey_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unattributed_journey_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    blocking_reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    error_code: Mapped[str | None] = mapped_column(String(64))
