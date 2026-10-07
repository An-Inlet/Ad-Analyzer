"""Shared provider execution authority/evidence ports, separate from B07 simulation.

Data models are not permission. Only the DB coordinator creates claims after current
consent, ownership, qualification, ledger and operational gates are checked.
"""

import re
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, model_validator

from app.goals.schemas import StrictModel
from app.mandates.schemas import AccountScope
from app.publication.contracts import PublicationScope, fingerprint
from app.publication.provider_contracts import Digest, Id

Environment = Literal["contract_test", "live"]
Purpose = Literal["create_paused", "activate", "existing_campaign_optimize"]
Amount = Annotated[int, Field(strict=True, ge=0, le=10**15)]


class ExecutionAccount(StrictModel):
    workspace_id: int = Field(strict=True, gt=0)
    account: AccountScope
    external_advertiser_id: str = Field(min_length=1, max_length=128)
    connection_version: str = Field(min_length=1, max_length=100)

    @classmethod
    def from_publication(cls, scope: PublicationScope) -> "ExecutionAccount":
        return cls.model_validate(scope.model_dump(exclude={"mandate_id", "mandate_revision"}))

    def digest(self) -> str:
        return fingerprint("inlet.execution-account.v1", self.model_dump(mode="json"))


class ProviderMandatePolicy(StrictModel):
    schema_version: Literal["inlet.provider-mandate.v1"] = "inlet.provider-mandate.v1"
    environment: Environment
    workspace_id: int = Field(strict=True, gt=0)
    goal_id: Id
    goal_revision: int = Field(strict=True, ge=1)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    time_zone: str = Field(min_length=1, max_length=64)
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    accounts: list[ExecutionAccount] = Field(min_length=1, max_length=20)
    total_cap_micros: Amount
    per_plan_cap_micros: Amount
    positive_change_cap_micros: Amount
    action_limit: int = Field(strict=True, ge=1, le=10000)
    cooldown_seconds: int = Field(strict=True, ge=0, le=86400)
    freshness_seconds: int = Field(strict=True, ge=1, le=300)
    aggressiveness_percent: Literal[5, 10, 20]
    allowed_purposes: list[Purpose] = Field(min_length=1, max_length=3)
    allowed_target_set_digest: Digest | None = None
    campaign_and_creative_policy: Literal["new_exact_review_required"]
    activation_policy: Literal["separate_exact_approval"]

    @model_validator(mode="after")
    def bounded(self) -> "ProviderMandatePolicy":
        from zoneinfo import ZoneInfo

        ZoneInfo(self.time_zone)
        if (
            self.starts_at >= self.ends_at
            or self.per_plan_cap_micros > self.total_cap_micros
            or self.positive_change_cap_micros > self.total_cap_micros
            or any(a.workspace_id != self.workspace_id for a in self.accounts)
            or len({a.account.account_id for a in self.accounts}) != len(self.accounts)
            or len(set(self.allowed_purposes)) != len(self.allowed_purposes)
            or (
                "existing_campaign_optimize" in self.allowed_purposes
                and self.allowed_target_set_digest is None
            )
        ):
            raise ValueError("invalid provider mandate policy")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class ProviderMandateBinding(StrictModel):
    mandate_id: Id
    revision: int = Field(strict=True, ge=1)
    consent_id: Id
    policy_digest: Digest
    ledger_id: Id
    environment: Environment


class ExposureEvidence(StrictModel):
    """Bounded server-calculated portfolio evidence; never a trusted customer input."""

    environment: Environment
    mandate: ProviderMandateBinding
    account: ExecutionAccount
    covered_account_ids: list[int] = Field(min_length=1, max_length=20)
    budget_owner_key: str = Field(min_length=1, max_length=256)
    target_set_digest: Digest
    state_digest: Digest
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    period_start: AwareDatetime
    period_end: AwareDatetime
    observed_at: AwareDatetime
    expires_at: AwareDatetime
    reporting_watermark: AwareDatetime
    completeness: Literal["complete", "incomplete"]
    qualification_id: Id
    model_version: str = Field(min_length=1, max_length=80)
    cap_semantics: Literal[
        "qualified_native_cap", "qualified_portfolio_bound", "contract_scenario", "unqualified"
    ]
    reported_spend_micros: Amount
    unreported_upper_micros: Amount | None
    unchanged_future_upper_micros: Amount | None
    proposed_owner_upper_micros: Amount | None
    existing_reservations_micros: Amount
    portfolio_upper_micros: Amount | None

    @model_validator(mode="after")
    def bound_is_explicit(self) -> "ExposureEvidence":
        if (
            self.environment != self.mandate.environment
            or self.period_start >= self.period_end
            or not self.reporting_watermark <= self.observed_at < self.expires_at
            or len(set(self.covered_account_ids)) != len(self.covered_account_ids)
            or self.account.account.account_id not in self.covered_account_ids
            or (self.environment == "live" and self.cap_semantics == "contract_scenario")
        ):
            raise ValueError("invalid exposure lineage or time")
        components = [
            self.unreported_upper_micros,
            self.unchanged_future_upper_micros,
            self.proposed_owner_upper_micros,
        ]
        bounded = (
            self.completeness == "complete"
            and self.cap_semantics != "unqualified"
            and all(value is not None for value in components)
        )
        if bounded:
            total = self.reported_spend_micros + self.existing_reservations_micros
            total += sum(value for value in components if value is not None)
            if self.portfolio_upper_micros != total:
                raise ValueError("portfolio bound must include all exposure")
        elif self.portfolio_upper_micros is not None:
            raise ValueError("unknown exposure cannot claim a bound")
        return self

    def digest(self) -> str:
        return fingerprint("inlet.exposure-evidence.v1", self.model_dump(mode="json"))

    def eligible(self, policy: ProviderMandatePolicy, now: datetime) -> bool:
        return (
            self.mandate.policy_digest == policy.digest()
            and self.environment == policy.environment
            and self.account in policy.accounts
            and set(self.covered_account_ids) == {a.account.account_id for a in policy.accounts}
            and self.currency == policy.currency
            and (self.period_start, self.period_end) == (policy.starts_at, policy.ends_at)
            and self.observed_at <= now < self.expires_at
            and (now - self.observed_at).total_seconds() <= policy.freshness_seconds
            and self.portfolio_upper_micros is not None
            and self.portfolio_upper_micros <= policy.total_cap_micros
            and self.proposed_owner_upper_micros is not None
            and self.proposed_owner_upper_micros <= policy.per_plan_cap_micros
        )


class NormalizedProviderReceipt(StrictModel):
    schema_version: Literal["inlet.provider-receipt-projection.v1"] = (
        "inlet.provider-receipt-projection.v1"
    )
    receipt_id: Id
    receipt_digest: Digest
    sequence: int = Field(strict=True, ge=1)
    supersedes_receipt_id: Id | None
    run_id: Id
    action_id: Id
    plan_id: Id
    step_id: str = Field(min_length=1, max_length=32)
    attempt_id: Id
    review_digest: Digest
    plan_digest: Digest
    request_digest: Digest
    fence: Id
    environment: Environment
    purpose: Purpose
    account: ExecutionAccount
    mandate: ProviderMandateBinding
    source_draft_id: Id | None
    source_revision: int | None = Field(strict=True, ge=1)
    goal_id: Id
    goal_revision: int = Field(strict=True, ge=1)
    budget_owner_key: str = Field(min_length=1, max_length=256)
    target_set_digest: Digest
    before_state_digest: Digest | None
    after_state_digest: Digest | None
    dispatched_at: AwareDatetime
    observed_at: AwareDatetime
    outcome: Literal[
        "verified_effect", "verified_target_state", "verified_no_effect", "unknown", "conflict"
    ]
    evidence: Literal["exact_readback", "authoritative_no_effect", "unresolved", "mismatch"]
    resource_kind: str | None = Field(max_length=32)
    resource_name: str | None = Field(max_length=384)
    readback_digest: Digest | None
    effective_lower: AwareDatetime | None = None
    effective_upper: AwareDatetime | None = None
    effective_time_evidence: Literal["unavailable", "authoritative_interval"] = "unavailable"

    @model_validator(mode="after")
    def provenance(self) -> "NormalizedProviderReceipt":
        if (
            self.environment != self.mandate.environment
            or self.observed_at < self.dispatched_at
            or (self.sequence == 1) != (self.supersedes_receipt_id is None)
            or (self.source_draft_id is None) != (self.source_revision is None)
        ):
            raise ValueError("invalid immutable receipt lineage")
        verified = self.outcome in {"verified_effect", "verified_target_state"}
        if verified and (
            not self.resource_name
            or not self.resource_kind
            or not self.readback_digest
            or self.evidence != "exact_readback"
        ):
            raise ValueError("verified receipt requires scoped readback")
        if verified:
            provider = self.account.account.platform
            family = "customers" if provider == "google_ads" else provider.removesuffix("_ads")
            prefix = f"{family}/{self.account.external_advertiser_id}/"
            if (
                not self.resource_name
                or not self.resource_kind
                or not self.resource_name.startswith(prefix + self.resource_kind + "/")
                or not re.fullmatch(r"[A-Za-z0-9_/~.=-]+", self.resource_name)
            ):
                raise ValueError("foreign projected resource")
        if not verified and any(
            value is not None
            for value in [
                self.resource_kind,
                self.resource_name,
                self.readback_digest,
                self.after_state_digest,
            ]
        ):
            raise ValueError("unverified receipt cannot claim effects")
        if self.outcome == "verified_no_effect" and self.evidence != "authoritative_no_effect":
            raise ValueError("no-effect requires terminal authority")
        if self.effective_time_evidence == "authoritative_interval":
            if (
                not verified
                or self.purpose == "create_paused"
                or self.effective_lower is None
                or self.effective_upper is None
                or not self.dispatched_at
                <= self.effective_lower
                <= self.effective_upper
                <= self.observed_at
            ):
                raise ValueError("authoritative effect interval unavailable")
        elif self.effective_lower is not None or self.effective_upper is not None:
            raise ValueError("status observation is not treatment time")
        return self
