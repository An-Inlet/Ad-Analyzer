"""Pure calendar slices of an unchanged report; no ownership or whole-graph proof."""

from datetime import UTC, date, datetime, time, timedelta
from decimal import Context, Decimal, localcontext
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import Field, field_validator, model_validator

from app.campaign_performance.presence_contracts import (
    Digest,
    Frozen,
    ReportedMetricPresenceV1,
    presence_digest,
)
from app.campaign_performance.presence_report import CampaignPerformanceV3, MetricSummaryV1
from app.planning_documents.common import fingerprint
from app.planning_documents.context import ReportingWindow

MAX_DOCUMENT_BYTES = 2 * 1024 * 1024
Reason = Literal["outside_imported_window", "unaligned_local_days", "requested_days_not_closed"]


class WindowProjectionUnavailable(ValueError):
    def __init__(self, reason: Reason) -> None:
        if reason not in {
            "outside_imported_window",
            "unaligned_local_days",
            "requested_days_not_closed",
        }:
            raise ValueError("unknown window incompatibility")
        self.reason = reason
        super().__init__(reason)


class WindowCampaignSummaryV1(Frozen):
    requested_days: int = Field(strict=True, ge=1, le=400)
    returned_days: int = Field(strict=True, ge=0, le=400)
    missing_calendar_days: int = Field(strict=True, ge=0, le=400)
    impressions: MetricSummaryV1
    clicks: MetricSummaryV1
    spend_micros: MetricSummaryV1
    selected_conversions: MetricSummaryV1
    selected_value_micros: MetricSummaryV1
    selected_zero_for_requested_window: bool = Field(strict=True)


def _midnight(instant: datetime, zone: ZoneInfo) -> date:
    local = instant.astimezone(zone)
    if local.time() != time():
        raise WindowProjectionUnavailable("unaligned_local_days")
    naive = datetime.combine(local.date(), time())
    possibilities = {
        candidate.astimezone(UTC)
        for fold in (0, 1)
        if (candidate := naive.replace(tzinfo=zone, fold=fold))
        .astimezone(UTC)
        .astimezone(zone)
        .replace(tzinfo=None)
        == naive
    }
    if len(possibilities) != 1 or instant.astimezone(UTC) not in possibilities:
        raise WindowProjectionUnavailable("unaligned_local_days")
    return local.date()


def _derive(
    original: CampaignPerformanceV3,
    window: ReportingWindow,
) -> tuple[date, date, tuple[ReportedMetricPresenceV1, ...], WindowCampaignSummaryV1]:
    h = original.presence
    zone = ZoneInfo(h.time_zone)
    start = _midnight(window.starts_at, zone)
    end = _midnight(window.ends_at_exclusive, zone) - timedelta(days=1)
    days = (end - start).days + 1
    if not 1 <= days <= 400:
        raise ValueError("requested calendar day capacity exceeded")
    if start < h.requested_starts_on or end > h.requested_ends_on:
        raise WindowProjectionUnavailable("outside_imported_window")
    if end >= h.completed_at.astimezone(zone).date():
        raise WindowProjectionUnavailable("requested_days_not_closed")
    rows = tuple(
        sorted(
            (r for r in original.campaign_facts if start <= r.metric_date <= end),
            key=lambda r: r.metric_date,
        )
    )
    complete = (
        h.pagination_complete
        and h.closed_requested_period
        and h.actual_starts_on <= start
        and end <= h.actual_ends_on
        and len(rows) == days
    )
    metrics: dict[str, MetricSummaryV1] = {}
    for name in (
        "impressions",
        "clicks",
        "spend_micros",
        "selected_conversions",
        "selected_value_micros",
    ):
        cells = [getattr(r, name) for r in rows]
        states = [c.presence for c in cells]
        values = [c.value for c in cells if c.value is not None]
        with localcontext(Context(prec=50)):
            value = sum(values) if values else None
        if isinstance(value, Decimal):
            rendered = format(value, "f")
            value = rendered.rstrip("0").rstrip(".") if "." in rendered else rendered
            if value == "-0":
                value = "0"
        present = states.count("present")
        metrics[name] = MetricSummaryV1(
            value=value,
            present_days=present,
            missing_days=states.count("missing"),
            unsupported_days=states.count("unsupported"),
            legacy_unknown_days=states.count("legacy_unknown"),
            coverage="unavailable"
            if not present
            else "observed_requested_days"
            if complete and present == days
            else "partial",
        )
    selected = metrics["selected_conversions"]
    summary = WindowCampaignSummaryV1(
        requested_days=days,
        returned_days=len(rows),
        missing_calendar_days=days - len(rows),
        selected_zero_for_requested_window=(
            h.selected_event.provenance == "explicit_selected"
            and selected.coverage == "observed_requested_days"
            and selected.value == "0"
        ),
        **metrics,
    )
    return start, end, rows, summary


class RequestedWindowPerformanceV1(Frozen):
    schema_version: Literal["inlet.requested-window-campaign-performance.v1"] = (
        "inlet.requested-window-campaign-performance.v1"
    )
    projection_version: Literal["inlet.reporting-window-projection.v1"] = (
        "inlet.reporting-window-projection.v1"
    )
    original: CampaignPerformanceV3
    original_document_digest: Digest
    requested_window: ReportingWindow
    requested_starts_on: date
    requested_ends_on: date
    selected_facts: tuple[ReportedMetricPresenceV1, ...] = Field(max_length=400)
    selected_fact_digest: Digest
    summary: WindowCampaignSummaryV1
    derivation: Literal["local_projection_of_imported_campaign_days"] = (
        "local_projection_of_imported_campaign_days"
    )
    causal_attribution: Literal["unavailable"] = "unavailable"
    spending_authorized: Literal[False] = False

    @field_validator("spending_authorized", mode="before")
    @classmethod
    def no_numeric_authority(cls, value: Any) -> Any:
        if type(value) is not bool:
            raise ValueError("authority must be exact boolean false")
        return value

    @field_validator("original", mode="wrap")
    @classmethod
    def original_context(cls, value: Any, handler: Any) -> CampaignPerformanceV3:
        with localcontext(Context(prec=50)):
            checked: CampaignPerformanceV3 = handler(value)
        return checked

    @field_validator("requested_window", mode="before")
    @classmethod
    def window_copy(cls, value: Any) -> Any:
        return value.model_dump(mode="python") if isinstance(value, ReportingWindow) else value

    @field_validator("requested_starts_on", "requested_ends_on", mode="before")
    @classmethod
    def exact_date(cls, value: Any) -> date:
        if type(value) is date:
            return value
        if type(value) is str and len(value) == 10:
            parsed = date.fromisoformat(value)
            if parsed.isoformat() == value:
                return parsed
        raise ValueError("exact ISO calendar date required")

    @model_validator(mode="after")
    def derived(self) -> "RequestedWindowPerformanceV1":
        try:
            start, end, rows, summary = _derive(self.original, self.requested_window)
        except WindowProjectionUnavailable as error:
            # A forged wrapper is invalid, not a known-data gap for an adapter.
            raise ValueError("invalid requested window wrapper") from error
        if (
            (self.requested_starts_on, self.requested_ends_on) != (start, end)
            or self.selected_facts != rows
            or self.summary != summary
            or self.original_document_digest
            != fingerprint("campaign-performance", self.original.model_dump(mode="json"))
            or self.selected_fact_digest != presence_digest(rows)
        ):
            raise ValueError("requested window projection differs from exact derivation")
        if len(self.model_dump_json().encode("utf-8")) > MAX_DOCUMENT_BYTES:
            raise ValueError("requested window document capacity exceeded")
        return self


def project_requested_window(
    original: CampaignPerformanceV3,
    *,
    requested_window: ReportingWindow,
) -> RequestedWindowPerformanceV1:
    with localcontext(Context(prec=50)):
        original = CampaignPerformanceV3.model_validate(original)
    requested_window = ReportingWindow.model_validate(requested_window.model_dump(mode="python"))
    start, end, rows, summary = _derive(original, requested_window)
    return RequestedWindowPerformanceV1(
        original=original,
        original_document_digest=fingerprint(
            "campaign-performance", original.model_dump(mode="json")
        ),
        requested_window=requested_window,
        requested_starts_on=start,
        requested_ends_on=end,
        selected_facts=rows,
        selected_fact_digest=presence_digest(rows),
        summary=summary,
    )
