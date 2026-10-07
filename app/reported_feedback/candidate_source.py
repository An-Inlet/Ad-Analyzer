"""Actual owned report dependencies to a distinct operational rule. Local DB only."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.commerce.evidence import digest
from app.customers.access import CustomerPrincipal, lock_customer_mutation
from app.customers.identity import IdentityProvider
from app.directional_feedback.contracts import DecisionOpportunityV1
from app.optimization_candidates.contracts import CandidateObservation
from app.optimization_candidates.service import source_current
from app.publication.execution_models import ProviderExecutionReceipt
from app.publication.optimization_contracts import MetaCurrentState, OptimizationReceipt
from app.publication.service import owner
from app.reported_feedback.candidate_contracts import (
    ReportedRuleCandidateV1,
    ReportedRuleEvidenceV1,
    ReportedRuleObservationV1,
    ReportedRuleWorkV1,
)
from app.reported_feedback.evaluator import bounded_delta
from app.reported_feedback.models import ReportedActionComparison, ReportedFeedbackJob
from app.reported_feedback.service import validate_comparison_dependencies


def unavailable() -> HTTPException:
    return HTTPException(409, "reported_rule_current_evidence_unavailable")


def read_reported_rule(
    db: Session,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    work: ReportedRuleWorkV1,
    native: CandidateObservation,
    clock: Callable[[], datetime],
) -> ReportedRuleObservationV1:
    """No acquisition/materialization, commits or network calls in this boundary."""
    work = ReportedRuleWorkV1.model_validate_json(work.model_dump_json())
    native = CandidateObservation.model_validate_json(native.model_dump_json())
    scope, policy = work.scope, work.policy
    wid = scope.account.workspace_id
    lock_customer_mutation(db, principal, wid, provider)
    owner(db, wid, principal.user.id)
    source_current(db, scope, principal.user.id)
    row = db.get(ReportedActionComparison, work.comparison_id, populate_existing=True)
    job = db.get(ReportedFeedbackJob, row.job_id, populate_existing=True) if row else None
    if (
        row is None
        or job is None
        or row.workspace_id != wid
        or row.account_id != scope.account.account.account_id
        or row.environment != policy.environment
        or job.original_actor_id != principal.user.id
        or job.original_session_digest != principal.session.digest
        or native.scope != scope
        or not isinstance(native.state, MetaCurrentState)
        or native.state.target != scope.target
        or scope.target.kind != "campaign"
        or native.state.digest() != work.selection.state_digest
    ):
        raise unavailable()
    now = clock()
    comparison = validate_comparison_dependencies(db, row, now)
    anchor = comparison.anchor
    raw = db.get(ProviderExecutionReceipt, anchor.latest_receipt_id, populate_existing=True)
    if raw is None or raw.workspace_id != wid:
        raise unavailable()
    receipt = OptimizationReceipt.model_validate(raw.receipt)
    original = receipt.after
    excluded = {
        "observed_at",
        "observation_started_at",
        "qualification_id",
        "qualification_revision",
    }
    state = native.state
    if (
        comparison.status != "operational_reported_as_of"
        or comparison.policy_digest != policy.comparison_policy_digest
        or comparison.policy_digest != policy.feedback_policy.comparison_policy_digest
    ):
        raise unavailable()
    if (
        anchor.environment != policy.environment
        or anchor.ledger_id != scope.mandate.ledger_id
        or anchor.goal_id != scope.goal_id
        or anchor.goal_revision != scope.goal_revision
        or anchor.external_account_id != scope.account.external_advertiser_id
        or anchor.external_campaign_id != scope.target.external_id
        or anchor.integration_id != scope.account.account.connection_id
        or anchor.cohort.currency != state.money.currency
        or anchor.cohort.time_zone != state.money.account_timezone
        or not isinstance(original, MetaCurrentState)
        or original.model_dump(mode="json", exclude=excluded)
        != state.model_dump(mode="json", exclude=excluded)
        or ("increase" if anchor.after_budget_micros > anchor.before_budget_micros else "decrease")
        != policy.feedback_policy.original_change
    ):
        raise unavailable()
    delta = bounded_delta((comparison,), policy.feedback_policy)
    opportunity = DecisionOpportunityV1(
        workspace_id=wid,
        environment=policy.environment,
        ledger_id=anchor.ledger_id,
        original_attempt_id=anchor.original_attempt_id,
        original_request_digest=anchor.original_request_digest,
        native_account_digest=digest(
            [
                "inlet.native-feedback-account.v1",
                scope.account.account.platform,
                scope.account.external_advertiser_id,
            ]
        ),
        budget_owner_key=scope.budget_owner_key,
    )
    expires = min(
        comparison.expires_at,
        native.evidence.expires_at,
        work.selection.expires_at,
        now
        + timedelta(
            seconds=min(
                policy.maximum_candidate_age_seconds, policy.feedback_policy.lifetime_seconds
            )
        ),
        datetime.fromtimestamp(principal.session.expires_at, UTC),
    )
    lock_customer_mutation(db, principal, wid, provider)
    now = clock()
    if expires <= now:
        raise unavailable()
    return ReportedRuleObservationV1(
        scope=scope,
        state=state,
        evidence=ReportedRuleEvidenceV1(
            scope_digest=scope.digest(),
            environment=policy.environment,
            source_reference=anchor.original_attempt_id,
            comparison_id=comparison.id,
            comparison_digest=comparison.digest(),
            acquisition_request_id=comparison.job_id,
            comparison_policy_digest=comparison.policy_digest,
            rule_policy_digest=policy.digest(),
            opportunity=opportunity,
            direction="increase" if delta > 0 else "decrease" if delta < 0 else "none",
            signed_delta_micros=delta,
            before=comparison.before,
            after=comparison.after,
            reported_completion_count=len(comparison.before.capsules)
            + len(comparison.after.capsules),
            observed_at=now,
            expires_at=expires,
        ),
    )


def assert_reported_rule_current(
    db: Session,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    work: ReportedRuleWorkV1,
    decision: ReportedRuleCandidateV1,
    clock: Callable[[], datetime],
) -> None:
    """Final original evidence check; never refresh a result's persisted lifetime."""
    wid = work.scope.account.workspace_id
    lock_customer_mutation(db, principal, wid, provider)
    owner(db, wid, principal.user.id)
    source_current(db, work.scope, principal.user.id)
    row = db.get(ReportedActionComparison, work.comparison_id, populate_existing=True)
    job = db.get(ReportedFeedbackJob, row.job_id, populate_existing=True) if row else None
    if row is None or job is None or row.workspace_id != wid:
        raise unavailable()
    now = clock()
    value = validate_comparison_dependencies(db, row, now)
    if (
        job.original_actor_id != principal.user.id
        or job.original_session_digest != principal.session.digest
        or value.id != decision.evidence.comparison_id
        or value.digest() != decision.evidence.comparison_digest
        or value.job_id != decision.evidence.acquisition_request_id
        or value.policy_digest != work.policy.comparison_policy_digest
        or work.policy.digest() != decision.policy_digest
        or decision.scope != work.scope
        or value.anchor.original_attempt_id != decision.evidence.opportunity.original_attempt_id
        or value.anchor.original_request_digest
        != decision.evidence.opportunity.original_request_digest
        or value.anchor.ledger_id != decision.evidence.opportunity.ledger_id
        or bounded_delta((value,), work.policy.feedback_policy)
        != decision.evidence.signed_delta_micros
        or not decision.observed_at <= now < min(decision.expires_at, value.expires_at)
    ):
        raise unavailable()
    lock_customer_mutation(db, principal, wid, provider)
    if not decision.observed_at <= clock() < min(decision.expires_at, value.expires_at):
        raise unavailable()
