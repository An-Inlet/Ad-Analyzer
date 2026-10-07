"""Automatically prepare an exact review, never manufacture customer approval."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.customers.access import CustomerPrincipal
from app.customers.models import CustomerSession, CustomerUser
from app.initial_planning.automatic_contracts import InitialReportedRuleWorkV1
from app.optimization_candidates import service as candidates
from app.optimization_candidates.documents import CandidateDecisionDocument
from app.optimization_candidates.models import CandidateResult
from app.optimization_candidates.review_contracts import (
    CandidateReviewIntent,
    CandidateReviewPrepared,
)
from app.optimization_candidates.review_models import CandidateReviewLink
from app.optimization_candidates.selection_contracts import CandidateWorkV2
from app.publication import execution_mandates, optimization, replacement
from app.publication.contracts import fingerprint
from app.publication.customer_authority import bind_authority
from app.publication.execution_models import ProviderExecutionReview, ProviderExposureReservation
from app.publication.optimization_execution_contracts import OptimizationRuntime
from app.publication.replacement_contracts import OptimizationReview, parse_review
from app.reported_feedback.candidate_contracts import ReportedRuleWorkV1


@dataclass(frozen=True)
class CandidateReviewRuntime:
    candidate: candidates.CandidateRuntime
    execution: OptimizationRuntime
    clock: Callable[[], datetime]


def get_candidate_review_runtime() -> CandidateReviewRuntime | None:
    return None


def original(db: Session, actor: str, session_digest: str) -> CustomerPrincipal:
    user = db.get(CustomerUser, actor, populate_existing=True)
    session = db.get(CustomerSession, session_digest, populate_existing=True)
    if user is None or session is None or session.user_id != actor:
        raise HTTPException(401, "original candidate session unavailable")
    return CustomerPrincipal(user, session)


def source_digest(work: CandidateWorkV2 | ReportedRuleWorkV1 | InitialReportedRuleWorkV1) -> str:
    return fingerprint("inlet.candidate-source.v1", work.scope.source.model_dump(mode="json"))


def bound_candidate(
    db: Session,
    wid: int,
    result_id: str,
    actor: str,
    session_digest: str,
    runtime: CandidateReviewRuntime,
    *,
    forward_review_id: str | None = None,
) -> tuple[
    CustomerPrincipal,
    CandidateDecisionDocument,
    CandidateResult,
    CandidateWorkV2 | ReportedRuleWorkV1 | InitialReportedRuleWorkV1,
]:
    principal = original(db, actor, session_digest)
    decision = candidates.read_result(
        db,
        wid,
        result_id,
        principal,
        runtime.candidate,
        erase_invalid=False,
        forward_review_id=forward_review_id,
    )
    result = db.get(CandidateResult, result_id, populate_existing=True)
    if result is None or result.workspace_id != wid:
        raise HTTPException(409, "candidate review source retracted")
    job = candidates.load(db, wid, result.job_id)
    work = candidates.owned_work(job)
    if (
        not isinstance(work, (CandidateWorkV2, ReportedRuleWorkV1, InitialReportedRuleWorkV1))
        or job.actor_id != actor
        or job.auth_session_digest != session_digest
        or decision.status != "suggested"
        or decision.action is None
        or decision.expires_at <= runtime.clock()
    ):
        raise HTTPException(409, "current original-session selected suggestion required")
    return principal, decision, result, work


def validate_plan(decision: CandidateDecisionDocument, document: OptimizationReview) -> None:
    plan, scope = document.plan, decision.scope
    if (
        plan.before.digest() != decision.state_digest
        or plan.intent.action != decision.action
        or plan.intent.scope != scope.account
        or plan.intent.mandate != scope.mandate
        or plan.intent.target != scope.target
        or plan.intent.budget_owner.key(scope.account) != scope.budget_owner_key
        or plan.intent.approved_target_set_digest != scope.target_set_digest
        or plan.intent.rationale_reference != decision.digest()
    ):
        raise HTTPException(409, "candidate and exact optimization plan changed")


def validate_bound_review(
    db: Session,
    wid: int,
    review_id: str,
    actor: str,
    principal: CustomerPrincipal,
    decision: CandidateDecisionDocument,
    result: CandidateResult,
    work: CandidateWorkV2 | ReportedRuleWorkV1 | InitialReportedRuleWorkV1,
    runtime: CandidateReviewRuntime,
    clock: Callable[[], datetime],
) -> None:
    """Internal second half of a guard, only with a freshly bound locked candidate."""
    # Workspace/session/source locks precede this FK fence. A concurrent derived
    # deletion must either retract before this check or wait for admission commit.
    link = db.get(CandidateReviewLink, review_id, populate_existing=True, with_for_update=True)
    if (
        link is None
        or link.workspace_id != wid
        or link.actor_id != actor
        or link.candidate_result_id != result.id
        or link.candidate_workspace_id != wid
    ):
        raise HTTPException(409, "candidate review retracted during admission")
    row = db.get(ProviderExecutionReview, review_id, populate_existing=True)
    if row is None or row.workspace_id != wid:
        raise HTTPException(409, "candidate review unavailable")
    document = parse_review(row.document)
    validate_plan(decision, document)
    if (
        row.digest != link.review_digest
        or row.plan_digest != link.plan_digest
        or document.digest() != link.review_digest
        or document.plan.digest() != link.plan_digest
        or result.decision_digest != link.candidate_digest
        or result.input_digest != link.input_digest
        or work.selection.manifest_digest != link.selection_digest
        or work.policy.digest() != link.policy_digest
        or decision.evidence_digest != link.evidence_digest
        or source_digest(work) != link.source_digest
        or work.policy.environment != link.environment
    ):
        raise HTTPException(409, "candidate review provenance changed")
    candidates.authorize(db, principal, wid, runtime.candidate)
    if min(decision.expires_at, work.selection.expires_at) <= clock():
        raise HTTPException(409, "candidate review expired after authority check")


def guard_for(runtime: CandidateReviewRuntime):  # type: ignore[no-untyped-def]
    def guard(
        db: Session, wid: int, review_id: str, actor: str, clock: Callable[[], datetime]
    ) -> None:
        link = db.get(CandidateReviewLink, review_id, populate_existing=True)
        if (
            link is None
            or link.workspace_id != wid
            or link.actor_id != actor
            or link.candidate_result_id is None
            or link.candidate_workspace_id != wid
        ):
            raise HTTPException(409, "candidate review provenance retracted")
        fresh = replace(runtime, clock=clock, candidate=replace(runtime.candidate, clock=clock))
        result_id = link.candidate_result_id
        principal, decision, result, work = bound_candidate(
            db,
            wid,
            result_id,
            actor,
            link.original_session_digest,
            fresh,
            forward_review_id=review_id,
        )
        validate_bound_review(
            db, wid, review_id, actor, principal, decision, result, work, fresh, clock
        )

    return guard


def bind_execution(
    runtime: CandidateReviewRuntime, principal: CustomerPrincipal
) -> OptimizationRuntime:
    return replace(
        runtime.execution,
        authorize=bind_authority(principal, runtime.candidate.identity),
        candidate_review_guard=guard_for(runtime),
        candidate_review_writer=None,
    )


def prepare_candidate_review(
    db: Session,
    principal: CustomerPrincipal,
    wid: int,
    intent: CandidateReviewIntent,
    runtime: CandidateReviewRuntime,
) -> CandidateReviewPrepared:
    actor, token = principal.user.id, principal.session.digest
    candidates.authorize(db, principal, wid, runtime.candidate)
    principal, decision, result, work = bound_candidate(
        db, wid, intent.result_id, actor, token, runtime
    )
    if decision.digest() != intent.expected_decision_digest:
        raise HTTPException(409, "candidate decision changed")
    ledger, policy = execution_mandates.checked(db, wid, work.scope.mandate, actor, runtime.clock)
    used = optimization.positive_changes_used(db, wid, ledger.id)
    if used > policy.positive_change_cap_micros or ledger.action_count >= policy.action_limit:
        raise HTTPException(409, "candidate cumulative mandate unavailable")
    reservations = list(
        db.scalars(
            select(ProviderExposureReservation)
            .where(
                ProviderExposureReservation.workspace_id == wid,
                ProviderExposureReservation.environment == policy.environment,
                ProviderExposureReservation.budget_owner_key == work.scope.budget_owner_key,
                ProviderExposureReservation.state == "held",
            )
            .with_for_update()
        )
    )
    if len(reservations) > 1 or (reservations and reservations[0].ledger_id != ledger.id):
        raise HTTPException(409, "candidate retained predecessor unavailable")
    predecessor = reservations[0].id if reservations else None

    def writer(
        session: Session, row: ProviderExecutionReview, document: OptimizationReview
    ) -> None:
        current_principal, current_decision, current_result, current_work = bound_candidate(
            session, wid, intent.result_id, actor, token, runtime
        )
        if current_decision.digest() != intent.expected_decision_digest:
            raise HTTPException(409, "candidate decision changed during qualification")
        validate_plan(current_decision, document)
        current_ledger, current_policy = execution_mandates.checked(
            session, wid, current_work.scope.mandate, actor, runtime.clock
        )
        if (
            optimization.positive_changes_used(session, wid, current_ledger.id)
            + document.plan.positive_change_micros
            > current_policy.positive_change_cap_micros
            or current_ledger.action_count >= current_policy.action_limit
        ):
            raise HTTPException(409, "candidate cumulative allowance changed")
        optimization.validate_document(document, current_policy, runtime.clock())
        existing = session.get(CandidateReviewLink, row.id)
        if existing is not None:
            guard_for(runtime)(session, wid, row.id, actor, runtime.clock)
            optimization.validate_document(document, current_policy, runtime.clock())
            return
        if row.actor != actor or row.workspace_id != wid or row.digest != document.digest():
            raise HTTPException(409, "candidate review persistence changed")
        row.candidate_provenance_required = True
        session.add(
            CandidateReviewLink(
                review_id=row.id,
                workspace_id=wid,
                candidate_result_id=current_result.id,
                candidate_workspace_id=wid,
                actor_id=actor,
                original_session_digest=token,
                environment=work.policy.environment,
                candidate_digest=current_decision.digest(),
                input_digest=current_result.input_digest,
                selection_digest=current_work.selection.manifest_digest,
                policy_digest=current_work.policy.digest(),
                evidence_digest=current_decision.evidence_digest,
                source_digest=source_digest(current_work),
                review_digest=row.digest,
                plan_digest=row.plan_digest,
                created_at=runtime.clock(),
            )
        )
        session.flush()
        guard_for(runtime)(session, wid, row.id, actor, runtime.clock)
        optimization.validate_document(document, current_policy, runtime.clock())

    execution = replace(bind_execution(runtime, principal), candidate_review_writer=writer)
    assert decision.action is not None
    try:
        if predecessor is None:
            row = optimization.prepare_optimization(
                db,
                wid,
                work.scope.mandate,
                work.scope.account,
                work.scope.target,
                decision.action,
                decision.digest(),
                actor,
                execution,
                runtime.clock,
            )
        else:
            row = replacement.prepare_repeat_optimization(
                db,
                wid,
                work.scope.mandate,
                work.scope.account,
                predecessor,
                work.scope.target,
                decision.action,
                decision.digest(),
                actor,
                execution,
                runtime.clock,
            )
        return CandidateReviewPrepared(
            review_id=row.id, review_digest=row.digest, plan_digest=row.plan_digest
        )
    except Exception:
        db.rollback()
        raise
