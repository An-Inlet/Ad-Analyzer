"""Owned retained initial observations to operational rule facts. No network or commits."""

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.initial_planning.automatic_contracts import InitialReportedRuleCandidateV1
    from app.session_automation.contracts import SemanticDecisionEpoch

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.customers.access import CustomerPrincipal, lock_customer_mutation
from app.customers.identity import IdentityProvider
from app.initial_planning.automatic_contracts import (
    InitialObservationReferenceV1,
    InitialReportedRuleEvidenceV1,
    InitialReportedRuleObservationV1,
    InitialReportedRulePolicyV1,
    InitialReportedRuleWorkV1,
    InitialRuleBasisV1,
)
from app.initial_planning.automatic_keys import opportunity_key
from app.initial_planning.calibration import classify, read_calibration
from app.initial_planning.capture import read_observation
from app.initial_planning.clock import effective_now
from app.initial_planning.review_v2_api_contracts import InitialPreviewExecutionRuntime
from app.initial_planning.review_v2_owned import current_preview, policy_pair
from app.initial_planning.review_v2_projection import native_review_match
from app.optimization_candidates.contracts import CandidateObservation, CandidateScope
from app.optimization_candidates.selection_contracts import SelectionProvenance
from app.publication.coordinator_contracts import CreationExecutionReview
from app.publication.execution_models import (
    ProviderExecutionAttempt,
    ProviderExecutionReview,
    ProviderExecutionRun,
)
from app.publication.optimization_contracts import (
    BudgetOwnerRef,
    GoogleBudgetSetV1,
    MetaBudgetSetV1,
    MetaCurrentState,
    OptimizationRequest,
    TikTokBudgetSetV1,
)
from app.publication.replacement_contracts import parse_review
from app.publication.service import owner
from app.session_automation.models import AutomaticDecisionAdmission

MAX_PRIOR_BUDGET_ATTEMPTS = 512


def unavailable() -> HTTPException:
    return HTTPException(409, "initial_rule_current_evidence_unavailable")


def no_prior_budget(
    db: Session,
    scope: CandidateScope,
    *,
    forward_review_id: str | None = None,
) -> str | None:
    """Fail closed on bounded protected history, independent of policy/session/period."""
    from app.initial_planning.automatic_keys import native_identity

    allowed = None
    if forward_review_id is not None:
        from app.initial_planning.automatic_models import InitialRuleAdmissionOrigin

        allowed = db.scalar(
            select(AutomaticDecisionAdmission)
            .where(
                AutomaticDecisionAdmission.workspace_id == scope.account.workspace_id,
                AutomaticDecisionAdmission.review_id == forward_review_id,
            )
            .execution_options(populate_existing=True)
        )
        origin = db.get(InitialRuleAdmissionOrigin, allowed.id) if allowed else None
        if (
            allowed is None
            or origin is None
            or origin.workspace_id != scope.account.workspace_id
            or origin.opportunity_id != opportunity_key(scope)[:32]
            or allowed.ledger_id != scope.mandate.ledger_id
            or allowed.environment != scope.mandate.environment
            or allowed.account_identity_digest != native_identity(scope)
            or allowed.budget_owner_key != scope.budget_owner_key
        ):
            raise unavailable()
    if db.scalar(
        select(AutomaticDecisionAdmission.id)
        .where(
            AutomaticDecisionAdmission.workspace_id == scope.account.workspace_id,
            AutomaticDecisionAdmission.environment == scope.mandate.environment,
            AutomaticDecisionAdmission.account_identity_digest == native_identity(scope),
            AutomaticDecisionAdmission.budget_owner_key == scope.budget_owner_key,
            AutomaticDecisionAdmission.id != (allowed.id if allowed else ""),
        )
        .limit(1)
    ):
        raise unavailable()
    # Creation history is not budget-decision history and must not exhaust this
    # bounded scan. Unknown/missing discriminators remain included and fail closed
    # in the strict parser below. Financial reservations are checked independently.
    schema = ProviderExecutionReview.document["schema_version"].as_string()
    purpose = ProviderExecutionReview.document["purpose"].as_string()
    rows = db.execute(
        select(ProviderExecutionAttempt, ProviderExecutionReview)
        .join(
            ProviderExecutionRun,
            ProviderExecutionRun.id == ProviderExecutionAttempt.run_id,
        )
        .join(ProviderExecutionReview, ProviderExecutionReview.id == ProviderExecutionRun.review_id)
        .where(
            ProviderExecutionAttempt.workspace_id == scope.account.workspace_id,
            or_(
                schema.is_(None),
                purpose.is_(None),
                schema != "inlet.execution-creation-review.v1",
                purpose != "create_paused",
            ),
        )
        .limit(MAX_PRIOR_BUDGET_ATTEMPTS + 1)
    ).all()
    if len(rows) > MAX_PRIOR_BUDGET_ATTEMPTS:
        raise unavailable()
    for attempt, review in rows:
        # Creation/activation are not prior budget-learning actions. Their unresolved
        # financial obligations remain independently enforced by execution admission.
        if review.document.get("schema_version") == "inlet.execution-creation-review.v1":
            try:
                creation = CreationExecutionReview.model_validate(review.document)
            except ValueError as exc:
                raise unavailable() from exc
            if creation.digest() != review.digest:
                raise unavailable()
            continue
        try:
            document = parse_review(review.document)
        except ValueError as exc:
            raise unavailable() from exc
        if document.digest() != review.digest:
            raise unavailable()
        try:
            request = OptimizationRequest.model_validate(attempt.request)
        except ValueError as exc:
            raise unavailable() from exc
        if (
            request.digest() != attempt.request_digest
            or request.intent != document.plan.intent
            or request.attempt_id != attempt.id
            or request.fence != attempt.fence
        ):
            raise unavailable()
        if allowed is not None and review.id == allowed.review_id:
            if review.digest != allowed.review_digest or review.plan_digest != allowed.plan_digest:
                raise unavailable()
            continue
        account = request.intent.scope
        if (
            request.intent.mandate.environment == scope.mandate.environment
            and account.account.platform == scope.account.account.platform
            and account.external_advertiser_id == scope.account.external_advertiser_id
            and request.intent.budget_owner.key(account) == scope.budget_owner_key
            and isinstance(
                request.intent.action, (MetaBudgetSetV1, GoogleBudgetSetV1, TikTokBudgetSetV1)
            )
        ):
            raise unavailable()
    return allowed.id if allowed else None


def resolve_initial_work(
    db: Session,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    scope: CandidateScope,
    selection: SelectionProvenance,
    preview_id: str,
    expected_digest: str,
    policy: InitialReportedRulePolicyV1,
    planning: InitialPreviewExecutionRuntime,
    *,
    forward_review_id: str | None = None,
) -> InitialReportedRuleWorkV1:
    from app.optimization_candidates.service import source_current

    wid = scope.account.workspace_id
    lock_customer_mutation(db, principal, wid, provider)
    owner(db, wid, principal.user.id)
    source_current(db, scope, principal.user.id)
    value, row, intent = current_preview(db, principal, provider, wid, preview_id, planning)
    if (
        value.digest() != expected_digest
        or value.native_observation is None
        or value.native_observation.request.scope.model_dump() != scope.account.model_dump()
        or value.native_observation.request.target.model_dump() != scope.target.model_dump()
        or BudgetOwnerRef.model_validate(value.native_observation.budget_owner.model_dump()).key(
            scope.account
        )
        != scope.budget_owner_key
        or value.native_observation.budget_owner.target_set_digest() != scope.target_set_digest
        or value.profile_digest != policy.planning_profile_digest
        or value.policy_digest != policy.initial.digest()
        or value.objective.cohort.account_id != scope.account.account.account_id
        or value.objective.goal_id != scope.goal_id
        or value.objective.goal_revision != scope.goal_revision
        or selection.actor_id != principal.user.id
    ):
        raise unavailable()
    policy_pair(
        db,
        wid,
        value,
        row,
        intent,
        scope.mandate,
        principal.user.id,
        planning,
        planning.planning.clock,
    )
    allowed_admission = no_prior_budget(db, scope, forward_review_id=forward_review_id)
    report = read_calibration(db, principal, provider, wid, value.calibration_id, planning.planning)
    if (
        report.status != "evaluated"
        or report.training_windows < policy.initial.minimum_training_windows
        or report.holdout_windows < policy.initial.minimum_holdout_windows
    ):
        raise unavailable()
    references = tuple(
        InitialObservationReferenceV1(
            observation_id=identifier,
            digest=read_observation(
                db, principal, provider, wid, identifier, planning.planning
            ).digest(),
        )
        for identifier in sorted(report.observation_ids)
    )
    from app.initial_planning.automatic_dependencies import ensure_opportunity

    now = effective_now(db, planning.planning)
    ensure_opportunity(
        db,
        scope,
        now,
        min(value.expires_at, report.expires_at, selection.expires_at),
        allowed_admission_id=allowed_admission,
    )
    key = opportunity_key(scope)
    return InitialReportedRuleWorkV1(
        scope=scope,
        policy=policy,
        selection=selection,
        basis=InitialRuleBasisV1(
            preview_id=value.id,
            preview_digest=value.digest(),
            calibration_id=report.id,
            calibration_digest=report.digest(),
            selected_observation_id=value.observation_id,
            objective_digest=value.objective.digest(),
            goal_digest=scope.goal_digest,
            observation_references=references,
            opportunity_id=key[:32],
            semantic_key_digest=key,
        ),
    )


def read_initial_rule(
    db: Session,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    work: InitialReportedRuleWorkV1,
    native: CandidateObservation,
    planning: InitialPreviewExecutionRuntime,
    clock: Callable[[], datetime],
) -> InitialReportedRuleObservationV1:
    work = InitialReportedRuleWorkV1.model_validate_json(work.model_dump_json())
    current = resolve_initial_work(
        db,
        principal,
        provider,
        work.scope,
        work.selection,
        work.basis.preview_id,
        work.basis.preview_digest,
        work.policy,
        planning,
    )
    if (
        current != work
        or native.scope != work.scope
        or not isinstance(native.state, MetaCurrentState)
    ):
        raise unavailable()
    value, _, _ = current_preview(
        db, principal, provider, work.scope.account.workspace_id, work.basis.preview_id, planning
    )
    if value.native_observation is None:
        raise unavailable()
    try:
        native_review_match(value.native_observation, native.state)
    except ValueError as exc:
        raise unavailable() from exc
    item = read_observation(
        db,
        principal,
        provider,
        work.scope.account.workspace_id,
        work.basis.selected_observation_id,
        planning.planning,
    )
    rule = next(r for r in work.policy.initial.rules if r.name == work.policy.initial.selected_rule)
    direction = classify(item, value.objective, rule)
    if direction not in {"increase", "decrease"} or direction != value.direction:
        raise unavailable()
    if value.before_budget_micros is None or value.after_budget_micros is None:
        raise unavailable()
    delta = value.after_budget_micros - value.before_budget_micros
    if abs(delta) > rule.budget_step_micros:
        raise unavailable()
    now = max(clock(), effective_now(db, planning.planning))
    expires = min(
        value.expires_at,
        work.selection.expires_at,
        now + timedelta(seconds=work.policy.maximum_candidate_age_seconds),
    )
    if now >= expires:
        raise unavailable()
    report = read_calibration(
        db,
        principal,
        provider,
        work.scope.account.workspace_id,
        work.basis.calibration_id,
        planning.planning,
    )
    evidence = InitialReportedRuleEvidenceV1(
        scope_digest=work.scope.digest(),
        environment=work.policy.environment,
        source_reference=work.basis.opportunity_id,
        basis=work.basis,
        rule_policy_digest=work.policy.digest(),
        direction=direction,
        signed_delta_micros=delta,
        training_windows=report.training_windows,
        holdout_windows=report.holdout_windows,
        observed_at=now,
        expires_at=expires,
    )
    return InitialReportedRuleObservationV1(scope=work.scope, state=native.state, evidence=evidence)


def assert_initial_rule_current(
    db: Session,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    work: InitialReportedRuleWorkV1,
    decision: "InitialReportedRuleCandidateV1",
    planning: InitialPreviewExecutionRuntime,
    clock: Callable[[], datetime],
    *,
    forward_review_id: str | None = None,
) -> None:
    from app.initial_planning.automatic_contracts import InitialReportedRuleCandidateV1
    from app.initial_planning.automatic_dependencies import require_initial_dependency
    from app.optimization_candidates.models import CandidateJob

    decision = InitialReportedRuleCandidateV1.model_validate_json(decision.model_dump_json())
    current = resolve_initial_work(
        db,
        principal,
        provider,
        work.scope,
        work.selection,
        work.basis.preview_id,
        work.basis.preview_digest,
        work.policy,
        planning,
        forward_review_id=forward_review_id,
    )
    now = max(clock(), effective_now(db, planning.planning))
    if (
        current != work
        or decision.scope != work.scope
        or decision.policy_digest != work.policy.digest()
        or decision.evidence.basis != work.basis
        or decision.expires_at <= now
        or decision.observed_at > now
    ):
        raise unavailable()
    job = db.scalar(
        select(CandidateJob)
        .where(
            CandidateJob.workspace_id == work.scope.account.workspace_id,
            CandidateJob.input_digest == work.digest(),
        )
        .execution_options(populate_existing=True)
    )
    if (
        job is None
        or job.actor_id != principal.user.id
        or job.auth_session_digest != principal.session.digest
    ):
        raise unavailable()
    require_initial_dependency(db, job, work)
    if forward_review_id is not None:
        admission = db.scalar(
            select(AutomaticDecisionAdmission)
            .where(
                AutomaticDecisionAdmission.workspace_id == work.scope.account.workspace_id,
                AutomaticDecisionAdmission.review_id == forward_review_id,
            )
            .execution_options(populate_existing=True)
        )
        if (
            admission is None
            or admission.actor_id != principal.user.id
            or admission.candidate_digest != decision.digest()
            or admission.evidence_digest != decision.evidence_digest
        ):
            raise unavailable()


def initial_rule_epoch(
    db: Session,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    work: InitialReportedRuleWorkV1,
    decision: "InitialReportedRuleCandidateV1",
    planning: InitialPreviewExecutionRuntime,
    clock: Callable[[], datetime],
    *,
    forward_review_id: str | None = None,
) -> "SemanticDecisionEpoch":
    from app.session_automation.contracts import SemanticDecisionEpoch

    assert_initial_rule_current(
        db,
        principal,
        provider,
        work,
        decision,
        planning,
        clock,
        forward_review_id=forward_review_id,
    )
    return SemanticDecisionEpoch(
        producer_family=INITIAL_RULE_PRODUCER_FAMILY,
        source_schema=decision.evidence.source_schema,
        source_reference=work.basis.opportunity_id,
        semantic_digest=work.basis.semantic_key_digest,
    )


# A code-versioned semantic producer identity, never policy-family/calibration/session-derived.
from app.publication.contracts import fingerprint as _fingerprint  # noqa: E402

INITIAL_RULE_PRODUCER_FAMILY = _fingerprint("inlet.initial-rule-producer.v1", {})[:32]
