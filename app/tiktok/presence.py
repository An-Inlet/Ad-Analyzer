"""Raw generic TikTok campaign observations; selected-event mapping remains unsupported."""

from datetime import date
from typing import Any

from pydantic import TypeAdapter, field_validator, model_validator

from app.campaign_performance.presence_contracts import (
    CountCellV1,
    Frozen,
    IntegerCountCellV1,
    MoneyCellV1,
    NativeId,
    _date,
)
from app.campaign_performance.raw_cells import count_cell, integer_cell, money_cell


class TikTokCampaignPresenceV1(Frozen):
    native_campaign_id: NativeId
    metric_date: date
    impressions: IntegerCountCellV1
    clicks: IntegerCountCellV1
    spend_micros: MoneyCellV1
    aggregate_conversions: CountCellV1
    selected_conversions: CountCellV1
    selected_value_micros: MoneyCellV1

    _day = field_validator("metric_date", mode="before")(_date)

    @model_validator(mode="after")
    def no_selected_mapping(self) -> "TikTokCampaignPresenceV1":
        if any(
            cell.presence != "unsupported"
            for cell in (self.selected_conversions, self.selected_value_micros)
        ):
            raise ValueError("generic TikTok metrics cannot qualify a selected event")
        return self


def parse_generic_campaign_row(
    row: dict[str, Any],
    *,
    advertiser: str,
    starts_on: date,
    ends_on: date,
) -> TikTokCampaignPresenceV1:
    """No objective, pixel, total or account label can supply selected-event meaning.

    Caller must bind the original request to verified account metadata and owned
    inventory. Provider timestamp forms are not guessed or truncated to local days.
    """
    try:
        TypeAdapter(NativeId).validate_python(advertiser)
        if (
            type(starts_on) is not date
            or type(ends_on) is not date
            or not (0 <= (ends_on - starts_on).days <= 30)
        ):
            raise ValueError("invalid reporting dates")
        if row.get("advertiser_id", advertiser) != advertiser:
            raise ValueError("foreign advertiser")
        dimensions, metrics = row["dimensions"], row["metrics"]
        if type(dimensions) is not dict or type(metrics) is not dict:
            raise ValueError("invalid metric objects")
        result = TikTokCampaignPresenceV1(
            native_campaign_id=dimensions["campaign_id"],
            metric_date=dimensions["stat_time_day"],
            impressions=integer_cell(metrics, "impressions"),
            clicks=integer_cell(metrics, "clicks"),
            spend_micros=money_cell(metrics, "spend"),
            aggregate_conversions=count_cell(metrics, "conversion"),
            selected_conversions=CountCellV1(presence="unsupported", value=None),
            selected_value_micros=MoneyCellV1(presence="unsupported", value=None),
        )
        if not starts_on <= result.metric_date <= ends_on:
            raise ValueError("date outside request")
        return result
    except (ValueError, TypeError, KeyError, AttributeError, ArithmeticError):
        raise ValueError("tiktok_raw_observation_unavailable") from None
