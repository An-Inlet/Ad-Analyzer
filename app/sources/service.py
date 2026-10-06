"""Session-bound source selection shared by TikTok and later customer-data adapters."""

import secrets
from datetime import datetime, timedelta
from typing import Any, cast
from urllib.parse import urlsplit
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.ads.enums import AdvertisingPlatform
from app.ads.repository import AdvertisingMetricsRepository
from app.ads.schemas import AdvertisingAccountCreate
from app.google_connections.security import digest
from app.imports.scope import ensure_native_integration
from app.mandates.service import workspace_lock
from app.settings import settings
from app.shopify.security import utc
from app.sources.contracts import (
    ProviderName,
    SourceAccount,
    SourceTransport,
    UnavailableSource,
    get_source_transport,
)
from app.sources.models import SourceAuthorization, SourceConnection
from app.sources.security import SourceVault
from app.workspaces.models import WorkspaceIntegration

HOSTS = {
    "tiktok_ads": {"business-api.tiktok.com", "ads.tiktok.com"},
    "klaviyo": {"www.klaviyo.com"},
    "hubspot": {"app.hubspot.com"},
    "omnisend": {"app.omnisend.com"},
}


def redirect(provider: ProviderName) -> str:
    origin = settings.customer_app_origin
    parsed = urlsplit(origin)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.path
        or parsed.query
        or parsed.fragment
        or parsed.username
    ):
        raise HTTPException(503, "customer origin unavailable")
    return origin + f"/api/customer/v1/sources/{provider}/callback"


def ready(transport: SourceTransport) -> None:
    if isinstance(transport, UnavailableSource) or transport.mode not in {
        "fixture",
        "provider_read",
    }:
        raise HTTPException(503, "source transport unavailable")
    SourceVault()


def begin(
    db: Session,
    provider: ProviderName,
    wid: int,
    sid: str,
    transport: SourceTransport,
    now: datetime,
) -> str:
    ready(transport)
    workspace_lock(db, wid)
    nonce = secrets.token_urlsafe(32)
    location = transport.authorize_url(nonce, redirect(provider))
    url = urlsplit(location)
    if url.scheme != "https" or url.hostname not in HOSTS[provider] or url.username or url.password:
        raise HTTPException(503, "source authorization unavailable")
    db.execute(delete(SourceAuthorization).where(SourceAuthorization.expires_at <= now))
    db.add(
        SourceAuthorization(
            digest=digest(nonce),
            provider=provider,
            workspace_id=wid,
            session_digest=sid,
            expires_at=now + timedelta(minutes=10),
            state="pending",
            accounts=[],
        )
    )
    db.commit()
    return location


def authorization(
    db: Session, provider: ProviderName, nonce: str, sid: str, now: datetime
) -> SourceAuthorization:
    row = db.scalar(
        select(SourceAuthorization)
        .where(
            SourceAuthorization.digest == digest(nonce),
            SourceAuthorization.provider == provider,
            SourceAuthorization.session_digest == sid,
            SourceAuthorization.expires_at > now,
        )
        .with_for_update()
    )
    if row is None:
        raise HTTPException(404, "authorization unavailable")
    return row


def finish(
    db: Session,
    provider: ProviderName,
    nonce: str,
    sid: str,
    code: str,
    transport: SourceTransport,
    now: datetime,
) -> SourceAuthorization:
    ready(transport)
    row = authorization(db, provider, nonce, sid, now)
    if row.state != "pending":
        raise HTTPException(409, "authorization already consumed")
    row.state = "exchanging"
    db.commit()
    try:
        grant = transport.exchange(code, redirect(provider))
    except Exception:
        raise HTTPException(502, "source authorization unavailable; restart connection") from None
    if grant.expires_at is not None and grant.expires_at <= now:
        raise HTTPException(409, "source consent expired")
    row = authorization(db, provider, nonce, sid, now)
    row.encrypted_grant = SourceVault().seal(
        row.workspace_id,
        provider,
        row.digest,
        {
            "access_token": grant.access_token.get_secret_value(),
            "refresh_token": grant.refresh_token.get_secret_value()
            if grant.refresh_token
            else None,
            "expires_at": grant.expires_at.isoformat() if grant.expires_at else None,
        },
    )
    row.accounts, row.state = [a.model_dump() for a in grant.accounts], "select_account"
    db.commit()
    return row


def owned(db: Session, wid: int, provider: ProviderName, cid: str) -> SourceConnection:
    workspace_lock(db, wid)
    row = db.scalar(
        select(SourceConnection)
        .where(
            SourceConnection.id == cid,
            SourceConnection.workspace_id == wid,
            SourceConnection.provider == provider,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise HTTPException(404, "source connection unavailable")
    return row


def select_account(
    db: Session, provider: ProviderName, nonce: str, sid: str, external: str, now: datetime
) -> SourceConnection:
    grant = authorization(db, provider, nonce, sid, now)
    workspace_lock(db, grant.workspace_id)
    if grant.state == "selected":
        replay = owned(db, grant.workspace_id, provider, grant.selected_id or "")
        if replay.external_id != external:
            raise HTTPException(409, "account selection already consumed")
        return replay
    if grant.state != "select_account" or not grant.encrypted_grant:
        raise HTTPException(409, "account selection unavailable")
    selected = next(
        (SourceAccount.model_validate(a) for a in grant.accounts if a["external_id"] == external),
        None,
    )
    if selected is None:
        raise HTTPException(404, "source account unavailable")
    existing = db.scalar(
        select(SourceConnection)
        .where(
            SourceConnection.workspace_id == grant.workspace_id,
            SourceConnection.provider == provider,
            SourceConnection.external_id == external,
        )
        .with_for_update()
    )
    integration = ensure_native_integration(
        db,
        workspace_id=grant.workspace_id,
        provider=provider,
        source_key="customer-source:" + provider + ":" + external,
        connection_id=existing.integration_id if existing else None,
        reauthorize=True,
    )
    account_id = None
    if provider == "tiktok_ads":
        if not external.isdigit() or not selected.currency or not selected.time_zone:
            raise HTTPException(422, "advertiser currency/time zone required")
        account = AdvertisingMetricsRepository(db).upsert_account(
            AdvertisingAccountCreate(
                workspace_id=grant.workspace_id,
                platform=AdvertisingPlatform.TIKTOK_ADS,
                external_account_id=external,
                name=selected.name,
                currency_code=selected.currency,
                time_zone=selected.time_zone,
            )
        )
        if account.connection_id not in {None, integration.id}:
            raise HTTPException(409, "advertiser owned by another connection")
        account.connection_id = integration.id
        db.flush()
        account_id = account.id
    end = now.astimezone(ZoneInfo(selected.time_zone or "UTC")).date() - timedelta(days=1)
    if existing is None:
        existing = SourceConnection(
            id=uuid4().hex,
            workspace_id=grant.workspace_id,
            integration_id=integration.id,
            provider=provider,
            account_id=account_id,
            external_id=external,
            generation=1,
            window_start=end - timedelta(days=29),
            window_end=end,
            staged={},
        )
        db.add(existing)
    else:
        existing.generation += 1
        existing.covered_from, existing.covered_through, existing.last_sync_at = None, None, None
        existing.cursor, existing.staged, existing.next_attempt_at = None, {}, None
        existing.window_start, existing.window_end = end - timedelta(days=29), end
    bundle = SourceVault().open(grant.workspace_id, provider, grant.digest, grant.encrypted_grant)
    existing.encrypted_grant = SourceVault().seal(grant.workspace_id, provider, existing.id, bundle)
    existing.status, existing.error_code = "connected", None
    grant.state, grant.selected_id, grant.encrypted_grant, grant.accounts = (
        "selected",
        existing.id,
        None,
        [],
    )
    db.commit()
    return existing


def token(row: SourceConnection, now: datetime) -> str:
    if row.status != "connected" or not row.encrypted_grant:
        raise HTTPException(409, "source reconnect required")
    bundle = SourceVault().open(row.workspace_id, row.provider, row.id, row.encrypted_grant)
    expires = bundle.get("expires_at")
    if expires is not None and utc(datetime.fromisoformat(expires)) <= now:
        raise HTTPException(409, "source refresh/reconnect required")
    return str(bundle["access_token"])


def disconnect(db: Session, row: SourceConnection) -> None:
    integration = db.get(WorkspaceIntegration, row.integration_id)
    assert integration is not None
    integration.status = "revoked"
    row.encrypted_grant, row.cursor, row.staged = None, None, {}
    row.status = "disconnected"
    row.generation += 1
    db.commit()


def view(row: SourceConnection) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": row.id,
        "workspace_id": row.workspace_id,
        "provider": row.provider,
        "connection_id": row.integration_id,
        "account_id": row.account_id,
        "status": row.status,
        "generation": row.generation,
        "last_sync_at": row.last_sync_at,
        "error_code": row.error_code,
        "mode": get_source_transport(cast(ProviderName, row.provider)).mode,
        "live_verified": False,
    }
    if row.provider == "tiktok_ads" and row.status in {"provider_error", "reconnect_required"}:
        result["status_label"] = (
            "Provider Request Rejected"
            if row.status == "provider_error"
            else "Reconnection Required"
        )
        result["next_action"] = (
            "Review provider access or configuration, then reconnect"
            if row.status == "provider_error"
            else "Reconnect this account to resume imports"
        )
    return result
