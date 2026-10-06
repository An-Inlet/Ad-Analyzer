"""Read-only owned target catalog; it cannot construct a spending runtime."""

from dataclasses import replace

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.ads.models import Campaign
from app.customers.access import CustomerPrincipal
from app.customers.identity import IdentityProvider
from app.executors.optimization_http import OptimizationUnavailable
from app.initial_planning.clock import effective_now
from app.initial_planning.contracts import EfficiencyObjectiveV1
from app.initial_planning.runtime import InitialPlanningRuntime
from app.publication import customer_optimization
from app.publication.customer_authority import bind_authority
from app.publication.customer_optimization_contracts import TargetCatalog, TargetQuery


def catalog(
    db: Session,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    objective: EfficiencyObjectiveV1,
    runtime: InitialPlanningRuntime,
) -> TargetCatalog:
    authorize = bind_authority(principal, provider)
    wid = objective.cohort.workspace_id
    authorize(db, wid, principal.user.id)
    if runtime.native is None or runtime.native.catalog is None:
        raise HTTPException(409, "Current native budget details are unavailable.")
    if (
        runtime.configuration is None
        or runtime.native.execution.environment != runtime.configuration.environment
    ):
        raise HTTPException(409, "Native read environment differs from planning configuration.")
    native = replace(
        runtime.native,
        execution=replace(runtime.native.execution, authorize=authorize),
        clock=lambda: effective_now(db, runtime),
    )
    query = TargetQuery(
        goal_id=objective.goal_id,
        goal_revision=objective.goal_revision,
        account_id=objective.cohort.account_id,
    )
    before = customer_optimization.request(db, wid, query, principal.user.id, native)
    observed_at = effective_now(db, runtime)
    db.rollback()  # no database transaction or locks during native HTTP
    assert native.catalog is not None
    try:
        result = TargetCatalog.model_validate(native.catalog(before, observed_at).model_dump())
    except (OptimizationUnavailable, ValueError, TypeError):
        raise HTTPException(
            409, "Current native campaign budget details are unavailable."
        ) from None
    current = customer_optimization.request(db, wid, query, principal.user.id, native)
    if (
        current != before
        or result.request != current
        or not result.observed_at <= effective_now(db, runtime) < result.expires_at
    ):
        raise HTTPException(409, "The native campaign catalog changed or expired.")
    campaign = db.get(Campaign, objective.cohort.campaign_id, populate_existing=True)
    if campaign is None or campaign.account_id != objective.cohort.account_id:
        raise HTTPException(409, "The reported campaign changed.")
    # Reporting is campaign-level: do not transfer its efficiency to a child or
    # unrelated native owner, even if that child is selectable elsewhere.
    options = tuple(
        option
        for option in result.options
        if option.state.target.kind == "campaign"
        and option.state.target.external_id == campaign.external_campaign_id
        and option.state.target == option.state.budget_owner.owner
        and option.state.money.currency == objective.cohort.currency
        and option.state.money.account_timezone == objective.cohort.time_zone
    )
    authorize(db, wid, principal.user.id)
    return result.model_copy(update={"options": list(options)})
