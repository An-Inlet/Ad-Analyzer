"""Customer intent/projection only; candidate selection and evidence stay server-owned."""

from typing import Literal

from pydantic import Field, model_validator

from app.goals.schemas import StrictModel
from app.optimization_candidates.contracts import CandidateDecision
from app.optimization_candidates.selection_contracts import (
    CandidatePolicyRef,
    CandidateSelectionBatch,
)
from app.publication.provider_contracts import Digest, Id


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
    selection: CandidateSelectionBatch
    job_ids: list[Id] = Field(max_length=20)
    spending_authority: Literal["none"] = "none"


class CandidateReadStatus(StrictModel):
    job_id: Id
    state: Literal["pending", "claimed", "completed", "blocked", "canceled"]
    result_id: Id | None
    decision: CandidateDecision | None
    decision_digest: Digest | None
    spending_authority: Literal["none"] = "none"

    @model_validator(mode="after")
    def exact_decision_digest(self) -> "CandidateReadStatus":
        expected = self.decision.digest() if self.decision is not None else None
        if self.decision_digest != expected:
            raise ValueError("candidate decision digest mismatch")
        return self
