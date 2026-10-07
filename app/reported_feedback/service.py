"""Owned operational comparison/application services; no provider mutation authority."""

from datetime import datetime, timedelta
from typing import cast
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.campaign_performance.models import PerformanceCompletion
from app.customers.access import CustomerPrincipal
from app.customers.identity import IdentityProvider
from app.customers.models import CustomerMembership, CustomerSession, CustomerUser
from app.initial_planning import preview as initial_preview
from app.initial_planning.clock import effective_now
from app.initial_planning.contracts import (
    CohortV1,
    EfficiencyObjectiveV1,
    InitialPreviewV1,
)
from app.initial_planning.models import PreviewRow
from app.initial_planning.preview_binding import bind_preview_row, preview_mandate_reference
from app.initial_planning.preview_v2 import InitialPreviewV2
from app.meta.security import utc
from app.publication import customer_intents, execution_mandates
from app.publication.contracts import fingerprint
from app.publication.customer_authority import bind_authority
from app.reported_feedback.anchor import resolve_anchor
from app.reported_feedback.contracts import (
    ComparisonIntentV1,
    ComparisonProgressV1,
    FeedbackPreviewIntentV1,
    OperationalReportedComparisonV1,
    ReportedAcquisitionRequestV1,
    ReportedFeedbackPolicyV1,
    ReportedFeedbackPreviewV1,
    ReportedWindowCapsuleV1,
    ReportWindowV1,
)
from app.reported_feedback.evaluator import bounded_delta, compare, midnight
from app.reported_feedback.invalidation import retract_account_comparisons
from app.reported_feedback.models import (
    ReportedActionComparison,
    ReportedComparisonDependency,
    ReportedFeedbackJob,
    ReportedFeedbackSlot,
    ReportedWindowCapsule,
)
from app.reported_feedback.runtime import ReportedFeedbackRuntime
from app.workspaces.models import Workspace


def local_job_authority(
    db: Session, job: ReportedFeedbackJob, now: datetime, *, lock: bool = False
) -> CustomerPrincipal:
    """No identity/provider IO. lock=True only after workspace and BEFORE native locks."""
    workspace = db.get(Workspace, job.workspace_id, populate_existing=True)
    user = db.get(CustomerUser, job.original_actor_id, populate_existing=True, with_for_update=lock)
    session = db.get(
        CustomerSession, job.original_session_digest, populate_existing=True, with_for_update=lock
    )
    member = db.get(
        CustomerMembership,
        (job.original_actor_id, job.workspace_id),
        populate_existing=True,
        with_for_update=lock,
    )
    if (
        workspace is None
        or workspace.status != "active"
        or user is None
        or session is None
        or member is None
        or user.status != "active"
        or session.user_id != user.id
        or session.revoked_at is not None
        or session.expires_at <= int(now.timestamp())
        or member.role != "owner"
        or member.status != "active"
    ):
        raise HTTPException(409, "reported_feedback_original_session_unavailable")
    return CustomerPrincipal(user=user, session=session)


def _current_job_id(db: Session, job: ReportedFeedbackJob) -> str | None:
    # No chronological tie-break or fallback to an older request after deletion.
    ids = list(
        db.scalars(
            select(ReportedFeedbackJob.id)
            .where(
                ReportedFeedbackJob.workspace_id == job.workspace_id,
                ReportedFeedbackJob.opportunity_digest == job.opportunity_digest,
                ReportedFeedbackJob.state.not_in(("blocked", "expired")),
            )
            .limit(2)
        )
    )
    return ids[0] if len(ids) == 1 else None


def local_job_current(
    db: Session, job: ReportedFeedbackJob, runtime: ReportedFeedbackRuntime, now: datetime
) -> ReportedAcquisitionRequestV1:
    """Caller holds workspace/native fence; no new principal locks or external IO."""
    now = max(now, effective_now(db, runtime.initial))
    principal = local_job_authority(db, job, now)
    if _current_job_id(db, job) != job.id:
        raise HTTPException(409, "reported_feedback_request_superseded")
    request = ReportedAcquisitionRequestV1.model_validate(job.document)
    if (
        request.digest() != job.document_digest
        or request.expires_at != utc(job.expires_at)
        or request.id != job.id
        or (
            request.anchor.cohort.workspace_id,
            request.anchor.cohort.account_id,
            request.anchor.cohort.campaign_id,
            request.anchor.environment,
        )
        != (job.workspace_id, job.account_id, job.campaign_id, job.environment)
        or request.anchor.original_attempt_id != job.original_attempt_id
        or request.anchor.source_connection_id != job.source_connection_id
        or request.anchor.source_generation != job.source_generation
        or request.policy.digest() != job.policy_digest
        or request.policy.family != job.policy_family
        or request.anchor.opportunity_digest(request.policy.family) != job.opportunity_digest
        or runtime.window_policy != request.policy
        or now >= request.expires_at
        or job.state in {"blocked", "expired"}
    ):
        raise HTTPException(409, "reported_feedback_request_changed_or_expired")
    current = resolve_anchor(db, job.workspace_id, job.original_attempt_id, principal.user.id, now)
    # Ordinary retained-report publication can invalidate export snapshots without
    # erasing historical capsules. Semantic privacy hooks physically erase the job.
    if current.model_dump(exclude={"privacy_revision"}) != request.anchor.model_dump(
        exclude={"privacy_revision"}
    ):
        raise HTTPException(409, "reported_feedback_original_configuration_changed")
    local_job_authority(db, job, max(now, effective_now(db, runtime.initial)))
    return request


def request_comparison(
    db: Session,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    workspace_id: int,
    intent: ComparisonIntentV1,
    runtime: ReportedFeedbackRuntime,
) -> ComparisonProgressV1:
    return _request(db, principal, provider, workspace_id, intent, runtime, None)


def _request(
    db: Session,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    wid: int,
    intent: ComparisonIntentV1,
    runtime: ReportedFeedbackRuntime,
    predecessor: ReportedFeedbackJob | None,
) -> ComparisonProgressV1:
    authorize = bind_authority(principal, provider)
    authorize(db, wid, principal.user.id)
    now = effective_now(db, runtime.initial)
    policy = runtime.window_policy
    if policy is None:
        raise HTTPException(409, "reported_feedback_not_configured")
    anchor = resolve_anchor(db, wid, intent.attempt_id, principal.user.id, now)
    if (intent.goal_id, intent.goal_revision) != (anchor.goal_id, anchor.goal_revision):
        raise HTTPException(409, "reported_feedback_goal_changed")
    if (anchor.environment, anchor.cohort.selected_event, anchor.cohort.query_version) != (
        policy.environment,
        policy.selected_event,
        policy.query_version,
    ):
        raise HTTPException(409, "reported_feedback_profile_unsupported")
    objective = EfficiencyObjectiveV1(
        cohort=anchor.cohort,
        goal_id=intent.goal_id,
        goal_revision=intent.goal_revision,
        maximum_reported_cpa_micros=intent.maximum_reported_cpa_micros,
    )
    input_digest = fingerprint(
        "inlet.reported-feedback-request-input.v1",
        {
            "anchor": anchor.model_dump(mode="json", exclude={"privacy_revision"}),
            "objective": objective.model_dump(mode="json"),
            "policy": policy.digest(),
            "actor": principal.user.id,
            "session": principal.session.digest,
            "predecessor": predecessor.id if predecessor else None,
        },
    )
    old = db.scalar(
        select(ReportedFeedbackJob).where(
            ReportedFeedbackJob.workspace_id == wid,
            ReportedFeedbackJob.input_digest == input_digest,
        )
    )
    if old is not None:
        return read_comparison_progress(db, principal, provider, wid, old.id, runtime)
    retained = list(
        db.scalars(
            select(ReportedFeedbackJob.id)
            .where(
                ReportedFeedbackJob.workspace_id == wid,
                ReportedFeedbackJob.account_id == anchor.cohort.account_id,
                ReportedFeedbackJob.campaign_id == anchor.cohort.campaign_id,
            )
            .limit(policy.maximum_requests + 1)
        )
    )
    if len(retained) >= policy.maximum_requests:
        raise HTTPException(409, "reported_feedback_retained_request_capacity")
    zone = ZoneInfo(anchor.cohort.time_zone)
    before_end = anchor.dispatched_at.astimezone(zone).date() - timedelta(days=1)
    after_start = anchor.configuration_observed_at.astimezone(zone).date() + timedelta(days=1)
    request = ReportedAcquisitionRequestV1(
        id=uuid4().hex,
        supersedes_request_id=predecessor.id if predecessor else None,
        anchor=anchor,
        objective=objective,
        policy=policy,
        before=ReportWindowV1(
            starts_on=before_end - timedelta(days=policy.window_days - 1), ends_on=before_end
        ),
        after=ReportWindowV1(
            starts_on=after_start, ends_on=after_start + timedelta(days=policy.window_days - 1)
        ),
        created_at=now,
        expires_at=now + timedelta(seconds=policy.retention_seconds),
    )
    due = max(
        now,
        midnight(request.after.ends_on + timedelta(days=1), zone.key)
        + timedelta(seconds=policy.minimum_close_age_seconds),
    )
    if due >= request.expires_at:
        raise HTTPException(409, "reported_feedback_retention_before_acquisition")
    # Another request never creates another independent action opportunity. Old
    # numeric outputs are invalidated before a new actual acquisition round.
    retract_account_comparisons(db, wid, anchor.cohort.account_id)
    previous = list(
        db.scalars(
            select(ReportedFeedbackJob)
            .where(
                ReportedFeedbackJob.workspace_id == wid,
                ReportedFeedbackJob.opportunity_digest == anchor.opportunity_digest(policy.family),
                ReportedFeedbackJob.state.not_in(("blocked", "expired")),
            )
            .limit(policy.maximum_requests + 1)
        )
    )
    for previous_row in previous:
        from app.reported_feedback.candidate_invalidation import erase_reported_candidates

        erase_reported_candidates(db, wid, previous_row.id)
        previous_row.state = "blocked"
        previous_row.error_code = "superseded_by_explicit_request"

    row = ReportedFeedbackJob(
        id=request.id,
        workspace_id=wid,
        account_id=anchor.cohort.account_id,
        campaign_id=anchor.cohort.campaign_id,
        environment=anchor.environment,
        document=request.model_dump(mode="json"),
        document_digest=request.digest(),
        expires_at=request.expires_at,
        original_attempt_id=anchor.original_attempt_id,
        original_actor_id=principal.user.id,
        original_session_digest=principal.session.digest,
        source_connection_id=anchor.source_connection_id,
        source_generation=anchor.source_generation,
        policy_family=policy.family,
        policy_digest=policy.digest(),
        input_digest=input_digest,
        opportunity_digest=anchor.opportunity_digest(policy.family),
        state="pending",
        completed_observations=0,
        next_due_at=due,
        created_at=now,
    )
    db.add(row)
    db.flush()
    authorize(db, wid, principal.user.id)
    local_job_current(db, row, runtime, effective_now(db, runtime.initial))
    return _progress(row, request)


def _progress(
    row: ReportedFeedbackJob, request: ReportedAcquisitionRequestV1
) -> ComparisonProgressV1:
    return ComparisonProgressV1.model_validate(
        {
            "id": row.id,
            "state": row.state,
            "completed_observations": row.completed_observations,
            "required_observations": 2 * request.policy.distinct_repeat_completions,
            "next_due_at": utc(row.next_due_at) if row.state in {"pending", "waiting"} else None,
            "expires_at": request.expires_at,
            "reason": row.error_code,
        }
    )


def _owned_job(
    db: Session,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    wid: int,
    request_id: str,
    runtime: ReportedFeedbackRuntime,
) -> tuple[ReportedFeedbackJob, ReportedAcquisitionRequestV1]:
    authorize = bind_authority(principal, provider)
    authorize(db, wid, principal.user.id)
    row = db.scalar(
        select(ReportedFeedbackJob)
        .where(
            ReportedFeedbackJob.id == request_id,
            ReportedFeedbackJob.workspace_id == wid,
            ReportedFeedbackJob.original_actor_id == principal.user.id,
            ReportedFeedbackJob.original_session_digest == principal.session.digest,
        )
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise HTTPException(404, "reported_feedback_request_not_found")
    return row, local_job_current(db, row, runtime, effective_now(db, runtime.initial))


def read_comparison_progress(
    db: Session,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    workspace_id: int,
    request_id: str,
    runtime: ReportedFeedbackRuntime,
) -> ComparisonProgressV1:
    row, request = _owned_job(db, principal, provider, workspace_id, request_id, runtime)
    return _progress(row, request)


def _capsules(
    db: Session, row: ReportedFeedbackJob, request: ReportedAcquisitionRequestV1, now: datetime
) -> tuple[ReportedWindowCapsuleV1, ...]:
    rows = list(
        db.scalars(
            select(ReportedWindowCapsule)
            .where(
                ReportedWindowCapsule.workspace_id == row.workspace_id,
                ReportedWindowCapsule.job_id == row.id,
            )
            .order_by(ReportedWindowCapsule.acquisition_completed_at, ReportedWindowCapsule.id)
            .limit(17)
        )
    )
    if len(rows) != row.completed_observations or len(rows) > 16:
        raise HTTPException(409, "reported_feedback_capsule_set_changed")
    result = []
    for capsule in rows:
        value = ReportedWindowCapsuleV1.model_validate(capsule.document)
        completion = db.get(PerformanceCompletion, capsule.completion_id, populate_existing=True)
        if (
            value.id != capsule.id
            or value.digest() != capsule.document_digest
            or value.job_id != row.id
            or value.cohort != request.anchor.cohort
            or value.source_generation != row.source_generation
            or value.environment != row.environment
            or value.policy_digest != row.policy_digest
            or value.completion_id != capsule.completion_id
            or value.acquisition_run_id != capsule.acquisition_run_id
            or (value.window.starts_on, value.window.ends_on)
            != (capsule.starts_on, capsule.ends_on)
            or value.acquisition_started_at != utc(capsule.acquisition_started_at)
            or value.acquisition_completed_at != utc(capsule.acquisition_completed_at)
            or value.expires_at != utc(capsule.expires_at)
            or now >= value.expires_at
            or completion is None
            or completion.workspace_id != row.workspace_id
            or completion.account_id != row.account_id
            or completion.manifest_digest != value.completion_manifest_digest
        ):
            raise HTTPException(409, "reported_feedback_capsule_changed_or_expired")
        result.append(value)
    return tuple(result)


def read_comparison(
    db: Session,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    workspace_id: int,
    request_id: str,
    runtime: ReportedFeedbackRuntime,
) -> OperationalReportedComparisonV1:
    row, request = _owned_job(db, principal, provider, workspace_id, request_id, runtime)
    if (
        row.state != "ready"
        or row.completed_observations != 2 * request.policy.distinct_repeat_completions
    ):
        raise HTTPException(409, "reported_feedback_acquisition_incomplete")
    now = effective_now(db, runtime.initial)
    capsules = _capsules(db, row, request, now)
    input_digest = fingerprint(
        "inlet.reported-comparison-input.v1",
        {
            "request": request.digest(),
            "capsules": sorted(c.digest() for c in capsules),
        },
    )
    old = db.scalar(
        select(ReportedActionComparison).where(
            ReportedActionComparison.workspace_id == workspace_id,
            ReportedActionComparison.input_digest == input_digest,
        )
    )
    if old is not None:
        if utc(old.expires_at) > now:
            result = validate_comparison_dependencies(db, old, now)
            bind_authority(principal, provider)(db, workspace_id, principal.user.id)
            local_job_current(db, row, runtime, effective_now(db, runtime.initial))
            if effective_now(db, runtime.initial) >= result.expires_at:
                raise HTTPException(409, "reported_feedback_comparison_expired")
            return result
        db.delete(old)
        db.flush()
    try:
        result = compare(request, capsules, now)
    except ValueError:
        raise HTTPException(409, "reported_feedback_evidence_unavailable") from None
    owned = dict(workspace_id=workspace_id, account_id=row.account_id, campaign_id=row.campaign_id)
    saved = ReportedActionComparison(
        **owned,
        id=result.id,
        environment=row.environment,
        document=result.model_dump(mode="json"),
        document_digest=result.digest(),
        expires_at=result.expires_at,
        job_id=row.id,
        original_attempt_id=row.original_attempt_id,
        receipt_id=result.anchor.latest_receipt_id,
        receipt_sequence=result.anchor.latest_receipt_sequence,
        policy_family=request.policy.family,
        input_digest=input_digest,
        assessed_at=now,
    )
    db.add(saved)
    db.flush()
    db.add_all(
        [
            ReportedComparisonDependency(**owned, comparison_id=result.id, capsule_id=c.id)
            for c in capsules
        ]
    )
    db.flush()
    bind_authority(principal, provider)(db, workspace_id, principal.user.id)
    local_job_current(db, row, runtime, effective_now(db, runtime.initial))
    if effective_now(db, runtime.initial) >= result.expires_at:
        raise HTTPException(409, "reported_feedback_comparison_expired")
    return result


def validate_comparison_dependencies(
    db: Session, row: ReportedActionComparison, now: datetime
) -> OperationalReportedComparisonV1:
    value = OperationalReportedComparisonV1.model_validate(row.document)
    job = db.get(ReportedFeedbackJob, row.job_id, populate_existing=True)
    if job is None:
        raise HTTPException(409, "reported_feedback_original_request_unavailable")
    principal = local_job_authority(db, job, now)
    request = ReportedAcquisitionRequestV1.model_validate(job.document)
    current = resolve_anchor(db, row.workspace_id, row.original_attempt_id, principal.user.id, now)
    capsules = _capsules(db, job, request, now)
    refs = tuple(value.before.capsules) + tuple(value.after.capsules)
    dependencies = set(
        db.scalars(
            select(ReportedComparisonDependency.capsule_id)
            .where(
                ReportedComparisonDependency.comparison_id == row.id,
                ReportedComparisonDependency.workspace_id == row.workspace_id,
            )
            .limit(17)
        )
    )
    if (
        _current_job_id(db, job) != job.id
        or (
            value.anchor.cohort.workspace_id,
            value.anchor.cohort.account_id,
            value.anchor.cohort.campaign_id,
            value.anchor.environment,
        )
        != (row.workspace_id, row.account_id, row.campaign_id, row.environment)
        or (job.workspace_id, job.account_id, job.campaign_id, job.environment)
        != (row.workspace_id, row.account_id, row.campaign_id, row.environment)
        or value.anchor.original_attempt_id != row.original_attempt_id
        or value.anchor.original_attempt_id != job.original_attempt_id
        or value.id != row.id
        or value.digest() != row.document_digest
        or value.job_id != job.id
        or job.document_digest != request.digest()
        or job.state != "ready"
        or request.expires_at <= now
        or value.expires_at != utc(row.expires_at)
        or now >= value.expires_at
        or value.anchor.latest_receipt_id != row.receipt_id
        or value.anchor.latest_receipt_sequence != row.receipt_sequence
        or value.policy_family != row.policy_family
        or value.policy_digest != job.policy_digest
        or value.anchor != request.anchor
        or current.model_dump(exclude={"privacy_revision"})
        != value.anchor.model_dump(exclude={"privacy_revision"})
        or {(c.id, c.digest()) for c in capsules} != {(c.id, c.digest) for c in refs}
        or dependencies != {c.id for c in capsules}
    ):
        raise HTTPException(409, "reported_feedback_comparison_changed_or_expired")
    # Re-evaluate fresh age/coverage/stability; the immutable assessment may never
    # prolong an observation's eligibility at a later read/export boundary.
    checked = compare(request, capsules, now)
    if (
        checked.status,
        checked.reasons,
        checked.relative_cpa_improvement,
        checked.before,
        checked.after,
    ) != (
        value.status,
        value.reasons,
        value.relative_cpa_improvement,
        value.before,
        value.after,
    ):
        raise HTTPException(409, "reported_feedback_evidence_changed")
    return value


def reobserve_comparison(
    db: Session,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    workspace_id: int,
    request_id: str,
    runtime: ReportedFeedbackRuntime,
) -> ComparisonProgressV1:
    bind_authority(principal, provider)(db, workspace_id, principal.user.id)
    previous = db.scalar(
        select(ReportedFeedbackJob).where(
            ReportedFeedbackJob.id == request_id,
            ReportedFeedbackJob.workspace_id == workspace_id,
            ReportedFeedbackJob.original_actor_id == principal.user.id,
            ReportedFeedbackJob.original_session_digest == principal.session.digest,
        )
    )
    if previous is not None and previous.state == "blocked":
        candidates = list(
            db.scalars(
                select(ReportedFeedbackJob)
                .where(
                    ReportedFeedbackJob.workspace_id == workspace_id,
                    ReportedFeedbackJob.opportunity_digest == previous.opportunity_digest,
                    ReportedFeedbackJob.state.not_in(("blocked", "expired")),
                )
                .limit(2)
            )
        )
        if len(candidates) == 1:
            successor = ReportedAcquisitionRequestV1.model_validate(candidates[0].document)
            if successor.supersedes_request_id == request_id:
                return read_comparison_progress(
                    db, principal, provider, workspace_id, successor.id, runtime
                )
    # Only an explicit owner intent opens a new bounded acquisition round; no
    # counter reset or scheduled retry creates a second independent opportunity.
    row, request = _owned_job(db, principal, provider, workspace_id, request_id, runtime)
    comparison = read_comparison(db, principal, provider, workspace_id, request_id, runtime)
    if comparison.status != "insufficient":
        raise HTTPException(409, "reported_feedback_reobserve_requires_insufficient")
    intent = ComparisonIntentV1(
        attempt_id=request.anchor.original_attempt_id,
        goal_id=request.objective.goal_id,
        goal_revision=request.objective.goal_revision,
        maximum_reported_cpa_micros=request.objective.maximum_reported_cpa_micros,
    )
    return _request(db, principal, provider, workspace_id, intent, runtime, row)


def _active_set(
    db: Session, cohort: CohortV1, policy: ReportedFeedbackPolicyV1, now: datetime
) -> tuple[OperationalReportedComparisonV1, ...]:
    rows = list(
        db.scalars(
            select(ReportedActionComparison)
            .where(
                ReportedActionComparison.workspace_id == cohort.workspace_id,
                ReportedActionComparison.account_id == cohort.account_id,
                ReportedActionComparison.campaign_id == cohort.campaign_id,
                ReportedActionComparison.environment == policy.environment,
                ReportedActionComparison.expires_at > now,
            )
            .order_by(ReportedActionComparison.id)
            .limit(65)
        )
    )
    if len(rows) > 64:
        raise HTTPException(409, "reported_feedback_contribution_capacity")
    unique: dict[str, OperationalReportedComparisonV1] = {}
    for row in rows:
        value = validate_comparison_dependencies(db, row, now)
        if value.anchor.cohort != cohort or value.policy_digest != policy.comparison_policy_digest:
            continue
        if value.status != "operational_reported_as_of":
            continue
        direction = (
            "increase"
            if value.anchor.after_budget_micros > value.anchor.before_budget_micros
            else "decrease"
        )
        if direction != policy.original_change:
            continue
        attempt = value.anchor.original_attempt_id
        if attempt in unique:
            raise HTTPException(409, "reported_feedback_duplicate_original_opportunity")
        unique[attempt] = value
    return tuple(sorted(unique.values(), key=lambda c: c.id))


def _active_digest(values: tuple[OperationalReportedComparisonV1, ...]) -> str:
    return fingerprint(
        "inlet.operational-reported-active-set.v1",
        {
            "comparisons": [
                {"comparison_id": value.id, "document_digest": value.digest()} for value in values
            ]
        },
    )


def validate_preview_dependencies(
    db: Session, row: ReportedFeedbackSlot, now: datetime
) -> ReportedFeedbackPreviewV1:
    """Local export/read fence. Caller owns workspace lock; no commits or network."""
    value = ReportedFeedbackPreviewV1.model_validate(row.document)
    local_job_authority(db, cast(ReportedFeedbackJob, row), now)
    cohort = value.cohort
    active = _active_set(db, cohort, value.policy, now)
    comparison = next((c for c in active if c.id == value.comparison_id), None)
    baseline = db.get(PreviewRow, row.baseline_preview_id, populate_existing=True)
    if (
        value.id != row.id
        or value.digest() != row.document_digest
        or (cohort.workspace_id, cohort.account_id, cohort.campaign_id)
        != (row.workspace_id, row.account_id, row.campaign_id)
        or value.environment != row.environment
        or value.policy.family != row.policy_family
        or value.policy_digest != value.policy.digest()
        or cohort.digest() != row.cohort_digest
        or value.expires_at != utc(row.expires_at)
        or value.created_at != utc(row.created_at)
        or now >= value.expires_at
        or not active
        or comparison is None
        or comparison.digest() != value.comparison_digest
        or row.comparison_id != value.comparison_id
        or comparison.anchor.original_attempt_id != row.original_attempt_id
        or comparison.anchor.opportunity_digest(value.policy.family) != row.opportunity_digest
        or row.opportunity_digest != value.opportunity_digest
        or _active_digest(active) != value.active_set_digest
        or len(active) != value.distinct_original_attempt_count
        or min(c.expires_at for c in active) < value.expires_at
        or baseline is None
        or baseline.workspace_id != row.workspace_id
        or baseline.original_actor_id != row.original_actor_id
        or baseline.original_session_digest != row.original_session_digest
        or baseline.document_digest != value.baseline_preview_digest
        or baseline.id != value.baseline_preview_id
        or utc(baseline.expires_at) < value.expires_at
    ):
        raise HTTPException(409, "reported_feedback_preview_changed_or_expired")
    try:
        base_document = bind_preview_row(
            {column.name: getattr(baseline, column.name) for column in baseline.__table__.columns}
        )
    except ValueError as exc:
        raise HTTPException(409, "reported_feedback_baseline_changed") from exc
    require_native_quantum(base_document, value.proposed_budget_micros)
    if (
        base_document.digest() != baseline.document_digest
        or base_document.id != baseline.id
        or (
            isinstance(base_document, InitialPreviewV2)
            and base_document.environment != value.environment
        )
        or base_document.objective != comparison.objective
        or base_document.after_budget_micros != value.baseline_budget_micros
        or base_document.recommendation_status != "proposed"
        or base_document.created_at
        < max(ref.acquired_at for ref in (*comparison.before.capsules, *comparison.after.capsules))
        or value.delta_micros != bounded_delta(active, value.policy)
        or len(active) < value.policy.minimum_distinct_original_attempts
        or value.before_reported_cpa_micros != comparison.before.reported_cpa_micros
        or value.after_reported_cpa_micros != comparison.after.reported_cpa_micros
    ):
        raise HTTPException(409, "reported_feedback_baseline_changed")
    return value


def require_native_quantum(
    baseline: InitialPreviewV1 | InitialPreviewV2, proposed_micros: int
) -> None:
    """V2 observed currency precision is a display constraint, never spending authority."""
    if isinstance(baseline, InitialPreviewV2):
        native = baseline.native_observation
        if native is None or proposed_micros % 10 ** (6 - native.currency_exponent):
            raise HTTPException(409, "reported_feedback_native_amount_unrepresentable")


def apply_feedback_preview(
    db: Session,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    workspace_id: int,
    intent: FeedbackPreviewIntentV1,
    runtime: ReportedFeedbackRuntime,
) -> ReportedFeedbackPreviewV1:
    authorize = bind_authority(principal, provider)
    authorize(db, workspace_id, principal.user.id)
    policy = runtime.feedback_policy
    if (
        policy is None
        or runtime.window_policy is None
        or policy.comparison_policy_digest != runtime.window_policy.digest()
    ):
        raise HTTPException(409, "reported_feedback_not_configured")
    if policy.minimum_distinct_original_attempts != 1:
        raise HTTPException(409, "reported_feedback_historical_multi_action_profile_unavailable")
    row = db.scalar(
        select(ReportedActionComparison).where(
            ReportedActionComparison.id == intent.comparison_id,
            ReportedActionComparison.workspace_id == workspace_id,
        )
    )
    if row is None:
        raise HTTPException(404, "reported_feedback_comparison_not_found")
    job, _ = _owned_job(db, principal, provider, workspace_id, row.job_id, runtime)
    now = effective_now(db, runtime.initial)
    comparison = validate_comparison_dependencies(db, row, now)
    baseline = initial_preview.read_preview(
        db, principal, provider, workspace_id, intent.baseline_preview_id, runtime.initial
    )
    baseline_row = db.get(PreviewRow, baseline.id)
    assert baseline_row is not None
    if (
        (isinstance(baseline, InitialPreviewV2) and baseline.environment != policy.environment)
        or baseline.objective != comparison.objective
        or baseline.after_budget_micros is None
        or baseline.created_at
        < max(ref.acquired_at for ref in (*comparison.before.capsules, *comparison.after.capsules))
        or baseline.recommendation_status != "proposed"
        or policy.environment != comparison.anchor.environment
    ):
        raise HTTPException(409, "reported_feedback_post_acquisition_baseline_required")
    active = _active_set(db, comparison.anchor.cohort, policy, now)
    if comparison not in active or len(active) < policy.minimum_distinct_original_attempts:
        raise HTTPException(409, "reported_feedback_independent_opportunities_insufficient")
    delta = bounded_delta(active, policy)
    proposed = baseline.after_budget_micros + delta
    if proposed <= 0:
        raise HTTPException(409, "reported_feedback_proposed_budget_nonpositive")
    require_native_quantum(baseline, proposed)
    # Displayed nominal amount stays inside the separately consented plan too;
    # this calculation creates no reservation, authority, or execution intent.
    reference = preview_mandate_reference(
        {
            column.name: getattr(baseline_row, column.name)
            for column in baseline_row.__table__.columns
        },
        baseline,
    )
    if reference is None:
        raise HTTPException(409, "reported_feedback_budget_baseline_required")
    binding = customer_intents.binding(
        db, workspace_id, *reference
    )
    _, mandate = execution_mandates.checked(
        db, workspace_id, binding, principal.user.id, lambda: effective_now(db, runtime.initial)
    )
    if proposed > min(mandate.per_plan_cap_micros, mandate.total_cap_micros) or (
        baseline.before_budget_micros is not None
        and proposed - baseline.before_budget_micros > mandate.positive_change_cap_micros
    ):
        raise HTTPException(409, "reported_feedback_nominal_plan_limit")
    expiry = min(
        baseline.expires_at,
        *(c.expires_at for c in active),
        now + timedelta(seconds=policy.lifetime_seconds),
    )
    assert (
        comparison.before.reported_cpa_micros is not None
        and comparison.after.reported_cpa_micros is not None
    )
    value = ReportedFeedbackPreviewV1(
        id=uuid4().hex,
        environment=policy.environment,
        cohort=comparison.anchor.cohort,
        policy=policy,
        comparison_id=comparison.id,
        comparison_digest=comparison.digest(),
        baseline_preview_id=baseline.id,
        baseline_preview_digest=baseline_row.document_digest,
        opportunity_digest=comparison.anchor.opportunity_digest(policy.family),
        active_set_digest=_active_digest(active),
        policy_digest=policy.digest(),
        distinct_original_attempt_count=len(active),
        before_reported_cpa_micros=comparison.before.reported_cpa_micros,
        after_reported_cpa_micros=comparison.after.reported_cpa_micros,
        baseline_budget_micros=baseline.after_budget_micros,
        delta_micros=delta,
        proposed_budget_micros=proposed,
        explanation=(
            "configuration_associated_reported_efficiency_not_causal",
            "distinct_original_attempts_only",
            "recomputed_from_unadjusted_baseline",
            "bounded_by_explicit_server_policy",
            "no_spending_authority_or_review_handoff",
        ),
        created_at=now,
        expires_at=expiry,
    )
    from app.reported_feedback.revisions import append_revision, current_slot

    probe = ReportedFeedbackSlot(
        workspace_id=workspace_id,
        environment=policy.environment,
        original_attempt_id=job.original_attempt_id,
        policy_family=policy.family,
        cohort_digest=value.cohort.digest(),
    )
    old = current_slot(db, probe)
    if old is not None and utc(old.expires_at) > now:
        previous = ReportedFeedbackPreviewV1.model_validate(old.document)
        if (
            previous.comparison_digest == value.comparison_digest
            and previous.baseline_preview_id == value.baseline_preview_id
            and previous.baseline_preview_digest == value.baseline_preview_digest
            and previous.policy_digest == value.policy_digest
            and previous.active_set_digest == value.active_set_digest
            and old.original_actor_id == principal.user.id
            and old.original_session_digest == principal.session.digest
        ):
            authorize(db, workspace_id, principal.user.id)
            local_job_current(db, job, runtime, effective_now(db, runtime.initial))
            return validate_preview_dependencies(db, old, effective_now(db, runtime.initial))
    revision = old.revision + 1 if old else 1
    saved = ReportedFeedbackSlot(
        id=value.id,
        workspace_id=workspace_id,
        account_id=job.account_id,
        campaign_id=job.campaign_id,
        environment=policy.environment,
        document=value.model_dump(mode="json"),
        document_digest=value.digest(),
        expires_at=value.expires_at,
        comparison_id=value.comparison_id,
        baseline_preview_id=baseline.id,
        original_attempt_id=job.original_attempt_id,
        original_actor_id=principal.user.id,
        original_session_digest=principal.session.digest,
        policy_family=policy.family,
        cohort_digest=value.cohort.digest(),
        opportunity_digest=value.opportunity_digest,
        revision=revision,
        created_at=now,
    )
    append_revision(db, saved)
    authorize(db, workspace_id, principal.user.id)
    local_job_current(db, job, runtime, effective_now(db, runtime.initial))
    # Appending preserves source/privacy epochs; final evidence still must be current.
    # The caller rolls back both revision and pointer on any rejection.
    initial_preview.read_preview(
        db, principal, provider, workspace_id, baseline.id, runtime.initial
    )
    return validate_preview_dependencies(db, saved, effective_now(db, runtime.initial))


def read_feedback_preview(
    db: Session,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    workspace_id: int,
    preview_id: str,
    runtime: ReportedFeedbackRuntime,
) -> ReportedFeedbackPreviewV1:
    bind_authority(principal, provider)(db, workspace_id, principal.user.id)
    row = db.scalar(
        select(ReportedFeedbackSlot).where(
            ReportedFeedbackSlot.id == preview_id,
            ReportedFeedbackSlot.workspace_id == workspace_id,
            ReportedFeedbackSlot.original_actor_id == principal.user.id,
            ReportedFeedbackSlot.original_session_digest == principal.session.digest,
        )
    )
    if row is None:
        raise HTTPException(404, "reported_feedback_preview_not_found")
    from app.reported_feedback.revisions import require_current_slot

    require_current_slot(db, row)
    value = validate_preview_dependencies(db, row, effective_now(db, runtime.initial))
    if runtime.feedback_policy != value.policy:
        raise HTTPException(409, "reported_feedback_policy_changed")
    initial_preview.read_preview(
        db, principal, provider, workspace_id, value.baseline_preview_id, runtime.initial
    )
    bind_authority(principal, provider)(db, workspace_id, principal.user.id)
    return validate_preview_dependencies(db, row, effective_now(db, runtime.initial))
