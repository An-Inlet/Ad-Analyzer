"""Additive simple optimization consent inputs; no changes to existing policy hashes."""

from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from app.initial_planning.budget_mandate_contracts import (
    Aggressiveness,
    Amount,
    BudgetMandateRuleV1,
    Identifier,
)
from app.initial_planning.contracts import Frozen
from app.publication.contracts import fingerprint
from app.publication.provider_contracts import Digest


class OptimizationOperatingRuleV1(BudgetMandateRuleV1):
    # Existing execution policy supports at most1000 actions. Do not admit a policy
    # the downstream immutable mandate cannot represent.
    action_limit: int = Field(strict=True, ge=1, le=1000)


class OptimizationOperatingPolicyV1(Frozen):
    schema_version: Literal["inlet.optimization-operating-policy.v1"] = (
        "inlet.optimization-operating-policy.v1"
    )
    policy_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    revision: int = Field(strict=True, gt=0)
    environment: Literal["contract_test", "live"]
    evidence_profile_digest: Digest
    currency: Literal["USD"]
    currency_exponent: Literal[2]
    rules: tuple[OptimizationOperatingRuleV1, ...] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def names(self) -> "OptimizationOperatingPolicyV1":
        if tuple(rule.name for rule in self.rules) != ("conservative", "balanced", "assertive"):
            raise ValueError("exact canonical named aggression mapping required")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))

    def rule(self, name: Aggressiveness) -> OptimizationOperatingRuleV1:
        return next(rule for rule in self.rules if rule.name == name)


class OptimizationSelectionV1(Frozen):
    goal_id: Identifier
    goal_revision: int = Field(strict=True, gt=0)
    account_id: int = Field(strict=True, gt=0)
    option_id: Digest


class OptimizationCustomerIntentV1(Frozen):
    selection: OptimizationSelectionV1
    total_cap_micros: Amount
    aggressiveness: Aggressiveness

    @model_validator(mode="after")
    def quantum(self) -> "OptimizationCustomerIntentV1":
        if self.total_cap_micros % 10000:
            raise ValueError("USD cent precision required")
        return self


class PrepareOptimizationMandateV1(Frozen):
    intent: OptimizationCustomerIntentV1
    mandate_id: Identifier | None = None
    expected_revision: int | None = Field(default=None, strict=True, gt=0)

    @model_validator(mode="after")
    def exact_edit(self) -> "PrepareOptimizationMandateV1":
        if (self.mandate_id is None) != (self.expected_revision is None):
            raise ValueError("complete edit identity required")
        return self


class ConsentOptimizationMandateV1(Frozen):
    selection: OptimizationSelectionV1
    expected_revision: int = Field(strict=True, gt=0)
    policy_digest: Digest
    preparation_digest: Digest


class PreparedOptimizationMandateV1(Frozen):
    """Customer review of exact conditional authority; never proof of headroom."""

    schema_version: Literal["inlet.prepared-optimization-mandate.v1"] = (
        "inlet.prepared-optimization-mandate.v1"
    )
    mandate_id: Identifier
    revision: int = Field(strict=True, gt=0)
    policy_digest: Digest
    preparation_digest: Digest
    state: Literal["draft", "active"]
    selection: OptimizationSelectionV1
    environment: Literal["contract_test", "live"]
    currency: Literal["USD"]
    time_zone: str = Field(min_length=1, max_length=100)
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    total_cap_micros: Amount
    per_plan_cap_micros: Amount
    positive_change_cap_micros: Amount
    aggressiveness: Aggressiveness
    target_label: str = Field(min_length=1, max_length=160)
    affected_target_count: int = Field(strict=True, ge=1, le=200)
    dispatch_qualified: Literal[False] = False

    @model_validator(mode="after")
    def bounds(self) -> "PreparedOptimizationMandateV1":
        if (
            self.starts_at >= self.ends_at
            or self.per_plan_cap_micros > self.total_cap_micros
            or self.positive_change_cap_micros > self.per_plan_cap_micros
        ):
            raise ValueError("exact bounded conditional mandate required")
        return self
