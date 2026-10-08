"""Pure whole-completion aggregation; import/API qualification remains separate."""

from datetime import date
from decimal import Decimal, Overflow, localcontext
from typing import Any

import pytest
from app.campaign_performance.presence_contracts import presence_digest
from app.campaign_performance.presence_summary import summarize_presence

from tests.test_reporting_presence_contracts import fact, header


def summarized(rows: tuple[Any, ...], **overrides: Any) -> Any:
    return summarize_presence(
        header(rows, **overrides), rows, campaign_id=3, native_campaign_id="123"
    )


def test_positive_100_clicks_10_conversions_100_dollars_never_becomes_zero() -> None:
    result = summarized((fact(),))
    assert result.clicks.value == 100 and result.spend_micros.value == 100_000_000
    assert result.selected_conversions.value == Decimal(10)
    assert not result.selected_zero_for_requested_window
    assert result.selected_conversions.coverage == "partial"
    assert result.missing_calendar_days == 29


@pytest.mark.parametrize("state", ["present", "missing", "unsupported", "legacy_unknown"])
def test_missing_day_and_missing_cell_are_not_window_zero(state: str) -> None:
    cell = dict(presence=state, value="0" if state == "present" else None)
    result = summarized((fact(selected_conversions=cell),))
    assert not result.selected_zero_for_requested_window
    assert result.selected_conversions.value == (Decimal(0) if state == "present" else None)
    assert result.returned_days == 1 and result.missing_calendar_days == 29


def zero_month() -> tuple[Any, ...]:
    return tuple(
        fact(
            metric_date=date(2026, 9, day),
            selected_conversions=dict(presence="present", value="0"),
        )
        for day in range(1, 31)
    )


def test_complete_present_selected_zero_is_observed_but_value_stays_missing() -> None:
    result = summarized(zero_month())
    assert result.selected_zero_for_requested_window
    assert result.selected_conversions.coverage == "observed_requested_days"
    assert result.selected_value_micros.value is None
    assert result.selected_value_micros.coverage == "unavailable"
    assert result.header.attribution.provenance == "provider_default_unknown"


@pytest.mark.parametrize("flag", ["pagination_complete", "closed_requested_period"])
def test_incomplete_source_cannot_assert_complete_zero(flag: str) -> None:
    result = summarized(zero_month(), **{flag: False})
    assert not result.selected_zero_for_requested_window
    assert result.selected_conversions.coverage == "partial"


def test_single_missing_cell_invalidates_zero_even_when_all_days_exist() -> None:
    rows = list(zero_month())
    rows[0] = fact(selected_conversions=dict(presence="missing", value=None))
    result = summarized(tuple(rows))
    assert result.missing_calendar_days == 0
    assert result.selected_conversions.present_days == 29
    assert result.selected_conversions.missing_days == 1
    assert not result.selected_zero_for_requested_window


def test_absent_campaign_and_empty_completion_do_not_become_zero() -> None:
    result = summarized(())
    assert result.returned_days == 0 and result.selected_conversions.value is None
    assert not result.selected_zero_for_requested_window
    other = fact(campaign_id=4, native_campaign_id="456")
    result = summarized((other,))
    assert result.returned_days == 0 and not result.selected_zero_for_requested_window


def test_whole_completion_digest_scope_and_local_native_mapping_required() -> None:
    rows = (fact(), fact(campaign_id=4, native_campaign_id="456"))
    h = header(rows)
    with pytest.raises(ValueError, match="count or digest"):
        summarize_presence(h, rows[:1], campaign_id=3, native_campaign_id="123")
    with pytest.raises(ValueError, match="identity"):
        summarize_presence(h, rows, campaign_id=3, native_campaign_id="456")
    corrupted = h.model_copy(update={"fact_digest": presence_digest(())})
    with pytest.raises(ValueError):
        summarize_presence(corrupted, rows, campaign_id=3, native_campaign_id="123")


def test_money_above_javascript_safe_integer_and_decimal_counts_sum_exactly() -> None:
    rows = tuple(
        fact(
            metric_date=date(2026, 9, day),
            spend_micros=dict(presence="present", value=2**63 - 1),
            selected_conversions=dict(presence="present", value="999999999999.999999"),
        )
        for day in (1, 2)
    )
    with localcontext() as context:
        context.prec = 2
        result = summarized(rows)
    assert result.spend_micros.value == 2 * (2**63 - 1)
    assert isinstance(result.spend_micros.value, int)
    assert result.selected_conversions.value == Decimal("1999999999999.999998")


@pytest.mark.parametrize("trap", [True, False])
def test_ambient_exponent_limits_and_traps_do_not_change_aggregate(trap: bool) -> None:
    rows = (fact(),)
    with localcontext() as context:
        context.Emax = 0
        context.Emin = 0
        context.traps[Overflow] = trap
        result = summarized(rows)
    assert result.selected_conversions.value == Decimal(10)
    assert not result.selected_zero_for_requested_window
