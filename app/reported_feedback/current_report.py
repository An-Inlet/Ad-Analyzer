"""Local fixed-window provenance, independent of rolling cadence or write authority."""

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.campaign_performance.models import PerformanceCompletion
from app.lifecycle.privacy import database_utc_now
from app.meta.models import MetaConnection
from app.meta.security import utc
from app.reported_feedback.contracts import ReportedAcquisitionRequestV1
from app.reported_feedback.models import ReportedFeedbackJob, ReportedWindowCapsule
from app.reported_feedback.service import _capsules, _current_job_id, local_job_authority


def require_fixed_current(
    db: Session, source: MetaConnection, completion: PerformanceCompletion, campaign_id: int
) -> None:
    """Caller retains workspace/source locks and verifies current pointer/metric manifest.

    Only the campaign actually acquired by a still-owned, current job can use this
    alternate coverage proof. This does not qualify an action or consult spending
    reservations, current runtime policy, or provider APIs.
    """

    def denied() -> HTTPException:
        return HTTPException(409, "current campaign reporting evidence unavailable")

    rows = list(
        db.scalars(
            select(ReportedWindowCapsule)
            .where(
                ReportedWindowCapsule.workspace_id == source.workspace_id,
                ReportedWindowCapsule.account_id == source.account_id,
                ReportedWindowCapsule.campaign_id == campaign_id,
                ReportedWindowCapsule.completion_id == completion.id,
            )
            .limit(2)
        )
    )
    if len(rows) != 1:
        raise denied()
    capsule = rows[0]
    job = db.get(ReportedFeedbackJob, capsule.job_id, populate_existing=True)
    if job is None:
        raise denied()
    now = database_utc_now(db)
    local_job_authority(db, job, now)
    try:
        request = ReportedAcquisitionRequestV1.model_validate(job.document)
        cohort = request.anchor.cohort
        if (
            _current_job_id(db, job) != job.id
            or job.state in {"blocked", "expired"}
            or job.error_code is not None
            or request.id != job.id
            or request.digest() != job.document_digest
            or request.expires_at != utc(job.expires_at)
            or now >= request.expires_at
            or request.anchor.original_attempt_id != job.original_attempt_id
            or request.anchor.opportunity_digest(request.policy.family) != job.opportunity_digest
            or request.policy.family != job.policy_family
            or request.policy.digest() != job.policy_digest
            or request.anchor.environment != job.environment
            or (cohort.workspace_id, cohort.account_id, cohort.campaign_id)
            != (source.workspace_id, source.account_id, campaign_id)
            or (job.workspace_id, job.account_id, job.campaign_id)
            != (source.workspace_id, source.account_id, campaign_id)
            or request.anchor.source_connection_id != source.id
            or job.source_connection_id != source.id
            or request.anchor.source_generation != source.generation
            or job.source_generation != source.generation
            or cohort.selected_event != completion.selected_event
            or cohort.currency != completion.currency
            or cohort.time_zone != completion.time_zone
            or cohort.query_version != completion.query_version
            or cohort.reporting_basis != completion.reporting_basis
        ):
            raise denied()
        values = _capsules(db, job, request, now)
        value = next((v for v in values if v.id == capsule.id), None)
        if (
            value is None
            or value.window not in (request.before, request.after)
            or (value.window.starts_on, value.window.ends_on)
            != (completion.starts_on, completion.ends_on)
            or value.acquisition_completed_at != utc(completion.completed_at)
            or value.captured_at != utc(capsule.captured_at)
            or value.captured_privacy_revision != completion.privacy_revision
            or capsule.source_generation != source.generation
        ):
            raise denied()
    except ValidationError:
        raise denied() from None
    local_job_authority(db, job, database_utc_now(db))
