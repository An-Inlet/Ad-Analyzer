"""Pure observed-row aggregation; no ownership, import or causal qualification."""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Context, Decimal, localcontext
from typing import Literal

from pydantic import TypeAdapter

from app.campaign_performance.presence_contracts import (
    CountCellV1,
    IntegerCountCellV1,
    MoneyCellV1,
    NativeId,
    Positive,
    ReportedMetricPresenceV1,
    ReportingSemanticsV1,
    validate_presence,
)


@dataclass(frozen=True)
class MetricPresenceSummary:
    value: Decimal | int | None
    present_days: int
    missing_days: int
    unsupported_days: int
    legacy_unknown_days: int
    coverage: Literal["observed_requested_days", "partial", "unavailable"]


@dataclass(frozen=True)
class CampaignPresenceSummary:
    header: ReportingSemanticsV1
    campaign_id: int
    native_campaign_id: str
    requested_days: int
    returned_days: int
    missing_calendar_days: int
    impressions: MetricPresenceSummary
    clicks: MetricPresenceSummary
    spend_micros: MetricPresenceSummary
    selected_conversions: MetricPresenceSummary
    selected_value_micros: MetricPresenceSummary

    @property
    def selected_zero_for_requested_window(self) -> bool:
        """Observed selected event count only, never causal sales or change authority."""
        return (
            self.header.selected_event.provenance == "explicit_selected"
            and self.selected_conversions.coverage == "observed_requested_days"
            and self.selected_conversions.value == 0
        )


def summarize_presence(
    header: ReportingSemanticsV1,
    facts: Sequence[ReportedMetricPresenceV1],
    *,
    campaign_id: int,
    native_campaign_id: str,
) -> CampaignPresenceSummary:
    """Caller supplies whole validated completion facts, never a selected subset."""
    header = ReportingSemanticsV1.model_validate(header)
    validate_presence(header, facts)
    campaign_id = TypeAdapter(Positive).validate_python(campaign_id)
    native_campaign_id = TypeAdapter(NativeId).validate_python(native_campaign_id)
    rows = []
    for original in facts:
        fact = ReportedMetricPresenceV1.model_validate(original)
        if (fact.campaign_id == campaign_id) != (fact.native_campaign_id == native_campaign_id):
            raise ValueError("requested local/native campaign identity mismatch")
        if fact.campaign_id == campaign_id:
            rows.append(fact)
    days = (header.requested_ends_on - header.requested_starts_on).days + 1
    complete = (
        header.pagination_complete
        and header.closed_requested_period
        and header.actual_starts_on == header.requested_starts_on
        and header.actual_ends_on == header.requested_ends_on
        and len(rows) == days
    )

    def aggregate(
        cells: Sequence[CountCellV1 | IntegerCountCellV1 | MoneyCellV1],
    ) -> MetricPresenceSummary:
        states = [cell.presence for cell in cells]
        values = [cell.value for cell in cells if cell.value is not None]
        # Fix precision independently of caller context;400 reviewed Decimal
        # cells fit well within50digits. Integer money/count sums stay integer.
        with localcontext(Context(prec=50)):
            value = sum(values) if values else None
        present = states.count("present")
        return MetricPresenceSummary(
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

    return CampaignPresenceSummary(
        header=header,
        campaign_id=campaign_id,
        native_campaign_id=native_campaign_id,
        requested_days=days,
        returned_days=len(rows),
        missing_calendar_days=days - len(rows),
        impressions=aggregate([r.impressions for r in rows]),
        clicks=aggregate([r.clicks for r in rows]),
        spend_micros=aggregate([r.spend_micros for r in rows]),
        selected_conversions=aggregate([r.selected_conversions for r in rows]),
        selected_value_micros=aggregate([r.selected_value_micros for r in rows]),
    )
