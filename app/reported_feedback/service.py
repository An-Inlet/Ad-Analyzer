"""Owned operational comparison/application services; no provider mutation authority."""

from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.customers.access import CustomerPrincipal
from app.customers.identity import IdentityProvider
from app.customers.models import CustomerMembership, CustomerSession, CustomerUser
from app.initial_planning.clock import effective_now
from app.initial_planning.contracts import EfficiencyObjectiveV1
from app.meta.security import utc
from app.publication.contracts import fingerprint
from app.publication.customer_authority import bind_authority
from app.reported_feedback.anchor import resolve_anchor
from app.reported_feedback.contracts import (
    ComparisonIntentV1,
    ComparisonProgressV1,
    ReportedAcquisitionRequestV1,
    ReportWindowV1,
)
from app.reported_feedback.evaluator import midnight
from app.reported_feedback.invalidation import retract_account_comparisons
from app.reported_feedback.models import ReportedFeedbackJob
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


def local_job_current(
    db: Session, job: ReportedFeedbackJob, runtime: ReportedFeedbackRuntime, now: datetime
) -> ReportedAcquisitionRequestV1:
    """Caller holds workspace/native fence; no new principal locks or external IO."""
    now = max(now, effective_now(db, runtime.initial))
    principal = local_job_authority(db, job, now)
    request = ReportedAcquisitionRequestV1.model_validate(job.document)
    if (
        request.digest() != job.document_digest
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
    if predecessor is not None:
        predecessor.state = "blocked"
        predecessor.error_code = "superseded_by_explicit_reobservation"
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
