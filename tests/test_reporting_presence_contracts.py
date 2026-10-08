"""Pure additive presence facts, not trusted publication or provider qualification."""

import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, cast

import pytest
from app.ads.models import AdvertisingAccount, DailyMetric
from app.campaign_performance import presence_contracts as c
from app.campaign_performance.service import manifest
from pydantic import ValidationError
from sqlalchemy.orm import Session


def fact(**updates: Any) -> c.ReportedMetricPresenceV1:
    values = dict(
        completion_id="a" * 32,
        workspace_id=1,
        account_id=2,
        campaign_id=3,
        native_campaign_id="123",
        metric_date="2026-09-01",
        impressions=dict(presence="present", value=1000),
        clicks=dict(presence="present", value=100),
        spend_micros=dict(presence="present", value=100_000_000),
        selected_conversions=dict(presence="present", value="10"),
        selected_value_micros=dict(presence="missing", value=None),
    )
    values.update(updates)
    return c.ReportedMetricPresenceV1.model_validate(values)


def header(facts: tuple[c.ReportedMetricPresenceV1, ...], **updates: Any) -> c.ReportingSemanticsV1:
    values = dict(
        workspace_id=1,
        account_id=2,
        connection_id=4,
        platform="meta_ads",
        source_connection_ref="7",
        generation=1,
        privacy_revision=0,
        completion_id="a" * 32,
        legacy_manifest_digest="b" * 64,
        producer_contract="fixture.explicit.v1",
        query_descriptor="campaign-day.selected-purchase.v1",
        requested_starts_on="2026-09-01",
        requested_ends_on="2026-09-30",
        actual_starts_on="2026-09-01",
        actual_ends_on="2026-09-30",
        currency="USD",
        time_zone="America/New_York",
        selected_event=dict(provenance="explicit_selected", native_event_id="purchase", label=None),
        attribution=dict(
            click_window_days=None,
            view_window_days=None,
            report_time_basis="unknown",
            provenance="provider_default_unknown",
            producer_contract="fixture.defaults-unknown.v1",
        ),
        pagination_complete=True,
        closed_requested_period=True,
        completed_at="2026-10-01T12:00:00Z",
        fact_count=len(facts),
        fact_digest=c.presence_digest(facts),
    )
    values.update(updates)
    return c.ReportingSemanticsV1.model_validate(values)


@pytest.mark.parametrize("state", ["present", "missing", "unsupported", "legacy_unknown"])
def test_presence_is_not_defaulted_zero(state: str) -> None:
    row = fact(selected_conversions=dict(presence=state, value="0" if state == "present" else None))
    c.validate_presence(header((row,)), (row,))
    assert row.selected_conversions.value == (Decimal(0) if state == "present" else None)
    assert row.selected_value_micros.value is None
    assert row.clicks.value == 100 and row.spend_micros.value == 100_000_000


def test_exact_decimal_canonical_and_json_roundtrip() -> None:
    rows = [
        fact(selected_conversions=dict(presence="present", value=v))
        for v in ("10", "10.000000", 10, Decimal("1E+1"))
    ]
    assert len({c.presence_digest((r,)) for r in rows}) == 1
    row = fact(selected_conversions=dict(presence="present", value="999999999999.999999"))
    assert c.ReportedMetricPresenceV1.model_validate_json(row.model_dump_json()) == row
    h = header((row,))
    assert c.ReportingSemanticsV1.model_validate_json(h.model_dump_json()) == h
    c.validate_presence(h, (row,))


@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        0.0,
        1.1,
        float("nan"),
        "NaN",
        "Infinity",
        Decimal("NaN"),
        Decimal("Infinity"),
        -1,
        "-1",
        "1e1",
        "01",
        "0.0000001",
        Decimal("1.0000000"),
        "1000000000000",
        b"1",
    ],
)
def test_invalid_exact_counts(value: Any) -> None:
    with pytest.raises(ValidationError):
        c.CountCellV1(presence="present", value=value)


@pytest.mark.parametrize("model", [c.CountCellV1, c.IntegerCountCellV1, c.MoneyCellV1])
@pytest.mark.parametrize(
    "presence,value", [("present", None), ("missing", 0), ("unsupported", 1), ("legacy_unknown", 0)]
)
def test_presence_value_invariant(model: Any, presence: str, value: Any) -> None:
    with pytest.raises(ValidationError):
        model(presence=presence, value=value)


@pytest.mark.parametrize(
    "model,limit",
    [(c.IntegerCountCellV1, c.MAX_INTEGER_COUNT), (c.MoneyCellV1, c.MAX_MONEY_MICROS)],
)
def test_integer_cells_are_strict_and_bounded(model: Any, limit: int) -> None:
    assert model(presence="present", value=limit).value == limit
    for value in [True, 1.0, "1", Decimal(1), -1, limit + 1]:
        with pytest.raises(ValidationError):
            model(presence="present", value=value)


@pytest.mark.parametrize("provenance", ["generic", "unavailable"])
@pytest.mark.parametrize("selected", ["selected_conversions", "selected_value_micros"])
def test_generic_cannot_qualify_either_selected_cell(provenance: str, selected: str) -> None:
    raw = fact().model_dump()
    raw["selected_conversions"] = dict(presence="unsupported", value=None)
    raw[selected] = dict(presence="present", value=0)
    row = c.ReportedMetricPresenceV1.model_validate(raw)
    h = header((row,), selected_event=dict(provenance=provenance, native_event_id=None, label=None))
    with pytest.raises(ValueError, match="cannot qualify"):
        c.validate_presence(h, (row,))


def test_event_and_unknown_attribution_invariants() -> None:
    for event in [
        dict(provenance="explicit_selected", native_event_id=None, label="Purchase"),
        dict(provenance="unavailable", native_event_id="purchase", label=None),
    ]:
        with pytest.raises(ValidationError):
            c.SelectedEventV1.model_validate(event)
    raw = header(()).attribution.model_dump()
    updates: list[dict[str, Any]] = [
        dict(click_window_days=0),
        dict(view_window_days=1),
        dict(report_time_basis="conversion"),
    ]
    for update in updates:
        with pytest.raises(ValidationError):
            c.AttributionBasisV1.model_validate({**raw, **update})
    assert (
        c.AttributionBasisV1.model_validate(
            {**raw, "provenance": "observed_response", "click_window_days": 0}
        ).click_window_days
        == 0
    )


@pytest.mark.parametrize(
    "update",
    [
        dict(workspace_id=True),
        dict(generation=0),
        dict(privacy_revision=-1),
        dict(connection_id="4"),
        dict(pagination_complete=1),
        dict(source_connection_ref=""),
        dict(returned_rows_scope="all_days"),
        dict(actual_starts_on="2026-08-31"),
        dict(actual_ends_on="2026-10-01"),
        dict(requested_ends_on="2028-01-01"),
        dict(completed_at="2026-10-01T00:30:00Z"),
        dict(completed_at="2026-10-01T12:00:00"),
        dict(completed_at=1790856000),
        dict(actual_starts_on=datetime(2026, 9, 1, tzinfo=UTC)),
        dict(time_zone="Invalid/Zone"),
    ],
)
def test_strict_header_dates_scope_and_local_closed_period(update: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        header((), **update)


def test_set_digest_order_empty_binding_and_identity() -> None:
    first, second = fact(), fact(metric_date="2026-09-02")
    assert c.presence_digest((first, second)) == c.presence_digest((second, first))
    c.validate_presence(header(()), ())  # Empty is not a synthetic zero fact.
    assert c.presence_digest(()) != c.presence_digest(
        (fact(selected_conversions=dict(presence="present", value="0")),)
    )
    for rows in [
        (first, first),
        (first, fact(workspace_id=2)),
        (first, fact(metric_date="2026-09-02", native_campaign_id="999")),
        (first, fact(campaign_id=4)),
    ]:
        with pytest.raises(ValueError):
            c.presence_digest(rows)
    updates: list[dict[str, Any]] = [
        dict(fact_count=0),
        dict(fact_digest="0" * 64),
        dict(account_id=8),
        dict(completion_id="c" * 32),
        dict(actual_starts_on="2026-09-02"),
    ]
    for update in updates:
        with pytest.raises(ValueError):
            c.validate_presence(header((first,), **update), (first,))


def test_unsafe_copies_revalidated_at_acceptance() -> None:
    row = fact()
    bad_cell = row.clicks.model_copy(update={"value": True})
    with pytest.raises(ValueError):
        c.presence_digest((row.model_copy(update={"clicks": bad_cell}),))
    h = header((row,))
    bad_event = h.selected_event.model_copy(update={"native_event_id": None})
    with pytest.raises(ValueError):
        c.validate_presence(h.model_copy(update={"selected_event": bad_event}), (row,))


def test_byte_and_count_caps(monkeypatch: pytest.MonkeyPatch) -> None:
    row = fact()
    with pytest.raises(ValueError, match="count capacity"):
        c.presence_digest((row,) * (c.MAX_FACTS + 1))
    fact_bytes = len(c._canonical(row))
    monkeypatch.setattr(c, "MAX_FACT_BYTES", fact_bytes)
    c.presence_digest((row,))
    monkeypatch.setattr(c, "MAX_FACT_BYTES", fact_bytes - 1)
    with pytest.raises(ValueError, match="fact byte"):
        c.presence_digest((row,))
    monkeypatch.setattr(c, "MAX_FACT_BYTES", fact_bytes)
    monkeypatch.setattr(c, "MAX_FACT_SET_BYTES", fact_bytes + 2)
    c.presence_digest((row,))
    monkeypatch.setattr(c, "MAX_FACT_SET_BYTES", fact_bytes + 1)
    with pytest.raises(ValueError, match="set byte"):
        c.presence_digest((row,))
    monkeypatch.setattr(c, "MAX_FACT_SET_BYTES", 128 * 1024 * 1024)
    h = header((row,))
    size = len(c._canonical(h))
    monkeypatch.setattr(c, "MAX_HEADER_BYTES", size)
    c.validate_presence(h, (row,))
    monkeypatch.setattr(c, "MAX_HEADER_BYTES", size - 1)
    with pytest.raises(ValueError, match="header byte"):
        c.validate_presence(h, (row,))


def test_legacy_manifest_golden_remains_separate() -> None:
    # Actual legacy function, isolated SQL result seam; no rewritten legacy hash algorithm.
    rows = [
        DailyMetric(
            campaign_id=3,
            metric_date=date(2026, 9, 1),
            impressions=1000,
            clicks=100,
            cost_micros=100_000_000,
            conversions=Decimal("10"),
            conversion_value_micros=0,
        )
    ]

    class Database:
        def scalars(self, statement: Any) -> list[DailyMetric]:
            return rows

    actual, returned = manifest(
        cast(Session, Database()),
        AdvertisingAccount(id=2, workspace_id=1, platform="meta_ads"),
        date(2026, 9, 1),
        date(2026, 9, 30),
    )
    legacy_bytes = (
        b'["inlet.campaign-performance-manifest.v1",'
        b'[[3,"2026-09-01",1000,100,100000000,"10.000000",0]]]'
    )
    assert actual == hashlib.sha256(legacy_bytes).hexdigest()
    assert returned == rows and actual != c.presence_digest((fact(),))


def test_selected_value_is_independent_and_presence_changes_digest() -> None:
    row = fact(
        selected_conversions=dict(presence="missing", value=None),
        selected_value_micros=dict(presence="present", value=0),
    )
    c.validate_presence(header((row,)), (row,))
    assert row.selected_conversions.value is None and row.selected_value_micros.value == 0
    unknown = fact(selected_conversions=dict(presence="legacy_unknown", value=None))
    missing = fact(selected_conversions=dict(presence="missing", value=None))
    assert c.presence_digest((unknown,)) != c.presence_digest((missing,))
    with pytest.raises(ValidationError):
        fact(clicks=dict(presence="present", value="0.5"))
