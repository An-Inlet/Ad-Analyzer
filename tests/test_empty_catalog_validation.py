"""Pure retained document joins, not provider observation or runtime qualification."""

from datetime import timedelta
from typing import Any

import pytest
from app.goals.schemas import GoalDefinition
from app.planning_documents.actions import ManualAction
from app.planning_documents.catalog_evidence import CatalogEvidence
from app.planning_documents.common import fingerprint
from app.planning_documents.context import PlanInputRevision
from app.planning_documents.creative_production_contracts import (
    CreativeCompositionV1,
    CreativeProposalV1,
)
from app.planning_documents.documents import PlanVersion
from app.planning_documents.empty_catalog_validation import (
    assert_empty_catalog_bindings,
    validate_empty_catalog_proposals,
)
from app.planning_documents.selected_plan_proof import SelectedRetainedProofV1
from app.planning_documents.source_contracts import SourceFence

from tests.test_creative_plan_document import document_values
from tests.test_empty_catalog_contracts import empty_evidence, proposal


def empty_document_values() -> dict[str, Any]:
    values = document_values()
    raw = values["inputs"].model_dump(mode="python")
    raw["total_ceiling_micros"] = raw["goal"]["definition"]["budget_micros"] = 0
    definition = values["inputs"].goal.definition.model_copy(update={"budget_micros": 0})
    raw["goal"]["definition_digest"] = fingerprint(
        "goal-definition", definition.model_dump(mode="json")
    )
    inputs = PlanInputRevision.model_validate(raw)
    p = proposal()
    projected = p.model_dump(mode="python")
    reference = projected["empty_catalog_witness"]["catalog_evidence"]["reference"]
    reference["source_revision"] = reference["account"]["connection_version"]
    p = CreativeProposalV1.model_validate(projected)
    p = CreativeProposalV1.model_validate(
        p.model_copy(update={"action": p.action.model_copy(update={"priority": 2})})
    )
    witness = p.empty_catalog_witness
    assert witness is not None
    ref = witness.catalog_evidence.reference
    prerequisite = ManualAction.model_validate(
        p.action.model_copy(
            update={
                "key": witness.prerequisite_action_key,
                "kind": "investigate",
                "priority": 1,
                "prerequisites": (),
                "evidence_keys": (ref.key,),
            }
        )
    )
    evidence = tuple(
        ref
        if e.kind == "native_catalog"
        else e.model_copy(
            update={"document_digest": inputs.digest(), "source_binding_digest": inputs.digest()}
        )
        if e.kind == "customer_context"
        else e
        for e in values["evidence"]
    )
    assert ref.account is not None
    source = SourceFence(
        account=ref.account,
        source_binding_digest=ref.source_binding_digest,
        source_revision=ref.source_revision,
        privacy_revision=ref.privacy_revision,
    )
    proof = values["selected_reporting_proof"].model_dump(mode="python")
    proof["accounts"][0]["source_fence"] = source
    scenario = values["scenarios"][0].model_copy(
        update={"ceiling_micros": 0, "unallocated_micros": 0}
    )
    values.update(
        inputs=inputs,
        actions=(prerequisite, p.action),
        briefs=(p.brief,),
        evidence=evidence,
        selected_reporting_proof=SelectedRetainedProofV1.model_validate(proof),
        scenarios=(scenario,),
        creative_composition=CreativeCompositionV1(
            basis_digest=values["creative_composition"].basis_digest, proposals=(p,), limitations=()
        ),
    )
    return values


def test_retained_empty_document_roundtrip_and_later_catalog_independence() -> None:
    values = empty_document_values()
    doc = PlanVersion.model_validate(values)
    encoded, digest = doc.model_dump_json(), doc.digest()
    # A separately observed populated catalog is not consulted when parsing history.
    later = document_values()
    assert later["creative_composition"].proposals[0].target_basis == "existing_campaign"
    assert PlanVersion.model_validate_json(encoded).digest() == digest
    assert doc.creative_composition is not None
    witness = doc.creative_composition.proposals[0].empty_catalog_witness
    assert witness is not None
    assert_empty_catalog_bindings(doc.creative_composition.proposals, (witness.catalog_evidence,))


@pytest.mark.parametrize(
    "attack",
    [
        "missing_prerequisite",
        "duplicate_prerequisite",
        "wrong_kind",
        "source_digest",
        "source_revision",
        "source_privacy",
        "evidence_digest",
        "window",
        "positive_budget",
        "constraint",
        "capacity",
        "expiry",
    ],
)
def test_document_rejects_broken_retained_joins(attack: str) -> None:
    raw = PlanVersion.model_validate(empty_document_values()).model_dump(mode="python")
    if attack == "missing_prerequisite":
        raw["actions"] = raw["actions"][1:]
    elif attack == "duplicate_prerequisite":
        raw["actions"] = (raw["actions"][0], *raw["actions"])
    elif attack == "wrong_kind":
        raw["actions"][0]["kind"] = "retain"
    elif attack.startswith("source_"):
        fence = raw["selected_reporting_proof"]["accounts"][0]["source_fence"]
        field = {
            "source_digest": "source_binding_digest",
            "source_revision": "source_revision",
            "source_privacy": "privacy_revision",
        }[attack]
        fence[field] = 1 if attack == "source_privacy" else "f" * 64
    elif attack == "evidence_digest":
        raw["evidence"][0]["document_digest"] = "f" * 64
    elif attack == "window":
        raw["inputs"]["reporting_window"]["starts_at"] -= timedelta(hours=1)
    elif attack == "positive_budget":
        raw["inputs"]["total_ceiling_micros"] = 1
        raw["inputs"]["goal"]["definition"]["budget_micros"] = 1
        raw["inputs"]["goal"]["definition_digest"] = fingerprint(
            "goal-definition",
            GoalDefinition.model_validate(raw["inputs"]["goal"]["definition"]).model_dump(
                mode="json"
            ),
        )
        raw["scenarios"][0]["ceiling_micros"] = raw["scenarios"][0]["unallocated_micros"] = 1
    elif attack == "constraint":
        raw["inputs"]["constraints"] = ("Do not prepare creative",)
    elif attack == "capacity":
        raw["inputs"]["maximum_creative_assets"] = 0
    else:
        raw["valid_until"] += timedelta(seconds=1)
    with pytest.raises(ValueError):
        PlanVersion.model_validate(raw)


@pytest.mark.parametrize("attack", ["missing", "duplicate", "changed_reference", "numeric_copy"])
def test_actual_collection_binding_refuses_substitution(attack: str) -> None:
    p = proposal()
    catalogs: tuple[CatalogEvidence, ...]
    catalog = empty_evidence()
    if attack == "missing":
        catalogs = ()
    elif attack == "duplicate":
        catalogs = (catalog, catalog)
    elif attack == "changed_reference":
        catalogs = (
            catalog.model_copy(
                update={
                    "reference": catalog.reference.model_copy(update={"declared_scope": "changed"})
                }
            ),
        )
    else:
        ref = catalog.reference.model_copy(
            update={"observed_at": catalog.reference.observed_at.timestamp()}
        )
        catalogs = (catalog.model_copy(update={"reference": ref}),)
    with pytest.raises(ValueError):
        assert_empty_catalog_bindings((p,), catalogs)


def test_direct_validator_revalidates_unsafe_reference_instants() -> None:
    doc = PlanVersion.model_validate(empty_document_values())
    assert doc.creative_composition is not None and doc.selected_reporting_proof is not None
    ref = doc.evidence[0].model_copy(
        update={"observed_at": doc.evidence[0].observed_at.timestamp()}
    )
    with pytest.raises(ValueError):
        validate_empty_catalog_proposals(
            inputs=doc.inputs,
            proposals=doc.creative_composition.proposals,
            actions=doc.actions,
            evidence=(ref, *doc.evidence[1:]),
            sources=tuple(a.source_fence for a in doc.selected_reporting_proof.accounts),
            generated_at=doc.generated_at,
            valid_until=doc.valid_until,
            privacy_revision=0,
        )
