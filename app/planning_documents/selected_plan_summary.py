"""Strict arithmetic receipt values; full-capture recomputation remains required."""

import re
from datetime import date
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import Field, field_validator

from app.campaign_performance.presence_contracts import MAX_MONEY_MICROS, NativeId, _date
from app.planning_documents.common import Digest, Frozen, Positive

Days = Annotated[int, Field(strict=True, ge=0, le=400)]


class SelectedMetricSummaryV1(Frozen):
    present_days: Days
    missing_days: Days
    unsupported_days: Days
    legacy_unknown_days: Days
    coverage: Literal["observed_requested_days", "partial", "unavailable"]


class SelectedCountSummaryV1(SelectedMetricSummaryV1):
    value: Decimal | None

    @field_validator("value", mode="before")
    @classmethod
    def exact_decimal(cls, value: Any) -> Decimal | None:
        if value is None:
            return None
        # Decimal JSON is deliberately a string; binary floats/bools/integers are
        # not count encodings. Summation and roundtrips preserve all six places.
        if type(value) is str:
            if (
                len(value) > 32
                or re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\.[0-9]{1,6})?", value) is None
            ):
                raise ValueError("bounded decimal required")
            try:
                value = Decimal(value)
            except ArithmeticError:
                raise ValueError("exact decimal required") from None
        if (
            type(value) is not Decimal
            or not value.is_finite()
            or not 0 <= value <= Decimal("400000000000000")
            or not isinstance(value.as_tuple().exponent, int)
            or int(value.as_tuple().exponent) < -6
        ):
            raise ValueError("exact bounded decimal count required")
        return value


class SelectedMoneySummaryV1(SelectedMetricSummaryV1):
    value: Annotated[int, Field(strict=True, ge=0, le=400 * MAX_MONEY_MICROS)] | None


class SelectedPlanSummaryV1(Frozen):
    capture_digest: Digest
    campaign_id: Positive
    native_campaign_id: NativeId
    starts_on: date
    ends_on: date
    requested_days: Annotated[int, Field(strict=True, ge=1, le=400)]
    returned_days: Days
    missing_calendar_days: Days
    conversions: SelectedCountSummaryV1
    value_micros: SelectedMoneySummaryV1
    zero_for_requested_window: Annotated[bool, Field(strict=True)]

    _dates = field_validator("starts_on", "ends_on", mode="before")(_date)
