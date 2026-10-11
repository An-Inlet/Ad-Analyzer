"""Original-session, independently scoped reporting contexts; no factory or writes."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ads.models import AdvertisingAccount
from app.automation.catalog import AutomationControlKey
from app.automation.service import AutomationControlService
from app.billing.entitlements import paid_work
from app.campaign_performance.selected_contracts import (
    ReportingScopeV1,
    SelectedCaptureRequestV1,
    capture_request_digest,
)
from app.campaign_performance.selected_storage import _aggregate, current_scope, read_selection
from app.customers.access import CustomerPrincipal
from app.customers.identity import IdentityProvider
from app.customers.models import CustomerSession
from app.executors.social_http import _private_http
from app.google_connections.http import GoogleHTTPRead
from app.google_connections.models import GoogleCustomerConnection
from app.google_connections.security import Vault
from app.google_connections.selected_catalog import (
    GoogleReportingCatalogContext,
    GoogleReportingCatalogRequestV1,
)
from app.google_connections.selected_http import SelectedGoogleContext
from app.google_connections.selected_presence import PRODUCER, query_profile_digest
from app.lifecycle.privacy import workspace_export_revision
from app.publication.customer_authority import bind_authority


class OwnedGoogleReportingContext:
    """One bounded operation. Inputs come from trusted customer composition only."""

    def __init__(
        self,
        sessions: Callable[[], Session],
        principal: CustomerPrincipal,
        identity_provider: IdentityProvider,
        workspace_id: int,
        account_id: int,
        oauth: GoogleHTTPRead,
        vault: Vault,
        clock: Callable[[], datetime],
    ) -> None:
        if (
            type(oauth) is not GoogleHTTPRead
            or oauth.version != "v24"
            or (oauth.developer is None or not oauth.developer.get_secret_value())
        ):
            raise HTTPException(503, "Google reporting configuration unavailable")
        self._sessions, self._oauth, self._vault, self._clock = sessions, oauth, vault, clock
        self._authorize = bind_authority(principal, identity_provider)
        self._actor, self._sid = principal.user.id, principal.session.digest
        self._auth_time, self._expiry = (
            principal.session.authenticated_at,
            principal.session.expires_at,
        )
        self._wid, self._aid = workspace_id, account_id
        self._started = self._now()
        self._deadline = min(
            self._started + timedelta(seconds=60), datetime.fromtimestamp(self._expiry, UTC)
        )
        self._catalog: GoogleReportingCatalogRequestV1 | None = None
        self._selected: SelectedCaptureRequestV1 | None = None
        self._grant: tuple[str, str | None] | None = None
        self._check_time()

    def _now(self) -> datetime:
        value = self._clock()
        if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("aware reporting clock required")
        return value.astimezone(UTC)

    def _check_time(self) -> None:
        if not self._started <= self._now() < self._deadline:
            raise HTTPException(409, "Google reporting operation expired")

    def _snapshot(
        self, expected: ReportingScopeV1 | None
    ) -> tuple[ReportingScopeV1, str, str | None]:
        self._check_time()
        with self._sessions() as db:
            self._authorize(db, self._wid, self._actor)
            session = db.get(CustomerSession, self._sid, populate_existing=True)
            if session is None or (session.authenticated_at, session.expires_at) != (
                self._auth_time,
                self._expiry,
            ):
                raise HTTPException(401, "original customer session required")
            paid_work(db, self._wid, self._now())
            if not AutomationControlService(db).master_enabled(AutomationControlKey.ALL_DATA_SYNCS):
                raise HTTPException(409, "Google reporting reads paused")
            account = db.scalar(
                select(AdvertisingAccount)
                .where(
                    AdvertisingAccount.workspace_id == self._wid, AdvertisingAccount.id == self._aid
                )
                .with_for_update()
            )
            source = db.scalar(
                select(GoogleCustomerConnection)
                .where(
                    GoogleCustomerConnection.workspace_id == self._wid,
                    GoogleCustomerConnection.account_id == self._aid,
                )
                .with_for_update()
            )
            if account is None or source is None:
                raise HTTPException(404, "Google reporting account unavailable")
            scope = ReportingScopeV1(
                workspace_id=self._wid,
                connection_id=account.connection_id,
                account_id=account.id,
                platform="google_ads",
                source_connection_ref=source.id,
                generation=source.generation,
                privacy_revision=workspace_export_revision(db, self._wid),
                native_account_id=account.external_account_id,
                currency=account.currency_code,
                time_zone=account.time_zone,
            )
            current_scope(db, scope)
            if expected is not None and scope != expected:
                raise HTTPException(409, "Google reporting source changed")
            if not source.encrypted_grant:
                raise HTTPException(409, "Google reporting reconnect required")
            grant = (source.encrypted_grant, source.login_customer_id)
            if self._grant is not None and grant != self._grant:
                raise HTTPException(409, "Google reporting grant changed")
            if self._selected is not None:
                if read_selection(db, self._wid, self._aid) != self._selected.selection:
                    raise HTTPException(409, "Google reporting selection changed")
                _aggregate(db, self._selected.aggregate)
            self._authorize(db, self._wid, self._actor)
            paid_work(db, self._wid, self._now())
            self._check_time()
            if self._grant is None:
                self._grant = grant
            return scope, grant[0], grant[1]

    def catalog_request(self) -> GoogleReportingCatalogRequestV1:
        if self._selected is not None:
            raise HTTPException(409, "Google reporting operation mismatch")
        if self._catalog is not None:
            self.revalidate_catalog(self._catalog)
            return self._catalog
        scope, _, _ = self._snapshot(None)
        self._catalog = GoogleReportingCatalogRequestV1(
            scope=scope,
            actor_id=self._actor,
            original_session_digest=self._sid,
            started_at=self._started,
        )
        return self._catalog

    def revalidate_catalog(self, request: GoogleReportingCatalogRequestV1) -> None:
        req = GoogleReportingCatalogRequestV1.model_validate(request)
        if self._catalog is None or self._selected is not None or req != self._catalog:
            raise HTTPException(409, "Google reporting request changed")
        self._snapshot(req.scope)

    def _bind_selected(self, request: SelectedCaptureRequestV1) -> SelectedCaptureRequestV1:
        req = SelectedCaptureRequestV1.model_validate(request)
        choice = req.selection
        if (
            self._catalog is not None
            or (req.aggregate.scope.workspace_id, req.aggregate.scope.account_id)
            != (self._wid, self._aid)
            or (
                choice.scope.platform != "google_ads"
                or choice.api_version != "v24"
                or choice.native_event_owner_id != choice.scope.native_account_id
                or choice.metric_family not in {"conversions", "all_conversions"}
                or req.producer_contract != PRODUCER
                or req.query_profile_digest
                != query_profile_digest(
                    "conversions" if choice.metric_family == "conversions" else "all_conversions"
                )
                or req.started_at > self._now()
            )
        ):
            raise HTTPException(409, "Google reporting request unavailable")
        if self._selected is not None and req != self._selected:
            raise HTTPException(409, "Google reporting request changed")
        self._selected = req
        self._deadline = min(self._deadline, req.started_at + timedelta(seconds=60))
        self._check_time()
        return req

    def revalidate_selected(self, request: SelectedCaptureRequestV1) -> None:
        req = self._bind_selected(request)
        self._snapshot(req.aggregate.scope)

    def _context(self, scope: ReportingScopeV1, digest: str) -> SelectedGoogleContext:
        before = self._snapshot(scope)
        # The snapshot transaction is closed before decryption and OAuth IO.
        private = _private_http.set(True)
        try:
            refresh = self._vault.open(self._wid, scope.source_connection_ref, before[1])
            if self._snapshot(scope) != before:
                raise HTTPException(409, "Google reporting source changed")
            began = self._now()
            self._check_time()
            access, seconds = self._oauth.access_context(refresh)
            expires = min(began + timedelta(seconds=seconds), self._deadline)
        finally:
            _private_http.reset(private)
        if self._snapshot(scope) != before or self._now() >= expires:
            raise HTTPException(409, "Google reporting context expired")
        developer = self._oauth.developer
        if developer is None or self._oauth.version != "v24":
            raise HTTPException(503, "Google reporting configuration unavailable")
        return SelectedGoogleContext(
            request_digest=digest,
            expires_at=expires,
            access_token=access,
            developer_token=developer,
            login_customer_id=before[2],
        )

    def catalog_context(
        self, request: GoogleReportingCatalogRequestV1
    ) -> GoogleReportingCatalogContext:
        self.revalidate_catalog(request)
        ctx = self._context(request.scope, request.digest())
        return GoogleReportingCatalogContext(
            request_digest=ctx.request_digest,
            expires_at=ctx.expires_at,
            access_token=ctx.access_token,
            developer_token=ctx.developer_token,
            login_customer_id=ctx.login_customer_id,
        )

    def selected_context(self, request: SelectedCaptureRequestV1) -> SelectedGoogleContext:
        self.revalidate_selected(request)
        return self._context(request.aggregate.scope, capture_request_digest(request))
