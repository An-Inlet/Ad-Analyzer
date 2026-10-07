"""Read-only native evidence. These types cannot satisfy optimization authority."""

from datetime import datetime
from typing import Literal, Protocol
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, ConfigDict, Field, model_validator

from app.initial_planning.contracts import CohortV1, Frozen
from app.mandates.schemas import AccountScope
from app.meta.budget_currency import supported_budget_exponent
from app.publication.contracts import fingerprint
from app.publication.execution_contracts import ExecutionAccount
from app.publication.optimization_contracts import BudgetOwnerRef, OptimizationTarget
from app.publication.provider_contracts import Digest, Id

UnsupportedBudgetReason = Literal[
    "required_settings_unavailable",
    "unsupported_campaign_profile",
    "account_not_active",
    "target_not_editable",
    "required_flags_unavailable",
    "budget_mode_unavailable",
    "budget_sharing_enabled",
    "budget_schedule_enabled",
    "budget_rebalance_enabled",
]


class NativeAccountScope(AccountScope):
    model_config = ConfigDict(extra="forbid", frozen=True)


class NativeExecutionAccount(ExecutionAccount):
    model_config = ConfigDict(extra="forbid", frozen=True)
    account: NativeAccountScope


class NativeBudgetTarget(OptimizationTarget):
    model_config = ConfigDict(extra="forbid", frozen=True)


class NativeBudgetOwnerV1(Frozen):
    provider: Literal["meta_ads"]
    owner: NativeBudgetTarget
    mode: Literal["independent", "campaign_pool"]
    affected_targets: tuple[NativeBudgetTarget, ...] = Field(min_length=1, max_length=200)
    topology_digest: Digest

    @model_validator(mode="after")
    def complete(self) -> "NativeBudgetOwnerV1":
        BudgetOwnerRef.model_validate(self.model_dump())
        targets = sorted(self.affected_targets, key=lambda t: (t.kind, t.external_id))
        if self.topology_digest != fingerprint(
            "inlet.optimization-topology.v1", {"targets": [t.model_dump() for t in targets]}
        ):
            raise ValueError("native topology digest mismatch")
        return self

    def target_set_digest(self) -> str:
        return BudgetOwnerRef.model_validate(self.model_dump()).target_set_digest()


class NativeBudgetRequestV1(Frozen):
    schema_version: Literal["inlet.native-budget-request.v1"] = "inlet.native-budget-request.v1"
    profile_digest: Digest
    environment: Literal["contract_test", "live"]
    scope: NativeExecutionAccount
    cohort: CohortV1
    goal_id: Id
    goal_revision: int = Field(strict=True, gt=0)
    goal_digest: Digest
    target: NativeBudgetTarget

    @model_validator(mode="after")
    def owned_campaign(self) -> "NativeBudgetRequestV1":
        ZoneInfo(self.cohort.time_zone)
        if (
            self.scope.workspace_id != self.cohort.workspace_id
            or self.scope.account.account_id != self.cohort.account_id
            or self.scope.account.platform != "meta_ads"
            or self.target.kind != "campaign"
        ):
            raise ValueError("native request scope mismatch")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class NativeBudgetObservationV1(Frozen):
    schema_version: Literal["inlet.native-budget-observation.v1"] = (
        "inlet.native-budget-observation.v1"
    )
    request: NativeBudgetRequestV1
    budget_owner: NativeBudgetOwnerV1
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    currency_exponent: int = Field(strict=True, ge=0, le=3)
    time_zone: str = Field(min_length=1, max_length=64)
    budget_mode: Literal["daily", "lifetime"] | None
    amount_micros: int | None = Field(strict=True, gt=0, le=10**15)
    account_status: str = Field(min_length=1, max_length=64)
    configured_status: str = Field(min_length=1, max_length=64)
    effective_status: str = Field(min_length=1, max_length=64)
    starts_at: AwareDatetime | None
    ends_at: AwareDatetime | None
    sharing_enabled: bool | None
    schedule_adjustments_enabled: bool | None
    rebalance_enabled: bool | None
    unaffected_settings_digest: Digest
    unsupported_reasons: tuple[UnsupportedBudgetReason, ...] = Field(max_length=9)
    observation_started_at: AwareDatetime
    observed_at: AwareDatetime
    expires_at: AwareDatetime
    spending_authority: Literal["none"] = "none"
    financial_qualification: Literal["unavailable"] = "unavailable"

    @model_validator(mode="after")
    def exact(self) -> "NativeBudgetObservationV1":
        if (
            self.currency_exponent != supported_budget_exponent(self.currency)
            or self.budget_owner.provider != "meta_ads"
            or self.budget_owner.owner != self.request.target
            or self.currency != self.request.cohort.currency
            or self.time_zone != self.request.cohort.time_zone
            or self.observation_started_at > self.observed_at
            or not 0 < (self.expires_at - self.observed_at).total_seconds() <= 300
            or (
                self.amount_micros is not None
                and self.amount_micros % 10 ** (6 - self.currency_exponent) != 0
            )
            or (self.budget_mode is None) != (self.amount_micros is None)
            or len(set(self.unsupported_reasons)) != len(self.unsupported_reasons)
            or (
                not self.unsupported_reasons
                and (
                    self.amount_micros is None
                    or self.account_status != "1"
                    or self.configured_status not in {"ACTIVE", "PAUSED"}
                    or any(
                        v is not False
                        for v in (
                            self.sharing_enabled,
                            self.schedule_adjustments_enabled,
                            self.rebalance_enabled,
                        )
                    )
                )
            )
        ):
            raise ValueError("invalid native budget observation")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class NativeBudgetOptionV1(Frozen):
    label: str = Field(min_length=1, max_length=200)
    observation: NativeBudgetObservationV1

    @model_validator(mode="after")
    def supported(self) -> "NativeBudgetOptionV1":
        if self.observation.unsupported_reasons:
            raise ValueError("unsupported native option")
        return self

    def identifier(self) -> str:
        return fingerprint("inlet.native-budget-option.v1", self.model_dump(mode="json"))


class NativeBudgetCatalogV1(Frozen):
    request: NativeBudgetRequestV1
    options: tuple[NativeBudgetOptionV1, ...] = Field(max_length=1)
    observed_at: AwareDatetime
    expires_at: AwareDatetime
    complete: Literal[True] = True

    @model_validator(mode="after")
    def exact(self) -> "NativeBudgetCatalogV1":
        if not 0 < (self.expires_at - self.observed_at).total_seconds() <= 300 or any(
            o.observation.request != self.request
            or o.observation.observed_at > self.observed_at
            or o.observation.expires_at < self.expires_at
            for o in self.options
        ):
            raise ValueError("invalid native catalog binding")
        return self


class NativeBudgetReader(Protocol):
    def read(self, request: NativeBudgetRequestV1, now: datetime) -> NativeBudgetCatalogV1: ...
