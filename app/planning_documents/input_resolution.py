"""Resolve customer input intent from owned records and exact server-read catalogs."""

from datetime import datetime

from sqlalchemy.orm import Session

from app.goals import service as goals
from app.goals.schemas import GoalDefinition
from app.planning_documents.common import fingerprint
from app.planning_documents.composer import targets
from app.planning_documents.context import (
    AccountRef,
    BudgetPeriod,
    ConfirmedGoalRef,
    CustomerAssumption,
    CustomerScenarioIntent,
    FixedAllocation,
    PlanInputRevision,
    TargetRef,
)
from app.planning_documents.ports import CatalogEvidence
from app.planning_documents.repository import changed, check_goal
from app.planning_documents.requests import CustomerInputs, TargetSelector
from app.publication import customer_intents


def prepare(
    db: Session,
    *,
    workspace_id: int,
    plan_id: str,
    revision: int,
    actor_id: str,
    intent: CustomerInputs,
    now: datetime,
) -> PlanInputRevision:
    """Caller holds current owner/session locks. Targets resolve after read IO."""
    intent = CustomerInputs.model_validate(intent)
    goal = goals.owned(db, workspace_id, intent.goal_id)
    db.refresh(goal)
    goals.expect(goal, intent.goal_revision)
    goal_revision = goals.current(db, goal)
    if (
        goal.confirmed_preview_id is None
        or goal_revision.definition is None
        or goal_revision.confirmed_at is None
    ):
        raise changed("confirm the current goal before planning")
    definition = GoalDefinition.model_validate(goal_revision.definition)
    accounts = []
    for account_id in sorted(intent.account_ids):
        scope = customer_intents.account(db, workspace_id, account_id)
        accounts.append(
            AccountRef(
                workspace_id=workspace_id,
                account_id=account_id,
                connection_id=scope.account.connection_id,
                platform=scope.account.platform,
                connection_version=scope.connection_version,
            )
        )
    result = PlanInputRevision(
        workspace_id=workspace_id,
        plan_id=plan_id,
        revision=revision,
        goal=ConfirmedGoalRef(
            workspace_id=workspace_id,
            goal_id=goal.id,
            revision=goal.revision,
            definition=definition,
            definition_digest=fingerprint("goal-definition", definition.model_dump(mode="json")),
            confirmation_reference=goal.confirmed_preview_id,
        ),
        accounts=tuple(accounts),
        budget_period=BudgetPeriod(
            starts_on=definition.budget_start,
            ends_on_exclusive=definition.budget_end,
            currency=definition.target_window.currency,
            time_zone=definition.target_window.time_zone,
        ),
        total_ceiling_micros=definition.budget_micros,
        aggressiveness=definition.aggressiveness,
        reporting_window=intent.reporting_window,
        comparison_window=intent.comparison_window,
        milestone=intent.milestone,
        product_offer=intent.product_offer,
        constraints=intent.constraints,
        assumptions=tuple(
            CustomerAssumption(
                key=f"customer-{index}", statement=value, author_id=actor_id, recorded_at=now
            )
            for index, value in enumerate(intent.assumptions)
        ),
        excluded_entity_keys=(),
        fixed_allocations=(),
        scenario_intents=(),
        maximum_creative_assets=intent.maximum_creative_assets,
        selected_reporting=intent.selected_reporting,
        created_by=actor_id,
        created_at=now,
    )
    check_goal(db, result, now)
    return result


def resolve(
    prepared: PlanInputRevision, intent: CustomerInputs, catalogs: tuple[CatalogEvidence, ...]
) -> PlanInputRevision:
    """Exact snapshot selectors only. Caller rechecks catalog source fences at commit."""
    prepared = PlanInputRevision.model_validate(prepared)
    intent = CustomerInputs.model_validate(intent)
    if prepared.selected_reporting != intent.selected_reporting:
        raise ValueError("prepared selected reporting differs")
    available = {
        (target.account.account_id, target.canonical_entity_key, target.selection_key): target
        for catalog in catalogs
        for target in targets(CatalogEvidence.model_validate(catalog))
    }

    def selected(selector: TargetSelector) -> TargetRef:
        key = (selector.account_id, selector.canonical_entity_key, selector.selection_key)
        target = available.get(key)
        if target is None or target.account not in prepared.accounts:
            raise changed("Selected target changed. Read the current catalog and select again.")
        return target

    def allocation(selector: TargetSelector, amount: int) -> FixedAllocation:
        return FixedAllocation(target=selected(selector), amount_micros=amount)

    values = prepared.model_dump(mode="python")
    values.update(
        excluded_entity_keys=tuple(selected(s).canonical_entity_key for s in intent.exclusions),
        fixed_allocations=tuple(
            allocation(a.target, a.amount_micros) for a in intent.fixed_allocations
        ),
        scenario_intents=tuple(
            CustomerScenarioIntent(
                key=scenario.key,
                title=scenario.title,
                allocations=tuple(
                    allocation(a.target, a.amount_micros) for a in scenario.allocations
                ),
                unallocated_micros=scenario.unallocated_micros,
            )
            for scenario in intent.scenario_intents
        ),
    )
    return PlanInputRevision.model_validate(values)
