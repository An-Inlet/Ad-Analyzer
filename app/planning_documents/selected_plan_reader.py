"""Owned SQL-only selected evidence; authority refresh belongs outside this context."""

from collections.abc import Callable
from copy import deepcopy
from datetime import datetime
from types import TracebackType
from typing import Any

from sqlalchemy import event, inspect, select
from sqlalchemy.orm import Session

from app.ads.models import AdvertisingAccount, Campaign, DailyMetric
from app.campaign_performance.models import CurrentPerformance, PerformanceCompletion
from app.campaign_performance.selected_models import (
    CurrentEventSelectionRow,
    EventSelectionRow,
    SelectedCaptureRow,
    SelectedFactRow,
)
from app.campaign_performance.selected_storage import read_selected_capture as read_selected_capture
from app.campaign_performance.service import Authorize
from app.customers.access import CustomerPrincipal
from app.customers.models import CustomerMembership, CustomerSession, CustomerUser
from app.database.session import Base
from app.google_connections.models import GoogleCustomerConnection
from app.lifecycle.privacy import database_utc_now
from app.meta.models import MetaConnection
from app.planning_documents.composer import targets
from app.planning_documents.context import AccountRef, ReportingWindow, TargetRef
from app.planning_documents.evidence_local import changed, resolve_source_fences
from app.planning_documents.ports import CatalogEvidence, SourceFence
from app.planning_documents.selected_inputs import SelectedCaptureSelectorV1
from app.planning_documents.selected_plan_evidence import (
    PreparedSelectedPlanProjection,
    SelectedCampaignBindingV1,
    SelectedPlanCaptureV1,
    SelectedPlanPinV1,
    SelectedPlanWindowV1,
)
from app.shopify.security import utc
from app.sources.models import SourceConnection
from app.workspaces.models import Workspace, WorkspaceIntegration


def load_selected_plan_graph(
    db: Session, *, account: AccountRef, expected_source: SourceFence, capture_id: str
) -> SelectedPlanCaptureV1:
    """Internal SQL port: caller owns original authorization and scope locks.

    No identity/provider IO or commit. Caller guards authority before and after.
    """
    account = AccountRef.model_validate(account)
    source = SourceFence.model_validate(expected_source)
    selector = SelectedCaptureSelectorV1(account_id=account.account_id, capture_id=capture_id)
    if (
        source.account != account
        or db.get_transaction() is None
        or db.in_nested_transaction()
        or db.new
        or db.dirty
        or db.deleted
    ):
        raise changed()
    with db.no_autoflush:
        capture = read_selected_capture(
            db, account.workspace_id, account.account_id, selector.capture_id
        )
        rows = db.execute(
            select(Campaign.id, Campaign.external_campaign_id, Campaign.platform)
            .where(Campaign.account_id == account.account_id)
            .order_by(Campaign.id)
            .limit(10_001)
        ).all()
        if len(rows) > 10_000 or any(row.platform.value != account.platform for row in rows):
            raise changed()
        return SelectedPlanCaptureV1(
            source_fence=source,
            capture=capture,
            campaigns=tuple(
                SelectedCampaignBindingV1(
                    campaign_id=row.id, native_campaign_id=row.external_campaign_id
                )
                for row in rows
            ),
        )


class OwnedSelectedPlanContext:
    """One clean caller-owned transaction; close before persistence or external IO."""

    def __init__(
        self,
        db: Session,
        *,
        principal: CustomerPrincipal,
        account: AccountRef,
        expected_source: SourceFence,
        capture_id: str,
        catalog: CatalogEvidence,
        authorize: Authorize,
        clock: Callable[[], datetime],
    ) -> None:
        self.db, self.principal, self.authorize, self.clock = db, principal, authorize, clock
        self.account = AccountRef.model_validate(account)
        self.source = SourceFence.model_validate(expected_source)
        self.catalog = CatalogEvidence.model_validate(catalog)
        self.capture_id = SelectedCaptureSelectorV1(
            account_id=account.account_id, capture_id=capture_id
        ).capture_id
        self._root = db.get_transaction()
        self._closed = self._invalid = False
        self._hooks: list[tuple[str, Any]] = []
        self._residents: dict[Any, dict[str, Any]] = {}
        self._expected_rows: dict[Any, dict[str, Any]] = {}
        if self._root is None or db.in_nested_transaction() or db.new or db.dirty or db.deleted:
            raise changed()
        self._connection = db.connection()
        self._connection_transaction = self._connection.get_transaction()
        self._targets = {t.canonical_entity_key: t for t in targets(self.catalog)}
        self._remember()
        try:
            for name, callback in (
                ("before_flush", self._flush),
                ("after_transaction_create", self._transaction),
                ("after_transaction_end", self._transaction),
            ):
                event.listen(db, name, callback)
                self._hooks.append((name, callback))
            with db.no_autoflush:
                self._authority()
                self._graph = load_selected_plan_graph(
                    db,
                    account=self.account,
                    expected_source=self.source,
                    capture_id=self.capture_id,
                )
                self._projection = PreparedSelectedPlanProjection(self._graph)
                self._witness = self._raw_witness(initialize=True)
                self._transaction_guard()
                self._remember()
                self._guard()
        except BaseException:
            self.close()
            raise

    def _transaction(self, db: Session, transaction: Any) -> None:
        if transaction.nested or transaction is self._root:
            self._invalid = True

    def _flush(self, db: Session, context: Any, instances: Any) -> None:
        self._invalid = True
        raise changed()

    def _remember(self) -> None:
        for row in self.db.identity_map.values():
            state = inspect(row)
            assert state is not None
            self._residents[state.key] = deepcopy(
                {c.key: state.dict[c.key] for c in state.mapper.column_attrs if c.key in state.dict}
            )

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
        for row in db.identity_map.values():
            state = inspect(row)
            assert state is not None
            expected = self._expected_rows.get((state.mapper.local_table.name, state.identity))
            if expected is not None and any(
                key in state.dict and state.dict[key] != value for key, value in expected.items()
            ):
                raise changed()
            previous = self._residents.get(state.key)
            if previous is not None and any(
                key not in state.dict or state.dict[key] != value for key, value in previous.items()
            ):
                raise changed()

    def _authority(self) -> None:
        self._transaction_guard()
        self.authorize(self.db, self.account.workspace_id, self.principal.user.id)
        now = max(utc(self.clock()), database_utc_now(self.db))
        ref = self.catalog.reference
        if (
            self.source.account != self.account
            or ref.account != self.account
            or ref.privacy_revision != self.source.privacy_revision
            or ref.source_binding_digest != self.source.source_binding_digest
            or ref.source_revision != self.source.source_revision
            or not ref.observed_at <= now < ref.expires_at
        ):
            raise changed()
        if resolve_source_fences(
            self.db, principal=self.principal, accounts=(self.account,), now=now
        ) != (self.source,):
            raise changed()

    def _raw_witness(self, *, initialize: bool = False) -> tuple[Any, ...]:
        """Bounded exact SQL values, not repeated capture parsing/summary construction."""
        capture = self._graph.capture
        dep = capture.request.aggregate
        source_model: Any = {
            "google_ads": GoogleCustomerConnection,
            "meta_ads": MetaConnection,
            "tiktok_ads": SourceConnection,
        }[self.account.platform]
        specifications = (
            (Workspace, Workspace.id == self.account.workspace_id, 1),
            (AdvertisingAccount, AdvertisingAccount.id == self.account.account_id, 1),
            (WorkspaceIntegration, WorkspaceIntegration.id == self.account.connection_id, 1),
            (source_model, source_model.account_id == self.account.account_id, 1),
            (CustomerUser, CustomerUser.id == self.principal.user.id, 1),
            (CustomerSession, CustomerSession.digest == self.principal.session.digest, 1),
            (
                CustomerMembership,
                (CustomerMembership.user_id == self.principal.user.id)
                & (CustomerMembership.workspace_id == self.account.workspace_id),
                1,
            ),
            (SelectedCaptureRow, SelectedCaptureRow.id == self.capture_id, 1),
            (SelectedFactRow, SelectedFactRow.capture_id == self.capture_id, 50_000),
            (EventSelectionRow, EventSelectionRow.id == capture.request.selection.selection_id, 1),
            (
                CurrentEventSelectionRow,
                CurrentEventSelectionRow.account_id == self.account.account_id,
                1,
            ),
            (PerformanceCompletion, PerformanceCompletion.id == dep.completion_id, 1),
            (CurrentPerformance, CurrentPerformance.account_id == self.account.account_id, 1),
            (Campaign, Campaign.account_id == self.account.account_id, 10_000),
            (
                DailyMetric,
                DailyMetric.campaign_id.in_(
                    select(Campaign.id).where(Campaign.account_id == self.account.account_id)
                )
                & DailyMetric.metric_date.between(dep.starts_on, dep.ends_on),
                50_000,
            ),
        )
        result = []
        size = 0
        for model, predicate, limit in specifications:
            table = Base.metadata.tables[model.__tablename__]
            rows = tuple(
                tuple(row)
                for row in self.db.execute(
                    select(*table.c)
                    .where(predicate)
                    .order_by(*table.primary_key.columns)
                    .limit(limit + 1)
                )
            )
            if len(rows) > limit:
                raise changed()
            size += len(repr(rows).encode())
            if size > 64 * 1024 * 1024:
                raise changed()
            if initialize:
                columns = list(table.c.keys())
                pk = [columns.index(c.key) for c in table.primary_key.columns]
                for row in rows:
                    self._expected_rows[(table.name, tuple(row[i] for i in pk))] = dict(
                        zip(columns, row, strict=True)
                    )
            result.append(rows)
        return tuple(result)

    def _guard(self) -> None:
        self._transaction_guard()
        with self.db.no_autoflush:
            self._authority()
            if self._raw_witness() != self._witness:
                raise changed()
            self.authorize(self.db, self.account.workspace_id, self.principal.user.id)
            self._transaction_guard()
            if (
                max(utc(self.clock()), database_utc_now(self.db))
                >= self.catalog.reference.expires_at
            ):
                raise changed()
            self._remember()

    @property
    def pin(self) -> SelectedPlanPinV1:
        self._guard()
        return self._projection.pin

    def snapshot(self) -> SelectedPlanCaptureV1:
        self._guard()
        return self._graph

    def read(self, target: TargetRef, requested_window: ReportingWindow) -> SelectedPlanWindowV1:
        target = TargetRef.model_validate(target)
        requested_window = ReportingWindow.model_validate(requested_window)
        self._guard()
        if target.kind != "campaign" or self._targets.get(target.canonical_entity_key) != target:
            raise changed()
        matches = [
            x
            for x in self._graph.campaigns
            if x.native_campaign_id == target.provider_reference.entity_id
        ]
        if len(matches) != 1:
            raise changed()
        result = self._projection.read(matches[0].campaign_id, requested_window)
        self._guard()
        return result

    def __enter__(self) -> "OwnedSelectedPlanContext":
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
        try:
            if exc_type is None:
                self._guard()
        finally:
            self.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for name, callback in self._hooks:
            event.remove(self.db, name, callback)
        self._hooks.clear()
        self._residents.clear()
        self._expected_rows.clear()
