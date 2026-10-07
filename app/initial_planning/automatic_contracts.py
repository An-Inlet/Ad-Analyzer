"""Initial reported-efficiency rule: explicit operational evidence, never learning proof."""

from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from app.initial_planning.contracts import Frozen, InitialPlanningConfiguration
from app.optimization_candidates.contracts import CandidateScope
from app.optimization_candidates.selection_contracts import SelectionProvenance
from app.publication.contracts import fingerprint
from app.publication.optimization_contracts import MetaBudgetSetV1, MetaCurrentState
from app.publication.provider_contracts import Digest, Id


class Committed(Frozen):
    schema_version: str

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class InitialReportedRulePolicyV1(Committed):
    schema_version: Literal["inlet.initial-reported-rule-policy.v1"] = (
        "inlet.initial-reported-rule-policy.v1"
    )
    workspace_id: int = Field(strict=True, gt=0)
    environment: Literal["contract_test", "live"]
    policy_id: Id
    revision: int = Field(strict=True, gt=0)
    policy_family: Id
    planning_profile_digest: Digest
    initial: InitialPlanningConfiguration
    allowed_operation: Literal["meta_budget_set_v1"]
    maximum_candidate_age_seconds: int = Field(strict=True, ge=1, le=300)

    @model_validator(mode="after")
    def exact(self) -> "InitialReportedRulePolicyV1":
        if self.environment != self.initial.environment:
            raise ValueError("initial policy environment mismatch")
        return self


class InitialObservationReferenceV1(Frozen):
    observation_id: Id
    digest: Digest


class InitialRuleBasisV1(Committed):
    schema_version: Literal["inlet.initial-rule-basis.v1"] = "inlet.initial-rule-basis.v1"
    preview_id: Id
    preview_digest: Digest
    calibration_id: Id
    calibration_digest: Digest
    selected_observation_id: Id
    objective_digest: Digest
    goal_digest: Digest
    observation_references: tuple[InitialObservationReferenceV1, ...] = Field(
        min_length=1, max_length=128
    )
    opportunity_id: Id
    semantic_key_digest: Digest

    @model_validator(mode="after")
    def complete(self) -> "InitialRuleBasisV1":
        ids = [ref.observation_id for ref in self.observation_references]
        if ids != sorted(set(ids)) or self.selected_observation_id not in ids:
            raise ValueError("unique sorted complete initial observation references required")
        if self.opportunity_id != self.semantic_key_digest[:32]:
            raise ValueError("stable full opportunity commitment required")
        return self


class InitialReportedRuleWorkV1(Committed):
    schema_version: Literal["inlet.initial-reported-rule-work.v1"] = (
        "inlet.initial-reported-rule-work.v1"
    )
    purpose: Literal["prepare_suggestion_only"] = "prepare_suggestion_only"
    scope: CandidateScope
    policy: InitialReportedRulePolicyV1
    selection: SelectionProvenance
    basis: InitialRuleBasisV1

    @model_validator(mode="after")
    def owned(self) -> "InitialReportedRuleWorkV1":
        if (
            self.scope.account.account.platform != "meta_ads"
            or self.scope.target.kind != "campaign"
            or self.scope.source.attempt_id is not None
            or self.policy.workspace_id != self.scope.account.workspace_id
            or self.policy.environment != self.scope.mandate.environment
            or self.selection.scope_digest != self.scope.digest()
            or self.selection.policy_digest != self.policy.digest()
            or self.basis.goal_digest != self.scope.goal_digest
        ):
            raise ValueError("exact initial rule scope without invented prior action required")
        return self


class InitialReportedRuleEvidenceV1(Committed):
    schema_version: Literal["inlet.initial-reported-rule-evidence.v1"] = (
        "inlet.initial-reported-rule-evidence.v1"
    )
    scope_digest: Digest
    environment: Literal["contract_test", "live"]
    source_schema: Literal["inlet.initial-reported-efficiency-rule.v1"] = (
        "inlet.initial-reported-efficiency-rule.v1"
    )
    source_reference: Id
    basis: InitialRuleBasisV1
    rule_policy_digest: Digest
    direction: Literal["increase", "decrease", "none"]
    signed_delta_micros: int = Field(strict=True, ge=-(10**15), le=10**15)
    training_windows: int = Field(strict=True, ge=0, le=128)
    holdout_windows: int = Field(strict=True, ge=0, le=128)
    observed_at: AwareDatetime
    expires_at: AwareDatetime
    interpretation: Literal["initial_reported_efficiency_rule"] = "initial_reported_efficiency_rule"
    correction_status: Literal["as_observed_unsettled"] = "as_observed_unsettled"
    empirical_qualification: Literal[False] = False
    causal_lift: Literal["unavailable"] = "unavailable"
    delivery_time: Literal["unavailable"] = "unavailable"
    spending_authority: Literal["none"] = "none"

    @model_validator(mode="after")
    def honest(self) -> "InitialReportedRuleEvidenceV1":
        wanted = (
            "increase"
            if self.signed_delta_micros > 0
            else "decrease"
            if self.signed_delta_micros < 0
            else "none"
        )
        if (
            self.source_reference != self.basis.opportunity_id
            or self.direction != wanted
            or not 0 < (self.expires_at - self.observed_at).total_seconds() <= 300
        ):
            raise ValueError("bounded operational initial direction required")
        return self


class InitialReportedRuleObservationV1(Frozen):
    scope: CandidateScope
    state: MetaCurrentState
    evidence: InitialReportedRuleEvidenceV1

    @model_validator(mode="after")
    def owned(self) -> "InitialReportedRuleObservationV1":
        if (
            self.state.scope != self.scope.account
            or self.state.target != self.scope.target
            or self.scope.target.kind != "campaign"
            or self.state.budget_owner.owner != self.state.target
            or self.state.budget_owner.key(self.scope.account) != self.scope.budget_owner_key
            or self.state.budget_owner.target_set_digest() != self.scope.target_set_digest
            or self.evidence.scope_digest != self.scope.digest()
            or self.evidence.environment != self.scope.mandate.environment
        ):
            raise ValueError("whole owned initial campaign budget required")
        return self


class InitialReportedRuleCandidateV1(Committed):
    schema_version: Literal["inlet.initial-reported-rule-candidate.v1"] = (
        "inlet.initial-reported-rule-candidate.v1"
    )
    scope: CandidateScope
    policy_digest: Digest
    state_digest: Digest
    evidence_digest: Digest
    evidence: InitialReportedRuleEvidenceV1
    status: Literal["blocked", "no_change", "suggested"]
    reasons: tuple[str, ...] = Field(min_length=1, max_length=16)
    action: MetaBudgetSetV1 | None
    nominal_before_micros: int = Field(strict=True, gt=0, le=10**15)
    nominal_after_micros: int | None = Field(default=None, strict=True, gt=0, le=10**15)
    observed_at: AwareDatetime
    expires_at: AwareDatetime
    spending_authority: Literal["none"] = "none"
    dispatch_ready: Literal[False] = False
    requires_new_execution_admission: Literal[True] = True

    @model_validator(mode="after")
    def honest(self) -> "InitialReportedRuleCandidateV1":
        if (
            self.evidence.digest() != self.evidence_digest
            or self.evidence.scope_digest != self.scope.digest()
            or self.evidence.environment != self.scope.mandate.environment
            or self.evidence.rule_policy_digest != self.policy_digest
            or (self.status == "suggested") != (self.action is not None)
            or (self.action is None) != (self.nominal_after_micros is None)
            or self.expires_at > self.evidence.expires_at
        ):
            raise ValueError("initial candidate commitment mismatch")
        if self.action is not None and (
            self.action.amount_micros != self.nominal_after_micros
            or self.expires_at <= self.observed_at
            or self.evidence.direction == "none"
            or (self.action.amount_micros > self.nominal_before_micros)
            != (self.evidence.direction == "increase")
            or self.action.amount_micros == self.nominal_before_micros
            or abs(self.action.amount_micros - self.nominal_before_micros)
            > abs(self.evidence.signed_delta_micros)
        ):
            raise ValueError("initial candidate cannot enlarge or reverse configured rule")
        return self
