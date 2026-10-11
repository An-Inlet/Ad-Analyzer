"""Immutable proof bindings only; current/historical SQL validators are separate."""

from typing import Any

import pytest
from app.planning_documents.context import PlanInputRevision
from app.planning_documents.documents import PlanVersion
from app.planning_documents.ports import SourceFence as LegacySourceFence
from app.planning_documents.selected_inputs import (
    SELECTED_GENERATOR_VERSION,
    SELECTED_POLICY_VERSION,
    SelectedCaptureSelectorV1,
)
from app.planning_documents.selected_plan_contracts import SelectedPlanPinV1
from app.planning_documents.selected_plan_evidence import SelectedPlanPinV1 as LegacyPin
from app.planning_documents.selected_plan_proof import (
    SelectedHeadProofV1,
    SelectedRetainedAccountProofV1,
    SelectedRetainedProofV1,
)
from app.planning_documents.selected_traffic_contracts import SelectedTrafficPinV1
from app.planning_documents.source_contracts import SourceFence

from tests.test_planning_document_contracts import packet
from tests.test_selected_plan_evidence import graph


def chosen() -> SelectedRetainedAccountProofV1:
    pin = graph().pin()
    return SelectedRetainedAccountProofV1(
        source_fence=pin.source_fence,
        legacy_reporting_digest="2" * 64,
        selection_head=SelectedHeadProofV1(
            selection_id=pin.selection_id, selection_digest=pin.selection_digest, invalidated=False
        ),
        capture_pin=pin,
    )


def none_document() -> PlanVersion:
    original = PlanVersion.model_validate(packet())
    inputs = PlanInputRevision.model_validate(
        original.inputs.model_copy(update={"selected_reporting": ()})
    )
    account = inputs.accounts[0]
    proof = SelectedRetainedProofV1(
        accounts=(
            SelectedRetainedAccountProofV1(
                source_fence=SourceFence(
                    account=account,
                    source_binding_digest="1" * 64,
                    source_revision=account.connection_version,
                    privacy_revision=original.evidence[0].privacy_revision,
                ),
                legacy_reporting_digest="2" * 64,
                selection_head=None,
                capture_pin=None,
            ),
        ),
    )
    return PlanVersion.model_validate(
        original.model_copy(
            update={
                "inputs": inputs,
                "policy_version": SELECTED_POLICY_VERSION,
                "generator_version": SELECTED_GENERATOR_VERSION,
                "selected_reporting_proof": proof,
            }
        )
    )


def test_old_type_exports_keep_class_identity() -> None:
    assert SourceFence is LegacySourceFence
    assert SelectedPlanPinV1 is LegacyPin


def test_explicit_none_v4_document_proof_roundtrip_and_registered_witness() -> None:
    from app.planning_documents.policy_capabilities import reporting_capability

    doc = none_document()
    assert PlanVersion.model_validate_json(doc.model_dump_json()) == doc
    assert doc.selected_reporting_proof is not None
    assert (
        reporting_capability(doc.policy_version, doc.generator_version).local_witness_kind
        == "local_reporting_v3"
    )
    assert PlanVersion.model_validate(packet()).model_dump().get("selected_reporting_proof") is None
    assert "selected_reporting_proof" not in PlanVersion.model_validate(packet()).model_dump()


@pytest.mark.parametrize("version", [1, 2, 3])
def test_legacy_pair_rejects_nonnull_proof_even_without_selectors(version: int) -> None:
    doc = PlanVersion.model_validate(packet())
    changed = doc.model_copy(
        update={
            "policy_version": f"inlet.descriptive-review.v{version}",
            "generator_version": f"inlet.descriptive-planning.v{version}",
            "selected_reporting_proof": none_document().selected_reporting_proof,
        }
    )
    with pytest.raises(ValueError):
        changed.digest()


def test_v4_requires_proof_and_explicit_input_intent() -> None:
    doc = none_document()
    with pytest.raises(ValueError):
        PlanVersion.model_validate(doc.model_copy(update={"selected_reporting_proof": None}))
    with pytest.raises(ValueError):
        PlanVersion.model_validate(
            doc.model_copy(
                update={"inputs": doc.inputs.model_copy(update={"selected_reporting": None})}
            )
        )


@pytest.mark.parametrize(
    "field,value",
    [("selection_head", None), ("legacy_reporting_digest", "x"), ("capture_pin", "x")],
)
def test_unsafe_account_proof_hash_revalidates(field: str, value: Any) -> None:
    with pytest.raises(ValueError):
        chosen().model_copy(update={field: value}).state_digest()


@pytest.mark.parametrize("invalidated", [True, 1, "false"])
def test_chosen_capture_requires_strict_active_original_head(invalidated: Any) -> None:
    account = chosen()
    assert account.selection_head
    with pytest.raises(ValueError):
        account.model_copy(
            update={
                "selection_head": account.selection_head.model_copy(
                    update={"invalidated": invalidated}
                )
            }
        ).state_digest()


def test_exact_input_account_selector_and_privacy_coverage() -> None:
    account = chosen()
    proof = SelectedRetainedProofV1(accounts=(account,))
    pin = account.capture_pin
    assert pin
    base = PlanVersion.model_validate(packet()).inputs
    inputs = PlanInputRevision.model_validate(
        base.model_copy(
            update={
                "accounts": (pin.account,),
                "selected_reporting": (
                    SelectedCaptureSelectorV1(
                        account_id=pin.account.account_id, capture_id=pin.capture_id
                    ),
                ),
            }
        )
    )
    proof.assert_inputs(inputs, pin.source_fence.privacy_revision)
    with pytest.raises(ValueError):
        proof.assert_inputs(inputs, pin.source_fence.privacy_revision + 1)
    with pytest.raises(ValueError):
        proof.assert_inputs(inputs.model_copy(update={"selected_reporting": ()}), 0)
    with pytest.raises(ValueError):
        SelectedRetainedProofV1(accounts=(account, account))
    other = account.model_copy(update={"capture_pin": None, "selection_head": None})
    assert other.state_digest() != account.state_digest()
    with pytest.raises(ValueError):
        SelectedRetainedProofV1(accounts=(other,)).assert_inputs(inputs, 0)


def traffic() -> SelectedTrafficPinV1:
    account = chosen()
    pin = account.capture_pin
    assert pin
    return SelectedTrafficPinV1(
        source_fence=pin.source_fence,
        aggregate=pin.aggregate,
        range_request_id="f" * 32,
        range_receipt_digest="1" * 64,
        presence_header_digest="2" * 64,
        presence_fact_digest="3" * 64,
        campaign_map_digest=pin.campaign_map_digest,
    )


def test_absent_traffic_preserves_prior_nested_canonical_proof_bytes() -> None:
    from app.planning_documents.common import fingerprint

    account = chosen()
    old_payload = dict(
        source_fence=account.source_fence.model_dump(mode="json"),
        legacy_reporting_digest=account.legacy_reporting_digest,
        selection_head=account.selection_head.model_dump(mode="json")
        if account.selection_head
        else None,
        capture_pin=account.capture_pin.model_dump(mode="json") if account.capture_pin else None,
    )
    assert account.model_dump(mode="json") == old_payload
    assert account.state_digest() == fingerprint("inlet.local-reporting-state.v3", old_payload)
    assert "traffic_pin" not in SelectedRetainedProofV1(accounts=(account,)).model_dump_json()
    assert "traffic_pin" not in none_document().model_dump_json()
    assert (
        "traffic_pin" not in none_document().model_dump()["selected_reporting_proof"]["accounts"][0]
    )


def test_optional_traffic_binds_exact_selected_acquisition_and_changes_commitment() -> None:
    original = chosen()
    account = SelectedRetainedAccountProofV1.model_validate(
        original.model_copy(update={"traffic_pin": traffic()})
    )
    assert account.state_digest() != original.state_digest()
    assert SelectedRetainedAccountProofV1.model_validate_json(account.model_dump_json()) == account
    with pytest.raises(ValueError):
        account.model_copy(update={"capture_pin": None}).state_digest()


@pytest.mark.parametrize("field", ["aggregate", "source_fence", "campaign_map_digest"])
def test_traffic_cannot_mix_another_selected_acquisition(field: str) -> None:
    pin = traffic()
    if field == "campaign_map_digest":
        value: Any = "f" * 64
    elif field == "aggregate":
        value = pin.aggregate.model_copy(update={"completion_id": "f" * 32})
    else:
        value = pin.source_fence.model_copy(update={"source_binding_digest": "f" * 64})
    with pytest.raises(ValueError):
        chosen().model_copy(
            update={"traffic_pin": pin.model_copy(update={field: value})}
        ).state_digest()
