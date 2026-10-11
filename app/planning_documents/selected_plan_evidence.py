"""Pure complete-capture projections; no SQL authority or active planning policy."""

from dataclasses import asdict
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import Field, model_validator

from app.campaign_performance.presence_contracts import NativeId
from app.campaign_performance.selected_contracts import (
    AggregateDependencyV1,
    SelectedCaptureV1,
    selected_capture_digest,
)
from app.campaign_performance.selected_summary import (
    SelectedSummaryContext,
)
from app.planning_documents.common import Digest, Frozen, Id, NoAuthority, Positive, fingerprint
from app.planning_documents.context import AccountRef, ReportingWindow
from app.planning_documents.ports import SourceFence
from app.planning_documents.selected_plan_summary import SelectedPlanSummaryV1

MAX_BYTES = 32 * 1024 * 1024


class SelectedCampaignBindingV1(Frozen):
    campaign_id: Positive
    native_campaign_id: NativeId


class SelectedPlanPinV1(Frozen):
    account: AccountRef
    source_fence: SourceFence
    aggregate: AggregateDependencyV1
    selection_id: Id
    selection_digest: Digest
    capture_id: Id
    request_digest: Digest
    capture_digest: Digest
    campaign_map_digest: Digest

    @model_validator(mode="after")
    def scope(self) -> "SelectedPlanPinV1":
        account, scope, source = self.account, self.aggregate.scope, self.source_fence
        if (
            source.account != account
            or source.source_revision != account.connection_version
            or source.privacy_revision != scope.privacy_revision
            or (account.workspace_id, account.connection_id, account.account_id, account.platform)
            != (scope.workspace_id, scope.connection_id, scope.account_id, scope.platform)
        ):
            raise ValueError("selected plan pin scope mismatch")
        return self


class SelectedPlanCaptureV1(Frozen):
    """Private whole graph, retained once per explicitly selected account."""

    source_fence: SourceFence
    capture: SelectedCaptureV1
    campaigns: tuple[SelectedCampaignBindingV1, ...] = Field(max_length=10_000)

    @model_validator(mode="after")
    def graph(self) -> "SelectedPlanCaptureV1":
        mapping = {x.campaign_id: x.native_campaign_id for x in self.campaigns}
        if (
            len(mapping) != len(self.campaigns)
            or len(set(mapping.values())) != len(mapping)
            or tuple(mapping) != tuple(sorted(mapping))
            or any(mapping.get(x.campaign_id) != x.native_campaign_id for x in self.capture.facts)
        ):
            raise ValueError("exact complete campaign mapping required")
        self._pin()  # Validate account, connection and privacy binding.
        if len(self.model_dump_json().encode()) > MAX_BYTES:
            raise ValueError("selected plan capture capacity exceeded")
        return self

    def _pin(self) -> SelectedPlanPinV1:
        request = self.capture.request
        return SelectedPlanPinV1(
            account=self.source_fence.account,
            source_fence=self.source_fence,
            aggregate=request.aggregate,
            selection_id=request.selection.selection_id,
            selection_digest=request.selection_digest,
            capture_id=request.capture_id,
            request_digest=self.capture.request_digest,
            capture_digest=selected_capture_digest(self.capture),
            campaign_map_digest=fingerprint(
                "selected-plan-campaign-map",
                {"campaigns": [x.model_dump() for x in self.campaigns]},
            ),
        )

    def pin(self) -> SelectedPlanPinV1:
        return type(self).model_validate(self)._pin()


def selected_local_days(
    requested: ReportingWindow, *, time_zone: str, completed_at: datetime
) -> tuple[date, date]:
    requested = ReportingWindow.model_validate(requested)
    if (
        type(completed_at) is not datetime
        or completed_at.tzinfo is None
        or completed_at.utcoffset() is None
    ):
        raise ValueError("aware capture completion required")
    zone = ZoneInfo(time_zone)
    start = requested.starts_at.astimezone(zone)
    end = requested.ends_at_exclusive.astimezone(zone)
    if (
        start.astimezone(UTC) != datetime.combine(start.date(), time.min, zone).astimezone(UTC)
        or end.astimezone(UTC) != datetime.combine(end.date(), time.min, zone).astimezone(UTC)
        or not 0 < (end.date() - start.date()).days <= 400
        or end.date() > completed_at.astimezone(zone).date()
    ):
        raise ValueError("selected window must contain exact closed local days")
    return start.date(), end.date() - timedelta(days=1)


class SelectedPlanWindowV1(Frozen):
    schema_version: Literal["inlet.selected-plan-window.v1"] = "inlet.selected-plan-window.v1"
    pin: SelectedPlanPinV1
    requested_window: ReportingWindow
    summary: SelectedPlanSummaryV1

    @model_validator(mode="after")
    def scope(self) -> "SelectedPlanWindowV1":
        if self.schema_version != "inlet.selected-plan-window.v1":
            raise ValueError("selected window schema mismatch")
        if self.summary.capture_digest != self.pin.capture_digest:
            raise ValueError("selected summary capture mismatch")
        return self


def project_selected_plan_window(
    graph: SelectedPlanCaptureV1, *, campaign_id: int, requested_window: ReportingWindow
) -> SelectedPlanWindowV1:
    graph = SelectedPlanCaptureV1.model_validate(graph)
    return _PreparedProjection(graph).read(campaign_id, requested_window)


class _PreparedProjection:
    """Internal validated graph/index reuse, never accepts public authority."""

    def __init__(self, graph: SelectedPlanCaptureV1) -> None:
        self.graph = graph
        self.pin = graph._pin()
        self.campaigns = {x.campaign_id: x.native_campaign_id for x in graph.campaigns}
        self.summaries = SelectedSummaryContext(
            graph.capture, graph.capture.request.aggregate, graph.capture.request.selection
        )

    def read(self, campaign_id: int, requested_window: ReportingWindow) -> SelectedPlanWindowV1:
        native = self.campaigns.get(campaign_id)
        if type(campaign_id) is not int or native is None:
            raise ValueError("selected campaign absent from exact mapping")
        capture = self.graph.capture
        starts, ends = selected_local_days(
            requested_window,
            time_zone=capture.request.aggregate.scope.time_zone,
            completed_at=capture.completed_at,
        )
        summary = self.summaries.read(
            campaign_id=campaign_id,
            native_campaign_id=native,
            starts_on=starts,
            ends_on=ends,
        )
        return SelectedPlanWindowV1(
            pin=self.pin,
            requested_window=requested_window,
            summary=SelectedPlanSummaryV1.model_validate(asdict(summary)),
        )


class SelectedPlanProjectionV1(NoAuthority):
    """Private arithmetic proof only; owned reader and catalog checks are separate."""

    captures: tuple[SelectedPlanCaptureV1, ...] = Field(max_length=20)
    windows: tuple[SelectedPlanWindowV1, ...] = Field(max_length=400)

    @model_validator(mode="after")
    def recompute(self) -> "SelectedPlanProjectionV1":
        by_account = {x.source_fence.account: x for x in self.captures}
        if len(by_account) != len(self.captures):
            raise ValueError("one explicit selected capture per account required")
        prepared = {account: _PreparedProjection(graph) for account, graph in by_account.items()}
        slots: set[tuple[int, int, datetime, datetime]] = set()
        for window in self.windows:
            graph = by_account.get(window.pin.account)
            if graph is None:
                raise ValueError("selected window lacks whole capture")
            expected = prepared[window.pin.account].read(
                window.summary.campaign_id, window.requested_window
            )
            if window.pin != expected.pin or window.summary != expected.summary:
                raise ValueError("selected window arithmetic or provenance changed")
            slot = (
                window.pin.account.account_id,
                window.summary.campaign_id,
                window.requested_window.starts_at.astimezone(UTC),
                window.requested_window.ends_at_exclusive.astimezone(UTC),
            )
            if slot in slots:
                raise ValueError("duplicate selected campaign/window")
            slots.add(slot)
        if len(self.model_dump_json().encode()) > MAX_BYTES:
            raise ValueError("selected projection capacity exceeded")
        return self
