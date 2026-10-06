"""Optional trusted server source ports; fields alone do not qualify native guarantees."""

from datetime import datetime, timedelta
from typing import Literal, Protocol

from pydantic import AwareDatetime, Field, model_validator

from app.goals.schemas import StrictModel
from app.publication.contracts import fingerprint
from app.publication.execution_contracts import (
    Environment,
    ExposureEvidence,
    ProviderMandateBinding,
)
from app.publication.optimization_contracts import OptimizationIntent, OptimizationState
from app.publication.optimization_execution_contracts import OptimizationQualification
from app.publication.provider_contracts import Digest
from app.publication.replacement_contracts import ReplacementSnapshot


class TransitionSourceRequest(StrictModel):
    binding: ProviderMandateBinding
    intent: OptimizationIntent
    before: OptimizationState
    qualification: OptimizationQualification
    snapshot: ReplacementSnapshot

    def digest(self) -> str:
        return fingerprint("inlet.transition-source-request.v1", self.model_dump(mode="json"))


class TransitionCertificate(StrictModel):
    request_digest: Digest
    source_profile: str = Field(min_length=1, max_length=80)
    source_revision: int = Field(strict=True, ge=1)
    source_evidence_digest: Digest
    observed_at: AwareDatetime
    expires_at: AwareDatetime
    semantics: Literal["current_proposed_delayed_no_effect_and_residual"]
    portfolio: ExposureEvidence

    @model_validator(mode="after")
    def epoch(self) -> "TransitionCertificate":
        if not self.observed_at < self.expires_at <= self.observed_at + timedelta(minutes=5):
            raise ValueError("bounded immutable source epoch required")
        return self

    def digest(self) -> str:
        return fingerprint("inlet.transition-certificate.v1", self.model_dump(mode="json"))


class TransitionProfile(StrictModel):
    environment: Environment
    qualification_profile: str = Field(min_length=1, max_length=80)
    qualification_revision: int = Field(strict=True, ge=1)
    proof_kind: Literal["qualified_transition", "contract_scenario"]
    cap_semantics: Literal["qualified_native_cap", "qualified_portfolio_bound", "contract_scenario"]
    model_version: str = Field(min_length=1, max_length=80)

    @model_validator(mode="after")
    def simulation_only(self) -> "TransitionProfile":
        if self.environment == "live" and (
            self.proof_kind == "contract_scenario" or self.cap_semantics == "contract_scenario"
        ):
            raise ValueError("contract scenarios cannot qualify live evidence")
        return self


class TransitionCertificateReader(Protocol):
    def __call__(
        self, request: TransitionSourceRequest, now: datetime, /
    ) -> TransitionCertificate: ...
