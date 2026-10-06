"""Explicit server assembly of unqualified diagnostics; no factory or financial proof."""

from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from typing import Any

import httpx
from fastapi import HTTPException
from pydantic import Field, SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ads.models import AdvertisingAccount
from app.collectors import google_native_inventory as google
from app.collectors import meta_native_inventory as meta
from app.collectors import tiktok_native_inventory as tiktok
from app.goals.schemas import StrictModel
from app.google_connections.http import GoogleHTTPRead
from app.google_connections.models import GoogleCustomerConnection
from app.google_connections.security import Vault as GoogleVault
from app.meta.models import MetaConnection
from app.meta.security import Vault as MetaVault
from app.publication import execution_mandates as mandates
from app.publication.execution_authorization import ExecutionAuthorizer
from app.publication.execution_contracts import ProviderMandateBinding
from app.settings import settings
from app.shopify.security import utc
from app.sources.models import SourceConnection
from app.sources.security import SourceVault

InventoryRequest = (
    google.GoogleNativeInventoryRequest
    | meta.MetaNativeInventoryRequest
    | tiktok.TikTokNativeInventoryRequest
)
Inventory = google.GoogleNativeInventory | meta.MetaNativeInventory | tiktok.TikTokNativeInventory


class NativeDiagnosticRequest(StrictModel):
    workspace_id: int = Field(gt=0)
    actor: str = Field(min_length=1, max_length=256)
    mandate: ProviderMandateBinding
    account_id: int = Field(gt=0)


class NativeDiagnosticService:
    """Server injects authenticated-session authorization; request never supplies it.

    Each authorization transaction is private and rolled back before HTTP. Credentials
    and the one-read access-token cache never escape this call or enter persistence.
    Explicit construction does not enable any application route or scheduled factory.
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        authorize: ExecutionAuthorizer,
        *,
        transports: Mapping[str, httpx.BaseTransport],
        google_oauth: GoogleHTTPRead | None = None,
        clock: Callable[[], datetime],
    ) -> None:
        self.sessions, self.authorize = session_factory, authorize
        self.transports, self.google_oauth, self.clock = dict(transports), google_oauth, clock

    def _snapshot(
        self, request: NativeDiagnosticRequest
    ) -> tuple[InventoryRequest, dict[str, Any]]:
        with self.sessions() as db:
            self.authorize(db, request.workspace_id, request.actor)
            _, policy = mandates.checked(
                db, request.workspace_id, request.mandate, request.actor, self.clock
            )
            selected = [a for a in policy.accounts if a.account.account_id == request.account_id]
            if len(selected) != 1:
                raise HTTPException(404, "diagnostic account unavailable")
            scope = selected[0]
            account = db.get(AdvertisingAccount, request.account_id)
            if account is None or (account.currency_code, account.time_zone) != (
                policy.currency,
                policy.time_zone,
            ):
                raise HTTPException(409, "diagnostic money context changed")
            provider = scope.account.platform
            cls: (
                type[google.GoogleNativeInventoryRequest]
                | type[meta.MetaNativeInventoryRequest]
                | type[tiktok.TikTokNativeInventoryRequest]
            )
            if provider == "google_ads":
                cls = google.GoogleNativeInventoryRequest
            elif provider == "meta_ads":
                cls = meta.MetaNativeInventoryRequest
            else:
                cls = tiktok.TikTokNativeInventoryRequest
            native_request = cls(
                account=scope,
                mandate=request.mandate,
                currency=policy.currency,
                time_zone=policy.time_zone,
                period_start=policy.starts_at,
                period_end=policy.ends_at,
            )
            # checked() has already locked/validated exact account, integration and generation.
            if provider == "google_ads":
                g = db.scalar(
                    select(GoogleCustomerConnection).where(
                        GoogleCustomerConnection.workspace_id == scope.workspace_id,
                        GoogleCustomerConnection.account_id == scope.account.account_id,
                        GoogleCustomerConnection.integration_id == scope.account.connection_id,
                    )
                )
                if g is None or not g.encrypted_grant:
                    raise HTTPException(409, "diagnostic credential unavailable")
                bundle = {
                    "refresh": GoogleVault().open(g.workspace_id, g.id, g.encrypted_grant),
                    "login": g.login_customer_id,
                }
            elif provider == "meta_ads":
                m = db.scalar(
                    select(MetaConnection).where(
                        MetaConnection.workspace_id == scope.workspace_id,
                        MetaConnection.account_id == scope.account.account_id,
                        MetaConnection.workspace_integration_id == scope.account.connection_id,
                    )
                )
                if m is None or not m.encrypted_credentials:
                    raise HTTPException(409, "diagnostic credential unavailable")
                bundle = MetaVault(settings).open(
                    m.workspace_id, m.external_account_id, m.encrypted_credentials
                )
            else:
                t = db.scalar(
                    select(SourceConnection).where(
                        SourceConnection.workspace_id == scope.workspace_id,
                        SourceConnection.account_id == scope.account.account_id,
                        SourceConnection.integration_id == scope.account.connection_id,
                        SourceConnection.provider == "tiktok_ads",
                    )
                )
                if t is None or not t.encrypted_grant:
                    raise HTTPException(409, "diagnostic credential unavailable")
                bundle = SourceVault().open(t.workspace_id, t.provider, t.id, t.encrypted_grant)
            return native_request, bundle

    def read(self, request: NativeDiagnosticRequest, now: datetime) -> Inventory:
        request = NativeDiagnosticRequest.model_validate(request.model_dump())
        original, _ = self._snapshot(request)
        provider = original.account.account.platform
        transport = self.transports.get(provider)
        if transport is None:
            raise HTTPException(503, "diagnostic transport unavailable")
        cache: tuple[str, SecretStr, datetime] | None = None

        def values(expected: InventoryRequest, current: datetime) -> dict[str, Any]:
            nonlocal cache
            fresh, bundle = self._snapshot(request)
            if fresh != original or expected != original or current < now:
                raise HTTPException(409, "diagnostic context changed")
            expires = current + timedelta(minutes=5)  # local context bound, NOT provider lifetime
            extra: dict[str, Any] = {}
            if provider == "google_ads":
                if self.google_oauth is None:
                    raise HTTPException(503, "diagnostic refresh unavailable")
                refresh = bundle["refresh"]
                if cache is None or cache[0] != refresh or cache[2] <= current:
                    access, seconds = self.google_oauth.access_context(refresh)
                    cache = (refresh, access, current + timedelta(seconds=seconds))
                token = cache[1]
                expires = min(expires, cache[2])
                extra = dict(
                    developer_token=self.google_oauth.developer, login_customer_id=bundle["login"]
                )
            else:
                raw = bundle.get("access_token")
                if not isinstance(raw, str) or not raw or len(raw) > 16384:
                    raise HTTPException(409, "diagnostic credential unavailable")
                token = SecretStr(raw)
                raw_expiry = bundle.get("expires_at")
                try:
                    if raw_expiry is not None:
                        grant_expiry = utc(datetime.fromisoformat(raw_expiry))
                        if provider == "meta_ads" and grant_expiry <= current + timedelta(
                            minutes=5
                        ):
                            raise ValueError()
                        expires = min(expires, grant_expiry)
                    elif provider == "meta_ads":
                        raise ValueError()
                except (ValueError, TypeError):
                    raise HTTPException(409, "diagnostic credential unavailable") from None
                if provider == "meta_ads":
                    extra["app_secret"] = settings.meta_client_secret
            # OAuth may block. Recheck exact current authorization after it, outside its session.
            after, after_bundle = self._snapshot(request)
            if after != original or after_bundle != bundle or expires <= self.clock():
                raise HTTPException(409, "diagnostic context changed")
            return dict(
                scope=original.account,
                request_digest=original.digest(),
                access_token=token,
                expires_at=expires,
                **extra,
            )

        result: Inventory
        if isinstance(original, google.GoogleNativeInventoryRequest):
            result = google.GoogleNativeInventoryHTTP(
                lambda r, n: google.GoogleNativeInventoryContext(**values(r, n)),
                transport=transport,
                clock=self.clock,
            )(original, now)
        elif isinstance(original, meta.MetaNativeInventoryRequest):
            result = meta.MetaNativeInventoryHTTP(
                lambda r, n: meta.MetaNativeInventoryContext(**values(r, n)),
                transport=transport,
                clock=self.clock,
            )(original, now)
        else:
            result = tiktok.TikTokNativeInventoryHTTP(
                lambda r, n: tiktok.TikTokNativeInventoryContext(**values(r, n)),
                transport=transport,
                clock=self.clock,
            )(original, now)
        final, _ = self._snapshot(request)
        if (
            final != original
            or result.request != original
            or not (now <= result.observed_at <= self.clock() < result.expires_at)
        ):
            raise HTTPException(409, "diagnostic result expired or changed")
        return result
