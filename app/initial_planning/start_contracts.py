"""Explicit initial operational Start commitments, separate from human approval."""

from typing import Literal

from pydantic import Field

from app.initial_planning.automatic_contracts import Committed
from app.optimization_candidates.selection_contracts import CandidatePolicyRef
from app.publication.execution_contracts import ProviderMandateBinding
from app.publication.provider_contracts import Digest, Id
from app.session_automation.contracts import AutomaticPolicyRef

INITIAL_AUTOMATIC_FAMILY = "54f030290671490da424160b8c0a0a49"


class InitialRuleAutomaticPolicyV1(Committed):
    schema_version: Literal["inlet.session-initial-rule-policy.v1"] = (
        "inlet.session-initial-rule-policy.v1"
    )
    decision_basis: Literal["initial_reported_efficiency_rule"]
    workspace_id: int = Field(strict=True, gt=0)
    environment: Literal["contract_test", "live"]
    policy_family: Literal["54f030290671490da424160b8c0a0a49"]
    policy_id: Id
    revision: int = Field(strict=True, ge=1)
    candidate_policy: CandidatePolicyRef
    candidate_policy_digest: Digest
    allowed_operations: tuple[Literal["meta_budget_set_v1"], ...] = Field(
        min_length=1, max_length=1
    )
    semantic_producer_families: tuple[Id, ...] = Field(min_length=1, max_length=1)
    lifetime_seconds: int = Field(strict=True, ge=1, le=300)
    cadence_seconds: int = Field(strict=True, ge=1, le=300)


class StartInitialReportedRuleAutomationV1(Committed):
    schema_version: Literal["inlet.start-initial-reported-rule-automation.v1"]
    decision_basis: Literal["initial_reported_efficiency_rule"]
    preview_id: Id
    expected_preview_digest: Digest
    mandate: ProviderMandateBinding
    policy: AutomaticPolicyRef
    expected_policy_digest: Digest


class InitialRuleAutomaticOptionV1(Committed):
    schema_version: Literal["inlet.initial-rule-automatic-option.v1"] = (
        "inlet.initial-rule-automatic-option.v1"
    )
    policy: AutomaticPolicyRef
    policy_digest: Digest
    label: str = Field(min_length=1, max_length=100)
    mandate: ProviderMandateBinding
    currency: Literal["USD"]
    total_limit_micros: int = Field(strict=True, gt=0, le=10**15)
    selected_rule: str = Field(min_length=1, max_length=64)
    maximum_adjustment_micros: int = Field(strict=True, gt=0, le=10**15)
    lifetime_seconds: int = Field(strict=True, ge=1, le=300)
    cadence_seconds: int = Field(strict=True, ge=1, le=300)
    decision_basis: Literal["initial_reported_efficiency_rule"] = "initial_reported_efficiency_rule"


class InitialRuleAutomaticOptionsV1(Committed):
    schema_version: Literal["inlet.initial-rule-automatic-options.v1"] = (
        "inlet.initial-rule-automatic-options.v1"
    )
    preview_id: Id
    preview_digest: Digest
    options: tuple[InitialRuleAutomaticOptionV1, ...] = Field(max_length=20)
    truncated: bool
    spending_authority: Literal["none"] = "none"
    correction_status: Literal["as_observed_unsettled"] = "as_observed_unsettled"
    causal_lift: Literal["unavailable"] = "unavailable"
    financial_qualification: Literal["checked_separately_before_each_change"] = (
        "checked_separately_before_each_change"
    )
