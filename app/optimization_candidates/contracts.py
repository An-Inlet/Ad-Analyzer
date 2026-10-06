"""Server-owned candidate inputs. None of these documents grants execution authority."""

from datetime import datetime, timedelta
from typing import Literal, Protocol

from pydantic import AwareDatetime, Field, model_validator
from sqlalchemy.orm import Session

from app.goals.schemas import StrictModel
from app.publication.contracts import fingerprint
from app.publication.execution_contracts import (
    Environment,
    ExecutionAccount,
    ProviderMandateBinding,
)
from app.publication.optimization_contracts import (
    OptimizationAction,
    OptimizationState,
    OptimizationTarget,
)
from app.publication.provider_contracts import Digest, Id


class CandidatePolicy(StrictModel):
    schema_version: Literal["inlet.candidate-policy.v1"] = "inlet.candidate-policy.v1"
    workspace_id: int = Field(strict=True, gt=0)
    environment: Environment
    policy_id: Id
    revision: int = Field(strict=True, ge=1)
    rule: Literal["bounded_budget_response_v1"] = "bounded_budget_response_v1"
    budget_step_micros: int | None = Field(default=None, strict=True, gt=0, le=10**15)
    minimum_observations: int | None = Field(default=None, strict=True, gt=0, le=10**9)

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class SourceFence(StrictModel):
    workspace_privacy_revision: int = Field(strict=True, ge=0)
    store_id: Id
    publication_id: Id
    generation: int = Field(strict=True, ge=1)
    privacy_epoch: int = Field(strict=True, ge=1)
    publication_revision: int = Field(strict=True, ge=1)
    source_revision: int = Field(strict=True, ge=0)
    manifest_digest: Digest
    attempt_id: Id | None = None
    receipt_id: Id | None = None
    receipt_sequence: int | None = Field(default=None, strict=True, ge=1)
    receipt_digest: Digest | None = None
    projection_digest: Digest | None = None

    @model_validator(mode="after")
    def complete_receipt(self) -> "SourceFence":
        values = [
            self.attempt_id,
            self.receipt_id,
            self.receipt_sequence,
            self.receipt_digest,
            self.projection_digest,
        ]
        if any(v is not None for v in values) and any(v is None for v in values):
            raise ValueError("complete evidence supersession lineage required")
        return self


class CandidateScope(StrictModel):
    account: ExecutionAccount
    mandate: ProviderMandateBinding
    goal_id: Id
    goal_revision: int = Field(strict=True, ge=1)
    goal_digest: Digest
    target: OptimizationTarget
    budget_owner_key: str = Field(min_length=1, max_length=256)
    target_set_digest: Digest
    source: SourceFence

    def digest(self) -> str:
        return fingerprint("inlet.candidate-scope.v1", self.model_dump(mode="json"))


class CandidateEvidence(StrictModel):
    schema_version: Literal["inlet.candidate-evidence.v1"] = "inlet.candidate-evidence.v1"
    scope_digest: Digest
    source_schema: str = Field(min_length=1, max_length=100)
    source_digest: Digest
    source_reference: Id
    qualification: Literal["unqualified", "contract_scenario", "qualified_learning"]
    qualification_profile: str | None = Field(default=None, min_length=1, max_length=100)
    qualification_revision: int | None = Field(default=None, strict=True, ge=1)
    qualification_digest: Digest | None = None
    direction: Literal["increase", "decrease", "none"]
    observation_count: int | None = Field(default=None, strict=True, ge=0, le=10**9)
    observed_at: AwareDatetime
    expires_at: AwareDatetime

    @model_validator(mode="after")
    def honest(self) -> "CandidateEvidence":
        if not self.observed_at < self.expires_at <= self.observed_at + timedelta(minutes=5):
            raise ValueError("bounded candidate observation lifetime required")
        if self.qualification == "unqualified" and self.direction != "none":
            raise ValueError("unqualified evidence cannot imply measured direction")
        if self.qualification == "qualified_learning" and any(
            v is None
            for v in [
                self.qualification_profile,
                self.qualification_revision,
                self.qualification_digest,
            ]
        ):
            raise ValueError("current server learning qualification reference required")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class CandidateObservation(StrictModel):
    scope: CandidateScope
    state: OptimizationState
    evidence: CandidateEvidence

    @model_validator(mode="after")
    def owned(self) -> "CandidateObservation":
        if (
            self.state.scope != self.scope.account
            or self.state.target != self.scope.target
            or self.state.budget_owner.key(self.scope.account) != self.scope.budget_owner_key
            or self.state.budget_owner.target_set_digest() != self.scope.target_set_digest
            or self.evidence.scope_digest != self.scope.digest()
            or (
                self.scope.mandate.environment == "live"
                and self.evidence.qualification == "contract_scenario"
            )
        ):
            raise ValueError("candidate observation scope or qualification mismatch")
        return self


class CandidateDecision(StrictModel):
    schema_version: Literal["inlet.optimization-candidate.v1"] = "inlet.optimization-candidate.v1"
    scope: CandidateScope
    policy_digest: Digest
    state_digest: Digest
    evidence_digest: Digest
    evidence: CandidateEvidence
    status: Literal["blocked", "no_change", "suggested"]
    reasons: list[str] = Field(min_length=1, max_length=16)
    action: OptimizationAction | None
    observed_at: AwareDatetime
    expires_at: AwareDatetime
    spending_authority: Literal["none"] = "none"
    dispatch_ready: Literal[False] = False
    requires_new_execution_admission: Literal[True] = True

    @model_validator(mode="after")
    def no_authority(self) -> "CandidateDecision":
        if (
            self.evidence.digest() != self.evidence_digest
            or self.evidence.scope_digest != self.scope.digest()
            or (
                self.scope.mandate.environment == "live"
                and self.evidence.qualification == "contract_scenario"
            )
            or (
                self.status == "suggested"
                and (
                    self.evidence.qualification == "unqualified"
                    or self.evidence.direction == "none"
                )
            )
        ):
            raise ValueError("candidate evidence cannot imply unsupported qualification")
        if (self.status == "suggested") != (self.action is not None):
            raise ValueError("only an explicit suggestion may contain a bounded action")
        if self.status == "suggested" and self.expires_at <= self.observed_at:
            raise ValueError("expired evidence cannot yield a current suggestion")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class CandidateWork(StrictModel):
    schema_version: Literal["inlet.candidate-work.v1"] = "inlet.candidate-work.v1"
    purpose: Literal["prepare_suggestion_only"] = "prepare_suggestion_only"
    scope: CandidateScope
    policy: CandidatePolicy

    @model_validator(mode="after")
    def scoped(self) -> "CandidateWork":
        if (
            self.policy.workspace_id != self.scope.account.workspace_id
            or self.policy.environment != self.scope.mandate.environment
        ):
            raise ValueError("candidate policy ownership mismatch")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class CandidateReadPort(Protocol):
    def __call__(
        self, db: Session, scope: CandidateScope, now: datetime, /
    ) -> CandidateObservation:
        """Read-only server source; current production learning adapter is absent."""
        ...
