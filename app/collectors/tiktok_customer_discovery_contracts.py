"""Bounded customer display only; native identifiers and credentials never appear."""

from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from app.collectors.tiktok_discovery_contracts import Frozen, IdentityType


class TikTokDiscoveryIntentV1(Frozen):
    account_id: int = Field(gt=0)
    identity_type: IdentityType


class TikTokPermissionDisplayV1(Frozen):
    name: Literal[
        "ads_only_mode",
        "is_gpppa",
        "can_push_video",
        "can_pull_video",
        "can_use_live_ads",
        "can_manage_message",
    ]
    state: Literal["true", "false", "absent", "null", "not_applicable", "unknown"]


class TikTokIdentityDisplayV1(Frozen):
    label: str = Field(min_length=1, max_length=120)
    status: Literal[
        "AVAILABLE",
        "NO_VALID_BIND_ACCOUNT",
        "SCOPE_UNAVAILABLE",
        "IS_PRIVATE_ACCOUNT",
        "NOT_BUSINESS_ACCOUNT",
        "absent",
        "null",
        "not_applicable",
        "unknown",
    ]
    permissions: tuple[TikTokPermissionDisplayV1, ...] = Field(max_length=6)
    reasons: tuple[Literal["custom_identity_phaseout", "identity_route_not_assessed"], ...]


EventReason = Literal[
    "event_deprecated",
    "event_deprecation_unknown",
    "event_not_optimizable",
    "optimization_event_unreported",
    "event_selection_not_assessed",
]


class TikTokEventDisplayV1(Frozen):
    label: str = Field(min_length=1, max_length=120)
    reasons: tuple[EventReason, ...] = Field(max_length=5)


class TikTokPixelDisplayV1(Frozen):
    label: str = Field(min_length=1, max_length=120)
    ownership: Literal["reported_owned", "shared", "unbound", "unknown"]
    events_count: int | None = Field(ge=0, le=1000)
    events_presence: Literal["absent", "null", "present"]
    events: tuple[TikTokEventDisplayV1, ...] = Field(max_length=20)
    events_display_truncated: bool
    reasons: tuple[Literal["pixel_scalar_shape_unverified", "tracking_readiness_unknown"], ...]


class TikTokDiscoveryViewV1(Frozen):
    schema_version: Literal["inlet.tiktok-customer-discovery.v1"] = (
        "inlet.tiktok-customer-discovery.v1"
    )
    account_id: int = Field(gt=0)
    identity_type: IdentityType
    status: Literal["observed", "unavailable"]
    reason: Literal["discovery_not_available", "business_center_selection_unavailable"] | None
    environment: Literal["contract_test"] | None
    collection_completeness: Literal["complete_requested_scope", "not_observed"]
    observed_started_at: AwareDatetime | None
    observed_ended_at: AwareDatetime | None
    identity_count: int | None = Field(ge=0, le=1000)
    pixel_count: int | None = Field(ge=0, le=200)
    event_count: int | None = Field(ge=0, le=200000)
    identities: tuple[TikTokIdentityDisplayV1, ...] = Field(max_length=20)
    pixels: tuple[TikTokPixelDisplayV1, ...] = Field(max_length=20)
    identities_display_truncated: bool
    pixels_display_truncated: bool
    display_truncated: bool
    publication_eligibility: Literal["not_assessed"] = "not_assessed"
    spending_authority: Literal["none"] = "none"

    @model_validator(mode="after")
    def consistency(self) -> "TikTokDiscoveryViewV1":
        if self.status == "unavailable":
            if (
                self.reason is None
                or self.environment is not None
                or self.collection_completeness != "not_observed"
                or any(
                    v is not None
                    for v in (
                        self.identity_count,
                        self.pixel_count,
                        self.event_count,
                        self.observed_started_at,
                        self.observed_ended_at,
                    )
                )
                or self.identities
                or self.pixels
                or self.display_truncated
                or self.identities_display_truncated
                or self.pixels_display_truncated
            ):
                raise ValueError("unavailable discovery has no observations")
        else:
            if (
                self.reason is not None
                or self.environment != "contract_test"
                or self.collection_completeness != "complete_requested_scope"
                or self.identity_count is None
                or self.pixel_count is None
                or self.observed_started_at is None
                or self.observed_ended_at is None
                or self.observed_ended_at < self.observed_started_at
                or len(self.identities) != min(20, self.identity_count)
                or len(self.pixels) != min(20, self.pixel_count)
                or self.identities_display_truncated != (self.identity_count > 20)
                or self.pixels_display_truncated != (self.pixel_count > 20)
            ):
                raise ValueError("inconsistent discovery display")
            if self.display_truncated != (
                self.identities_display_truncated
                or self.pixels_display_truncated
                or any(p.events_display_truncated for p in self.pixels)
            ):
                raise ValueError("inconsistent display truncation")
        return self
