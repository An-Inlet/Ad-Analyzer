"""Owned transaction-local window reads; no runtime activation or external IO.

Caller resolves catalog/receipt provenance and refreshes identity before SQL.
Raw SQL mutation and external IO during the read slice are prohibited caller
behavior, not a sandbox guarantee. Close before persistence or any external call.
"""

from collections.abc import Callable
from datetime import datetime
from types import TracebackType
from typing import Any

from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.ads.models import Campaign
from app.campaign_performance.models import CurrentPerformance, PerformanceCompletion
from app.campaign_performance.presence_report import (
    CampaignPerformanceV3,
    PresenceReadContext,
    read_current_with_presence,
)
from app.campaign_performance.service import Authorize
from app.campaign_performance.window_projection import (
    RequestedWindowPerformanceV1,
    WindowProjectionUnavailable,
    project_requested_window,
)
from app.customers.access import CustomerPrincipal
from app.lifecycle.privacy import database_utc_now
from app.planning_documents.composer import targets
from app.planning_documents.context import AccountRef, ReportingWindow, TargetRef
from app.planning_documents.evidence_local import changed, resolve_source_fences
from app.planning_documents.ports import CatalogEvidence, ReportingPresencePin, SourceFence
from app.planning_documents.retained_sources import capture_reporting_presence_pin
from app.planning_documents.window_evidence import KnownWindowGap
from app.shopify.security import utc


def _scalars(item: PerformanceCompletion) -> tuple[Any, ...]:
    return tuple(
        utc(value) if isinstance(value, datetime) else value
        for column in PerformanceCompletion.__table__.columns
        for value in (getattr(item, column.name),)
    )


class _GuardedPresence(PresenceReadContext):
    def __init__(self, owner: "OwnedWindowReadContext") -> None:
        super().__init__(owner.db)
        self.owner = owner

    def read(self, item: PerformanceCompletion) -> Any:
        if self.owner._checking:
            self.owner._transaction_guard()
            self.owner._completion_guard(item)
        else:
            self.owner._guard(item)
        return super().read(item)


class OwnedWindowReadContext:
    """Use prepare_owned_window_context, then with/close; never share transactions."""

    def __init__(
        self,
        db: Session,
        *,
        principal: CustomerPrincipal,
        account: AccountRef,
        expected_source: SourceFence,
        expected_reporting_pin: ReportingPresencePin,
        catalog: CatalogEvidence,
        authorize: Authorize,
        clock: Callable[[], datetime],
    ) -> None:
        self.db, self.principal, self.authorize, self.clock = db, principal, authorize, clock
        self.account = AccountRef.model_validate(account)
        self.source = SourceFence.model_validate(expected_source)
        self.pin = ReportingPresencePin.model_validate(expected_reporting_pin)
        self.catalog = CatalogEvidence.model_validate(catalog)
        self._closed, self._invalid, self._checking = False, False, False
        self._hooks: list[tuple[str, Any]] = []
        self._root = db.get_transaction()
        if self._root is None or db.in_nested_transaction() or db.new or db.dirty or db.deleted:
            raise changed()
        self._connection = db.connection()
        self._connection_transaction = self._connection.get_transaction()
        self._originals: dict[int, CampaignPerformanceV3] = {}
        self._targets = {target.canonical_entity_key: target for target in targets(self.catalog)}
        self._completion_id: str | None = None
        self._completion: tuple[Any, ...] | None = None
        try:
            for name, callback in (
                ("after_transaction_create", self._transaction_event),
                ("after_transaction_end", self._transaction_event),
                ("before_flush", self._flush_event),
            ):
                event.listen(db, name, callback)
                self._hooks.append((name, callback))
            with db.no_autoflush:
                self._authority_guard()
                current = db.get(CurrentPerformance, account.account_id, populate_existing=True)
                if current is not None:
                    if current.workspace_id != account.workspace_id:
                        raise changed()
                    self._completion_id = current.completion_id
                    item = db.get(
                        PerformanceCompletion, current.completion_id, populate_existing=True
                    )
                    if item is None:
                        raise changed()
                    self._completion = _scalars(item)
                self._presence = _GuardedPresence(self)
                self._guard()
        except BaseException:
            self.close()
            raise

    def _transaction_event(self, db: Session, transaction: Any) -> None:
        if transaction.nested or transaction is self._root:
            self._invalid = True

    def _flush_event(self, db: Session, context: Any, instances: Any) -> None:
        self._invalid = True
        raise changed()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for name, callback in self._hooks:
            event.remove(self.db, name, callback)
        self._hooks.clear()
        self._originals.clear()

    def __enter__(self) -> "OwnedWindowReadContext":
        try:
            self._guard()
        except BaseException:
            self.close()
            raise
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def _transaction_guard(self) -> None:
        db = self.db
        if (
            self._closed
            or self._invalid
            or self._root is None
            or not self._root.is_active
            or db.get_transaction() is not self._root
            or db.in_nested_transaction()
            or self._connection.closed
            or self._connection.get_transaction() is not self._connection_transaction
            or db.new
            or db.dirty
            or db.deleted
        ):
            raise changed()

    def _completion_guard(self, supplied: PerformanceCompletion | None = None) -> None:
        # Check supplied identity-map values BEFORE any refresh can overwrite them.
        if supplied is not None and _scalars(supplied) != self._completion:
            raise changed()
        if self._completion_id is not None:
            resident = self.db.identity_map.get(
                self.db.identity_key(PerformanceCompletion, self._completion_id)
            )
            if resident is not None and _scalars(resident) != self._completion:
                raise changed()
        current = self.db.get(CurrentPerformance, self.account.account_id, populate_existing=True)
        if self._completion_id is None:
            if current is not None:
                raise changed()
            return
        if current is None or (current.workspace_id, current.completion_id) != (
            self.account.workspace_id,
            self._completion_id,
        ):
            raise changed()
        item = self.db.get(PerformanceCompletion, self._completion_id, populate_existing=True)
        if item is None or _scalars(item) != self._completion:
            raise changed()

    def _authority_guard(self) -> None:
        self._transaction_guard()
        self.authorize(self.db, self.account.workspace_id, self.principal.user.id)
        now = max(utc(self.clock()), database_utc_now(self.db))
        reference = self.catalog.reference
        if (
            self.source.account != self.account
            or self.pin.account != self.account
            or reference.account != self.account
            or reference.privacy_revision != self.source.privacy_revision
            or reference.source_binding_digest != self.source.source_binding_digest
            or reference.source_revision != self.source.source_revision
            or not reference.observed_at <= now < reference.expires_at
        ):
            raise changed()
        fresh = resolve_source_fences(
            self.db,
            principal=self.principal,
            accounts=(self.account,),
            now=now,
        )
        if fresh != (self.source,):
            raise changed()

    def _guard(self, supplied: PerformanceCompletion | None = None) -> None:
        self._transaction_guard()
        with self.db.no_autoflush:
            self._authority_guard()
            self._completion_guard(supplied)
            reference = self.catalog.reference
            self._checking = True
            try:
                digest = capture_reporting_presence_pin(
                    self.db,
                    self.principal,
                    self.account,
                    self.source.privacy_revision,
                    presence_context=self._presence,
                )
            finally:
                self._checking = False
            if digest != self.pin.document_digest:
                raise changed()
            self.authorize(self.db, self.account.workspace_id, self.principal.user.id)
            self._transaction_guard()
            if max(utc(self.clock()), database_utc_now(self.db)) >= reference.expires_at:
                raise changed()

    def read(
        self, target: TargetRef, requested_window: ReportingWindow
    ) -> RequestedWindowPerformanceV1 | KnownWindowGap:
        target = TargetRef.model_validate(target)
        requested_window = ReportingWindow.model_validate(requested_window)
        self._guard()
        if target.kind != "campaign" or self._targets.get(target.canonical_entity_key) != target:
            raise changed()
        if self._completion_id is None:
            return KnownWindowGap(reason="current_reporting_unavailable")
        with self.db.no_autoflush:
            campaign = self.db.scalar(
                select(Campaign).where(
                    Campaign.account_id == self.account.account_id,
                    Campaign.platform == self.account.platform,
                    Campaign.external_campaign_id == target.provider_reference.entity_id,
                )
            )
            if campaign is None:
                self._guard()
                return KnownWindowGap(reason="campaign_reporting_unavailable")
            original = self._originals.get(campaign.id)
            if original is None:
                doc = read_current_with_presence(
                    self.db,
                    self.account.workspace_id,
                    self.principal.user.id,
                    self.account.account_id,
                    campaign.id,
                    self._completion_id,
                    self.authorize,
                    context=self._presence,
                )
                if not isinstance(doc, CampaignPerformanceV3):
                    self._guard()
                    return KnownWindowGap(reason="reporting_presence_unavailable")
                original = doc
                self._originals[campaign.id] = doc
            try:
                result: RequestedWindowPerformanceV1 | KnownWindowGap = project_requested_window(
                    original,
                    requested_window=requested_window,
                )
            except WindowProjectionUnavailable as error:
                result = KnownWindowGap(reason=error.reason)
            self._guard()
            return result


def prepare_owned_window_context(
    db: Session,
    *,
    principal: CustomerPrincipal,
    account: AccountRef,
    expected_source: SourceFence,
    expected_reporting_pin: ReportingPresencePin,
    catalog: CatalogEvidence,
    authorize: Authorize,
    clock: Callable[[], datetime],
) -> OwnedWindowReadContext:
    return OwnedWindowReadContext(
        db,
        principal=principal,
        account=account,
        expected_source=expected_source,
        expected_reporting_pin=expected_reporting_pin,
        catalog=catalog,
        authorize=authorize,
        clock=clock,
    )


def read_owned_requested_window(
    context: OwnedWindowReadContext,
    *,
    target: TargetRef,
    requested_window: ReportingWindow,
) -> RequestedWindowPerformanceV1 | KnownWindowGap:
    return context.read(target, requested_window)
