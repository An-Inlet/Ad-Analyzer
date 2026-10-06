"""Versioned structural selection provenance; never a provider qualification."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, TypeAdapter, model_validator

from app.goals.schemas import StrictModel
from app.optimization_candidates.contracts import CandidatePolicy, CandidateScope, CandidateWork
from app.publication.contracts import fingerprint
from app.publication.provider_contracts import Digest, Id


class CandidatePolicyRef(StrictModel):
    policy_id: Id
    revision: int = Field(strict=True, ge=1)


class SelectionProvenance(StrictModel):
    schema_version: Literal["inlet.candidate-selection.v1"] = "inlet.candidate-selection.v1"
    method: Literal["exact_mandate_native_owner_v1"] = "exact_mandate_native_owner_v1"
    actor_id: Id
    scope_digest: Digest
    policy_digest: Digest
    catalog_digest: Digest
    option_id: Digest
    state_digest: Digest
    manifest_digest: Digest
    observed_at: AwareDatetime
    expires_at: AwareDatetime
    authority: Literal["none"] = "none"

    @model_validator(mode="after")
    def bounded(self) -> "SelectionProvenance":
        if not 0 < (self.expires_at - self.observed_at).total_seconds() <= 300:
            raise ValueError("bounded current selection required")
        return self


class CandidateWorkV2(StrictModel):
    schema_version: Literal["inlet.candidate-work.v2"] = "inlet.candidate-work.v2"
    purpose: Literal["prepare_suggestion_only"] = "prepare_suggestion_only"
    scope: CandidateScope
    policy: CandidatePolicy
    selection: SelectionProvenance

    @model_validator(mode="after")
    def scoped(self) -> "CandidateWorkV2":
        CandidateWork(scope=self.scope, policy=self.policy)
        if (
            self.selection.scope_digest != self.scope.digest()
            or self.selection.policy_digest != self.policy.digest()
        ):
            raise ValueError("selection scope changed")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


CandidateWorkDocument = Annotated[
    CandidateWork | CandidateWorkV2, Field(discriminator="schema_version")
]
WORK_ADAPTER: TypeAdapter[CandidateWork | CandidateWorkV2] = TypeAdapter(CandidateWorkDocument)


def parse_work(value: object) -> CandidateWork | CandidateWorkV2:
    return WORK_ADAPTER.validate_python(value)


class SelectionBlock(StrictModel):
    account_id: int = Field(strict=True, gt=0)
    reason: Literal["approved_owner_unavailable", "contradictory_owner_snapshots"]


class CandidateSelectionBatch(StrictModel):
    schema_version: Literal["inlet.candidate-selection-batch.v1"] = (
        "inlet.candidate-selection-batch.v1"
    )
    workspace_id: int = Field(strict=True, gt=0)
    manifest_digest: Digest
    selected: list[CandidateWorkV2] = Field(max_length=20)
    blocked: list[SelectionBlock] = Field(max_length=20)
    authority: Literal["none"] = "none"

    @model_validator(mode="after")
    def bound_manifest(self) -> "CandidateSelectionBatch":
        identifiers = [w.scope.account.account.account_id for w in self.selected]
        blocked = [b.account_id for b in self.blocked]
        if len(set(identifiers + blocked)) != len(identifiers + blocked) or any(
            w.scope.account.workspace_id != self.workspace_id
            or w.selection.manifest_digest != self.manifest_digest
            for w in self.selected
        ):
            raise ValueError("selection batch scope mismatch")
        return self
