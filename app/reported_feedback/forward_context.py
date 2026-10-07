"""Server-only exact candidate successor, never a general historical source exemption."""

from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.optimization_candidates.documents import parse_decision_document, parse_work_document
from app.optimization_candidates.models import CandidateJob, CandidateResult
from app.optimization_candidates.review_models import CandidateReviewLink
from app.publication.execution_models import (
    ProviderExecutionReview,
    ProviderExecutionRun,
    ProviderExposureReservation,
    ProviderReservationReplacement,
)
from app.publication.replacement_contracts import RepeatOptimizationReview, parse_review
from app.reported_feedback.candidate_contracts import ReportedRuleCandidateV1, ReportedRuleWorkV1


@dataclass(frozen=True)
class ReportedForwardContext:
    review_id: str
    actor_id: str
    original_session_digest: str


def owned_successor(
    db: Session,
    wid: int,
    attempt_id: str,
    original: ProviderExecutionRun,
    held: ProviderExposureReservation,
    context: ReportedForwardContext,
) -> str:
    def deny() -> HTTPException:
        return HTTPException(409, "reported_rule_own_successor_unavailable")

    link = db.get(CandidateReviewLink, context.review_id, populate_existing=True)
    review = db.get(ProviderExecutionReview, context.review_id, populate_existing=True)
    result = (
        db.get(CandidateResult, link.candidate_result_id, populate_existing=True)
        if link and link.candidate_result_id
        else None
    )
    job = db.get(CandidateJob, result.job_id, populate_existing=True) if result else None
    if (
        link is None
        or review is None
        or result is None
        or job is None
        or any(row.workspace_id != wid for row in (link, review, result, job))
        or link.candidate_workspace_id != wid
        or link.actor_id != context.actor_id
        or job.actor_id != context.actor_id
        or link.original_session_digest != context.original_session_digest
        or job.auth_session_digest != context.original_session_digest
        or not review.candidate_provenance_required
    ):
        raise deny()
    work, decision, document = (
        parse_work_document(job.work),
        parse_decision_document(result.decision),
        parse_review(review.document),
    )
    if (
        not isinstance(work, ReportedRuleWorkV1)
        or not isinstance(decision, ReportedRuleCandidateV1)
        or not isinstance(document, RepeatOptimizationReview)
    ):
        raise deny()
    successor = db.scalar(
        select(ProviderExecutionRun).where(
            ProviderExecutionRun.workspace_id == wid, ProviderExecutionRun.review_id == review.id
        )
    )
    audit = db.scalar(
        select(ProviderReservationReplacement).where(
            ProviderReservationReplacement.workspace_id == wid,
            ProviderReservationReplacement.predecessor_id == original.reservation_id,
            ProviderReservationReplacement.successor_id == held.id,
        )
    )
    plan = document.plan
    if (
        successor is None
        or audit is None
        or successor.canceled_at is not None
        or successor.reservation_id != held.id
        or audit.successor_run_id != successor.id
        or audit.review_id != review.id
        or audit.actor != context.actor_id
        or audit.environment != held.environment
        or audit.ledger_id != held.ledger_id
        or audit.budget_owner_key != held.budget_owner_key
        or document.predecessor.predecessor_id != original.reservation_id
        or work.scope.source.attempt_id != attempt_id
        or decision.evidence.opportunity.original_attempt_id != attempt_id
        or decision.scope != work.scope
        or decision.digest() != result.decision_digest
        or result.decision_digest != link.candidate_digest
        or work.digest() != job.input_digest
        or result.input_digest != job.input_digest
        or link.input_digest != job.input_digest
        or work.selection.manifest_digest != link.selection_digest
        or work.policy.digest() != link.policy_digest
        or decision.policy_digest != work.policy.digest()
        or decision.evidence_digest != result.evidence_digest
        or result.evidence_digest != link.evidence_digest
        or document.digest() != review.digest
        or review.digest != link.review_digest
        or plan.digest() != review.plan_digest
        or review.plan_digest != link.plan_digest
        or plan.intent.scope != work.scope.account
        or plan.intent.mandate != work.scope.mandate
        or plan.intent.target != work.scope.target
        or plan.intent.action != decision.action
        or plan.before.digest() != decision.state_digest
        or held.ledger_id != work.scope.mandate.ledger_id
        or held.environment != work.policy.environment
        or held.budget_owner_key != work.scope.budget_owner_key
    ):
        raise deny()
    return successor.id
