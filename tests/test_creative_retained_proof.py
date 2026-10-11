"""Pure retained commitments do not replace collection or final SQL authority."""

import subprocess
import sys
from datetime import timedelta
from typing import Any

import pytest
from app.planning_documents.creative_basis import CreativeInputV1
from app.planning_documents.creative_retained_proof import (
    CreativeRetainedProofV1,
    creative_proof_from_collection,
)

from tests.test_creative_image_collection import envelope, saved


def test_ordered_roundtrip_preserves_basis_without_private_identity() -> None:
    collection, ticket = envelope()
    proof = creative_proof_from_collection(collection, ticket)
    assert proof.basis == collection.basis
    assert tuple(x.media_id for x in proof.images) == tuple(x.media_id for x in proof.basis.images)
    restored = CreativeRetainedProofV1.model_validate_json(proof.model_dump_json())
    assert restored == proof and restored.digest() == proof.digest()
    assert restored.source_binding_digest() == proof.source_binding_digest()
    assert proof.source_binding_digest() != proof.digest()
    for private in ("created_by", "ticket_digest", "session_digest"):
        assert private not in proof.model_dump_json()
    assert not proof.advertising_writes_enabled and proof.spending_authority == "none"
    proof.assert_inputs(ticket.inputs, ticket.privacy_revision)


def test_empty_selection_retains_explicit_proof() -> None:
    collection, ticket = envelope()
    requested = CreativeInputV1()
    ticket = saved(ticket, requested)
    collection = type(collection).model_validate(
        collection.model_copy(
            update={
                "basis": collection.basis.model_copy(update={"requested": requested, "images": ()}),
                "rows": (),
                "ticket_digest": ticket.digest(),
            }
        )
    )
    proof = creative_proof_from_collection(collection, ticket)
    assert proof.images == () and proof.basis.requested == requested
    proof.assert_inputs(ticket.inputs, ticket.privacy_revision)
    with pytest.raises(ValueError, match="exact saved"):
        proof.assert_inputs(
            ticket.inputs.model_copy(update={"creative": None}), ticket.privacy_revision
        )


@pytest.mark.parametrize("field", ["created_by", "created_at", "observed_at"])
def test_complete_identity_and_observation_commitments(field: str) -> None:
    collection, ticket = envelope()
    before = creative_proof_from_collection(collection, ticket)
    row = collection.rows[0]
    if field == "created_by":
        row = row.model_copy(update={"created_by": "f" * 32})
    else:
        old = getattr(row.witness, field)
        row = row.model_copy(
            update={"witness": row.witness.model_copy(update={field: old - timedelta(seconds=1)})}
        )
    changed = type(collection).model_validate(
        collection.model_copy(
            update={
                "rows": (row, *collection.rows[1:]),
                "basis": collection.basis.model_copy(
                    update={"images": (row.witness, *collection.basis.images[1:])}
                ),
            }
        )
    )
    after = creative_proof_from_collection(changed, ticket)
    assert after.digest() != before.digest()
    assert (after.source_binding_digest() == before.source_binding_digest()) == (
        field == "observed_at"
    )
    assert (after.images == before.images) == (field == "observed_at")


@pytest.mark.parametrize("attack", ["missing", "extra", "reverse", "digest", "schema", "authority"])
def test_copied_proof_revalidates_before_both_digests(attack: str) -> None:
    collection, ticket = envelope()
    proof = creative_proof_from_collection(collection, ticket)
    changes: dict[str, Any]
    if attack == "missing":
        changes = {"images": proof.images[:1]}
    elif attack == "extra":
        changes = {"images": (*proof.images, proof.images[0])}
    elif attack == "reverse":
        changes = {"images": tuple(reversed(proof.images))}
    elif attack == "digest":
        changes = {
            "images": (
                proof.images[0].model_copy(update={"row_identity_digest": True}),
                *proof.images[1:],
            )
        }
    elif attack == "schema":
        changes = {"schema_version": "unknown"}
    else:
        changes = {"advertising_writes_enabled": 1}
    poisoned = proof.model_copy(update=changes)
    for operation in (poisoned.digest, poisoned.source_binding_digest):
        with pytest.raises(ValueError):
            operation()


@pytest.mark.parametrize("privacy", [True, "0", -1, 99])
def test_privacy_binding_is_strict(privacy: Any) -> None:
    collection, ticket = envelope()
    proof = creative_proof_from_collection(collection, ticket)
    with pytest.raises(ValueError):
        proof.assert_inputs(ticket.inputs, privacy)


def test_factory_rejects_wrong_ticket_and_scope() -> None:
    collection, ticket = envelope()
    with pytest.raises(ValueError):
        creative_proof_from_collection(collection, ticket.model_copy(update={"actor_id": "f" * 32}))
    proof = creative_proof_from_collection(collection, ticket)
    wrong_basis = proof.basis.model_copy(update={"workspace_id": proof.basis.workspace_id + 1})
    with pytest.raises(ValueError):
        proof.model_copy(update={"basis": wrong_basis}).assert_inputs(
            ticket.inputs, ticket.privacy_revision
        )
    with pytest.raises(ValueError):
        CreativeRetainedProofV1.model_validate(
            {**proof.model_dump(), "created_by": ticket.actor_id}
        )


@pytest.mark.parametrize("first", ["documents", "creative_retained_proof"])
def test_document_leaf_import_orders(first: str) -> None:
    second = "creative_retained_proof" if first == "documents" else "documents"
    subprocess.run(
        [
            sys.executable,
            "-c",
            f"import app.planning_documents.{first}; import app.planning_documents.{second}",
        ],
        check=True,
        capture_output=True,
        timeout=20,
    )


@pytest.mark.parametrize("field", ["requested", "currency", "workspace"])
def test_valid_but_foreign_basis_scope_cannot_bind(field: str) -> None:
    collection, ticket = envelope()
    proof = creative_proof_from_collection(collection, ticket)
    data = proof.model_dump(mode="python")
    if field == "requested":
        data["basis"]["requested"]["product"]["name"] = "Different product"
    elif field == "currency":
        data["basis"]["goal_currency"] = "EUR"
        data["basis"]["requested"]["product"]["list_price"]["currency"] = "EUR"
    else:
        data["basis"]["workspace_id"] += 1
        for image in data["basis"]["images"]:
            image["workspace_id"] += 1
    changed = CreativeRetainedProofV1.model_validate(data)
    with pytest.raises(ValueError, match="exact saved"):
        changed.assert_inputs(ticket.inputs, ticket.privacy_revision)
