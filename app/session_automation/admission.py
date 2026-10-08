"""Atomic semantic consumption plus a run with explicit automatic authority."""

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import advertising_capabilities
from app.customers.access import CustomerPrincipal
from app.initial_planning.automatic_contracts import InitialReportedRuleCandidateV1
from app.initial_planning.automatic_source import INITIAL_RULE_PRODUCER_FAMILY
from app.initial_planning.start_contracts import InitialRuleAutomaticPolicyV1
from app.initial_planning.start_service import linked_work
from app.optimization_candidates import review_bridge
from app.optimization_candidates.contracts import CandidateDecision
from app.optimization_candidates.documents import CandidateDecisionDocument
from app.optimization_candidates.review_models import CandidateReviewLink
from app.publication import optimization
from app.publication.contracts import fingerprint
from app.publication.execution_models import (
    ProviderExecutionApproval,
    ProviderExecutionReview,
    ProviderExecutionRun,
)
from app.publication.optimization_execution_contracts import OptimizationRuntime
from app.reported_feedback.automatic_contracts import (
    REPORTED_RULE_EPOCH_FAMILY,
    ReportedRuleAutomaticPolicyV1,
)
from app.reported_feedback.candidate_contracts import ReportedRuleCandidateV1
from app.session_automation import service
from app.session_automation.contracts import SemanticDecisionEpoch, SessionMandateDecisionAuthority
from app.session_automation.models import AutomaticDecisionAdmission
from app.session_automation.runtime import AutomaticPolicyDocument, SessionAutomationRuntime
from app.shopify.security import utc


def epoch_for(
    db: Session,
    principal: CustomerPrincipal,
    decision: CandidateDecisionDocument,
    families: list[str] | tuple[str, ...],
    runtime: SessionAutomationRuntime,
    policy: AutomaticPolicyDocument | None = None,
) -> SemanticDecisionEpoch:
    if isinstance(decision, InitialReportedRuleCandidateV1):
        if (
            not isinstance(policy, InitialRuleAutomaticPolicyV1)
            or decision.policy_digest != policy.candidate_policy_digest
            or tuple(families) != (INITIAL_RULE_PRODUCER_FAMILY,)
        ):
            raise HTTPException(409, "explicit initial automatic policy required")
        return SemanticDecisionEpoch(
            producer_family=INITIAL_RULE_PRODUCER_FAMILY,
            source_schema=decision.evidence.source_schema,
            source_reference=decision.evidence.basis.opportunity_id,
            semantic_digest=decision.evidence.basis.semantic_key_digest,
        )
    if isinstance(policy, InitialRuleAutomaticPolicyV1):
        raise HTTPException(409, "initial automatic policy basis changed")
    if isinstance(decision, ReportedRuleCandidateV1):
        if (
            not isinstance(policy, ReportedRuleAutomaticPolicyV1)
            or decision.policy_digest != policy.candidate_policy_digest
            or tuple(families) != (REPORTED_RULE_EPOCH_FAMILY,)
        ):
            raise HTTPException(409, "explicit operational automatic policy required")
        # Caller first bound the owned result through the final DB-only source guard.
        # Use immutable original request opportunity, never a report/policy/session refresh.
        return SemanticDecisionEpoch(
            producer_family=REPORTED_RULE_EPOCH_FAMILY,
            source_schema=decision.evidence.source_schema,
            source_reference=decision.evidence.opportunity.original_attempt_id,
            semantic_digest=decision.evidence.opportunity.semantic_digest,
        )
    if isinstance(policy, ReportedRuleAutomaticPolicyV1):
        raise HTTPException(409, "automatic policy basis changed")
    if not isinstance(decision, CandidateDecision):
        raise HTTPException(409, "initial automatic admission unavailable")
    matches = [
        p
        for p in runtime.epoch_producers
        if p.family in families
        and p.source_schema == decision.evidence.source_schema
        and p.environment == decision.scope.mandate.environment
    ]
    if (
        len(matches) != 1
        or decision.evidence.qualification == "unqualified"
        or (
            decision.scope.mandate.environment == "live"
            and decision.evidence.qualification != "qualified_learning"
        )
    ):
        raise HTTPException(409, "evidence_not_ready")
    producer = matches[0]
    if producer.authorized_read is not None:
        value = producer.authorized_read(db, principal, decision)
    elif producer.read is not None:
        value = producer.read(db, decision)
    else:
        raise HTTPException(409, "semantic evidence reader unavailable")
    epoch = SemanticDecisionEpoch.model_validate(value.model_dump(mode="json"))
    if (
        epoch.producer_family != matches[0].family
        or epoch.source_schema != decision.evidence.source_schema
        or epoch.source_reference != decision.evidence.source_reference
    ):
        raise HTTPException(409, "semantic evidence binding changed")
    return epoch


def account_identity(decision: CandidateDecisionDocument) -> str:
    account = decision.scope.account
    return fingerprint(
        "inlet.automatic-native-account.v1",
        {
            "platform": account.account.platform,
            "external_advertiser_id": account.external_advertiser_id,
        },
    )


def guard_for(runtime: SessionAutomationRuntime):  # type: ignore[no-untyped-def]
    def guard(
        db: Session, wid: int, review_id: str, actor: str, clock: Callable[[], datetime]
    ) -> None:
        fresh = replace(runtime, clock=clock)
        admission = db.scalar(
            select(AutomaticDecisionAdmission).where(
                AutomaticDecisionAdmission.workspace_id == wid,
                AutomaticDecisionAdmission.review_id == review_id,
            )
        )
        if admission is None:
            raise HTTPException(409, "automatic decision authority unavailable")
        row, principal, policy, _ = service.current(db, wid, admission.session_run_id, fresh)
        link = db.get(CandidateReviewLink, review_id, populate_existing=True)
        if link is None or link.candidate_result_id is None or link.workspace_id != wid:
            raise HTTPException(409, "candidate review source retracted")
        _, decision, result, work = review_bridge.bound_candidate(
            db,
            wid,
            link.candidate_result_id,
            actor,
            row.original_session_digest,
            runtime.review,
            forward_review_id=review_id,
        )
        if isinstance(policy, InitialRuleAutomaticPolicyV1):
            job, exact = linked_work(db, row, fresh)
            if result.job_id != job.id or work != exact:
                raise HTTPException(409, "initial Start candidate changed")
        epoch = epoch_for(db, principal, decision, policy.semantic_producer_families, fresh, policy)
        review = db.get(ProviderExecutionReview, review_id, populate_existing=True)
        db.refresh(admission, with_for_update=True)
        if (
            review is None
            or review.workspace_id != wid
            or actor != principal.user.id
            or admission.actor_id != actor
            or admission.environment != policy.environment
            or admission.ledger_id != row.ledger_id
            or admission.policy_digest != policy.digest()
            or admission.policy_family != policy.policy_family
            or admission.epoch_digest != epoch.digest()
            or admission.account_identity_digest != account_identity(decision)
            or admission.budget_owner_key != decision.scope.budget_owner_key
            or admission.candidate_digest != decision.digest()
            or admission.evidence_digest != decision.evidence_digest
            or (admission.review_digest, admission.plan_digest)
            != (review.digest, review.plan_digest)
            or decision.action is None
            or decision.action.kind not in policy.allowed_operations
            or decision.scope.mandate != service.binding(row)
        ):
            raise HTTPException(409, "automatic decision binding changed")
        # The caller has already fenced candidate provenance. Resample the original
        # session and expiry after the semantic source/admission locks as well.
        if isinstance(decision, InitialReportedRuleCandidateV1):
            review_bridge.validate_bound_review(
                db, wid, review_id, actor, principal, decision, result, work, runtime.review, clock
            )
        else:
            review_bridge.guard_for(runtime.review)(db, wid, review_id, actor, clock)
        service.current(db, wid, row.id, fresh)
        if utc(admission.expires_at) <= clock():
            raise HTTPException(409, "automatic decision expired")

    return guard


def execution_runtime(
    db: Session, wid: int, identifier: str, runtime: SessionAutomationRuntime
) -> OptimizationRuntime:
    _, principal, _, _ = service.current(db, wid, identifier, runtime)
    return replace(
        review_bridge.bind_execution(runtime.review, principal),
        automatic_authority_guard=guard_for(runtime),
    )


def admit(
    db: Session, wid: int, identifier: str, review_id: str, runtime: SessionAutomationRuntime
) -> ProviderExecutionRun:
    advertising_capabilities.require_advertising_write()
    try:
        session_run, principal, policy, mandate = service.current(db, wid, identifier, runtime)
        execution = execution_runtime(db, wid, identifier, runtime)
        row, document = optimization.checked_review(
            db, wid, review_id, principal.user.id, execution, runtime.clock
        )
        if not row.candidate_provenance_required or (
            db.get(ProviderExecutionApproval, row.id) is not None
        ):
            raise HTTPException(409, "automatic decision cannot reuse human approval")
        link = db.get(CandidateReviewLink, row.id, populate_existing=True)
        if link is None or link.candidate_result_id is None:
            raise HTTPException(409, "candidate review source retracted")
        _, decision, result, work = review_bridge.bound_candidate(
            db,
            wid,
            link.candidate_result_id,
            principal.user.id,
            session_run.original_session_digest,
            runtime.review,
            forward_review_id=review_id,
        )
        if isinstance(policy, InitialRuleAutomaticPolicyV1):
            job, exact = linked_work(db, session_run, runtime)
            if result.job_id != job.id or work != exact:
                raise HTTPException(409, "initial Start candidate changed")
        if decision.scope.mandate != service.binding(session_run) or (
            decision.action is None or decision.action.kind not in policy.allowed_operations
        ):
            raise HTTPException(409, "automatic decision outside mandate budget scope")
        epoch = epoch_for(
            db, principal, decision, policy.semantic_producer_families, runtime, policy
        )
        # Workspace/ledger locks serialize semantic consumption. The DB unique key
        # also defends competing sessions/revisions without minting a replacement.
        existing = db.scalar(
            select(AutomaticDecisionAdmission).where(
                AutomaticDecisionAdmission.workspace_id == wid,
                AutomaticDecisionAdmission.environment == policy.environment,
                AutomaticDecisionAdmission.ledger_id == session_run.ledger_id,
                AutomaticDecisionAdmission.account_identity_digest == account_identity(decision),
                AutomaticDecisionAdmission.budget_owner_key == decision.scope.budget_owner_key,
                AutomaticDecisionAdmission.policy_family == policy.policy_family,
                AutomaticDecisionAdmission.epoch_digest == epoch.digest(),
            )
        )
        if existing is not None:
            if existing.review_id != row.id or existing.session_run_id != identifier:
                raise HTTPException(409, "decision_already_used")
            admission = existing
        else:
            if db.scalar(
                select(ProviderExecutionRun.id).where(ProviderExecutionRun.review_id == row.id)
            ):
                raise HTTPException(409, "optimization authority cannot change")
            service.current(db, wid, identifier, runtime)
            admission = AutomaticDecisionAdmission(
                id=uuid4().hex,
                workspace_id=wid,
                session_run_id=identifier,
                review_id=row.id,
                environment=policy.environment,
                ledger_id=session_run.ledger_id,
                account_identity_digest=account_identity(decision),
                budget_owner_key=decision.scope.budget_owner_key,
                policy_family=policy.policy_family,
                policy_digest=policy.digest(),
                epoch_digest=epoch.digest(),
                producer_family=epoch.producer_family,
                review_digest=row.digest,
                plan_digest=row.plan_digest,
                candidate_digest=decision.digest(),
                evidence_digest=decision.evidence_digest,
                actor_id=principal.user.id,
                admitted_at=runtime.clock(),
                expires_at=min(
                    utc(session_run.expires_at),
                    decision.expires_at,
                    document.plan.exposure.expires_at,
                ),
            )
            db.add(admission)
            row.automatic_authority_required = True
            db.flush()
        if isinstance(decision, InitialReportedRuleCandidateV1):
            from app.initial_planning.automatic_contracts import InitialReportedRuleWorkV1
            from app.initial_planning.automatic_dependencies import consume_origin

            if not isinstance(work, InitialReportedRuleWorkV1):
                raise HTTPException(409, "initial work changed")
            consume_origin(db, principal, work, decision, admission.id, runtime.clock)
        run = optimization.create_run(
            db,
            wid,
            row.id,
            principal.user.id,
            execution,
            runtime.clock,
            authority=SessionMandateDecisionAuthority(admission_id=admission.id),
            commit=False,
        )
        guard_for(runtime)(db, wid, row.id, principal.user.id, runtime.clock)
        optimization.validate_document(document, mandate, runtime.clock())
        db.commit()
        return run
    except Exception:
        db.rollback()
        raise
