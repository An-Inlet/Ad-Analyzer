"""Owned operational comparison/application services; no provider mutation authority."""

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.customers.access import CustomerPrincipal
from app.customers.models import CustomerMembership, CustomerSession, CustomerUser
from app.initial_planning.clock import effective_now
from app.reported_feedback.anchor import resolve_anchor
from app.reported_feedback.contracts import ReportedAcquisitionRequestV1
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
