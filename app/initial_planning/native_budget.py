"""Owned read-only option discovery, with no qualified optimization runtime."""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.ads.models import Campaign
from app.collectors.meta_budget import NativeBudgetUnavailable
from app.customers.access import CustomerPrincipal
from app.customers.identity import IdentityProvider
from app.goals import service as goals
from app.initial_planning.clock import effective_now
from app.initial_planning.contracts import EfficiencyObjectiveV1
from app.initial_planning.native_budget_contracts import (
    NativeBudgetCatalogV1,
    NativeBudgetRequestV1,
)
from app.initial_planning.runtime import InitialPlanningRuntime
from app.publication import customer_intents
from app.publication.contracts import fingerprint
from app.publication.customer_authority import bind_authority


def owned_request(
    db: Session,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    objective: EfficiencyObjectiveV1,
    runtime: InitialPlanningRuntime,
) -> NativeBudgetRequestV1:
    wid = objective.cohort.workspace_id
    authorize = bind_authority(principal, provider)
    authorize(db, wid, principal.user.id)
    profile = runtime.profile
    if profile is None or runtime.configuration != profile.initial or runtime.native_budget is None:
        raise HTTPException(409, "native_budget_runtime_unavailable")
    goal = goals.owned(db, wid, objective.goal_id)
    goals.expect(goal, objective.goal_revision)
    if goals.assessment(db, goal, effective_now(db, runtime)) != "confirmed":
        raise HTTPException(409, "current_confirmed_goal_required")
    definition = goals.current(db, goal).definition
    if definition is None:
        raise HTTPException(409, "current_confirmed_goal_required")
    scope = customer_intents.account(db, wid, objective.cohort.account_id)
    campaign = db.get(Campaign, objective.cohort.campaign_id)
    if campaign is None or campaign.account_id != objective.cohort.account_id:
        raise HTTPException(409, "native_budget_campaign_changed")
    return NativeBudgetRequestV1.model_validate(
        {
            "profile_digest": profile.digest(),
            "environment": profile.environment,
            "scope": scope.model_dump(),
            "cohort": objective.cohort.model_dump(),
            "goal_id": goal.id,
            "goal_revision": goal.revision,
            "goal_digest": fingerprint(
                "inlet.initial-preview-goal.v1",
                definition,
            ),
            "target": {
                "kind": "campaign",
                "external_id": campaign.external_campaign_id,
                "campaign_id": campaign.external_campaign_id,
            },
        }
    )


def catalog(
    db: Session,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    objective: EfficiencyObjectiveV1,
    runtime: InitialPlanningRuntime,
) -> NativeBudgetCatalogV1:
    request = owned_request(db, principal, provider, objective, runtime)
    assert runtime.native_budget is not None
    # Bind original identity while its owning session is active, then release all
    # database transactions before opening the scoped HTTP context.
    reader_context = runtime.native_budget(principal, provider)
    now = effective_now(db, runtime)
    db.rollback()
    try:
        with reader_context as reader:
            result = reader.read(request, now)
    except NativeBudgetUnavailable as error:
        reason = (
            "native_budget_currency_unsupported"
            if str(error) == "native_budget_currency_unsupported"
            else "native_budget_unavailable"
        )
        raise HTTPException(409, reason) from None
    current = owned_request(db, principal, provider, objective, runtime)
    if (
        current != request
        or result.request != current
        or not (result.observed_at <= effective_now(db, runtime) < result.expires_at)
    ):
        raise HTTPException(409, "native_budget_context_changed")
    return result
