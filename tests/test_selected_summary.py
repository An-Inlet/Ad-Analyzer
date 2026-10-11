"""Whole-graph selected summary guards; no owned API or provider evidence claim."""

from datetime import date
from decimal import Decimal, localcontext
from typing import Any

import pytest
from app.campaign_performance import selected_contracts as c
from app.campaign_performance.selected_summary import (
    SelectedCampaignSummary,
    summarize_selected_capture,
)

from tests.test_selected_reporting_contracts import capture


def summarize(value: c.SelectedCaptureV1, **changes: Any) -> SelectedCampaignSummary:
    args: dict[str, Any] = dict(
        current_aggregate=value.request.aggregate,
        current_selection=value.request.selection,
        campaign_id=5,
        native_campaign_id="555",
        starts_on=date(2026, 9, 29),
        ends_on=date(2026, 9, 30),
    )
    args.update(changes)
    return summarize_selected_capture(value, **args)


def two_days(state: str = "present", value: Any = "0") -> c.SelectedCaptureV1:
    original = capture(state=state, value=value)
    earlier = original.facts[0].model_copy(update={"metric_date": date(2026, 9, 29)})
    return c.SelectedCaptureV1.model_validate(
        original.model_copy(update={"facts": (earlier, *original.facts)})
    )


def test_positive_selected_total_never_zero_finding() -> None:
    result = summarize(capture())
    assert result.conversions.value == 10
    assert not result.zero_for_requested_window
    assert result.conversions.coverage == "partial" and result.missing_calendar_days == 1


def test_full_explicit_zero_distinct_from_missing_row_or_field() -> None:
    result = summarize(two_days())
    assert result.zero_for_requested_window and result.conversions.value == 0
    assert result.value_micros.value is None
    sparse = summarize(capture(value="0"))
    assert not sparse.zero_for_requested_window and sparse.conversions.value == 0
    missing = summarize(two_days(state="missing", value=None))
    assert not missing.zero_for_requested_window and missing.conversions.value is None


@pytest.mark.parametrize("state", ["missing", "unsupported", "legacy_unknown"])
def test_nonpresent_cells_never_zero(state: str) -> None:
    result = summarize(two_days(state=state, value=None))
    assert not result.zero_for_requested_window and result.conversions.coverage == "unavailable"


def test_empty_capture_stays_unavailable() -> None:
    empty = capture().model_copy(update={"facts": ()})
    result = summarize(empty)
    assert result.returned_days == 0 and result.missing_calendar_days == 2
    assert result.conversions.value is None and not result.zero_for_requested_window


def test_slice_still_binds_whole_graph_and_current_dependencies() -> None:
    whole = two_days(value="10")
    result = summarize(whole, starts_on=date(2026, 9, 30))
    assert result.conversions.value == 10 and result.requested_days == 1
    assert result.capture_digest == c.selected_capture_digest(whole)
    changed = whole.request.aggregate.model_copy(update={"manifest_digest": "9" * 64})
    with pytest.raises(ValueError, match="dependencies changed"):
        summarize(whole, starts_on=date(2026, 9, 30), current_aggregate=changed)
    malformed = whole.facts[0].model_copy(update={"request_digest": "9" * 64})
    with pytest.raises(ValueError):
        summarize(
            whole.model_copy(update={"facts": (malformed, whole.facts[1])}),
            starts_on=date(2026, 9, 30),
        )


@pytest.mark.parametrize(
    "update",
    [
        {"campaign_id": 6},
        {"native_campaign_id": "666"},
        {"campaign_id": True},
        {"starts_on": date(2026, 8, 1)},
        {"ends_on": date(2026, 10, 1)},
    ],
)
def test_mismatch_or_relabelled_range_fails(update: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        summarize(capture(), **update)


def test_decimal_sum_exact_even_under_low_ambient_precision() -> None:
    with localcontext() as context:
        context.prec = 2
        result = summarize(two_days(value="999999999999.999999"))
    assert result.conversions.value == Decimal("1999999999999.999998")
