"""Complete immutable creative commitment; no current media/paid/byte authority."""

from collections.abc import Sequence

from app.planning_documents.creative_inputs import (
    CREATIVE_GENERATOR_VERSION,
    CREATIVE_POLICY_VERSION,
)
from app.planning_documents.documents import PlanVersion
from app.planning_documents.models import PlanDependencyRow
from app.planning_documents.retained_sources import RetainedSourceWitness, _row
from app.shopify.security import utc


def creative_local_witness(document: PlanVersion) -> RetainedSourceWitness:
    document = PlanVersion.model_validate(document)
    if (document.policy_version, document.generator_version) != (
        CREATIVE_POLICY_VERSION,
        CREATIVE_GENERATOR_VERSION,
    ) or document.creative_proof is None:
        raise ValueError("exact creative document required")
    return _creative_local_witness(document)


def _creative_local_witness(document: PlanVersion) -> RetainedSourceWitness:
    from app.planning_documents.selected_policy_contract import selected_policy_contract

    document = PlanVersion.model_validate(document)
    if (
        not selected_policy_contract(
            document.policy_version, document.generator_version
        ).requires_creative
        or document.creative_proof is None
    ):
        raise ValueError("exact creative document required")
    proof = document.creative_proof
    proof.assert_inputs(document.inputs, document.evidence[0].privacy_revision)
    return RetainedSourceWitness(
        workspace_id=document.inputs.workspace_id,
        plan_id=document.inputs.plan_id,
        version=document.version,
        evidence_key="local:creative:basis",
        account_id=None,
        connection_id=None,
        store_id=None,
        kind="local_creative_basis_v1",
        source_binding_digest=proof.source_binding_digest(),
        document_digest=proof.digest(),
        source_revision=proof.schema_version,
        observed_at=document.generated_at,
        expires_at=document.valid_until,
        privacy_revision=proof.basis.privacy_revision,
    )


def _validate_creative_local_dependency(
    document: PlanVersion, dependencies: Sequence[PlanDependencyRow]
) -> None:
    expected = _creative_local_witness(document).model_dump()
    expected["observed_at"] = utc(expected["observed_at"])
    expected["expires_at"] = utc(expected["expires_at"])
    matches = [
        row
        for row in dependencies
        if row.evidence_key == "local:creative:basis" or row.kind == "local_creative_basis_v1"
    ]
    if len(matches) != 1 or _row(matches[0]) != expected:
        raise ValueError("complete original creative dependency required")


def validate_creative_local_dependency(
    document: PlanVersion, dependencies: Sequence[PlanDependencyRow]
) -> None:
    creative_local_witness(document)
    _validate_creative_local_dependency(document, dependencies)
