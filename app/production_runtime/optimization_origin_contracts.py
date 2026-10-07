"""Minimal retained origin of a customer-prepared optimization mandate revision."""

from typing import Literal

from pydantic import Field, model_validator

from app.initial_planning.budget_mandate_contracts import Identifier
from app.initial_planning.contracts import Frozen
from app.production_runtime.optimization_policy_contracts import (
    OptimizationCustomerIntentV1,
    OptimizationOperatingPolicyV1,
)
from app.publication.contracts import fingerprint
from app.publication.provider_contracts import Digest, Id


class OptimizationMandatePreparationV1(Frozen):
    schema_version: Literal["inlet.optimization-mandate-preparation.v1"] = (
        "inlet.optimization-mandate-preparation.v1"
    )
    workspace_id: int = Field(strict=True, gt=0)
    mandate_id: Identifier
    mandate_revision: int = Field(strict=True, gt=0)
    environment: Literal["contract_test", "live"]
    provider_policy_digest: Digest
    goal_digest: Digest
    intent: OptimizationCustomerIntentV1
    account_scope_digest: Digest
    target_set_digest: Digest
    inventory_request_digest: Digest
    inventory_digest: Digest
    native_state_digest: Digest
    qualification_id: Id
    qualification_revision: int = Field(strict=True, gt=0)
    qualification_digest: Digest
    evidence_profile_digest: Digest
    operating_policy: OptimizationOperatingPolicyV1
    operating_policy_digest: Digest

    @model_validator(mode="after")
    def exact_policy(self) -> "OptimizationMandatePreparationV1":
        if (
            self.operating_policy.digest() != self.operating_policy_digest
            or self.operating_policy.environment != self.environment
            or self.operating_policy.evidence_profile_digest != self.evidence_profile_digest
        ):
            raise ValueError("exact operating policy origin required")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))
