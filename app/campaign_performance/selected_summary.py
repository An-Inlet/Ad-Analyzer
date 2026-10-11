"""Pure selected observations for future plan adapters, never owned-reader proof."""

from dataclasses import dataclass
from datetime import date
from decimal import Context, Decimal, localcontext

from pydantic import TypeAdapter

from app.campaign_performance.presence_contracts import NativeId, Positive, _date
from app.campaign_performance.presence_summary import MetricPresenceSummary
from app.campaign_performance.selected_contracts import (
    AggregateDependencyV1,
    CustomerEventSelectionV1,
    SelectedCampaignDayV1,
    SelectedCaptureV1,
    selected_capture_digest,
    validate_selected_dependencies,
)


@dataclass(frozen=True)
class SelectedCampaignSummary:
    capture_digest: str
    campaign_id: int
    native_campaign_id: str
    starts_on: date
    ends_on: date
    requested_days: int
    returned_days: int
    missing_calendar_days: int
    conversions: MetricPresenceSummary
    value_micros: MetricPresenceSummary
    zero_for_requested_window: bool


def summarize_selected_capture(
    capture: SelectedCaptureV1,
    *,
    current_aggregate: AggregateDependencyV1,
    current_selection: CustomerEventSelectionV1,
    campaign_id: int,
    native_campaign_id: str,
    starts_on: date,
    ends_on: date,
) -> SelectedCampaignSummary:
    """Validate the whole graph before slicing; require caller-loaded dependencies.

    All inputs remain untrusted DTOs: the eventual service must load dependencies
    through original-session authorization and current owned storage. This function
    does no I/O and cannot certify the provider query, freshness or customer access.
    """
    return SelectedSummaryContext(capture, current_aggregate, current_selection).read(
        campaign_id=campaign_id,
        native_campaign_id=native_campaign_id,
        starts_on=starts_on,
        ends_on=ends_on,
    )


class SelectedSummaryContext:
    """Validate once and index a bounded immutable graph; no owned SQL authority."""

    def __init__(
        self,
        capture: SelectedCaptureV1,
        aggregate: AggregateDependencyV1,
        selection: CustomerEventSelectionV1,
    ) -> None:
        self._capture = SelectedCaptureV1.model_validate(capture)
        validate_selected_dependencies(self._capture, aggregate, selection)
        self._digest = selected_capture_digest(self._capture)
        self._rows: dict[int, list[SelectedCampaignDayV1]] = {}
        self._native: dict[str, int] = {}
        for fact in self._capture.facts:
            self._rows.setdefault(fact.campaign_id, []).append(fact)
            self._native[fact.native_campaign_id] = fact.campaign_id

    def read(
        self, *, campaign_id: int, native_campaign_id: str, starts_on: date, ends_on: date
    ) -> SelectedCampaignSummary:
        campaign_id = TypeAdapter(Positive).validate_python(campaign_id)
        native_campaign_id = TypeAdapter(NativeId).validate_python(native_campaign_id)
        starts_on, ends_on = _date(starts_on), _date(ends_on)
        request = self._capture.request
        if not request.requested_starts_on <= starts_on <= ends_on <= request.requested_ends_on:
            raise ValueError("selected summary outside captured window")
        candidates = self._rows.get(campaign_id, [])
        if (
            candidates and candidates[0].native_campaign_id != native_campaign_id
        ) or self._native.get(native_campaign_id, campaign_id) != campaign_id:
            raise ValueError("selected summary campaign identity mismatch")
        rows = [fact for fact in candidates if starts_on <= fact.metric_date <= ends_on]
        days = (ends_on - starts_on).days + 1

        def summary(field: str) -> MetricPresenceSummary:
            cells = [getattr(row, field) for row in rows]
            present = sum(cell.presence == "present" for cell in cells)
            with localcontext(Context(prec=50)):
                value: Decimal | int | None = (
                    sum((cell.value for cell in cells if cell.value is not None), 0)
                    if present
                    else None
                )
            return MetricPresenceSummary(
                value=value,
                present_days=present,
                missing_days=sum(cell.presence == "missing" for cell in cells),
                unsupported_days=sum(cell.presence == "unsupported" for cell in cells),
                legacy_unknown_days=sum(cell.presence == "legacy_unknown" for cell in cells),
                coverage="unavailable"
                if not present
                else ("observed_requested_days" if present == days else "partial"),
            )

        conversions, value = summary("selected_conversions"), summary("selected_value_micros")
        return SelectedCampaignSummary(
            capture_digest=self._digest,
            campaign_id=campaign_id,
            native_campaign_id=native_campaign_id,
            starts_on=starts_on,
            ends_on=ends_on,
            requested_days=days,
            returned_days=len(rows),
            missing_calendar_days=days - len(rows),
            conversions=conversions,
            value_micros=value,
            zero_for_requested_window=(
                self._capture.capability == "supported"
                and conversions.coverage == "observed_requested_days"
                and conversions.value == 0
            ),
        )
