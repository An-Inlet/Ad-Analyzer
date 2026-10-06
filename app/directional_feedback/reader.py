"""Owned local consumer; caller owns transaction, no IO or implicit commit.

Facts producers in this interface must read already-persisted qualified facts only.
Independent provider acquisition belongs outside these locked transactions.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.commerce.evidence import digest
from app.customers.access import CustomerPrincipal
from app.directional_feedback.contracts import (
    DecisionOpportunityV1,
    DirectionalAssociationPolicyV1,
    DirectionalInputsV1,
    DirectionalQualificationV1,
    QualifiedDirectionalFactsV1,
)
from app.optimization_candidates import service as candidates
from app.optimization_candidates.contracts import CandidateWork
from app.optimization_candidates.selection_contracts import CandidateWorkV2
from app.outcome_feedback import service as feedback
from app.outcome_feedback.models import ContributionSlot, FeedbackRecord
from app.outcome_feedback.snapshot import FeedbackSnapshotV1, read_feedback_snapshot
from app.outcomes.feedback import decision_policy_for
from app.outcomes.maturity import PolicyLookup, policy_for
from app.publication import execution_mandates as mandates
from app.publication.coordinator import read_owned_outcome_receipt
from app.publication.execution_contracts import ExposureEvidence
from app.publication.execution_models import (
    ProviderExecutionAttempt,
    ProviderExecutionReview,
    ProviderExecutionRun,
    ProviderExposureReservation,
)
from app.publication.optimization_contracts import (
    GoogleBudgetSetV1,
    GoogleCurrentState,
    MetaBudgetSetV1,
    MetaCurrentState,
    TikTokBudgetSetV1,
)
from app.publication.replacement_contracts import parse_review
from app.publication.replacement_lineage import ancestors

Work = CandidateWork | CandidateWorkV2
Change = Literal["increase", "decrease", "unchanged", "unsupported"]


def directional_policy_for(family: str) -> DirectionalAssociationPolicyV1 | None:
    return None


def directional_qualification_for(
    policy: DirectionalAssociationPolicyV1,
) -> DirectionalQualificationV1 | None:
    return None


class LocalQualifiedFactsProducer(Protocol):
    def __call__(
        self, db: Session, snapshot: FeedbackSnapshotV1, completions: tuple[str, ...], /
    ) -> QualifiedDirectionalFactsV1 | None: ...


@dataclass(frozen=True)
class DirectionalReadRuntime:
    candidate: candidates.CandidateRuntime
    policies: Callable[[str], DirectionalAssociationPolicyV1 | None] = directional_policy_for
    qualifications: Callable[
        [DirectionalAssociationPolicyV1], DirectionalQualificationV1 | None
    ] = directional_qualification_for
    facts: LocalQualifiedFactsProducer | None = None
    feedback_policies: feedback.DecisionLookup = decision_policy_for
    maturity_policies: PolicyLookup = policy_for


def get_directional_runtime() -> DirectionalReadRuntime | None:
    return None


def resolve_original_opportunity(
    db: Session, principal: CustomerPrincipal, work: Work, runtime: candidates.CandidateRuntime
) -> DecisionOpportunityV1:
    candidates.current(db, work, principal, runtime)
    wid, scope = work.scope.account.workspace_id, work.scope
    ledger, policy = mandates.checked(db, wid, scope.mandate, principal.user.id, runtime.clock)
    held = list(
        db.scalars(
            select(ProviderExposureReservation)
            .where(
                ProviderExposureReservation.workspace_id == wid,
                ProviderExposureReservation.environment == policy.environment,
                ProviderExposureReservation.budget_owner_key == scope.budget_owner_key,
                ProviderExposureReservation.state == "held",
            )
            .with_for_update()
            .limit(2)
        )
    )
    if len(held) != 1 or held[0].ledger_id != ledger.id:
        raise HTTPException(409, "current retained original action required")
    current = held[0]
    chain = ancestors(db, current)
    if not chain or chain[-1][0].id != current.id:
        raise HTTPException(409, "current original lineage unavailable")
    exposure = ExposureEvidence.model_validate(current.evidence)
    if exposure.account != scope.account or exposure.target_set_digest != scope.target_set_digest:
        raise HTTPException(409, "original owner scope changed")
    runs = list(
        db.scalars(
            select(ProviderExecutionRun)
            .where(
                ProviderExecutionRun.workspace_id == wid,
                ProviderExecutionRun.reservation_id == current.id,
            )
            .limit(2)
        )
    )
    if len(runs) != 1:
        raise HTTPException(409, "unique current original run required")
    attempts = list(
        db.scalars(
            select(ProviderExecutionAttempt)
            .where(
                ProviderExecutionAttempt.workspace_id == wid,
                ProviderExecutionAttempt.run_id == runs[0].id,
            )
            .limit(2)
        )
    )
    if len(attempts) != 1:
        raise HTTPException(409, "unique current original attempt required")
    attempt = attempts[0]
    receipt = read_owned_outcome_receipt(db, wid, attempt.id, principal.user.id)
    row = db.get(ProviderExecutionReview, runs[0].review_id, populate_existing=True)
    if (
        row is None
        or row.workspace_id != wid
        or receipt is None
        or receipt.outcome not in {"verified_effect", "verified_target_state"}
    ):
        raise HTTPException(409, "verified current original action required")
    document = parse_review(row.document)
    if (
        document.digest() != row.digest
        or document.plan.digest() != row.plan_digest
        or receipt.review_digest != row.digest
        or receipt.plan_digest != row.plan_digest
        or receipt.request_digest != attempt.request_digest
        or receipt.purpose != "existing_campaign_optimize"
        or document.plan.intent.scope != scope.account
        or document.plan.intent.target != scope.target
        or receipt.budget_owner_key != scope.budget_owner_key
        or receipt.target_set_digest != scope.target_set_digest
        or receipt.goal_id != scope.goal_id
        or receipt.goal_revision != scope.goal_revision
        or scope.source.attempt_id != attempt.id
    ):
        raise HTTPException(409, "current original opportunity changed")
    candidates.authorize(db, principal, wid, runtime)
    return DecisionOpportunityV1(
        workspace_id=wid,
        environment=policy.environment,
        ledger_id=ledger.id,
        original_attempt_id=attempt.id,
        original_request_digest=attempt.request_digest,
        native_account_digest=digest(
            [
                "inlet.native-feedback-account.v1",
                scope.account.account.platform,
                scope.account.external_advertiser_id,
            ]
        ),
        budget_owner_key=scope.budget_owner_key,
    )


def budget_change(db: Session, wid: int, run_id: str) -> Change:
    run = db.get(ProviderExecutionRun, run_id, populate_existing=True)
    row = db.get(ProviderExecutionReview, run.review_id, populate_existing=True) if run else None
    if run is None or row is None or run.workspace_id != wid or row.workspace_id != wid:
        raise HTTPException(409, "owned intervention plan unavailable")
    review = parse_review(row.document)
    if review.digest() != row.digest or review.plan.digest() != row.plan_digest:
        raise HTTPException(409, "intervention plan changed")
    state, action = review.plan.before, review.plan.intent.action
    if not isinstance(action, (GoogleBudgetSetV1, MetaBudgetSetV1, TikTokBudgetSetV1)):
        return "unsupported"
    if isinstance(state, GoogleCurrentState):
        before = state.budget_amount_micros
    elif isinstance(state, MetaCurrentState):
        if bool(state.daily_budget_micros) == bool(state.lifetime_budget_micros):
            return "unsupported"
        before = state.daily_budget_micros or state.lifetime_budget_micros or 0
    else:
        before = state.budget_micros or 0
    return (
        "increase"
        if action.amount_micros > before
        else "decrease"
        if action.amount_micros < before
        else "unchanged"
    )


def read_directional_inputs(
    db: Session,
    principal: CustomerPrincipal,
    work: Work,
    anchor_assessment_id: str,
    policy: DirectionalAssociationPolicyV1,
    runtime: DirectionalReadRuntime,
) -> DirectionalInputsV1:
    candidate = runtime.candidate
    if (
        runtime.policies(policy.family) != policy
        or policy.candidate_policy_digest != work.policy.digest()
    ):
        raise HTTPException(409, "registered directional policy required")
    wid, actor = work.scope.account.workspace_id, principal.user.id
    opportunity = resolve_original_opportunity(db, principal, work, candidate)

    def authorize(session: Session) -> None:
        candidates.authorize(session, principal, wid, candidate)

    _, anchor = feedback.read_current(
        db, wid, actor, anchor_assessment_id, authorize, candidate.clock, runtime.maturity_policies
    )
    if anchor.receipt.attempt_id != opportunity.original_attempt_id:
        raise HTTPException(409, "latest original action assessment required")
    snapshot = read_feedback_snapshot(
        db,
        wid,
        actor,
        anchor_assessment_id,
        policy.feedback_family,
        authorize,
        candidate.clock,
        decisions=runtime.feedback_policies,
        policies=runtime.maturity_policies,
    )
    if (
        snapshot.scope.account != work.scope.account
        or snapshot.scope.target_set_digest != work.scope.target_set_digest
        or snapshot.scope.target_digest != digest(work.scope.target.model_dump(mode="json"))
    ):
        raise HTTPException(409, "directional candidate target changed")
    changes: list[Change] = []
    completions: set[str] = set()
    for ref in snapshot.contributions:
        slot = db.get(ContributionSlot, ref.slot_id, populate_existing=True)
        row = db.get(FeedbackRecord, slot.feedback_id, populate_existing=True) if slot else None
        if (
            slot is None
            or row is None
            or slot.workspace_id != wid
            or slot.revision != ref.revision
            or row.workspace_id != wid
            or row.document_digest != ref.feedback_digest
        ):
            raise HTTPException(409, "contribution unavailable")
        _, value = feedback.read_current(
            db, wid, actor, row.assessment_id, authorize, candidate.clock, runtime.maturity_policies
        )
        changes.append(budget_change(db, wid, value.receipt.run_id))
        for maturity in (value.before_maturity, value.after_maturity):
            if maturity is not None:
                completions.update(maturity.supporting_completions)
    facts = runtime.facts(db, snapshot, tuple(sorted(completions))) if runtime.facts else None
    if facts is not None and set(facts.completion_digests) != completions:
        raise HTTPException(409, "qualified completion commitments changed")
    if resolve_original_opportunity(db, principal, work, candidate) != opportunity:
        raise HTTPException(409, "original opportunity changed during read")
    current_snapshot = read_feedback_snapshot(
        db,
        wid,
        actor,
        anchor_assessment_id,
        policy.feedback_family,
        authorize,
        candidate.clock,
        decisions=runtime.feedback_policies,
        policies=runtime.maturity_policies,
    )
    if current_snapshot != snapshot or runtime.policies(policy.family) != policy:
        raise HTTPException(409, "directional evidence changed during read")
    return DirectionalInputsV1(
        snapshot=snapshot, opportunity=opportunity, original_changes=tuple(changes), facts=facts
    )
