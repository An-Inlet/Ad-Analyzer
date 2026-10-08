"""Owned fixed-window reads through the existing Meta staging and terminal transaction."""

from datetime import datetime, time, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.ads.enums import AdvertisingPlatform
from app.ads.models import AdvertisingAccount
from app.campaign_performance.models import PerformanceCompletion
from app.campaign_performance.service import manifest
from app.initial_planning.clock import effective_now
from app.meta.models import MetaConnection
from app.meta.security import MetaError, utc
from app.reported_feedback.contracts import (
    FixedWindowLeaseV1,
    ReportedDayV1,
    ReportedWindowCapsuleV1,
    ReportWindowV1,
)
from app.reported_feedback.models import ReportedFeedbackJob, ReportedWindowCapsule
from app.reported_feedback.runtime import ReportedFeedbackRuntime


def due_job(db: Session, wid: int, now: datetime) -> ReportedFeedbackJob | None:
    return db.scalar(
        select(ReportedFeedbackJob)
        .where(
            ReportedFeedbackJob.workspace_id == wid,
            (ReportedFeedbackJob.state == "acquiring")
            | (
                ReportedFeedbackJob.state.in_(("pending", "waiting"))
                & (ReportedFeedbackJob.next_due_at <= now)
            ),
        )
        .order_by(
            case((ReportedFeedbackJob.state == "acquiring", 0), else_=1),
            ReportedFeedbackJob.next_due_at,
            ReportedFeedbackJob.id,
        )
        .limit(1)
        .execution_options(populate_existing=True)
    )


def lock_job_authority(
    db: Session, wid: int, now: datetime, runtime: ReportedFeedbackRuntime
) -> str | None:
    """Workspace is already locked; principal locks must precede the native source."""
    from app.reported_feedback.service import local_job_authority

    job = due_job(db, wid, now)
    if job is not None:
        try:
            local_job_authority(db, job, max(now, effective_now(db, runtime.initial)), lock=True)
        except HTTPException:
            job.state, job.error_code = "blocked", "reported_original_authority_unavailable"
            return None
        return job.id
    return None


def lease_for(job: ReportedFeedbackJob) -> FixedWindowLeaseV1:
    if (
        job.native_run_id is None
        or job.acquisition_started_at is None
        or job.selected_start is None
        or job.selected_end is None
    ):
        raise MetaError("meta_reported_feedback_checkpoint_invalid")
    return FixedWindowLeaseV1(
        job_id=job.id,
        acquisition_run_id=job.native_run_id,
        source_connection_id=job.source_connection_id,
        source_generation=job.source_generation,
        observation_ordinal=job.completed_observations,
        window=ReportWindowV1(starts_on=job.selected_start, ends_on=job.selected_end),
        acquisition_started_at=utc(job.acquisition_started_at),
        rolling_covered_from=job.rolling_covered_from,
        rolling_covered_through=job.rolling_covered_through,
        rolling_last_sync_at=utc(job.rolling_last_sync_at) if job.rolling_last_sync_at else None,
    )


def active_lease(db: Session, source: MetaConnection) -> FixedWindowLeaseV1 | None:
    jobs = list(
        db.scalars(
            select(ReportedFeedbackJob)
            .where(
                ReportedFeedbackJob.workspace_id == source.workspace_id,
                ReportedFeedbackJob.source_connection_id == source.id,
                ReportedFeedbackJob.native_run_id.is_not(None),
            )
            .limit(2)
            .execution_options(populate_existing=True)
        )
    )
    if len(jobs) > 1:
        raise MetaError("meta_reported_feedback_checkpoint_invalid")
    return lease_for(jobs[0]) if jobs else None


def abort_fixed_window(
    db: Session, source: MetaConnection, lease: FixedWindowLeaseV1 | None, reason: str
) -> None:
    """A lost/disabled fixed run can never resume as an ordinary rolling checkpoint."""

    from app.meta import staging
    from app.meta.presence_staging import clear_campaign_presence
    from app.reported_feedback.invalidation import retract_account_comparisons

    if lease is not None:
        job = db.get(ReportedFeedbackJob, lease.job_id, populate_existing=True)
        if job is not None:
            job.state, job.error_code, job.native_run_id = "blocked", reason, None
        source.covered_from, source.covered_through = (
            lease.rolling_covered_from,
            lease.rolling_covered_through,
        )
        source.last_sync_at = lease.rolling_last_sync_at
    else:
        # The removed job also removed the only retained rolling checkpoint copy.
        source.covered_from = source.covered_through = source.last_sync_at = None
    staging.clear(db, source.id)
    clear_campaign_presence(db, source.id)
    source.window_start = source.window_end = source.cursor = None
    source.phase = "campaigns"
    retract_account_comparisons(db, source.workspace_id, source.account_id)


def require_lease(
    db: Session,
    source: MetaConnection,
    lease: FixedWindowLeaseV1,
    now: datetime,
    runtime: ReportedFeedbackRuntime,
) -> ReportedFeedbackJob:
    from app.reported_feedback.service import local_job_current

    job = db.get(ReportedFeedbackJob, lease.job_id, populate_existing=True)
    if (
        job is None
        or job.state != "acquiring"
        or job.workspace_id != source.workspace_id
        or job.account_id != source.account_id
        or source.id != lease.source_connection_id
        or source.generation != lease.source_generation
        or source.window_start != lease.window.starts_on
        or source.window_end != lease.window.ends_on
        or not source.phase.startswith("rf_")
        or lease_for(job) != lease
    ):
        raise MetaError("meta_reported_feedback_checkpoint_invalid")
    try:
        local_job_current(db, job, runtime, now)
    except HTTPException:
        raise MetaError("meta_reported_feedback_authority_changed") from None
    return job


def claim_fixed_window(
    db: Session,
    source: MetaConnection,
    account: AdvertisingAccount,
    now: datetime,
    runtime: ReportedFeedbackRuntime,
    *,
    rolling_due: bool,
    authorized_job_id: str | None = None,
) -> FixedWindowLeaseV1 | None:
    """Never interrupt a rolling/detail run or starve a due ordinary acquisition."""
    from app.reported_feedback.service import local_job_current

    if (
        authorized_job_id is None
        or rolling_due
        or source.window_start is not None
        or source.window_end is not None
    ):
        return None
    job = db.get(ReportedFeedbackJob, authorized_job_id, populate_existing=True)
    if (
        job is None
        or job.workspace_id != source.workspace_id
        or job.state not in {"pending", "waiting", "acquiring"}
        or utc(job.next_due_at) > now
    ):
        return None
    now = max(now, effective_now(db, runtime.initial))
    if job.state == "acquiring":
        job.state, job.error_code = "blocked", "reported_native_checkpoint_lost"
        job.native_run_id = None
        return None
    if (
        job.account_id != account.id
        or account.workspace_id != source.workspace_id
        or job.source_connection_id != source.id
        or job.source_generation != source.generation
    ):
        job.state, job.error_code = "blocked", "reported_source_changed"
        return None
    try:
        request = local_job_current(db, job, runtime, now)
    except HTTPException:
        job.state, job.error_code = "blocked", "reported_original_authority_unavailable"
        return None
    ordinal = job.completed_observations
    if ordinal >= request.policy.distinct_repeat_completions * 2:
        job.state = "ready"
        return None
    window = request.before if ordinal % 2 == 0 else request.after
    close = datetime.combine(
        window.ends_on + timedelta(days=1), time.min, ZoneInfo(request.anchor.cohort.time_zone)
    )
    previous = db.scalar(
        select(func.max(ReportedWindowCapsule.acquisition_completed_at)).where(
            ReportedWindowCapsule.job_id == job.id,
            ReportedWindowCapsule.starts_on == window.starts_on,
            ReportedWindowCapsule.ends_on == window.ends_on,
        )
    )
    due = close + timedelta(seconds=request.policy.minimum_close_age_seconds)
    if previous is not None:
        due = max(
            due, utc(previous) + timedelta(seconds=request.policy.minimum_repeat_spacing_seconds)
        )
    if now < due:
        job.next_due_at, job.state = due, "waiting"
        return None
    count = (
        db.scalar(
            select(func.count(ReportedWindowCapsule.id)).where(
                ReportedWindowCapsule.workspace_id == source.workspace_id,
                ReportedWindowCapsule.account_id == source.account_id,
            )
        )
        or 0
    )
    if count >= request.policy.maximum_capsules:
        job.state, job.error_code = "blocked", "reported_capsule_capacity_exceeded"
        return None
    job.native_run_id = uuid4().hex
    job.acquisition_started_at = now
    job.selected_start, job.selected_end = window.starts_on, window.ends_on
    job.rolling_covered_from, job.rolling_covered_through = (
        source.covered_from,
        source.covered_through,
    )
    job.rolling_last_sync_at = source.last_sync_at
    job.state, job.error_code = "acquiring", None
    db.flush()
    return lease_for(job)


def capture_terminal_window(
    db: Session,
    source: MetaConnection,
    completion: PerformanceCompletion,
    lease: FixedWindowLeaseV1,
    now: datetime,
    runtime: ReportedFeedbackRuntime,
) -> ReportedWindowCapsuleV1:
    from app.reported_feedback.invalidation import retract_account_comparisons
    from app.reported_feedback.service import local_job_current

    now = max(now, effective_now(db, runtime.initial))
    job = require_lease(db, source, lease, now, runtime)
    request = local_job_current(db, job, runtime, now)
    cohort = request.anchor.cohort
    account = db.get(AdvertisingAccount, source.account_id, populate_existing=True)
    if (
        account is None
        or completion.workspace_id != cohort.workspace_id
        or completion.account_id != cohort.account_id
        or completion.platform != "meta_ads"
        or completion.generation != lease.source_generation
        or completion.source_connection_ref != str(source.id)
        or completion.starts_on != lease.window.starts_on
        or completion.ends_on != lease.window.ends_on
        or completion.selected_event != cohort.selected_event
        or completion.query_version != cohort.query_version
        or completion.currency != cohort.currency
        or completion.time_zone != cohort.time_zone
        or completion.reporting_basis != cohort.reporting_basis
        or not lease.acquisition_started_at <= utc(completion.completed_at) <= now
    ):
        raise MetaError("meta_reported_feedback_completion_changed")
    digest, metrics = manifest(db, account, lease.window.starts_on, lease.window.ends_on)
    if digest != completion.manifest_digest or len(metrics) != completion.row_count:
        raise MetaError("meta_reported_feedback_completion_changed")
    days = tuple(
        ReportedDayV1(
            day=m.metric_date,
            spend_micros=m.cost_micros,
            conversions=m.conversions,
            conversion_value_micros=m.conversion_value_micros,
        )
        for m in metrics
        if m.campaign_id == cohort.campaign_id
        and m.platform == AdvertisingPlatform.META_ADS
        and m.entity_type == "campaign"
    )
    value = ReportedWindowCapsuleV1(
        id=uuid4().hex,
        job_id=job.id,
        acquisition_run_id=lease.acquisition_run_id,
        completion_id=completion.id,
        completion_manifest_digest=completion.manifest_digest,
        environment=request.policy.environment,
        cohort=cohort,
        source_generation=source.generation,
        captured_privacy_revision=completion.privacy_revision,
        policy_digest=request.policy.digest(),
        window=lease.window,
        acquisition_started_at=lease.acquisition_started_at,
        acquisition_completed_at=utc(completion.completed_at),
        captured_at=now,
        expires_at=min(
            utc(job.expires_at), now + timedelta(seconds=request.policy.retention_seconds)
        ),
        days=days,
    )
    prior = list(
        db.scalars(
            select(ReportedWindowCapsule)
            .where(
                ReportedWindowCapsule.workspace_id == cohort.workspace_id,
                ReportedWindowCapsule.account_id == cohort.account_id,
                ReportedWindowCapsule.campaign_id == cohort.campaign_id,
                ReportedWindowCapsule.source_generation == source.generation,
                ReportedWindowCapsule.starts_on == lease.window.starts_on,
                ReportedWindowCapsule.ends_on == lease.window.ends_on,
            )
            .limit(129)
        )
    )
    if len(prior) > 128:
        raise MetaError("meta_reported_feedback_capacity_exceeded")
    if any(ReportedWindowCapsuleV1.model_validate(row.document).days != days for row in prior):
        retract_account_comparisons(db, cohort.workspace_id, cohort.account_id)
    db.add(
        ReportedWindowCapsule(
            id=value.id,
            workspace_id=cohort.workspace_id,
            account_id=cohort.account_id,
            campaign_id=cohort.campaign_id,
            environment=value.environment,
            document=value.model_dump(mode="json"),
            document_digest=value.digest(),
            expires_at=value.expires_at,
            job_id=job.id,
            completion_id=completion.id,
            acquisition_run_id=lease.acquisition_run_id,
            source_generation=source.generation,
            starts_on=lease.window.starts_on,
            ends_on=lease.window.ends_on,
            acquisition_started_at=value.acquisition_started_at,
            acquisition_completed_at=value.acquisition_completed_at,
            captured_at=now,
        )
    )
    job.completed_observations += 1
    job.native_run_id = None
    job.acquisition_started_at = None
    job.selected_start = job.selected_end = None
    job.next_due_at = now
    job.state = (
        "ready"
        if job.completed_observations == request.policy.distinct_repeat_completions * 2
        else "waiting"
    )
    job.completed_at = now if job.state == "ready" else None
    db.flush()
    return value
