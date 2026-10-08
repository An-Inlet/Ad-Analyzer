"""Actual owned read-only preparation of separately consented conditional authority."""

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.customers.access import CustomerPrincipal
from app.customers.identity import IdentityProvider
from app.goals import service as goals
from app.goals.schemas import GoalDefinition
from app.initial_planning import calibration, native_budget, preview
from app.initial_planning.budget_mandate_contracts import (
    BudgetMandateCustomerIntentV1,
    BudgetMandateOperatingPolicyV1,
    BudgetMandatePreparationV1,
    BudgetMandatePreparedV1,
    ConsentBudgetMandateV1,
    PrepareBudgetMandateV1,
)
from app.initial_planning.budget_mandate_models import BudgetMandatePreparationRow
from app.initial_planning.clock import effective_now
from app.initial_planning.contracts import PreviewIntentV1
from app.initial_planning.native_budget_contracts import NativeBudgetOptionV1
from app.initial_planning.planning_consent_models import PlanningConsentRow
from app.initial_planning.planning_consents import checked_planning_limits, consent_digest
from app.initial_planning.runtime import InitialPlanningRuntime
from app.publication import execution_mandates as mandates
from app.publication.budget_period import financial_budget_period
from app.publication.contracts import fingerprint
from app.publication.customer_authority import bind_authority
from app.publication.execution_contracts import ExecutionAccount, ProviderMandatePolicy
from app.publication.execution_models import ProviderExecutionMandate


def denied(reason: str) -> HTTPException:
    return HTTPException(409, reason)


def resolve(
    db: Session,
    wid: int,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    intent: BudgetMandateCustomerIntentV1,
    runtime: InitialPlanningRuntime,
    operating: BudgetMandateOperatingPolicyV1 | None,
) -> tuple[ProviderMandatePolicy, NativeBudgetOptionV1, str]:
    profile = runtime.profile
    if operating is None or profile is None:
        raise denied("budget_mandate_policy_unavailable")
    if (
        operating.planning_reporting_profile_digest != profile.digest()
        or operating.environment != profile.environment
    ):
        raise denied("budget_mandate_policy_changed")
    selection = intent.selection
    objective = calibration.read_objective(
        db, principal, provider, wid, selection.calibration_id, runtime
    )
    evidence = PreviewIntentV1(
        objective=objective,
        calibration_id=selection.calibration_id,
        observation_id=selection.observation_id,
    )
    before = preview.inputs(db, principal, provider, evidence, runtime)
    catalog = native_budget.catalog(db, principal, provider, objective, runtime)
    if preview.inputs(db, principal, provider, evidence, runtime) != before:
        raise denied("budget_mandate_reporting_changed")
    option = next(
        (o for o in catalog.options if o.identifier() == selection.native_option_id), None
    )
    if option is None:
        raise denied("budget_mandate_selection_changed")
    native = option.observation
    if (
        native.unsupported_reasons
        or native.budget_mode != "daily"
        or native.currency != operating.currency
        or native.currency_exponent != 2
    ):
        raise denied("budget_mandate_native_unsupported")
    goal = goals.owned(db, wid, objective.goal_id)
    definition = GoalDefinition.model_validate(goals.current(db, goal).definition)
    if (
        definition.aggressiveness != intent.aggressiveness
        or intent.total_cap_micros > definition.budget_micros
        or definition.target_window.currency != native.currency
        or definition.target_window.time_zone != native.time_zone
    ):
        raise denied("budget_mandate_goal_limits_changed")
    rule = operating.rule(intent.aggressiveness)
    per_plan = min(intent.total_cap_micros, rule.per_plan_cap_micros)
    starts_at, ends_at = financial_budget_period(definition)
    policy = ProviderMandatePolicy(
        workspace_id=wid,
        environment=operating.environment,
        goal_id=goal.id,
        goal_revision=goal.revision,
        currency=native.currency,
        time_zone=native.time_zone,
        starts_at=starts_at,
        ends_at=ends_at,
        accounts=[ExecutionAccount.model_validate(native.request.scope.model_dump())],
        total_cap_micros=intent.total_cap_micros,
        per_plan_cap_micros=per_plan,
        positive_change_cap_micros=min(per_plan, rule.positive_change_cap_micros),
        action_limit=rule.action_limit,
        cooldown_seconds=rule.cooldown_seconds,
        freshness_seconds=rule.freshness_seconds,
        aggressiveness_percent=rule.aggressiveness_percent,
        allowed_purposes=["existing_campaign_optimize"],
        allowed_target_set_digest=native.budget_owner.target_set_digest(),
        campaign_and_creative_policy="new_exact_review_required",
        activation_policy="separate_exact_approval",
    )
    return (
        policy,
        option,
        fingerprint("inlet.initial-preview-goal.v1", definition.model_dump(mode="json")),
    )


def projection(
    row: ProviderExecutionMandate,
    policy: ProviderMandatePolicy,
    document: BudgetMandatePreparationV1,
    option: NativeBudgetOptionV1,
) -> BudgetMandatePreparedV1:
    return BudgetMandatePreparedV1.model_validate(
        dict(
            mandate_id=row.id,
            revision=row.revision,
            policy_digest=policy.digest(),
            preparation_digest=document.digest(),
            state=row.state,
            total_cap_micros=policy.total_cap_micros,
            per_plan_cap_micros=policy.per_plan_cap_micros,
            positive_change_cap_micros=policy.positive_change_cap_micros,
            aggressiveness=document.customer_intent.aggressiveness,
            currency=policy.currency,
            native_label=option.label,
            affected_target_count=len(option.observation.budget_owner.affected_targets),
        )
    )


def prepare_budget_mandate(
    db: Session,
    workspace_id: int,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    body: PrepareBudgetMandateV1,
    runtime: InitialPlanningRuntime,
    operating_policy: BudgetMandateOperatingPolicyV1 | None,
) -> BudgetMandatePreparedV1:
    authorize = bind_authority(principal, provider)
    try:
        policy, option, goal_digest = resolve(
            db, workspace_id, principal, provider, body.intent, runtime, operating_policy
        )
        assert operating_policy is not None and runtime.profile is not None
        authorize(db, workspace_id, principal.user.id)
        if body.mandate_id:
            _, old = mandates.owned(db, workspace_id, body.mandate_id)
            old_policy = mandates.policy(db, old)
            if policy.total_cap_micros > old_policy.total_cap_micros:
                raise denied("budget_mandate_overall_cap_increase_requires_new_review")
        row = mandates.revise(
            db,
            workspace_id,
            policy,
            principal.user.id,
            lambda: effective_now(db, runtime),
            mandate_id=body.mandate_id,
            expected_revision=body.expected_revision,
            commit=False,
        )
        document = BudgetMandatePreparationV1(
            workspace_id=workspace_id,
            mandate_id=row.id,
            mandate_revision=row.revision,
            policy_digest=policy.digest(),
            operating_policy=operating_policy,
            operating_policy_digest=operating_policy.digest(),
            planning_profile_digest=runtime.profile.digest(),
            goal_digest=goal_digest,
            customer_intent=body.intent,
            account_scope_digest=policy.accounts[0].digest(),
            target_set_digest=option.observation.budget_owner.target_set_digest(),
        )
        db.add(
            BudgetMandatePreparationRow(
                workspace_id=workspace_id,
                mandate_id=row.id,
                mandate_revision=row.revision,
                policy_digest=policy.digest(),
                digest=document.digest(),
                document=document.model_dump(mode="json"),
            )
        )
        db.flush()
        authorize(db, workspace_id, principal.user.id)
        if effective_now(db, runtime) >= option.observation.expires_at:
            raise denied("budget_mandate_native_expired")
        result = projection(row, policy, document, option)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


def consent_budget_mandate(
    db: Session,
    workspace_id: int,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    mandate_id: str,
    body: ConsentBudgetMandateV1,
    runtime: InitialPlanningRuntime,
    operating_policy: BudgetMandateOperatingPolicyV1 | None,
) -> BudgetMandatePreparedV1:
    authorize = bind_authority(principal, provider)
    try:
        authorize(db, workspace_id, principal.user.id)
        _, row = mandates.owned(db, workspace_id, mandate_id)
        stored = db.get(BudgetMandatePreparationRow, (mandate_id, body.expected_revision))
        if stored is None or stored.workspace_id != workspace_id:
            raise denied("budget_mandate_preparation_unavailable")
        document = BudgetMandatePreparationV1.model_validate(stored.document)
        if (
            document.workspace_id != workspace_id
            or document.mandate_id != mandate_id
            or document.mandate_revision != row.revision
            or row.revision != body.expected_revision
            or stored.digest != document.digest()
            or stored.digest != body.preparation_digest
            or stored.policy_digest != document.policy_digest
            or document.policy_digest != body.policy_digest
            or document.customer_intent.selection != body.selection
            or operating_policy is None
            or document.operating_policy != operating_policy
            or runtime.profile is None
            or document.planning_profile_digest != runtime.profile.digest()
        ):
            raise denied("budget_mandate_preparation_changed")
        policy, option, goal_digest = resolve(
            db,
            workspace_id,
            principal,
            provider,
            document.customer_intent,
            runtime,
            operating_policy,
        )
        authorize(db, workspace_id, principal.user.id)
        _, row = mandates.owned(db, workspace_id, mandate_id)
        if (
            policy != mandates.policy(db, row)
            or policy.digest() != document.policy_digest
            or goal_digest != document.goal_digest
            or policy.accounts[0].digest() != document.account_scope_digest
            or policy.allowed_target_set_digest != document.target_set_digest
        ):
            raise denied("budget_mandate_preparation_changed")
        if effective_now(db, runtime) >= option.observation.expires_at:
            raise denied("budget_mandate_native_expired")
        if row.state != "draft":
            raise denied("planning_draft_required")
        confirmed_at = effective_now(db, runtime)
        record = db.get(PlanningConsentRow, (mandate_id, body.expected_revision))
        if record is None:
            record = PlanningConsentRow(
                mandate_id=mandate_id,
                mandate_revision=body.expected_revision,
                workspace_id=workspace_id,
                policy_digest=policy.digest(),
                preparation_digest=document.digest(),
                actor=principal.user.id,
                confirmed_at=confirmed_at,
                digest=consent_digest(
                    workspace_id,
                    mandate_id,
                    body.expected_revision,
                    policy.digest(),
                    document.digest(),
                    principal.user.id,
                    confirmed_at,
                ),
            )
            db.add(record)
            db.flush()
        checked_planning_limits(
            db, principal, provider, workspace_id, mandate_id, body.expected_revision, runtime
        )
        if effective_now(db, runtime) >= option.observation.expires_at:
            raise denied("budget_mandate_native_expired")
        result = projection(row, policy, document, option).model_copy(update={"state": "confirmed"})
        db.commit()
        return result
    except ValidationError:
        db.rollback()
        raise denied("budget_mandate_preparation_invalid") from None
    except Exception:
        db.rollback()
        raise
