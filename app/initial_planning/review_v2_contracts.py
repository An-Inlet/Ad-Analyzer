"""New handoff commitments; never rewrite native preview bytes or grant authority."""

from typing import TYPE_CHECKING, Literal

from pydantic import AwareDatetime, ConfigDict, Field, model_validator

from app.initial_planning.contracts import Frozen
from app.publication.contracts import fingerprint
from app.publication.execution_contracts import ProviderMandateBinding
from app.publication.provider_contracts import Digest, Id

if TYPE_CHECKING:
    from app.publication.optimization_execution_contracts import OptimizationQualification


def qualification_commitment(value: "OptimizationQualification") -> str:
    """Commit the full retained qualification envelope, not only its evidence digest."""
    return fingerprint(
        "inlet.initial-preview-execution-qualification.v1", value.model_dump(mode="json")
    )


class FrozenMandateBinding(ProviderMandateBinding):
    model_config = ConfigDict(extra="forbid", frozen=True)


class InitialPreviewExecutionIntentV1(Frozen):
    expected_preview_digest: Digest
    mandate_id: Id
    mandate_revision: int = Field(strict=True, ge=1)

    def digest(self) -> str:
        return fingerprint(
            "inlet.initial-preview-execution-intent.v1", self.model_dump(mode="json")
        )


class InitialPreviewExecutionPreparedV1(Frozen):
    schema_version: Literal["inlet.initial-preview-execution-prepared.v1"] = (
        "inlet.initial-preview-execution-prepared.v1"
    )
    preview_id: Id
    preview_digest: Digest
    review_id: Id
    review_digest: Digest
    plan_digest: Digest
    execution_mandate: FrozenMandateBinding
    status: Literal["review_required"] = "review_required"
    spending_authority: Literal["none"] = "none"


class NativeReviewMatchV1(Frozen):
    schema_version: Literal["inlet.native-review-match.v1"] = "inlet.native-review-match.v1"
    native_observation_digest: Digest
    qualified_state_digest: Digest
    semantic_digest: Digest
    spending_authority: Literal["none"] = "none"

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class InitialPreviewExecutionProofV1(Frozen):
    schema_version: Literal["inlet.initial-preview-execution-proof.v1"] = (
        "inlet.initial-preview-execution-proof.v1"
    )
    workspace_id: int = Field(strict=True, gt=0)
    preview_id: Id
    review_id: Id
    preview_digest: Digest
    profile_digest: Digest
    intent_digest: Digest
    native_observation_digest: Digest
    semantic_match_digest: Digest
    planning_mandate: FrozenMandateBinding
    execution_mandate: FrozenMandateBinding
    qualified_state_digest: Digest
    qualification_digest: Digest
    plan_digest: Digest
    created_at: AwareDatetime
    expires_at: AwareDatetime
    spending_authority: Literal["none"] = "none"

    @model_validator(mode="after")
    def separate_consent_same_ledger(self) -> "InitialPreviewExecutionProofV1":
        if (
            self.planning_mandate.mandate_id == self.execution_mandate.mandate_id
            or self.planning_mandate.consent_id == self.execution_mandate.consent_id
            or self.planning_mandate.ledger_id != self.execution_mandate.ledger_id
            or self.planning_mandate.environment != self.execution_mandate.environment
            or self.created_at >= self.expires_at
        ):
            raise ValueError("invalid separate execution handoff binding")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))
