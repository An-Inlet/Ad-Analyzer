"""Current owned planning limits; never an execution binding or financial admission."""

from datetime import datetime

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.billing.entitlements import live_paid_work, paid_work
from app.customers.access import CustomerPrincipal
from app.customers.identity import IdentityProvider
from app.goals import service as goals
from app.initial_planning.budget_mandate_contracts import BudgetMandatePreparationV1
from app.initial_planning.budget_mandate_models import BudgetMandatePreparationRow
from app.initial_planning.clock import effective_now
from app.initial_planning.planning_consent_models import PlanningConsentRow
from app.initial_planning.runtime import InitialPlanningRuntime
from app.publication import customer_intents
from app.publication.contracts import fingerprint
from app.publication.customer_authority import bind_authority
from app.publication.execution_contracts import ProviderMandatePolicy
from app.publication.execution_models import ProviderExecutionMandate, ProviderExecutionRevision
from app.publication.service import owner
from app.settings import settings
from app.shopify.security import utc


def consent_digest(
    wid: int,
    mandate_id: str,
    revision: int,
    policy_digest: str,
    preparation_digest: str,
    actor: str,
    confirmed_at: datetime,
) -> str:
    return fingerprint(
        "inlet.planning-consent.v1",
        {
            "workspace_id": wid,
            "mandate_id": mandate_id,
            "mandate_revision": revision,
            "policy_digest": policy_digest,
            "preparation_digest": preparation_digest,
            "actor": actor,
            "confirmed_at": utc(confirmed_at).isoformat(),
        },
    )


def checked_planning_limits(
    db: Session,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    workspace_id: int,
    mandate_id: str,
    revision: int,
    runtime: InitialPlanningRuntime,
) -> ProviderMandatePolicy:
    authorize = bind_authority(principal, provider)
    authorize(db, workspace_id, principal.user.id)
    row = db.get(PlanningConsentRow, (mandate_id, revision), populate_existing=True)
    preparation = db.get(
        BudgetMandatePreparationRow, (mandate_id, revision), populate_existing=True
    )
    mandate = db.get(ProviderExecutionMandate, mandate_id, populate_existing=True)
    stored = db.get(ProviderExecutionRevision, (mandate_id, revision), populate_existing=True)
    if (
        row is None
        or preparation is None
        or mandate is None
        or stored is None
        or any(r.workspace_id != workspace_id for r in (row, preparation, mandate, stored))
        or mandate.revision != revision
        or mandate.state != "draft"
    ):
        raise HTTPException(409, "current_planning_confirmation_required")
    try:
        document = BudgetMandatePreparationV1.model_validate(preparation.document)
        policy = ProviderMandatePolicy.model_validate(stored.policy)
    except ValidationError:
        raise HTTPException(409, "planning_confirmation_invalid") from None
    if (
        runtime.profile is None
        or settings.budget_mandate_policy_path is None
        or document.operating_policy_digest != settings.budget_mandate_policy_digest
        or runtime.configuration != runtime.profile.initial
        or document.planning_profile_digest != runtime.profile.digest()
        or policy.workspace_id != workspace_id
        or policy.environment != runtime.profile.environment
        or document.workspace_id != workspace_id
        or document.mandate_id != mandate_id
        or document.mandate_revision != revision
        or document.digest() != preparation.digest
        or row.preparation_digest != preparation.digest
        or policy.digest() != stored.digest
        or stored.digest != row.policy_digest
        or row.policy_digest != preparation.policy_digest
        or row.policy_digest != document.policy_digest
        or row.digest
        != consent_digest(
            workspace_id,
            mandate_id,
            revision,
            row.policy_digest,
            row.preparation_digest,
            row.actor,
            row.confirmed_at,
        )
        or len(policy.accounts) != 1
        or policy.accounts[0].digest() != document.account_scope_digest
        or policy.allowed_target_set_digest != document.target_set_digest
    ):
        raise HTTPException(409, "planning_confirmation_changed")
    try:
        owner(db, workspace_id, row.actor)
    except HTTPException as error:
        if error.status_code not in {403, 404}:
            raise
        raise HTTPException(409, "planning_confirmer_unavailable") from None
    goal = goals.owned(db, workspace_id, policy.goal_id)
    goals.expect(goal, policy.goal_revision)
    definition = goals.current(db, goal).definition
    if (
        definition is None
        or fingerprint("inlet.initial-preview-goal.v1", definition) != document.goal_digest
    ):
        raise HTTPException(409, "planning_goal_changed")
    for scope in policy.accounts:
        if customer_intents.account(db, workspace_id, scope.account.account_id) != scope:
            raise HTTPException(409, "planning_account_changed")
    now = effective_now(db, runtime)
    (live_paid_work if policy.environment == "live" else paid_work)(db, workspace_id, now)
    if goals.assessment(db, goal, now) != "confirmed":
        raise HTTPException(409, "current_confirmed_goal_required")
    authorize(db, workspace_id, principal.user.id)
    now = effective_now(db, runtime)
    if not policy.starts_at <= now < policy.ends_at or utc(row.confirmed_at) > now:
        raise HTTPException(409, "planning_confirmation_outside_period")
    return policy
