"""Customer source setup; unconfigured transports fail closed."""

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import FileResponse
from pydantic import Field
from sqlalchemy import select

from app.customers.access import (
    Database,
    MutationPrincipal,
    Principal,
    Provider,
    customer_workspace,
    guard_customer_mutation,
)
from app.customers.oauth import callback_relay
from app.goals.schemas import StrictModel
from app.settings import settings
from app.sources import service as s
from app.sources.contracts import ProviderName, SourceTransport, get_source_transport
from app.sources.models import SourceConnection

router = APIRouter(prefix="/api/customer/v1", tags=["customer"])
Transport = Annotated[SourceTransport, Depends(get_source_transport)]


class Callback(StrictModel):
    state: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")
    code: str = Field(min_length=1, max_length=4096)


class Selection(StrictModel):
    state: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")
    external_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")


def access(db: Database, user: str, wid: int, response: Response, write: bool) -> None:
    _, role = customer_workspace(db, user, wid)
    if write and role not in {"owner", "admin"}:
        raise HTTPException(403, "insufficient role")
    response.headers["Cache-Control"] = "no-store"


@router.post("/workspaces/{workspace_id}/sources/{provider}/authorize")
def authorize(
    workspace_id: int,
    provider: ProviderName,
    principal: MutationPrincipal,
    db: Database,
    response: Response,
    transport: Transport,
) -> dict[str, Any]:
    guard_customer_mutation(db, principal, workspace_id)
    access(db, principal.user.id, workspace_id, response, True)
    return {
        "authorization_url": s.begin(
            db, provider, workspace_id, principal.session.digest, transport, datetime.now(UTC)
        ),
        "mode": transport.mode,
    }


@router.get("/sources/{provider}/callback")
def browser_callback(provider: ProviderName) -> Response:
    if provider == "tiktok_ads":
        return FileResponse(
            Path(__file__).parents[1] / "portal" / "static" / "tiktok-callback.html",
            media_type="text/html",
            headers={
                "Cache-Control": "no-store",
                "Referrer-Policy": "no-referrer",
                "X-Frame-Options": "DENY",
                "Content-Security-Policy": (
                    "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
                    "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
                ),
            },
        )
    return callback_relay()


@router.post("/sources/{provider}/callback")
def callback(
    provider: ProviderName,
    body: Callback,
    principal: MutationPrincipal,
    db: Database,
    response: Response,
    transport: Transport,
    identity: Provider,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    pending = s.authorization(db, provider, body.state, principal.session.digest, now, lock=False)
    wid = pending.workspace_id

    def guard() -> None:
        guard_customer_mutation(db, principal, wid)
        identity.check_active(principal.user.subject, principal.session.authenticated_at)

    guard()
    access(db, principal.user.id, wid, response, True)
    pending = s.finish(
        db,
        provider,
        body.state,
        principal.session.digest,
        body.code,
        transport,
        now,
        before_persist=guard,
        clock=lambda: datetime.now(UTC),
    )
    return {
        "workspace_id": pending.workspace_id,
        "accounts": pending.accounts,
        "live_verified": False,
        "mode": transport.mode,
    }


@router.post("/workspaces/{workspace_id}/sources/{provider}/select")
def select_account(
    workspace_id: int,
    provider: ProviderName,
    body: Selection,
    principal: MutationPrincipal,
    db: Database,
    response: Response,
) -> dict[str, Any]:
    guard_customer_mutation(db, principal, workspace_id)
    access(db, principal.user.id, workspace_id, response, True)
    now = datetime.now(UTC)
    pending = s.authorization(db, provider, body.state, principal.session.digest, now)
    if pending.workspace_id != workspace_id:
        raise HTTPException(404, "authorization unavailable")
    return s.view(
        s.select_account(db, provider, body.state, principal.session.digest, body.external_id, now)
    )


@router.get("/workspaces/{workspace_id}/sources/{provider}")
def listing(
    workspace_id: int,
    provider: ProviderName,
    principal: Principal,
    db: Database,
    response: Response,
) -> list[dict[str, Any]]:
    access(db, principal.user.id, workspace_id, response, False)
    return [
        s.view(row)
        for row in db.scalars(
            select(SourceConnection).where(
                SourceConnection.workspace_id == workspace_id, SourceConnection.provider == provider
            )
        )
    ]


@router.delete("/workspaces/{workspace_id}/sources/{provider}/{connection_id}")
def disconnect(
    workspace_id: int,
    provider: ProviderName,
    connection_id: str,
    principal: MutationPrincipal,
    db: Database,
    response: Response,
) -> dict[str, Any]:
    guard_customer_mutation(db, principal, workspace_id)
    access(db, principal.user.id, workspace_id, response, True)
    row = s.owned(db, workspace_id, provider, connection_id)
    s.disconnect(db, row)
    return s.view(row)


@router.get("/workspaces/{workspace_id}/sources/tiktok_ads/{connection_id}/report")
def tiktok_report(
    workspace_id: int,
    connection_id: str,
    start: Annotated[date, Query()],
    end: Annotated[date, Query()],
    principal: Principal,
    db: Database,
    response: Response,
) -> dict[str, Any]:
    from app.ads.enums import AdvertisingPlatform
    from app.api.repository import ReadOnlyAdsRepository
    from app.imports.scope import (
        AdvertisingImportScope,
        ImportScopeError,
        validate_advertising_scope,
    )

    access(db, principal.user.id, workspace_id, response, False)
    row = s.owned(db, workspace_id, "tiktok_ads", connection_id)
    if row.account_id is None:
        raise HTTPException(404, "advertiser unavailable")
    if not 0 <= (end - start).days <= 90:
        raise HTTPException(422, "invalid reporting window")
    try:
        validate_advertising_scope(
            db,
            AdvertisingImportScope(
                workspace_id, row.integration_id, row.account_id, AdvertisingPlatform.TIKTOK_ADS
            ),
        )
    except ImportScopeError:
        raise HTTPException(404, "advertiser unavailable") from None
    totals = ReadOnlyAdsRepository(db).account_metric_totals(row.account_id, start, end)
    covered = bool(
        row.covered_from
        and row.covered_through
        and row.covered_from <= start <= end <= row.covered_through
    )
    return {
        "account_id": row.account_id,
        "spend_micros": totals["cost_micros"] if row.last_sync_at and covered else None,
        "conversions": None,
        "conversion_value_micros": None,
        "conversion_semantics": "not_yet_qualified",
        "last_sync_at": row.last_sync_at,
        "mode": s.view(row)["mode"],
        "live_verified": False,
    }


@router.get("/workspaces/{workspace_id}/sources/tiktok_ads/setup")
def tiktok_setup(
    workspace_id: int, principal: Principal, db: Database, response: Response
) -> dict[str, Any]:
    _, role = customer_workspace(db, principal.user.id, workspace_id)
    response.headers["Cache-Control"] = "no-store"
    try:
        s.ready(get_source_transport("tiktok_ads"), "tiktok_ads")
        callback = s.redirect("tiktok_ads")
        enabled = bool(settings.tiktok_app_id)
    except HTTPException:
        callback, enabled = "", False
    return {
        "enabled": enabled,
        "can_manage": role in {"owner", "admin"},
        "app_id": settings.tiktok_app_id if enabled else "",
        "redirect_uri": callback,
        "authorization_endpoint": "https://business-api.tiktok.com/portal/auth",
    }
