"""Owner-only read projection, using POST for bounded structured input and CSRF."""

from fastapi import APIRouter, Request, Response

from app.customers.access import Database, MutationPrincipal, Provider, require_customer
from app.outcomes.descriptive import compare
from app.outcomes.descriptive_contracts import DescriptiveComparison, DescriptiveRequest
from app.publication.service import owner

router = APIRouter(prefix="/api/customer/v1/workspaces/{workspace_id}", tags=["customer"])


@router.post("/descriptive-comparisons")
def descriptive_comparison(
    workspace_id: int,
    body: DescriptiveRequest,
    principal: MutationPrincipal,
    db: Database,
    provider: Provider,
    request: Request,
    response: Response,
) -> DescriptiveComparison:
    def authorize() -> None:
        db.expire(principal.session)
        db.expire(principal.user)
        current = require_customer(request, db, provider)
        owner(db, workspace_id, current.user.id)

    result = compare(db, workspace_id, body, authorize)
    response.headers["Cache-Control"] = "no-store"
    return result
