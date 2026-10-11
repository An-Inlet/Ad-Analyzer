"""Separate selected-event commitments: no provider or persistence qualification."""

from datetime import date
from typing import Any

import pytest
from app.campaign_performance import selected_contracts as c
from app.campaign_performance.presence_contracts import _canonical
from pydantic import ValidationError


def request() -> c.SelectedCaptureRequestV1:
    scope = c.ReportingScopeV1(
        workspace_id=1,
        connection_id=2,
        account_id=3,
        platform="google_ads",
        source_connection_ref="a" * 32,
        generation=1,
        privacy_revision=0,
        native_account_id="1234567890",
        currency="USD",
        time_zone="America/New_York",
    )
    selection = c.CustomerEventSelectionV1.model_validate(
        dict(
            selection_id="b" * 32,
            scope=scope,
            confirmed_by_customer_id="4" * 32,
            confirmed_at="2026-10-01T10:00:00Z",
            event_namespace="google_conversion_action",
            native_event_owner_id="1234567890",
            native_event_id="customers/1234567890/conversionActions/123",
            metric_family="conversions",
            api_version="v24",
            query_profile_digest="c" * 64,
        )
    )
    return c.SelectedCaptureRequestV1.model_validate(
        dict(
            capture_id="d" * 32,
            aggregate=dict(
                completion_id="e" * 32,
                manifest_digest="f" * 64,
                scope=scope,
                starts_on="2026-09-29",
                ends_on="2026-09-30",
            ),
            selection=selection,
            selection_digest=c.selection_digest(selection),
            requested_starts_on="2026-09-29",
            requested_ends_on="2026-09-30",
            started_at="2026-10-01T12:00:00Z",
            producer_contract="fixture.action.v1",
            query_profile_digest="c" * 64,
            attribution=dict(
                click_window_days=None,
                view_window_days=None,
                report_time_basis="unknown",
                provenance="provider_default_unknown",
                producer_contract="fixture.action.v1",
            ),
        )
    )


def capture(*, state: str = "present", value: Any = "10") -> c.SelectedCaptureV1:
    req = request()
    digest = c.capture_request_digest(req)
    return c.SelectedCaptureV1.model_validate(
        dict(
            request=req,
            request_digest=digest,
            completed_at="2026-10-01T12:01:00Z",
            capability="supported",
            pagination_complete=True,
            page_count=1,
            facts=[
                dict(
                    capture_id=req.capture_id,
                    request_digest=digest,
                    campaign_id=5,
                    native_campaign_id="555",
                    metric_date="2026-09-30",
                    selected_conversions=dict(presence=state, value=value),
                    selected_value_micros=dict(presence="unsupported", value=None),
                )
            ],
        )
    )


def test_selected_count_independent_of_aggregate_and_roundtrips() -> None:
    result = capture()
    assert result.facts[0].selected_conversions.value == 10
    assert result.facts[0].selected_value_micros.value is None
    assert "conversions" not in c.AggregateDependencyV1.model_fields
    assert c.SelectedCaptureV1.model_validate_json(result.model_dump_json()) == result
    c.validate_selected_dependencies(result, result.request.aggregate, result.request.selection)


@pytest.mark.parametrize(
    "state,value",
    [
        ("present", "0"),
        ("missing", None),
        ("unsupported", None),
        ("legacy_unknown", None),
    ],
)
def test_zero_missing_unsupported_unknown_are_distinct(state: str, value: Any) -> None:
    result = capture(state=state, value=value)
    assert result.facts[0].selected_conversions.presence == state
    assert (result.facts[0].selected_conversions.value == 0) is (state == "present")


@pytest.mark.parametrize("value", [True, 0.0, -1, "NaN", "0.0000001", "1000000000000"])
def test_raw_invalid_values_cannot_qualify(value: Any) -> None:
    with pytest.raises(ValidationError):
        capture(value=value)


@pytest.mark.parametrize(
    "field,value",
    [
        ("completion_id", "1" * 32),
        ("manifest_digest", "2" * 64),
        ("starts_on", date(2026, 9, 28)),
    ],
)
def test_aggregate_correction_invalidates_whole_selected_graph(field: str, value: Any) -> None:
    original = capture()
    changed = original.request.aggregate.model_copy(update={field: value})
    with pytest.raises(ValueError, match="dependencies changed"):
        c.validate_selected_dependencies(original, changed, original.request.selection)


@pytest.mark.parametrize(
    "field,value",
    [
        ("workspace_id", 9),
        ("account_id", 9),
        ("connection_id", 9),
        ("generation", 2),
        ("privacy_revision", 1),
        ("currency", "EUR"),
        ("time_zone", "UTC"),
        ("native_account_id", "9999999999"),
        ("source_connection_ref", "9" * 32),
    ],
)
def test_current_scope_change_is_not_adopted(field: str, value: Any) -> None:
    original = capture()
    changed = original.request.aggregate.model_copy(
        update={
            "scope": original.request.aggregate.scope.model_copy(update={field: value}),
        }
    )
    with pytest.raises(ValueError, match="dependencies changed"):
        c.validate_selected_dependencies(original, changed, original.request.selection)


@pytest.mark.parametrize(
    "field,value",
    [
        ("selection_id", "1" * 32),
        ("metric_family", "all_conversions"),
        ("native_event_id", "customers/1234567890/conversionActions/456"),
        ("api_version", "v25"),
        ("query_profile_digest", "9" * 64),
    ],
)
def test_selection_change_invalidates_capture(field: str, value: Any) -> None:
    original = capture()
    changed = original.request.selection.model_copy(update={field: value})
    with pytest.raises(ValueError, match="dependencies changed"):
        c.validate_selected_dependencies(original, original.request.aggregate, changed)


@pytest.mark.parametrize(
    "update",
    [
        {"pagination_complete": False},
        {"pagination_complete": 1},
        {"completed_at": 1790856000},
        {"page_count": 101},
        {"page_count": True},
        {"request_digest": "9" * 64},
        {"capability": "unsupported"},
        {"capability": "unknown"},
        {"spending_authorized": True},
        {"completed_at": "2026-10-01T11:59:00Z"},
    ],
)
def test_unsafe_copied_capture_revalidated(update: dict[str, Any]) -> None:
    original = capture()
    with pytest.raises(ValidationError):
        c.selected_capture_digest(original.model_copy(update=update))


@pytest.mark.parametrize(
    "update",
    [
        {"requested_starts_on": "2026-08-01"},
        {"requested_ends_on": "2026-10-01"},
        {"query_profile_digest": "9" * 64},
        {"selection_digest": "9" * 64},
        {"started_at": "2026-10-01T03:59:00Z"},
    ],
)
def test_request_does_not_expand_or_relabel_source(update: dict[str, Any]) -> None:
    original = request()
    with pytest.raises(ValidationError):
        c.capture_request_digest(original.model_copy(update=update))


def test_empty_returned_rows_not_filled_and_digest_commits_presence() -> None:
    original = capture()
    empty = c.SelectedCaptureV1.model_validate(original.model_copy(update={"facts": ()}))
    assert empty.facts == ()
    variants = [
        original,
        empty,
        capture(state="present", value="0"),
        capture(state="missing", value=None),
        capture(state="unsupported", value=None),
    ]
    assert len({c.selected_capture_digest(v) for v in variants}) == 5


@pytest.mark.parametrize(
    "update",
    [
        {"campaign_id": 6},
        {"native_campaign_id": "666"},
        {},
        {"metric_date": "2026-08-31"},
        {"capture_id": "9" * 32},
        {"request_digest": "9" * 64},
    ],
)
def test_duplicate_and_crossbound_rows_rejected(update: dict[str, Any]) -> None:
    original = capture()
    row = original.facts[0].model_copy(update=update)
    with pytest.raises(ValidationError):
        c.SelectedCaptureV1.model_validate(
            original.model_copy(
                update={
                    "facts": (original.facts[0], row),
                }
            )
        )


def test_digest_order_independent_but_binds_out_of_slice_rows() -> None:
    original = capture()
    earlier = original.facts[0].model_copy(update={"metric_date": date(2026, 9, 29)})
    first = original.model_copy(update={"facts": (original.facts[0], earlier)})
    second = original.model_copy(update={"facts": (earlier, original.facts[0])})
    assert c.selected_capture_digest(first) == c.selected_capture_digest(second)
    assert c.selected_capture_digest(first) != c.selected_capture_digest(original)


@pytest.mark.parametrize(
    "update",
    [
        {"native_event_owner_id": "9999999999"},
        {"event_namespace": "tiktok_event"},
        {"native_event_id": "Purchase"},
        {"confirmed_by_customer_id": True},
        {"metric_family": "actions"},
        {"api_version": "latest"},
    ],
)
def test_selection_exact_identity_and_definition(update: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        c.selection_digest(request().selection.model_copy(update=update))


def test_capture_size_limit_checked_incrementally(monkeypatch: pytest.MonkeyPatch) -> None:
    original = capture()
    monkeypatch.setattr(c, "MAX_SELECTED_BYTES", 1)
    with pytest.raises(ValidationError, match="byte capacity"):
        c.selected_capture_digest(original)


@pytest.mark.parametrize(
    "platform,source,namespace,family,event",
    [
        (
            "google_ads",
            "a" * 32,
            "google_conversion_action",
            "conversions",
            "customers/1234567890/conversionActions/123",
        ),
        ("meta_ads", "123", "meta_action_type", "actions", "offsite_conversion.purchase"),
        ("tiktok_ads", "a" * 32, "tiktok_event", "event_count", "fixture_event"),
    ],
)
def test_actual_customer_and_provider_id_shapes(
    platform: str,
    source: str,
    namespace: str,
    family: str,
    event: str,
) -> None:
    original = request().selection
    values = original.model_dump(mode="python")
    values.update(event_namespace=namespace, metric_family=family, native_event_id=event)
    values["scope"].update(platform=platform, source_connection_ref=source)
    result = c.CustomerEventSelectionV1.model_validate(values)
    assert result.confirmed_by_customer_id == "4" * 32
    assert result.scope.source_connection_ref == source
    # Shape validation does not certify that fixture_event is supported by TikTok.


@pytest.mark.parametrize("empty", [False, True])
def test_exact_serialized_capture_boundary(
    monkeypatch: pytest.MonkeyPatch,
    empty: bool,
) -> None:
    original = capture()
    if empty:
        original = original.model_copy(update={"facts": ()})
    size = len(_canonical(original))
    monkeypatch.setattr(c, "MAX_SELECTED_BYTES", size)
    c.SelectedCaptureV1.model_validate(original)
    monkeypatch.setattr(c, "MAX_SELECTED_BYTES", size - 1)
    with pytest.raises(ValidationError, match="byte capacity"):
        c.SelectedCaptureV1.model_validate(original)


def test_dst_fold_confirmation_and_completion_use_instants() -> None:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    zone = ZoneInfo("America/New_York")
    req = request()
    late_selection = req.selection.model_copy(
        update={
            "confirmed_at": datetime(2026, 11, 1, 1, 45, tzinfo=zone, fold=1),
        }
    )
    early_start = req.model_copy(
        update={
            "selection": late_selection,
            "selection_digest": c.selection_digest(late_selection),
            "started_at": datetime(2026, 11, 1, 1, 50, tzinfo=zone, fold=0),
        }
    )
    with pytest.raises(ValidationError, match="confirmed before capture"):
        c.SelectedCaptureRequestV1.model_validate(early_start)
    late_start = c.SelectedCaptureRequestV1.model_validate(
        req.model_copy(
            update={
                "started_at": datetime(2026, 11, 1, 1, 50, tzinfo=zone, fold=1),
            }
        )
    )
    with pytest.raises(ValidationError, match="completion precedes"):
        c.SelectedCaptureV1.model_validate(
            capture().model_copy(
                update={
                    "request": late_start,
                    "request_digest": c.capture_request_digest(late_start),
                    "completed_at": datetime(2026, 11, 1, 1, 55, tzinfo=zone, fold=0),
                    "facts": (),
                }
            )
        )


def test_changed_confirmation_dst_fold_is_not_equal_current_selection() -> None:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    req = request()
    zone = ZoneInfo("America/New_York")
    first = c.CustomerEventSelectionV1.model_validate(
        req.selection.model_copy(
            update={
                "confirmed_at": datetime(2026, 11, 1, 1, 30, tzinfo=zone, fold=0),
            }
        )
    )
    second = first.model_copy(
        update={
            "confirmed_at": datetime(2026, 11, 1, 1, 30, tzinfo=zone, fold=1),
        }
    )
    req = c.SelectedCaptureRequestV1.model_validate(
        req.model_copy(
            update={
                "selection": first,
                "selection_digest": c.selection_digest(first),
                "started_at": "2026-11-01T08:00:00Z",
            }
        )
    )
    original = c.SelectedCaptureV1.model_validate(
        capture().model_copy(
            update={
                "request": req,
                "request_digest": c.capture_request_digest(req),
                "completed_at": "2026-11-01T08:01:00Z",
                "facts": (),
            }
        )
    )
    with pytest.raises(ValueError, match="dependencies changed"):
        c.validate_selected_dependencies(original, req.aggregate, second)
