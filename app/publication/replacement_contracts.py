"""Explicit original-request closure and funded transitional reservation replacement.

These are server evidence ports, never customer authority or inferred native bounds.
Existing v1 optimization plan/request serialization remains unchanged.
"""

from datetime import datetime, timedelta
from typing import Literal, Protocol

from pydantic import AwareDatetime, Field, model_validator
from sqlalchemy.orm import Session

from app.goals.schemas import StrictModel
from app.publication.contracts import fingerprint
from app.publication.execution_contracts import (
    Environment,
    ExecutionAccount,
    ExposureEvidence,
    NormalizedProviderReceipt,
    ProviderMandateBinding,
)
from app.publication.optimization_contracts import OptimizationIntent, OptimizationState
from app.publication.optimization_execution_contracts import (
    OptimizationExecutionReview,
    OptimizationPlan,
    OptimizationQualification,
)
from app.publication.provider_contracts import Digest, Id


class ReservationAncestor(StrictModel):
    reservation_id: Id
    state: Literal["held", "superseded"]
    amount_micros: int = Field(strict=True, ge=0)
    evidence_digest: Digest
    replacement_audit_id: Id | None
    replacement_audit_digest: Digest | None

    @model_validator(mode="after")
    def paired_link(self) -> "ReservationAncestor":
        if (self.replacement_audit_id is None) != (self.replacement_audit_digest is None):
            raise ValueError("complete immutable replacement link required")
        return self


class ReplacementSnapshot(StrictModel):
    schema_version: Literal["inlet.replacement-snapshot.v1"] = "inlet.replacement-snapshot.v1"
    workspace_id: int = Field(strict=True, gt=0)
    predecessor_id: Id
    ledger_id: Id
    environment: Environment
    account: ExecutionAccount
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    period_start: AwareDatetime
    period_end: AwareDatetime
    accounting_account_set_digest: Digest
    budget_owner_key: str = Field(min_length=1, max_length=256)
    target_set_digest: Digest
    ancestry: list[ReservationAncestor] = Field(min_length=1, max_length=32)
    run_ids: list[Id] = Field(min_length=1, max_length=128)
    receipts: list[NormalizedProviderReceipt] = Field(min_length=1, max_length=256)
    spent_high_water_micros: int = Field(strict=True, ge=0)
    action_count: int = Field(strict=True, ge=0)
    positive_changes_micros: int = Field(strict=True, ge=0)

    @model_validator(mode="after")
    def lineage(self) -> "ReplacementSnapshot":
        if (
            self.workspace_id != self.account.workspace_id
            or self.period_start >= self.period_end
            or self.ancestry[-1].reservation_id != self.predecessor_id
            or self.ancestry[-1].state != "held"
            or any(a.state != "superseded" for a in self.ancestry[:-1])
            or self.ancestry[0].replacement_audit_id is not None
            or any(a.replacement_audit_id is None for a in self.ancestry[1:])
            or len({a.reservation_id for a in self.ancestry}) != len(self.ancestry)
            or len(set(self.run_ids)) != len(self.run_ids)
            or len({r.attempt_id for r in self.receipts}) != len(self.receipts)
            or any(
                r.account != self.account
                or r.environment != self.environment
                or r.run_id not in self.run_ids
                or r.budget_owner_key != self.budget_owner_key
                or r.purpose != "existing_campaign_optimize"
                or r.outcome not in {"verified_target_state", "verified_no_effect"}
                for r in self.receipts
            )
        ):
            raise ValueError("complete resolved same-owner optimization lineage required")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class ClosedOriginalRequest(StrictModel):
    attempt_id: Id
    request_digest: Digest
    fence: Id
    basis: Literal["authoritative_request_terminal", "authoritative_later_effect_impossible"]
    evidence_digest: Digest


class ReplacementEvidence(StrictModel):
    schema_version: Literal["inlet.replacement-evidence.v1"] = "inlet.replacement-evidence.v1"
    snapshot_digest: Digest
    intent_digest: Digest
    environment: Environment
    qualification_profile: str = Field(min_length=1, max_length=80)
    qualification_revision: int = Field(strict=True, ge=1)
    proof_kind: Literal["qualified_transition", "contract_scenario"]
    observed_at: AwareDatetime
    expires_at: AwareDatetime
    closed_requests: list[ClosedOriginalRequest] = Field(min_length=1, max_length=256)
    closure_evidence_digest: Digest
    transition_evidence_digest: Digest
    transition_semantics: Literal["current_proposed_delayed_no_effect_and_residual"]
    portfolio: ExposureEvidence
    unresolved: list[str] = Field(max_length=32)

    @model_validator(mode="after")
    def bounded(self) -> "ReplacementEvidence":
        if (
            not self.observed_at < self.expires_at <= self.observed_at + timedelta(minutes=5)
            or self.environment != self.portfolio.environment
            or (self.environment == "live" and self.proof_kind == "contract_scenario")
            or len({c.attempt_id for c in self.closed_requests}) != len(self.closed_requests)
            or self.unresolved
        ):
            raise ValueError("qualified bounded original closure and transition proof required")
        return self

    def bind(self, snapshot: ReplacementSnapshot, intent: OptimizationIntent) -> None:
        expected = {(r.attempt_id, r.request_digest, r.fence) for r in snapshot.receipts}
        actual = {(r.attempt_id, r.request_digest, r.fence) for r in self.closed_requests}
        if (
            self.snapshot_digest != snapshot.digest()
            or self.intent_digest != intent.digest()
            or self.environment != snapshot.environment
            or actual != expected
            or self.portfolio.account != snapshot.account
            or self.portfolio.budget_owner_key != snapshot.budget_owner_key
            or self.portfolio.target_set_digest != snapshot.target_set_digest
            or self.portfolio.mandate != intent.mandate
            or self.portfolio.currency != snapshot.currency
            or (self.portfolio.period_start, self.portfolio.period_end)
            != (snapshot.period_start, snapshot.period_end)
            or self.portfolio.reported_spend_micros < snapshot.spent_high_water_micros
            or any(r.observed_at > self.observed_at for r in snapshot.receipts)
        ):
            raise ValueError("all original ancestor requests and portfolio must bind replacement")


class RepeatOptimizationReview(StrictModel):
    schema_version: Literal["inlet.execution-repeat-optimization-review.v1"] = (
        "inlet.execution-repeat-optimization-review.v1"
    )
    purpose: Literal["existing_campaign_optimize"] = "existing_campaign_optimize"
    plan: OptimizationPlan
    predecessor: ReplacementSnapshot
    replacement: ReplacementEvidence

    @model_validator(mode="after")
    def exact(self) -> "RepeatOptimizationReview":
        self.replacement.bind(self.predecessor, self.plan.intent)
        if self.plan.exposure != self.replacement.portfolio:
            raise ValueError("exact reviewed transitional reservation required")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class ReplacementAuditDocument(StrictModel):
    schema_version: Literal["inlet.reservation-replacement.v1"] = "inlet.reservation-replacement.v1"
    predecessor_id: Id
    successor_id: Id
    successor_run_id: Id
    review_id: Id
    review_digest: Digest
    snapshot: ReplacementSnapshot
    evidence: ReplacementEvidence
    actor: Id
    replaced_at: AwareDatetime

    @model_validator(mode="after")
    def scoped(self) -> "ReplacementAuditDocument":
        if (
            self.predecessor_id != self.snapshot.predecessor_id
            or self.predecessor_id == self.successor_id
            or self.evidence.snapshot_digest != self.snapshot.digest()
        ):
            raise ValueError("exact reservation replacement chain required")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class ReplacementReader(Protocol):
    def __call__(
        self,
        db: Session,
        binding: ProviderMandateBinding,
        intent: OptimizationIntent,
        before: OptimizationState,
        qualification: OptimizationQualification,
        snapshot: ReplacementSnapshot,
        now: datetime,
        /,
    ) -> ReplacementEvidence: ...


OptimizationReview = OptimizationExecutionReview | RepeatOptimizationReview


def parse_review(raw: dict[str, object]) -> OptimizationReview:
    if raw.get("schema_version") == "inlet.execution-repeat-optimization-review.v1":
        return RepeatOptimizationReview.model_validate(raw)
    return OptimizationExecutionReview.model_validate(raw)
