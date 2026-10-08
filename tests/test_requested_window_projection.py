"""Pure projections only: fixture construction is not current source proof."""

from datetime import UTC, date, datetime, time, timedelta
from decimal import Inexact, Overflow, localcontext
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from app.campaign_performance.contracts import CampaignPerformanceV1
from app.campaign_performance.presence_contracts import ReportedMetricPresenceV1, presence_digest
from app.campaign_performance.presence_report import CampaignPerformanceV3, campaign_summary
from app.campaign_performance.window_projection import (
    RequestedWindowPerformanceV1,
    WindowProjectionUnavailable,
    project_requested_window,
)
from app.planning_documents.context import ReportingWindow
from pydantic import ValidationError

from tests.test_reporting_presence_contracts import fact, header


def report(
    start: date = date(2026, 8, 1),
    days: int = 56,
    rows: tuple[ReportedMetricPresenceV1, ...] | None = None,
    **updates: Any,
) -> CampaignPerformanceV3:
    end = start + timedelta(days=days - 1)
    if rows is None:
        rows = tuple(fact(metric_date=start + timedelta(days=i)) for i in range(days))
    h = header(
        rows,
        **dict(
            requested_starts_on=start,
            requested_ends_on=end,
            actual_starts_on=start,
            actual_ends_on=end,
            completed_at=datetime.combine(end + timedelta(days=2), time(), UTC),
        )
        | updates,
    )
    old = CampaignPerformanceV1(
        completion_id=h.completion_id,
        manifest_digest=h.legacy_manifest_digest,
        account_id=h.account_id,
        campaign_id=3,
        generation=h.generation,
        privacy_revision=h.privacy_revision,
        starts_on=start,
        ends_on=end,
        currency=h.currency,
        time_zone=h.time_zone,
        completed_at=h.completed_at,
        semantics="explicit_platform_event",
        selected_event=h.selected_event.native_event_id,
        reporting_basis="provider_defaults_unspecified",
        reported_day_count=len(rows),
        campaign_rows_available=bool(rows),
        impressions=None,
        clicks=None,
        spend_micros=None,
        conversions=None,
        conversion_value_micros=None,
        cpa_micros=None,
        reported_roas=None,
    )
    return CampaignPerformanceV3(
        legacy=old,
        presence=h,
        native_campaign_id="123",
        campaign_facts=rows,
        summary=campaign_summary(h, rows, 3, "123"),
    )


def window(start: date, days: int = 7, zone: str = "America/New_York") -> ReportingWindow:
    return ReportingWindow(
        starts_at=datetime.combine(start, time(), ZoneInfo(zone)),
        ends_at_exclusive=datetime.combine(start + timedelta(days=days), time(), ZoneInfo(zone)),
    )


def test_56_day_original_unchanged_and_exact_positive_seven_day_slice() -> None:
    source = report()
    body = source.model_dump_json()
    result = project_requested_window(source, requested_window=window(date(2026, 9, 1)))
    assert result.original.model_dump_json() == body
    assert len(result.original.campaign_facts) == 56 and len(result.selected_facts) == 7
    assert result.summary.selected_conversions.value == "70"
    assert result.summary.clicks.value == 700 and result.summary.spend_micros.value == 700_000_000
    assert not result.summary.selected_zero_for_requested_window
    one = project_requested_window(source, requested_window=window(date(2026, 9, 1), 1))
    assert (
        one.summary.clicks.value,
        one.summary.selected_conversions.value,
        one.summary.spend_micros.value,
    ) == (100, "10", 100_000_000)
    assert RequestedWindowPerformanceV1.model_validate_json(result.model_dump_json()) == result


@pytest.mark.parametrize("mode", ["zero", "missing", "calendar", "allmissing", "empty", "value"])
def test_zero_missing_calendar_and_independent_value(mode: str) -> None:
    start = date(2026, 9, 1)
    rows = tuple(
        fact(
            metric_date=start + timedelta(days=i),
            selected_conversions=dict(presence="present", value="0"),
        )
        for i in range(7)
    )
    if mode in {"missing", "allmissing"}:
        rows = tuple(
            r.model_copy(
                update={
                    "selected_conversions": fact(
                        selected_conversions=dict(presence="missing", value=None)
                    ).selected_conversions
                }
            )
            if mode == "allmissing" or i == 0
            else r
            for i, r in enumerate(rows)
        )
    if mode == "calendar":
        rows = rows[:-1]
    if mode == "empty":
        rows = ()
    if mode == "value":
        rows = tuple(
            r.model_copy(
                update={
                    "selected_value_micros": fact(
                        selected_value_micros=dict(presence="present", value=9)
                    ).selected_value_micros
                }
            )
            for r in rows
        )
    result = project_requested_window(report(start, 7, rows), requested_window=window(start))
    assert result.summary.selected_zero_for_requested_window == (mode in {"zero", "value"})
    assert result.summary.selected_conversions.value == (
        None if mode in {"allmissing", "empty"} else "0"
    )
    assert result.summary.missing_calendar_days == (
        1 if mode == "calendar" else 7 if mode == "empty" else 0
    )
    assert result.summary.selected_value_micros.value == (63 if mode == "value" else None)


@pytest.mark.parametrize("flag", ["pagination_complete", "closed_requested_period"])
def test_partial_source_flags_preserved(flag: str) -> None:
    result = project_requested_window(
        report(**dict[str, Any]({flag: False})), requested_window=window(date(2026, 9, 1))
    )
    assert result.summary.clicks.coverage == "partial"
    assert not getattr(result.original.presence, flag)


def test_partial_original_actual_scope_fully_covers_interior() -> None:
    rows = tuple(fact(metric_date=date(2026, 9, i)) for i in range(1, 8))
    source = report(rows=rows, actual_starts_on=date(2026, 9, 1), actual_ends_on=date(2026, 9, 7))
    result = project_requested_window(source, requested_window=window(date(2026, 9, 1)))
    assert result.summary.clicks.coverage == "observed_requested_days"
    assert result.original.summary.clicks.coverage == "partial"


@pytest.mark.parametrize("start,hours", [(date(2026, 3, 8), 23), (date(2026, 11, 1), 25)])
def test_dst_calendar_day_not_elapsed_day(start: date, hours: int) -> None:
    wanted = window(start, 1)
    assert (
        wanted.ends_at_exclusive.astimezone(UTC) - wanted.starts_at.astimezone(UTC)
    ).total_seconds() == hours * 3600
    result = project_requested_window(report(start, 1), requested_window=wanted)
    assert result.summary.requested_days == 1


@pytest.mark.parametrize(
    "mode,reason",
    [
        ("outside", "outside_imported_window"),
        ("nonmidnight", "unaligned_local_days"),
        ("open", "requested_days_not_closed"),
        ("ambiguous", "unaligned_local_days"),
        ("nonexistent", "unaligned_local_days"),
    ],
)
def test_known_incompatibilities_only(mode: str, reason: str) -> None:
    source = report()
    wanted = window(date(2026, 9, 1))
    if mode == "outside":
        wanted = window(date(2026, 7, 31))
    if mode == "nonmidnight":
        wanted = wanted.model_copy(update={"starts_at": wanted.starts_at + timedelta(hours=1)})
    if mode == "open":
        source = report(
            date(2026, 9, 1),
            1,
            closed_requested_period=False,
            completed_at=datetime(2026, 9, 1, 12, tzinfo=UTC),
        )
        wanted = window(date(2026, 9, 1), 1)
    if mode in {"ambiguous", "nonexistent"}:
        start = date(2020, 11, 1) if mode == "ambiguous" else date(2018, 11, 4)
        zone = "America/Havana" if mode == "ambiguous" else "America/Sao_Paulo"
        source = report(start, 2, time_zone=zone)
        wanted = window(start, 1, zone)
    with pytest.raises(WindowProjectionUnavailable) as error:
        project_requested_window(source, requested_window=wanted)
    assert error.value.reason == reason


@pytest.mark.parametrize(
    "field,value",
    [
        ("selected_facts", ()),
        ("selected_fact_digest", "c" * 64),
        ("original_document_digest", "c" * 64),
        ("requested_starts_on", date(2026, 8, 1)),
        ("spending_authorized", True),
        ("spending_authorized", 0),
    ],
)
def test_copied_wrapper_tampering_rejected(field: str, value: Any) -> None:
    result = project_requested_window(report(), requested_window=window(date(2026, 9, 1)))
    with pytest.raises(ValidationError):
        RequestedWindowPerformanceV1.model_validate(result.model_copy(update={field: value}))


def test_forged_summary_source_identity_and_unsafe_window_are_errors_not_gaps() -> None:
    source = report()
    wanted = window(date(2026, 9, 1))
    result = project_requested_window(source, requested_window=wanted)
    variants = [
        result.model_copy(
            update={
                "summary": result.summary.model_copy(
                    update={"selected_zero_for_requested_window": True}
                )
            }
        ),
        result.model_copy(update={"requested_window": window(date(2026, 7, 1))}),
    ]
    for variant in variants:
        with pytest.raises(ValidationError):
            RequestedWindowPerformanceV1.model_validate(variant)
    bad = source.model_copy(
        update={
            "campaign_facts": (
                source.campaign_facts[0].model_copy(update={"native_campaign_id": "999"}),
            )
        }
    )
    with pytest.raises(ValidationError):
        project_requested_window(bad, requested_window=wanted)
    with pytest.raises(ValidationError):
        project_requested_window(
            source,
            requested_window=wanted.model_copy(update={"ends_at_exclusive": wanted.starts_at}),
        )


def test_hostile_decimal_context_and_document_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    source = report()
    wanted = window(date(2026, 9, 1))
    baseline = project_requested_window(source, requested_window=wanted)
    with localcontext() as context:
        context.prec = 1
        context.Emax = 1
        context.traps[Inexact] = True
        context.traps[Overflow] = True
        assert project_requested_window(source, requested_window=wanted) == baseline
    from app.campaign_performance import window_projection as module

    size = len(baseline.model_dump_json().encode())
    monkeypatch.setattr(module, "MAX_DOCUMENT_BYTES", size)
    assert project_requested_window(source, requested_window=wanted) == baseline
    monkeypatch.setattr(module, "MAX_DOCUMENT_BYTES", size - 1)
    with pytest.raises(ValueError, match="capacity"):
        project_requested_window(source, requested_window=wanted)
    assert baseline.selected_fact_digest == presence_digest(baseline.selected_facts)


def test_actual_two_mib_wrapper_boundary_without_truncation() -> None:
    from app.campaign_performance.window_projection import MAX_DOCUMENT_BYTES

    source = report()
    wanted = window(date(2026, 9, 1))
    baseline = project_requested_window(source, requested_window=wanted)
    # The unchanged legacy decimal field has no byte cap of its own. Padding its
    # exact zero spelling exercises the real wrapper cap while original V3 fits.
    padding = MAX_DOCUMENT_BYTES - len(baseline.model_dump_json().encode())
    raw = source.model_dump(mode="python")
    raw["legacy"]["conversions"] = "0." + "0" * padding
    at = CampaignPerformanceV3.model_validate(raw)
    accepted = project_requested_window(at, requested_window=wanted)
    assert len(accepted.model_dump_json().encode()) == MAX_DOCUMENT_BYTES
    raw["legacy"]["conversions"] += "0"
    above = CampaignPerformanceV3.model_validate(raw)
    with pytest.raises(ValueError, match="capacity"):
        project_requested_window(above, requested_window=wanted)


def test_duplicate_source_rows_and_unselected_event_cannot_qualify_zero() -> None:
    source = report()
    invalid = source.model_copy(
        update={"campaign_facts": (source.campaign_facts[0],) * len(source.campaign_facts)}
    )
    with pytest.raises(ValidationError):
        project_requested_window(invalid, requested_window=window(date(2026, 9, 1)))
    start = date(2026, 9, 1)
    rows = tuple(
        fact(
            metric_date=start + timedelta(days=i),
            selected_conversions=dict(presence="unsupported", value=None),
        )
        for i in range(7)
    )
    unselected = report(
        start,
        7,
        rows,
        selected_event=dict(provenance="unavailable", native_event_id=None, label=None),
    )
    projected = project_requested_window(unselected, requested_window=window(start))
    assert projected.summary.selected_conversions.value is None
    assert projected.summary.selected_conversions.unsupported_days == 7
    assert not projected.summary.selected_zero_for_requested_window
