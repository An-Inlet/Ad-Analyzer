"""Owned read-only TikTok display; no client proof or provider identifiers accepted."""

from fastapi import APIRouter, HTTPException, Response
from pydantic import ValidationError

from app.collectors import tiktok_customer_discovery as display
from app.collectors.tiktok_customer_discovery_contracts import (
    TikTokDiscoveryIntentV1,
    TikTokDiscoveryViewV1,
)
from app.collectors.tiktok_owned_discovery import TikTokDiscoveryUnavailable
from app.customers.access import Database, MutationPrincipal, Provider
from app.production_runtime.tiktok_discovery import read_configured_discovery
from app.publication import customer_intents
from app.publication.customer_authority import bind_authority
from app.settings import settings

router = APIRouter(prefix="/api/customer/v1/workspaces/{workspace_id}/execution", tags=["customer"])


@router.post("/tiktok/discovery", response_model=TikTokDiscoveryViewV1)
def read_tiktok_discovery(
    workspace_id: int,
    body: TikTokDiscoveryIntentV1,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    response: Response,
) -> TikTokDiscoveryViewV1:
    response.headers["Cache-Control"] = "no-store"
    actor = principal.user.id
    authorize = bind_authority(principal, provider)
    authorize(db, workspace_id, actor)
    scope = customer_intents.account(db, workspace_id, body.account_id)
    if scope.account.platform != "tiktok_ads":
        raise HTTPException(409, "Choose a connected TikTok account.")
    if body.identity_type == "BC_AUTH_TT":
        authorize(db, workspace_id, actor)
        return display.unavailable(body, "business_center_selection_unavailable")
    db.rollback()  # No caller transaction or workspace/source locks span HTTP.
    try:
        result = read_configured_discovery(db, authorize, actor, settings, scope, body)
        authorize(db, workspace_id, actor)
        if customer_intents.account(db, workspace_id, body.account_id) != scope:
            raise HTTPException(409, "The account changed. Refresh before reading again.")
        authorize(db, workspace_id, actor)
        return result
    except (TikTokDiscoveryUnavailable, ValidationError):
        raise HTTPException(
            409, "TikTok discovery could not be completed. Refresh and try again."
        ) from None
