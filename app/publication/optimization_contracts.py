"""Exact existing-campaign budget/pause ports; no resume, arbitrary patch or CAS claim."""

from datetime import datetime
from typing import Annotated, Literal, Protocol
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, Field, SecretStr, model_validator

from app.goals.schemas import StrictModel
from app.publication.contracts import fingerprint
from app.publication.execution_contracts import (
    ExecutionAccount,
    ExposureEvidence,
    ProviderMandateBinding,
)
from app.publication.provider_contracts import Digest, Id, Micros
from app.publication.social_contracts import NumericId


class OptimizationTarget(StrictModel):
    kind: Literal["campaign", "adset", "adgroup"]
    external_id: NumericId
    campaign_id: NumericId

    @model_validator(mode="after")
    def parent(self) -> "OptimizationTarget":
        if self.kind == "campaign" and self.external_id != self.campaign_id:
            raise ValueError("campaign parent mismatch")
        return self


class BudgetOwnerRef(StrictModel):
    provider: Literal["meta_ads", "tiktok_ads"]
    owner: OptimizationTarget
    mode: Literal["independent", "campaign_pool"]
    affected_targets: list[OptimizationTarget] = Field(min_length=1, max_length=200)
    topology_digest: Digest

    @model_validator(mode="after")
    def complete_target_set(self) -> "BudgetOwnerRef":
        keys = [(target.kind, target.external_id) for target in self.affected_targets]
        if (
            len(set(keys)) != len(keys)
            or self.owner not in self.affected_targets
            or any(target.campaign_id != self.owner.campaign_id for target in self.affected_targets)
            or (self.mode == "independent" and self.affected_targets != [self.owner])
            or (self.mode == "campaign_pool" and self.owner.kind != "campaign")
            or (
                self.provider == "meta_ads"
                and any(t.kind == "adgroup" for t in self.affected_targets)
            )
            or (
                self.provider == "tiktok_ads"
                and any(t.kind == "adset" for t in self.affected_targets)
            )
        ):
            raise ValueError("invalid complete budget owner topology")
        return self

    def target_set_digest(self) -> str:
        targets = sorted(self.affected_targets, key=lambda t: (t.kind, t.external_id))
        return fingerprint(
            "inlet.optimization-targets.v1",
            {"provider": self.provider, "targets": [t.model_dump() for t in targets]},
        )

    def key(self, scope: ExecutionAccount) -> str:
        provider = self.provider.removesuffix("_ads")
        return (
            f"{provider}/{scope.external_advertiser_id}/{self.owner.kind}/{self.owner.external_id}"
        )


class GoogleBudgetOwnerRef(StrictModel):
    """Bounded independent native Google budget; complete owning campaign topology."""

    provider: Literal["google_ads"] = "google_ads"
    owner: OptimizationTarget
    mode: Literal["independent"] = "independent"
    affected_targets: list[OptimizationTarget] = Field(min_length=1, max_length=200)
    native_budget_resource: str = Field(pattern=r"^customers/[0-9]{10}/campaignBudgets/[0-9]+$")
    topology_digest: Digest

    @model_validator(mode="after")
    def independent(self) -> "GoogleBudgetOwnerRef":
        if self.owner.kind != "campaign" or self.affected_targets != [self.owner]:
            raise ValueError("one complete independently owned Google campaign required")
        return self

    def target_set_digest(self) -> str:
        return fingerprint(
            "inlet.optimization-targets.v1",
            {
                "provider": self.provider,
                "targets": [t.model_dump() for t in self.affected_targets],
            },
        )

    def key(self, scope: ExecutionAccount) -> str:
        prefix = f"customers/{scope.external_advertiser_id}/campaignBudgets/"
        if scope.account.platform != "google_ads" or not self.native_budget_resource.startswith(
            prefix
        ):
            raise ValueError("foreign native Google budget")
        return self.native_budget_resource


OptimizationBudgetOwner = Annotated[
    BudgetOwnerRef | GoogleBudgetOwnerRef, Field(discriminator="provider")
]


class MoneyContext(StrictModel):
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    currency_exponent: int = Field(strict=True, ge=0, le=3)
    account_timezone: str = Field(min_length=1, max_length=64)
    period_start: AwareDatetime
    period_end: AwareDatetime

    @model_validator(mode="after")
    def semantics(self) -> "MoneyContext":
        ZoneInfo(self.account_timezone)
        if self.period_start >= self.period_end:
            raise ValueError("invalid money horizon")
        return self


class CurrentStateBase(StrictModel):
    scope: ExecutionAccount
    target: OptimizationTarget
    budget_owner: OptimizationBudgetOwner
    money: MoneyContext
    account_status: str = Field(min_length=1, max_length=64)
    configured_status: str = Field(min_length=1, max_length=64)
    effective_status: str = Field(min_length=1, max_length=128)
    parent_configured_status: str = Field(min_length=1, max_length=64)
    starts_at: AwareDatetime | None
    ends_at: AwareDatetime | None
    sharing_enabled: bool | None
    schedule_adjustments_enabled: bool | None
    rebalance_enabled: bool | None
    unaffected_settings_digest: Digest
    qualification_id: Id
    qualification_revision: int = Field(strict=True, ge=1)
    unsupported_features: list[str] = Field(max_length=32)
    complete: bool
    provider_cas: Literal["unavailable"] = "unavailable"
    observation_started_at: AwareDatetime
    observed_at: AwareDatetime

    @model_validator(mode="after")
    def same_owner(self) -> "CurrentStateBase":
        if (
            getattr(self, "api_version", None)
            != {"meta_ads": "v26.0", "tiktok_ads": "v1.3", "google_ads": "v25"}.get(
                self.scope.account.platform
            )
            or self.observation_started_at > self.observed_at
            or self.scope.account.platform != self.budget_owner.provider
            or self.target not in self.budget_owner.affected_targets
        ):
            raise ValueError("invalid current state ownership")
        return self

    def digest(self) -> str:
        return fingerprint(
            "inlet.optimization-state.v1",
            self.model_dump(mode="json", exclude={"observed_at", "observation_started_at"}),
        )


class MetaCurrentState(CurrentStateBase):
    kind: Literal["meta_current_v26"] = "meta_current_v26"
    api_version: Literal["v26.0"] = "v26.0"
    objective: str = Field(min_length=1, max_length=64)
    buying_type: str = Field(min_length=1, max_length=64)
    daily_budget_micros: int | None = Field(strict=True, ge=0, le=10**15)
    lifetime_budget_micros: int | None = Field(strict=True, ge=0, le=10**15)


class TikTokCurrentState(CurrentStateBase):
    kind: Literal["tiktok_current_v13"] = "tiktok_current_v13"
    api_version: Literal["v1.3"] = "v1.3"
    campaign_type: str = Field(min_length=1, max_length=64)
    objective_type: str = Field(min_length=1, max_length=64)
    promotion_type: str = Field(min_length=1, max_length=64)
    budget_optimize_on: bool | None
    budget_mode: str = Field(min_length=1, max_length=64)
    budget_micros: int | None = Field(strict=True, ge=0, le=10**15)
    schedule_type: str = Field(min_length=1, max_length=64)
    schedule_wire_timezone: Literal["UTC"]


class GoogleCurrentState(CurrentStateBase):
    kind: Literal["google_current_v25"] = "google_current_v25"
    api_version: Literal["v25"] = "v25"
    native_budget_resource: str = Field(pattern=r"^customers/[0-9]{10}/campaignBudgets/[0-9]+$")
    budget_amount_micros: int = Field(strict=True, ge=0, le=10**15)
    budget_total_amount_micros: int | None = Field(strict=True, ge=0, le=10**15)
    budget_explicitly_shared: bool
    budget_reference_count: int = Field(strict=True, ge=0)
    owning_campaign_ids: list[NumericId] = Field(min_length=1, max_length=200)
    budget_period: str = Field(min_length=1, max_length=64)
    budget_delivery_method: str = Field(min_length=1, max_length=64)
    budget_status: str = Field(min_length=1, max_length=64)
    budget_type: str = Field(min_length=1, max_length=64)
    advertising_channel_type: str = Field(min_length=1, max_length=64)
    advertising_channel_sub_type: str = Field(min_length=1, max_length=64)
    bidding_strategy_type: str = Field(min_length=1, max_length=64)
    manual_cpc_digest: Digest
    network_settings_digest: Digest
    campaign_start_date: str = Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
    campaign_end_date: str | None = Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")

    @model_validator(mode="after")
    def independent_native_owner(self) -> "GoogleCurrentState":
        if (
            not isinstance(self.budget_owner, GoogleBudgetOwnerRef)
            or self.native_budget_resource != self.budget_owner.key(self.scope)
            or self.budget_explicitly_shared
            or self.budget_reference_count != 1
            or self.owning_campaign_ids != [self.target.campaign_id]
            or self.target != self.budget_owner.owner
            or (self.campaign_end_date is None) != (self.ends_at is None)
        ):
            raise ValueError("complete independent native Google budget ownership required")
        return self


OptimizationState = Annotated[
    MetaCurrentState | TikTokCurrentState | GoogleCurrentState, Field(discriminator="kind")
]


class MetaBudgetSetV1(StrictModel):
    kind: Literal["meta_budget_set_v1"] = "meta_budget_set_v1"
    budget_field: Literal["daily_budget", "lifetime_budget"]
    amount_micros: Micros


class MetaStatusSetV1(StrictModel):
    kind: Literal["meta_status_set_v1"] = "meta_status_set_v1"
    status: Literal["PAUSED"]


class TikTokBudgetSetV1(StrictModel):
    kind: Literal["tiktok_budget_set_v1"] = "tiktok_budget_set_v1"
    budget_mode: Literal["BUDGET_MODE_DAY", "BUDGET_MODE_TOTAL"]
    amount_micros: Micros


class TikTokStatusSetV1(StrictModel):
    kind: Literal["tiktok_status_set_v1"] = "tiktok_status_set_v1"
    operation_status: Literal["DISABLE"]


class GoogleBudgetSetV1(StrictModel):
    kind: Literal["google_budget_set_v1"] = "google_budget_set_v1"
    amount_micros: Micros


class GoogleStatusSetV1(StrictModel):
    kind: Literal["google_status_set_v1"] = "google_status_set_v1"
    status: Literal["PAUSED"]


OptimizationAction = Annotated[
    MetaBudgetSetV1
    | MetaStatusSetV1
    | TikTokBudgetSetV1
    | TikTokStatusSetV1
    | GoogleBudgetSetV1
    | GoogleStatusSetV1,
    Field(discriminator="kind"),
]


class OptimizationIntent(StrictModel):
    schema_version: Literal["inlet.optimization-intent.v1"] = "inlet.optimization-intent.v1"
    scope: ExecutionAccount
    mandate: ProviderMandateBinding
    target: OptimizationTarget
    budget_owner: OptimizationBudgetOwner
    action: OptimizationAction
    expected_state_digest: Digest
    approved_target_set_digest: Digest
    qualification_id: Id
    qualification_revision: int = Field(strict=True, ge=1)
    rationale_reference: Digest

    @model_validator(mode="after")
    def scoped_action(self) -> "OptimizationIntent":
        prefix = {"meta_ads": "meta_", "tiktok_ads": "tiktok_", "google_ads": "google_"}.get(
            self.scope.account.platform, "unsupported_"
        )
        if (
            self.scope.account.platform not in {"meta_ads", "tiktok_ads", "google_ads"}
            or self.budget_owner.provider != self.scope.account.platform
            or not self.action.kind.startswith(prefix)
            or self.target not in self.budget_owner.affected_targets
            or self.approved_target_set_digest != self.budget_owner.target_set_digest()
            or (
                isinstance(self.action, (MetaBudgetSetV1, TikTokBudgetSetV1, GoogleBudgetSetV1))
                and self.target != self.budget_owner.owner
            )
        ):
            raise ValueError("unapproved optimization target or budget owner")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class OptimizationRequest(StrictModel):
    intent: OptimizationIntent
    intent_digest: Digest
    before: OptimizationState
    exposure: ExposureEvidence
    action_id: Id
    attempt_id: Id
    fence: Id
    dispatched_at: AwareDatetime

    @model_validator(mode="after")
    def exact_preconditions(self) -> "OptimizationRequest":
        i, s, e = self.intent, self.before, self.exposure
        if (
            i.digest() != self.intent_digest
            or s.digest() != i.expected_state_digest
            or s.scope != i.scope
            or s.target != i.target
            or s.budget_owner != i.budget_owner
            or s.qualification_id != i.qualification_id
            or s.qualification_revision != i.qualification_revision
            or e.account != i.scope
            or e.mandate != i.mandate
            or e.state_digest != s.digest()
            or e.target_set_digest != i.approved_target_set_digest
            or e.budget_owner_key != i.budget_owner.key(i.scope)
            or e.currency != s.money.currency
            or (e.period_start, e.period_end) != (s.money.period_start, s.money.period_end)
            or s.observed_at > self.dispatched_at
        ):
            raise ValueError("optimization preflight binding mismatch")
        if isinstance(
            i.action, (MetaBudgetSetV1, TikTokBudgetSetV1, GoogleBudgetSetV1)
        ) and i.action.amount_micros % 10 ** (6 - s.money.currency_exponent):
            raise ValueError("budget precision loss")
        if isinstance(i.action, TikTokBudgetSetV1) and (
            not isinstance(s, TikTokCurrentState) or i.action.budget_mode != s.budget_mode
        ):
            raise ValueError("budget mode changes unavailable")
        return self

    def digest(self) -> str:
        return fingerprint("inlet.optimization-request.v1", self.model_dump(mode="json"))


class OptimizationContext(StrictModel):
    scope: ExecutionAccount
    access_token: SecretStr = Field(exclude=True, repr=False)
    app_secret: SecretStr | None = Field(default=None, exclude=True, repr=False)
    developer_token: SecretStr | None = Field(default=None, exclude=True, repr=False)
    login_customer_id: str | None = Field(default=None, pattern=r"^[0-9]{10}$", exclude=True)
    expires_at: AwareDatetime


class OptimizationResponse(StrictModel):
    request_digest: Digest
    outcome: Literal["acknowledged", "unknown"]


class OptimizationReceipt(StrictModel):
    action_id: Id
    attempt_id: Id
    fence: Id
    scope: ExecutionAccount
    mandate: ProviderMandateBinding
    intent_digest: Digest
    request_digest: Digest
    budget_owner_key: str = Field(min_length=1, max_length=256)
    before_state_digest: Digest
    after: OptimizationState | None
    outcome: Literal["verified_target_state", "conflict", "unknown", "verified_no_effect"]
    evidence: Literal["exact_readback", "mismatch", "unresolved", "authoritative_no_effect"]
    observed_at: AwareDatetime

    @model_validator(mode="after")
    def target_evidence(self) -> "OptimizationReceipt":
        if self.outcome == "verified_target_state":
            if (
                self.after is None
                or self.after.scope != self.scope
                or self.evidence != "exact_readback"
                or self.after.budget_owner.key(self.scope) != self.budget_owner_key
                or self.after.observed_at != self.observed_at
            ):
                raise ValueError("exact same-owner readback required")
        elif self.after is not None:
            raise ValueError("unverified state cannot become effect evidence")
        if self.outcome == "verified_no_effect" and self.evidence != "authoritative_no_effect":
            raise ValueError("old state is not proof of no effect")
        return self


class OptimizationValidation(StrictModel):
    request_digest: Digest
    kind: Literal["local_schema", "provider_validate_only", "unsupported"]
    valid: bool
    blockers: list[str] = Field(max_length=32)
    publication_authorized: Literal[False] = False


class OptimizationTransport(Protocol):
    def read_current(
        self,
        scope: ExecutionAccount,
        target: OptimizationTarget,
        money: MoneyContext,
        qualification_id: str,
        qualification_revision: int,
        context: OptimizationContext,
        now: datetime,
    ) -> OptimizationState: ...
    def validate_only(
        self, request: OptimizationRequest, context: OptimizationContext, now: datetime
    ) -> OptimizationValidation: ...
    def apply_once(
        self, request: OptimizationRequest, context: OptimizationContext, now: datetime
    ) -> OptimizationResponse: ...
    def read_back(
        self,
        request: OptimizationRequest,
        response: OptimizationResponse,
        context: OptimizationContext,
        now: datetime,
    ) -> OptimizationReceipt: ...
    def reconcile(
        self,
        request: OptimizationRequest,
        history: list[OptimizationResponse],
        context: OptimizationContext,
        now: datetime,
    ) -> OptimizationReceipt: ...


def get_optimization_transport() -> OptimizationTransport | None:
    return None
