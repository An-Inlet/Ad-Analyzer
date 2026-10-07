"""Customer intent/projection only; candidate selection and evidence stay server-owned."""

from typing import Literal

from pydantic import Field, model_validator

from app.goals.schemas import StrictModel
from app.optimization_candidates.documents import CandidateDecisionDocument
from app.optimization_candidates.selection_contracts import (
    CandidatePolicyRef,
    CandidateSelectionBatch,
)
from app.publication.provider_contracts import Digest, Id
from app.reported_feedback.candidate_contracts import (
    ReportedRuleCandidateV1,
    ReportedRuleSelectionBatchV1,
)
from app.reported_feedback.customer_contracts import ReportedRuleBasisDetailsV1


class CandidateReadIntent(StrictModel):
    mandate_id: Id
    mandate_revision: int = Field(strict=True, ge=1)
    policy: CandidatePolicyRef


class CandidatePolicyOption(StrictModel):
    policy: CandidatePolicyRef
    label: str = Field(min_length=1, max_length=160)


class CandidateMandateOption(StrictModel):
    mandate_id: Id
    revision: int = Field(strict=True, ge=1)
    policy_digest: Digest
    label: str = Field(min_length=1, max_length=160)


class CandidateCapabilities(StrictModel):
    configured: bool
    policies: list[CandidatePolicyOption] = Field(max_length=20)
    mandates: list[CandidateMandateOption] = Field(max_length=20)
    truncated: bool
    automatic_available: Literal[False] = False
    automatic_unavailable_reason: Literal["first_decision_producer_unavailable"] = (
        "first_decision_producer_unavailable"
    )
    spending_authority: Literal["none"] = "none"


class CandidateReadPrepared(StrictModel):
    selection: CandidateSelectionBatch | ReportedRuleSelectionBatchV1
    job_ids: list[Id] = Field(max_length=20)
    spending_authority: Literal["none"] = "none"


class CandidateReadStatus(StrictModel):
    job_id: Id
    state: Literal["pending", "claimed", "completed", "blocked", "canceled"]
    result_id: Id | None
    decision: CandidateDecisionDocument | None
    decision_digest: Digest | None
    basis_details: ReportedRuleBasisDetailsV1 | None = None
    spending_authority: Literal["none"] = "none"

    @model_validator(mode="after")
    def exact_decision_digest(self) -> "CandidateReadStatus":
        expected = self.decision.digest() if self.decision is not None else None
        reported = isinstance(self.decision, ReportedRuleCandidateV1)
        if reported != (self.basis_details is not None):
            raise ValueError("candidate basis details mismatch")
        if isinstance(self.decision, ReportedRuleCandidateV1) and self.basis_details is not None:
            details = self.basis_details
            if (
                details.environment != self.decision.evidence.environment
                or details.nominal_before_micros != self.decision.nominal_before_micros
                or details.nominal_after_micros != self.decision.nominal_after_micros
                or details.observed_at != self.decision.observed_at
                or details.expires_at != self.decision.expires_at
                or details.reported_completion_count
                != self.decision.evidence.reported_completion_count
            ):
                raise ValueError("candidate basis details changed")
        if self.decision_digest != expected:
            raise ValueError("candidate decision digest mismatch")
        return self
