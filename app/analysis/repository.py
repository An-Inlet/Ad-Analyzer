from collections.abc import Sequence
from datetime import date, datetime
from typing import cast

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.analysis.enums import AnalysisCadence, AnalysisRunStatus
from app.analysis.models import AnalysisRun


class AnalysisRunRepository:
    """Persistence for idempotent, workspace-owned analysis runs."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_run_key(self, workspace_id: int, run_key: str) -> AnalysisRun | None:
        return self.session.scalar(
            select(AnalysisRun).where(
                AnalysisRun.workspace_id == workspace_id,
                AnalysisRun.run_key == run_key,
            )
        )

    def claim(
        self,
        *,
        workspace_id: int,
        account_id: int | None,
        source_job_run_id: int | None,
        run_key: str,
        cadence: AnalysisCadence,
        schedule_policy_version: str,
        scheduled_for: datetime,
        metric_date_from: date,
        metric_date_to: date,
        outcome_date_from: date,
        outcome_date_to: date,
        started_at: datetime,
    ) -> tuple[AnalysisRun, bool]:
        existing = self.get_by_run_key(workspace_id, run_key)
        if existing is not None:
            return existing, False
        row = AnalysisRun(
            workspace_id=workspace_id,
            account_id=account_id,
            source_job_run_id=source_job_run_id,
            run_key=run_key,
            cadence=cadence,
            status=AnalysisRunStatus.RUNNING,
            schedule_policy_version=schedule_policy_version,
            scheduled_for=scheduled_for,
            metric_date_from=metric_date_from,
            metric_date_to=metric_date_to,
            outcome_date_from=outcome_date_from,
            outcome_date_to=outcome_date_to,
            started_at=started_at,
            blocking_reasons=[],
        )
        self.session.add(row)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            existing = self.get_by_run_key(workspace_id, run_key)
            if existing is None:
                raise
            return existing, False
        self.session.refresh(row)
        return row, True

    def list_runs(
        self,
        workspace_id: int,
        *,
        cadence: AnalysisCadence | None = None,
        status: AnalysisRunStatus | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> tuple[list[AnalysisRun], int]:
        stmt = select(AnalysisRun).where(AnalysisRun.workspace_id == workspace_id)
        if cadence is not None:
            stmt = stmt.where(AnalysisRun.cadence == cadence)
        if status is not None:
            stmt = stmt.where(AnalysisRun.status == status)
        total = self.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = self.session.scalars(
            stmt.order_by(AnalysisRun.scheduled_for.desc(), AnalysisRun.id.desc())
            .limit(limit)
            .offset(offset)
        ).all()
        return list(rows), int(total)

    def finish_succeeded(
        self,
        row: AnalysisRun,
        *,
        finished_at: datetime,
        accounts_analyzed: int,
        findings_count: int,
        high_severity_findings_count: int,
        outcome_analysis_ready: bool,
        outcome_campaign_count: int,
        attributed_journey_count: int,
        unattributed_journey_count: int,
        blocking_reasons: Sequence[str],
    ) -> AnalysisRun:
        row.status = AnalysisRunStatus.SUCCEEDED
        row.finished_at = finished_at
        row.accounts_analyzed = accounts_analyzed
        row.findings_count = findings_count
        row.high_severity_findings_count = high_severity_findings_count
        row.outcome_analysis_ready = outcome_analysis_ready
        row.outcome_campaign_count = outcome_campaign_count
        row.attributed_journey_count = attributed_journey_count
        row.unattributed_journey_count = unattributed_journey_count
        row.blocking_reasons = list(dict.fromkeys(blocking_reasons))
        row.error_code = None
        return row

    def finish_failed(self, run_id: int, *, finished_at: datetime) -> AnalysisRun:
        row = cast(AnalysisRun, self.session.get(AnalysisRun, run_id))
        row.status = AnalysisRunStatus.FAILED
        row.finished_at = finished_at
        row.error_code = "analysis_failed"
        row.blocking_reasons = ["analysis_failed"]
        return row
