from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.billing import service
from app.billing.contracts import BillingTransport, UnavailableBilling, get_billing_transport
from app.billing.entitlements import policy
from app.billing.models import WorkspaceBilling
from app.billing.webhooks import receive
from app.customers.access import Database, MutationPrincipal, Principal, customer_workspace
from app.settings import settings

router = APIRouter(tags=["customer"])
Transport = Annotated[BillingTransport, Depends(get_billing_transport)]


@router.get("/api/customer/v1/workspaces/{workspace_id}/billing")
def status(
    workspace_id: int, principal: Principal, db: Database, response: Response, transport: Transport
) -> dict[str, Any]:
    customer_workspace(db, principal.user.id, workspace_id)
    response.headers["Cache-Control"] = "no-store"
    row = db.get(WorkspaceBilling, workspace_id)
    return {
        "status": row.status if row else "unconfigured",
        "mode": "unavailable"
        if isinstance(transport, UnavailableBilling)
        else transport.mode,
        "live_verified": False,
        "period_end": row.period_end if row else None,
        "cancel_at_period_end": row.cancel_at_period_end if row else False,
        "enforcement_enabled": settings.billing_required,
    }


@router.post("/api/customer/v1/workspaces/{workspace_id}/billing/checkout")
def checkout(
    workspace_id: int,
    principal: MutationPrincipal,
    db: Database,
    response: Response,
    transport: Transport,
) -> dict[str, Any]:
    _, role = customer_workspace(db, principal.user.id, workspace_id)
    if role != "owner":
        raise HTTPException(403, "workspace owner required")
    response.headers["Cache-Control"] = "no-store"
    return service.checkout(
        db,
        workspace_id,
        policy(),
        transport,
        settings.customer_app_origin + "/app/settings",
        datetime.now(UTC),
    )


@router.post("/api/billing/stripe/events")
async def webhook(request: Request, db: Database) -> dict[str, bool]:
    if settings.billing_webhook_secret is None:
        raise HTTPException(503, "billing webhook unavailable")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 262144:
            raise HTTPException(413, "billing event too large")
    return {
        "received": receive(
            db,
            bytes(body),
            request.headers.get("Stripe-Signature", ""),
            settings.billing_webhook_secret.get_secret_value(),
            datetime.now(UTC),
        )
    }


@router.post("/api/customer/v1/workspaces/{workspace_id}/billing/management")
def management(
    workspace_id: int,
    principal: MutationPrincipal,
    db: Database,
    response: Response,
    transport: Transport,
) -> dict[str, str]:
    _, role = customer_workspace(db, principal.user.id, workspace_id)
    if role != "owner":
        raise HTTPException(403, "workspace owner required")
    response.headers["Cache-Control"] = "no-store"
    return service.management(
        db,
        workspace_id,
        transport,
        settings.billing_portal_configuration,
        settings.customer_app_origin + "/app/settings",
        datetime.now(UTC),
    )
