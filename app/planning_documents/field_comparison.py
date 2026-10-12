"""Pure normalized-field comparison; no provider qualification or runtime authority."""

from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from app.planning_documents.common import Digest, Frozen, Id, Title
from app.planning_documents.context import TargetRef
from app.planning_documents.documents import PlanVersion
from app.planning_documents.events import (
    FieldComparison,
    ObservationEvidence,
    ReadObservedStatus,
    VersionBinding,
)
from app.planning_documents.fields import ProposedField, SupportedValue, TargetingValue

SCHEMA: Literal["inlet.planning-field-facts.v1"] = "inlet.planning-field-facts.v1"
LIMITATIONS = (
    "Comparison covers only supported proposed fields, not the entire action or campaign.",
    "Values are compared exactly; no URL, country-order or delivery-status "
    "normalization is inferred.",
    "A match does not verify implementation, who changed a setting, or when it changed.",
    "Observation intervals are not atomic snapshots and do not establish delivery or causal lift.",
)


class FieldFactsV1(Frozen):
    schema_version: Literal["inlet.planning-field-facts.v1"] = SCHEMA
    target: TargetRef
    extraction_contract: Title
    observation_started_at: AwareDatetime
    observed_at: AwareDatetime
    expires_at: AwareDatetime
    values: tuple[SupportedValue, ...] = Field(max_length=3)

    @model_validator(mode="after")
    def bounded_facts(self) -> "FieldFactsV1":
        if not self.observation_started_at <= self.observed_at < self.expires_at:
            raise ValueError("ordered field observation required")
        if len({v.field for v in self.values}) != len(self.values):
            raise ValueError("duplicate observed field")
        if any(
            isinstance(v, TargetingValue) and len(set(v.value)) != len(v.value) for v in self.values
        ):
            raise ValueError("duplicate observed country")
        return self


class FieldSnapshotV1(Frozen):
    facts: FieldFactsV1
    evidence: ObservationEvidence

    @model_validator(mode="after")
    def exact_snapshot(self) -> "FieldSnapshotV1":
        source = self.evidence.source
        if (
            source.document_schema != SCHEMA
            or source.document_digest != self.facts.digest()
            or self.evidence.target != self.facts.target
            or source.observation_started_at != self.facts.observation_started_at
            or source.observed_at != self.facts.observed_at
            or source.expires_at != self.facts.expires_at
        ):
            raise ValueError("field snapshot digest, target or interval mismatch")
        return self


class ComparisonAdmissionV1(Frozen):
    """Caller-supplied pure context, never an authorization or qualification token."""

    binding: VersionBinding
    event_id: Id
    compared_at: AwareDatetime
    privacy_revision: int = Field(strict=True, ge=0)
    source_binding_digest: Digest
    extraction_contract: Title


def _same_target(left: TargetRef, right: TargetRef) -> bool:
    # Fresh selection/name/evidence keys are snapshot-specific, not stable identity.
    return (
        left.account == right.account
        and left.provider_reference == right.provider_reference
        and left.canonical_entity_key == right.canonical_entity_key
        and left.kind == right.kind
        and left.budget_owner_key == right.budget_owner_key
    )


def compare_fields(
    document: PlanVersion,
    admission: ComparisonAdmissionV1,
    snapshot: FieldSnapshotV1 | None,
) -> ReadObservedStatus:
    """Compare synthetic or independently admitted facts, without acquiring/persisting them.

    Runtime callers must establish original-session, ownership, paid-access, source
    authenticity/extraction, current privacy and final commit authority separately.
    No application route or qualified producer currently calls this function.
    """
    document = PlanVersion.model_validate(document)
    admission = ComparisonAdmissionV1.model_validate(admission)
    admission.binding.assert_document(document)
    if admission.compared_at < document.generated_at:
        raise ValueError("comparison predates plan")
    action = next(a for a in document.actions if a.key == admission.binding.action_key)
    proposals = tuple(p for p in action.proposed_fields if isinstance(p, ProposedField))
    for proposal in proposals:
        if isinstance(proposal.proposed, TargetingValue) and len(
            set(proposal.proposed.value)
        ) != len(proposal.proposed.value):
            raise ValueError("duplicate proposed country")
    if snapshot is not None:
        snapshot = FieldSnapshotV1.model_validate(snapshot)
        source = snapshot.evidence.source
        if (
            not isinstance(action.target, TargetRef)
            or not _same_target(action.target, snapshot.facts.target)
            or source.workspace_id != admission.binding.workspace_id
            or source.privacy_revision != admission.privacy_revision
            or source.source_binding_digest != admission.source_binding_digest
            or snapshot.facts.extraction_contract != admission.extraction_contract
            or not document.generated_at
            <= source.observation_started_at
            <= source.observed_at
            <= admission.compared_at
            < source.expires_at
        ):
            raise ValueError("field comparison source, identity or admission mismatch")
    values = {v.field: v for v in snapshot.facts.values} if snapshot is not None else {}
    comparisons = tuple(
        FieldComparison(
            proposal_key=p.key,
            expected=p.proposed,
            observed=values.get(p.proposed.field),
            evidence=(snapshot.evidence if snapshot and p.proposed.field in values else None),
            unavailable_reason=(
                None
                if p.proposed.field in values
                else "No independently admitted observation is available for this proposed field."
            ),
        )
        for p in proposals
    )
    observed = tuple(c for c in comparisons if c.observed is not None)
    status: Literal["matching", "partial", "conflicting", "unavailable"] = (
        "unavailable"
        if not observed
        else "conflicting"
        if any(c.expected != c.observed for c in observed)
        else "partial"
        if len(observed) < len(comparisons)
        else "matching"
    )
    extra = (
        ("Unsupported proposed fields were not compared; their original limitations still apply.",)
        if len(proposals) != len(action.proposed_fields)
        else ()
    )
    result = ReadObservedStatus(
        **admission.binding.model_dump(),
        event_id=admission.event_id,
        observed_at=admission.compared_at,
        status=status,
        comparisons=comparisons,
        limitations=(*LIMITATIONS, *extra),
    )
    result.assert_document(document)
    return result
