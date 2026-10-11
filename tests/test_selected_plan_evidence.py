"""Pure arithmetic/full-graph evidence; no original-session or live qualification."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal, localcontext
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from app.campaign_performance.selected_contracts import SelectedCaptureV1
from app.planning_documents.context import AccountRef, ReportingWindow
from app.planning_documents.ports import SourceFence
from app.planning_documents.selected_plan_evidence import (
    SelectedCampaignBindingV1,
    SelectedPlanCaptureV1,
    SelectedPlanProjectionV1,
    project_selected_plan_window,
    selected_local_days,
)

from tests.test_selected_reporting_contracts import capture
from tests.test_selected_summary import two_days


def graph(value: SelectedCaptureV1 | None = None) -> SelectedPlanCaptureV1:
    return SelectedPlanCaptureV1(
        source_fence=SourceFence(
            account=AccountRef(
                workspace_id=1,
                account_id=3,
                connection_id=2,
                platform="google_ads",
                connection_version="fixture-source:1",
            ),
            source_binding_digest="1" * 64,
            source_revision="fixture-source:1",
            privacy_revision=0,
        ),
        capture=value or capture(),
        campaigns=(SelectedCampaignBindingV1(campaign_id=5, native_campaign_id="555"),),
    )


def window() -> ReportingWindow:
    return ReportingWindow(
        starts_at=datetime(2026, 9, 29, tzinfo=ZoneInfo("America/New_York")),
        ends_at_exclusive=datetime(2026, 10, 1, tzinfo=ZoneInfo("America/New_York")),
    )


@pytest.mark.parametrize("value", ["10", "0", "0.123456"])
def test_whole_graph_roundtrip_positive_partial_and_exact_decimal(value: str) -> None:
    whole = graph(capture(value=value))
    projected = project_selected_plan_window(whole, campaign_id=5, requested_window=window())
    proof = SelectedPlanProjectionV1(captures=(whole,), windows=(projected,))
    assert projected.summary.conversions.value == Decimal(value)
    assert not projected.summary.zero_for_requested_window
    assert projected.summary.missing_calendar_days == 1
    assert proof.advertising_writes_enabled is False
    assert SelectedPlanProjectionV1.model_validate_json(proof.model_dump_json()) == proof


def test_only_all_observed_explicit_zero_days_qualify() -> None:
    for value, expected in ((two_days(), True), (capture(value="0"), False)):
        result = project_selected_plan_window(
            graph(value), campaign_id=5, requested_window=window()
        )
        assert result.summary.zero_for_requested_window is expected
        assert result.summary.value_micros.value is None


@pytest.mark.parametrize("state", ["missing", "unsupported", "legacy_unknown"])
def test_nonpresent_cells_do_not_become_zero(state: str) -> None:
    whole = graph(two_days(state=state, value=None))
    result = project_selected_plan_window(whole, campaign_id=5, requested_window=window())
    assert result.summary.conversions.value is None
    assert not result.summary.zero_for_requested_window


@pytest.mark.parametrize(
    "field", ["conversions", "zero_for_requested_window", "native_campaign_id"]
)
def test_arbitrary_copied_summary_cannot_qualify(field: str) -> None:
    whole = graph()
    result = project_selected_plan_window(whole, campaign_id=5, requested_window=window())
    changed: Any = {
        "conversions": result.summary.conversions.model_copy(update={"value": Decimal(0)}),
        "zero_for_requested_window": True,
        "native_campaign_id": "777",
    }[field]
    corrupt = result.model_copy(
        update={"summary": result.summary.model_copy(update={field: changed})}
    )
    with pytest.raises(ValueError, match="arithmetic or provenance"):
        SelectedPlanProjectionV1(captures=(whole,), windows=(corrupt,))


def test_missing_duplicate_and_changed_whole_graph_rejected() -> None:
    whole = graph()
    result = project_selected_plan_window(whole, campaign_id=5, requested_window=window())
    for captures, windows in (
        ((), (result,)),
        ((whole, whole), (result,)),
        ((whole,), (result, result)),
    ):
        with pytest.raises(ValueError):
            SelectedPlanProjectionV1(captures=captures, windows=windows)
    changed = graph(capture(value="1"))
    with pytest.raises(ValueError, match="arithmetic or provenance"):
        SelectedPlanProjectionV1(captures=(changed,), windows=(result,))


@pytest.mark.parametrize("kind", ["privacy", "account", "mapping", "hidden_fact"])
def test_unsafe_copy_scope_and_full_graph_revalidation(kind: str) -> None:
    whole = graph()
    if kind == "privacy":
        corrupt = whole.model_copy(
            update={"source_fence": whole.source_fence.model_copy(update={"privacy_revision": 1})}
        )
    elif kind == "account":
        corrupt = whole.model_copy(
            update={"source_fence": whole.source_fence.model_copy(update={"source_revision": "2"})}
        )
    elif kind == "mapping":
        corrupt = whole.model_copy(update={"campaigns": ()})
    else:
        fact = whole.capture.facts[0].model_copy(update={"request_digest": "9" * 64})
        corrupt = whole.model_copy(
            update={"capture": whole.capture.model_copy(update={"facts": (fact,)})}
        )
    with pytest.raises(ValueError):
        corrupt.pin()


def test_equivalent_utc_window_and_no_float_rounding() -> None:
    local = window()
    utc = ReportingWindow(
        starts_at=local.starts_at.astimezone(UTC),
        ends_at_exclusive=local.ends_at_exclusive.astimezone(UTC),
    )
    with localcontext() as precision:
        precision.prec = 2
        result = project_selected_plan_window(
            graph(two_days(value="999999999999.999999")), campaign_id=5, requested_window=utc
        )
    assert result.summary.conversions.value == Decimal("1999999999999.999998")


@pytest.mark.parametrize("kind", ["unaligned", "outside", "open"])
def test_invalid_requested_windows(kind: str) -> None:
    requested = window()
    if kind == "unaligned":
        requested = requested.model_copy(
            update={"starts_at": requested.starts_at + timedelta(hours=1)}
        )
    elif kind == "outside":
        requested = requested.model_copy(
            update={"starts_at": requested.starts_at - timedelta(days=1)}
        )
    else:
        requested = requested.model_copy(
            update={"ends_at_exclusive": requested.ends_at_exclusive + timedelta(days=1)}
        )
    with pytest.raises(ValueError):
        project_selected_plan_window(graph(), campaign_id=5, requested_window=requested)


def test_dst_local_calendar_not_fixed_utc_duration() -> None:
    zone = ZoneInfo("America/New_York")
    requested = ReportingWindow(
        starts_at=datetime(2026, 11, 1, tzinfo=zone),
        ends_at_exclusive=datetime(2026, 11, 2, tzinfo=zone),
    )
    starts, ends = selected_local_days(
        requested, time_zone=zone.key, completed_at=datetime(2026, 11, 3, tzinfo=UTC)
    )
    assert starts == ends
    folded = requested.model_copy(
        update={"starts_at": datetime(2026, 11, 1, 1, 30, tzinfo=zone, fold=1)}
    )
    with pytest.raises(ValueError):
        selected_local_days(
            folded, time_zone=zone.key, completed_at=datetime(2026, 11, 3, tzinfo=UTC)
        )


@pytest.mark.parametrize("value", [True, 1.0, "1"])
@pytest.mark.parametrize("field", ["requested_days", "returned_days", "missing_calendar_days"])
def test_summary_day_counts_reject_json_and_copied_coercions(field: str, value: Any) -> None:
    whole = graph()
    result = project_selected_plan_window(whole, campaign_id=5, requested_window=window())
    payload = result.model_dump(mode="json")
    payload["summary"][field] = value
    with pytest.raises(ValueError):
        type(result).model_validate(payload)
    copied = result.model_copy(update={"summary": result.summary.model_copy(update={field: value})})
    with pytest.raises(ValueError):
        SelectedPlanProjectionV1(captures=(whole,), windows=(copied,))


@pytest.mark.parametrize(
    "field,value",
    [
        ("conversions", True),
        ("conversions", 10.0),
        ("value_micros", True),
        ("value_micros", 1.0),
        ("value_micros", "1"),
    ],
)
def test_metric_specific_summary_types_reject_coercion(field: str, value: Any) -> None:
    whole = graph()
    result = project_selected_plan_window(whole, campaign_id=5, requested_window=window())
    payload = result.model_dump(mode="json")
    payload["summary"][field]["value"] = value
    with pytest.raises(ValueError):
        type(result).model_validate(payload)
    metric = getattr(result.summary, field).model_copy(update={"value": value})
    copied = result.model_copy(
        update={"summary": result.summary.model_copy(update={field: metric})}
    )
    with pytest.raises(ValueError):
        SelectedPlanProjectionV1(captures=(whole,), windows=(copied,))


def test_projection_builds_one_validated_index_per_complete_capture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.campaign_performance.selected_summary import SelectedSummaryContext
    from app.planning_documents import selected_plan_evidence

    whole = graph(two_days(value="10"))
    zone = ZoneInfo("America/New_York")
    windows = tuple(
        project_selected_plan_window(
            whole,
            campaign_id=5,
            requested_window=ReportingWindow(
                starts_at=datetime(2026, 9, day, tzinfo=zone),
                ends_at_exclusive=datetime(2026, 9, day, tzinfo=zone) + timedelta(days=1),
            ),
        )
        for day in (29, 30)
    )
    calls: list[int] = []

    class Counted(SelectedSummaryContext):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            calls.append(1)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(selected_plan_evidence, "SelectedSummaryContext", Counted)
    proof = SelectedPlanProjectionV1(captures=(whole,), windows=windows)
    assert len(proof.windows) == 2 and len(calls) == 1


def test_prepared_reader_validates_input_and_exposes_only_immutable_values() -> None:
    from app.planning_documents.selected_plan_evidence import PreparedSelectedPlanProjection

    original = graph()
    prepared = PreparedSelectedPlanProjection(original)
    assert prepared.pin == original.pin()
    assert prepared.snapshot() == original
    assert prepared.read(5, window()).summary.conversions.value == 10
    with pytest.raises(ValueError):
        PreparedSelectedPlanProjection(original.model_copy(update={"campaigns": ()}))
    with pytest.raises(AttributeError):
        object.__setattr__(prepared, "pin", original.pin())
    changed = original.model_copy(update={"capture": capture(value="1")})
    assert changed != prepared.snapshot()
    assert prepared.read(5, window()).summary.conversions.value == 10
