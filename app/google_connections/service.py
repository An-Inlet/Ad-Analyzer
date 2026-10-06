"""Scoped customer authorization and resumable read imports."""

import secrets
from collections.abc import Callable
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode, urlsplit
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.ads.enums import AdvertisingPlatform, JobRunStatus, MetricEntityType
from app.ads.models import Campaign, DailyMetric, JobRun
from app.ads.repository import AdvertisingMetricsRepository
from app.ads.schemas import AdvertisingAccountCreate, CampaignCreate, DailyMetricCreate
from app.google_connections.contracts import (
    Account,
    GoogleAuthorizationUnavailable,
    GoogleReadTransport,
    Page,
    UnavailableTransport,
    get_transport,
)
from app.google_connections.models import (
    GoogleAuthorization,
    GoogleCustomerConnection,
    GoogleImportCompletion,
)
from app.google_connections.security import Vault, digest
from app.imports.scope import (
    AdvertisingImportScope,
    ensure_native_integration,
    validate_advertising_scope,
)
from app.mandates.service import workspace_lock
from app.settings import settings
from app.shopify.security import utc
from app.workspaces.models import WorkspaceIntegration

PLATFORM = AdvertisingPlatform.GOOGLE_ADS


class GoogleReadUnavailable(HTTPException):
    """Current transient read attempt failed; persisted pages remain retryable."""

    def __init__(self) -> None:
        super().__init__(502, "Google read unavailable")


def redirect_uri() -> str:
    origin = settings.customer_app_origin
    url = urlsplit(origin)
    if (
        url.scheme != "https"
        or not url.hostname
        or url.path
        or url.query
        or url.fragment
        or url.username
    ):
        raise HTTPException(503, "customer origin unavailable")
    return origin + "/api/customer/v1/google/callback"


def ready(transport: GoogleReadTransport) -> None:
    if isinstance(transport, UnavailableTransport) or transport.mode not in {
        "fixture",
        "google_read",
    }:
        raise HTTPException(503, "Google customer transport unavailable")
    Vault()


def start(db: Session, wid: int, sid: str, now: datetime, transport: GoogleReadTransport) -> str:
    ready(transport)
    workspace_lock(db, wid)
    db.execute(
        delete(GoogleAuthorization)
        .execution_options(synchronize_session="fetch")
        .where(GoogleAuthorization.expires_at <= now)
    )
    db.execute(
        delete(GoogleAuthorization).where(
            GoogleAuthorization.workspace_id == wid,
            GoogleAuthorization.session_digest == sid,
            GoogleAuthorization.state != "selected",
        )
    )
    nonce = secrets.token_urlsafe(32)
    db.add(
        GoogleAuthorization(
            digest=digest(nonce),
            workspace_id=wid,
            session_digest=sid,
            expires_at=now + timedelta(minutes=10),
            state="pending",
            accounts=[],
        )
    )
    db.commit()
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(
        {
            "client_id": settings.google_customer_client_id,
            "redirect_uri": redirect_uri(),
            "response_type": "code",
            "scope": "https://www.googleapis.com/auth/adwords",
            "access_type": "offline",
            "prompt": "consent",
            "state": nonce,
        }
    )


def authorization(
    db: Session, nonce: str, sid: str, now: datetime, *, lock: bool = True
) -> GoogleAuthorization:
    peek = db.get(GoogleAuthorization, digest(nonce), populate_existing=True)
    if peek is None or peek.session_digest != sid:
        raise HTTPException(404, "authorization unavailable")
    if lock:
        workspace_lock(db, peek.workspace_id)
    query = select(GoogleAuthorization).where(GoogleAuthorization.digest == digest(nonce))
    if lock:
        query = query.with_for_update()
    row = db.scalar(query.execution_options(populate_existing=True))
    if row is None or row.session_digest != sid or utc(row.expires_at) <= now:
        raise HTTPException(404, "authorization unavailable")
    return row


def finish(
    db: Session,
    nonce: str,
    sid: str,
    code: str,
    now: datetime,
    transport: GoogleReadTransport,
    *,
    before_persist: Callable[[], None] | None = None,
) -> GoogleAuthorization:
    ready(transport)
    row = authorization(db, nonce, sid, now)
    if row.state != "pending":
        raise HTTPException(409, "authorization already consumed")
    row.state = "exchanging"
    db.commit()  # Single-use before exchange; uncertainty requires fresh consent.
    try:
        grant = transport.exchange(code, redirect_uri())
    except Exception:
        raise HTTPException(502, "Google authorization unavailable; restart connection") from None
    if before_persist is not None:
        before_persist()
    row = authorization(db, nonce, sid, now)
    row.encrypted_grant = Vault().seal(
        row.workspace_id, row.digest, grant.refresh_token.get_secret_value()
    )
    row.accounts = [a.model_dump() for a in grant.accounts if not a.manager]
    row.state = "select_account"
    db.commit()
    return row


def choose(
    db: Session, nonce: str, sid: str, external_id: str, now: datetime
) -> GoogleCustomerConnection:
    # Consistent lock order with imports/disconnect: workspace before connection.
    reference = authorization(db, nonce, sid, now, lock=False)
    wid = reference.workspace_id
    workspace_lock(db, wid)
    row = authorization(db, nonce, sid, now)
    if row.state == "selected":
        replay = owned(db, wid, row.selected_connection_id or "")
        if replay.external_account_id != external_id:
            raise HTTPException(409, "account selection already consumed")
        return replay
    if row.state != "select_account" or row.encrypted_grant is None:
        raise HTTPException(409, "account selection unavailable")
    selected = next(
        (Account.model_validate(a) for a in row.accounts if a["external_id"] == external_id), None
    )
    if selected is None or selected.manager:
        raise HTTPException(404, "account unavailable")
    existing = db.scalar(
        select(GoogleCustomerConnection)
        .where(
            GoogleCustomerConnection.workspace_id == wid,
            GoogleCustomerConnection.external_account_id == external_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    token = Vault().open(wid, row.digest, row.encrypted_grant)
    integration = ensure_native_integration(
        db,
        workspace_id=wid,
        provider="google_ads",
        source_key="google-customer:" + external_id,
        connection_id=existing.integration_id if existing else None,
        reauthorize=True,
    )
    repository = AdvertisingMetricsRepository(db)
    account = repository.upsert_account(
        AdvertisingAccountCreate(
            workspace_id=wid,
            platform=PLATFORM,
            external_account_id=external_id,
            name=selected.name,
            currency_code=selected.currency,
            time_zone=selected.time_zone,
        )
    )
    if account.connection_id not in (None, integration.id):
        raise HTTPException(409, "account bound to another connection")
    account.connection_id = integration.id
    db.flush()
    end = now.astimezone(ZoneInfo(selected.time_zone)).date() - timedelta(days=1)
    if existing is None:
        existing = GoogleCustomerConnection(
            id=uuid4().hex,
            workspace_id=wid,
            integration_id=integration.id,
            account_id=account.id,
            external_account_id=external_id,
            backfill_through=end,
            history_floor=end - timedelta(days=89),
            phase="recent",
            window_start=end - timedelta(days=6),
            window_end=end,
            generation=1,
            staged={},
        )
        db.add(existing)
    else:
        discard_pending_analysis(db, existing)
        existing.generation += 1
        existing.cursor, existing.staged = None, {}
        existing.window_start, existing.window_end = end - timedelta(days=6), end
        existing.backfill_through, existing.history_floor, existing.phase = (
            end,
            end - timedelta(days=89),
            "recent",
        )
    existing.login_customer_id = selected.login_customer_id
    existing.encrypted_grant = Vault().seal(wid, existing.id, token)
    existing.status, existing.error_code, existing.next_attempt_at = "connected", None, None
    row.state, row.selected_connection_id, row.encrypted_grant = "selected", existing.id, None
    row.accounts = []
    db.commit()
    return existing


def owned(db: Session, wid: int, cid: str) -> GoogleCustomerConnection:
    workspace_lock(db, wid)
    row = db.scalar(
        select(GoogleCustomerConnection)
        .where(GoogleCustomerConnection.id == cid, GoogleCustomerConnection.workspace_id == wid)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise HTTPException(404, "connection unavailable")
    return row


def discard_pending_analysis(db: Session, row: GoogleCustomerConnection) -> None:
    """Caller holds workspace/connection lock; discard only this ownership scope."""
    db.execute(
        delete(GoogleImportCompletion).where(
            GoogleImportCompletion.state == "pending",
            GoogleImportCompletion.job_id.in_(
                select(JobRun.id).where(
                    JobRun.workspace_id == row.workspace_id,
                    JobRun.connection_id == row.integration_id,
                    JobRun.account_id == row.account_id,
                )
            ),
        )
    )


def disconnect(db: Session, row: GoogleCustomerConnection) -> None:
    # Refresh under the same lock even for callers holding a stale ORM instance.
    row = owned(db, row.workspace_id, row.id)
    integration = db.get(WorkspaceIntegration, row.integration_id)
    assert integration is not None
    discard_pending_analysis(db, row)
    integration.status = "revoked"
    row.status, row.encrypted_grant, row.cursor, row.staged = "disconnected", None, None, {}
    row.generation += 1
    row.next_attempt_at, row.error_code = None, None
    db.commit()


def tick(
    db: Session, wid: int, cid: str, generation: int, transport: GoogleReadTransport, now: datetime
) -> int | None:
    from app.billing.entitlements import paid_work

    paid_work(db, wid, now)
    ready(transport)
    row = owned(db, wid, cid)
    if row.generation != generation or row.status != "connected" or not row.encrypted_grant:
        raise HTTPException(409, "connection unavailable or replaced")
    scope = AdvertisingImportScope(wid, row.integration_id, row.account_id, PLATFORM)
    account, _ = validate_advertising_scope(db, scope)
    if row.window_start > row.window_end:
        end = now.astimezone(ZoneInfo(account.time_zone or "UTC")).date() - timedelta(days=1)
        if row.window_start > end:
            # Caught up: revisit delayed attribution newest-first in bounded windows.
            # The snapshot end stays fixed while the refresh cycle is in progress.
            if row.phase != "current":
                raise HTTPException(409, "invalid import window")
            row.phase = "refresh"
            row.backfill_through = end
            row.window_start = max(row.history_floor, end - timedelta(days=6))
            row.window_end = end
        else:
            row.window_end = min(end, row.window_start + timedelta(days=6))
    token = Vault().open(wid, cid, row.encrypted_grant)
    try:
        page = transport.page(
            token,
            row.external_account_id,
            row.window_start,
            row.window_end,
            row.cursor,
            row.login_customer_id,
        )
    except GoogleAuthorizationUnavailable:
        # The workspace/connection lock is held across the read; obsolete queued
        # generations are rejected before any IO and cannot invalidate new consent.
        discard_pending_analysis(db, row)
        row.status, row.error_code = "reconnect_required", "authorization_unavailable"
        row.encrypted_grant, row.cursor, row.staged = None, None, {}
        row.generation += 1
        row.next_attempt_at = None
        db.commit()
        raise HTTPException(409, "Google connection requires fresh consent") from None
    except Exception:
        row.error_code = "read_unavailable"
        row.next_attempt_at = now + timedelta(minutes=5)
        db.commit()
        raise GoogleReadUnavailable() from None
    if page.external_account_id != row.external_account_id:
        raise HTTPException(409, "collector ownership mismatch")
    staged = dict(row.staged)
    seen = list(staged.get("cursors", []))
    if page.next_cursor is not None and (
        page.next_cursor == row.cursor or page.next_cursor in seen
    ):
        raise HTTPException(409, "repeated collector cursor")
    pages = list(staged.get("pages", [])) + [page.model_dump(mode="json")]
    if len(pages) > 100 or sum(len(p["metrics"]) + len(p["campaigns"]) for p in pages) > 50_000:
        raise HTTPException(409, "import window exceeds bounded capacity")
    if page.next_cursor is not None:
        row.staged = {"pages": pages, "cursors": seen + [page.next_cursor]}
        row.cursor = page.next_cursor
        row.next_attempt_at = now
        db.commit()
        return None
    repo = AdvertisingMetricsRepository(db)
    repo.scope = scope
    campaigns: dict[str, Any] = {}
    metrics: dict[tuple[str, Any], Any] = {}
    for parsed in (Page.model_validate(p) for p in pages):
        for c in parsed.campaigns:
            prior = campaigns.get(c.external_id)
            if prior is not None and prior != c:
                raise HTTPException(409, "conflicting campaign pages")
            campaigns[c.external_id] = c
        for metric in parsed.metrics:
            key = (metric.campaign_external_id, metric.day)
            if not row.window_start <= metric.day <= row.window_end or (
                key in metrics and metrics[key] != metric
            ):
                raise HTTPException(409, "conflicting metric window")
            metrics[key] = metric
    mapped = {
        key: repo.upsert_campaign(
            CampaignCreate(
                account_id=row.account_id,
                platform=PLATFORM,
                external_campaign_id=key,
                name=c.name,
                status=c.status,
                channel_type=c.channel,
            )
        )
        for key, c in campaigns.items()
    }
    if any(key[0] not in mapped for key in metrics):
        raise HTTPException(409, "metric campaign unavailable")
    db.execute(
        delete(DailyMetric).where(
            DailyMetric.campaign_id.in_(
                select(Campaign.id).where(Campaign.account_id == row.account_id)
            ),
            DailyMetric.entity_type == MetricEntityType.CAMPAIGN,
            DailyMetric.metric_date >= row.window_start,
            DailyMetric.metric_date <= row.window_end,
        )
    )
    for (external, day), metric in metrics.items():
        campaign = mapped[external]
        repo.upsert_daily_metric(
            DailyMetricCreate(
                platform=PLATFORM,
                metric_date=day,
                entity_type=MetricEntityType.CAMPAIGN,
                entity_id=campaign.id,
                campaign_id=campaign.id,
                impressions=metric.impressions,
                clicks=metric.clicks,
                cost_micros=metric.cost_micros,
                conversions=Decimal(metric.conversions),
                conversion_value_micros=metric.conversion_value_micros,
            )
        )
    job = repo.create_job_run(
        platform=PLATFORM,
        job_name="google_customer_fixture_sync",
        status=JobRunStatus.SUCCEEDED,
        account_id=row.account_id,
        workspace_id=wid,
        connection_id=row.integration_id,
    )
    repo.finish_job_run(job, status=JobRunStatus.SUCCEEDED, records_processed=len(metrics))
    row.last_sync_at, row.error_code, row.cursor, row.staged = now, None, None, {}
    if row.phase in {"recent", "history"} and row.window_start > row.history_floor:
        row.window_end = row.window_start - timedelta(days=1)
        row.window_start = max(row.history_floor, row.window_end - timedelta(days=6))
        row.phase = "history"
    elif row.phase in {"recent", "history"}:
        row.phase = "current"
        row.window_start, row.window_end = (
            row.backfill_through + timedelta(days=1),
            row.backfill_through,
        )
    elif row.phase == "refresh":
        floor = max(row.history_floor, row.backfill_through - timedelta(days=89))
        if row.window_start > floor:
            row.window_end = row.window_start - timedelta(days=1)
            row.window_start = max(floor, row.window_end - timedelta(days=6))
        else:
            row.phase = "current"
            row.window_start = row.backfill_through + timedelta(days=1)
            row.window_end = row.backfill_through
    else:
        row.window_start = row.window_end + timedelta(days=1)
    row.next_attempt_at = now if row.phase != "current" else now + timedelta(hours=1)
    db.flush()
    db.add(GoogleImportCompletion(job_id=job.id, state="pending"))
    db.commit()
    return job.id


def view(row: GoogleCustomerConnection) -> dict[str, Any]:
    return {
        "id": row.id,
        "workspace_id": row.workspace_id,
        "account_id": row.account_id,
        "external_account_id": row.external_account_id,
        "connection_id": row.integration_id,
        "status": row.status,
        "generation": row.generation,
        "window_start": row.window_start,
        "window_end": row.window_end,
        "last_sync_at": row.last_sync_at,
        "error_code": row.error_code,
        "phase": row.phase,
        "mode": get_transport().mode,
        "live_verified": False,
    }
