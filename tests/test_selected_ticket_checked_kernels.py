"""Strict same-call parity; SQL-separated currentness is qualified independently."""

import ast
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime, timedelta, timezone, tzinfo
from pathlib import Path
from typing import Any, cast
from zoneinfo import ZoneInfo

import pytest
from app.commerce.reporting import MeasurementWindow
from app.goals.progress_contracts import ClosedDayCoverageV1, GoalSalesProgressV1
from app.planning_documents import selected_paired_evidence as paired_module
from app.planning_documents import selected_plan_bundle as selected_module
from app.planning_documents.common import fingerprint
from app.planning_documents.ports import CommerceEvidence, GenerationTicket
from app.planning_documents.selected_paired_evidence import SelectedPairedEvidenceV1
from app.planning_documents.selected_plan_bundle import SelectedPlanEvidenceBundleV1
from pydantic import BaseModel, ValidationError
from pydantic_core import TzInfo

from tests.owner_review_v6_fixture import ready as owner_ready
from tests.test_planning_document_ports import commerce_data, ready_bundle
from tests.test_selected_paired_composer import ready as paired_ready
from tests.test_selected_plan_bundle import ready as selected_ready

BASELINES = {
    "selected": (
        "d56362940e52f5af4ea1f521e1d547327134a85b496a392575b5fa08ec169548",
        "529062740a815e25f3f510d1aec5864e347e88a11d01531859c02a4c7dab869c",
        "6b248b0a1efd7983cf81e81c4de1bd38aa81d91ac9e22ff24ba53de42919bfc4",
        "c565029075c1479f28489d4a6a7aa0c490737061efa76f243239735b71932cca",
    ),
    "paired": (
        "d56362940e52f5af4ea1f521e1d547327134a85b496a392575b5fa08ec169548",
        "529062740a815e25f3f510d1aec5864e347e88a11d01531859c02a4c7dab869c",
        "e0671bef7f41cdac83716b1d9352c1169c34fbca86eb813ab654c8e6ba848cef",
        "532dc6fe9c79f4efc09dd5a351ea119cfa748e228174abaf1cb82efd50e116cf",
    ),
    "owner": (
        "353d9aacef0e24a7ee98045c6dc5e93813d6503ee5a4b9b22c5f1669ed9e0a43",
        "2db0fb3d5bfc225da0157c90ac3702d785dd4a5d08dc04d5144d803b73b02b65",
        "9d508ecb5b2885a4c9332b095ec14a42ac435ced99c9c4eb212ce4e4162c0f5f",
        "f764f24c0c9283fb05a5031db8506c0c749a4b578ae5a7d1b7b5371feaf90a5d",
    ),
}


def fixture(kind: str) -> tuple[Any, Any]:
    if kind == "selected":
        return selected_ready()
    if kind == "paired":
        ticket, bundle, _ = paired_ready()
        return ticket, bundle
    ticket, evidence, _, _ = owner_ready()
    return ticket, evidence.reporting


def original_selected(bundle: Any, ticket: Any) -> None:
    bundle = type(bundle).model_validate(bundle)
    ticket = GenerationTicket.model_validate(ticket)
    selected_module._assert_selected_ticket_checked(bundle, ticket)


def original_paired(bundle: Any, ticket: Any) -> None:
    bundle = type(bundle).model_validate(bundle)
    ticket = GenerationTicket.model_validate(ticket)
    original_selected(bundle.selected, ticket)
    paired_module._assert_paired_ticket_remaining(bundle, ticket)


@pytest.mark.parametrize("kind", ["selected", "paired", "owner"])
@pytest.mark.parametrize("roundtrip", [False, True])
def test_original_byte_goldens_and_actual_eligibility(
    kind: str,
    roundtrip: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Original pre-enrichment projection: compatibility goldens must stay unchanged.
    from tests.test_selected_observation_provenance import legacy_pin_projection

    legacy_pin_projection(monkeypatch)
    ticket, bundle = fixture(kind)
    if roundtrip:
        ticket = GenerationTicket.model_validate_json(ticket.model_dump_json())
        bundle = type(bundle).model_validate_json(bundle.model_dump_json())
        assert type(ticket.prepared_at.tzinfo) is TzInfo
    assert selected_module._inert_selected_values(ticket, bundle)
    expected = BASELINES[kind]
    assert hashlib.sha256(ticket.model_dump_json().encode()).hexdigest() == expected[0]
    assert ticket.digest() == expected[1]
    assert hashlib.sha256(bundle.model_dump_json().encode()).hexdigest() == expected[2]
    assert bundle.digest() == expected[3]
    checked: Any
    if kind == "selected":
        checked, checked_ticket = selected_module._validate_selected_ticket_pair(bundle, ticket)
    else:
        checked, checked_ticket = paired_module._validate_paired_ticket_pair(bundle, ticket)
    assert checked.model_dump_json() == bundle.model_dump_json()
    assert checked_ticket.model_dump_json() == ticket.model_dump_json()


@pytest.mark.parametrize("boundary", ["public_paired", "selected_reader", "paired_reader"])
def test_only_documented_immediate_reparses_removed(
    boundary: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    ticket, paired, _ = paired_ready()
    calls: Counter[str] = Counter()
    for cls in (GenerationTicket, SelectedPlanEvidenceBundleV1, SelectedPairedEvidenceV1):
        original = cast(Any, cls).model_validate.__func__

        def wrapped(
            model: type[Any], /, value: Any, *, _original: Any = original, **kwargs: Any
        ) -> Any:
            calls[model.__name__] += 1
            return _original(model, value, **kwargs)

        monkeypatch.setattr(cls, "model_validate", classmethod(wrapped))
    b: Any
    if boundary == "public_paired":
        original_paired(paired, ticket)
    elif boundary == "selected_reader":
        t = GenerationTicket.model_validate(ticket)
        b = SelectedPlanEvidenceBundleV1.model_validate(paired.selected)
        original_selected(b, t)
    else:
        t = GenerationTicket.model_validate(ticket)
        b = SelectedPairedEvidenceV1.model_validate(paired)
        original_paired(b, t)
    before = calls.copy()
    calls.clear()
    if boundary == "public_paired":
        paired.assert_ticket(ticket)
        removed = {"GenerationTicket": 1, "SelectedPlanEvidenceBundleV1": 1}
    elif boundary == "selected_reader":
        selected_module._validate_selected_ticket_pair(paired.selected, ticket)
        removed = {"GenerationTicket": 1, "SelectedPlanEvidenceBundleV1": 1}
    else:
        paired_module._validate_paired_ticket_pair(paired, ticket)
        removed = {
            "GenerationTicket": 2,
            "SelectedPlanEvidenceBundleV1": 1,
            "SelectedPairedEvidenceV1": 1,
        }
    assert dict(before - calls) == removed
    assert not calls - before
    assert calls["GenerationTicket"] >= 1


@pytest.mark.parametrize("change", ["privacy", "source", "policy", "copied_bool", "naive_time"])
def test_original_error_order_retained(change: str) -> None:
    ticket, bundle, _ = paired_ready()
    if change == "privacy":
        ticket = ticket.model_copy(update={"privacy_revision": ticket.privacy_revision + 1})
    elif change == "source":
        source = ticket.sources[0].model_copy(update={"source_binding_digest": "f" * 64})
        ticket = ticket.model_copy(update={"sources": (source,)})
    elif change == "policy":
        ticket = ticket.model_copy(update={"policy_digest": "f" * 64})
    elif change == "copied_bool":
        ticket = ticket.model_copy(update={"expected_version": True})
    else:
        ticket = ticket.model_copy(update={"prepared_at": ticket.prepared_at.replace(tzinfo=None)})

    def old() -> None:
        t = GenerationTicket.model_validate(ticket)
        b = SelectedPairedEvidenceV1.model_validate(bundle)
        original_paired(b, t)

    with pytest.raises(ValueError) as before:
        old()
    with pytest.raises(ValueError) as after:
        paired_module._validate_paired_ticket_pair(bundle, ticket)
    assert type(after.value) is type(before.value)
    assert str(after.value) == str(before.value)


class StatefulZone(tzinfo):
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.failure: RuntimeError | None = None

    def tzname(self, dt: datetime | None) -> str:
        self.calls.append("name")
        return "Synthetic UTC"

    def utcoffset(self, dt: datetime | None) -> timedelta:
        self.calls.append("offset")
        if self.failure is not None:
            raise self.failure
        return timedelta(0)

    def dst(self, dt: datetime | None) -> timedelta:
        self.calls.append("dst")
        return timedelta(0)


@pytest.mark.parametrize("raise_suffix", [False, True])
def test_custom_timezone_original_suffix_trace_and_exception_identity(
    monkeypatch: pytest.MonkeyPatch, raise_suffix: bool
) -> None:
    ticket, bundle, _ = paired_ready()
    zone = StatefulZone()
    ticket = ticket.model_copy(update={"prepared_at": ticket.prepared_at.replace(tzinfo=zone)})
    events: list[str] = []
    sentinel = RuntimeError("synthetic original suffix error")
    original = SelectedPairedEvidenceV1.assert_ticket
    timezone_failure = False

    def suffix(self: SelectedPairedEvidenceV1, checked: GenerationTicket) -> None:
        events.append("suffix")
        if timezone_failure:
            zone.failure = sentinel
        elif raise_suffix:
            raise sentinel
        original(self, checked)

    monkeypatch.setattr(SelectedPairedEvidenceV1, "assert_ticket", suffix)

    def old() -> None:
        t = GenerationTicket.model_validate(ticket)
        b = SelectedPairedEvidenceV1.model_validate(bundle)
        b.assert_ticket(t)

    traces = []
    for operation in (old, lambda: paired_module._validate_paired_ticket_pair(bundle, ticket)):
        zone.calls.clear()
        events.clear()
        if raise_suffix:
            with pytest.raises(RuntimeError) as caught:
                operation()
            assert caught.value is sentinel
        else:
            operation()
        traces.append((tuple(zone.calls), tuple(events)))
    assert traces[0] == traces[1]
    assert traces[0][0] and traces[0][1] == ("suffix",)
    zone.calls.clear()
    assert not selected_module._inert_selected_values(ticket)
    assert zone.calls == []
    if raise_suffix:
        timezone_failure = True
        failures = []
        traces = []
        for operation in (old, lambda: paired_module._validate_paired_ticket_pair(bundle, ticket)):
            zone.failure = None
            zone.calls.clear()
            events.clear()
            with pytest.raises((RuntimeError, ValidationError)) as timezone_error:
                operation()
            failures.append(timezone_error.value)
            traces.append((tuple(zone.calls), tuple(events)))
        assert traces[0] == traces[1]
        assert traces[0][0][-1] == "offset"
        assert type(failures[0]) is type(failures[1])
        assert str(failures[0]) == str(failures[1])
        if failures[0] is sentinel:
            assert failures[1] is sentinel
        else:
            assert "synthetic original suffix error" in str(failures[0])


def test_scanner_bounds_unknown_shapes_and_builtin_timezones(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Hostile:
        def __getattribute__(self, name: str) -> Any:
            raise AssertionError("unexpected attribute callback")

    class DateSubtype(datetime):
        pass

    assert not selected_module._inert_selected_values(Hostile())
    assert not selected_module._inert_selected_values(DateSubtype(2026, 1, 1, tzinfo=UTC))
    assert not selected_module._inert_selected_values({"x": 1})
    assert not selected_module._inert_selected_values([1])
    for zone in (UTC, timezone(timedelta(hours=1)), ZoneInfo("America/New_York"), TzInfo(0)):
        assert selected_module._inert_selected_values(datetime(2026, 1, 1, tzinfo=zone))

    class Node(BaseModel):
        child: Any = None

    class ShadowNode(Node):
        @property
        def __dict__(self) -> dict[str, Any]:
            raise AssertionError("shadowed dictionary property invoked")

        @__dict__.setter
        def __dict__(self, value: dict[str, Any]) -> None:
            raise AssertionError("shadowed dictionary setter invoked")

    shadow = object.__new__(ShadowNode)
    BaseModel.__dict__["__dict__"].__set__(shadow, {"child": 1})
    assert selected_module._inert_selected_values(shadow)
    node = Node()
    node.__dict__["child"] = node
    assert not selected_module._inert_selected_values(node)
    monkeypatch.setattr(selected_module, "_SCALAR_SCAN_LIMIT", 2)
    assert not selected_module._inert_selected_values((1, 2, 3))


def test_nonnull_legacy_coverage_canonicalization_and_custom_fallback() -> None:
    class CoverageSubtype(ClosedDayCoverageV1):
        pass

    class WindowSubtype(MeasurementWindow):
        pass

    ticket, evidence = ready_bundle()
    data = commerce_data(ticket, evidence)
    progress = data["document"]
    window = progress.target_window
    coverage = ClosedDayCoverageV1(
        starts_on=window.start,
        ends_on_exclusive=window.end,
        starts_at=datetime.combine(window.start, datetime.min.time(), tzinfo=UTC),
        ends_at_exclusive=datetime.combine(window.end, datetime.min.time(), tzinfo=UTC),
        closed_day_count=(window.end - window.start).days,
        extent="full_window_as_of",
    )
    # Strict unavailable progress can retain coverage without claiming a measured amount.
    progress = GoalSalesProgressV1.model_validate(
        progress.model_copy(
            update={
                "coverage": coverage,
                "as_of": coverage.ends_at_exclusive,
                "status": "unavailable",
                "reasons": ("missing_history",),
            }
        )
    )
    custom = progress.model_copy(
        update={
            "coverage": CoverageSubtype.model_validate(coverage.model_dump(mode="python")),
            "target_window": WindowSubtype.model_validate(window.model_dump(mode="python")),
        }
    )
    assert not selected_module._inert_selected_values(custom)
    ref = dict(data["reference"])
    ref.update(
        observation_started_at=progress.as_of,
        observed_at=progress.as_of,
        expires_at=progress.as_of + timedelta(hours=1),
        reasons=progress.reasons,
    )
    ref["document_digest"] = fingerprint("goal-progress", progress.model_dump(mode="json"))
    ref["reporting_window"] = {
        "starts_at": coverage.starts_at,
        "ends_at_exclusive": coverage.ends_at_exclusive,
    }
    checked = CommerceEvidence.model_validate({"reference": ref, "document": custom})
    assert type(checked.document) is GoalSalesProgressV1
    assert type(checked.document.coverage) is ClosedDayCoverageV1
    assert type(checked.document.target_window) is MeasurementWindow
    assert selected_module._inert_selected_values(checked)
    assert checked.document.model_dump_json() == progress.model_dump_json()

    class AdversarialProgress(GoalSalesProgressV1):
        def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            # The legacy before-validator calls this original public serialization port.
            values = super().model_dump(*args, **kwargs)
            values["coverage"] = custom.coverage
            values["target_window"] = custom.target_window
            return values

    adversarial = AdversarialProgress.model_validate(progress.model_dump(mode="python"))
    retained = CommerceEvidence.model_validate({"reference": ref, "document": adversarial})
    assert type(retained.document) is GoalSalesProgressV1
    assert type(retained.document.coverage) is CoverageSubtype
    assert type(retained.document.target_window) is WindowSubtype
    assert not selected_module._inert_selected_values(retained)
    assert retained.document.model_dump_json() == progress.model_dump_json()
    assert custom.coverage is not None
    invalid = custom.model_copy(
        update={"coverage": custom.coverage.model_copy(update={"closed_day_count": True})}
    )
    with pytest.raises(ValidationError):
        CommerceEvidence.model_validate({"reference": ref, "document": invalid})


@pytest.mark.parametrize(
    "module,function,expected",
    [
        (
            "selected_plan_bundle",
            "_assert_selected_ticket_checked",
            "470715f0abebef9243bc5f39023eed41f5c7be509cbfa89d325815a99c196a9f",
        ),
        (
            "selected_paired_evidence",
            "_assert_paired_ticket_remaining",
            "15b6ccddefecbf92b35c8d18d16d257b531df17982facd789069ddc14fcdf6fb",
        ),
    ],
)
def test_invariant_ast_matches_original_prechange_body(
    module: str, function: str, expected: str
) -> None:
    tree = ast.parse(Path("app/planning_documents", module + ".py").read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == function)
    body = ast.dump(ast.Module(body=node.body, type_ignores=[]), include_attributes=False)
    assert hashlib.sha256(body.encode()).hexdigest() == expected


# Test-only frozen field/config inventory; never used by production dispatch.
SCHEMA_CLASSES = (
    "app.campaign_performance.capture_settings.CaptureSettingsV1",
    "app.campaign_performance.capture_settings.RequestedAttributionV1",
    "app.campaign_performance.presence_contracts.AttributionBasisV1",
    "app.campaign_performance.presence_contracts.CountCellV1",
    "app.campaign_performance.presence_contracts.Frozen",
    "app.campaign_performance.presence_contracts.IntegerCountCellV1",
    "app.campaign_performance.presence_contracts.MoneyCellV1",
    "app.campaign_performance.presence_contracts.ReportedMetricPresenceV1",
    "app.campaign_performance.presence_contracts.ReportingSemanticsV1",
    "app.campaign_performance.presence_contracts.SelectedEventV1",
    "app.campaign_performance.range_receipt_contracts.RangeReceiptV1",
    "app.campaign_performance.selected_contracts.AggregateDependencyV1",
    "app.campaign_performance.selected_contracts.CustomerEventSelectionV1",
    "app.campaign_performance.selected_contracts.ReportingScopeV1",
    "app.campaign_performance.selected_contracts.SelectedCampaignDayV1",
    "app.campaign_performance.selected_contracts.SelectedCaptureRequestV1",
    "app.campaign_performance.selected_contracts.SelectedCaptureV1",
    "app.commerce.reporting.MeasurementWindow",
    "app.goals.progress_contracts.ClosedDayCoverageV1",
    "app.goals.progress_contracts.Frozen",
    "app.goals.progress_contracts.GoalSalesProgressV1",
    "app.goals.schemas.GoalDefinition",
    "app.goals.schemas.StrictModel",
    "app.planning_catalog.contracts.CoverageV1",
    "app.planning_catalog.contracts.Frozen",
    "app.planning_catalog.contracts.GoogleSettingsV1",
    "app.planning_catalog.contracts.MetaSettingsV1",
    "app.planning_catalog.contracts.TargetCatalogV1",
    "app.planning_catalog.contracts.TargetV1",
    "app.planning_catalog.contracts.TikTokSettingsV1",
    "app.planning_catalog.metadata_contracts.MetadataCoverageV1",
    "app.planning_catalog.metadata_contracts.MetadataEntityV1",
    "app.planning_catalog.metadata_contracts.PlanningMetadataV1",
    "app.planning_catalog.metadata_contracts.PlanningTargetV2",
    "app.planning_catalog.metadata_contracts.ProviderReferenceV1",
    "app.planning_catalog.metadata_contracts.TargetCatalogV2",
    "app.planning_documents.catalog_evidence.CatalogEvidence",
    "app.planning_documents.common.Frozen",
    "app.planning_documents.common.NoAuthority",
    "app.planning_documents.context.AccountRef",
    "app.planning_documents.context.BudgetPeriod",
    "app.planning_documents.context.ConfirmedGoalRef",
    "app.planning_documents.context.CustomerAssumption",
    "app.planning_documents.context.EvidenceRef",
    "app.planning_documents.context.PlanInputRevision",
    "app.planning_documents.context.ReportingWindow",
    "app.planning_documents.context.TargetRef",
    "app.planning_documents.creative_basis.CreativeInputV1",
    "app.planning_documents.creative_basis.CustomerListPriceV1",
    "app.planning_documents.creative_basis.CustomerProductV1",
    "app.planning_documents.creative_basis.PlanningMediaSelectionV1",
    "app.planning_documents.google_budget_intents.GoogleDailyBudgetIntentV1",
    "app.planning_documents.google_budget_intents.ResolvedGoogleDailyBudgetIntentV1",
    "app.planning_documents.ports.CommerceEvidence",
    "app.planning_documents.ports.ContextEvidence",
    "app.planning_documents.ports.EvidenceGap",
    "app.planning_documents.ports.GenerationTicket",
    "app.planning_documents.ports.PlanningCompositionPolicy",
    "app.planning_documents.ports.ReportingGapPin",
    "app.planning_documents.selected_inputs.SelectedCaptureSelectorV1",
    "app.planning_documents.selected_observation_provenance.SelectedObservationProvenanceV1",
    "app.planning_documents.selected_paired_evidence.SelectedPairedEvidenceV1",
    "app.planning_documents.selected_paired_evidence.TrafficWindowEvidenceV1",
    "app.planning_documents.selected_paired_evidence.TrafficWindowGapV1",
    "app.planning_documents.selected_plan_bundle.SelectedPlanEvidenceBundleV1",
    "app.planning_documents.selected_plan_bundle.SelectedReportingGapV1",
    "app.planning_documents.selected_plan_bundle.SelectedWindowEvidenceV1",
    "app.planning_documents.selected_plan_contracts.SelectedCampaignBindingV1",
    "app.planning_documents.selected_plan_contracts.SelectedPlanPinV1",
    "app.planning_documents.selected_plan_evidence.SelectedPlanCaptureV1",
    "app.planning_documents.selected_plan_evidence.SelectedPlanWindowV1",
    "app.planning_documents.selected_plan_proof.SelectedHeadProofV1",
    "app.planning_documents.selected_plan_proof.SelectedRetainedAccountProofV1",
    "app.planning_documents.selected_plan_proof.SelectedRetainedProofV1",
    "app.planning_documents.selected_plan_summary.SelectedCountSummaryV1",
    "app.planning_documents.selected_plan_summary.SelectedMetricSummaryV1",
    "app.planning_documents.selected_plan_summary.SelectedMoneySummaryV1",
    "app.planning_documents.selected_plan_summary.SelectedPlanSummaryV1",
    "app.planning_documents.selected_traffic.RawRangeTrafficGraphV1",
    "app.planning_documents.selected_traffic.SelectedTrafficWindowV1",
    "app.planning_documents.selected_traffic.TrafficMetricSummaryV1",
    "app.planning_documents.selected_traffic_contracts.SelectedTrafficPinV1",
    "app.planning_documents.source_contracts.SourceFence",
)
SCHEMA_SHA256 = "39ff12333d36b8104f660b099e20d16f7337e49e53f775db59b3f03a2ed05b72"


def test_declared_field_and_revalidation_configuration_inventory() -> None:
    inventory = {}
    for full in SCHEMA_CLASSES:
        module, name = full.rsplit(".", 1)
        tree = ast.parse(Path(*module.split(".")).with_suffix(".py").read_text())
        node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name)
        inventory[full] = {
            "bases": [ast.unparse(x) for x in node.bases],
            "fields": [
                (n.target.id, ast.unparse(n.annotation))
                for n in node.body
                if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)
            ],
            "configuration": [
                ast.unparse(n.value)
                for n in node.body
                if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "model_config" for t in n.targets)
            ],
        }
    assert (
        hashlib.sha256(json.dumps(inventory, sort_keys=True).encode()).hexdigest() == SCHEMA_SHA256
    )
