"""Synthetic candidate constraints and exact retained templates, never live qualification."""

from typing import Any

import pytest
from app.planning_documents.composer import targets
from app.planning_documents.constraint_interpretation import (
    LITERAL,
    ConstraintInterpretationV1,
    interpret_constraints,
)
from app.planning_documents.creative_basis import CreativeInputV1
from app.planning_documents.creative_plan_bundle import CreativePairedEvidenceV1
from app.planning_documents.documents import PlanVersion
from app.planning_documents.ports import (
    ContextEvidence,
    GenerationTicket,
    PlanningCompositionPolicy,
)
from app.planning_documents.runtime_policy import configured_policy
from app.planning_documents.storage import canonical, plan_version_storage_pair
from app.settings import Settings

from tests.test_creative_plan_composer import compose
from tests.test_creative_plan_composer import ready as legacy_ready


def candidate_policy() -> PlanningCompositionPolicy:
    return PlanningCompositionPolicy(
        version="inlet.descriptive-review.v7", generator_version="inlet.descriptive-planning.v7"
    )


def ready(
    platform: str = "meta",
    *,
    constraints: tuple[str, ...] = (LITERAL,),
    product_restrictions: tuple[str, ...] = (),
    images: int = 1,
    **changes: Any,
) -> Any:
    initial = legacy_ready(platform, images=images)
    creative = initial[0].inputs.creative.model_dump(mode="python")
    creative["product"].update(
        name="50% OFF! BUY NOW",
        customer_asserted_facts=("SAVE 20 USD TODAY",),
        restrictions=product_restrictions,
    )
    ticket, evidence, _, now = legacy_ready(
        platform,
        images=images,
        constraints=constraints,
        creative=CreativeInputV1.model_validate(creative),
        **changes,
    )
    policy = candidate_policy()
    ticket = GenerationTicket.model_validate(
        ticket.model_copy(
            update=dict(
                policy_version=policy.version,
                policy_digest=policy.digest(),
            )
        )
    )
    selected = evidence.reporting.selected
    contexts = tuple(
        ContextEvidence(
            reference=entry.reference.model_copy(update=dict(document_digest=policy.digest())),
            document=policy,
        )
        if entry.reference.kind == "planning_policy"
        else entry
        for entry in selected.context
    )
    selected = selected.model_copy(update=dict(context=contexts))
    evidence = CreativePairedEvidenceV1.model_validate(
        evidence.model_copy(
            update=dict(
                reporting=evidence.reporting.model_copy(update=dict(selected=selected)),
                creative=evidence.creative.model_copy(update=dict(ticket_digest=ticket.digest())),
            )
        )
    )
    return ticket, evidence, policy, now


@pytest.mark.parametrize(
    "constraints,product,disposition",
    [
        ((), (), "no_constraints"),
        ((LITERAL,), (), "fully_recognized"),
        ((LITERAL, LITERAL), (LITERAL,), "fully_recognized"),
        ((LITERAL, "No ads until reviewed"), (), "unresolved"),
        (("no discount claims.",), (), "unresolved"),
        (("No discount claims",), (), "unresolved"),
        (("Allow discount claims.",), (), "unresolved"),
        (("No discount claims. Except today.",), (), "unresolved"),
        ((), ("Do not publish product images",), "unresolved"),
        ((LITERAL,), (LITERAL, "No videos"), "unresolved"),
    ],
)
def test_exact_ordered_interpretation(constraints: Any, product: Any, disposition: str) -> None:
    inputs = ready(constraints=constraints, product_restrictions=product)[0].inputs
    result = interpret_constraints(inputs)
    assert result.disposition == disposition
    assert tuple(e.original_text for e in result.entries) == constraints
    assert tuple(e.source_index for e in result.entries) == tuple(range(len(constraints)))
    assert tuple(e.original_text for e in result.product_entries) == product
    assert result.input_digest == inputs.digest()
    result.assert_inputs(inputs)
    assert ConstraintInterpretationV1.model_validate_json(result.model_dump_json()) == result
    with pytest.raises(ValueError):
        result.model_copy(update=dict(input_digest="0" * 64)).assert_inputs(inputs)
    if result.entries:
        changed = result.model_copy(
            update=dict(
                entries=(
                    result.entries[0].model_copy(update=dict(rule=None, unresolved_reason=None)),
                )
            )
        )
        with pytest.raises(ValueError):
            changed.assert_inputs(inputs)


@pytest.mark.parametrize("platform", ["meta", "tiktok"])
@pytest.mark.parametrize(
    "variant",
    ["recognized", "none", "unknown", "product_unknown", "capacity", "images", "excluded", "zero"],
)
def test_candidate_constraints_and_preserved_limits(platform: str, variant: str) -> None:
    changes: dict[str, Any] = {}
    if variant == "none":
        changes["constraints"] = ()
    elif variant == "unknown":
        changes["constraints"] = (LITERAL, "Do not use video")
    elif variant == "product_unknown":
        changes["product_restrictions"] = ("No ads",)
    elif variant == "capacity":
        changes["maximum_creative_assets"] = 0
    elif variant == "images":
        changes["images"] = 0
    elif variant == "excluded":
        catalog = ready(platform)[1].reporting.selected.catalogs[0]
        changes["excluded_entity_keys"] = tuple(t.canonical_entity_key for t in targets(catalog))
    elif variant == "zero":
        goal = ready(platform)[0].inputs.goal.model_dump(mode="python")
        from app.planning_documents.common import fingerprint

        definition = goal["definition"]
        definition["budget_micros"] = 0
        from app.goals.schemas import GoalDefinition

        definition = GoalDefinition.model_validate(definition)
        goal["definition"] = definition
        goal["definition_digest"] = fingerprint(
            "goal-definition", definition.model_dump(mode="json")
        )
        changes.update(goal=goal, total_ceiling_micros=0)
    values = ready(platform, **changes)
    doc = compose(values)
    assert doc.schema_version == "inlet.plan-version.v4"
    assert doc.inputs == values[0].inputs
    assert doc.constraint_interpretation == interpret_constraints(doc.inputs)
    assert doc.creative_composition is not None and doc.creative_proof is not None
    assert doc.creative_proof.basis.requested == doc.inputs.creative
    assert doc.inputs.creative is not None and doc.inputs.creative.product is not None
    assert doc.inputs.creative.product.name == "50% OFF! BUY NOW"
    for scenario in doc.scenarios:
        assert scenario.ceiling_micros == doc.inputs.total_ceiling_micros
        assert (
            sum(a.amount_micros for a in scenario.allocations) + scenario.unallocated_micros
            == scenario.ceiling_micros
        )
    proposals = doc.creative_composition.proposals
    if variant in {"recognized", "none", "zero"}:
        assert len(proposals) == 1
        p = proposals[0]
        assert "50% OFF" not in p.model_dump_json() and "SAVE 20" not in p.model_dump_json()
        assert p.brief.hooks == ("Explore the product.",)
        assert p.production.source_images == doc.inputs.creative.media_selections
        assert p.production.deliverable_status == "production_required"
        assert len(p.production.storyboard) == (0 if platform == "meta" else 3)
        assert any("No advertising spend" in step for step in p.action.manual_steps)
    else:
        assert not proposals and not doc.briefs
        assert any("Deferred:" in s for s in doc.section_limitations)
    assert all(a.native_budget is None and not a.proposed_fields for a in doc.actions)
    assert not doc.advertising_writes_enabled and doc.spending_authority == "none"
    assert PlanVersion.model_validate_json(doc.model_dump_json()) == doc
    assert plan_version_storage_pair(doc) == (canonical(doc), doc.digest())


@pytest.mark.parametrize(
    "fault", ["missing", "input_digest", "text", "scope", "copy", "schema", "policy", "unsafe"]
)
def test_retained_constraint_or_copy_forgery_refused(fault: str) -> None:
    doc = compose(ready())
    data = doc.model_dump(mode="python")
    if fault == "missing":
        data.pop("constraint_interpretation")
    elif fault == "input_digest":
        data["constraint_interpretation"]["input_digest"] = "0" * 64
    elif fault == "text":
        data["constraint_interpretation"]["original_constraints"] = ()
    elif fault == "scope":
        data["constraint_interpretation"]["original_product_restrictions"] = ("No ads",)
    elif fault in {"copy", "unsafe"}:
        data["creative_composition"]["proposals"][0]["brief"]["hooks"] = ("Buy 50% off",)
        data["briefs"][0]["hooks"] = ("Buy 50% off",)
    elif fault == "schema":
        data["schema_version"] = "inlet.plan-version.v1"
    else:
        data["policy_version"] = "inlet.descriptive-review.v5"
    with pytest.raises(ValueError):
        if fault == "unsafe":
            plan_version_storage_pair(doc.model_copy(update=data))
        else:
            PlanVersion.model_validate(data)


def test_candidate_explicit_configuration_and_legacy_reader_floor() -> None:
    config = Settings()
    assert config.customer_planning_policy == "v3"
    selected = Settings(INLET_CUSTOMER_PLANNING_POLICY="v7")
    assert configured_policy(selected) == candidate_policy()
    old = compose(legacy_ready())
    assert "constraint_interpretation" not in old.model_dump(mode="json")
    import hashlib
    import json
    import runpy
    from pathlib import Path

    fixture = Path("tests/fixtures/q10/pre-constraint-documents.py.txt")
    provenance = json.loads(fixture.with_name("reader-provenance.json").read_text())
    assert hashlib.sha256(fixture.read_bytes()).hexdigest() == provenance["sha256"]
    old_reader = runpy.run_path(str(fixture))["PlanVersion"]
    from tests.test_selected_paired_composer import compose as compose_v4
    from tests.test_selected_paired_composer import ready as ready_v4

    enriched = compose_v4(*ready_v4())
    assert (
        hashlib.sha256(enriched.model_dump_json().encode()).hexdigest()
        == provenance["enriched_v4_json_sha256"]
    )
    assert (
        old_reader.model_validate_json(enriched.model_dump_json()).model_dump_json()
        == enriched.model_dump_json()
    )
    prior = old_reader.model_validate_json(old.model_dump_json())
    assert prior.model_dump_json() == old.model_dump_json() and prior.digest() == old.digest()
    with pytest.raises(ValueError, match="schema_version"):
        old_reader.model_validate_json(compose(ready()).model_dump_json())


def test_v4_mixed_typed_and_stripped_capture_provenance_refused() -> None:
    from pathlib import Path

    from app.planning_documents.constraint_document import assert_constraint_capture_provenance
    from app.planning_documents.selected_plan_contracts import SelectedPlanPinV1

    prior = PlanVersion.model_validate_json(
        Path("tests/fixtures/selected_provenance/pre-settings-plan-v2.json").read_bytes()
    )
    assert prior.selected_reporting_proof is not None
    pin = prior.selected_reporting_proof.accounts[0].capture_pin
    assert pin is not None and pin.observation_provenance is not None
    stripped = SelectedPlanPinV1.model_validate(
        pin.model_copy(update=dict(observation_provenance=None))
    )
    assert_constraint_capture_provenance(())
    assert_constraint_capture_provenance((pin, pin))
    assert_constraint_capture_provenance((stripped, stripped))
    with pytest.raises(ValueError, match="cover every"):
        assert_constraint_capture_provenance((pin, stripped))
