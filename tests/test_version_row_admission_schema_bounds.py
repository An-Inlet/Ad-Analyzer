"""Bounded resident snapshots; no SQL, authority or timing qualification."""

import ast
import hashlib
import json
from datetime import UTC, datetime, timedelta, timezone, tzinfo
from decimal import Decimal
from pathlib import Path
from typing import Any, get_args

import pytest
from app.planning_documents import version_row_admission as admission
from app.planning_documents.documents import PlanVersion
from pydantic import BaseModel

from tests.owner_review_v6_fixture import ready
from tests.test_owner_review_v6_pure import compose


def test_cumulative_byte_budget_and_exact_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(admission, "_MAX_BYTES", 96)
    scan = admission._Snapshot()
    assert scan.scalar("é" * 32) is not admission._UNSUPPORTED
    assert scan.bytes == 96
    assert scan.scalar(None) is admission._UNSUPPORTED
    assert admission._Snapshot().scalar("é" * 33) is admission._UNSUPPORTED


@pytest.mark.parametrize("limit", ["nodes", "depth"])
def test_node_and_depth_limits_fall_back(limit: str, monkeypatch: pytest.MonkeyPatch) -> None:
    value = (("bounded",),)
    annotation = tuple[tuple[str, ...], ...]
    assert admission._Snapshot().copy(value, annotation) is not admission._UNSUPPORTED
    monkeypatch.setattr(admission, "_MAX_NODES" if limit == "nodes" else "_MAX_DEPTH", 1)
    assert admission._Snapshot().copy(value, annotation) is admission._UNSUPPORTED


def test_document_budget_is_shared_with_prior_scalar_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = PlanVersion.model_validate_json(compose(ready()).model_dump_json())
    measured = admission._Snapshot()
    assert admission._snapshot_version(document, measured) is not None
    monkeypatch.setattr(admission, "_MAX_BYTES", measured.bytes)
    assert admission._snapshot_version(document) is not None
    shared = admission._Snapshot()
    assert shared.scalar("already counted row bytes") is not admission._UNSUPPORTED
    assert admission._snapshot_version(document, shared) is None


@pytest.mark.parametrize("value", ["NaN", "sNaN", "Infinity", "-Infinity"])
def test_nonfinite_decimal_falls_back(value: str) -> None:
    assert admission._Snapshot().scalar(Decimal(value)) is admission._UNSUPPORTED


def test_decimal_representation_and_pre_expansion_bound() -> None:
    scan = admission._Snapshot()
    assert scan.scalar(Decimal("1.00")) != scan.scalar(Decimal("1.0"))
    large = Decimal("1" * 10_000)
    assert Decimal.__sizeof__(large) > 4096
    assert admission._Snapshot().scalar(large) is admission._UNSUPPORTED


def test_timezone_name_and_datetime_final_charge_are_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    value = datetime(2026, 1, 1, tzinfo=timezone(timedelta(0), "x" * 512))
    monkeypatch.setattr(admission, "_MAX_BYTES", 256)
    assert admission._Snapshot().scalar(value) is admission._UNSUPPORTED
    monkeypatch.setattr(admission, "_MAX_BYTES", 64)
    assert admission._Snapshot().scalar(datetime(2026, 1, 1, tzinfo=UTC)) is admission._UNSUPPORTED


def test_custom_scalar_and_model_equality_callbacks_are_not_invoked() -> None:
    calls: list[str] = []

    class CustomZone(tzinfo):
        def utcoffset(self, dt: datetime | None) -> timedelta:
            calls.append("offset")
            raise AssertionError("Custom timezone called")

        def dst(self, dt: datetime | None) -> timedelta:
            calls.append("dst")
            raise AssertionError("Custom timezone called")

        def tzname(self, dt: datetime | None) -> str:
            calls.append("name")
            raise AssertionError("Custom timezone called")

    class CustomDateTime(datetime):
        def utcoffset(self) -> timedelta:
            calls.append("datetime")
            raise AssertionError("Custom datetime called")

    class CustomEquality(BaseModel):
        value: int

        def __eq__(self, other: Any) -> bool:
            calls.append("equality")
            raise AssertionError("Custom equality called")

    assert (
        admission._Snapshot().scalar(datetime(2026, 1, 1, tzinfo=CustomZone()))
        is admission._UNSUPPORTED
    )
    assert (
        admission._Snapshot().scalar(CustomDateTime(2026, 1, 1, tzinfo=UTC))
        is admission._UNSUPPORTED
    )
    assert (
        admission._Snapshot().copy(CustomEquality(value=1), CustomEquality)
        is admission._UNSUPPORTED
    )
    assert calls == []


def test_unknown_container_and_repeated_model_alias_fall_back() -> None:
    class Value(BaseModel):
        amount: int

    value = Value(amount=1)
    assert admission._Snapshot().copy((value,), tuple[Value, ...]) is not admission._UNSUPPORTED
    assert admission._Snapshot().copy((value, value), tuple[Value, ...]) is admission._UNSUPPORTED
    cyclic: list[Any] = []
    cyclic.append(cyclic)
    assert admission._Snapshot().copy(cyclic, list[Any]) is admission._UNSUPPORTED


# Reviewed source inventory: assertions deliberately require review on schema,
# config, intrinsic validators/serializers or their fixed helper changes. This
# is test-only and never becomes a production registry/cache.
_SCHEMA_MODELS = (
    "app.campaign_performance.presence_contracts.AttributionBasisV1",
    "app.campaign_performance.presence_contracts.Frozen",
    "app.campaign_performance.selected_contracts.AggregateDependencyV1",
    "app.campaign_performance.selected_contracts.ReportingScopeV1",
    "app.commerce.reporting.MeasurementWindow",
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
    "app.planning_documents.actions.Allocation",
    "app.planning_documents.actions.BudgetScenario",
    "app.planning_documents.actions.CreativeBrief",
    "app.planning_documents.actions.ManualAction",
    "app.planning_documents.actions.NativeBudget",
    "app.planning_documents.actions.UnavailableBudget",
    "app.planning_documents.catalog_evidence.CatalogEvidence",
    "app.planning_documents.common.Frozen",
    "app.planning_documents.common.NoAuthority",
    "app.planning_documents.context.AccountRef",
    "app.planning_documents.context.AccountTarget",
    "app.planning_documents.context.BudgetPeriod",
    "app.planning_documents.context.ConfirmedGoalRef",
    "app.planning_documents.context.CustomerAssumption",
    "app.planning_documents.context.CustomerScenarioIntent",
    "app.planning_documents.context.EvidenceRef",
    "app.planning_documents.context.FixedAllocation",
    "app.planning_documents.context.PlanInputRevision",
    "app.planning_documents.context.ReportingWindow",
    "app.planning_documents.context.TargetRef",
    "app.planning_documents.creative_basis.CreativeBasisV1",
    "app.planning_documents.creative_basis.CreativeInputV1",
    "app.planning_documents.creative_basis.CustomerListPriceV1",
    "app.planning_documents.creative_basis.CustomerProductV1",
    "app.planning_documents.creative_basis.OwnedPlanningImageV1",
    "app.planning_documents.creative_basis.PlanningMediaSelectionV1",
    "app.planning_documents.creative_production_contracts.CreativeCompositionV1",
    "app.planning_documents.creative_production_contracts.CreativeProductionV1",
    "app.planning_documents.creative_production_contracts.CreativeProposalV1",
    "app.planning_documents.creative_production_contracts.CreativeShotV1",
    "app.planning_documents.creative_retained_proof.CreativeImageCommitmentV1",
    "app.planning_documents.creative_retained_proof.CreativeRetainedProofV1",
    "app.planning_documents.documents.PlanVersion",
    "app.planning_documents.empty_catalog_contracts.EmptyDeclaredCatalogWitnessV1",
    "app.planning_documents.fields.LandingPageValue",
    "app.planning_documents.fields.ProposedField",
    "app.planning_documents.fields.StatusValue",
    "app.planning_documents.fields.TargetingValue",
    "app.planning_documents.fields.UnavailableField",
    "app.planning_documents.google_budget_intents.GoogleDailyBudgetIntentV1",
    "app.planning_documents.google_budget_intents.ResolvedGoogleDailyBudgetIntentV1",
    "app.planning_documents.google_budget_owner_contracts.GoogleDailyBudgetOwnerWitnessV1",
    "app.planning_documents.google_budget_owner_review_contracts.GoogleBudgetOwnerReviewProofV1",
    "app.planning_documents.google_budget_owner_review_contracts.GoogleBudgetOwnerReviewV1",
    "app.planning_documents.selected_inputs.SelectedCaptureSelectorV1",
    "app.planning_documents.selected_observation_provenance.SelectedObservationProvenanceV1",
    "app.planning_documents.selected_plan_contracts.SelectedPlanPinV1",
    "app.planning_documents.selected_plan_proof.SelectedHeadProofV1",
    "app.planning_documents.selected_plan_proof.SelectedRetainedAccountProofV1",
    "app.planning_documents.selected_plan_proof.SelectedRetainedProofV1",
    "app.planning_documents.selected_traffic_contracts.SelectedTrafficPinV1",
    "app.planning_documents.source_contracts.SourceFence",
)

_HELPER_MODULES = (
    "app.collectors.account_diagnostic_contracts",
    "app.planning_documents.creative_plan_document",
    "app.planning_documents.creative_inputs",
    "app.planning_documents.empty_catalog_validation",
    "app.planning_documents.google_budget_generation_guard",
    "app.planning_documents.google_budget_input_bindings",
    "app.planning_documents.owner_review_plan_document",
    "app.planning_documents.owner_review_policy",
    "app.publication.contracts",
)

_INVENTORY_SHA256 = "a5fb280bf5b193f2bad4c9cf936a4f8dc722b372d0c3a2ce6d7ba4830ba079c7"


def test_declared_schema_and_config_inventory_is_complete() -> None:
    pending: list[type[BaseModel]] = [PlanVersion]
    found: set[type[BaseModel]] = set()
    while pending:
        model = pending.pop()
        if model in found:
            continue
        found.add(model)
        pending.extend(
            base
            for base in model.__bases__
            if issubclass(base, BaseModel) and base is not BaseModel
        )
        annotations = [field.annotation for field in model.model_fields.values()]
        while annotations:
            annotation = annotations.pop()
            if isinstance(annotation, type) and issubclass(annotation, BaseModel):
                pending.append(annotation)
            else:
                annotations.extend(get_args(annotation))
    assert (
        tuple(sorted(f"{model.__module__}.{model.__name__}" for model in found)) == _SCHEMA_MODELS
    )
    legacy = {
        "app.commerce.reporting.MeasurementWindow",
        "app.goals.schemas.StrictModel",
        "app.goals.schemas.GoalDefinition",
    }
    for model in found:
        assert model.model_config.get("extra") == "forbid"
        name = f"{model.__module__}.{model.__name__}"
        if name in legacy:
            assert model.model_config.get("frozen") is None
            assert model.model_config.get("revalidate_instances") is None
        else:
            assert model.model_config.get("frozen") is True
            assert model.model_config.get("revalidate_instances") == "always"


def test_fixed_validator_serializer_and_schema_source_inventory() -> None:
    root = Path(__file__).resolve().parents[1]
    parts: dict[str, str] = {}
    for module in sorted({name.rsplit(".", 1)[0] for name in _SCHEMA_MODELS}):
        tree = ast.parse(root.joinpath(*module.split(".")).with_suffix(".py").read_text())
        wanted = {
            name.rsplit(".", 1)[1] for name in _SCHEMA_MODELS if name.rsplit(".", 1)[0] == module
        }
        nodes: list[ast.stmt] = [
            node
            for node in tree.body
            if isinstance(node, (ast.Import, ast.ImportFrom, ast.Assign, ast.AnnAssign))
            or isinstance(node, ast.ClassDef)
            and node.name in wanted
            or isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        parts[module] = ast.dump(ast.Module(body=nodes, type_ignores=[]), include_attributes=False)
    for module in _HELPER_MODULES:
        tree = ast.parse(root.joinpath(*module.split(".")).with_suffix(".py").read_text())
        parts[module] = ast.dump(tree, include_attributes=False)
    encoded = json.dumps(parts, sort_keys=True, separators=(",", ":")).encode()
    assert hashlib.sha256(encoded).hexdigest() == _INVENTORY_SHA256
