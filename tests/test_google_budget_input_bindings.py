"""Pure original input joins, not current SQL/selector authorization."""

from datetime import timedelta
from typing import Any

import pytest
from app.planning_documents.context import PlanInputRevision
from app.planning_documents.google_budget_input_bindings import (
    _targets,
)
from app.planning_documents.google_budget_input_bindings import (
    validate_google_daily_budget_input_bindings as validate,
)
from app.planning_documents.google_budget_owner_contracts import resolve_google_daily_budget_intent
from app.planning_documents.source_contracts import SourceFence

from tests.test_creative_composition import ready
from tests.test_creative_empty_account_composition import budget
from tests.test_google_budget_owner_contracts import derive, evidence, intent


def setup(*, zero: bool = False) -> dict[str, Any]:
    catalog = evidence()
    owner = derive(catalog)
    inputs, _, _ = ready("google")
    inputs = budget(inputs, 0 if zero else inputs.total_ceiling_micros)
    raw = inputs.model_dump(mode="python")
    raw.update(
        accounts=(owner.representative.account,),
        reporting_window=catalog.reference.reporting_window,
        created_at=catalog.reference.observed_at + timedelta(seconds=1),
        scenario_intents=(
            dict(
                key="alternative",
                title="One owner",
                allocations=(dict(target=owner.representative, amount_micros=0 if zero else 1),),
                unallocated_micros=inputs.total_ceiling_micros - (0 if zero else 1),
            ),
        ),
    )
    inputs = PlanInputRevision.model_validate(raw)
    resolved = resolve_google_daily_budget_intent(
        intent(owner, requested_amount_micros=0 if zero else 1), owner
    )
    source = SourceFence(
        account=owner.representative.account,
        source_revision=catalog.reference.source_revision,
        source_binding_digest=catalog.reference.source_binding_digest,
        privacy_revision=catalog.reference.privacy_revision,
    )
    return dict(
        inputs=inputs,
        intents=(resolved,),
        catalogs=(catalog,),
        sources=(source,),
        privacy_revision=source.privacy_revision,
    )


def test_exact_original_witness_without_wall_clock_ttl() -> None:
    values = setup()
    result = validate(**values)
    assert len(result) == 1
    assert result[0].model_dump_json() == derive(values["catalogs"][0]).model_dump_json()
    # Pure original October fixture timestamps need no current clock/session injection.
    assert validate(**setup(zero=True))[0].current_amount_micros > 0


@pytest.mark.parametrize(
    "case",
    [
        "source-missing",
        "source-duplicate",
        "source-revision",
        "source-privacy",
        "privacy-bool",
        "catalog-missing",
        "catalog-duplicate",
        "catalog-privacy",
        "resolved-representative",
        "resolved-source",
        "resolved-amount",
        "duplicate-intent",
        "scenario-missing",
        "constraint",
        "positive-zero",
        "excluded-unresolved",
        "excluded-member",
        "before-observation",
        "at-expiry",
        "numeric-created",
        "reporting-window",
    ],
)
def test_binding_refuses_invalid_original_graph(case: str) -> None:
    values = setup(zero=case == "positive-zero")
    inputs, catalog, resolved, source = (
        values["inputs"],
        values["catalogs"][0],
        values["intents"][0],
        values["sources"][0],
    )
    if case == "source-missing":
        values["sources"] = ()
    elif case == "source-duplicate":
        values["sources"] = (source, source)
    elif case == "source-revision":
        values["sources"] = (source.model_copy(update=dict(source_revision="wrong")),)
    elif case == "source-privacy":
        values["sources"] = (
            source.model_copy(update=dict(privacy_revision=source.privacy_revision + 1)),
        )
    elif case == "privacy-bool":
        values["privacy_revision"] = True
    elif case == "catalog-missing":
        values["catalogs"] = ()
    elif case == "catalog-duplicate":
        values["catalogs"] = (catalog, catalog)
    elif case == "catalog-privacy":
        values["catalogs"] = (
            catalog.model_copy(
                update=dict(
                    reference=catalog.reference.model_copy(
                        update=dict(privacy_revision=source.privacy_revision + 1)
                    )
                )
            ),
        )
    elif case == "resolved-representative":
        values["intents"] = (
            resolved.model_copy(update=dict(representative_canonical_key="0" * 64)),
        )
    elif case == "resolved-source":
        values["intents"] = (resolved.model_copy(update=dict(source_binding_digest="0" * 64)),)
    elif case == "resolved-amount":
        values["intents"] = (
            resolved.model_copy(
                update=dict(observed_amount_micros=resolved.observed_amount_micros + 1)
            ),
        )
    elif case == "duplicate-intent":
        values["intents"] = (resolved, resolved)
    elif case == "scenario-missing":
        values["intents"] = (resolved.model_copy(update=dict(scenario_key="missing")),)
    elif case == "constraint":
        values["inputs"] = inputs.model_copy(update=dict(constraints=("Resolve this",)))
    elif case == "positive-zero":
        values["intents"] = (resolved.model_copy(update=dict(requested_amount_micros=1)),)
    elif case.startswith("excluded"):
        values["inputs"] = inputs.model_copy(
            update=dict(
                excluded_entity_keys=(
                    "0" * 64
                    if case == "excluded-unresolved"
                    else derive(catalog).affected_campaigns[-1].canonical_entity_key,
                )
            )
        )
    elif case == "before-observation":
        values["inputs"] = inputs.model_copy(
            update=dict(created_at=catalog.reference.observed_at - timedelta(microseconds=1))
        )
    elif case == "at-expiry":
        values["inputs"] = inputs.model_copy(update=dict(created_at=catalog.reference.expires_at))
    elif case == "numeric-created":
        values["inputs"] = inputs.model_copy(update=dict(created_at=1770000000))
    elif case == "reporting-window":
        values["inputs"] = inputs.model_copy(
            update=dict(
                reporting_window=inputs.reporting_window.model_copy(
                    update=dict(starts_at=inputs.reporting_window.starts_at - timedelta(hours=1))
                )
            )
        )
    with pytest.raises(ValueError):
        validate(**values)


def test_empty_intents_still_require_exact_full_sources_and_bounds() -> None:
    values = setup()
    values["intents"] = ()
    assert validate(**values) == ()
    values["sources"] = ()
    with pytest.raises(ValueError):
        validate(**values)
    values = setup()
    values["intents"] = ()
    values["catalogs"] = values["catalogs"] * 21
    with pytest.raises(ValueError):
        validate(**values)


def graph(*, second_owner: bool = False, removed_child: bool = False) -> Any:
    """Strict projected graph; no acquisition claim."""
    import copy

    from app.planning_catalog.metadata_contracts import (
        PlanningMetadataV1,
        canonical_key,
        selection_key,
        settings_key,
    )
    from app.planning_documents.catalog_evidence import CatalogEvidence
    from app.publication.contracts import fingerprint

    catalog = evidence(removed=removed_child)
    raw = catalog.model_dump(mode="python")
    comp = raw["catalog"]
    native, metadata = comp["native_observation"], comp["metadata_observation"]
    if second_owner:
        for ident in ("3", "4"):
            row = copy.deepcopy(metadata["entities"][0])
            row["reference"]["entity_id"] = ident
            metadata["entities"] += (row,)
            setting = copy.deepcopy(native["targets"][0])
            setting["selection_key"] = settings_key(native["source_binding_digest"], row_model(row))
            setting["budget_owner_key"] = "f" * 64
            native["targets"] += (setting,)
    else:
        row = copy.deepcopy(metadata["entities"][0])
        row.update(kind="adgroup", name="Child")
        row["reference"].update(entity_id="10", parent_campaign_id="9" if removed_child else "1")
        metadata["entities"] += (row,)
    for coverage in native["coverage"]:
        coverage["observed_count"] = sum(t["kind"] == coverage["kind"] for t in native["targets"])
    for coverage in metadata["coverage"]:
        coverage["count"] = sum(t["kind"] == coverage["kind"] for t in metadata["entities"])
    md = PlanningMetadataV1.model_validate(metadata)
    comp["composite_digest"] = fingerprint(
        "inlet.planning-catalog-composite.v1",
        dict(native_inventory_digest=native["inventory_digest"], metadata_digest=md.digest()),
    )
    lookup = {t["selection_key"]: t for t in native["targets"]}
    comp["targets"] = []
    for entity in md.entities:
        canonical = canonical_key(md, entity)
        skey = settings_key(native["source_binding_digest"], entity)
        setting = lookup.get(skey)
        comp["targets"].append(
            dict(
                canonical_entity_key=canonical,
                selection_key=selection_key(
                    canonical, native["source_binding_digest"], comp["composite_digest"]
                ),
                entity=entity,
                native_settings_key=skey if setting else None,
                budget_owner_key=setting["budget_owner_key"] if setting else None,
            )
        )
    raw["reference"]["document_digest"] = comp["composite_digest"]
    return CatalogEvidence.model_validate(raw)


def row_model(row: Any) -> Any:
    from app.planning_catalog.metadata_contracts import MetadataEntityV1

    return MetadataEntityV1.model_validate(row)


def with_catalog(values: dict[str, Any], catalog: Any) -> dict[str, Any]:
    owner = derive(catalog)
    inputs = values["inputs"]
    raw = inputs.model_dump(mode="python")
    raw["scenario_intents"][0]["allocations"][0]["target"] = owner.representative
    values.update(
        inputs=PlanInputRevision.model_validate(raw),
        catalogs=(catalog,),
        intents=(
            resolve_google_daily_budget_intent(intent(owner, requested_amount_micros=1), owner),
        ),
    )
    return values


@pytest.mark.parametrize("removed", [False, True])
@pytest.mark.parametrize("mode", ["excluded", "allocation"])
def test_child_owner_none_cannot_hide_parent_pool(removed: bool, mode: str) -> None:
    values = with_catalog(setup(), graph(removed_child=removed))
    inputs = values["inputs"]
    child = next(t for t in _targets(values["catalogs"][0]) if t.kind == "adgroup")
    assert child.budget_owner_key is None
    data = inputs.model_dump(mode="python")
    if mode == "excluded":
        data["excluded_entity_keys"] = (child.canonical_entity_key,)
    else:
        data["scenario_intents"][0]["allocations"] += (dict(target=child, amount_micros=1),)
        data["scenario_intents"][0]["unallocated_micros"] -= 1
    values["inputs"] = PlanInputRevision.model_validate(data)
    with pytest.raises(ValueError, match="child"):
        validate(**values)


def test_two_independent_shared_owners_in_one_account() -> None:
    from app.planning_documents.google_budget_owner_contracts import (
        derive_google_daily_budget_owner,
    )

    catalog = graph(second_owner=True)
    values = with_catalog(setup(), catalog)
    second = derive_google_daily_budget_owner(catalog, "f" * 64)
    raw = values["inputs"].model_dump(mode="python")
    raw["scenario_intents"][0]["allocations"] += (
        dict(target=second.representative, amount_micros=1),
    )
    raw["scenario_intents"][0]["unallocated_micros"] -= 1
    values["inputs"] = PlanInputRevision.model_validate(raw)
    values["intents"] += (
        resolve_google_daily_budget_intent(intent(second, requested_amount_micros=1), second),
    )
    result = validate(**values)
    assert len(result) == 2 and result[0].owner_key != result[1].owner_key


@pytest.mark.parametrize("empty", [False, True])
@pytest.mark.parametrize(
    "field,value",
    [("atomic_snapshot", 0), ("advertising_writes_enabled", 0), ("platform", b"google_ads")],
)
def test_original_copied_catalog_primitives_rejected(empty: bool, field: str, value: Any) -> None:
    values = setup()
    catalog = values["catalogs"][0]
    native = catalog.catalog.native_observation.model_copy(update={field: value})
    values["catalogs"] = (
        catalog.model_copy(
            update={"catalog": catalog.catalog.model_copy(update={"native_observation": native})}
        ),
    )
    if empty:
        values["intents"] = ()
    with pytest.raises(ValueError):
        validate(**values)


@pytest.mark.parametrize(
    "field", ["display_name", "provider_reference", "account", "canonical_entity_key"]
)
def test_allocation_requires_entire_original_target(field: str) -> None:
    values = setup()
    inputs = values["inputs"]
    scenario = inputs.scenario_intents[0]
    allocation = scenario.allocations[0]
    target = allocation.target
    changed = {
        "display_name": "Alias",
        "provider_reference": target.provider_reference.model_copy(
            update={"advertiser_id": "9999999999"}
        ),
        "account": target.account.model_copy(
            update={"workspace_id": target.account.workspace_id + 1}
        ),
        "canonical_entity_key": "0" * 64,
    }[field]
    altered = target.model_copy(update={field: changed})
    values["inputs"] = inputs.model_copy(
        update={
            "scenario_intents": (
                scenario.model_copy(
                    update={"allocations": (allocation.model_copy(update={"target": altered}),)}
                ),
            )
        }
    )
    with pytest.raises(ValueError):
        validate(**values)


def test_equivalent_offset_admission_and_copied_numeric_window() -> None:
    from datetime import timezone

    values = setup()
    inputs = values["inputs"]
    values["inputs"] = inputs.model_copy(
        update={"created_at": inputs.created_at.astimezone(timezone(timedelta(hours=-4)))}
    )
    assert len(validate(**values)) == 1
    values["inputs"] = inputs.model_copy(
        update={"reporting_window": inputs.reporting_window.model_copy(update={"starts_at": True})}
    )
    with pytest.raises(ValueError):
        validate(**values)
