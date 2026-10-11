"""Historical linked sources are not fabricated full-account source authority."""

from typing import Any

import pytest
from app.planning_documents.context import PlanInputRevision
from app.planning_documents.google_budget_input_bindings import (
    validate_google_daily_budget_input_bindings,
)
from app.planning_documents.google_budget_input_bindings import (
    validate_retained_google_daily_budget_input_bindings as retained,
)

from tests.test_google_budget_input_bindings import setup


def historical() -> dict[str, Any]:
    values = setup()
    values.pop("privacy_revision")
    return values


def test_retained_original_witness_and_unselected_account() -> None:
    values = historical()
    assert len(retained(**values)) == 1
    inputs = values["inputs"]
    other = inputs.accounts[0].model_copy(update={"account_id": inputs.accounts[0].account_id + 1})
    raw = inputs.model_dump(mode="python")
    raw["accounts"] += (other,)
    values["inputs"] = PlanInputRevision.model_validate(raw)
    assert len(retained(**values)) == 1
    with pytest.raises(ValueError, match="full source"):
        validate_google_daily_budget_input_bindings(
            **values, privacy_revision=values["sources"][0].privacy_revision
        )


@pytest.mark.parametrize(
    "case",
    [
        "missing",
        "duplicate",
        "foreign",
        "generation",
        "privacy",
        "missing-catalog",
        "numeric",
        "raw-flag",
        "wrong-resolved",
    ],
)
def test_retained_original_corruption(case: str) -> None:
    values = historical()
    source = values["sources"][0]
    if case == "missing":
        values["sources"] = ()
    elif case == "duplicate":
        values["sources"] *= 2
    elif case == "foreign":
        values["sources"] = (
            source.model_copy(
                update={
                    "account": source.account.model_copy(
                        update={"workspace_id": source.account.workspace_id + 1}
                    )
                }
            ),
        )
    elif case == "generation":
        values["sources"] = (source.model_copy(update={"source_revision": "wrong"}),)
    elif case == "privacy":
        values["sources"] = (
            source.model_copy(update={"privacy_revision": source.privacy_revision + 1}),
        )
    elif case == "missing-catalog":
        values["catalogs"] = ()
    elif case == "numeric":
        values["inputs"] = values["inputs"].model_copy(update={"created_at": True})
    elif case == "raw-flag":
        catalog = values["catalogs"][0]
        native = catalog.catalog.native_observation.model_copy(update={"atomic_snapshot": 0})
        values["catalogs"] = (
            catalog.model_copy(
                update={
                    "catalog": catalog.catalog.model_copy(update={"native_observation": native})
                }
            ),
        )
    else:
        values["intents"] = (
            values["intents"][0].model_copy(update={"source_binding_digest": "0" * 64}),
        )
    with pytest.raises(ValueError):
        retained(**values)


def test_empty_no_link_history_has_no_invented_epoch() -> None:
    values = historical()
    inputs = values["inputs"]
    raw = inputs.model_dump(mode="python")
    raw["scenario_intents"] = ()
    values.update(inputs=PlanInputRevision.model_validate(raw), intents=(), catalogs=(), sources=())
    assert retained(**values) == ()
    values["inputs"] = inputs
    with pytest.raises(ValueError, match="no-receipt"):
        retained(**values)


def test_two_linked_accounts_require_same_real_privacy_epoch() -> None:
    from app.planning_catalog.metadata_contracts import (
        PlanningMetadataV1,
        canonical_key,
        selection_key,
    )
    from app.planning_documents.catalog_evidence import CatalogEvidence
    from app.publication.contracts import fingerprint

    values = historical()
    first = values["catalogs"][0]
    source = values["sources"][0]
    other = source.account.model_copy(update={"account_id": source.account.account_id + 1})
    raw = first.model_dump(mode="python")
    raw["reference"].update(
        account=other, privacy_revision=source.privacy_revision + 1, key="second-catalog"
    )
    composite = raw["catalog"]
    composite["native_observation"]["account_id"] = other.account_id
    composite["metadata_observation"]["account_id"] = other.account_id
    metadata = PlanningMetadataV1.model_validate(composite["metadata_observation"])
    composite["composite_digest"] = fingerprint(
        "inlet.planning-catalog-composite.v1",
        dict(
            native_inventory_digest=composite["native_observation"]["inventory_digest"],
            metadata_digest=metadata.digest(),
        ),
    )
    for target, entity in zip(composite["targets"], metadata.entities, strict=True):
        key = canonical_key(metadata, entity)
        target["canonical_entity_key"] = key
        target["selection_key"] = selection_key(
            key, metadata.source_binding_digest, composite["composite_digest"]
        )
    raw["reference"]["document_digest"] = composite["composite_digest"]
    second = CatalogEvidence.model_validate(raw)
    values["catalogs"] += (second,)
    values["sources"] += (
        source.model_copy(
            update={"account": other, "privacy_revision": source.privacy_revision + 1}
        ),
    )
    inputs = values["inputs"].model_dump(mode="python")
    inputs["accounts"] += (other,)
    values["inputs"] = PlanInputRevision.model_validate(inputs)
    with pytest.raises(ValueError, match="privacy must be unanimous"):
        retained(**values)
