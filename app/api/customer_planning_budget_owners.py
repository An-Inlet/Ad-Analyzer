"""CSRF-protected original-receipt Google owner discovery."""

from fastapi import APIRouter, Response

from app.api import customer_planning_documents
from app.customers.access import Database, MutationPrincipal, Provider
from app.planning_documents.google_budget_owner_discovery import read_google_budget_owners
from app.planning_documents.google_budget_owner_discovery_contracts import (
    GoogleBudgetOwnersRequestV1,
    GoogleBudgetOwnersViewV1,
)
from app.planning_documents.read_context import snapshot

router = APIRouter(prefix="/api/customer/v1/workspaces/{workspace_id}/planning", tags=["customer"])


@router.post("/google-budget-owners", response_model=GoogleBudgetOwnersViewV1)
def discover_google_budget_owners(
    workspace_id: int,
    body: GoogleBudgetOwnersRequestV1,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    response: Response,
) -> GoogleBudgetOwnersViewV1:
    response.headers["Cache-Control"] = "no-store"
    original = snapshot(principal)
    configured = customer_planning_documents.service(db, provider, principal)
    return read_google_budget_owners(configured, original, workspace_id, body)
