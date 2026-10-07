"""Strict hash-only historical export; it never asserts current handoff eligibility."""

import json
from collections.abc import Mapping
from typing import Any

from app.initial_planning.review_v2_contracts import InitialPreviewExecutionProofV1
from app.shopify.security import utc


def export_execution_proof(row: Mapping[str, Any]) -> dict[str, Any]:
    raw = row["document"]
    if len(json.dumps(raw, allow_nan=False)) > 16384:
        raise ValueError("execution proof capacity")
    proof = InitialPreviewExecutionProofV1.model_validate(raw)
    if (
        proof.workspace_id != row["workspace_id"]
        or proof.review_id != row["review_id"]
        or proof.digest() != row["digest"]
    ):
        raise ValueError("execution proof ownership mismatch")
    return {
        "review_id": proof.review_id,
        "workspace_id": proof.workspace_id,
        "digest": proof.digest(),
        "document": proof.model_dump(mode="json"),
    }


def bind_execution_proof(
    row: Mapping[str, Any],
    link: Mapping[str, Any],
    preview: Mapping[str, Any],
    review: Mapping[str, Any],
) -> InitialPreviewExecutionProofV1:
    """Strict preinsert commitment check, not original-session/financial authorization."""
    from app.initial_planning.preview_v2 import InitialPreviewV2, PreviewIntentV2
    from app.initial_planning.review_v2_contracts import InitialPreviewExecutionIntentV1
    from app.publication.replacement_contracts import parse_review

    exported = export_execution_proof(row)
    proof = InitialPreviewExecutionProofV1.model_validate(exported["document"])
    value = InitialPreviewV2.model_validate(preview["document"])
    saved_intent = PreviewIntentV2.model_validate(preview["intent"])
    financial = parse_review(review["document"])
    intent = InitialPreviewExecutionIntentV1(
        expected_preview_digest=proof.preview_digest,
        mandate_id=proof.execution_mandate.mandate_id,
        mandate_revision=proof.execution_mandate.revision,
    )
    if (
        proof.intent_digest != intent.digest()
        or proof.intent_digest != link["intent_digest"]
        or proof.execution_mandate.policy_digest != link["mandate_digest"]
        or proof.execution_mandate.consent_id != review["consent_id"]
        or proof.execution_mandate.model_dump() != financial.plan.intent.mandate.model_dump()
        or financial.digest() != review["digest"]
        or financial.plan.digest() != proof.plan_digest
        or financial.plan.before.digest() != proof.qualified_state_digest
        or proof.planning_mandate.policy_digest != preview["mandate_digest"]
        or proof.planning_mandate.mandate_id != saved_intent.mandate_id
        or proof.planning_mandate.revision != saved_intent.mandate_revision
        or value.native_observation is None
        or value.id != proof.preview_id
        or value.digest() != proof.preview_digest
        or preview["document_digest"] != proof.preview_digest
        or value.profile_digest != proof.profile_digest
        or value.native_observation.digest() != proof.native_observation_digest
        or proof.expires_at > value.expires_at
        or proof.expires_at > utc(link["expires_at"])
        or proof.created_at < value.created_at
        or value.environment != proof.execution_mandate.environment
        or value.objective.cohort.workspace_id != proof.workspace_id
        or preview["workspace_id"] != proof.workspace_id
        or link["workspace_id"] != proof.workspace_id
        or link["review_id"] != proof.review_id
        or link["preview_id"] != proof.preview_id
        or link["preview_digest"] != proof.preview_digest
        or link["native_state_digest"] != proof.qualified_state_digest
        or link["plan_digest"] != proof.plan_digest
        or link["environment"] != proof.execution_mandate.environment
        or review["id"] != proof.review_id
        or review["workspace_id"] != proof.workspace_id
        or not review["initial_preview_provenance_required"]
        or review["initial_preview_origin_id"] != proof.preview_id
        or review["digest"] != link["review_digest"]
        or review["plan_digest"] != proof.plan_digest
    ):
        raise ValueError("execution proof parent commitment mismatch")
    return proof
