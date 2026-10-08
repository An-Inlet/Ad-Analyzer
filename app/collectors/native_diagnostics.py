"""Explicit server assembly of unqualified diagnostics; no factory or financial proof."""

from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from typing import Any

import httpx
from fastapi import HTTPException
from pydantic import AwareDatetime, Field, SecretStr, TypeAdapter, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ads.models import AdvertisingAccount
from app.automation.catalog import AutomationControlKey
from app.automation.service import AutomationControlService
from app.billing.entitlements import paid_work
from app.collectors import google_native_inventory as google
from app.collectors import meta_native_inventory as meta
from app.collectors import tiktok_native_inventory as tiktok
from app.collectors.account_diagnostic_contracts import validate_observation_period
from app.goals.schemas import StrictModel
from app.google_connections.http import GoogleHTTPRead
from app.google_connections.models import GoogleCustomerConnection
from app.google_connections.security import Vault as GoogleVault
from app.meta.models import MetaConnection
from app.meta.security import Vault as MetaVault
from app.planning_catalog.metadata_contracts import PlanningMetadataV1
from app.publication import customer_intents
from app.publication import execution_mandates as mandates
from app.publication.execution_authorization import ExecutionAuthorizer
from app.publication.execution_contracts import ExecutionAccount, ProviderMandateBinding
from app.settings import settings
from app.shopify.security import utc
from app.sources.models import SourceConnection
from app.sources.security import SourceVault

InventoryRequest = (
    google.GoogleInventoryRequest | meta.MetaInventoryRequest | tiktok.TikTokInventoryRequest
)
Inventory = google.GoogleNativeInventory | meta.MetaNativeInventory | tiktok.TikTokNativeInventory


class NativeDiagnosticRequest(StrictModel):
    workspace_id: int = Field(gt=0)
    actor: str = Field(min_length=1, max_length=256)
    mandate: ProviderMandateBinding
    account_id: int = Field(gt=0)


class AccountDiagnosticRequest(StrictModel):
    expected_account: ExecutionAccount
    workspace_id: int = Field(strict=True, gt=0)
    actor: str = Field(min_length=1, max_length=256)
    account_id: int = Field(strict=True, gt=0)
    starts_at: AwareDatetime
    ends_at: AwareDatetime

    @model_validator(mode="after")
    def bounded(self) -> "AccountDiagnosticRequest":
        validate_observation_period(self.starts_at, self.ends_at)
        return self


DiagnosticRequest = NativeDiagnosticRequest | AccountDiagnosticRequest


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

    def _snapshot(self, request: DiagnosticRequest) -> tuple[InventoryRequest, dict[str, Any]]:
        with self.sessions() as db:
            self.authorize(db, request.workspace_id, request.actor)
            native_request: InventoryRequest
            if isinstance(request, AccountDiagnosticRequest):
                if not timedelta(0) < request.ends_at - request.starts_at <= timedelta(days=366):
                    raise HTTPException(422, "diagnostic period exceeds bound")
                if request.ends_at > self.clock():
                    raise HTTPException(422, "diagnostic period must not be in the future")
                if not AutomationControlService(db).master_enabled(
                    AutomationControlKey.ALL_DATA_SYNCS
                ):
                    raise HTTPException(409, "diagnostic reads paused")
                paid_work(db, request.workspace_id, self.clock())
                scope = customer_intents.account(db, request.workspace_id, request.account_id)
                if scope != request.expected_account:
                    raise HTTPException(409, "diagnostic account changed")
                account = db.get(AdvertisingAccount, request.account_id)
                if account is None:
                    raise HTTPException(404, "diagnostic account unavailable")
                provider = scope.account.platform
                observation_type: (
                    type[google.GoogleAccountObservationRequestV2]
                    | type[meta.MetaAccountObservationRequestV2]
                    | type[tiktok.TikTokAccountObservationRequestV2]
                )
                if provider == "google_ads":
                    observation_type = google.GoogleAccountObservationRequestV2
                elif provider == "meta_ads":
                    observation_type = meta.MetaAccountObservationRequestV2
                else:
                    observation_type = tiktok.TikTokAccountObservationRequestV2
                native_request = observation_type(
                    account=scope,
                    currency=account.currency_code,
                    time_zone=account.time_zone,
                    period_start=request.starts_at,
                    period_end=request.ends_at,
                )
                self.authorize(db, request.workspace_id, request.actor)
                paid_work(db, request.workspace_id, self.clock())
            else:
                _, policy = mandates.checked(
                    db, request.workspace_id, request.mandate, request.actor, self.clock
                )
                selected = [
                    a for a in policy.accounts if a.account.account_id == request.account_id
                ]
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

    def read(self, request: DiagnosticRequest, now: datetime) -> Inventory:
        return self._read_operation(request, now, None)[0]

    def read_catalog(
        self, request: AccountDiagnosticRequest, now: datetime
    ) -> tuple[Inventory, PlanningMetadataV1]:
        from app.planning_catalog.metadata_http import read_metadata

        result, metadata = self._read_operation(
            request,
            now,
            lambda inventory, transport, values: read_metadata(
                inventory, transport, values, self.clock
            ),
        )
        assert metadata is not None
        return result, metadata

    def _read_operation(
        self,
        request: DiagnosticRequest,
        now: datetime,
        metadata_reader: Callable[
            [
                Inventory,
                httpx.BaseTransport,
                Callable[[InventoryRequest, datetime], dict[str, Any]],
            ],
            PlanningMetadataV1,
        ]
        | None,
    ) -> tuple[Inventory, PlanningMetadataV1 | None]:
        request = TypeAdapter(DiagnosticRequest).validate_python(request.model_dump())
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
        if isinstance(
            original,
            (google.GoogleNativeInventoryRequest, google.GoogleAccountObservationRequestV2),
        ):
            result = google.GoogleNativeInventoryHTTP(
                lambda r, n: google.GoogleNativeInventoryContext(**values(r, n)),
                transport=transport,
                clock=self.clock,
            )(original, now)
        elif isinstance(
            original, (meta.MetaNativeInventoryRequest, meta.MetaAccountObservationRequestV2)
        ):
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
        metadata = None
        if metadata_reader is not None:
            if not isinstance(request, AccountDiagnosticRequest):
                raise HTTPException(409, "planning read requires owned account observation")
            metadata = metadata_reader(result, transport, values)
            from app.planning_catalog.metadata_binding import validate_bound_metadata

            metadata = validate_bound_metadata(result, metadata, self.clock())
            if (
                metadata.request_digest != original.digest()
                or metadata.native_inventory_digest != result.digest()
                or metadata.expires_at > result.expires_at
                or not result.observed_at
                <= metadata.observation_started_at
                <= metadata.observed_at
                <= self.clock()
                < metadata.expires_at
            ):
                raise HTTPException(409, "planning metadata expired or changed")
        final, _ = self._snapshot(request)
        if (
            final != original
            or (metadata is not None and self.clock() >= metadata.expires_at)
            or result.request != original
            or not (now <= result.observed_at <= self.clock() < result.expires_at)
        ):
            raise HTTPException(409, "diagnostic result expired or changed")
        return result, metadata
