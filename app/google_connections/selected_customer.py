"""Original-session customer reporting choices; no advertising or capture authority."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

import httpx
from fastapi import HTTPException
from pydantic import AwareDatetime, Field, model_validator
from sqlalchemy.orm import Session

from app.automation.catalog import AutomationControlKey
from app.automation.service import AutomationControlService
from app.billing.entitlements import paid_work
from app.campaign_performance.models import CurrentPerformance, PerformanceCompletion
from app.campaign_performance.presence_contracts import Digest, Frozen, Id, Positive
from app.campaign_performance.selected_contracts import (
    AggregateDependencyV1,
    CustomerEventSelectionV1,
    selection_digest,
)
from app.campaign_performance.selected_models import CurrentEventSelectionRow
from app.campaign_performance.selected_storage import (
    SelectedReportingUnavailable,
    _aggregate,
    current_scope,
    invalidate_selected_account,
    lock_scope,
    read_selection,
    store_selection,
)
from app.customers.access import CustomerPrincipal
from app.customers.identity import IdentityProvider
from app.customers.models import CustomerSession
from app.google_connections.http import GoogleHTTPRead
from app.google_connections.security import Vault
from app.google_connections.selected_catalog import (
    Family,
    GoogleReportingCatalogHTTP,
    GoogleReportingCatalogUnavailable,
    GoogleReportingCatalogV1,
    GoogleReportingOptionV1,
)
from app.google_connections.selected_source_pin import SourcePin, source_pin
from app.planning_documents import authority
from app.planning_documents.read_context import snapshot


class AccountIntent(Frozen):
    account_id: Positive


class SelectionIntent(AccountIntent):
    option_id: Digest
    expected_selection_id: Id | None
    expected_selection_digest: Digest | None

    @model_validator(mode="after")
    def paired(self) -> "SelectionIntent":
        if (self.expected_selection_id is None) != (self.expected_selection_digest is None):
            raise ValueError("expected selection pair required")
        return self


class InvalidationIntent(AccountIntent):
    expected_selection_id: Id
    expected_selection_digest: Digest


class OptionView(Frozen):
    option_id: Digest
    label: str = Field(min_length=1, max_length=160)
    metric_family: Family
    api_version: Literal["v24"] = "v24"


class OptionsView(Frozen):
    account_id: Positive
    observed_at: AwareDatetime
    expires_at: AwareDatetime
    options: tuple[OptionView, ...] = Field(max_length=2000)
    spending_authorized: Literal[False] = False


class SelectionView(Frozen):
    account_id: Positive
    state: Literal["none", "selected", "refresh_required", "unavailable"]
    selection_id: Id | None = None
    selection_digest: Digest | None = None
    confirmed_at: AwareDatetime | None = None
    label: str | None = Field(default=None, min_length=1, max_length=160)
    metric_family: Family | None = None
    api_version: Literal["v24"] | None = None
    spending_authorized: Literal[False] = False

    @model_validator(mode="after")
    def shape(self) -> "SelectionView":
        pair = self.selection_id is not None and self.selection_digest is not None
        if self.state == "none":
            if self.selection_id is not None or self.selection_digest is not None:
                raise ValueError("unexpected selection")
        elif not pair:
            raise ValueError("selection receipt pair required")
        details = (self.confirmed_at, self.metric_family, self.api_version)
        if self.state == "selected":
            if any(v is None for v in details):
                raise ValueError("selected details required")
        elif any(v is not None for v in (*details, self.label)):
            raise ValueError("unavailable choice is not current")
        return self


@dataclass(frozen=True)
class SelectedCustomerRuntime:
    sessions: Callable[[], Session] = field(repr=False)
    oauth: GoogleHTTPRead = field(repr=False)
    vault: Vault = field(repr=False)
    transport: Callable[[], httpx.BaseTransport] = field(repr=False)
    clock: Callable[[], datetime] = field(repr=False)
    available: Callable[[], bool] | None = field(default=None, repr=False)


def unavailable() -> HTTPException:
    return HTTPException(409, "reporting_selection_unavailable")


class SelectedCustomerService:
    def __init__(
        self,
        principal: CustomerPrincipal,
        provider: IdentityProvider,
        workspace_id: int,
        runtime: SelectedCustomerRuntime | None,
        sessions: Callable[[], Session] | None = None,
    ) -> None:
        self.original = snapshot(principal)
        self.provider, self.wid, self.runtime = provider, workspace_id, runtime
        self.sessions = sessions or (runtime.sessions if runtime else None)
        self._active: tuple[Session, authority.IdentityFact, object] | None = None
        self._catalog_pin: SourcePin | None = None

    @contextmanager
    def open(self, account_id: int, *, read: bool = True) -> Iterator[Session]:
        if self._active is not None or self.sessions is None:
            raise unavailable()
        fact = authority.refresh(self.original, self.provider)
        with self.sessions() as db:
            # Legacy SQLite does not BEGIN for SELECT/SAVEPOINT. A nested storage
            # release must never commit before the final original-session guard.
            if db.get_bind().dialect.name == "sqlite":
                connection = db.connection()
                driver = connection.connection.driver_connection
                assert driver is not None
                if not driver.in_transaction:
                    connection.exec_driver_sql("BEGIN")
            current = authority.lock(db, self.original, self.wid, fact)
            authority.final(current, fact)
            self._active = (db, fact, db.get_transaction())
            try:
                self.guard(db, account_id, read=read)
                yield db
            finally:
                # Callers perform final guard after all flush/waits before commit.
                # Never reauthorize/start SQL after a successful commit.
                self._active = None

    def now(self) -> datetime:
        value = self.runtime.clock() if self.runtime else datetime.now(UTC)
        if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
            raise unavailable()
        return value.astimezone(UTC)

    def require_runtime(self) -> None:
        if self.runtime is None or (
            self.runtime.available is not None and not self.runtime.available()
        ):
            raise HTTPException(503, "reporting_selection_runtime_unavailable")

    def guard(self, db: Session, account_id: int, *, read: bool = False) -> None:
        active = self._active
        if active is None or active[0] is not db or active[2] is not db.get_transaction():
            raise HTTPException(401, "reporting transaction authority required")
        current = authority.lock(db, self.original, self.wid, active[1])
        row = db.get(CustomerSession, self.original.session.digest, populate_existing=True)
        if row is None or (row.authenticated_at, row.expires_at) != (
            self.original.session.authenticated_at,
            self.original.session.expires_at,
        ):
            raise HTTPException(401, "original customer session required")
        account = lock_scope(db, self.wid, account_id)
        if account.platform.value != "google_ads":
            raise unavailable()
        if read:
            self.require_runtime()
            paid_work(db, self.wid, self.now())
            if not AutomationControlService(db).master_enabled(AutomationControlKey.ALL_DATA_SYNCS):
                raise HTTPException(409, "reporting_reads_paused")
        authority.final(current, active[1])
        if self.now().timestamp() >= self.original.session.expires_at:
            raise HTTPException(401, "original customer session expired")
        if read:
            self.require_runtime()

    def head(self, db: Session, account_id: int) -> CurrentEventSelectionRow | None:
        return db.get(CurrentEventSelectionRow, account_id, populate_existing=True)

    def cas(self, db: Session, intent: SelectionIntent | InvalidationIntent) -> None:
        head = self.head(db, intent.account_id)
        expected = (intent.expected_selection_id, intent.expected_selection_digest)
        actual = (head.selection_id, head.selection_digest) if head else (None, None)
        if actual != expected:
            raise HTTPException(409, "reporting_selection_changed")

    def state(self, db: Session, account_id: int) -> SelectionView:
        self.guard(db, account_id)
        head = self.head(db, account_id)
        if head is None:
            self.guard(db, account_id)
            return SelectionView(account_id=account_id, state="none")
        if head.invalidated:
            self.guard(db, account_id)
            return SelectionView(
                account_id=account_id,
                state="refresh_required",
                selection_id=head.selection_id,
                selection_digest=head.selection_digest,
            )
        try:
            selected = read_selection(db, self.wid, account_id)
        except (SelectedReportingUnavailable, HTTPException):
            self.guard(db, account_id)
            return SelectionView(
                account_id=account_id,
                state="unavailable",
                selection_id=head.selection_id,
                selection_digest=head.selection_digest,
            )
        self.guard(db, account_id)
        return self.receipt(selected)

    def invalidate(self, db: Session, intent: InvalidationIntent) -> SelectionView:
        self.guard(db, intent.account_id)
        self.cas(db, intent)
        invalidate_selected_account(db, self.wid, intent.account_id)
        self.guard(db, intent.account_id)
        return SelectionView(
            account_id=intent.account_id,
            state="refresh_required",
            selection_id=intent.expected_selection_id,
            selection_digest=intent.expected_selection_digest,
        )

    def catalog(
        self, intent: AccountIntent, expected: SelectionIntent | None = None
    ) -> GoogleReportingCatalogV1:
        runtime = self.runtime
        with self.open(intent.account_id, read=runtime is not None) as db:
            if runtime is None:
                raise HTTPException(503, "reporting_selection_runtime_unavailable")
            if expected is not None:
                self.cas(db, expected)
            self._catalog_pin = source_pin(db, self.wid, intent.account_id)
            self.guard(db, intent.account_id, read=True)
        from app.google_connections.selected_owned_context import OwnedGoogleReportingContext

        assert self.sessions is not None
        context = OwnedGoogleReportingContext(
            self.sessions,
            self.original,
            self.provider,
            self.wid,
            intent.account_id,
            runtime.oauth,
            runtime.vault,
            runtime.clock,
            expected_grant=self._catalog_pin.grant(),
            runtime_available=runtime.available,
        )
        request = context.catalog_request()
        try:
            return GoogleReportingCatalogHTTP(
                context.catalog_context,
                context.revalidate_catalog,
                transport=runtime.transport(),
                clock=runtime.clock,
            )(request)
        except GoogleReportingCatalogUnavailable:
            raise unavailable() from None

    def options(self, intent: AccountIntent) -> OptionsView:
        catalog = self.catalog(intent)
        assert self.runtime is not None
        with self.open(intent.account_id) as db:
            self.current_catalog(db, intent.account_id, catalog)
            return OptionsView(
                account_id=intent.account_id,
                observed_at=catalog.observed_at,
                expires_at=catalog.expires_at,
                options=tuple(
                    OptionView(
                        option_id=x.identifier(catalog.request),
                        label=x.label,
                        metric_family=x.metric_family,
                    )
                    for x in catalog.options
                ),
            )

    def current_catalog(self, db: Session, aid: int, catalog: GoogleReportingCatalogV1) -> None:
        self.guard(db, aid, read=True)
        current_scope(db, catalog.request.scope)
        pin = source_pin(db, self.wid, aid)
        if pin != self._catalog_pin or pin.source_id != catalog.request.scope.source_connection_ref:
            raise unavailable()
        self.guard(db, aid, read=True)
        if not catalog.request.started_at <= self.now() < catalog.expires_at:
            raise unavailable()

    def aggregate(self, db: Session, catalog: GoogleReportingCatalogV1) -> None:
        scope = catalog.request.scope
        current = db.get(CurrentPerformance, scope.account_id, populate_existing=True)
        completion = (
            db.get(PerformanceCompletion, current.completion_id, populate_existing=True)
            if current
            else None
        )
        if completion is None or completion.workspace_id != self.wid:
            raise HTTPException(409, "reporting_aggregate_refresh_required")
        try:
            _aggregate(
                db,
                AggregateDependencyV1(
                    completion_id=completion.id,
                    manifest_digest=completion.manifest_digest,
                    scope=scope,
                    starts_on=completion.starts_on,
                    ends_on=completion.ends_on,
                ),
            )
        except (SelectedReportingUnavailable, HTTPException):
            raise HTTPException(409, "reporting_aggregate_refresh_required") from None

    @staticmethod
    def receipt(value: CustomerEventSelectionV1, label: str | None = None) -> SelectionView:
        if (
            value.metric_family not in {"conversions", "all_conversions"}
            or value.api_version != "v24"
        ):
            raise unavailable()
        return SelectionView(
            account_id=value.scope.account_id,
            state="selected",
            selection_id=value.selection_id,
            selection_digest=selection_digest(value),
            confirmed_at=value.confirmed_at,
            label=label,
            metric_family=value.metric_family,
            api_version="v24",
        )

    def confirm(self, intent: SelectionIntent) -> SelectionView:
        catalog = self.catalog(intent, intent)
        option = next(
            (x for x in catalog.options if x.identifier(catalog.request) == intent.option_id), None
        )
        if option is None:
            raise HTTPException(409, "reporting_option_changed")
        assert self.runtime is not None
        with self.open(intent.account_id) as db:
            self.current_catalog(db, intent.account_id, catalog)
            self.cas(db, intent)
            self.aggregate(db, catalog)
            head = self.head(db, intent.account_id)
            if head is not None and not head.invalidated:
                existing = read_selection(db, self.wid, intent.account_id)
                if (
                    existing.confirmed_by_customer_id != self.original.user.id
                    or not self.same_choice(existing, option)
                ):
                    raise HTTPException(409, "reporting_selection_invalidation_required")
                chosen = existing
            else:
                chosen = CustomerEventSelectionV1(
                    selection_id=uuid4().hex,
                    scope=catalog.request.scope,
                    confirmed_by_customer_id=self.original.user.id,
                    confirmed_at=self.now(),
                    event_namespace="google_conversion_action",
                    native_event_owner_id=option.owner_customer_id,
                    native_event_id=option.resource_name,
                    metric_family=option.metric_family,
                    api_version="v24",
                    query_profile_digest=option.query_profile_digest,
                )
                store_selection(
                    db, chosen, intent.expected_selection_id, intent.expected_selection_digest
                )
            self.current_catalog(db, intent.account_id, catalog)
            self.aggregate(db, catalog)
            db.flush()
            self.current_catalog(db, intent.account_id, catalog)
            result = self.receipt(chosen, option.label)
            self.require_runtime()
            db.commit()
            return result

    @staticmethod
    def same_choice(value: CustomerEventSelectionV1, option: GoogleReportingOptionV1) -> bool:
        return (
            value.native_event_owner_id,
            value.native_event_id,
            value.metric_family,
            value.query_profile_digest,
            value.api_version,
        ) == (
            option.owner_customer_id,
            option.resource_name,
            option.metric_family,
            option.query_profile_digest,
            "v24",
        )
