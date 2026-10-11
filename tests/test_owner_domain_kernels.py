"""Model-specific checked derivations; public validation and bytes remain exact."""

import hashlib
import json
from typing import Any

import pytest
from app.planning_documents import google_budget_owner_contracts as owners
from app.planning_documents import google_budget_owner_review_contracts as reviews
from app.planning_documents.google_budget_owner_review import (
    compose_google_budget_owner_reviews as compose,
)
from pydantic import SerializerFunctionWrapHandler, model_serializer, model_validator

from tests.test_google_budget_owner_contracts import derive, evidence, intent
from tests.test_google_budget_owner_review import ready

BASELINE = {
    "complete": {
        "json_sha256": "91b3bd6310d99719738c0e0a1173785c8dafe2893c3fb668ff9509410847eedb",
        "digest": "5516a0dbe8a09cec15099f3bf27d208433c27eb19503e3637fc5b459cc445a89",
    },
    "zero": {
        "json_sha256": "b49f85905d408c230052487b399687ac24194f583ab8c88676ae489f7864dcde",
        "digest": "3b15367d12b1f3ae6123cf7a43b1335810e6b0a8b28a8b91aa1a8df9b8ff1d27",
    },
    "empty": {
        "json_sha256": "fbbbdd99a2f6d2efa289134e0a417e0f6a4a0ce800ebb5174d11f6318110eab1",
        "digest": "0497e453c4ef73600ca9dcb33fed90244caa5639cb1b7aa5a9cb7b38f01ddff1",
    },
    "witness": {
        "json_sha256": "ee80fa6af9740e3f14208d740d5c6068572287b976ef4f557bc6d5d04c24571b",
        "digest": "da1585c13ea1c2b5b504c2b585fd4771228a51aa26cce818019fe0da31934fbd",
        "facts": "15505cb9f57e3873048ede4b90d5967c502fbd10c58a229b2a3e212a2f0dced4",
    },
    "removed": {
        "json_sha256": "082c23e100744ac015faf62db6a7b9a6c43c79366dfe1815adbbf1de945187cf",
        "digest": "6d47b8c7fd9ad98b72bba4b539c466170d5e31ddff8258c717948de174a87834",
        "facts": "927befff85094a8a5a7cf04fe78d4a446be493afd3fb242d09c7cf72c47ae7d5",
    },
}


@pytest.mark.parametrize(
    "name,zero,empty", [("complete", False, False), ("zero", True, False), ("empty", False, True)]
)
def test_prechange_proof_bytes(name: str, zero: bool, empty: bool) -> None:
    _, proof = compose(**ready(zero=zero, empty=empty), first_priority=4)
    assert (
        hashlib.sha256(proof.model_dump_json().encode()).hexdigest()
        == BASELINE[name]["json_sha256"]
    )
    assert proof.digest() == BASELINE[name]["digest"]


@pytest.mark.parametrize("removed", [False, True])
def test_prechange_witness_and_facts_bytes(removed: bool) -> None:
    witness = derive(evidence(removed=removed))
    expected = BASELINE["removed" if removed else "witness"]
    assert hashlib.sha256(witness.model_dump_json().encode()).hexdigest() == expected["json_sha256"]
    assert witness.digest() == expected["digest"]
    assert owners.owner_facts_digest(witness) == expected["facts"]


def test_checked_resolver_keeps_one_validation_and_fresh_derivation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    witness = derive(evidence())
    request = intent(witness)
    original = owners._parts
    calls = []

    def parts(*args: Any) -> Any:
        calls.append(1)
        return original(*args)

    monkeypatch.setattr(owners, "_parts", parts)
    owners.resolve_google_daily_budget_intent(request, witness)
    assert len(calls) == 2  # One strict witness validation, one facts projection.
    owners.resolve_google_daily_budget_intent(request, witness)
    assert len(calls) == 4
    with pytest.raises(ValueError):
        owners.resolve_google_daily_budget_intent(
            request, witness.model_copy(update={"reference_count": True})
        )


@pytest.mark.parametrize(
    "field,value",
    [("advertising_writes_enabled", 0), ("current_amount_micros", True), ("owner_key", b"a" * 64)],
)
def test_public_witness_entries_reject_unsafe_copies(field: str, value: Any) -> None:
    witness = derive(evidence()).model_copy(update={field: value})
    for operation in (
        witness.digest,
        lambda: owners.owner_facts_digest(witness),
        lambda: owners.GoogleDailyBudgetOwnerWitnessV1.model_validate(witness),
    ):
        with pytest.raises(ValueError):
            operation()


def test_proof_complete_checked_payload_and_public_options() -> None:
    _, proof = compose(**ready(), first_priority=4)
    review = proof.reviews[0]
    assert reviews._owner_review_payload_checked(review) == review.model_dump(mode="json")
    assert proof.model_dump(include={"input_digest"}) == {"input_digest": proof.input_digest}
    assert (
        json.loads(proof.model_dump_json(exclude={"reviews"}))["input_digest"] == proof.input_digest
    )
    copied = proof.model_copy(
        update={"reviews": (review.model_copy(update={"application": "available"}),)}
    )
    for operation in (copied.digest, copied.model_dump, copied.model_dump_json):
        with pytest.raises(ValueError):
            operation()


class ExtendedReview(reviews.GoogleBudgetOwnerReviewV1):
    extra_text: str = "kept Unicode café"

    @model_serializer(mode="wrap")
    def custom(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        value: dict[str, Any] = handler(self)
        value["custom"] = "preserved"
        return value


class RejectingReview(reviews.GoogleBudgetOwnerReviewV1):
    @model_validator(mode="after")
    def reject(self) -> "RejectingReview":
        raise ValueError("subclass validator preserved")


def test_subclass_and_inventory_use_original_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    _, proof = compose(**ready(), first_priority=4)
    extended = ExtendedReview(**proof.reviews[0].model_dump(mode="python"))
    assert not reviews._review_checked_eligible(extended)
    assert extended.model_dump()["custom"] == "preserved"
    assert extended.model_dump()["extra_text"] == "kept Unicode café"
    with pytest.raises(ValueError, match="subclass validator preserved"):
        RejectingReview(**proof.reviews[0].model_dump(mode="python"))
    review = proof.reviews[0]
    monkeypatch.setattr(reviews, "_REVIEW_FIELDS", frozenset())
    assert not reviews._review_checked_eligible(review)
    assert (
        reviews.GoogleBudgetOwnerReviewProofV1.model_validate(proof).model_dump_json()
        == proof.model_dump_json()
    )


class ExtendedWitness(owners.GoogleDailyBudgetOwnerWitnessV1):
    extra_text: str = "witness café"

    @model_serializer(mode="wrap")
    def custom(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        value: dict[str, Any] = handler(self)
        value["custom"] = "witness kept"
        return value


class ExtendedProof(reviews.GoogleBudgetOwnerReviewProofV1):
    extra_text: str = "proof café"


def test_witness_and_proof_subclass_digest_and_options() -> None:
    from app.planning_documents.common import fingerprint

    witness = ExtendedWitness(**derive(evidence()).model_dump(mode="python"))
    assert not owners._checked_witness_eligible(witness)
    assert witness.digest() == fingerprint(witness.schema_version, witness.model_dump(mode="json"))
    assert witness.model_dump(include={"extra_text"}) == {
        "extra_text": "witness café",
        "custom": "witness kept",
    }
    _, proof = compose(**ready(), first_priority=4)
    extended = ExtendedProof(**proof.model_dump(mode="python"))
    assert extended.model_dump(mode="python", include={"extra_text"}) == {
        "extra_text": "proof café"
    }
    assert json.loads(extended.model_dump_json(exclude={"reviews"}))["extra_text"] == "proof café"


def test_exact_utf8_proof_size_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    _, proof = compose(**ready(), first_priority=4)
    size = len(
        json.dumps(
            proof.model_dump(mode="json"),
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    monkeypatch.setattr(reviews, "MAX_DOCUMENT_BYTES", size)
    assert reviews.GoogleBudgetOwnerReviewProofV1.model_validate(proof) == proof
    monkeypatch.setattr(reviews, "MAX_DOCUMENT_BYTES", size - 1)
    with pytest.raises(ValueError, match="byte bound"):
        reviews.GoogleBudgetOwnerReviewProofV1.model_validate(proof)


class ProofWithExtendedReview(reviews.GoogleBudgetOwnerReviewProofV1):
    reviews: tuple[ExtendedReview, ...]


def test_proof_subtype_child_uses_original_full_size_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, original = compose(**ready(), first_priority=4)
    child = ExtendedReview(**original.reviews[0].model_dump(mode="python"))
    proof = ProofWithExtendedReview(input_digest=original.input_digest, reviews=(child,))
    assert type(proof.reviews[0]) is ExtendedReview
    data = proof.model_dump(mode="json")
    assert data["reviews"][0]["extra_text"] == "kept Unicode café"
    assert data["reviews"][0]["custom"] == "preserved"
    size = len(
        json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()
    )
    monkeypatch.setattr(reviews, "MAX_DOCUMENT_BYTES", size)
    ProofWithExtendedReview.model_validate(proof)
    monkeypatch.setattr(reviews, "MAX_DOCUMENT_BYTES", size - 1)
    with pytest.raises(ValueError, match="byte bound"):
        ProofWithExtendedReview.model_validate(proof)


def test_nested_catalog_subtype_disables_checked_path() -> None:
    from app.planning_documents.catalog_evidence import CatalogEvidence

    class CatalogSubtype(CatalogEvidence):
        extra_text: str = "retained"

    witness = derive(evidence())
    child = CatalogSubtype(**witness.catalog_evidence.model_dump(mode="python"))
    copied = witness.model_copy(update={"catalog_evidence": child})
    assert not owners._checked_witness_eligible(copied)


@pytest.mark.parametrize("level", ["review", "proof"])
@pytest.mark.parametrize("operation", ["validate", "digest", "dump", "json"])
def test_deep_invalid_copy_refused_by_public_boundaries(level: str, operation: str) -> None:
    _, proof = compose(**ready(), first_priority=4)
    review = proof.reviews[0]
    witness = review.witness.model_copy(update={"current_amount_micros": True})
    bad_review = review.model_copy(update={"witness": witness})
    bad = bad_review if level == "review" else proof.model_copy(update={"reviews": (bad_review,)})
    with pytest.raises(ValueError):
        if operation == "validate":
            type(bad).model_validate(bad)
        elif operation == "digest":
            bad.digest()
        elif operation == "dump":
            bad.model_dump()
        else:
            bad.model_dump_json()
