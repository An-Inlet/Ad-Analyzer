"""Conditional customer authority, independently configured from provider execution."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from app.initial_planning.contracts import Frozen
from app.publication.contracts import fingerprint
from app.publication.provider_contracts import Digest

Identifier = Annotated[str, Field(pattern=r"^[a-f0-9]{32}$")]
Amount = Annotated[int, Field(strict=True, ge=0, le=10**15)]
Aggressiveness = Literal["conservative", "balanced", "assertive"]


class BudgetMandateRuleV1(Frozen):
    name: Aggressiveness
    aggressiveness_percent: Literal[5, 10, 20]
    per_plan_cap_micros: Amount
    positive_change_cap_micros: Amount
    action_limit: int = Field(strict=True, ge=1, le=10000)
    cooldown_seconds: int = Field(strict=True, ge=0, le=86400)
    freshness_seconds: int = Field(strict=True, ge=1, le=300)

    @model_validator(mode="after")
    def quantum(self) -> "BudgetMandateRuleV1":
        if self.per_plan_cap_micros % 10000 or self.positive_change_cap_micros % 10000:
            raise ValueError("USD caps must have cent precision")
        return self


class BudgetMandateOperatingPolicyV1(Frozen):
    schema_version: Literal["inlet.budget-mandate-operating-policy.v1"] = (
        "inlet.budget-mandate-operating-policy.v1"
    )
    policy_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    revision: int = Field(strict=True, gt=0)
    environment: Literal["contract_test", "live"]
    planning_reporting_profile_digest: Digest
    currency: Literal["USD"]
    currency_exponent: Literal[2]
    rules: tuple[BudgetMandateRuleV1, ...] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def names(self) -> "BudgetMandateOperatingPolicyV1":
        if tuple(r.name for r in self.rules) != ("conservative", "balanced", "assertive"):
            raise ValueError("exact canonically ordered aggression mapping required")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))

    def rule(self, name: Aggressiveness) -> BudgetMandateRuleV1:
        return next(rule for rule in self.rules if rule.name == name)


class BudgetMandateSelectionV1(Frozen):
    calibration_id: Identifier
    observation_id: Identifier
    native_option_id: Digest


class BudgetMandateCustomerIntentV1(Frozen):
    selection: BudgetMandateSelectionV1
    total_cap_micros: Amount
    aggressiveness: Aggressiveness

    @model_validator(mode="after")
    def quantum(self) -> "BudgetMandateCustomerIntentV1":
        if self.total_cap_micros % 10000:
            raise ValueError("USD total must have cent precision")
        return self


class PrepareBudgetMandateV1(Frozen):
    intent: BudgetMandateCustomerIntentV1
    mandate_id: Identifier | None = None
    expected_revision: int | None = Field(default=None, strict=True, gt=0)

    @model_validator(mode="after")
    def edit(self) -> "PrepareBudgetMandateV1":
        if (self.mandate_id is None) != (self.expected_revision is None):
            raise ValueError("complete edit identity required")
        return self


class ConsentBudgetMandateV1(Frozen):
    selection: BudgetMandateSelectionV1
    expected_revision: int = Field(strict=True, gt=0)
    policy_digest: Digest
    preparation_digest: Digest


class BudgetMandatePreparationV1(Frozen):
    """Minimal authority origin; no reports, tokens, native payloads or session secret."""

    schema_version: Literal["inlet.budget-mandate-preparation.v1"] = (
        "inlet.budget-mandate-preparation.v1"
    )
    workspace_id: int = Field(strict=True, gt=0)
    mandate_id: Identifier
    mandate_revision: int = Field(strict=True, gt=0)
    policy_digest: Digest
    operating_policy: BudgetMandateOperatingPolicyV1
    operating_policy_digest: Digest
    planning_profile_digest: Digest
    goal_digest: Digest
    customer_intent: BudgetMandateCustomerIntentV1
    account_scope_digest: Digest
    target_set_digest: Digest

    @model_validator(mode="after")
    def binding(self) -> "BudgetMandatePreparationV1":
        if (
            self.operating_policy.digest() != self.operating_policy_digest
            or self.operating_policy.planning_reporting_profile_digest
            != self.planning_profile_digest
        ):
            raise ValueError("exact operating policy and planning profile required")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class BudgetMandatePreparedV1(Frozen):
    mandate_id: Identifier
    revision: int = Field(strict=True, gt=0)
    policy_digest: Digest
    preparation_digest: Digest
    state: Literal["draft", "confirmed", "paused", "revoked"]
    planning_only: Literal[True] = True
    spending_authority: Literal["none"] = "none"
    total_cap_micros: Amount
    per_plan_cap_micros: Amount
    positive_change_cap_micros: Amount
    aggressiveness: Aggressiveness
    currency: Literal["USD"]
    native_label: str = Field(min_length=1, max_length=160)
    affected_target_count: int = Field(strict=True, gt=0, le=200)
    execution_available: Literal[False] = False
    exposure_qualified: Literal[False] = False
    new_campaign_and_creative_review: Literal["new_exact_review_required"] = (
        "new_exact_review_required"
    )
    activation_review: Literal["separate_exact_approval"] = "separate_exact_approval"
