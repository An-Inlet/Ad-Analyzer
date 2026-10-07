"""Explicit original-session operational Start; no mature-learning or live defaults."""

from typing import Literal

from pydantic import Field

from app.optimization_candidates.selection_contracts import CandidatePolicyRef
from app.publication.execution_contracts import ProviderMandateBinding
from app.publication.provider_contracts import Digest, Id
from app.reported_feedback.candidate_contracts import Committed
from app.session_automation.contracts import AutomaticPolicyRef

# Protocol identities, independent of deployment, policy revision or numeric calibration.
REPORTED_RULE_FAMILY = "7e6f69dfd2fa43fd8c72a9757e35541f"
REPORTED_RULE_EPOCH_FAMILY = "e4887d5a47e8421380e170f8ccf055bc"


class ReportedRuleAutomaticPolicyV1(Committed):
    schema_version: Literal["inlet.session-reported-rule-policy.v1"] = (
        "inlet.session-reported-rule-policy.v1"
    )
    decision_basis: Literal["operational_reported_efficiency_rule"]
    workspace_id: int = Field(strict=True, gt=0)
    environment: Literal["contract_test", "live"]
    policy_family: Literal["7e6f69dfd2fa43fd8c72a9757e35541f"]
    policy_id: Id
    revision: int = Field(strict=True, ge=1)
    candidate_policy: CandidatePolicyRef
    candidate_policy_digest: Digest
    allowed_operations: tuple[Literal["meta_budget_set_v1"], ...] = Field(
        min_length=1, max_length=1
    )
    semantic_producer_families: tuple[Literal["e4887d5a47e8421380e170f8ccf055bc"], ...] = Field(
        min_length=1, max_length=1
    )
    lifetime_seconds: int = Field(strict=True, ge=1, le=86400)
    cadence_seconds: int = Field(strict=True, ge=1, le=86400)


class StartReportedRuleAutomationV1(Committed):
    schema_version: Literal["inlet.start-reported-rule-automation.v1"]
    decision_basis: Literal["operational_reported_efficiency_rule"]
    mandate: ProviderMandateBinding
    policy: AutomaticPolicyRef
    expected_policy_digest: Digest


class ReportedRuleParametersViewV1(Committed):
    schema_version: Literal["inlet.reported-rule-parameters-view.v1"] = (
        "inlet.reported-rule-parameters-view.v1"
    )
    original_change: Literal["increase", "decrease"]
    favorable_direction: Literal["increase", "decrease"]
    unfavorable_direction: Literal["increase", "decrease"]
    # Canonical decimal strings keep exact parameters across JavaScript serialization.
    neutral_band: str = Field(pattern=r"^(0|[1-9][0-9]*)(\.[0-9]*[1-9])?$")
    weight: str = Field(pattern=r"^(0|[1-9][0-9]*)(\.[0-9]*[1-9])?$")
    contribution_clamp: str = Field(pattern=r"^(0|[1-9][0-9]*)(\.[0-9]*[1-9])?$")
    aggregate_clamp: str = Field(pattern=r"^(0|[1-9][0-9]*)(\.[0-9]*[1-9])?$")
    maximum_nominal_adjustment_micros: int = Field(strict=True, gt=0, le=10**15)
    minimum_distinct_original_attempts: Literal[1]
    evidence_lifetime_seconds: int = Field(strict=True, gt=0)


class ReportedRuleAutomaticPolicyOptionV1(Committed):
    schema_version: Literal["inlet.reported-rule-automatic-option.v1"] = (
        "inlet.reported-rule-automatic-option.v1"
    )
    policy: AutomaticPolicyRef
    policy_digest: Digest
    label: str = Field(min_length=1, max_length=100)
    environment: Literal["contract_test", "live"]
    decision_basis: Literal["operational_reported_efficiency_rule"]
    rule_parameters: ReportedRuleParametersViewV1
    lifetime_seconds: int = Field(strict=True, ge=1, le=86400)
    cadence_seconds: int = Field(strict=True, ge=1, le=86400)
    session_bound: Literal[True] = True
    causal_lift: Literal["unavailable"] = "unavailable"
    financial_qualification: Literal["checked_separately_before_each_change"] = (
        "checked_separately_before_each_change"
    )
