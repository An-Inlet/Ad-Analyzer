"""Strict raw JSON/scalar decoding before legacy defaults; no provider authority."""

import json
import re
from decimal import Context, Decimal, localcontext
from typing import Any

from app.campaign_performance.presence_contracts import (
    MAX_INTEGER_COUNT,
    MAX_MONEY_MICROS,
    CountCellV1,
    IntegerCountCellV1,
    MoneyCellV1,
)


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def _nonfinite(value: str) -> None:
    raise ValueError("nonfinite JSON token")


def exact_json(raw: bytes, *, limit: int) -> dict[str, Any]:
    if type(raw) is not bytes or len(raw) > limit:
        raise ValueError("raw response byte bound")
    try:
        result = json.loads(
            raw.decode("utf-8"),
            parse_float=Decimal,
            parse_constant=_nonfinite,
            object_pairs_hook=_object,
        )
    except (ValueError, RecursionError):
        raise ValueError("invalid raw JSON") from None
    if not isinstance(result, dict):
        raise ValueError("JSON object required")
    return result


def count_cell(values: dict[str, Any], key: str) -> CountCellV1:
    if key not in values:
        return CountCellV1(presence="missing", value=None)
    # Null is malformed, distinct from an absent supported field.
    return CountCellV1(presence="present", value=values[key])


def integer_cell(values: dict[str, Any], key: str) -> IntegerCountCellV1:
    if key not in values:
        return IntegerCountCellV1(presence="missing", value=None)
    value = values[key]
    if type(value) is str and re.fullmatch(r"(?:0|[1-9][0-9]{0,9})", value):
        value = int(value)
    if type(value) is not int or not 0 <= value <= MAX_INTEGER_COUNT:
        raise ValueError("invalid integer metric")
    return IntegerCountCellV1(presence="present", value=value)


def money_cell(values: dict[str, Any], key: str) -> MoneyCellV1:
    if key not in values:
        return MoneyCellV1(presence="missing", value=None)
    value = values[key]
    if type(value) not in (str, int, Decimal):
        raise ValueError("exact decimal money required")
    if isinstance(value, str) and (
        len(value) > 24 or re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\.[0-9]{1,6})?", value) is None
    ):
        raise ValueError("invalid exact decimal money")
    number = Decimal(value)
    # Conservative prebound prevents huge-exponent arithmetic. Exact micros bound
    # follows inside an explicit context, independent of a caller's precision.
    if not number.is_finite() or not 0 <= number <= MAX_MONEY_MICROS:
        raise ValueError("money outside bounds")
    exponent = number.as_tuple().exponent
    if not isinstance(exponent, int) or exponent < -6:
        raise ValueError("money exceeds six fractional places")
    with localcontext(Context(prec=50)):
        micros = number * 1_000_000
        if micros != micros.to_integral_value() or micros > MAX_MONEY_MICROS:
            raise ValueError("money not exactly representable")
    return MoneyCellV1(presence="present", value=int(micros))
