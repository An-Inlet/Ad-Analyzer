"""Social execution accepts exact owned confirmation references, never provider proof."""

from typing import Annotated, Any

from fastapi import APIRouter, Query, Response
from sqlalchemy import select

from app.api.customer_execution import Runtime, Store, bound
from app.api.customer_social_review import view
from app.customers.access import Database, MutationPrincipal, Principal, Provider
from app.publication import customer_intents
from app.publication.provider_contracts import Id
from app.publication.service import owner
from app.publication.social_execution_intents import SocialCreationIntent, prepare_creation
from app.publication.social_review_models import (
    SocialConfigurationApproval,
    SocialConfigurationReview,
)

router = APIRouter(
    prefix="/api/customer/v1/workspaces/{workspace_id}/execution/social", tags=["customer"]
)


@router.post("/creation-reviews", status_code=201)
def create_review(
    workspace_id: int,
    body: SocialCreationIntent,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    runtime: Runtime,
    media: Store,
    response: Response,
) -> dict[str, Any]:
    server = bound(runtime, principal, provider)
    row = prepare_creation(db, workspace_id, body, principal.user.id, media, server)
    response.headers["Cache-Control"] = "no-store"
    return customer_intents.review_view(row)


@router.get("/confirmed-configurations")
def configurations(
    workspace_id: int,
    draft_id: Annotated[Id, Query()],
    principal: Principal,
    db: Database,
    response: Response,
) -> list[dict[str, Any]]:
    owner(db, workspace_id, principal.user.id)
    rows = db.scalars(
        select(SocialConfigurationReview)
        .join(
            SocialConfigurationApproval,
            (SocialConfigurationApproval.review_id == SocialConfigurationReview.id)
            & (SocialConfigurationApproval.workspace_id == workspace_id),
        )
        .where(
            SocialConfigurationReview.workspace_id == workspace_id,
            SocialConfigurationReview.draft_id == draft_id,
        )
        .order_by(SocialConfigurationReview.created_at.desc(), SocialConfigurationReview.id)
        .limit(50)
    )
    response.headers["Cache-Control"] = "no-store"
    return [view(db, row) for row in rows]
