"""Pin projections share pure validation only; never database authority."""

from datetime import datetime, timedelta, tzinfo
from typing import Any

import pytest
from app.campaign_performance.selected_contracts import (
    SelectedCaptureV1,
    capture_request_digest,
    selected_capture_digest,
)
from app.planning_documents.selected_capture_projection import (
    _inert_capture,
    selected_capture_projection,
)
from app.planning_documents.selected_observation_provenance import selected_observation_provenance
from app.planning_documents.selected_plan_evidence import SelectedPlanCaptureV1
from pydantic import ValidationError

from tests.test_selected_plan_evidence import graph
from tests.test_selected_reporting_contracts import capture


def test_pin_validates_capture_once(monkeypatch: pytest.MonkeyPatch) -> None:
    whole = graph()
    expected = whole._pin()
    original = SelectedCaptureV1.model_validate
    calls = 0

    def observed(cls: type[SelectedCaptureV1], /, value: Any, **kwargs: Any) -> SelectedCaptureV1:
        nonlocal calls
        calls += 1
        return original(value, **kwargs)

    monkeypatch.setattr(SelectedCaptureV1, "model_validate", classmethod(observed))
    assert whole._pin() == expected
    assert calls == 1


@pytest.mark.parametrize("state,value", [("present", "10"), ("present", "0"), ("missing", None)])
def test_exact_projection_matches_separate_helpers(state: str, value: str | None) -> None:
    original = capture(state=state, value=value)
    assert _inert_capture(original)
    digest, provenance = selected_capture_projection(original)
    assert digest == selected_capture_digest(original)
    assert (
        provenance.model_dump_json() == selected_observation_provenance(original).model_dump_json()
    )


def test_v2_projection_preserves_settings_bytes() -> None:
    from tests.test_meta_selected_count import request

    req = request()
    original = SelectedCaptureV1(
        schema_version="inlet.selected-capture.v2",
        request=req,
        request_digest=capture_request_digest(req),
        completed_at=req.started_at,
        capability="supported",
        pagination_complete=True,
        page_count=1,
        facts=(),
    )
    assert _inert_capture(original)
    digest, provenance = selected_capture_projection(original)
    assert digest == selected_capture_digest(original)
    assert (
        provenance.model_dump_json() == selected_observation_provenance(original).model_dump_json()
    )


@pytest.mark.parametrize("public", [selected_capture_digest, selected_observation_provenance])
def test_public_helpers_still_reject_unvalidated_copies(public: Any) -> None:
    changed = capture().model_copy(update={"request_digest": "0" * 64})
    with pytest.raises(ValidationError):
        public(changed)


@pytest.mark.parametrize("field,value", [("request_digest", "0" * 64), ("page_count", 0)])
def test_invalid_copy_preserves_first_validation_error(field: str, value: Any) -> None:
    changed = capture().model_copy(update={field: value})
    with pytest.raises(ValidationError) as separate:
        selected_capture_digest(changed)
    with pytest.raises(ValidationError) as combined:
        selected_capture_projection(changed)
    assert combined.value.errors(include_context=False) == separate.value.errors(
        include_context=False
    )
    assert [
        (type(error.get("ctx", {}).get("error")), str(error.get("ctx", {}).get("error")))
        for error in combined.value.errors()
    ] == [
        (type(error.get("ctx", {}).get("error")), str(error.get("ctx", {}).get("error")))
        for error in separate.value.errors()
    ]


def test_subclass_retains_both_validations(monkeypatch: pytest.MonkeyPatch) -> None:
    class CaptureSubtype(SelectedCaptureV1):
        pass

    value = CaptureSubtype.model_validate(capture().model_dump())
    assert not _inert_capture(value)
    original = SelectedCaptureV1.model_validate
    calls = 0

    def observed(cls: type[SelectedCaptureV1], /, value: Any, **kwargs: Any) -> SelectedCaptureV1:
        nonlocal calls
        calls += 1
        return original(value, **kwargs)

    monkeypatch.setattr(SelectedCaptureV1, "model_validate", classmethod(observed))
    selected_capture_projection(value)
    assert calls == 2


def test_custom_timezone_keeps_original_callback_sequence() -> None:
    events: list[str] = []

    class CustomZone(tzinfo):
        def utcoffset(self, dt: datetime | None) -> timedelta:
            events.append("offset")
            return timedelta(0)

        def dst(self, dt: datetime | None) -> timedelta:
            events.append("dst")
            return timedelta(0)

        def tzname(self, dt: datetime | None) -> str:
            events.append("name")
            return "fixture"

    original = capture()
    changed = original.model_copy(
        update={"completed_at": original.completed_at.replace(tzinfo=CustomZone())}
    )
    assert not _inert_capture(changed)
    assert not events
    expected = selected_capture_digest(changed), selected_observation_provenance(changed)
    expected_events = list(events)
    events.clear()
    assert selected_capture_projection(changed) == expected
    assert events == expected_events


def test_guard_rejects_unknown_and_cycles_without_callbacks() -> None:
    class Hostile:
        def __getattribute__(self, key: str) -> Any:
            raise AssertionError("guard invoked custom attribute access")

    assert not _inert_capture(Hostile())
    changed = capture()
    object.__setattr__(changed, "request", changed)
    assert not _inert_capture(changed)


@pytest.mark.parametrize("slot", ["__pydantic_private__", "__pydantic_extra__"])
def test_guard_rejects_custom_state(slot: str) -> None:
    changed = capture()
    object.__setattr__(changed, slot, {"unexpected": "state"})
    assert not _inert_capture(changed)


def test_guard_rejects_undeclared_resident_field() -> None:
    changed = capture()
    object.__setattr__(changed, "unexpected", "state")
    assert not _inert_capture(changed)


@pytest.mark.parametrize("slot", ["__pydantic_private__", "__pydantic_extra__"])
def test_guard_treats_missing_slots_as_ineligible(slot: str) -> None:
    changed = capture()
    object.__delattr__(changed, slot)
    assert not _inert_capture(changed)


def test_pin_rereads_capture_replaced_by_custom_callback() -> None:
    whole = graph()
    initial = whole.capture
    replacement = initial.model_copy(
        update={"completed_at": initial.completed_at + timedelta(seconds=1)}
    )

    class ReplacingZone(tzinfo):
        def utcoffset(self, dt: datetime | None) -> timedelta:
            object.__setattr__(whole, "capture", replacement)
            return timedelta(0)

        def dst(self, dt: datetime | None) -> timedelta:
            return timedelta(0)

        def tzname(self, dt: datetime | None) -> str:
            return "fixture"

    dirty = initial.model_copy(
        update={"completed_at": initial.completed_at.replace(tzinfo=ReplacingZone())}
    )
    object.__setattr__(whole, "capture", dirty)
    pin = whole._pin()
    assert pin.observation_provenance is not None
    assert pin.observation_provenance.completed_at == replacement.completed_at
    assert pin.capture_digest == selected_capture_digest(initial)


def test_fallback_second_validation_preserves_exception_and_callback_prefix() -> None:
    events: list[str] = []
    fail_after: int | None = None

    class FailingZone(tzinfo):
        def utcoffset(self, dt: datetime | None) -> timedelta:
            events.append("offset")
            if fail_after is not None and len(events) > fail_after:
                raise RuntimeError("fixture second validation")
            return timedelta(0)

        def dst(self, dt: datetime | None) -> timedelta:
            return timedelta(0)

        def tzname(self, dt: datetime | None) -> str:
            return "fixture"

    original = capture()
    changed = original.model_copy(
        update={"completed_at": original.completed_at.replace(tzinfo=FailingZone())}
    )
    selected_capture_digest(changed)
    fail_after = len(events)
    assert fail_after > 0
    events.clear()
    with pytest.raises(ValidationError, match="fixture second validation") as separate:
        selected_capture_digest(changed)
        selected_observation_provenance(changed)
    expected_events = list(events)
    events.clear()
    with pytest.raises(ValidationError, match="fixture second validation") as combined:
        selected_capture_projection(changed)
    assert events == expected_events
    assert combined.value.errors(include_input=False) == separate.value.errors(include_input=False)


def test_custom_graph_preserves_attribute_evaluation_order() -> None:
    events: list[str] = []

    class GraphSubtype(SelectedPlanCaptureV1):
        def __getattribute__(self, key: str) -> Any:
            if key in {"capture", "source_fence", "campaigns"}:
                events.append(key)
            return super().__getattribute__(key)

    whole = graph()
    custom = GraphSubtype.model_construct(**whole.__dict__)
    events.clear()
    assert custom._pin() == whole._pin()
    assert events == [
        "capture",
        "source_fence",
        "source_fence",
        "capture",
        "capture",
        "capture",
        "campaigns",
    ]
