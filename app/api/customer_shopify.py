"""Customer-owned Shopify authorization, isolated from operator credentials."""

import base64
import hashlib
import time
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse
from pydantic import Field
from sqlalchemy import select

from app.customers.access import (
    CustomerPrincipal,
    Database,
    MutationPrincipal,
    Principal,
    Provider,
    customer_workspace,
)
from app.customers.models import CustomerMembership, CustomerSession, CustomerUser
from app.goals.schemas import StrictModel
from app.settings import settings
from app.shopify.client import ShopifyClient
from app.shopify.models import ShopifyConnection, ShopifyOAuthState
from app.shopify.security import ShopifyError, configuration_ready, verify_callback
from app.shopify.service import ConnectionService
from app.workspaces.models import Workspace

router = APIRouter(prefix="/api/customer/v1", tags=["customer"])


def get_customer_shopify_client() -> ShopifyClient:
    # Construction performs no network IO; authorization remains disabled by default.
    return ShopifyClient(settings)


Client = Annotated[ShopifyClient, Depends(get_customer_shopify_client)]


class Authorization(StrictModel):
    shop: str = Field(min_length=1, max_length=253)


class Callback(StrictModel):
    query: list[tuple[str, str]] = Field(min_length=1, max_length=32)


def guard(db: Database, principal: CustomerPrincipal, workspace_id: int) -> str:
    """Lock current authorization through credential persistence/disconnection."""
    db.scalar(
        select(Workspace)
        .where(Workspace.id == workspace_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    # Login updates user contact data before rotating its presented session.
    # Use the same order so neither transaction holds the other's next row.
    user = db.scalar(
        select(CustomerUser)
        .where(CustomerUser.id == principal.user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    session = db.scalar(
        select(CustomerSession)
        .where(CustomerSession.digest == principal.session.digest)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if (
        session is None
        or session.revoked_at is not None
        or session.expires_at <= int(time.time())
        or user is None
        or user.status != "active"
        or session.user_id != user.id
    ):
        raise HTTPException(401, "customer authentication required")
    db.scalar(
        select(CustomerMembership)
        .where(
            CustomerMembership.user_id == user.id, CustomerMembership.workspace_id == workspace_id
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    _, role = customer_workspace(db, user.id, workspace_id)
    if role not in {"owner", "admin"}:
        raise HTTPException(403, "insufficient role")
    return role


def ready() -> None:
    if not configuration_ready(settings, customer=True):
        raise HTTPException(503, "Shopify customer connection unavailable")


def view(row: ShopifyConnection) -> dict[str, Any]:
    return {
        "id": row.id,
        "shop_domain": row.shop_domain,
        "shop_name": row.shop_name,
        "status": row.status,
        "currency": row.currency_code,
        "time_zone": row.time_zone,
        "last_sync_at": row.last_sync_at,
        "error_code": row.error_code,
        "commerce_store_id": row.commerce_store_id,
        "live_verified": False,
    }


@router.post("/workspaces/{workspace_id}/shopify/authorize")
def authorize(
    workspace_id: int,
    body: Authorization,
    principal: MutationPrincipal,
    db: Database,
    response: Response,
    client: Client,
) -> dict[str, str]:
    guard(db, principal, workspace_id)
    ready()
    response.headers["Cache-Control"] = "no-store"
    try:
        url = ConnectionService(db, settings, client).begin(
            workspace_id,
            body.shop,
            "customer:" + principal.session.digest,
            datetime.now(UTC),
            customer=True,
        )
    except ShopifyError:
        db.rollback()
        raise HTTPException(422, "Shopify authorization unavailable") from None
    return {"authorization_url": url}


@router.get("/workspaces/{workspace_id}/shopify")
def listing(
    workspace_id: int, principal: Principal, db: Database, response: Response
) -> list[dict[str, Any]]:
    customer_workspace(db, principal.user.id, workspace_id)
    response.headers["Cache-Control"] = "no-store"
    row = ConnectionService(db, settings).get(workspace_id)
    return [view(row)] if row else []


@router.delete("/workspaces/{workspace_id}/shopify", status_code=204)
def disconnect(
    workspace_id: int, principal: MutationPrincipal, db: Database, response: Response
) -> None:
    role = guard(db, principal, workspace_id)
    try:
        ConnectionService(db, settings).disconnect(workspace_id, role)
    except ShopifyError:
        db.rollback()
        raise HTTPException(503, "Shopify disconnection unavailable") from None
    response.headers["Cache-Control"] = "no-store"


@router.post("/shopify/callback")
def callback(
    body: Callback,
    principal: MutationPrincipal,
    db: Database,
    response: Response,
    client: Client,
    provider: Provider,
) -> dict[str, Any]:
    ready()
    response.headers["Cache-Control"] = "no-store"
    try:
        secret = settings.shopify_client_secret
        assert secret is not None
        values = verify_callback(body.query, secret.get_secret_value(), datetime.now(UTC))
        service = ConnectionService(db, settings, client)
        actor = "customer:" + principal.session.digest
        pending = service.pending(values, actor, datetime.now(UTC))
        wid, nonce = pending.workspace_id, pending.digest
        role = guard(db, principal, wid)
        # Serialize concurrent callbacks after the workspace lock, refreshing the nonce.
        locked_state = db.scalar(
            select(ShopifyOAuthState)
            .where(ShopifyOAuthState.digest == nonce)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if locked_state is None:
            raise ShopifyError("invalid_oauth_state")

        def recheck() -> None:
            guard(db, principal, wid)
            provider.check_active(principal.user.subject, principal.session.authenticated_at)

        row = service.finish(
            locked_state, values["code"], role, datetime.now(UTC), before_persist=recheck
        )
        return {"workspace_id": wid, **view(row)}
    except ShopifyError:
        db.rollback()
        raise HTTPException(422, "Shopify callback unavailable; restart authorization") from None
    except HTTPException:
        db.rollback()
        raise


@router.get("/shopify/callback")
def browser_callback() -> Response:
    # All query material stays in browser memory. No interpolation into HTML/JS.
    html = """<!doctype html><html lang="en"><meta charset="utf-8">
<title>Connect Shopify — Inlet</title><h1>Connect Shopify</h1>
<p id="result">Completing authorization…</p><script>
const query = [...new URLSearchParams(location.search).entries()];
history.replaceState(null, '', location.pathname);
const csrf = document.cookie.split('; ').find(x => x.startsWith('__Host-inlet_csrf='));
fetch(location.pathname, {method:'POST', credentials:'same-origin',
 headers:{'Content-Type':'application/json','X-CSRF-Token':csrf ? csrf.split('=')[1] : ''},
 body:JSON.stringify({query})})
.then(r => {document.getElementById('result').textContent = r.ok
 ? 'Store connected. Return to Inlet.'
 : 'Connection unavailable. Restart authorization in Inlet.';})
.catch(() => {document.getElementById('result').textContent=
 'Connection unavailable. Restart in Inlet.';});
</script></html>"""
    script = html.split("<script>", 1)[1].split("</script>", 1)[0]
    digest = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    return HTMLResponse(
        html,
        headers={
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "X-Frame-Options": "DENY",
            "Content-Security-Policy": "default-src 'none'; connect-src 'self'; "
            f"script-src 'sha256-{digest}'; base-uri 'none'; frame-ancestors 'none'",
        },
    )
