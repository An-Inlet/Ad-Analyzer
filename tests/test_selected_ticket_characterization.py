"""Prechange pure compatibility characterization, not SQL or timing qualification."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta, timezone, tzinfo
from typing import Any, ClassVar
from zoneinfo import ZoneInfo

import pytest
from app.campaign_performance.presence_contracts import CountCellV1, ReportedMetricPresenceV1
from app.commerce.reporting import MeasurementWindow
from app.goals.progress_contracts import GoalSalesProgressV1
from app.goals.schemas import GoalDefinition
from app.planning_catalog.metadata_contracts import ProviderReferenceV1
from app.planning_documents.context import AccountRef, ConfirmedGoalRef, ReportingWindow, TargetRef
from app.planning_documents.ports import CommerceEvidence, GenerationTicket
from app.planning_documents.selected_paired_evidence import SelectedPairedEvidenceV1
from app.planning_documents.selected_plan_bundle import SelectedPlanEvidenceBundleV1
from app.planning_documents.source_contracts import SourceFence
from pydantic import (
    SerializerFunctionWrapHandler,
    ValidationError,
    model_serializer,
    model_validator,
)

from tests.owner_review_v6_fixture import ready as owner_ready
from tests.test_planning_document_ports import commerce_data, ready_bundle
from tests.test_selected_paired_composer import ready as paired_ready
from tests.test_selected_plan_bundle import ready as selected_ready


@pytest.mark.parametrize("kind", ["selected", "paired", "owner"])
def test_genuine_fixture_repeated_declared_validation_is_stable(kind: str) -> None:
    if kind == "selected":
        ticket, bundle = selected_ready()
    elif kind == "paired":
        ticket, bundle, _ = paired_ready()
    else:
        ticket, evidence, _, _ = owner_ready()
        bundle = evidence.reporting
    original = (
        ticket.model_dump_json(),
        bundle.model_dump_json(),
        ticket.digest(),
        bundle.digest(),
    )
    bundle.assert_ticket(ticket)
    checked_ticket = GenerationTicket.model_validate(ticket)
    checked_bundle = type(bundle).model_validate(bundle)
    checked_bundle.assert_ticket(checked_ticket)
    assert (
        checked_ticket.model_dump_json(),
        checked_bundle.model_dump_json(),
        checked_ticket.digest(),
        checked_bundle.digest(),
    ) == original


@pytest.mark.parametrize("kind", ["selected", "paired"])
def test_public_subtype_validator_and_override_remain_observable(kind: str) -> None:
    events: list[str] = []
    sentinel = RuntimeError("synthetic subtype validator")

    class SelectedSubtype(SelectedPlanEvidenceBundleV1):
        armed: ClassVar[bool] = False

        @model_validator(mode="after")
        def custom(self) -> "SelectedSubtype":
            events.append("validate")
            if self.armed:
                raise sentinel
            return self

        def assert_ticket(self, ticket: GenerationTicket) -> None:
            events.append("public")
            super().assert_ticket(ticket)

    class PairedSubtype(SelectedPairedEvidenceV1):
        armed: ClassVar[bool] = False

        @model_validator(mode="after")
        def custom(self) -> "PairedSubtype":
            events.append("validate")
            if self.armed:
                raise sentinel
            return self

        def assert_ticket(self, ticket: GenerationTicket) -> None:
            events.append("public")
            super().assert_ticket(ticket)

    ticket, paired, _ = paired_ready()
    if kind == "selected":
        subtype: Any = SelectedSubtype.model_validate(paired.selected.model_dump(mode="python"))
    else:
        subtype = PairedSubtype.model_validate(paired.model_dump(mode="python"))
    events.clear()
    subtype.assert_ticket(ticket)
    assert events == ["public", "validate"]
    type(subtype).armed = True
    events.clear()
    with pytest.raises(RuntimeError) as caught:
        subtype.assert_ticket(ticket)
    assert caught.value is sentinel
    assert events == ["public", "validate"]
    # The reader's existing DECLARED parse is intentionally different from public type(self).
    declared = SelectedPlanEvidenceBundleV1 if kind == "selected" else SelectedPairedEvidenceV1
    events.clear()
    checked = declared.model_validate(subtype)
    assert type(checked) is declared
    assert events == []
    checked.assert_ticket(ticket)
    assert events == []


@pytest.mark.parametrize("kind", ["planning", "catalog", "presence"])
def test_declared_always_children_preserve_extra_refusal_and_reparse_same_fields(kind: str) -> None:
    events: list[str] = []

    class AccountSubtype(AccountRef):
        @model_validator(mode="after")
        def custom_validation(self) -> "AccountSubtype":
            events.append("validate")
            return self

        @model_serializer(mode="wrap")
        def custom(self, handler: SerializerFunctionWrapHandler) -> Any:
            events.append("serialize")
            return handler(self)

    class ReferenceSubtype(ProviderReferenceV1):
        @model_validator(mode="after")
        def custom_validation(self) -> "ReferenceSubtype":
            events.append("validate")
            return self

        @model_serializer(mode="wrap")
        def custom(self, handler: SerializerFunctionWrapHandler) -> Any:
            events.append("serialize")
            return handler(self)

    class CountSubtype(CountCellV1):
        @model_validator(mode="after")
        def custom_validation(self) -> "CountSubtype":
            events.append("validate")
            return self

        @model_serializer(mode="wrap")
        def custom(self, handler: SerializerFunctionWrapHandler) -> Any:
            events.append("serialize")
            return handler(self)

    class ExtraAccountSubtype(AccountSubtype):
        extra_marker: str = "synthetic"

    class ExtraReferenceSubtype(ReferenceSubtype):
        extra_marker: str = "synthetic"

    class ExtraCountSubtype(CountSubtype):
        extra_marker: str = "synthetic"

    ticket, paired, _ = paired_ready()
    extra_class: Any
    base: Any
    subtype_class: Any
    if kind == "planning":
        parent: Any = ticket.sources[0]
        field, base, subtype_class = "account", AccountRef, AccountSubtype
        parent_class: Any = SourceFence
        extra_class = ExtraAccountSubtype
    elif kind == "catalog":
        parent = paired.selected.performance[0].target
        field, base, subtype_class = "provider_reference", ProviderReferenceV1, ReferenceSubtype
        parent_class = TargetRef
        extra_class = ExtraReferenceSubtype
    else:
        parent = paired.traffic_graphs[0].facts[0]
        field, base, subtype_class = "selected_conversions", CountCellV1, CountSubtype
        parent_class = ReportedMetricPresenceV1
        extra_class = ExtraCountSubtype
    original = getattr(parent, field)
    extra = extra_class.model_validate(original.model_dump(mode="python"))
    with pytest.raises(ValidationError) as caught:
        parent_class.model_validate(parent.model_copy(update={field: extra}))
    errors = caught.value.errors()
    assert len(errors) == 1
    assert errors[0]["loc"] == (field, "extra_marker")
    assert errors[0]["type"] == "extra_forbidden"
    child = subtype_class.model_validate(original.model_dump(mode="python"))
    events.clear()
    checked = parent_class.model_validate(parent.model_copy(update={field: child}))
    returned = getattr(checked, field)
    assert type(returned) is base
    assert returned.model_dump(mode="json") == original.model_dump(mode="json")
    assert events == []
    assert "extra_marker" not in returned.__dict__


@pytest.mark.parametrize("kind", ["goal", "commerce"])
def test_legacy_dump_edges_reparse_custom_children_and_preserve_failures(
    kind: str, record_property: Callable[[str, object], None]
) -> None:
    events: list[str] = []

    class WindowSubtype(MeasurementWindow):
        @model_serializer(mode="wrap")
        def custom(self, handler: SerializerFunctionWrapHandler) -> Any:
            events.append("window")
            return handler(self)

    class GoalSubtype(GoalDefinition):
        corrupt: ClassVar[bool] = False

        @model_serializer(mode="wrap")
        def custom(self, handler: SerializerFunctionWrapHandler) -> Any:
            events.append("document")
            result = handler(self)
            if self.corrupt:
                result["budget_micros"] = "not-an-integer"
            return result

    class ProgressSubtype(GoalSalesProgressV1):
        corrupt: ClassVar[bool] = False

        @model_serializer(mode="wrap")
        def custom(self, handler: SerializerFunctionWrapHandler) -> Any:
            events.append("document")
            result = handler(self)
            if self.corrupt:
                result["status"] = "invalid-status"
            return result

    ticket, evidence = ready_bundle()
    base: Any
    subtype_class: Any
    if kind == "goal":
        parent: Any = ticket.inputs.goal
        field, base, subtype_class = "definition", GoalDefinition, GoalSubtype
        parent_class: Any = ConfirmedGoalRef
    else:
        parent = CommerceEvidence.model_validate(commerce_data(ticket, evidence))
        field, base, subtype_class = "document", GoalSalesProgressV1, ProgressSubtype
        parent_class = CommerceEvidence
    original = getattr(parent, field)
    child = subtype_class.model_validate(original.model_dump(mode="python"))
    window = WindowSubtype.model_validate(original.target_window.model_dump(mode="python"))
    child = child.model_copy(update={"target_window": window})
    supplied = parent.model_copy(update={field: child})
    events.clear()
    checked = parent_class.model_validate(supplied)
    original_trace = tuple(events)
    record_property("original_serializer_trace", ",".join(original_trace))
    assert original_trace[0] == "document"
    assert original_trace.count("document") == 1
    assert set(original_trace) <= {"document", "window"}
    assert original_trace.count("window") <= 1
    returned = getattr(checked, field)
    assert type(returned) is base
    assert type(returned.target_window) is MeasurementWindow
    assert checked.model_dump_json() == parent.model_dump_json()
    events.clear()
    assert parent_class.model_validate(checked).model_dump_json() == parent.model_dump_json()
    assert events == []
    subtype_class.corrupt = True
    with pytest.raises(ValidationError):
        parent_class.model_validate(supplied)
    assert tuple(events) == original_trace


class CustomZone(tzinfo):
    def tzname(self, dt: datetime | None) -> str:
        return "Synthetic custom zone"

    def utcoffset(self, dt: datetime | None) -> timedelta:
        return timedelta(hours=-4)

    def dst(self, dt: datetime | None) -> timedelta:
        return timedelta(0)


@pytest.mark.parametrize("kind", ["utc", "fixed", "fold", "custom"])
def test_aware_datetime_preserves_resident_timezone_behavior(kind: str) -> None:
    zones = {
        "utc": UTC,
        "fixed": timezone(timedelta(hours=-4)),
        "fold": ZoneInfo("America/New_York"),
        "custom": CustomZone(),
    }
    zone = zones[kind]
    start = datetime(2026, 11, 1, 1, 15, tzinfo=zone, fold=0)
    end = datetime(2026, 11, 1, 1, 45, tzinfo=zone, fold=1)
    window = ReportingWindow(starts_at=start, ends_at_exclusive=end)
    checked = ReportingWindow.model_validate(window)
    assert checked.starts_at.tzinfo is zone
    assert checked.ends_at_exclusive.tzinfo is zone
    assert checked.ends_at_exclusive.fold == 1
    assert checked.starts_at.astimezone(UTC) == start.astimezone(UTC)
    assert checked.ends_at_exclusive.astimezone(UTC) == end.astimezone(UTC)
    assert checked.model_dump_json() == window.model_dump_json()
    assert (type(checked.starts_at.tzinfo) is CustomZone) == (kind == "custom")


@pytest.mark.parametrize("kind", ["source", "capture"])
def test_copied_invalid_nested_originals_still_reject(kind: str) -> None:
    ticket, bundle = selected_ready()
    if kind == "source":
        source = ticket.sources[0]
        bad = source.model_copy(
            update={"account": source.account.model_copy(update={"account_id": True})}
        )
        ticket = ticket.model_copy(update={"sources": (bad,)})
    else:
        graph = bundle.selected_captures[0]
        fact = graph.capture.facts[0]
        bad_cell = fact.selected_conversions.model_copy(update={"value": True})
        bad_fact = fact.model_copy(update={"selected_conversions": bad_cell})
        capture = graph.capture.model_copy(update={"facts": (bad_fact,) + graph.capture.facts[1:]})
        bundle = bundle.model_copy(
            update={"selected_captures": (graph.model_copy(update={"capture": capture}),)}
        )
    with pytest.raises(ValueError):
        bundle.assert_ticket(ticket)
