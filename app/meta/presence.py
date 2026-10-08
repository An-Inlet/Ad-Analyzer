"""Pure Meta campaign-day presence; not persisted provenance or ownership proof."""

import re
from datetime import date
from typing import Any

from pydantic import field_validator, model_validator

from app.campaign_performance.presence_contracts import (
    AttributionBasisV1,
    CountCellV1,
    Frozen,
    IntegerCountCellV1,
    MoneyCellV1,
    NativeId,
    SelectedEventV1,
)
from app.meta.normalize import decimal_value, metric_values, micros
from app.meta.security import API_VERSION, PURCHASE_ACTIONS, MetaError, identifier

PRESENCE_PRODUCER_CONTRACT = "meta.campaign-day.presence.v1"
QUERY_DESCRIPTOR = f"meta.{API_VERSION}.campaign-day.v1"
UNKNOWN_ATTRIBUTION = AttributionBasisV1(
    click_window_days=None,
    view_window_days=None,
    report_time_basis="unknown",
    provenance="provider_default_unknown",
    producer_contract=PRESENCE_PRODUCER_CONTRACT,
)


class MetaPresenceCellsV1(Frozen):
    native_campaign_id: NativeId
    metric_date: date
    selected_event: SelectedEventV1
    impressions: IntegerCountCellV1
    clicks: IntegerCountCellV1
    spend_micros: MoneyCellV1
    selected_conversions: CountCellV1
    selected_value_micros: MoneyCellV1

    @field_validator("metric_date", mode="before")
    @classmethod
    def exact_day(cls, value: Any) -> date:
        if type(value) is date:
            return value
        if type(value) is str and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
            return date.fromisoformat(value)
        raise ValueError("exact ISO metric date required")

    @model_validator(mode="after")
    def selected_cells(self) -> "MetaPresenceCellsV1":
        if self.selected_event.provenance != "explicit_selected" and (
            self.selected_conversions.presence == "present"
            or self.selected_value_micros.presence == "present"
        ):
            raise ValueError("unselected event cannot qualify selected metrics")
        if (
            self.selected_event.native_event_id not in PURCHASE_ACTIONS
            and self.selected_value_micros.presence == "present"
        ):
            raise ValueError("selected value unsupported for this event")
        return self


def _selected(items: object, event: str) -> object | None:
    """Membership only after legacy validation; absence is never a numeric zero."""
    if items is None:
        return None
    if not isinstance(items, list):
        raise MetaError("meta_invalid_metric")
    for item in items:
        if not isinstance(item, dict):
            raise MetaError("meta_invalid_metric")
        if item.get("action_type") == event:
            value: object = item["value"]  # Legacy validation rejected null/missing values.
            return value
    return None


def parse_meta_presence(
    source: dict[str, Any],
    *,
    expected_advertiser: str,
    currency: str,
    starts_on: date,
    ends_on: date,
    selected_event: str | None,
) -> MetaPresenceCellsV1:
    """Retain original field presence and match unchanged legacy numeric semantics.

    Money follows existing decimal-to-micros ROUND_HALF_UP. Selected counts never
    round: more than six fractional places fail qualification. Unsupported value
    event lists are ignored exactly as by metric_values, not promoted to evidence.
    """
    try:
        identifier(expected_advertiser)
        if (
            type(currency) is not str
            or re.fullmatch(r"[A-Z]{3}", currency) is None
            or type(starts_on) is not date
            or type(ends_on) is not date
            or starts_on > ends_on
            or (selected_event is not None and type(selected_event) is not str)
        ):
            raise ValueError("invalid reporting profile")
        native = identifier(source["campaign_id"])
        day = MetaPresenceCellsV1.exact_day(source["date_start"])
        if source["date_start"] != day.isoformat() or source["date_stop"] != day.isoformat():
            raise ValueError("metric dates must be exact ISO days")
        normalized = metric_values(
            source, expected_advertiser, currency, starts_on, ends_on, selected_event
        )
        event = selected_event or None
        raw_count = _selected(source.get("actions"), event) if event else None
        raw_value = (
            _selected(source.get("action_values"), event) if event in PURCHASE_ACTIONS else None
        )
        counts = CountCellV1(
            presence="unsupported"
            if event is None
            else "missing"
            if raw_count is None
            else "present",
            value=None if raw_count is None else decimal_value(raw_count),
        )
        money = MoneyCellV1(
            presence=(
                "unsupported"
                if event not in PURCHASE_ACTIONS
                else "missing"
                if raw_value is None
                else "present"
            ),
            value=None if raw_value is None else micros(raw_value),
        )
        if (counts.value is not None and counts.value != normalized["conversions"]) or (
            money.value is not None and money.value != normalized["conversion_value_micros"]
        ):
            raise ValueError("presence and legacy numeric values differ")
        return MetaPresenceCellsV1(
            native_campaign_id=native,
            metric_date=normalized["metric_date"],
            selected_event=SelectedEventV1(
                provenance="explicit_selected" if event else "unavailable",
                native_event_id=event,
                label=None,
            ),
            impressions=IntegerCountCellV1(presence="present", value=normalized["impressions"]),
            clicks=IntegerCountCellV1(presence="present", value=normalized["clicks"]),
            spend_micros=MoneyCellV1(presence="present", value=normalized["cost_micros"]),
            selected_conversions=counts,
            selected_value_micros=money,
        )
    except (KeyError, TypeError, ValueError):
        raise MetaError("meta_invalid_metric") from None
