"""Retained constraint and exact neutral-copy validation for candidate documents."""

from typing import TYPE_CHECKING

from app.planning_documents.constrained_creative import constrained_proposal
from app.planning_documents.context import TargetRef
from app.planning_documents.creative_composition import CreativeCompositionReferencesV1
from app.planning_documents.ports import PlanningCompositionPolicy
from app.planning_documents.selected_plan_contracts import SelectedPlanPinV1

if TYPE_CHECKING:
    from app.planning_documents.documents import PlanVersion


def assert_constraint_capture_provenance(captures: tuple[SelectedPlanPinV1, ...]) -> None:
    if any(pin.observation_provenance is not None for pin in captures) and any(
        pin.observation_provenance is None for pin in captures
    ):
        raise ValueError("v4 typed provenance must cover every selected capture")


def validate_constraint_document(document: "PlanVersion") -> None:
    interpretation = document.constraint_interpretation
    proof, composition = document.creative_proof, document.creative_composition
    if interpretation is None or proof is None or composition is None:
        raise ValueError("complete retained constraint interpretation and creative proof required")
    interpretation.assert_inputs(document.inputs)
    if interpretation.disposition == "unresolved" and composition.proposals:
        raise ValueError("unresolved restrictions cannot produce creative proposals")
    customer = tuple(e for e in document.evidence if e.kind == "customer_context")
    policies = tuple(e for e in document.evidence if e.kind == "planning_policy")
    if len(customer) != 1 or len(policies) != 1:
        raise ValueError("exact original customer and policy evidence required")
    policy = PlanningCompositionPolicy(
        version=document.policy_version, generator_version=document.generator_version
    )
    if (
        customer[0].document_digest != document.inputs.digest()
        or policies[0].document_digest != policy.digest()
    ):
        raise ValueError("original constraint input and policy evidence mismatch")
    refs = CreativeCompositionReferencesV1(
        basis_key="creative:basis",
        basis_digest=proof.basis.digest(),
        customer_key=customer[0].key,
        customer_input_digest=document.inputs.digest(),
        policy_key=policies[0].key,
        policy_digest=policy.digest(),
        policy=policy,
    )
    for proposal in composition.proposals:
        target = proposal.action.target
        if (
            not isinstance(target, TargetRef)
            or not proof.basis.images
            or proof.basis.requested.product is None
        ):
            raise ValueError("constraint production requires existing target and selected image")
        if proposal != constrained_proposal(target, proof.basis, refs, proposal.action.priority):
            raise ValueError("exact constrained public-copy and production obligations required")
