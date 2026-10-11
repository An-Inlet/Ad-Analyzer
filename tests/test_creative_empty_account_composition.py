"""Pure scoped preparation only; actual SQL/API provenance is qualified separately."""

from typing import Any

import pytest
from app.goals.schemas import GoalDefinition
from app.planning_documents.actions import ManualAction
from app.planning_documents.common import fingerprint
from app.planning_documents.context import AccountTarget, PlanInputRevision
from app.planning_documents.creative_basis import CreativeBasisV1
from app.planning_documents.creative_composition import compose_creative_proposals
from app.planning_documents.ports import CatalogEvidence

from tests.test_creative_composition import ready, references
from tests.test_empty_catalog_contracts import empty_evidence, proposal


def budget(inputs: PlanInputRevision, amount: int) -> PlanInputRevision:
    data = inputs.model_dump(mode="python")
    data["total_ceiling_micros"] = amount
    data["goal"]["definition"]["budget_micros"] = amount
    definition = GoalDefinition.model_validate(data["goal"]["definition"])
    data["goal"]["definition_digest"] = fingerprint(
        "goal-definition", definition.model_dump(mode="json")
    )
    return PlanInputRevision.model_validate(data)


def prepared() -> tuple[PlanInputRevision, CatalogEvidence, CreativeBasisV1, ManualAction]:
    inputs, _, basis = ready()
    inputs = budget(inputs, 0)
    catalog = empty_evidence()
    account = catalog.reference.account
    assert account is not None
    data = inputs.model_dump(mode="python")
    data.update(
        accounts=(account,),
        workspace_id=account.workspace_id,
        reporting_window=catalog.reference.reporting_window,
    )
    data["goal"]["workspace_id"] = account.workspace_id
    inputs = PlanInputRevision.model_validate(data)
    raw = basis.model_dump(mode="python")
    raw.update(
        workspace_id=account.workspace_id, privacy_revision=catalog.reference.privacy_revision
    )
    for image in raw["images"]:
        image.update(
            workspace_id=account.workspace_id, privacy_revision=catalog.reference.privacy_revision
        )
    basis = CreativeBasisV1.model_validate(raw)
    source = proposal().action.model_dump(mode="python")
    source.update(
        key=f"review:account_{account.account_id}",
        kind="investigate",
        target=AccountTarget(account=account),
        prerequisites=(),
        evidence_keys=(catalog.reference.key,),
    )
    return inputs, catalog, basis, ManualAction.model_validate(source)


def run(inputs: Any, catalog: Any, basis: Any, prerequisites: Any) -> Any:
    return compose_creative_proposals(
        inputs,
        (catalog,),
        basis,
        references(inputs, basis),
        first_priority=2,
        account_prerequisites=prerequisites,
    )


def test_exact_empty_account_preparation_retains_original_witness() -> None:
    inputs, catalog, basis, prerequisite = prepared()
    result = run(inputs, catalog, basis, (prerequisite,))
    assert len(result.proposals) == 1
    value = result.proposals[0]
    assert value.target_basis == "observed_empty_account"
    assert value.empty_catalog_witness is not None
    assert (
        value.empty_catalog_witness.catalog_evidence.model_dump_json() == catalog.model_dump_json()
    )
    assert value.empty_catalog_witness.prerequisite_action_key == prerequisite.key
    assert value.action.target == prerequisite.target == value.brief.target
    assert value.action.prerequisites == (prerequisite.key,)
    assert value.action.native_budget is None and value.action.proposed_fields == ()
    assert value.production.source_images == basis.requested.media_selections
    assert value.production.selected_image_id == basis.images[0].media_id
    assert value.production.deliverable_status == "production_required"
    assert value.production.visual_assessment == "not_assessed"
    assert value.production.storyboard == ()
    text = " ".join(value.action.manual_steps)
    assert "declared query" in text and "Missing history is not zero conversions" in text
    assert "Do not buy distribution, launch or activate" in text
    assert "does not cover or authorize labor or production costs" in text
    assert value.brief.hooks == ("Meet Reusable travel mug.",)
    assert "no delivery or sales effect is predicted" in value.action.expected_effect


@pytest.mark.parametrize(
    "case",
    [
        "positive-budget",
        "capacity-zero",
        "capacity-missing",
        "constraints",
        "product",
        "image",
        "prerequisite",
        "wrong-key",
        "wrong-target",
        "wrong-kind",
        "wrong-reference",
    ],
)
def test_recognized_ineligible_input_defers(case: str) -> None:
    inputs, catalog, basis, prerequisite = prepared()
    prerequisites: tuple[ManualAction, ...] = (prerequisite,)
    updates: dict[str, Any] = {}
    if case == "positive-budget":
        inputs = budget(inputs, 1)
    elif case == "capacity-zero":
        updates["maximum_creative_assets"] = 0
    elif case == "capacity-missing":
        updates["maximum_creative_assets"] = None
    elif case == "constraints":
        updates["constraints"] = ("Confirm restrictions",)
    elif case in {"product", "image"}:
        raw = basis.model_dump(mode="python")
        if case == "product":
            raw["requested"]["product"] = None
        else:
            raw["requested"]["media_selections"] = ()
            raw["images"] = ()
        basis = CreativeBasisV1.model_validate(raw)
    elif case == "prerequisite":
        prerequisites = ()
    else:
        changes: dict[str, dict[str, Any]] = {
            "wrong-key": dict(key="review:other"),
            "wrong-target": dict(
                target=prerequisite.target.model_copy(
                    update=dict(
                        account=prerequisite.target.account.model_copy(update=dict(account_id=999))
                    )
                )
            ),
            "wrong-kind": dict(kind="creative_review"),
            "wrong-reference": dict(evidence_keys=("other:catalog",)),
        }
        change = changes[case]
        prerequisites = (ManualAction.model_validate(prerequisite.model_copy(update=change)),)
    inputs = PlanInputRevision.model_validate(inputs.model_copy(update=updates))
    assert run(inputs, catalog, basis, prerequisites).proposals == ()


def test_duplicate_prerequisite_is_not_silently_selected() -> None:
    inputs, catalog, basis, prerequisite = prepared()
    with pytest.raises(ValueError, match="duplicate"):
        run(inputs, catalog, basis, (prerequisite, prerequisite))


def test_nonempty_excluded_catalog_does_not_become_empty_witness() -> None:
    from app.planning_documents.composer import targets

    inputs, catalogs, basis = ready()
    inputs = budget(inputs, 0)
    excluded = tuple(t.canonical_entity_key for t in targets(catalogs[0]))
    inputs = PlanInputRevision.model_validate(
        inputs.model_copy(update=dict(excluded_entity_keys=excluded))
    )
    assert (
        compose_creative_proposals(
            inputs, catalogs, basis, references(inputs, basis), first_priority=1
        ).proposals
        == ()
    )


def test_final_actual_catalog_binding_failure_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.planning_documents import empty_catalog_validation

    inputs, catalog, basis, prerequisite = prepared()

    def fail(*args: Any) -> None:
        raise ValueError("unexpected binding failure")

    monkeypatch.setattr(empty_catalog_validation, "assert_empty_catalog_bindings", fail)
    with pytest.raises(ValueError, match="unexpected binding failure"):
        run(inputs, catalog, basis, (prerequisite,))


def test_copied_corrupt_catalog_is_not_an_absence_gap() -> None:
    inputs, catalog, basis, prerequisite = prepared()
    broken = catalog.model_copy(
        update=dict(reference=catalog.reference.model_copy(update=dict(document_digest="0" * 64)))
    )
    with pytest.raises(ValueError):
        run(inputs, broken, basis, (prerequisite,))


def test_witness_construction_errors_are_not_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.planning_documents import creative_composition

    inputs, catalog, basis, prerequisite = prepared()

    def fail(**kwargs: Any) -> Any:
        raise ValueError("unexpected witness failure")

    monkeypatch.setattr(creative_composition, "EmptyDeclaredCatalogWitnessV1", fail)
    with pytest.raises(ValueError, match="unexpected witness failure"):
        run(inputs, catalog, basis, (prerequisite,))
