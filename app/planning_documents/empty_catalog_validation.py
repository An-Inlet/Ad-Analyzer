"""Immutable empty-query joins and exact collected evidence; no runtime authority."""

from datetime import datetime
from typing import Any

from app.planning_documents.actions import ManualAction
from app.planning_documents.catalog_evidence import CatalogEvidence
from app.planning_documents.context import AccountTarget, EvidenceRef, PlanInputRevision
from app.planning_documents.creative_plan_document import creative_instant
from app.planning_documents.creative_production_contracts import CreativeProposalV1
from app.planning_documents.empty_catalog_contracts import (
    EmptyDeclaredCatalogWitnessV1,
    _strict_originals,
)
from app.planning_documents.source_contracts import SourceFence


def _reference_values(reference: EvidenceRef) -> dict[str, Any]:
    values = reference.model_dump(mode="json")
    for field in ("observation_started_at", "observed_at", "expires_at"):
        values[field] = creative_instant(getattr(reference, field)).isoformat()
    if reference.reporting_window is not None:
        values["reporting_window"] = {
            "starts_at": creative_instant(reference.reporting_window.starts_at).isoformat(),
            "ends_at_exclusive": creative_instant(
                reference.reporting_window.ends_at_exclusive
            ).isoformat(),
        }
    return values


def validate_empty_catalog_proposals(
    *,
    inputs: PlanInputRevision,
    proposals: tuple[CreativeProposalV1, ...],
    actions: tuple[ManualAction, ...],
    evidence: tuple[EvidenceRef, ...],
    sources: tuple[SourceFence, ...],
    generated_at: datetime,
    valid_until: datetime,
    privacy_revision: int,
) -> None:
    checked = tuple(CreativeProposalV1.model_validate(p) for p in proposals)
    empty = tuple(p for p in checked if p.target_basis == "observed_empty_account")
    if not empty:
        return
    inputs = PlanInputRevision.model_validate(inputs)
    actions = tuple(ManualAction.model_validate(a) for a in actions)
    _strict_originals(evidence)
    evidence = tuple(EvidenceRef.model_validate(e) for e in evidence)
    sources = tuple(SourceFence.model_validate(s) for s in sources)
    source_accounts = [s.account.account_id for s in sources]
    if (
        type(privacy_revision) is not int
        or privacy_revision < 0
        or len(set(source_accounts)) != len(source_accounts)
        or {s.account for s in sources} != set(inputs.accounts)
        or any(s.privacy_revision != privacy_revision for s in sources)
        or inputs.total_ceiling_micros != 0
        or inputs.creative is None
        or inputs.creative.product is None
        or not inputs.creative.media_selections
        or not inputs.maximum_creative_assets
        or len(checked) > inputs.maximum_creative_assets
        or inputs.constraints
    ):
        raise ValueError("empty-query preparation requires exact zero-budget creative inputs")
    generated, until = creative_instant(generated_at), creative_instant(valid_until)
    for proposal in empty:
        witness = proposal.empty_catalog_witness
        assert witness is not None  # Validated discriminator requires a complete witness.
        ref = witness.catalog_evidence.reference
        account = ref.account
        if account is None or account not in inputs.accounts:
            raise ValueError("empty-query preparation requires the exact owned account")
        matching_refs = tuple(e for e in evidence if e.key == ref.key)
        matching_sources = tuple(s for s in sources if s.account == account)
        if (
            len(matching_refs) != 1
            or _reference_values(matching_refs[0]) != _reference_values(ref)
            or len(matching_sources) != 1
            or matching_sources[0].source_binding_digest != ref.source_binding_digest
            or matching_sources[0].source_revision != ref.source_revision
            or ref.privacy_revision != privacy_revision
            or ref.workspace_id != inputs.workspace_id
            or ref.reporting_window is None
            or creative_instant(ref.reporting_window.starts_at)
            != creative_instant(inputs.reporting_window.starts_at)
            or creative_instant(ref.reporting_window.ends_at_exclusive)
            != creative_instant(inputs.reporting_window.ends_at_exclusive)
            or not creative_instant(ref.observed_at) <= generated < until
            or until > creative_instant(ref.expires_at)
        ):
            raise ValueError("empty-query preparation requires exact retained source evidence")
        prerequisites = tuple(a for a in actions if a.key == witness.prerequisite_action_key)
        if (
            len(prerequisites) != 1
            or not isinstance(prerequisites[0].target, AccountTarget)
            or prerequisites[0].target != proposal.action.target
            or prerequisites[0].kind != "investigate"
            or prerequisites[0].native_budget is not None
            or prerequisites[0].proposed_fields
            or ref.key not in prerequisites[0].evidence_keys
            or proposal.action.prerequisites != (prerequisites[0].key,)
        ):
            raise ValueError("empty-query preparation requires its exact measurement prerequisite")


def assert_empty_catalog_bindings(
    proposals: tuple[CreativeProposalV1, ...], catalogs: tuple[CatalogEvidence, ...]
) -> None:
    checked = tuple(CreativeProposalV1.model_validate(p) for p in proposals)
    empty = tuple(p for p in checked if p.target_basis == "observed_empty_account")
    if not empty:
        return
    actual = tuple((c, CatalogEvidence.model_validate(c)) for c in catalogs)
    for proposal in empty:
        witness = proposal.empty_catalog_witness
        assert witness is not None
        expected = witness.catalog_evidence
        matching = tuple(
            c
            for c, validated in actual
            if validated.reference.account == expected.reference.account
        )
        if len(matching) != 1:
            raise ValueError("empty catalog witness differs from actual collected evidence")
        actual_witness = EmptyDeclaredCatalogWitnessV1(
            catalog_evidence=matching[0], prerequisite_action_key=witness.prerequisite_action_key
        )
        # JSON retains original offset encodings and every committed field. Python
        # datetime equality alone can equate distinct instants in a repeated hour.
        if actual_witness.catalog_evidence.model_dump(mode="json") != expected.model_dump(
            mode="json"
        ):
            raise ValueError("empty catalog witness differs from actual collected evidence")
