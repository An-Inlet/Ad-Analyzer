"""Independent customer decisions, assertions and observations; no execution state."""

from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from app.planning_documents.common import Digest, Frozen, Id, Key, NoAuthority, Positive, Text
from app.planning_documents.context import EvidenceRef, TargetRef
from app.planning_documents.documents import PlanVersion
from app.planning_documents.fields import ProposedField, SupportedValue


class VersionBinding(NoAuthority):
    workspace_id: Positive
    plan_id: Id
    version: Positive
    document_digest: Digest
    action_key: Key
    action_digest: Digest

    def assert_document(self, document: PlanVersion) -> None:
        self = type(self).model_validate(self)
        document = PlanVersion.model_validate(document)
        action = next((a for a in document.actions if a.key == self.action_key), None)
        if (
            self.workspace_id != document.inputs.workspace_id
            or self.plan_id != document.inputs.plan_id
            or self.version != document.version
            or self.document_digest != document.digest()
            or action is None
            or self.action_digest != action.digest()
        ):
            raise ValueError("exact plan version and action binding required")


class CustomerDecision(VersionBinding):
    event_id: Id
    actor_id: Id
    recorded_at: AwareDatetime
    decision: Literal["accepted_for_manual_application", "rejected", "deferred"]
    reason: Text
    supersedes_event_id: Id | None


class ManualAssertion(VersionBinding):
    event_id: Id
    actor_id: Id
    recorded_at: AwareDatetime
    assertion: Literal["customer_reports_applied", "retracted"]
    reported_applied_at: AwareDatetime | None
    supersedes_event_id: Id | None
    statement: Text
    verification: Literal["customer_report_only"] = "customer_report_only"

    @model_validator(mode="after")
    def ordered(self) -> "ManualAssertion":
        if self.assertion == "customer_reports_applied":
            if self.reported_applied_at is None or self.reported_applied_at > self.recorded_at:
                raise ValueError("nonfuture reported application time required")
        elif self.reported_applied_at is not None or self.supersedes_event_id is None:
            raise ValueError("retraction must refer to earlier assertion")
        if self.event_id == self.supersedes_event_id:
            raise ValueError("event cannot supersede itself")
        return self


class ObservationEvidence(Frozen):
    source: EvidenceRef
    target: TargetRef

    @model_validator(mode="after")
    def owned_native(self) -> "ObservationEvidence":
        if (
            self.source.key != self.target.catalog_evidence_key
            or self.source.kind != "native_catalog"
            or self.source.coverage == "unavailable"
            or self.source.account != self.target.account
        ):
            raise ValueError("observed field needs exact available owned native evidence")
        return self


class FieldComparison(Frozen):
    proposal_key: Key
    expected: SupportedValue
    observed: SupportedValue | None
    evidence: ObservationEvidence | None
    unavailable_reason: Text | None

    @model_validator(mode="after")
    def coherent(self) -> "FieldComparison":
        if self.observed is None:
            if self.unavailable_reason is None:
                raise ValueError("missing field observation reason")
        elif (
            self.evidence is None
            or self.unavailable_reason is not None
            or self.expected.field != self.observed.field
        ):
            raise ValueError("observed field and evidence mismatch")
        return self


class ReadObservedStatus(VersionBinding):
    event_id: Id
    observed_at: AwareDatetime
    status: Literal["matching", "partial", "conflicting", "unavailable"]
    comparisons: tuple[FieldComparison, ...] = Field(max_length=20)
    limitations: tuple[Text, ...] = Field(min_length=1, max_length=20)
    causality: Literal["not_assessed"] = "not_assessed"
    applied_by: None = None

    @model_validator(mode="after")
    def evidence_required(self) -> "ReadObservedStatus":
        keys = [c.proposal_key for c in self.comparisons]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate compared proposal")
        observed = [c for c in self.comparisons if c.observed is not None]
        expected_status = (
            "unavailable"
            if not observed
            else "conflicting"
            if any(c.expected != c.observed for c in observed)
            else "partial"
            if len(observed) != len(self.comparisons)
            else "matching"
        )
        if self.status != expected_status:
            raise ValueError("status must reflect typed comparisons")
        return self

    def assert_document(self, document: PlanVersion) -> None:
        self = type(self).model_validate(self)
        document = PlanVersion.model_validate(document)
        super().assert_document(document)
        action = next(a for a in document.actions if a.key == self.action_key)
        proposals = {p.key: p for p in action.proposed_fields if isinstance(p, ProposedField)}
        if set(proposals) != {c.proposal_key for c in self.comparisons}:
            raise ValueError("compare every supported field on exact action")
        for comparison in self.comparisons:
            if comparison.evidence is not None:
                source, target = comparison.evidence.source, comparison.evidence.target
                if (
                    not isinstance(action.target, TargetRef)
                    or target.account != action.target.account
                    or target.canonical_entity_key != action.target.canonical_entity_key
                    or target.provider_reference != action.target.provider_reference
                    or not document.generated_at
                    <= source.observation_started_at
                    <= source.observed_at
                    <= self.observed_at
                    < source.expires_at
                ):
                    raise ValueError("observation target/source/time mismatch")
            if comparison.expected != proposals[comparison.proposal_key].proposed:
                raise ValueError("comparison expected value differs from proposal")
