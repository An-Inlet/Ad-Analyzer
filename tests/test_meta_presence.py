"""Pure original-response parsing; no DB, collector invocation or network."""

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from app.meta import presence as p
from app.meta.normalize import metric_values
from app.meta.security import API_VERSION, MetaError
from pydantic import ValidationError

DAY = date(2026, 9, 1)


def source(**updates: Any) -> dict[str, Any]:
    return {
        "account_id": "123",
        "campaign_id": "456",
        "account_currency": "USD",
        "date_start": "2026-09-01",
        "date_stop": "2026-09-01",
        "impressions": "1000",
        "clicks": "100",
        "spend": "100",
        "actions": [{"action_type": "purchase", "value": "10"}],
        "action_values": [{"action_type": "purchase", "value": "42.0000005"}],
        **updates,
    }


def parse(row: dict[str, Any], event: str | None = "purchase") -> p.MetaPresenceCellsV1:
    return p.parse_meta_presence(
        row,
        expected_advertiser="123",
        currency="USD",
        starts_on=DAY,
        ends_on=DAY,
        selected_event=event,
    )


def test_positive_exact_numeric_profile_and_roundtrip() -> None:
    raw = source()
    cells = parse(raw)
    old = metric_values(raw, "123", "USD", DAY, DAY, "purchase")
    assert cells.native_campaign_id == "456" and cells.metric_date == DAY
    assert cells.clicks.value == 100 and cells.spend_micros.value == 100_000_000
    assert cells.selected_conversions.value == Decimal(10) == old["conversions"]
    assert cells.selected_value_micros.value == 42_000_001 == old["conversion_value_micros"]
    assert cells.selected_event.native_event_id == "purchase"
    assert cells.selected_event.provenance == "explicit_selected"
    assert p.MetaPresenceCellsV1.model_validate_json(cells.model_dump_json()) == cells
    assert f"meta.{API_VERSION}.campaign-day.v1" == p.QUERY_DESCRIPTOR
    assert p.PRESENCE_PRODUCER_CONTRACT == "meta.campaign-day.presence.v1"
    assert p.UNKNOWN_ATTRIBUTION.provenance == "provider_default_unknown"
    assert p.UNKNOWN_ATTRIBUTION.click_window_days is None
    assert p.UNKNOWN_ATTRIBUTION.view_window_days is None
    assert p.UNKNOWN_ATTRIBUTION.report_time_basis == "unknown"


@pytest.mark.parametrize("field", ["actions", "action_values"])
@pytest.mark.parametrize("missing", ["absent", None, [], [{"action_type": "lead", "value": "9"}]])
def test_missing_is_not_zero_and_cells_independent(field: str, missing: Any) -> None:
    raw = source()
    if missing == "absent":
        del raw[field]
    else:
        raw[field] = missing
    cells = parse(raw)
    absent = cells.selected_conversions if field == "actions" else cells.selected_value_micros
    other = cells.selected_value_micros if field == "actions" else cells.selected_conversions
    assert absent.presence == "missing" and absent.value is None
    assert other.presence == "present" and other.value is not None
    legacy = metric_values(raw, "123", "USD", DAY, DAY, "purchase")
    assert legacy["conversions" if field == "actions" else "conversion_value_micros"] == 0


@pytest.mark.parametrize("field", ["actions", "action_values"])
def test_explicit_selected_zero_present(field: str) -> None:
    cells = parse(source(**{field: [{"action_type": "purchase", "value": "0"}]}))
    selected = cells.selected_conversions if field == "actions" else cells.selected_value_micros
    assert selected.presence == "present" and selected.value == 0


@pytest.mark.parametrize("event", [None, ""])
def test_unselected_never_promotes_generic_metrics(event: str | None) -> None:
    cells = parse(source(), event)
    assert cells.selected_event.provenance == "unavailable"
    for selected in (cells.selected_conversions, cells.selected_value_micros):
        assert selected.presence == "unsupported" and selected.value is None


def test_nonpurchase_selected_value_unsupported() -> None:
    raw = source(
        actions=[{"action_type": "lead", "value": "1.234567"}],
        action_values=[{"action_type": "lead", "value": "100"}],
    )
    cells = parse(raw, "lead")
    assert cells.selected_conversions.value == Decimal("1.234567")
    assert cells.selected_value_micros.presence == "unsupported"
    assert cells.selected_value_micros.value is None


@pytest.mark.parametrize("event", ["purchase", "offsite_conversion.fb_pixel_purchase"])
def test_only_exact_event_not_overlapping_aggregate(event: str) -> None:
    other = "purchase" if event != "purchase" else "offsite_conversion.fb_pixel_purchase"
    raw = source(
        actions=[{"action_type": event, "value": "2"}, {"action_type": other, "value": "99"}]
    )
    assert parse(raw, event).selected_conversions.value == 2


@pytest.mark.parametrize("field", ["actions", "action_values"])
@pytest.mark.parametrize(
    "bad",
    [
        True,
        {},
        [None],
        [{"action_type": "purchase"}],
        [{"action_type": "purchase", "value": None}],
        [{"action_type": "purchase", "value": "NaN"}],
    ],
)
def test_malformed_selected_lists_controlled(field: str, bad: Any) -> None:
    with pytest.raises(MetaError) as error:
        parse(source(**{field: bad}))
    assert error.value.code == "meta_invalid_metric"


@pytest.mark.parametrize("field", ["actions", "action_values"])
def test_duplicate_selected_entries_reject(field: str) -> None:
    with pytest.raises(MetaError) as error:
        parse(source(**{field: [{"action_type": "purchase", "value": "0"}] * 2}))
    assert error.value.code == "meta_ambiguous_conversion_metric"


@pytest.mark.parametrize("value", ["0.0000001", "1.0000000", True, 1.0, "-1", "Infinity"])
def test_count_precision_and_malformed_values(value: Any) -> None:
    with pytest.raises(MetaError):
        parse(source(actions=[{"action_type": "purchase", "value": value}]))


@pytest.mark.parametrize(
    "field,bad",
    [
        ("account_id", "999"),
        ("account_id", 123),
        ("campaign_id", "bad"),
        ("campaign_id", 456),
        ("account_currency", "EUR"),
        ("date_start", "20260901"),
        ("date_start", "2026-09-02"),
        ("date_stop", "2026-09-02"),
        ("clicks", "1.5"),
        ("clicks", "2147483648"),
        ("impressions", True),
        ("spend", -1),
    ],
)
def test_exact_scope_and_required_metrics(field: str, bad: Any) -> None:
    with pytest.raises(MetaError):
        parse(source(**{field: bad}))


@pytest.mark.parametrize(
    "field",
    [
        "account_id",
        "campaign_id",
        "account_currency",
        "date_start",
        "date_stop",
        "impressions",
        "clicks",
        "spend",
    ],
)
def test_missing_required_fields_reject(field: str) -> None:
    raw = source()
    del raw[field]
    with pytest.raises(MetaError):
        parse(raw)


def test_present_integer_zero_and_empty_lists_are_distinct() -> None:
    cells = parse(source(impressions="0", clicks="0", spend="0", actions=[], action_values=[]))
    assert all(
        cell.presence == "present" and cell.value == 0
        for cell in (cells.impressions, cells.clicks, cells.spend_micros)
    )
    assert cells.selected_conversions.presence == "missing"
    assert cells.selected_value_micros.presence == "missing"


def test_unsafe_nested_copy_revalidation() -> None:
    cells = parse(source())
    bad = cells.model_copy(update={"clicks": cells.clicks.model_copy(update={"value": True})})
    with pytest.raises(ValidationError):
        p.MetaPresenceCellsV1.model_validate(bad)
    bad = cells.model_copy(
        update={"selected_event": cells.selected_event.model_copy(update={"provenance": "generic"})}
    )
    with pytest.raises(ValidationError):
        p.MetaPresenceCellsV1.model_validate(bad)


def test_numeric_disagreement_never_qualifies(monkeypatch: pytest.MonkeyPatch) -> None:
    original = metric_values

    def changed(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {**original(*args, **kwargs), "conversions": Decimal(999)}

    monkeypatch.setattr(p, "metric_values", changed)
    with pytest.raises(MetaError):
        parse(source())


@pytest.mark.parametrize("event", ["unknown-event", "generic_conversions"])
def test_unsupported_event_profile_rejects(event: str) -> None:
    with pytest.raises(MetaError):
        parse(source(), event)


def test_existing_provider_money_maximum_preserved_exactly() -> None:
    raw = source(spend="999999999999")
    assert metric_values(raw, "123", "USD", DAY, DAY, "purchase")["cost_micros"] > 0
    # Existing provider-normalizer bound is below signed bigint, and remains valid.
    assert parse(raw).spend_micros.value == 999999999999000000


@pytest.mark.parametrize("field", ["actions", "action_values"])
def test_oversized_supported_action_list_rejects(field: str) -> None:
    raw = source(**{field: [{"action_type": "other", "value": "1"}] * 1001})
    with pytest.raises(MetaError):
        parse(raw)
