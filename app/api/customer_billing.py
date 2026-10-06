import re
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.billing import repository, service
from app.billing.contracts import (
    BillingManagementTransport,
    BillingTransport,
    UnavailableBilling,
    get_billing_transport,
)
from app.billing.entitlements import policy
from app.billing.offers import configured_offer
from app.billing.scope import LEGACY_TEST_SCOPE, BillingScopeV1, configured_scope
from app.billing.webhooks import receive
from app.customers.access import (
    Database,
    MutationPrincipal,
    Principal,
    Provider,
    customer_workspace,
    lock_customer_mutation,
)
from app.settings import settings
from app.shopify.security import utc

router = APIRouter(tags=["customer"])
Transport = Annotated[BillingTransport, Depends(get_billing_transport)]


def portal_configuration() -> str:
    if (
        settings.billing_provider_mode in {"stripe_test", "stripe_live"}
        and settings.billing_offer_profile is not None
    ):
        try:
            return configured_offer().portal.configuration_id
        except ValueError:
            return ""
    return settings.billing_portal_configuration


@router.get("/api/customer/v1/workspaces/{workspace_id}/billing")
def status(
    workspace_id: int, principal: Principal, db: Database, response: Response, transport: Transport
) -> dict[str, Any]:
    _, role = customer_workspace(db, principal.user.id, workspace_id)
    response.headers["Cache-Control"] = "no-store"
    scope: BillingScopeV1 | None = repository.transport_scope(transport)
    if settings.app_env == "production" and isinstance(transport, UnavailableBilling):
        # A disabled production factory must never present legacy test evidence.
        try:
            candidate = configured_scope()
            scope = candidate if candidate.environment == "live" else None
        except ValueError:
            scope = None
    row = repository.billing(db, workspace_id, scope) if scope is not None else None
    try:
        configured_policy = policy()
    except HTTPException:
        configured_policy = None
    available = not isinstance(transport, UnavailableBilling) and transport.mode in {
        "stripe_test",
        "stripe_live",
    }
    owner = role == "owner"
    existing = row is not None and row.status in {
        "active",
        "trialing",
        "past_due",
        "unpaid",
        "paused",
        "incomplete",
    }
    verified = bool(
        row
        and configured_policy
        and row.verified_at
        and not row.error_code
        and datetime.now(UTC) - timedelta(seconds=configured_policy.max_snapshot_age_seconds)
        <= utc(row.verified_at)
        <= datetime.now(UTC)
    )
    return {
        "can_checkout": owner and available and configured_policy is not None and not existing,
        "can_manage": bool(
            owner
            and available
            and row
            and row.customer_id
            and isinstance(transport, BillingManagementTransport)
            and re.fullmatch(r"bpc_[A-Za-z0-9_]{1,128}", portal_configuration())
        ),
        "checkout_pending": bool(row and row.checkout_key and not row.subscription_id),
        "verification_current": verified,
        "needs_attention": bool(row and row.error_code),
        "status": row.status if row else "unconfigured",
        "mode": "unavailable" if isinstance(transport, UnavailableBilling) else transport.mode,
        "live_verified": False,
        "scope": scope.model_dump() if scope is not None else None,
        "period_end": row.period_end if row else None,
        "cancel_at_period_end": row.cancel_at_period_end if row else False,
        "enforcement_enabled": (
            settings.app_env == "production"
            or settings.billing_provider_mode == "stripe_live"
            or settings.billing_required
        ),
    }


@router.post("/api/customer/v1/workspaces/{workspace_id}/billing/checkout")
def checkout(
    workspace_id: int,
    principal: MutationPrincipal,
    db: Database,
    response: Response,
    transport: Transport,
    identity: Provider,
) -> dict[str, Any]:
    _, role = customer_workspace(db, principal.user.id, workspace_id)
    if role != "owner":
        raise HTTPException(403, "workspace owner required")
    response.headers["Cache-Control"] = "no-store"
    result = service.checkout(
        db,
        workspace_id,
        policy(),
        transport,
        settings.customer_app_origin + f"/app/settings?workspace={workspace_id}&billing_return=1",
        datetime.now(UTC),
    )
    lock_customer_mutation(db, principal, workspace_id, identity)
    if customer_workspace(db, principal.user.id, workspace_id)[1] != "owner":
        raise HTTPException(403, "workspace owner required")
    return result


@router.post("/api/billing/stripe/events")
async def webhook(request: Request, db: Database) -> dict[str, bool]:
    # Historical endpoint is permanently test-only, even after deployment switches modes.
    scope = LEGACY_TEST_SCOPE
    if settings.billing_provider_mode == "stripe_test":
        try:
            scope = configured_scope()
        except ValueError:
            raise HTTPException(503, "billing webhook unavailable") from None
    return await receive_webhook(request, db, scope, live=False)


@router.post("/api/billing/stripe/{environment}/events")
async def scoped_webhook(environment: str, request: Request, db: Database) -> dict[str, bool]:
    try:
        if environment not in {"test", "live"}:
            raise ValueError
        scope = BillingScopeV1(
            environment="live" if environment == "live" else "test",
            merchant_account_id=settings.billing_merchant_account_id,
        )
        if not scope.qualified:
            raise ValueError
    except ValueError:
        raise HTTPException(503, "billing webhook unavailable") from None
    # Receipt-only lane remains available with its dedicated secret when forward
    # billing is disabled. It never grants entitlement or calls the provider.
    return await receive_webhook(request, db, scope, live=environment == "live")


async def receive_webhook(
    request: Request, db: Database, scope: BillingScopeV1, *, live: bool
) -> dict[str, bool]:
    secret = settings.billing_live_webhook_secret if live else settings.billing_webhook_secret
    if secret is None:
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
            secret.get_secret_value(),
            datetime.now(UTC),
            scope=scope,
        )
    }


@router.post("/api/customer/v1/workspaces/{workspace_id}/billing/management")
def management(
    workspace_id: int,
    principal: MutationPrincipal,
    db: Database,
    response: Response,
    transport: Transport,
    identity: Provider,
) -> dict[str, str]:
    _, role = customer_workspace(db, principal.user.id, workspace_id)
    if role != "owner":
        raise HTTPException(403, "workspace owner required")
    response.headers["Cache-Control"] = "no-store"
    result = service.management(
        db,
        workspace_id,
        transport,
        portal_configuration(),
        settings.customer_app_origin + f"/app/settings?workspace={workspace_id}&billing_return=1",
        datetime.now(UTC),
    )
    lock_customer_mutation(db, principal, workspace_id, identity)
    if customer_workspace(db, principal.user.id, workspace_id)[1] != "owner":
        raise HTTPException(403, "workspace owner required")
    return result
