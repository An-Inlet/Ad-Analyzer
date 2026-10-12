"""Genuine synthetic pure V6; no SQL/runtime/owner authorization qualification."""

from typing import Any

import pytest
from app.planning_documents import documents
from app.planning_documents.common import MAX_DOCUMENT_BYTES
from app.planning_documents.creative_plan_composer import CreativePlanComposer
from app.planning_documents.documents import PlanVersion
from app.planning_documents.owner_review_plan_composer import OwnerReviewPlanComposer
from app.planning_documents.owner_review_plan_document import linked_owner_input_catalogs
from app.planning_documents.policy_capabilities import reporting_capability
from app.planning_documents.selected_composer import SelectedPlanComposer
from app.planning_documents.selected_policy_contract import selected_policy_contract

from tests.owner_review_v6_fixture import ready, social_catalog
from tests.test_creative_plan_composer import compose as old_compose
from tests.test_creative_plan_composer import ready as old_ready


def compose(values: Any) -> PlanVersion:
    ticket, evidence, policy, now = values
    return OwnerReviewPlanComposer().compose(
        ticket=ticket, evidence=evidence, policy=policy, generated_at=now
    )


@pytest.mark.parametrize(
    "zero,empty,no_links",
    [(False, False, False), (True, False, False), (False, True, False), (True, True, True)],
)
def test_complete_genuine_v6_investigation_only(zero: bool, empty: bool, no_links: bool) -> None:
    values = ready(zero=zero, empty=empty, no_links=no_links)
    ticket, evidence, policy, _ = values
    doc = compose(values)
    assert doc.inputs == ticket.inputs
    assert doc.google_budget_owner_review is not None
    assert doc.google_budget_input_catalogs == (
        () if no_links else evidence.reporting.selected.catalogs
    )
    assert len(doc.google_budget_owner_review.reviews) == (0 if empty else 1)
    for review in doc.google_budget_owner_review.reviews:
        assert review.application == "unavailable"
        assert (
            review.period_spending_compatibility == review.provider_edit_validity == "not_assessed"
        )
        action = next(a for a in doc.actions if a.key == review.action_key)
        assert (
            action.kind == "investigate"
            and action.native_budget is None
            and not action.proposed_fields
        )
        assert review.intent.requested_amount_micros == (0 if zero else 1)
        assert all(
            a.priority < action.priority
            for a in doc.actions
            if a.key != action.key and a.kind != "creative_review"
        )
    assert PlanVersion.model_validate_json(doc.model_dump_json()) == doc
    assert PlanVersion.model_validate(doc).digest() == doc.digest()
    assert reporting_capability(policy.version, policy.generator_version).mode == (
        "owner_review_creative_selected_requested_window"
    )


@pytest.mark.parametrize("social", ["meta", "tiktok"])
@pytest.mark.parametrize("usage", ["scenario", "exclusion", "fixed", "unselected"])
def test_full_mixed_catalog_set_and_global_creative_order(social: str, usage: str) -> None:
    values = ready(social=social, usage=usage)
    doc = compose(values)
    assert doc.google_budget_input_catalogs is not None
    assert len(doc.google_budget_input_catalogs) == (1 if usage == "unselected" else 2)
    assert doc.selected_reporting_proof is not None
    assert len(doc.selected_reporting_proof.accounts) == 2
    assert doc.google_budget_owner_review is not None
    assert len(doc.google_budget_owner_review.reviews) == 1
    priorities = [a.priority for a in doc.actions if a.key.startswith("owner-review:")]
    assert all(a.priority > max(priorities) for a in doc.actions if a.kind == "creative_review")
    if usage != "unselected":
        with pytest.raises(ValueError):
            PlanVersion.model_validate(
                doc.model_copy(
                    update={"google_budget_input_catalogs": doc.google_budget_input_catalogs[:1]}
                )
            )
    assert PlanVersion.model_validate_json(doc.model_dump_json()) == doc


@pytest.mark.parametrize(
    "field",
    [
        "google_budget_owner_review",
        "google_budget_input_catalogs",
        "selected_reporting_proof",
        "creative_proof",
        "creative_composition",
    ],
)
def test_v6_requires_complete_proof_matrix(field: str) -> None:
    doc = compose(ready())
    changed = doc.model_copy(update={field: None})
    with pytest.raises(ValueError):
        PlanVersion.model_validate(changed)
    with pytest.raises(ValueError):
        changed.digest()
    for dump in (changed.model_dump, changed.model_dump_json):
        with pytest.raises(ValueError):
            dump()


@pytest.mark.parametrize("version", [1, 2, 3, 4, 5])
def test_old_pair_still_refuses_nonnull_owner_document(version: int) -> None:
    doc = compose(ready(empty=True))
    with pytest.raises(ValueError):
        PlanVersion.model_validate(
            doc.model_copy(
                update={
                    "policy_version": f"inlet.descriptive-review.v{version}",
                    "generator_version": f"inlet.descriptive-planning.v{version}",
                }
            )
        )


@pytest.mark.parametrize("empty", [False, True])
def test_old_composer_entrypoints_reject_genuine_v6(empty: bool) -> None:
    ticket, evidence, policy, now = ready(empty=empty)
    with pytest.raises(ValueError):
        CreativePlanComposer().compose(
            ticket=ticket, evidence=evidence, policy=policy, generated_at=now
        )
    with pytest.raises(ValueError):
        SelectedPlanComposer()._compose(
            ticket, evidence.reporting, policy, now, creative=evidence.creative
        )
    with pytest.raises(ValueError):
        SelectedPlanComposer().compose(
            ticket=ticket, evidence=evidence.reporting, policy=policy, generated_at=now
        )


def test_old_creative_wrapper_rejects_v6_even_absent_owner_input() -> None:
    ticket, evidence, policy, now = ready()
    ticket = ticket.model_copy(
        update={"inputs": ticket.inputs.model_copy(update={"google_daily_budget_intents": None})}
    )
    with pytest.raises(ValueError, match="canonical creative"):
        CreativePlanComposer().compose(
            ticket=ticket, evidence=evidence, policy=policy, generated_at=now
        )


@pytest.mark.parametrize(
    "case", ["duplicate", "order", "foreign-account", "raw-bool", "reference", "proof"]
)
def test_complete_catalog_and_unsafe_copy_revalidation(case: str) -> None:
    doc = compose(ready(social="meta"))
    assert doc.google_budget_input_catalogs is not None
    first, second = doc.google_budget_input_catalogs
    changes: dict[str, Any] = {}
    if case == "duplicate":
        changes["google_budget_input_catalogs"] = (first, first)
    elif case == "order":
        changes["google_budget_input_catalogs"] = (second, first)
    elif case == "foreign-account":
        assert first.reference.account is not None
        first = first.model_copy(
            update={
                "reference": first.reference.model_copy(
                    update={
                        "account": first.reference.account.model_copy(update={"connection_id": 999})
                    }
                )
            }
        )
        changes["google_budget_input_catalogs"] = (first, second)
    elif case == "raw-bool":
        first = first.model_copy(
            update={
                "catalog": first.catalog.model_copy(
                    update={
                        "native_observation": first.catalog.native_observation.model_copy(
                            update={"advertising_writes_enabled": 0}
                        )
                    }
                )
            }
        )
        changes["google_budget_input_catalogs"] = (first, second)
    elif case == "reference":
        first = first.model_copy(
            update={"reference": first.reference.model_copy(update={"key": "catalog:other"})}
        )
        changes["google_budget_input_catalogs"] = (first, second)
    else:
        assert doc.google_budget_owner_review is not None
        changes["google_budget_owner_review"] = doc.google_budget_owner_review.model_copy(
            update={"input_digest": "0" * 64}
        )
    changed = doc.model_copy(update=changes)
    with pytest.raises(ValueError):
        PlanVersion.model_validate(changed)
    for dump in (changed.model_dump, changed.model_dump_json):
        with pytest.raises(ValueError):
            dump()


def test_exact_unused_catalog_refusal_and_input_target_substitution() -> None:
    values = ready(social="meta", usage="unselected")
    doc = compose(values)
    with pytest.raises(ValueError, match="linked catalog set"):
        PlanVersion.model_validate(
            doc.model_copy(
                update={"google_budget_input_catalogs": values[1].reporting.selected.catalogs}
            )
        )
    inputs = values[0].inputs
    target = inputs.scenario_intents[0].allocations[0].target
    altered = inputs.model_copy(
        update={
            "scenario_intents": (
                inputs.scenario_intents[0].model_copy(
                    update={
                        "allocations": (
                            inputs.scenario_intents[0]
                            .allocations[0]
                            .model_copy(
                                update={
                                    "target": target.model_copy(update={"selection_key": "0" * 64})
                                }
                            ),
                        )
                    }
                ),
            )
        }
    )
    with pytest.raises(ValueError):
        linked_owner_input_catalogs(altered, values[1].reporting.selected.catalogs)


def test_exact_document_byte_bound_and_legacy_omission(monkeypatch: pytest.MonkeyPatch) -> None:
    doc = compose(ready(social="meta"))
    size = len(doc.model_dump_json().encode())
    assert size < MAX_DOCUMENT_BYTES == 1_048_576
    monkeypatch.setattr(documents, "MAX_DOCUMENT_BYTES", size)
    assert PlanVersion.model_validate(doc) == doc
    monkeypatch.setattr(documents, "MAX_DOCUMENT_BYTES", size - 1)
    with pytest.raises(ValueError, match="operational document size"):
        PlanVersion.model_validate(doc)
    monkeypatch.setattr(documents, "MAX_DOCUMENT_BYTES", 1_048_576)
    old = old_compose(old_ready())
    for dump in (old.model_dump(), old.model_dump(mode="json")):
        assert (
            "google_budget_owner_review" not in dump and "google_budget_input_catalogs" not in dump
        )
    contract = selected_policy_contract(old.policy_version, old.generator_version)
    assert (
        not contract.requires_owner_review and "requires_owner_review" not in contract.model_dump()
    )


def test_rehashed_other_platform_catalog_cannot_replace_original_link() -> None:
    doc = compose(ready(social="meta"))
    assert doc.google_budget_input_catalogs is not None
    google, old = doc.google_budget_input_catalogs
    changed = social_catalog(google, "meta", renamed=True)
    assert type(changed).model_validate(changed) == changed
    assert changed.catalog.composite_digest != old.catalog.composite_digest
    altered = doc.model_copy(update={"google_budget_input_catalogs": (google, changed)})
    for check in (
        lambda: PlanVersion.model_validate(altered),
        altered.model_dump,
        altered.model_dump_json,
    ):
        with pytest.raises(ValueError):
            check()


@pytest.mark.parametrize("case", ["policy", "evidence", "creative"])
def test_shared_core_independently_validates_original_packet(case: str) -> None:
    ticket, evidence, policy, now = ready()
    creative = evidence.creative
    paired = evidence.reporting
    if case == "policy":
        policy = policy.model_copy(update={"version": "inlet.descriptive-review.v5"})
    elif case == "evidence":
        paired = paired.model_copy(
            update={"selected": paired.selected.model_copy(update={"input_digest": "0" * 64})}
        )
    else:
        creative = None
    with pytest.raises(ValueError):
        SelectedPlanComposer()._compose_document(ticket, paired, policy, now, creative=creative)


def test_retagged_stripped_owner_document_cannot_serialize() -> None:
    doc = compose(ready())
    altered = doc.model_copy(
        update={
            "policy_version": "inlet.descriptive-review.v5",
            "generator_version": "inlet.descriptive-planning.v5",
            "google_budget_owner_review": None,
            "google_budget_input_catalogs": None,
        }
    )
    for check in (
        lambda: PlanVersion.model_validate(altered),
        altered.model_dump,
        altered.model_dump_json,
    ):
        with pytest.raises(ValueError):
            check()


@pytest.mark.parametrize("field", ["policy_version", "generator_version"])
def test_mismatched_reserved_pair_refuses_without_serialization_recursion(field: str) -> None:
    from tests.test_planning_composer import compose as legacy_compose
    from tests.test_planning_composer import fixture

    doc = legacy_compose(*fixture())
    prefix = (
        "inlet.descriptive-review" if field == "policy_version" else "inlet.descriptive-planning"
    )
    altered = doc.model_copy(update={field: prefix + ".v6"})
    for check in (
        lambda: PlanVersion.model_validate(altered),
        altered.model_dump,
        altered.model_dump_json,
    ):
        with pytest.raises(ValueError, match="exact v6 pair"):
            check()


@pytest.mark.parametrize("case", ["policy", "evidence"])
def test_shared_noncreative_v4_core_cannot_bypass_validation(case: str) -> None:
    from datetime import timedelta

    from tests.test_selected_paired_composer import ready as v4_ready

    ticket, paired, policy = v4_ready()
    now = paired.selected.collected_at + timedelta(seconds=1)
    if case == "policy":
        policy = policy.model_copy(update={"version": "inlet.descriptive-review.v3"})
    else:
        paired = paired.model_copy(
            update={"selected": paired.selected.model_copy(update={"input_digest": "0" * 64})}
        )
    with pytest.raises(ValueError):
        SelectedPlanComposer()._compose_document(ticket, paired, policy, now)


@pytest.mark.parametrize("usage", ["scenario", "exclusion"])
def test_retained_mixed_meta_optional_schedule_is_original_evidence(usage: str) -> None:
    from app.planning_documents.google_budget_owner_review import (
        validate_retained_google_budget_owner_review,
    )

    doc = compose(ready(social="meta", usage=usage))
    assert doc.google_budget_owner_review is not None
    assert doc.google_budget_input_catalogs is not None
    assert doc.selected_reporting_proof is not None
    validate_retained_google_budget_owner_review(
        inputs=doc.inputs,
        actions=doc.actions,
        proof=doc.google_budget_owner_review,
        catalogs=doc.google_budget_input_catalogs,
        sources=tuple(p.source_fence for p in doc.selected_reporting_proof.accounts),
    )


def test_frozen_full_v4_v5_document_and_descriptor_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    import hashlib
    import json
    from pathlib import Path

    from tests.test_selected_observation_provenance import legacy_pin_projection
    from tests.test_selected_paired_composer import compose as compose_v4
    from tests.test_selected_paired_composer import ready as ready_v4

    # These frozen hashes predate typed capture provenance. Keep original bytes.
    legacy_pin_projection(monkeypatch)
    expected = json.loads(
        (Path(__file__).parent / "fixtures/owner_review/legacy-goldens.json").read_text()
    )
    actual = {
        "v4": compose_v4(*ready_v4()),
        "v5meta": old_compose(old_ready("meta")),
        "v5tiktok": old_compose(old_ready("tiktok")),
    }
    for key, doc in actual.items():
        golden = expected["documents"][key]
        assert hashlib.sha256(doc.model_dump_json().encode()).hexdigest() == golden["json_sha256"]
        assert doc.digest() == golden["digest"]
        assert (
            selected_policy_contract(doc.policy_version, doc.generator_version).model_dump_json()
            == golden["descriptor"]
        )
