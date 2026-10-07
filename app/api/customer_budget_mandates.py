"""Customer budget/scope consent remains independent of qualified provider writes."""

from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.api.customer_initial_planning import Runtime
from app.customers.access import Database, MutationPrincipal, Provider
from app.initial_planning.budget_mandate_configuration import load_budget_mandate_policy
from app.initial_planning.budget_mandate_contracts import (
    BudgetMandateOperatingPolicyV1,
    BudgetMandatePreparedV1,
    ConsentBudgetMandateV1,
    PrepareBudgetMandateV1,
)
from app.initial_planning.budget_mandates import consent_budget_mandate, prepare_budget_mandate
from app.settings import settings

router = APIRouter(
    prefix="/api/customer/v1/workspaces/{workspace_id}/initial-planning/budget-mandates",
    tags=["customer"],
)


@lru_cache(maxsize=4)
def _pinned(path: str | None, digest: str | None) -> BudgetMandateOperatingPolicyV1 | None:
    return load_budget_mandate_policy(path, digest)


def get_budget_mandate_policy() -> BudgetMandateOperatingPolicyV1 | None:
    return _pinned(settings.budget_mandate_policy_path, settings.budget_mandate_policy_digest)


Policy = Annotated[BudgetMandateOperatingPolicyV1 | None, Depends(get_budget_mandate_policy)]


@router.post("", status_code=201, response_model=BudgetMandatePreparedV1)
def prepare(
    workspace_id: int,
    body: PrepareBudgetMandateV1,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    runtime: Runtime,
    policy: Policy,
    response: Response,
) -> BudgetMandatePreparedV1:
    response.headers["Cache-Control"] = "no-store"
    return prepare_budget_mandate(db, workspace_id, principal, provider, body, runtime, policy)


@router.post("/{mandate_id}/consent", response_model=BudgetMandatePreparedV1)
def consent(
    workspace_id: int,
    mandate_id: str,
    body: ConsentBudgetMandateV1,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    runtime: Runtime,
    policy: Policy,
    response: Response,
) -> BudgetMandatePreparedV1:
    response.headers["Cache-Control"] = "no-store"
    return consent_budget_mandate(
        db, workspace_id, principal, provider, mandate_id, body, runtime, policy
    )
