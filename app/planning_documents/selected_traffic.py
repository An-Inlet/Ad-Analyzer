"""Pure immutable raw traffic projections, separate from selected conversions."""

from datetime import UTC, date
from typing import Annotated, Any, Literal

from pydantic import Field, field_validator, model_validator

from app.campaign_performance.presence_contracts import (
    MAX_INTEGER_COUNT,
    MAX_MONEY_MICROS,
    Frozen,
    NativeId,
    Positive,
    ReportedMetricPresenceV1,
    ReportingSemanticsV1,
    _canonical,
    _date,
    validate_presence,
)
from app.campaign_performance.range_receipt_contracts import RangeReceiptV1
from app.campaign_performance.selected_contracts import AggregateDependencyV1, _instant
from app.planning_documents.common import fingerprint
from app.planning_documents.context import ReportingWindow
from app.planning_documents.selected_plan_contracts import SelectedCampaignBindingV1
from app.planning_documents.selected_plan_evidence import selected_local_days
from app.planning_documents.selected_traffic_contracts import (
    SelectedTrafficPinV1 as SelectedTrafficPinV1,
)
from app.planning_documents.source_contracts import SourceFence

PROFILE = "google.v24.campaign-day.raw-required-traffic.v1"
Days = Annotated[int, Field(strict=True, ge=0, le=400)]


def _window(value: Any) -> ReportingWindow:
    data = value.model_dump(mode="python") if isinstance(value, ReportingWindow) else value
    if not isinstance(data, dict):
        raise ValueError("reporting window required")
    for name in ("starts_at", "ends_at_exclusive"):
        _instant(data.get(name))
    checked = ReportingWindow.model_validate(data)
    return ReportingWindow(
        starts_at=checked.starts_at.astimezone(UTC),
        ends_at_exclusive=checked.ends_at_exclusive.astimezone(UTC),
    )


class RawRangeTrafficGraphV1(Frozen):
    receipt: RangeReceiptV1
    header: ReportingSemanticsV1
    facts: tuple[ReportedMetricPresenceV1, ...] = Field(max_length=50_000)
    campaigns: tuple[SelectedCampaignBindingV1, ...] = Field(max_length=10_000)
    source_fence: SourceFence

    @model_validator(mode="after")
    def graph(self) -> "RawRangeTrafficGraphV1":
        receipt, header = self.receipt, self.header
        validate_presence(header, self.facts)
        scope = receipt.final_scope
        metadata = scope.model_dump(exclude={"native_account_id"})
        if (
            any(getattr(header, name) != value for name, value in metadata.items())
            or header.completion_id != receipt.completion_id
            or header.legacy_manifest_digest != receipt.manifest_digest
            or header.producer_contract != PROFILE
            or header.query_descriptor != receipt.query_version
            or header.completed_at.astimezone(UTC) != receipt.completed_at.astimezone(UTC)
            or header.fact_count != receipt.row_count
            or header.requested_starts_on != receipt.requested_starts_on
            or header.actual_starts_on != receipt.requested_starts_on
            or header.requested_ends_on != receipt.requested_ends_on
            or header.actual_ends_on != receipt.requested_ends_on
            or not header.pagination_complete
            or not header.closed_requested_period
            or header.selected_event.model_dump()
            != {"provenance": "generic", "native_event_id": None, "label": None}
            or header.attribution.model_dump()
            != {
                "click_window_days": None,
                "view_window_days": None,
                "report_time_basis": "unknown",
                "provenance": "provider_default_unknown",
                "producer_contract": PROFILE,
            }
        ):
            raise ValueError("raw traffic receipt/header mismatch")
        mapping = {x.campaign_id: x.native_campaign_id for x in self.campaigns}
        keys = tuple((x.campaign_id, x.metric_date) for x in self.facts)
        if (
            len(mapping) != len(self.campaigns)
            or len(set(mapping.values())) != len(mapping)
            or tuple(mapping) != tuple(sorted(mapping))
            or keys != tuple(sorted(keys))
        ):
            raise ValueError("canonical complete campaign/fact mapping required")
        for fact in self.facts:
            if (
                mapping.get(fact.campaign_id) != fact.native_campaign_id
                or not receipt.requested_starts_on <= fact.metric_date <= receipt.requested_ends_on
                or any(
                    cell.presence != "present"
                    for cell in (fact.impressions, fact.clicks, fact.spend_micros)
                )
                or fact.selected_conversions.presence != "unsupported"
                or fact.selected_value_micros.presence != "unsupported"
            ):
                raise ValueError("raw traffic cell or campaign mismatch")
        self._pin()
        if len(_canonical(self)) > 32 * 1024 * 1024:
            raise ValueError("raw traffic graph capacity exceeded")
        return self

    def _pin(self) -> SelectedTrafficPinV1:
        receipt = self.receipt
        return SelectedTrafficPinV1(
            source_fence=self.source_fence,
            aggregate=AggregateDependencyV1(
                completion_id=receipt.completion_id,
                manifest_digest=receipt.manifest_digest,
                scope=receipt.final_scope,
                starts_on=receipt.requested_starts_on,
                ends_on=receipt.requested_ends_on,
            ),
            range_request_id=receipt.request_id,
            range_receipt_digest=receipt.digest(),
            presence_header_digest=fingerprint(
                "raw-range-traffic-header", self.header.model_dump(mode="json")
            ),
            presence_fact_digest=self.header.fact_digest,
            campaign_map_digest=fingerprint(
                "selected-plan-campaign-map",
                {"campaigns": [x.model_dump() for x in self.campaigns]},
            ),
        )

    def pin(self) -> SelectedTrafficPinV1:
        return type(self).model_validate(self)._pin()


class TrafficMetricSummaryV1(Frozen):
    value: Annotated[int, Field(strict=True, ge=0, le=400 * MAX_MONEY_MICROS)] | None
    present_days: Days
    missing_days: Days
    unsupported_days: Days
    legacy_unknown_days: Days
    coverage: Literal["observed_requested_days", "partial", "unavailable"]

    @model_validator(mode="after")
    def consistency(self) -> "TrafficMetricSummaryV1":
        total = (
            self.present_days + self.missing_days + self.unsupported_days + self.legacy_unknown_days
        )
        expected = (
            "unavailable"
            if not self.present_days
            else "observed_requested_days"
            if self.present_days == total
            else "partial"
        )
        if (
            not 1 <= total <= 400
            or (self.value is not None) != bool(self.present_days)
            or self.coverage != expected
        ):
            raise ValueError("traffic summary coverage mismatch")
        return self


class SelectedTrafficWindowV1(Frozen):
    schema_version: Literal["inlet.selected-traffic-window.v1"] = "inlet.selected-traffic-window.v1"
    pin: SelectedTrafficPinV1
    requested_window: ReportingWindow
    campaign_id: Positive
    native_campaign_id: NativeId
    starts_on: date
    ends_on: date
    requested_days: Annotated[int, Field(strict=True, ge=1, le=400)]
    returned_days: Days
    missing_calendar_days: Days
    impressions: TrafficMetricSummaryV1
    clicks: TrafficMetricSummaryV1
    spend_micros: TrafficMetricSummaryV1

    _dates = field_validator("starts_on", "ends_on", mode="before")(_date)
    _requested = field_validator("requested_window", mode="before")(_window)

    @model_validator(mode="after")
    def coverage(self) -> "SelectedTrafficWindowV1":
        scope = self.pin.aggregate
        # End-of-window midnight is sufficient to validate alignment, not freshness.
        starts, ends = selected_local_days(
            self.requested_window,
            time_zone=scope.scope.time_zone,
            completed_at=self.requested_window.ends_at_exclusive,
        )
        if (
            (starts, ends) != (self.starts_on, self.ends_on)
            or not scope.starts_on <= starts <= ends <= scope.ends_on
            or self.requested_days != (ends - starts).days + 1
            or self.returned_days + self.missing_calendar_days != self.requested_days
        ):
            raise ValueError("traffic window bounds mismatch")
        for cell in (self.impressions, self.clicks, self.spend_micros):
            if (
                cell.present_days != self.returned_days
                or cell.missing_days != self.missing_calendar_days
                or cell.unsupported_days
                or cell.legacy_unknown_days
            ):
                raise ValueError("traffic window cell coverage mismatch")
        if any(
            x.value is not None and x.value > self.returned_days * MAX_INTEGER_COUNT
            for x in (self.impressions, self.clicks)
        ):
            raise ValueError("traffic count capacity exceeded")
        if (
            self.spend_micros.value is not None
            and self.spend_micros.value > self.returned_days * MAX_MONEY_MICROS
        ):
            raise ValueError("traffic money capacity exceeded")
        return self


def project_raw_range_traffic(
    graph: RawRangeTrafficGraphV1, *, campaign_id: int, requested_window: ReportingWindow
) -> SelectedTrafficWindowV1:
    return PreparedRawRangeTrafficProjection(graph).read(campaign_id, requested_window)


class PreparedRawRangeTrafficProjection:
    """Validate and index the immutable graph once; caller still owns SQL authority."""

    def __init__(self, graph: RawRangeTrafficGraphV1) -> None:
        self._graph = RawRangeTrafficGraphV1.model_validate(graph)
        self._pin = self._graph._pin()
        self._mapping = {x.campaign_id: x.native_campaign_id for x in self._graph.campaigns}
        self._rows: dict[int, list[ReportedMetricPresenceV1]] = {}
        for fact in self._graph.facts:
            self._rows.setdefault(fact.campaign_id, []).append(fact)

    @property
    def pin(self) -> SelectedTrafficPinV1:
        return self._pin

    def snapshot(self) -> RawRangeTrafficGraphV1:
        return self._graph

    def read(self, campaign_id: int, requested_window: ReportingWindow) -> SelectedTrafficWindowV1:
        graph = self._graph
        mapping = self._mapping
        requested_window = _window(requested_window)
        if type(campaign_id) is not int or campaign_id not in mapping:
            raise ValueError("traffic campaign absent from mapping")
        starts, ends = selected_local_days(
            requested_window,
            time_zone=graph.header.time_zone,
            completed_at=graph.header.completed_at,
        )
        if (
            not graph.receipt.requested_starts_on
            <= starts
            <= ends
            <= graph.receipt.requested_ends_on
        ):
            raise ValueError("traffic window outside captured interval")
        rows = [x for x in self._rows.get(campaign_id, ()) if starts <= x.metric_date <= ends]
        days = (ends - starts).days + 1

        def summary(name: str) -> TrafficMetricSummaryV1:
            return TrafficMetricSummaryV1(
                value=sum(getattr(x, name).value for x in rows) if rows else None,
                present_days=len(rows),
                missing_days=days - len(rows),
                unsupported_days=0,
                legacy_unknown_days=0,
                coverage="observed_requested_days"
                if len(rows) == days
                else "partial"
                if rows
                else "unavailable",
            )

        return SelectedTrafficWindowV1(
            pin=self._pin,
            requested_window=requested_window,
            campaign_id=campaign_id,
            native_campaign_id=mapping[campaign_id],
            starts_on=starts,
            ends_on=ends,
            requested_days=days,
            returned_days=len(rows),
            missing_calendar_days=days - len(rows),
            impressions=summary("impressions"),
            clicks=summary("clicks"),
            spend_micros=summary("spend_micros"),
        )
