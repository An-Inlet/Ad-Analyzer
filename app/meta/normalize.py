import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.meta.security import CONVERSION_ACTIONS, PURCHASE_ACTIONS, MetaError, identifier


def account_metadata(data: dict[str, Any]) -> dict[str, str]:
    try:
        currency = str(data["currency"])
        if not re.fullmatch(r"[A-Z]{3}", currency):
            raise ValueError("currency")
        zone = str(data["timezone_name"])
        ZoneInfo(zone)
        name = str(data["name"]).strip()[:255]
        if not name:
            raise ValueError("name")
        return {
            "account_id": identifier(data["account_id"]),
            "name": name,
            "currency_code": currency,
            "time_zone": zone,
        }
    except (KeyError, TypeError, ValueError, ZoneInfoNotFoundError):
        raise MetaError("meta_invalid_account") from None


def decimal_value(value: object, *, maximum: Decimal = Decimal("999999999999")) -> Decimal:
    try:
        if isinstance(value, bool) or not isinstance(value, str | int | Decimal):
            raise ValueError("number")
        result = Decimal(value)
        if not result.is_finite() or not 0 <= result <= maximum:
            raise ValueError("range")
        return result
    except (InvalidOperation, TypeError, ValueError):
        raise MetaError("meta_invalid_metric") from None


def micros(value: object) -> int:
    return int((decimal_value(value) * 1_000_000).to_integral_value(rounding=ROUND_HALF_UP))


def count(value: object) -> int:
    number = decimal_value(value, maximum=Decimal(2_147_483_647))
    if number != number.to_integral_value():
        raise MetaError("meta_invalid_metric")
    return int(number)


def action_value(items: object, action_type: str) -> Decimal:
    if items is None:
        return Decimal(0)
    if not isinstance(items, list) or len(items) > 1000:
        raise MetaError("meta_invalid_metric")
    matches = []
    for item in items:
        if not isinstance(item, dict):
            raise MetaError("meta_invalid_metric")
        if item.get("action_type") == action_type:
            matches.append(decimal_value(item.get("value")))
    if len(matches) > 1:
        # Aggregate and child action types overlap; only one explicit event is used.
        raise MetaError("meta_ambiguous_conversion_metric")
    return matches[0] if matches else Decimal(0)


def metric_values(
    source: dict[str, Any],
    account_id: str,
    currency: str,
    start: date,
    end: date,
    action_type: str | None,
) -> dict[str, Any]:
    try:
        if identifier(source["account_id"]) != account_id or source["account_currency"] != currency:
            raise ValueError("account")
        day = date.fromisoformat(source["date_start"])
        if source["date_stop"] != day.isoformat() or not start <= day <= end:
            raise ValueError("date")
        if (action_type or "") not in CONVERSION_ACTIONS:
            raise ValueError("action")
        conversions = (
            action_value(source.get("actions"), action_type) if action_type else Decimal(0)
        )
        value = (
            action_value(source.get("action_values"), action_type)
            if action_type in PURCHASE_ACTIONS
            else Decimal(0)
        )
        return {
            "metric_date": day,
            "impressions": count(source["impressions"]),
            "clicks": count(source["clicks"]),
            "cost_micros": micros(source["spend"]),
            "conversions": conversions,
            "conversion_value_micros": micros(value),
        }
    except (KeyError, TypeError, ValueError):
        raise MetaError("meta_invalid_metric") from None
