"""Owned catalog resolution, exact intent compilation and safe customer projections."""

from dataclasses import replace
from typing import Any, Literal

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.customers.access import CustomerPrincipal
from app.customers.identity import IdentityProvider
from app.executors.optimization_http import OptimizationUnavailable
from app.goals import service as goals
from app.publication import customer_intents as intents
from app.publication import execution_mandates as mandates
from app.publication import optimization, replacement
from app.publication.contracts import fingerprint
from app.publication.customer_authority import bind_authority
from app.publication.customer_optimization_contracts import (
    BudgetIntent,
    CustomerOptimizationRuntime,
    InitialOptimizationIntent,
    OptimizationPolicyIntent,
    RepeatOptimizationIntent,
    TargetCatalog,
    TargetChoice,
    TargetOption,
    TargetQuery,
    TargetRequest,
)
from app.publication.execution_contracts import ProviderMandatePolicy
from app.publication.execution_models import ProviderExecutionReview, ProviderExecutionRevision
from app.publication.optimization_contracts import (
    GoogleBudgetSetV1,
    GoogleCurrentState,
    GoogleStatusSetV1,
    MetaBudgetSetV1,
    MetaCurrentState,
    MetaStatusSetV1,
    OptimizationAction,
    TikTokBudgetSetV1,
    TikTokStatusSetV1,
)
from app.publication.replacement_contracts import RepeatOptimizationReview, parse_review


def bind(
    runtime: CustomerOptimizationRuntime | None,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
) -> CustomerOptimizationRuntime:
    if runtime is None or (
        runtime.execution.environment == "live" and not runtime.execution.live_enabled
    ):
        raise intents.unavailable("optimization_runtime_unavailable")
    return replace(
        runtime, execution=replace(runtime.execution, authorize=bind_authority(principal, provider))
    )


def request(
    db: Session, wid: int, query: TargetQuery, actor: str, runtime: CustomerOptimizationRuntime
) -> TargetRequest:
    runtime.execution.authorize(db, wid, actor)
    goal = goals.owned(db, wid, query.goal_id)
    goals.expect(goal, query.goal_revision)
    if goals.assessment(db, goal, runtime.clock()) != "confirmed":
        raise intents.unavailable("current_confirmed_goal_required")
    return TargetRequest(
        goal_id=goal.id,
        goal_revision=goal.revision,
        goal_digest=fingerprint(
            "inlet.optimization-goal.v1", {"definition": goals.current(db, goal).definition}
        ),
        scope=intents.account(db, wid, query.account_id),
    )


def discover(
    db: Session, wid: int, query: TargetQuery, actor: str, runtime: CustomerOptimizationRuntime
) -> TargetCatalog:
    if runtime.catalog is None:
        raise intents.unavailable("owned_target_catalog_unavailable")
    before = request(db, wid, query, actor, runtime)
    db.commit()
    try:
        result = TargetCatalog.model_validate(runtime.catalog(before, runtime.clock()).model_dump())
    except (ValueError, TypeError, OptimizationUnavailable):
        raise intents.unavailable("owned_target_catalog_unavailable") from None
    current = request(db, wid, query, actor, runtime)
    if (
        current != before
        or result.request != current
        or not result.observed_at <= runtime.clock() < result.expires_at
    ):
        raise intents.unavailable("owned_target_catalog_changed")
    return result


def choose(
    db: Session, wid: int, choice: TargetChoice, actor: str, runtime: CustomerOptimizationRuntime
) -> TargetOption:
    catalog = discover(
        db,
        wid,
        TargetQuery.model_validate(choice.model_dump(exclude={"option_id"})),
        actor,
        runtime,
    )
    for option in catalog.options:
        if option.identifier(catalog.request) == choice.option_id:
            return option
    raise intents.unavailable("owned_target_choice_changed")


def option_view(option: TargetOption) -> dict[str, Any]:
    s = option.state
    amount = (
        s.budget_amount_micros
        if isinstance(s, GoogleCurrentState)
        else (s.daily_budget_micros if bool(s.daily_budget_micros) else s.lifetime_budget_micros)
        if isinstance(s, MetaCurrentState)
        else s.budget_micros
    )
    kind = (
        "daily"
        if isinstance(s, GoogleCurrentState)
        or (isinstance(s, MetaCurrentState) and bool(s.daily_budget_micros))
        or (
            not isinstance(s, (GoogleCurrentState, MetaCurrentState))
            and s.budget_mode == "BUDGET_MODE_DAY"
        )
        else "lifetime"
    )
    return {
        "label": option.label,
        "parent_label": option.parent_label,
        "target_level": s.target.kind,
        "platform": s.scope.account.platform,
        "budget_owner_mode": s.budget_owner.mode,
        "affected_target_count": len(s.budget_owner.affected_targets),
        "currency": s.money.currency,
        "time_zone": s.money.account_timezone,
        "budget_kind": kind,
        "amount_micros": amount,
        "configured_status": s.configured_status,
        "observed_at": s.observed_at.isoformat(),
    }


def make_policy(
    db: Session,
    wid: int,
    body: OptimizationPolicyIntent,
    actor: str,
    runtime: CustomerOptimizationRuntime,
) -> ProviderMandatePolicy:
    option = choose(db, wid, body.choice, actor, runtime)
    state = option.state
    return ProviderMandatePolicy(
        **body.limits.model_dump(),
        workspace_id=wid,
        goal_id=body.choice.goal_id,
        goal_revision=body.choice.goal_revision,
        environment=runtime.execution.environment,
        accounts=[state.scope],
        currency=state.money.currency,
        time_zone=state.money.account_timezone,
        allowed_purposes=["existing_campaign_optimize"],
        allowed_target_set_digest=state.budget_owner.target_set_digest(),
        freshness_seconds=60,
        campaign_and_creative_policy="new_exact_review_required",
        activation_policy="separate_exact_approval",
    )


def current_policy_catalog(
    db: Session, wid: int, identifier: str, actor: str, runtime: CustomerOptimizationRuntime
) -> None:
    runtime.execution.authorize(db, wid, actor)
    _, row = mandates.owned(db, wid, identifier)
    policy = mandates.policy(db, row)
    if policy.allowed_purposes != ["existing_campaign_optimize"] or len(policy.accounts) != 1:
        raise intents.unavailable("optimization_policy_required")
    catalog = discover(
        db,
        wid,
        TargetQuery(
            goal_id=policy.goal_id,
            goal_revision=policy.goal_revision,
            account_id=policy.accounts[0].account.account_id,
        ),
        actor,
        runtime,
    )
    _, current = mandates.owned(db, wid, identifier)
    if (
        mandates.policy(db, current) != policy
        or catalog.request.scope != policy.accounts[0]
        or not any(
            option.state.budget_owner.target_set_digest() == policy.allowed_target_set_digest
            and option.state.money.currency == policy.currency
            and option.state.money.account_timezone == policy.time_zone
            for option in catalog.options
        )
    ):
        raise intents.unavailable("optimization_policy_target_changed")


def _prepare(
    db: Session,
    wid: int,
    body: InitialOptimizationIntent,
    actor: str,
    runtime: CustomerOptimizationRuntime,
) -> ProviderExecutionReview:
    option = choose(db, wid, body.choice, actor, runtime)
    binding = intents.binding(db, wid, body.mandate_id, body.mandate_revision)
    _, policy = mandates.checked(db, wid, binding, actor, runtime.clock)
    state = option.state
    if (
        policy.goal_id,
        policy.goal_revision,
        policy.allowed_target_set_digest,
        policy.currency,
        policy.time_zone,
    ) != (
        body.choice.goal_id,
        body.choice.goal_revision,
        state.budget_owner.target_set_digest(),
        state.money.currency,
        state.money.account_timezone,
    ):
        raise intents.unavailable("optimization_policy_target_changed")
    action: OptimizationAction
    if isinstance(body.action, BudgetIntent):
        amount = body.action.amount_micros
        if isinstance(state, GoogleCurrentState):
            action = GoogleBudgetSetV1(amount_micros=amount)
        elif isinstance(state, MetaCurrentState):
            if bool(state.daily_budget_micros) == bool(state.lifetime_budget_micros):
                raise intents.unavailable("ambiguous_native_budget")
            action = MetaBudgetSetV1(
                amount_micros=amount,
                budget_field="daily_budget" if state.daily_budget_micros else "lifetime_budget",
            )
        else:
            if state.budget_mode not in {"BUDGET_MODE_DAY", "BUDGET_MODE_TOTAL"}:
                raise intents.unavailable("unsupported_native_budget")
            action = TikTokBudgetSetV1(amount_micros=amount, budget_mode=state.budget_mode)
    else:
        action = (
            GoogleStatusSetV1(status="PAUSED")
            if isinstance(state, GoogleCurrentState)
            else MetaStatusSetV1(status="PAUSED")
            if isinstance(state, MetaCurrentState)
            else TikTokStatusSetV1(operation_status="DISABLE")
        )
    rationale = fingerprint("inlet.customer-optimization-intent.v1", body.model_dump(mode="json"))
    if isinstance(body, RepeatOptimizationIntent):
        return replacement.prepare_repeat_optimization(
            db,
            wid,
            binding,
            state.scope,
            body.predecessor_id,
            state.target,
            action,
            rationale,
            actor,
            runtime.execution,
            runtime.clock,
        )
    return optimization.prepare_optimization(
        db,
        wid,
        binding,
        state.scope,
        state.target,
        action,
        rationale,
        actor,
        runtime.execution,
        runtime.clock,
    )


def prepare(
    db: Session,
    wid: int,
    body: InitialOptimizationIntent,
    actor: str,
    runtime: CustomerOptimizationRuntime,
) -> ProviderExecutionReview:
    try:
        row = _prepare(db, wid, body, actor, runtime)
    except (OptimizationUnavailable, ValidationError):
        raise intents.unavailable("qualified_optimization_review_unavailable") from None
    runtime.execution.authorize(db, wid, actor)
    return row


def purpose(
    row: ProviderExecutionReview,
) -> Literal["create_paused", "activate", "existing_campaign_optimize"]:
    pairs = {
        ("create_paused", "inlet.execution-creation-review.v1"): "create_paused",
        ("activate", "inlet.execution-activation-review.v1"): "activate",
        (
            "existing_campaign_optimize",
            "inlet.execution-optimization-review.v1",
        ): "existing_campaign_optimize",
        (
            "existing_campaign_optimize",
            "inlet.execution-repeat-optimization-review.v1",
        ): "existing_campaign_optimize",
    }
    value = pairs.get((str(row.document.get("purpose")), str(row.document.get("schema_version"))))
    if value is None:
        raise intents.unavailable("unsupported_execution_review")
    return value  # type: ignore[return-value]


def review_view(row: ProviderExecutionReview, db: Session) -> dict[str, Any]:
    try:
        document = parse_review(row.document)
    except ValidationError:
        raise intents.unavailable("execution_review_integrity_unavailable") from None
    if row.digest != document.digest() or row.plan_digest != document.plan.digest():
        raise intents.unavailable("execution_review_integrity_unavailable")
    plan = document.plan
    binding = plan.intent.mandate
    revision = db.get(ProviderExecutionRevision, (binding.mandate_id, binding.revision))
    if revision is None or revision.workspace_id != row.workspace_id:
        raise intents.unavailable("reviewed_policy_unavailable")
    try:
        policy = ProviderMandatePolicy.model_validate(revision.policy)
    except ValidationError:
        raise intents.unavailable("reviewed_policy_unavailable") from None
    if policy.digest() != binding.policy_digest or revision.digest != binding.policy_digest:
        raise intents.unavailable("reviewed_policy_unavailable")
    before = option_view(TargetOption(label="unused", parent_label="unused", state=plan.before))
    before.pop("label")
    before.pop("parent_label")
    return {
        "id": row.id,
        "review_digest": row.digest,
        "plan_digest": row.plan_digest,
        "purpose": document.purpose,
        "environment": plan.intent.mandate.environment,
        "optimization_kind": "repeat"
        if isinstance(document, RepeatOptimizationReview)
        else "initial",
        "platform": plan.intent.scope.account.platform,
        "currency": plan.before.money.currency,
        "target_level": plan.intent.target.kind,
        "affected_target_count": len(plan.before.budget_owner.affected_targets),
        "action": plan.intent.action.model_dump(mode="json"),
        "before": before,
        "target": plan.intent.target.model_dump(mode="json"),
        "affected_targets": [
            t.model_dump(mode="json") for t in plan.before.budget_owner.affected_targets
        ],
        "reviewed_limits": {
            "total_cap_micros": policy.total_cap_micros,
            "per_plan_cap_micros": policy.per_plan_cap_micros,
            "positive_change_cap_micros": policy.positive_change_cap_micros,
            "aggressiveness_percent": policy.aggressiveness_percent,
            "starts_at": policy.starts_at.isoformat(),
            "ends_at": policy.ends_at.isoformat(),
        },
        "other_held_exposure_micros": plan.exposure.existing_reservations_micros,
        "positive_change_micros": plan.positive_change_micros,
        "reserved_upper_micros": plan.exposure.proposed_owner_upper_micros,
        "qualification_expires_at": plan.qualification.expires_at.isoformat(),
        "provider_compare_and_swap": "unavailable",
        "effective_time": "unavailable",
    }
