"""Exact local-date financial boundaries; never choose a fold or normalize a gap."""

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException

from app.goals.schemas import GoalDefinition


def _midnight(day: date, zone: ZoneInfo) -> datetime:
    local = datetime.combine(day, time.min)
    first = local.replace(tzinfo=zone, fold=0).astimezone(UTC)
    second = local.replace(tzinfo=zone, fold=1).astimezone(UTC)
    if first != second or first.astimezone(zone).replace(tzinfo=None) != local:
        raise ValueError("budget boundary is ambiguous or nonexistent")
    return first


def financial_budget_period(definition: GoalDefinition) -> tuple[datetime, datetime]:
    """Preserve explicit goal dates/timezone or deny the whole new authority period."""
    try:
        zone = ZoneInfo(definition.target_window.time_zone)
        start = _midnight(definition.budget_start, zone)
        end = _midnight(definition.budget_end, zone)
        if start >= end:
            raise ValueError("budget period ordering")
    except (ValueError, OverflowError, ZoneInfoNotFoundError):
        raise HTTPException(409, "financial_budget_period_unavailable") from None
    return start, end
