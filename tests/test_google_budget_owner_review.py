"""Standalone pure owner investigation, never a generated native-edit recommendation."""

import json
from typing import Any

import pytest
from app.planning_documents.actions import ManualAction, UnavailableBudget
from app.planning_documents.common import MAX_DOCUMENT_BYTES
from app.planning_documents.context import PlanInputRevision
from app.planning_documents.google_budget_owner_contracts import resolve_google_daily_budget_intent
from app.planning_documents.google_budget_owner_review import (
    REVIEW_MESSAGE,
)
from app.planning_documents.google_budget_owner_review import (
    compose_google_budget_owner_reviews as compose,
)
from app.planning_documents.google_budget_owner_review import (
    validate_google_budget_owner_review as validate,
)
from app.planning_documents.google_budget_owner_review_contracts import (
    GoogleBudgetOwnerReviewProofV1,
    GoogleBudgetOwnerReviewV1,
    owner_review_action_key,
)

from tests.test_google_budget_input_bindings import setup
from tests.test_google_budget_owner_contracts import derive, evidence, intent


def ready(*, zero: bool = False, empty: bool = False) -> dict[str, Any]:
    values = setup(zero=zero)
    raw = values.pop("inputs").model_dump(mode="python")
    raw["google_daily_budget_intents"] = () if empty else values.pop("intents")
    values.pop("intents", None)
    values["inputs"] = PlanInputRevision.model_validate(raw)
    return values


@pytest.mark.parametrize("zero,empty", [(False, False), (True, False), (False, True)])
def test_complete_investigation_only_and_exact_roundtrip(zero: bool, empty: bool) -> None:
    values = ready(zero=zero, empty=empty)
    actions, proof = compose(**values, first_priority=4)
    validate(**values, actions=actions, proof=proof)
    assert proof.input_digest == values["inputs"].digest()
    assert len(actions) == len(proof.reviews) == (0 if empty else 1)
    assert GoogleBudgetOwnerReviewProofV1.model_validate_json(proof.model_dump_json()) == proof
    assert (
        proof.digest()
        == GoogleBudgetOwnerReviewProofV1.model_validate_json(proof.model_dump_json()).digest()
    )
    if not empty:
        action, review = actions[0], proof.reviews[0]
        assert action.kind == "investigate" and action.priority == 4
        assert action.native_budget is None and action.proposed_fields == ()
        assert action.rationale == REVIEW_MESSAGE and action.manual_steps[-1] == REVIEW_MESSAGE
        assert len(review.witness.affected_campaigns) == 2
        assert review.application == "unavailable"
        assert (
            review.period_spending_compatibility == review.provider_edit_validity == "not_assessed"
        )
        assert review.witness.model_dump_json() == derive(values["catalogs"][0]).model_dump_json()
        assert review.intent.requested_amount_micros == (0 if zero else 1)
        assert "not a conversion" in action.manual_steps[2]
        assert "not evidence" in action.limitations[1]


@pytest.mark.parametrize(
    "field,value",
    [
        ("privacy_revision", True),
        ("privacy_revision", -1),
        ("sources", ()),
        ("catalogs", ()),
        ("first_priority", True),
        ("first_priority", 0),
        ("first_priority", 101),
    ],
)
def test_strict_source_and_priority_refusal(field: str, value: Any) -> None:
    values = ready()
    values.update(first_priority=1)
    values[field] = value
    with pytest.raises(ValueError):
        compose(**values)


@pytest.mark.parametrize(
    "case", ["absent", "duplicate", "source", "raw-bool", "raw-bytes", "empty-source"]
)
def test_complete_original_binding_not_a_primitive_display(case: str) -> None:
    values = ready(empty=case == "empty-source")
    inputs = values["inputs"]
    if case == "absent":
        values["inputs"] = inputs.model_copy(update={"google_daily_budget_intents": None})
    elif case == "duplicate":
        values["inputs"] = inputs.model_copy(
            update={"google_daily_budget_intents": inputs.google_daily_budget_intents * 2}
        )
    elif case in {"source", "empty-source"}:
        values["sources"] = ()
    else:
        catalog = values["catalogs"][0]
        native = catalog.catalog.native_observation.model_copy(
            update={
                "advertising_writes_enabled" if case == "raw-bool" else "platform": 0
                if case == "raw-bool"
                else b"google_ads",
            }
        )
        values["catalogs"] = (
            catalog.model_copy(
                update={
                    "catalog": catalog.catalog.model_copy(update={"native_observation": native})
                }
            ),
        )
    with pytest.raises(ValueError):
        compose(**values, first_priority=1)


@pytest.mark.parametrize(
    "case", ["input", "missing", "duplicate", "title", "steps", "priority", "unbound", "budget"]
)
def test_full_action_proof_binding(case: str) -> None:
    values = ready()
    actions, proof = compose(**values, first_priority=1)
    action = actions[0]
    if case == "input":
        proof = proof.model_copy(update={"input_digest": "0" * 64})
    elif case == "missing":
        actions = ()
    elif case == "duplicate":
        proof = proof.model_copy(update={"reviews": proof.reviews * 2})
    elif case == "title":
        actions = (action.model_copy(update={"title": "Apply this budget"}),)
    elif case == "steps":
        actions = (action.model_copy(update={"manual_steps": ("Apply the amount now.",)}),)
    elif case == "priority":
        actions = (action.model_copy(update={"priority": True}),)
    elif case == "unbound":
        actions += (action.model_copy(update={"key": "owner-review:" + "e" * 64, "priority": 2}),)
    else:
        actions += (
            ManualAction.model_validate(
                action.model_copy(
                    update={
                        "key": "other-budget",
                        "priority": 2,
                        "kind": "budget_review",
                        "native_budget": UnavailableBudget(reason="Not assessed"),
                    }
                )
            ),
        )
    with pytest.raises(ValueError):
        validate(**values, actions=actions, proof=proof)


def test_valid_rehashed_substitution_does_not_match_actual_catalog() -> None:
    values = ready()
    actions, proof = compose(**values, first_priority=1)
    other = derive(evidence(change="name"))
    resolved = resolve_google_daily_budget_intent(intent(other, requested_amount_micros=1), other)
    substituted = GoogleBudgetOwnerReviewV1(
        action_key=owner_review_action_key(other), intent=resolved, witness=other
    )
    changed = GoogleBudgetOwnerReviewProofV1(
        input_digest=proof.input_digest, reviews=(substituted,)
    )
    assert changed.digest() != proof.digest()
    with pytest.raises(ValueError, match="actual input/catalog"):
        validate(**values, actions=actions, proof=changed)


@pytest.mark.parametrize(
    "field,value",
    [
        ("advertising_writes_enabled", 0),
        ("application", b"unavailable"),
        ("period_spending_compatibility", "qualified"),
    ],
)
def test_unsafe_copied_proof_primitives_rejected(field: str, value: Any) -> None:
    _, proof = compose(**ready(), first_priority=1)
    copied = proof.model_copy(
        update={"reviews": (proof.reviews[0].model_copy(update={field: value}),)}
    )
    for operation in (
        copied.digest,
        copied.model_dump,
        copied.model_dump_json,
        copied.reviews[0].model_dump,
        copied.reviews[0].model_dump_json,
    ):
        with pytest.raises(ValueError):
            operation()


def test_total_output_bound_and_no_silent_action_truncation() -> None:
    values = ready()
    actions, proof = compose(**values, first_priority=1)
    filler = tuple(
        ManualAction.model_validate(
            actions[0].model_copy(
                update={
                    "key": f"report-{i}",
                    "priority": i,
                    "manual_steps": ("x" * 2000,) * 20,
                    "limitations": ("y" * 2000,) * 20,
                }
            )
        )
        for i in range(2, 101)
    )
    assert (
        len(json.dumps([a.model_dump(mode="json") for a in actions + filler]).encode())
        > MAX_DOCUMENT_BYTES
    )
    with pytest.raises(ValueError, match="byte bound"):
        validate(**values, actions=actions + filler, proof=proof)
    with pytest.raises(ValueError, match="bounded action tuple"):
        validate(**values, actions=actions * 101, proof=proof)
    with pytest.raises(ValueError):
        GoogleBudgetOwnerReviewProofV1.model_validate(
            proof.model_copy(update={"reviews": proof.reviews * 21})
        )
