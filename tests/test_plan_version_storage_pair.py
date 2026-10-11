"""Exact adjacent storage serialization; no authority/performance qualification."""

import hashlib
from datetime import datetime
from typing import Any

import pytest
from app.planning_documents import storage
from app.planning_documents.documents import PlanVersion

from tests.owner_review_v6_fixture import ready as ready_v6
from tests.test_creative_plan_composer import compose as compose_v5
from tests.test_creative_plan_composer import ready as ready_v5
from tests.test_creative_plan_document import legacy_documents
from tests.test_owner_review_v6_pure import compose as compose_v6


def document(version: int, *, empty: bool = False) -> PlanVersion:
    if version < 5:
        return legacy_documents()[version - 1]
    if version == 5:
        return compose_v5(ready_v5())
    return compose_v6(ready_v6(empty=empty))


@pytest.mark.parametrize(
    "version,empty",
    [(1, False), (2, False), (3, False), (4, False), (5, False), (6, False), (6, True)],
)
def test_exact_existing_json_and_digest(version: int, empty: bool) -> None:
    value = document(version, empty=empty)
    raw, digest = storage.plan_version_storage_pair(value)
    assert raw == storage.canonical(value)
    assert digest == value.digest()
    assert (
        digest
        == hashlib.sha256(
            b"inlet.planning-documents.v1\0PlanVersion\0" + raw.encode("utf-8")
        ).hexdigest()
    )


@pytest.mark.parametrize("attack", ["version", "mixed", "catalog", "source", "time"])
def test_unsafe_copies_fail_existing_validation(attack: str) -> None:
    value = document(6)
    if attack == "version":
        changed = value.model_copy(update={"version": 0})
    elif attack == "mixed":
        changed = value.model_copy(update={"policy_version": "inlet.descriptive-review.v3"})
    elif attack == "catalog":
        changed = value.model_copy(update={"google_budget_input_catalogs": ()})
    elif attack == "source":
        proof = value.selected_reporting_proof
        assert proof is not None
        changed = value.model_copy(
            update={"selected_reporting_proof": proof.model_copy(update={"accounts": ()})}
        )
    else:
        changed = value.model_copy(update={"generated_at": datetime(2026, 1, 1)})
    with pytest.raises(ValueError):
        storage.canonical(changed)
    with pytest.raises(ValueError):
        storage.plan_version_storage_pair(changed)


def test_exact_model_and_single_serialization(monkeypatch: pytest.MonkeyPatch) -> None:
    value = document(6)
    original = storage.canonical
    calls: list[PlanVersion] = []

    def observed(candidate: Any) -> str:
        calls.append(candidate)
        return original(candidate)

    def forbidden(*args: Any, **kwargs: Any) -> str:
        raise AssertionError("candidate.digest must not be called")

    monkeypatch.setattr(storage, "canonical", observed)
    # Child model digest methods remain untouched.
    monkeypatch.setattr(PlanVersion, "digest", forbidden)
    storage.plan_version_storage_pair(value)
    assert calls == [value]

    class OtherPlanVersion(PlanVersion):
        pass

    subclass = OtherPlanVersion.model_construct(**value.__dict__)
    with pytest.raises(ValueError, match="exact PlanVersion"):
        storage.plan_version_storage_pair(subclass)


def test_no_cross_call_cache_and_immutable_pair() -> None:
    value = document(6)
    original = storage.plan_version_storage_pair(value)
    copied = value.model_copy(update={"version": 0})
    with pytest.raises(ValueError):
        storage.plan_version_storage_pair(copied)
    assert storage.plan_version_storage_pair(value) == original
    assert type(original[0]) is str and type(original[1]) is str


def test_canonical_byte_bound_remains(monkeypatch: pytest.MonkeyPatch) -> None:
    value = document(6)
    raw = storage.canonical(value)
    monkeypatch.setattr(storage, "MAX_DOCUMENT_BYTES", len(raw.encode("utf-8")) - 1)
    with pytest.raises(ValueError, match="exceeds bound"):
        storage.plan_version_storage_pair(value)
