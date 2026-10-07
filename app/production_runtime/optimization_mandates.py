"""Meaningful customer consent compiled from admitted options and pinned server policy."""

from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.goals import service as goals
from app.goals.schemas import GoalDefinition
from app.production_runtime import optimization_origin
from app.production_runtime.optimization_assembly import ConfiguredOptimization, period
from app.production_runtime.optimization_catalog_contracts import OwnedOptimizationAdmission
from app.production_runtime.optimization_origin_contracts import OptimizationMandatePreparationV1
from app.production_runtime.optimization_policy_contracts import (
    ConsentOptimizationMandateV1,
    OptimizationCustomerIntentV1,
    PreparedOptimizationMandateV1,
    PrepareOptimizationMandateV1,
)
from app.publication import customer_optimization as catalog
from app.publication import execution_mandates as mandates
from app.publication.customer_optimization_contracts import (
    CustomerOptimizationRuntime,
    TargetChoice,
    TargetOption,
)
from app.publication.execution_contracts import ProviderMandatePolicy
from app.publication.execution_models import ProviderExecutionMandate, ProviderExecutionRevision


def require(runtime: CustomerOptimizationRuntime) -> ConfiguredOptimization:
    if runtime.configured is None:
        raise HTTPException(409, "optimization_customer_policy_unavailable")
    return runtime.configured


@dataclass(frozen=True)
class Resolution:
    policy: ProviderMandatePolicy
    option: TargetOption
    admission: OwnedOptimizationAdmission
    goal_digest: str


def resolve(
    db: Session,
    wid: int,
    intent: OptimizationCustomerIntentV1,
    actor: str,
    runtime: CustomerOptimizationRuntime,
) -> Resolution:
    configured = require(runtime)
    option = catalog.choose(
        db, wid, TargetChoice.model_validate(intent.selection.model_dump()), actor, runtime
    )
    result = configured.last_catalog
    if result is None:
        raise optimization_origin.unavailable()
    admitted = next((a for a in result.admitted if a.option_id == intent.selection.option_id), None)
    if admitted is None or admitted.state_digest != option.state.digest():
        raise optimization_origin.unavailable()
    goal = goals.owned(db, wid, intent.selection.goal_id)
    definition = GoalDefinition.model_validate(goals.current(db, goal).definition)
    state = option.state
    operating = configured.operating
    if (
        intent.total_cap_micros > definition.budget_micros
        or intent.aggressiveness != definition.aggressiveness
        or state.money.currency != operating.currency
        or state.money.currency_exponent != operating.currency_exponent
        or state.money.account_timezone != definition.target_window.time_zone
        or state.money.currency != definition.target_window.currency
    ):
        raise HTTPException(409, "optimization_customer_goal_limits_changed")
    rule = operating.rule(intent.aggressiveness)
    cap = min(intent.total_cap_micros, rule.per_plan_cap_micros)
    starts, ends = period(definition)
    policy = ProviderMandatePolicy(
        workspace_id=wid,
        environment=operating.environment,
        goal_id=goal.id,
        goal_revision=goal.revision,
        currency=state.money.currency,
        time_zone=state.money.account_timezone,
        starts_at=starts,
        ends_at=ends,
        accounts=[state.scope],
        total_cap_micros=intent.total_cap_micros,
        per_plan_cap_micros=cap,
        positive_change_cap_micros=min(cap, rule.positive_change_cap_micros),
        action_limit=rule.action_limit,
        cooldown_seconds=rule.cooldown_seconds,
        freshness_seconds=rule.freshness_seconds,
        aggressiveness_percent=rule.aggressiveness_percent,
        allowed_purposes=["existing_campaign_optimize"],
        allowed_target_set_digest=state.budget_owner.target_set_digest(),
        campaign_and_creative_policy="new_exact_review_required",
        activation_policy="separate_exact_approval",
    )
    return Resolution(policy, option, admitted, result.catalog.request.goal_digest)


def document_for(
    mid: str,
    revision: int,
    intent: OptimizationCustomerIntentV1,
    resolved: Resolution,
    configured: ConfiguredOptimization,
) -> OptimizationMandatePreparationV1:
    policy, admitted = resolved.policy, resolved.admission
    return OptimizationMandatePreparationV1(
        workspace_id=policy.workspace_id,
        mandate_id=mid,
        mandate_revision=revision,
        environment=policy.environment,
        provider_policy_digest=policy.digest(),
        goal_digest=resolved.goal_digest,
        intent=intent,
        account_scope_digest=policy.accounts[0].digest(),
        target_set_digest=resolved.option.state.budget_owner.target_set_digest(),
        inventory_request_digest=admitted.candidate.request_digest,
        inventory_digest=admitted.candidate.inventory_digest,
        native_state_digest=admitted.state_digest,
        qualification_id=admitted.qualification.qualification_id,
        qualification_revision=admitted.qualification.qualification_revision,
        qualification_digest=admitted.qualification.evidence_digest,
        evidence_profile_digest=configured.manifest.evidence_profile_digest,
        operating_policy=configured.operating,
        operating_policy_digest=configured.operating.digest(),
    )


def projection(
    row: ProviderExecutionMandate, resolved: Resolution, document: OptimizationMandatePreparationV1
) -> PreparedOptimizationMandateV1:
    policy = resolved.policy
    return PreparedOptimizationMandateV1.model_validate(
        dict(
            mandate_id=row.id,
            revision=row.revision,
            policy_digest=policy.digest(),
            preparation_digest=document.digest(),
            state=row.state,
            selection=document.intent.selection,
            environment=policy.environment,
            currency=policy.currency,
            time_zone=policy.time_zone,
            starts_at=policy.starts_at,
            ends_at=policy.ends_at,
            total_cap_micros=policy.total_cap_micros,
            per_plan_cap_micros=policy.per_plan_cap_micros,
            positive_change_cap_micros=policy.positive_change_cap_micros,
            aggressiveness=document.intent.aggressiveness,
            target_label=resolved.option.label,
            affected_target_count=len(resolved.option.state.budget_owner.affected_targets),
        )
    )


def final(
    db: Session,
    wid: int,
    row: ProviderExecutionMandate,
    resolved: Resolution,
    actor: str,
    runtime: CustomerOptimizationRuntime,
) -> None:
    configured = require(runtime)
    runtime.execution.authorize(db, wid, actor)
    revision = db.get(ProviderExecutionRevision, (row.id, row.revision), populate_existing=True)
    if revision is None:
        raise optimization_origin.unavailable()
    configured.origin_guard(db, revision, resolved.policy)
    mandates.validate_policy(db, resolved.policy, actor, runtime.clock)
    now = runtime.clock()
    if not (
        resolved.admission.qualification.observed_at
        <= now
        < resolved.admission.qualification.expires_at
        and resolved.admission.candidate.observed_at
        <= now
        < resolved.admission.candidate.expires_at
    ):
        raise HTTPException(409, "optimization_customer_admission_expired")


def prepare(
    db: Session,
    wid: int,
    body: PrepareOptimizationMandateV1,
    actor: str,
    runtime: CustomerOptimizationRuntime,
) -> PreparedOptimizationMandateV1:
    configured = require(runtime)
    try:
        resolved = resolve(db, wid, body.intent, actor, runtime)
        if body.mandate_id:
            _, old = mandates.owned(db, wid, body.mandate_id)
            old_policy = mandates.policy(db, old)
            if resolved.policy.total_cap_micros > old_policy.total_cap_micros:
                raise HTTPException(409, "optimization_overall_cap_increase_requires_new_review")
        row = mandates.revise(
            db,
            wid,
            resolved.policy,
            actor,
            runtime.clock,
            mandate_id=body.mandate_id,
            expected_revision=body.expected_revision,
            commit=False,
            origin_factory=lambda mid, rev: document_for(
                mid, rev, body.intent, resolved, configured
            ),
        )
        final(db, wid, row, resolved, actor, runtime)
        document = document_for(row.id, row.revision, body.intent, resolved, configured)
        result = projection(row, resolved, document)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


def consent(
    db: Session,
    wid: int,
    mandate_id: str,
    body: ConsentOptimizationMandateV1,
    actor: str,
    runtime: CustomerOptimizationRuntime,
) -> PreparedOptimizationMandateV1:
    configured = require(runtime)
    try:
        runtime.execution.authorize(db, wid, actor)
        _, row = mandates.owned(db, wid, mandate_id)
        revision = db.get(ProviderExecutionRevision, (row.id, row.revision), populate_existing=True)
        if revision is None or row.revision != body.expected_revision:
            raise optimization_origin.unavailable()
        stored = optimization_origin.read(db, revision, mandates.policy(db, row))
        if (
            stored is None
            or stored.digest() != body.preparation_digest
            or stored.provider_policy_digest != body.policy_digest
            or stored.intent.selection != body.selection
        ):
            raise optimization_origin.unavailable()
        resolved = resolve(db, wid, stored.intent, actor, runtime)
        # New read timestamps aren't authority revisions; all exact semantic source
        # commitments remain required, including the source's own evidence digest.
        current = document_for(
            mandate_id, body.expected_revision, stored.intent, resolved, configured
        )
        if current.model_dump(exclude={"inventory_digest"}) != stored.model_dump(
            exclude={"inventory_digest"}
        ):
            raise HTTPException(409, "optimization_customer_preparation_changed")
        _, row = mandates.owned(db, wid, mandate_id)
        final(db, wid, row, resolved, actor, runtime)
        mandates.consent(
            db,
            wid,
            mandate_id,
            body.expected_revision,
            body.policy_digest,
            actor,
            runtime.clock,
            origin_guard=configured.origin_guard,
            commit=False,
        )
        final(db, wid, row, resolved, actor, runtime)
        result = projection(row, resolved, stored)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
