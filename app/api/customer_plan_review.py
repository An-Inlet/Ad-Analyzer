"""Exact server-derived period/context for the existing planning simulation UI."""

from datetime import UTC, datetime, time
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Response
from pydantic import AwareDatetime, Field, ValidationError

from app.api.customer_mandates import access
from app.customers.access import Database, MutationPrincipal, Provider, lock_customer_mutation
from app.goals import service as goals
from app.goals.schemas import GoalDefinition, StrictModel
from app.mandates.schemas import AccountScope, MandateDefinition
from app.publication import customer_intents

router = APIRouter(prefix="/api/customer/v1/workspaces/{workspace_id}/mandates", tags=["customer"])


class PlanningContextIntent(StrictModel):
    goal_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    expected_revision: int = Field(strict=True, ge=1)
    account_id: int = Field(strict=True, gt=0)


class PlanningContext(StrictModel):
    goal_id: str
    goal_revision: int
    account: AccountScope
    currency: str
    time_zone: str
    local_start: str
    local_end: str
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    total_ceiling_micros: int
    mode: Literal["simulation"] = "simulation"
    live_execution_enabled: Literal[False] = False


def exact_period(definition: GoalDefinition) -> tuple[datetime, datetime]:
    zone = ZoneInfo(definition.target_window.time_zone)
    resolved = []
    for day in (definition.budget_start, definition.budget_end):
        local = datetime.combine(day, time.min)
        first = local.replace(tzinfo=zone, fold=0).astimezone(UTC)
        second = local.replace(tzinfo=zone, fold=1).astimezone(UTC)
        if first != second or first.astimezone(zone).replace(tzinfo=None) != local:
            raise HTTPException(
                422, "The goal period has an ambiguous or nonexistent local boundary."
            )
        resolved.append(first)
    return resolved[0], resolved[1]


@router.post("/planning-context", response_model=PlanningContext)
def planning_context(
    workspace_id: int,
    body: PlanningContextIntent,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    response: Response,
) -> PlanningContext:
    lock_customer_mutation(db, principal, workspace_id, provider)
    access(db, principal.user.id, workspace_id, response, "draft")
    goal = goals.owned(db, workspace_id, body.goal_id)
    goals.expect(goal, body.expected_revision)
    if goals.assessment(db, goal, datetime.now(UTC)) != "confirmed":
        raise HTTPException(409, "Current confirmed goal required.")
    definition = GoalDefinition.model_validate(goals.current(db, goal).definition)
    scope = customer_intents.account(db, workspace_id, body.account_id)
    from app.ads.models import AdvertisingAccount

    account = db.get(AdvertisingAccount, scope.account.account_id)
    if account is None or account.currency_code != definition.target_window.currency:
        raise HTTPException(409, "Account currency must match the goal.")
    start, end = exact_period(definition)
    # Validate the fixed profile/period against the existing API; nothing is persisted.
    try:
        MandateDefinition(
            goal_id=goal.id,
            goal_revision=goal.revision,
            currency=definition.target_window.currency,
            time_zone=definition.target_window.time_zone,
            starts_at=start,
            ends_at=end,
            accounts=[scope.account],
            total_cap_micros=definition.budget_micros,
            per_action_cap_micros=definition.budget_micros,
            positive_change_cap_micros=0,
            action_limit=1,
            cooldown_seconds=0,
            freshness_seconds=60,
            allowed_actions=["new_campaign"],
        )
    except ValidationError:
        raise HTTPException(
            422, "The confirmed goal budget period cannot support this plan."
        ) from None

    lock_customer_mutation(db, principal, workspace_id, provider)
    goals.expect(goal, body.expected_revision)
    if goals.assessment(db, goal, datetime.now(UTC)) != "confirmed":
        raise HTTPException(409, "Current confirmed goal required.")
    response.headers["Cache-Control"] = "no-store"
    return PlanningContext(
        goal_id=goal.id,
        goal_revision=goal.revision,
        account=scope.account,
        currency=definition.target_window.currency,
        time_zone=definition.target_window.time_zone,
        local_start=definition.budget_start.isoformat(),
        local_end=definition.budget_end.isoformat(),
        starts_at=start,
        ends_at=end,
        total_ceiling_micros=definition.budget_micros,
    )
