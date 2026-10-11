"""Genuine pure v5 composition; these fixtures do not authenticate media or persist plans."""

from datetime import timedelta
from typing import Any

import pytest
from app.planning_documents.composer import PlanCompositionUnavailable, targets
from app.planning_documents.context import PlanInputRevision
from app.planning_documents.creative_basis import CreativeBasisV1
from app.planning_documents.creative_composition import canonical_creative_policy
from app.planning_documents.creative_image_collection import (
    CollectedCreativeBasisV1,
    PlanningImageRowPinV1,
)
from app.planning_documents.creative_plan_bundle import CreativePairedEvidenceV1
from app.planning_documents.creative_plan_composer import CreativePlanComposer
from app.planning_documents.documents import PlanVersion
from app.planning_documents.policy_capabilities import reporting_capability
from app.planning_documents.ports import ContextEvidence, GenerationTicket
from app.planning_documents.selected_paired_evidence import SelectedPairedEvidenceV1
from app.planning_documents.selected_plan_bundle import SelectedPlanEvidenceBundleV1
from app.planning_documents.selected_plan_proof import SelectedRetainedProofV1

from tests.test_creative_composition import ready as creative_ready


def ready(platform: str = "meta", *, images: int = 1, **changes: Any) -> Any:
    inputs, catalogs, basis = creative_ready(platform, images=images)
    catalogs = tuple(
        type(c).model_validate(
            c.model_copy(
                update={
                    "reference": c.reference.model_copy(
                        update={"source_revision": c.reference.account.connection_version}
                    )
                }
            )
        )
        for c in catalogs
    )
    inputs = PlanInputRevision.model_validate(
        inputs.model_copy(update={"creative": basis.requested, "selected_reporting": (), **changes})
    )
    basis = CreativeBasisV1.model_validate(basis.model_copy(update={"requested": inputs.creative}))
    policy = canonical_creative_policy()
    prepared = max(inputs.created_at, *(c.reference.observed_at for c in catalogs))
    basis = CreativeBasisV1.model_validate(
        basis.model_copy(
            update={
                "images": tuple(
                    image.model_copy(update={"created_at": prepared, "observed_at": prepared})
                    for image in basis.images
                )
            }
        )
    )
    proof = SelectedRetainedProofV1(
        accounts=tuple(
            dict(
                source_fence=dict(
                    account=c.reference.account,
                    source_binding_digest=c.reference.source_binding_digest,
                    source_revision=c.reference.source_revision,
                    privacy_revision=c.reference.privacy_revision,
                ),
                legacy_reporting_digest="a" * 64,
                selection_head=None,
                capture_pin=None,
            )
            for c in catalogs
        )
    )
    ticket = GenerationTicket(
        operation_id="e" * 32,
        actor_id="a" * 32,
        session_digest="b" * 64,
        inputs=inputs,
        expected_version=0,
        expected_parent_digest=None,
        privacy_revision=basis.privacy_revision,
        sources=tuple(a.source_fence for a in proof.accounts),
        policy_version=policy.version,
        policy_digest=policy.digest(),
        prepared_at=prepared,
    )
    contexts = tuple(
        ContextEvidence(
            reference=catalogs[0].reference.model_copy(
                update={
                    "key": key,
                    "kind": kind,
                    "account": None,
                    "document_digest": doc.digest(),
                }
            ),
            document=doc,
        )
        for key, kind, doc in (
            ("context:inputs", "customer_context", inputs),
            ("context:policy", "planning_policy", policy),
        )
    )
    windows = (inputs.reporting_window,) + (
        (inputs.comparison_window,) if inputs.comparison_window else ()
    )
    selected = SelectedPlanEvidenceBundleV1(
        operation_id=ticket.operation_id,
        input_digest=inputs.digest(),
        privacy_revision=ticket.privacy_revision,
        collected_at=prepared + timedelta(seconds=1),
        reporting_proof=proof,
        catalogs=catalogs,
        selected_captures=(),
        performance=(),
        commerce=None,
        context=contexts,
        gaps=(),
        window_gaps=tuple(
            dict(
                account=c.reference.account,
                target=target,
                requested_window=window,
                reason="unsupported_selected_mapping",
                reporting_pin_digest=pin.state_digest(),
                explanation="Selected social reporting is unavailable in this fixture.",
            )
            for c, pin in zip(catalogs, proof.accounts, strict=True)
            for target in targets(c)
            if target.kind == "campaign"
            for window in windows
        ),
    )
    evidence = CreativePairedEvidenceV1(
        reporting=SelectedPairedEvidenceV1(
            selected=selected, traffic_graphs=(), traffic=(), traffic_gaps=()
        ),
        creative=CollectedCreativeBasisV1(
            basis=basis,
            rows=tuple(
                PlanningImageRowPinV1(witness=i, created_by=ticket.actor_id) for i in basis.images
            ),
            ticket_digest=ticket.digest(),
        ),
    )
    evidence.assert_ticket(ticket)
    return ticket, evidence, policy, prepared + timedelta(seconds=2)


def compose(values: Any) -> PlanVersion:
    ticket, evidence, policy, now = values
    return CreativePlanComposer().compose(
        ticket=ticket, evidence=evidence, policy=policy, generated_at=now
    )


@pytest.mark.parametrize("platform", ["meta", "tiktok"])
@pytest.mark.parametrize("images", [0, 1, 2])
def test_genuine_typed_output_and_original_reporting(platform: str, images: int) -> None:
    values = ready(platform, images=images)
    doc = compose(values)
    ticket, evidence, policy, _ = values
    assert doc.policy_version == policy.version
    assert doc.inputs == ticket.inputs
    assert doc.selected_reporting_proof == evidence.reporting.selected.reporting_proof
    assert doc.creative_proof is not None and doc.creative_composition is not None
    assert doc.creative_proof.basis == evidence.creative.basis
    proposals = doc.creative_composition.proposals
    assert len(proposals) == 1
    ordinary = [a for a in doc.actions if a.kind == "creative_review"]
    assert ordinary == [proposals[0].action] and doc.briefs == (proposals[0].brief,)
    assert proposals[0].action.priority == len(doc.actions)
    assert proposals[0].production.source_images == ticket.inputs.creative.media_selections
    assert proposals[0].production.deliverable_status == "production_required"
    assert len(proposals[0].production.storyboard) == (3 if platform == "tiktok" else 0)
    assert all(a.native_budget is None for a in doc.actions)
    assert PlanVersion.model_validate_json(doc.model_dump_json()) == doc
    with pytest.raises(ValueError):
        reporting_capability(policy.version, policy.generator_version)


@pytest.mark.parametrize("capacity", [0, None, 1])
def test_capacity_and_complete_limitations(capacity: int | None) -> None:
    values = ready(maximum_creative_assets=capacity)
    doc = compose(values)
    assert doc.creative_composition is not None
    assert len(doc.creative_composition.proposals) == (1 if capacity else 0)
    assert set(doc.creative_composition.limitations) <= set(doc.section_limitations)


@pytest.mark.parametrize("attack", ["ticket", "policy", "basis", "past_image", "future_generation"])
def test_exact_ticket_policy_basis_and_time(attack: str) -> None:
    ticket, evidence, policy, now = ready()
    if attack == "ticket":
        ticket = ticket.model_copy(update={"operation_id": "f" * 32})
    elif attack == "policy":
        policy = policy.model_copy(update={"version": "inlet.descriptive-review.v4"})
    elif attack == "basis":
        evidence = evidence.model_copy(
            update={"creative": evidence.creative.model_copy(update={"ticket_digest": "f" * 64})}
        )
    elif attack == "past_image":
        image = evidence.creative.basis.images[0].model_copy(
            update={
                "created_at": ticket.prepared_at - timedelta(seconds=2),
                "observed_at": ticket.prepared_at - timedelta(seconds=1),
            }
        )
        pin = evidence.creative.rows[0].model_copy(update={"witness": image})
        evidence = evidence.model_copy(
            update={
                "creative": evidence.creative.model_copy(
                    update={
                        "basis": evidence.creative.basis.model_copy(update={"images": (image,)}),
                        "rows": (pin,),
                    }
                )
            }
        )
    else:
        now = ticket.prepared_at - timedelta(seconds=1)
    with pytest.raises(PlanCompositionUnavailable):
        compose((ticket, evidence, policy, now))


def test_constraints_and_exclusions_do_not_leave_generic_creative() -> None:
    values = ready(constraints=("Customer must clarify geographic scope",))
    doc = compose(values)
    assert doc.creative_composition is not None and not doc.creative_composition.proposals
    assert not doc.briefs and all(a.kind != "creative_review" for a in doc.actions)
    original = ready()
    keys = tuple(
        target.canonical_entity_key
        for catalog in original[1].reporting.selected.catalogs
        for target in targets(catalog)
        if target.kind == "campaign"
    )
    excluded = compose(ready(excluded_entity_keys=keys))
    assert excluded.creative_composition is not None
    assert not excluded.creative_composition.proposals and not excluded.briefs


def test_complete_action_capacity_fails_instead_of_dropping_proposal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.planning_documents import selected_composer

    values = ready()
    complete = compose(values)
    monkeypatch.setattr(selected_composer, "MAX_ACTIONS", len(complete.actions) - 1)
    with pytest.raises(PlanCompositionUnavailable, match="capacity"):
        compose(values)


def test_genuine_google_v5_preserves_positive_selected_traffic() -> None:
    from app.planning_documents.creative_basis import CreativeInputV1

    from tests.test_selected_paired_composer import ready as reporting_ready

    original, paired, _ = reporting_ready("10")
    requested = CreativeInputV1()
    policy = canonical_creative_policy()
    inputs = PlanInputRevision.model_validate(
        original.inputs.model_copy(update={"creative": requested})
    )
    ticket = GenerationTicket.model_validate(
        {
            **original.model_dump(),
            "operation_id": "f" * 32,
            "inputs": inputs,
            "policy_version": policy.version,
            "policy_digest": policy.digest(),
        }
    )
    contexts = tuple(
        ContextEvidence(
            reference=item.reference.model_copy(
                update={
                    "document_digest": document.digest(),
                    "source_binding_digest": document.digest(),
                }
            ),
            document=document,
        )
        for item in paired.selected.context
        for document in (inputs if item.reference.kind == "customer_context" else policy,)
    )
    selected = SelectedPlanEvidenceBundleV1.model_validate(
        paired.selected.model_copy(
            update={
                "operation_id": ticket.operation_id,
                "input_digest": inputs.digest(),
                "context": contexts,
            }
        )
    )
    reporting = SelectedPairedEvidenceV1.model_validate(
        paired.model_copy(update={"selected": selected})
    )
    basis = CreativeBasisV1(
        workspace_id=inputs.workspace_id,
        goal_currency=inputs.goal.definition.target_window.currency,
        privacy_revision=ticket.privacy_revision,
        requested=requested,
        images=(),
    )
    envelope = CreativePairedEvidenceV1(
        reporting=reporting,
        creative=CollectedCreativeBasisV1(basis=basis, rows=(), ticket_digest=ticket.digest()),
    )
    doc = compose((ticket, envelope, policy, selected.collected_at + timedelta(seconds=1)))
    assert doc.selected_reporting_proof == paired.selected.reporting_proof
    text = doc.model_dump_json().lower()
    assert "spend without conversions" not in text
    assert "100 observed clicks" in doc.actions[0].rationale
    assert "100 USD observed spend" in doc.actions[0].rationale
    assert "Observed zero selected conversions" not in doc.actions[0].rationale
    assert doc.actions[0].kind == "retain"
    assert {item.reference.key for item in paired.traffic} <= set(doc.actions[0].evidence_keys)
    assert doc.creative_composition is not None and not doc.creative_composition.proposals


@pytest.mark.parametrize("bad", [None, True, "2026-10-01T00:00:00Z"])
def test_generation_time_requires_datetime(bad: Any) -> None:
    ticket, evidence, policy, _ = ready()
    with pytest.raises(PlanCompositionUnavailable, match="generation time"):
        compose((ticket, evidence, policy, bad))


def test_explicit_missing_product_is_retained_and_deferred() -> None:
    from app.planning_documents.creative_basis import CreativeInputV1

    doc = compose(ready(images=0, creative=CreativeInputV1()))
    assert doc.creative_proof is not None
    assert doc.creative_proof.basis.requested == CreativeInputV1()
    assert doc.creative_composition is not None and not doc.creative_composition.proposals
    assert any("product information missing" in line for line in doc.section_limitations)


def test_image_generation_bounds_use_instants_across_dst_fold() -> None:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from app.planning_documents.creative_plan_bundle import assert_creative_collection_time

    ticket, evidence, _, _ = ready()
    zone = ZoneInfo("America/New_York")
    ticket = GenerationTicket.model_validate(
        ticket.model_copy(
            update={
                "prepared_at": datetime(2026, 11, 1, 1, 0, tzinfo=zone, fold=0),
            }
        )
    )
    image = evidence.creative.basis.images[0].model_copy(
        update={
            "created_at": ticket.prepared_at,
            "observed_at": datetime(2026, 11, 1, 1, 30, tzinfo=zone, fold=1),
        }
    )
    collection = CollectedCreativeBasisV1.model_validate(
        evidence.creative.model_copy(
            update={
                "ticket_digest": ticket.digest(),
                "basis": evidence.creative.basis.model_copy(update={"images": (image,)}),
                "rows": (evidence.creative.rows[0].model_copy(update={"witness": image}),),
            }
        )
    )
    with pytest.raises(ValueError, match="predates"):
        assert_creative_collection_time(
            collection, ticket, datetime(2026, 11, 1, 1, 45, tzinfo=zone, fold=0)
        )
    assert_creative_collection_time(
        collection, ticket, datetime(2026, 11, 1, 1, 45, tzinfo=zone, fold=1)
    )
