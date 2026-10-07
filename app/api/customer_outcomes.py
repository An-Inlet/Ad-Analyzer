"""Owned report creation/read; no provider execution or spending authority."""

from fastapi import APIRouter, Request, Response

from app.customers.access import (
    Database,
    MutationPrincipal,
    Principal,
    Provider,
    require_customer,
)
from app.outcomes import owned
from app.outcomes.owned_contracts import AssessmentRequest
from app.publication.service import owner

router = APIRouter(
    prefix="/api/customer/v1/workspaces/{workspace_id}/outcome-assessments", tags=["customer"]
)


@router.post("", status_code=201)
def create_assessment(
    workspace_id: int,
    body: AssessmentRequest,
    principal: MutationPrincipal,
    db: Database,
    provider: Provider,
    request: Request,
    response: Response,
) -> dict[str, object]:
    def authorize() -> None:
        db.expire(principal.session)
        db.expire(principal.user)
        current = require_customer(request, db, provider)
        owner(db, workspace_id, current.user.id)

    row = owned.create(db, workspace_id, principal.user.id, body, authorize)
    result = owned.read(db, workspace_id, row.id, principal.user.id, authorize)
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get("/{assessment_id}")
def read_assessment(
    workspace_id: int,
    assessment_id: str,
    principal: Principal,
    db: Database,
    provider: Provider,
    request: Request,
    response: Response,
) -> dict[str, object]:
    def authorize() -> None:
        db.expire(principal.session)
        db.expire(principal.user)
        current = require_customer(request, db, provider)
        owner(db, workspace_id, current.user.id)

    result = owned.read(db, workspace_id, assessment_id, principal.user.id, authorize)
    response.headers["Cache-Control"] = "no-store"
    return result
