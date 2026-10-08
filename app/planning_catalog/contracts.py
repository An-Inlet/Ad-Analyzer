"""Strict planning inventory projection, independent of financial qualification."""

from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.collectors.account_diagnostic_contracts import validate_observation_period

Platform = Literal["google_ads", "meta_ads", "tiktok_ads"]
Kind = Literal["campaign", "adgroup", "adset"]
Digest = Annotated[str, Field(strict=True, pattern=r"^[a-f0-9]{64}$")]
Code = Annotated[str, Field(strict=True, pattern=r"^[a-z_]{1,100}$")]
NativeText = Annotated[str, Field(strict=True, min_length=1, max_length=100)]
Amount = Annotated[int, Field(strict=True, ge=0, le=10**15)]


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, revalidate_instances="always")


class TargetCatalogIntentV1(Frozen):
    account_id: int = Field(strict=True, gt=0)
    starts_at: AwareDatetime
    ends_at: AwareDatetime

    @model_validator(mode="after")
    def period(self) -> "TargetCatalogIntentV1":
        validate_observation_period(self.starts_at, self.ends_at)
        return self


class GoogleSettingsV1(Frozen):
    platform: Literal["google_ads"] = "google_ads"
    status: NativeText
    channel: NativeText | None
    bidding_strategy: NativeText | None
    starts_native: NativeText | None
    ends_native: NativeText | None
    budget_amount_micros: Amount | None
    budget_total_amount_micros: Amount | None
    budget_period: NativeText | None
    budget_status: NativeText | None
    budget_type: NativeText | None
    budget_explicitly_shared: bool | None = Field(strict=True)
    budget_reference_count: int | None = Field(strict=True, ge=0, le=1000000)


class MetaSettingsV1(Frozen):
    platform: Literal["meta_ads"] = "meta_ads"
    configured_status: NativeText
    effective_status: NativeText
    daily_budget_native: Amount | None
    lifetime_budget_native: Amount | None
    spend_cap_native: Amount | None
    unit_semantics: Literal["native_integer_unqualified"] = "native_integer_unqualified"
    starts_at: AwareDatetime | None
    ends_at: AwareDatetime | None
    budget_schedule_enabled: bool | None = Field(strict=True)
    budget_sharing_enabled: bool | None = Field(strict=True)
    budget_rebalance_enabled: bool | None = Field(strict=True)


class TikTokSettingsV1(Frozen):
    platform: Literal["tiktok_ads"] = "tiktok_ads"
    operation_status: NativeText
    secondary_status: NativeText | None
    budget_native: str | None = Field(strict=True, pattern=r"^[0-9]{1,16}(?:\.[0-9]{1,6})?$")
    unit_semantics: Literal["native_decimal_unqualified"] = "native_decimal_unqualified"
    budget_mode: NativeText | None
    budget_optimize_on: bool | None = Field(strict=True)
    campaign_type: NativeText | None
    objective_type: NativeText | None
    promotion_type: NativeText | None
    schedule_type: NativeText | None
    schedule_start_native: NativeText | None
    schedule_end_native: NativeText | None


Settings = Annotated[
    GoogleSettingsV1 | MetaSettingsV1 | TikTokSettingsV1, Field(discriminator="platform")
]


class TargetV1(Frozen):
    selection_key: Digest
    kind: Kind
    parent_selection_key: Digest | None
    budget_owner_key: Digest | None
    name: str | None = Field(strict=True, min_length=1, max_length=160)
    name_source: Literal["native_observation", "unavailable"]
    settings: Settings
    unavailable_fields: tuple[Code, ...] = Field(max_length=30)
    reasons: tuple[Code, ...] = Field(max_length=20)

    @model_validator(mode="after")
    def consistent(self) -> "TargetV1":
        if (self.name is None) != (self.name_source == "unavailable"):
            raise ValueError("name provenance mismatch")
        if (self.kind == "campaign") != (self.parent_selection_key is None):
            raise ValueError("target parent mismatch")
        if self.kind == "adset" and self.settings.platform != "meta_ads":
            raise ValueError("target platform mismatch")
        if self.kind == "adgroup" and self.settings.platform == "meta_ads":
            raise ValueError("target platform mismatch")
        return self


class CoverageV1(Frozen):
    kind: Kind
    status: Literal["complete", "partial", "unavailable"]
    observed_count: int = Field(strict=True, ge=0, le=200)
    scope: Literal[
        "provider_campaigns",
        "sdk_known_effective_statuses",
        "regular_campaign_families",
        "not_collected",
    ]
    reasons: tuple[Code, ...] = Field(max_length=20)

    @model_validator(mode="after")
    def consistent(self) -> "CoverageV1":
        if self.status == "complete" and self.scope != "provider_campaigns":
            raise ValueError("limited or missing inventory cannot be complete")
        if self.status != "complete" and not self.reasons:
            raise ValueError("incomplete coverage needs reasons")
        if self.status == "unavailable" and (self.observed_count or self.scope != "not_collected"):
            raise ValueError("unavailable coverage cannot contain observations")
        return self


class TargetCatalogV1(Frozen):
    schema_version: Literal["inlet.planning-target-catalog.v1"] = "inlet.planning-target-catalog.v1"
    workspace_id: int = Field(strict=True, gt=0)
    account_id: int = Field(strict=True, gt=0)
    connection_id: int = Field(strict=True, gt=0)
    platform: Platform
    connection_version: str = Field(strict=True, min_length=1, max_length=100)
    source_binding_digest: Digest
    inventory_digest: Digest
    currency: str = Field(strict=True, pattern=r"^[A-Z]{3}$")
    time_zone: str = Field(strict=True, min_length=1, max_length=64)
    reporting_starts_at: AwareDatetime
    reporting_ends_at: AwareDatetime
    observation_started_at: AwareDatetime
    observed_at: AwareDatetime
    expires_at: AwareDatetime
    coverage: tuple[CoverageV1, ...] = Field(min_length=2, max_length=2)
    targets: tuple[TargetV1, ...] = Field(max_length=400)
    advertising_writes_enabled: Literal[False] = False
    spending_authority: Literal["none"] = "none"
    atomic_snapshot: Literal[False] = False

    @model_validator(mode="after")
    def consistent(self) -> "TargetCatalogV1":
        try:
            ZoneInfo(self.time_zone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("catalog timezone invalid") from exc
        validate_observation_period(self.reporting_starts_at, self.reporting_ends_at)
        if (
            not self.reporting_ends_at
            <= self.observation_started_at
            <= self.observed_at
            < self.expires_at
        ):
            raise ValueError("catalog chronology invalid")
        expected = {"campaign", "adset" if self.platform == "meta_ads" else "adgroup"}
        if {v.kind for v in self.coverage} != expected:
            raise ValueError("exact platform coverage required")
        keys = {t.selection_key for t in self.targets}
        parents = {t.selection_key for t in self.targets if t.kind == "campaign"}
        if len(keys) != len(self.targets) or any(
            t.settings.platform != self.platform
            or t.kind not in expected
            or (t.parent_selection_key is not None and t.parent_selection_key not in parents)
            for t in self.targets
        ):
            raise ValueError("catalog target ownership graph invalid")
        if any(
            c.observed_count != sum(t.kind == c.kind for t in self.targets) for c in self.coverage
        ):
            raise ValueError("coverage count mismatch")
        return self
