import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ads.models import AdvertisingAccount
from app.analysis.enums import AnalysisCadence
from app.analysis.granular import GranularAnalysisService
from app.analysis.models import AnalysisRun
from app.analysis.repository import AnalysisRunRepository
from app.api.repository import ReadOnlyAdsRepository
from app.measurement.repository import MeasurementRepository
from app.measurement.unified import UnifiedOutcomeService
from app.optimizer.analytics import MetricWindow, inclusive_window_days
from app.optimizer.recommendations import generate_findings

logger = logging.getLogger(__name__)


class AnalysisRunRequestError(RuntimeError):
    """Fixed failure for an invalid workspace, account, or sync-job scope."""

    def __init__(self) -> None:
        super().__init__("Invalid workspace analysis run request.")


@dataclass(frozen=True)
class AnalysisSummary:
    accounts_analyzed: int
    findings_count: int
    high_severity_findings_count: int
    outcome_analysis_ready: bool
    outcome_campaign_count: int
    attributed_journey_count: int
    unattributed_journey_count: int
    blocking_reasons: tuple[str, ...]


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _window_ending(end: date, window_days: int) -> tuple[date, date]:
    return end - timedelta(days=window_days - 1), end


def _metric_window(
    repository: ReadOnlyAdsRepository,
    account_id: int,
    start: date,
    end: date,
) -> MetricWindow:
    totals = repository.account_metric_totals(account_id, start, end)
    return MetricWindow(
        date_from=start,
        date_to=end,
        window_days=inclusive_window_days(start, end),
        days_with_metric_rows=int(totals.get("days_with_metrics") or 0),
        impressions=int(totals["impressions"] or 0),
        clicks=int(totals["clicks"] or 0),
        cost_micros=int(totals["cost_micros"] or 0),
        conversions=Decimal(totals["conversions"] or 0),
        conversion_value_micros=int(totals["conversion_value_micros"] or 0),
    )


class AnalysisRunService:
    """Execute existing local analyzers and persist only aggregate run metadata."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = AnalysisRunRepository(session)

    def execute(
        self,
        *,
        workspace_id: int,
        cadence: AnalysisCadence,
        run_key: str,
        scheduled_for: datetime,
        window_days: int,
        account_id: int | None = None,
        source_job_run_id: int | None = None,
        policy_version: str = "v1",
        as_of: datetime | None = None,
    ) -> AnalysisRun:
        resolved_as_of = _utc(as_of or datetime.now(UTC))
        metric_end = resolved_as_of.date() - timedelta(days=1)
        metric_start, metric_end = _window_ending(metric_end, window_days)
        contract_snapshot = MeasurementRepository(self.session).get_for_workspace(workspace_id)
        maturity_days = (
            contract_snapshot.contract.outcome_maturity_days
            if contract_snapshot is not None
            else 90
        )
        outcome_end = resolved_as_of.date() - timedelta(days=maturity_days)
        outcome_start, outcome_end = _window_ending(outcome_end, window_days)
        row, claimed = self.repository.claim(
            workspace_id=workspace_id,
            account_id=account_id,
            source_job_run_id=source_job_run_id,
            run_key=run_key,
            cadence=cadence,
            schedule_policy_version=policy_version,
            scheduled_for=_utc(scheduled_for),
            metric_date_from=metric_start,
            metric_date_to=metric_end,
            outcome_date_from=outcome_start,
            outcome_date_to=outcome_end,
            started_at=resolved_as_of,
        )
        if not claimed:
            return row
        try:
            summary = self._analyze(
                workspace_id=workspace_id,
                account_id=account_id,
                metric_start=metric_start,
                metric_end=metric_end,
                outcome_start=outcome_start,
                outcome_end=outcome_end,
                as_of=resolved_as_of,
            )
            row = self.repository.finish_succeeded(
                row,
                finished_at=resolved_as_of,
                accounts_analyzed=summary.accounts_analyzed,
                findings_count=summary.findings_count,
                high_severity_findings_count=summary.high_severity_findings_count,
                outcome_analysis_ready=summary.outcome_analysis_ready,
                outcome_campaign_count=summary.outcome_campaign_count,
                attributed_journey_count=summary.attributed_journey_count,
                unattributed_journey_count=summary.unattributed_journey_count,
                blocking_reasons=summary.blocking_reasons,
            )
            self.session.commit()
            self.session.refresh(row)
            return row
        except Exception as exc:
            self.session.rollback()
            logger.error(
                "analysis_run_failed cadence=%s error_type=%s",
                cadence.value,
                type(exc).__name__,
            )
            row = self.repository.finish_failed(row.id, finished_at=resolved_as_of)
            self.session.commit()
            self.session.refresh(row)
            return row

    def _analyze(
        self,
        *,
        workspace_id: int,
        account_id: int | None,
        metric_start: date,
        metric_end: date,
        outcome_start: date,
        outcome_end: date,
        as_of: datetime,
    ) -> AnalysisSummary:
        account_statement = select(AdvertisingAccount).where(
            AdvertisingAccount.workspace_id == workspace_id
        )
        if account_id is not None:
            account_statement = account_statement.where(AdvertisingAccount.id == account_id)
        accounts = list(
            self.session.scalars(account_statement.order_by(AdvertisingAccount.id.asc())).all()
        )
        if account_id is not None and not accounts:
            raise AnalysisRunRequestError()

        ads_repository = ReadOnlyAdsRepository(self.session)
        findings_count = 0
        high_severity_count = 0
        span = inclusive_window_days(metric_start, metric_end)
        comparison_end = metric_start - timedelta(days=1)
        comparison_start = comparison_end - timedelta(days=span - 1)
        for account in accounts:
            _, last_success_at = ads_repository.account_sync_status(account.id)
            current = _metric_window(ads_repository, account.id, metric_start, metric_end)
            comparison = _metric_window(
                ads_repository,
                account.id,
                comparison_start,
                comparison_end,
            )
            findings = generate_findings(
                current,
                comparison,
                last_success_at=last_success_at,
                now=as_of,
            )
            findings_count += len(findings)
            high_severity_count += sum(finding.severity == "high" for finding in findings)

        granular_counts = GranularAnalysisService(self.session).count_workspace_findings(
            workspace_id,
            metric_start,
            metric_end,
            account_id=account_id,
            now=as_of,
        )
        findings_count += granular_counts.findings_count
        high_severity_count += granular_counts.high_severity_findings_count

        outcome = UnifiedOutcomeService(self.session).report(
            workspace_id,
            outcome_start,
            outcome_end,
            as_of=as_of,
        )
        blocking_reasons = list(outcome.blocking_reasons)
        if not accounts:
            blocking_reasons.append("advertising_accounts_missing")
        return AnalysisSummary(
            accounts_analyzed=len(accounts),
            findings_count=findings_count,
            high_severity_findings_count=high_severity_count,
            outcome_analysis_ready=outcome.analysis_ready,
            outcome_campaign_count=len(outcome.campaigns),
            attributed_journey_count=outcome.source_coverage.attributed_journey_count,
            unattributed_journey_count=outcome.source_coverage.unattributed_journey_count,
            blocking_reasons=tuple(dict.fromkeys(blocking_reasons)),
        )
