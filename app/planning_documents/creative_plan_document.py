"""Document-safe creative evidence bindings; no collection or runtime authority."""

from datetime import UTC, datetime
from typing import Any

from pydantic import AwareDatetime, TypeAdapter

from app.planning_documents.actions import CreativeBrief, ManualAction
from app.planning_documents.context import EvidenceRef, PlanInputRevision
from app.planning_documents.creative_basis import _instant
from app.planning_documents.creative_production_contracts import CreativeCompositionV1
from app.planning_documents.creative_retained_proof import CreativeRetainedProofV1


def creative_instant(value: Any) -> datetime:
    return TypeAdapter(AwareDatetime).validate_python(_instant(value)).astimezone(UTC)


def creative_basis_reference(
    proof: CreativeRetainedProofV1, inputs: PlanInputRevision, valid_until: datetime
) -> EvidenceRef:
    proof = CreativeRetainedProofV1.model_validate(proof)
    inputs = PlanInputRevision.model_validate(inputs)
    proof.assert_inputs(inputs, proof.basis.privacy_revision)
    observed = [creative_instant(inputs.created_at)] + [
        creative_instant(image.observed_at) for image in proof.basis.images
    ]
    return EvidenceRef(
        key="creative:basis",
        kind="creative_basis",
        account=None,
        reporting_window=None,
        document_schema=proof.schema_version,
        source_revision=proof.schema_version,
        document_digest=proof.digest(),
        source_binding_digest=proof.source_binding_digest(),
        workspace_id=proof.basis.workspace_id,
        privacy_revision=proof.basis.privacy_revision,
        expires_at=creative_instant(valid_until),
        observation_started_at=min(observed),
        observed_at=max(observed),
        coverage="complete_in_declared_scope",
        declared_scope=(
            "Customer-declared input and owned image bytes observed at recorded times only."
        ),
        reasons=(
            "customer_supplied_claims",
            "visual_assessment_unavailable",
            "production_required",
        ),
        metric_basis=(
            "No measured performance, suitability, rights or continued availability qualification."
        ),
    )


def validate_creative_document(
    *,
    inputs: PlanInputRevision,
    proof: CreativeRetainedProofV1,
    composition: CreativeCompositionV1,
    evidence: tuple[EvidenceRef, ...],
    actions: tuple[ManualAction, ...],
    briefs: tuple[CreativeBrief, ...],
    valid_until: datetime,
) -> None:
    proof = CreativeRetainedProofV1.model_validate(proof)
    composition = CreativeCompositionV1.model_validate(composition)
    proof.assert_inputs(inputs, evidence[0].privacy_revision)
    composition.assert_basis(proof.basis)
    if tuple(ref for ref in evidence if ref.kind == "creative_basis") != (
        creative_basis_reference(proof, inputs, valid_until),
    ):
        raise ValueError("exact single creative basis reference required")
    expected_actions = {p.action.key: p.action for p in composition.proposals}
    expected_briefs = {p.brief.key: p.brief for p in composition.proposals}
    if (
        {a.key: a for a in actions if a.kind == "creative_review"} != expected_actions
        or {b.key: b for b in briefs} != expected_briefs
        or any(p.production.basis_evidence_key != "creative:basis" for p in composition.proposals)
    ):
        raise ValueError("complete exact typed creative actions and briefs required")
    capacity = inputs.maximum_creative_assets
    if len(composition.proposals) > (capacity or 0):
        raise ValueError("creative proposal capacity unavailable or exceeded")
