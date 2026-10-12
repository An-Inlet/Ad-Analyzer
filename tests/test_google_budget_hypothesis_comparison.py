"""Synthetic normalized proofs only; no acquired provider evidence or runtime admission."""

from datetime import timedelta
from typing import Any

import pytest
from app.planning_catalog.metadata_contracts import PlanningMetadataV1, selection_key
from app.planning_documents import google_budget_hypothesis_comparison as boundary
from app.planning_documents.catalog_evidence import CatalogEvidence
from app.planning_documents.documents import PlanVersion
from app.planning_documents.events import VersionBinding
from app.planning_documents.google_budget_owner_contracts import GoogleDailyBudgetOwnerWitnessV1
from app.publication.contracts import fingerprint

from tests.owner_review_v6_fixture import ready
from tests.test_google_budget_owner_contracts import derive, evidence
from tests.test_owner_review_v6_pure import compose


@pytest.fixture(scope="module")
def document() -> PlanVersion:
    return compose(ready())


def fresh(
    document: PlanVersion, amount: int = 1, change: str | None = None, removed: bool = False
) -> GoogleDailyBudgetOwnerWitnessV1:
    catalog = evidence(change=change, removed=removed).model_dump(mode="python")
    graph = catalog["catalog"]
    native, metadata = graph["native_observation"], graph["metadata_observation"]
    now = document.generated_at + timedelta(seconds=1)
    for row in (native, metadata):
        row.update(
            observation_started_at=now, observed_at=now, expires_at=now + timedelta(minutes=5)
        )
    for row in native["targets"]:
        row["settings"]["budget_amount_micros"] = amount
    # Explicit synthetic commitment; does not authenticate a raw native inventory.
    native["inventory_digest"] = "d" * 64
    metadata["native_inventory_digest"] = native["inventory_digest"]
    composite = fingerprint(
        "inlet.planning-catalog-composite.v1",
        dict(
            native_inventory_digest=native["inventory_digest"],
            metadata_digest=PlanningMetadataV1.model_validate(metadata).digest(),
        ),
    )
    graph.update(composite_digest=composite, expires_at=native["expires_at"])
    for row in graph["targets"]:
        row["selection_key"] = selection_key(
            row["canonical_entity_key"], native["source_binding_digest"], composite
        )
    catalog["reference"].update(
        document_digest=composite,
        observation_started_at=now,
        observed_at=now,
        expires_at=native["expires_at"],
    )
    return derive(CatalogEvidence.model_validate(catalog))


def packet(document: PlanVersion, witness: GoogleDailyBudgetOwnerWitnessV1 | None) -> Any:
    assert document.google_budget_owner_review is not None
    review = document.google_budget_owner_review.reviews[0]
    action = next(a for a in document.actions if a.key == review.action_key)
    return boundary.GoogleBudgetHypothesisComparisonV1(
        document=document,
        binding=VersionBinding(
            workspace_id=document.inputs.workspace_id,
            plan_id=document.inputs.plan_id,
            version=document.version,
            document_digest=document.digest(),
            action_key=action.key,
            action_digest=action.digest(),
        ),
        compared_at=document.generated_at + timedelta(seconds=2),
        privacy_revision=review.witness.catalog_evidence.reference.privacy_revision,
        source_binding_digest=review.intent.source_binding_digest,
        integrity="clear",
        fresh=witness,
    )


@pytest.mark.parametrize(
    "amount,status",
    [(1, "matches_hypothesis"), (0, "differs_from_hypothesis"), (2, "differs_from_hypothesis")],
)
def test_exact_integer_hypothesis_only(document: PlanVersion, amount: int, status: str) -> None:
    result = packet(document, fresh(document, amount))
    assert result.status == status and result.unavailable_reason is None
    assert result.application == "unavailable"
    assert result.provider_edit_validity == result.period_spending_compatibility == "not_assessed"
    assert result.causality == "not_assessed"
    assert result.advertising_writes_enabled is False and result.spending_authority == "none"
    assert result.fresh.atomic_snapshot is False
    encoded = result.model_dump_json()
    restored = boundary.GoogleBudgetHypothesisComparisonV1.model_validate_json(encoded)
    assert restored == result and restored.status == status and restored.digest() == result.digest()
    assert restored.document == document and restored.fresh == result.fresh
    assert result.document.google_budget_owner_review.reviews[0].intent.requested_amount_micros == 1
    assert all(
        not a.proposed_fields for a in document.actions if a.key == result.binding.action_key
    )


def test_missing_is_not_zero_and_zero_hypothesis_is_supported(document: PlanVersion) -> None:
    missing = packet(document, None)
    assert missing.status == "unavailable" and missing.unavailable_reason
    zero = compose(ready(zero=True))
    assert packet(zero, fresh(zero, 0)).status == "matches_hypothesis"


@pytest.mark.parametrize("change", ["name", "status"])
def test_snapshot_keys_names_and_eligible_status_are_not_identity(
    document: PlanVersion, change: str
) -> None:
    result = packet(document, fresh(document, change=change))
    assert result.status == "matches_hypothesis"


@pytest.mark.parametrize("case", ["member", "removed"])
def test_changed_topology_refuses(document: PlanVersion, case: str) -> None:
    witness = fresh(
        document, change="member" if case == "member" else None, removed=case == "removed"
    )
    with pytest.raises(ValueError, match="topology"):
        packet(document, witness)


@pytest.mark.parametrize(
    "case",
    [
        "expired",
        "future",
        "predates",
        "privacy",
        "source",
        "integrity",
        "binding",
        "bool",
        "amount",
        "account",
        "naive",
    ],
)
def test_invalid_copies_cannot_compare_serialize_or_hash(document: PlanVersion, case: str) -> None:
    good = packet(document, fresh(document))
    changes: dict[str, Any] = {}
    if case == "expired":
        changes["compared_at"] = good.fresh.catalog_evidence.reference.expires_at
    elif case == "future":
        changes["compared_at"] = document.generated_at
    elif case == "predates":
        changes["fresh"] = derive(evidence())
    elif case == "privacy":
        changes["privacy_revision"] = good.privacy_revision + 1
    elif case == "source":
        changes["source_binding_digest"] = "0" * 64
    elif case == "integrity":
        changes["integrity"] = "invalidated"
    elif case == "binding":
        changes["binding"] = good.binding.model_copy(update={"document_digest": "0" * 64})
    elif case == "bool":
        changes["privacy_revision"] = True
    elif case == "amount":
        changes["fresh"] = good.fresh.model_copy(update={"current_amount_micros": 99})
    elif case == "account":
        representative = good.fresh.representative
        changes["fresh"] = good.fresh.model_copy(
            update={
                "representative": representative.model_copy(
                    update={
                        "account": representative.account.model_copy(
                            update={"connection_version": "other"}
                        )
                    }
                )
            }
        )
    else:
        changes["compared_at"] = good.compared_at.replace(tzinfo=None)
    bad = good.model_copy(update=changes)
    for operation in (lambda: bad.status, bad.model_dump, bad.model_dump_json, bad.digest):
        with pytest.raises(ValueError):
            operation()


def test_bound_and_no_claim_injection(
    document: PlanVersion, monkeypatch: pytest.MonkeyPatch
) -> None:
    good = packet(document, fresh(document))
    data = good.model_dump()
    data["status"] = "implemented"
    with pytest.raises(ValueError):
        boundary.GoogleBudgetHypothesisComparisonV1.model_validate(data)
    monkeypatch.setattr(boundary, "MAX_PACKET_BYTES", 4096)
    with pytest.raises(ValueError, match="byte bound"):
        good.model_dump_json()
