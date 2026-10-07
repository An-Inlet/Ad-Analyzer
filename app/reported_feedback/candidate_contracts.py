"""Explicit reported-efficiency rule documents, never qualified-learning evidence."""

from datetime import timedelta
from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from app.commerce.evidence import digest as source_digest
from app.directional_feedback.contracts import DecisionOpportunityV1
from app.initial_planning.contracts import Frozen
from app.optimization_candidates.contracts import CandidateScope
from app.optimization_candidates.selection_contracts import SelectionBlock, SelectionProvenance
from app.publication.contracts import fingerprint
from app.publication.optimization_contracts import MetaBudgetSetV1, MetaCurrentState
from app.publication.provider_contracts import Digest, Id
from app.reported_feedback.contracts import ReportedFeedbackPolicyV1, ReportedWindowSummaryV1


class Committed(Frozen):
    schema_version: str

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class ReportedRulePolicyV1(Committed):
    schema_version: Literal["inlet.reported-rule-policy.v1"] = "inlet.reported-rule-policy.v1"
    workspace_id: int = Field(strict=True, gt=0)
    environment: Literal["contract_test", "live"]
    policy_id: Id
    revision: int = Field(strict=True, ge=1)
    policy_family: Id
    feedback_policy: ReportedFeedbackPolicyV1
    comparison_policy_digest: Digest
    allowed_operation: Literal["meta_budget_set_v1"]
    maximum_candidate_age_seconds: int = Field(strict=True, ge=1, le=300)

    @model_validator(mode="after")
    def exact_policy(self) -> "ReportedRulePolicyV1":
        if (
            self.feedback_policy.environment != self.environment
            or self.feedback_policy.comparison_policy_digest != self.comparison_policy_digest
            or self.feedback_policy.minimum_distinct_original_attempts != 1
        ):
            raise ValueError("one-original exact reported policy required")
        return self


class ReportedRuleEvidenceV1(Committed):
    schema_version: Literal["inlet.reported-rule-evidence.v1"] = "inlet.reported-rule-evidence.v1"
    scope_digest: Digest
    environment: Literal["contract_test", "live"]
    source_schema: Literal["inlet.operational-reported-comparison.v1"] = (
        "inlet.operational-reported-comparison.v1"
    )
    source_reference: Id
    comparison_id: Id
    comparison_digest: Digest
    acquisition_request_id: Id
    comparison_policy_digest: Digest
    rule_policy_digest: Digest
    opportunity: DecisionOpportunityV1
    direction: Literal["increase", "decrease", "none"]
    signed_delta_micros: int = Field(strict=True, ge=-(10**15), le=10**15)
    before: ReportedWindowSummaryV1
    after: ReportedWindowSummaryV1
    reported_completion_count: int = Field(strict=True, ge=4, le=16)
    original_attempt_count: Literal[1] = 1
    observed_at: AwareDatetime
    expires_at: AwareDatetime
    basis: Literal["operational_reported_efficiency_rule"] = "operational_reported_efficiency_rule"
    correction_status: Literal["as_observed_unsettled"] = "as_observed_unsettled"
    causal_lift: Literal["unavailable"] = "unavailable"
    delivery_time: Literal["unavailable"] = "unavailable"
    spending_authority: Literal["none"] = "none"

    @model_validator(mode="after")
    def exact_evidence(self) -> "ReportedRuleEvidenceV1":
        refs = (*self.before.capsules, *self.after.capsules)
        expected = (
            "increase"
            if self.signed_delta_micros > 0
            else "decrease"
            if self.signed_delta_micros < 0
            else "none"
        )
        if (
            self.direction != expected
            or self.source_reference != self.opportunity.original_attempt_id
            or self.environment != self.opportunity.environment
            or len(refs) != self.reported_completion_count
            or len({r.completion_id for r in refs}) != len(refs)
            or self.before.window.ends_on >= self.after.window.starts_on
            or any(
                s.missing_dates
                or not s.revisions_within_tolerance
                or s.reported_cpa_micros is None
                or s.conversions is None
                or s.conversions <= 0
                for s in (self.before, self.after)
            )
            or not self.observed_at < self.expires_at <= self.observed_at + timedelta(minutes=5)
        ):
            raise ValueError("exact bounded operational report evidence required")
        return self


class ReportedRuleObservationV1(Committed):
    schema_version: Literal["inlet.reported-rule-observation.v1"] = (
        "inlet.reported-rule-observation.v1"
    )
    scope: CandidateScope
    state: MetaCurrentState
    evidence: ReportedRuleEvidenceV1

    @model_validator(mode="after")
    def owned(self) -> "ReportedRuleObservationV1":
        if (
            self.state.scope != self.scope.account
            or self.state.target != self.scope.target
            or self.state.target.kind != "campaign"
            or self.state.budget_owner.key(self.scope.account) != self.scope.budget_owner_key
            or self.state.budget_owner.target_set_digest() != self.scope.target_set_digest
            or self.evidence.scope_digest != self.scope.digest()
            or self.evidence.environment != self.scope.mandate.environment
            or self.evidence.opportunity.workspace_id != self.scope.account.workspace_id
            or self.evidence.opportunity.ledger_id != self.scope.mandate.ledger_id
            or self.evidence.opportunity.native_account_digest
            != source_digest(
                [
                    "inlet.native-feedback-account.v1",
                    self.scope.account.account.platform,
                    self.scope.account.external_advertiser_id,
                ]
            )
            or self.state.budget_owner.owner != self.state.target
            or self.evidence.opportunity.budget_owner_key != self.scope.budget_owner_key
        ):
            raise ValueError("exact campaign-level reported observation required")
        return self


class ReportedRuleWorkV1(Committed):
    schema_version: Literal["inlet.reported-rule-work.v1"] = "inlet.reported-rule-work.v1"
    purpose: Literal["prepare_suggestion_only"] = "prepare_suggestion_only"
    scope: CandidateScope
    policy: ReportedRulePolicyV1
    selection: SelectionProvenance
    comparison_id: Id

    @model_validator(mode="after")
    def owned(self) -> "ReportedRuleWorkV1":
        if (
            self.scope.account.account.platform != "meta_ads"
            or self.scope.target.kind != "campaign"
            or self.scope.source.attempt_id is None
            or self.policy.workspace_id != self.scope.account.workspace_id
            or self.policy.environment != self.scope.mandate.environment
            or self.selection.scope_digest != self.scope.digest()
            or self.selection.policy_digest != self.policy.digest()
        ):
            raise ValueError("reported work scope changed")
        return self


class ReportedRuleCandidateV1(Committed):
    schema_version: Literal["inlet.reported-rule-candidate.v1"] = "inlet.reported-rule-candidate.v1"
    scope: CandidateScope
    policy_digest: Digest
    state_digest: Digest
    evidence_digest: Digest
    evidence: ReportedRuleEvidenceV1
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
    def honest(self) -> "ReportedRuleCandidateV1":
        if (
            self.evidence.digest() != self.evidence_digest
            or self.evidence.scope_digest != self.scope.digest()
            or self.evidence.environment != self.scope.mandate.environment
            or self.evidence.rule_policy_digest != self.policy_digest
            or (self.status == "suggested") != (self.action is not None)
            or (self.action is None) != (self.nominal_after_micros is None)
            or self.expires_at > self.evidence.expires_at
        ):
            raise ValueError("reported decision commitment changed")
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
            raise ValueError("reported suggestion cannot enlarge or reverse the rule")
        return self


class ReportedRuleSelectionBatchV1(Committed):
    schema_version: Literal["inlet.reported-rule-selection.v1"] = "inlet.reported-rule-selection.v1"
    workspace_id: int = Field(strict=True, gt=0)
    manifest_digest: Digest
    selected: tuple[ReportedRuleWorkV1, ...] = Field(max_length=20)
    blocked: tuple[SelectionBlock, ...] = Field(max_length=20)
    authority: Literal["none"] = "none"

    @model_validator(mode="after")
    def owned_manifest(self) -> "ReportedRuleSelectionBatchV1":
        ids = [w.scope.account.account.account_id for w in self.selected]
        ids += [b.account_id for b in self.blocked]
        if len(set(ids)) != len(ids) or any(
            w.scope.account.workspace_id != self.workspace_id
            or w.selection.manifest_digest != self.manifest_digest
            for w in self.selected
        ):
            raise ValueError("reported selection ownership mismatch")
        return self
