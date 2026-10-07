"""Discovery-only TikTok response projections; never publication qualification."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

IdentityType = Literal["CUSTOMIZED_USER", "AUTH_CODE", "TT_USER", "BC_AUTH_TT"]
Applicability = Literal["applicable", "not_applicable", "unknown"]


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class ObservedFieldV1[T](Frozen):
    presence: Literal["absent", "null", "present"]
    applicability: Applicability = "unknown"
    recognition: Literal["recognized", "unrecognized", "not_evaluated"] = "not_evaluated"
    value: T | None = None

    @model_validator(mode="after")
    def consistent(self) -> "ObservedFieldV1[T]":
        if (self.presence == "present") != (self.value is not None):
            raise ValueError("field presence mismatch")
        if self.presence != "present" and self.recognition != "not_evaluated":
            raise ValueError("absent/null recognition unavailable")
        return self


class ObservedIdV1(ObservedFieldV1[str | int]):
    # The supplied table transcription omits exact native ID scalar type columns.
    scalar_shape_qualification: Literal["unverified"] = "unverified"

    @model_validator(mode="after")
    def bounded_id(self) -> "ObservedIdV1":
        if isinstance(self.value, str) and not 1 <= len(self.value) <= 128:
            raise ValueError("observed ID bounds")
        if isinstance(self.value, int) and not 0 <= self.value <= 2**64 - 1:
            raise ValueError("observed ID bounds")
        return self


class TikTokIdentityPageRequestV1(Frozen):
    schema_version: Literal["inlet.tiktok-identity-page-request.v1"] = (
        "inlet.tiktok-identity-page-request.v1"
    )
    advertiser_id: str = Field(min_length=1, max_length=128)
    identity_type: IdentityType
    identity_authorized_bc_id: str | None = Field(default=None, min_length=1, max_length=128)
    keyword: str | None = Field(default=None, min_length=1, max_length=128)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)

    @model_validator(mode="after")
    def applicable(self) -> "TikTokIdentityPageRequestV1":
        if (self.identity_type == "BC_AUTH_TT") != (self.identity_authorized_bc_id is not None):
            raise ValueError("exact BC identity scope required")
        if self.keyword is not None and self.identity_type != "CUSTOMIZED_USER":
            raise ValueError("keyword applies only to customized identities")
        return self


class TikTokPixelPageRequestV1(Frozen):
    schema_version: Literal["inlet.tiktok-pixel-page-request.v1"] = (
        "inlet.tiktok-pixel-page-request.v1"
    )
    advertiser_id: str = Field(min_length=1, max_length=128)
    code: str | None = Field(default=None, min_length=1, max_length=128)
    pixel_id: str | None = Field(default=None, min_length=1, max_length=128)
    name: str | None = Field(default=None, min_length=1, max_length=256)
    order_by: Literal["EARLIEST_CREATE", "LATEST_CREATE"]
    available_for_catalog_only: bool
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=20)


class TikTokPageInfoV1(Frozen):
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total_page: int = Field(ge=0)
    total_number: int = Field(ge=0)


class TikTokIdentityObservationV1(Frozen):
    identity_id: str = Field(min_length=1, max_length=128)
    identity_type: ObservedFieldV1[str]
    identity_authorized_bc_id: ObservedFieldV1[str]
    display_name: ObservedFieldV1[str]
    available_status: ObservedFieldV1[str]
    ads_only_mode: ObservedFieldV1[bool]
    is_gpppa: ObservedFieldV1[bool]
    can_push_video: ObservedFieldV1[bool]
    can_pull_video: ObservedFieldV1[bool]
    can_use_live_ads: ObservedFieldV1[bool]
    can_manage_message: ObservedFieldV1[bool]


class TikTokPixelOwnershipV1(Frozen):
    asset_relation_status: ObservedFieldV1[str]
    ownership_status: ObservedFieldV1[bool]
    owner_bc_id: ObservedFieldV1[str]


class TikTokPixelEventV1(Frozen):
    deprecated: ObservedFieldV1[bool]
    name: ObservedFieldV1[str]
    event_type: ObservedFieldV1[str]
    custom_event_type: ObservedFieldV1[str]
    event_code: ObservedFieldV1[str]
    event_id: ObservedIdV1
    optimization_event: ObservedFieldV1[str]
    statistic_type: ObservedFieldV1[str]
    currency: ObservedFieldV1[str]


class TikTokPixelObservationV1(Frozen):
    pixel_id: ObservedIdV1
    pixel_code: ObservedFieldV1[str]
    pixel_name: ObservedFieldV1[str]
    pixel_setup_mode: ObservedFieldV1[str]
    asset_ownership: ObservedFieldV1[TikTokPixelOwnershipV1]
    events: ObservedFieldV1[tuple[TikTokPixelEventV1, ...]]
    tracking_readiness: Literal["unknown"] = "unknown"


class TikTokIdentityPageV1(Frozen):
    schema_version: Literal["inlet.tiktok-identity-page.v1"] = "inlet.tiktok-identity-page.v1"
    request: TikTokIdentityPageRequestV1
    page_info: TikTokPageInfoV1
    identities: tuple[TikTokIdentityObservationV1, ...] = Field(max_length=100)
    collection_completeness: Literal["page_only"] = "page_only"
    pagination_consistency: Literal["unverified"] = "unverified"
    publication_eligibility: Literal["not_assessed"] = "not_assessed"
    spending_authority: Literal["none"] = "none"


class TikTokPixelPageV1(Frozen):
    schema_version: Literal["inlet.tiktok-pixel-page.v1"] = "inlet.tiktok-pixel-page.v1"
    request: TikTokPixelPageRequestV1
    page_info: TikTokPageInfoV1
    pixels: tuple[TikTokPixelObservationV1, ...] = Field(max_length=20)
    scalar_shape_qualification: Literal["unverified"] = "unverified"
    collection_completeness: Literal["page_only"] = "page_only"
    pagination_consistency: Literal["unverified"] = "unverified"
    publication_eligibility: Literal["not_assessed"] = "not_assessed"
    spending_authority: Literal["none"] = "none"
