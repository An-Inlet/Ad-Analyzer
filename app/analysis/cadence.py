import logging
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import Any

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.ads.enums import JobRunStatus
from app.ads.models import JobRun
from app.analysis.enums import AnalysisCadence
from app.analysis.models import AnalysisRun
from app.analysis.policy import AnalysisCadencePolicy, AnalysisCadencePolicyError
from app.analysis.service import AnalysisRunRequestError, AnalysisRunService
from app.workspaces.models import Workspace, WorkspaceConfiguration

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AnalysisTickResult:
    post_sync_run_id: int | None
    scheduled_run_ids: tuple[int, ...]
    invalid_policy_count: int


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _nightly_schedule(now: datetime, hour_utc: int) -> datetime | None:
    scheduled = datetime.combine(now.date(), time(hour=hour_utc), tzinfo=UTC)
    return scheduled if now >= scheduled else None


def _weekly_schedule(now: datetime, weekday_utc: int, hour_utc: int) -> datetime | None:
    week_start = now.date() - timedelta(days=now.weekday())
    scheduled_date = week_start + timedelta(days=weekday_utc)
    scheduled = datetime.combine(scheduled_date, time(hour=hour_utc), tzinfo=UTC)
    return scheduled if now >= scheduled else None


def _policy(session: Session, workspace_id: int) -> AnalysisCadencePolicy:
    configuration = session.get(WorkspaceConfiguration, workspace_id)
    return AnalysisCadencePolicy.from_workspace_analysis(
        configuration.analysis if configuration is not None else None
    )


def run_post_sync_analysis(
    engine: Engine,
    source_job_run_id: int,
    *,
    as_of: datetime | None = None,
) -> AnalysisRun | None:
    """Run the lightweight analysis once for a successful, account-scoped sync."""
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with session_factory() as session:
        source_job = session.get(JobRun, source_job_run_id)
        if (
            source_job is None
            or source_job.status != JobRunStatus.SUCCEEDED
            or source_job.account_id is None
            or source_job.finished_at is None
        ):
            raise AnalysisRunRequestError()
        policy = _policy(session, source_job.workspace_id)
        if not policy.post_sync.enabled:
            return None
        resolved_as_of = _utc(as_of or datetime.now(UTC))
        return AnalysisRunService(session).execute(
            workspace_id=source_job.workspace_id,
            account_id=source_job.account_id,
            source_job_run_id=source_job.id,
            cadence=AnalysisCadence.POST_SYNC,
            run_key=f"post_sync:job:{source_job.id}",
            scheduled_for=_utc(source_job.finished_at),
            window_days=policy.post_sync.window_days,
            policy_version=policy.version,
            as_of=resolved_as_of,
        )


def run_due_analyses(
    engine: Engine,
    *,
    as_of: datetime | None = None,
) -> tuple[tuple[int, ...], int]:
    """Run at most one nightly and one weekly analysis per active workspace period."""
    resolved_as_of = _utc(as_of or datetime.now(UTC))
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with session_factory() as session:
        workspace_ids = list(
            session.scalars(
                select(Workspace.id)
                .where(Workspace.status == "active")
                .order_by(Workspace.id.asc())
            ).all()
        )
    run_ids: list[int] = []
    invalid_policy_count = 0
    for workspace_id in workspace_ids:
        with session_factory() as session:
            try:
                policy = _policy(session, workspace_id)
            except AnalysisCadencePolicyError:
                invalid_policy_count += 1
                logger.error("analysis_policy_invalid workspace_scope=redacted")
                continue
            scheduled: list[tuple[AnalysisCadence, datetime, int]] = []
            nightly_at = _nightly_schedule(resolved_as_of, policy.nightly.hour_utc)
            if policy.nightly.enabled and nightly_at is not None:
                scheduled.append((AnalysisCadence.NIGHTLY, nightly_at, policy.nightly.window_days))
            weekly_at = _weekly_schedule(
                resolved_as_of,
                policy.weekly.weekday_utc,
                policy.weekly.hour_utc,
            )
            if policy.weekly.enabled and weekly_at is not None:
                scheduled.append((AnalysisCadence.WEEKLY, weekly_at, policy.weekly.window_days))
            for cadence, scheduled_for, window_days in scheduled:
                row = AnalysisRunService(session).execute(
                    workspace_id=workspace_id,
                    cadence=cadence,
                    run_key=f"{cadence.value}:{scheduled_for.date().isoformat()}",
                    scheduled_for=scheduled_for,
                    window_days=window_days,
                    policy_version=policy.version,
                    as_of=resolved_as_of,
                )
                run_ids.append(row.id)
    return tuple(run_ids), invalid_policy_count


def run_analysis_tick(
    engine: Engine,
    sync_outcome: Any | None,
    *,
    as_of: datetime | None = None,
) -> AnalysisTickResult:
    """Run post-sync analysis when eligible, then independently run due schedules."""
    post_sync_run_id: int | None = None
    sync_result = getattr(sync_outcome, "result", None)
    if sync_result is not None and sync_result.status == JobRunStatus.SUCCEEDED:
        try:
            post_sync_run = run_post_sync_analysis(
                engine,
                sync_result.job_run_id,
                as_of=as_of,
            )
            post_sync_run_id = post_sync_run.id if post_sync_run is not None else None
        except (AnalysisCadencePolicyError, AnalysisRunRequestError) as exc:
            logger.error("post_sync_analysis_not_started error_type=%s", type(exc).__name__)
    scheduled_run_ids, invalid_policy_count = run_due_analyses(engine, as_of=as_of)
    return AnalysisTickResult(
        post_sync_run_id=post_sync_run_id,
        scheduled_run_ids=scheduled_run_ids,
        invalid_policy_count=invalid_policy_count,
    )
