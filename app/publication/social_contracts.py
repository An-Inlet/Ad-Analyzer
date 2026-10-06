"""Additive Meta/TikTok provider contracts. Existing Google/fixture hashes stay unchanged.

These are bounded manual profiles with explicit qualification blockers. SDK field
existence is not authority or proof that a field combination is eligible.
"""

import re
from datetime import datetime
from typing import Annotated, Literal, Protocol
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, Field, SecretStr, model_validator

from app.campaign_review.contracts import MetaImage, ReviewArtifact, TikTokVideo
from app.goals.schemas import StrictModel
from app.publication.contracts import PublicationScope, fingerprint
from app.publication.provider_contracts import Digest, Id, Micros

NumericId = Annotated[str, Field(pattern=r"^[0-9]{1,32}$")]
OpaqueId = Annotated[str, Field(pattern=r"^[A-Za-z0-9_.=-]{1,256}$")]
ResourceKind = Literal["campaigns", "adsets", "adgroups", "creatives", "ads", "images", "videos"]


class ProviderMediaBinding(StrictModel):
    media_id: Id
    sha256: Digest
    byte_size: int = Field(strict=True, gt=0, le=512 * 1024 * 1024)
    mime: Literal["image/png", "image/jpeg", "video/mp4"]
    width: int = Field(strict=True, gt=0, le=16384)
    height: int = Field(strict=True, gt=0, le=16384)
    duration_ms: int | None = Field(default=None, strict=True, gt=0, le=600000)
    validation_version: Literal["image_v1", "video_v1"]
    validation_digest: Digest

    @model_validator(mode="after")
    def valid_media(self) -> "ProviderMediaBinding":
        if self.mime == "video/mp4":
            if self.duration_ms is None or self.validation_version != "video_v1":
                raise ValueError("validated video metadata required")
        elif (
            self.duration_ms is not None
            or self.validation_version != "image_v1"
            or self.byte_size > 8 * 1024 * 1024
            or self.width * self.height > 16_000_000
        ):
            raise ValueError("invalid bounded image metadata")
        return self


class MetaAttribution(StrictModel):
    event_type: Literal["CLICK_THROUGH", "VIEW_THROUGH"]
    window_days: Literal[1, 7]


class SocialFields(StrictModel):
    account_timezone: str = Field(min_length=1, max_length=64)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    reservation_micros: Micros
    budget_semantics: Literal["lifetime_budget_not_independent_hard_cap"]
    activation_policy: Literal["separate_exact_approval"]
    automation_omission_policy: Literal["no_optional_assets_or_automation_requested"]

    @model_validator(mode="after")
    def timezone_valid(self) -> "SocialFields":
        ZoneInfo(self.account_timezone)
        return self


class MetaImagePublicationFields(SocialFields):
    kind: Literal["meta_image_v26"] = "meta_image_v26"
    currency_minor_unit_exponent: int = Field(strict=True, ge=0, le=3)
    adset_lifetime_budget_micros: Micros
    page_id: NumericId
    pixel_id: NumericId
    conversion_event: Literal["PURCHASE"]
    objective: Literal["OUTCOME_SALES"]
    buying_type: Literal["AUCTION"]
    bid_strategy: Literal["LOWEST_COST_WITHOUT_CAP"]
    optimization_goal: Literal["OFFSITE_CONVERSIONS"]
    billing_event: Literal["IMPRESSIONS"]
    destination_type: Literal["WEBSITE"]
    attribution: list[MetaAttribution] = Field(min_length=1, max_length=2)
    attribution_count_type: Literal["ALL_CONVERSIONS"]
    countries: list[str] = Field(min_length=1, max_length=20)
    language_locale_ids: dict[str, int] = Field(min_length=1, max_length=10)
    age_min: int = Field(strict=True, ge=18, le=65)
    age_max: int = Field(strict=True, ge=18, le=65)
    publisher_platforms: list[Literal["facebook"]] = Field(min_length=1, max_length=1)
    facebook_positions: list[Literal["feed"]] = Field(min_length=1, max_length=1)
    advantage_audience: Literal[0]
    dynamic_creative: Literal[False]
    is_adset_budget_sharing_enabled: Literal[False]
    special_ad_categories: list[str] = Field(max_length=0)
    special_ad_category_declaration: Literal["none_applicable"]
    dsa_beneficiary: str | None = Field(max_length=200)
    dsa_payor: str | None = Field(max_length=200)
    url_tags: str = Field(max_length=2048)
    image: ProviderMediaBinding

    @model_validator(mode="after")
    def bounded_meta(self) -> "MetaImagePublicationFields":
        if (
            self.adset_lifetime_budget_micros > self.reservation_micros
            or self.adset_lifetime_budget_micros % (10 ** (6 - self.currency_minor_unit_exponent))
            or self.age_min > self.age_max
            or self.image.mime == "video/mp4"
            or len({v.event_type for v in self.attribution}) != len(self.attribution)
            or any(type(v) is not int or v <= 0 for v in self.language_locale_ids.values())
        ):
            raise ValueError("invalid bounded Meta profile")
        return self


class TikTokVideoPublicationFields(SocialFields):
    kind: Literal["tiktok_video_v13"] = "tiktok_video_v13"
    currency_decimal_places: int = Field(strict=True, ge=0, le=3)
    lifetime_budget_micros: Micros
    objective_type: Literal["WEB_CONVERSIONS"]
    promotion_type: Literal["WEBSITE"]
    campaign_type: Literal["REGULAR_CAMPAIGN"]
    budget_optimize_on: Literal[False]
    campaign_budget_mode: Literal["BUDGET_MODE_TOTAL"]
    adgroup_budget_mode: Literal["BUDGET_MODE_TOTAL"]
    placement_type: Literal["PLACEMENT_TYPE_NORMAL"]
    placements: list[Literal["PLACEMENT_TIKTOK"]] = Field(min_length=1, max_length=1)
    pixel_id: NumericId
    optimization_event: Literal["SHOPPING"]
    optimization_goal: Literal["CONVERT"]
    billing_event: Literal["OCPM"]
    bid_type: Literal["BID_TYPE_NO_BID"]
    pacing: Literal["PACING_MODE_SMOOTH"]
    schedule_type: Literal["SCHEDULE_START_END"]
    schedule_wire_timezone: Literal["UTC"]
    click_attribution_window: Literal["ONE_DAY", "SEVEN_DAYS"]
    view_attribution_window: Literal["OFF", "ONE_DAY"]
    engaged_view_attribution_window: Literal["OFF", "ONE_DAY"]
    attribution_event_count: Literal["EVERY"]
    location_ids_by_country: dict[str, list[NumericId]] = Field(min_length=1, max_length=20)
    language_codes: dict[str, str] = Field(min_length=1, max_length=10)
    age_groups: list[Literal["AGE_18_24", "AGE_25_34", "AGE_35_44", "AGE_45_54", "AGE_55_100"]] = (
        Field(min_length=1, max_length=5)
    )
    gender: Literal["GENDER_UNLIMITED"]
    smart_audience_enabled: Literal[False]
    smart_interest_behavior_enabled: Literal[False]
    search_result_enabled: Literal[False]
    comment_disabled: bool = Field(strict=True)
    share_disabled: bool = Field(strict=True)
    video_download_disabled: bool = Field(strict=True)
    identity_type: Literal["CUSTOMIZED_USER"]
    identity_id: OpaqueId
    creative_material_mode: Literal["CUSTOM"]
    ad_format: Literal["SINGLE_VIDEO"]
    video: ProviderMediaBinding
    cover: ProviderMediaBinding
    tracking_pixel_id: NumericId
    click_tracking_url: Literal[None]
    impression_tracking_url: Literal[None]

    @model_validator(mode="after")
    def bounded_tiktok(self) -> "TikTokVideoPublicationFields":
        if (
            self.lifetime_budget_micros > self.reservation_micros
            or self.lifetime_budget_micros % (10 ** (6 - self.currency_decimal_places))
            or self.tracking_pixel_id != self.pixel_id
            or self.video.mime != "video/mp4"
            or self.cover.mime == "video/mp4"
            or self.video.media_id == self.cover.media_id
            or len(set(self.age_groups)) != len(self.age_groups)
            or any(not 1 <= len(v) <= 100 for v in self.location_ids_by_country.values())
            or any(not re.fullmatch(r"[A-Za-z_-]{2,16}", v) for v in self.language_codes.values())
        ):
            raise ValueError("invalid bounded TikTok profile")
        return self


SocialConfiguration = Annotated[
    MetaImagePublicationFields | TikTokVideoPublicationFields, Field(discriminator="kind")
]


class SocialPublicationReview(StrictModel):
    schema_version: Literal["inlet.social-publication-review.v1"] = (
        "inlet.social-publication-review.v1"
    )
    source: ReviewArtifact
    source_digest: Digest
    scope: PublicationScope
    configuration: SocialConfiguration
    # Still unqualified combinations: later server evidence extension must explicitly
    # replace this requirement, never interpret SDK enum presence as qualification.
    qualification_blockers: list[str] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def binding(self) -> "SocialPublicationReview":
        source, scope, config = self.source, self.scope, self.configuration
        d = source.definition
        if (
            source.fingerprint() != self.source_digest
            or not source.offline_reviewable
            or source.blockers
            or source.workspace_id != scope.workspace_id
            or d.account != scope.account
            or source.connection_version != scope.connection_version
            or d.mandate_id != scope.mandate_id
            or d.mandate_revision != scope.mandate_revision
            or config.currency != d.currency
            or config.reservation_micros != d.budget_micros
            or not re.fullmatch(r"[0-9]{1,32}", scope.external_advertiser_id)
        ):
            raise ValueError("social source binding mismatch")
        if isinstance(config, MetaImagePublicationFields):
            if not isinstance(d.content, MetaImage) or scope.account.platform != "meta_ads":
                raise ValueError("Meta source required")
            countries, languages, media = (
                set(config.countries),
                set(config.language_locale_ids),
                config.image,
            )
        else:
            if not isinstance(d.content, TikTokVideo) or scope.account.platform != "tiktok_ads":
                raise ValueError("TikTok source required")
            countries, languages, media = (
                set(config.location_ids_by_country),
                set(config.language_codes),
                config.video,
            )
        if (
            countries != set(d.content.audience.countries)
            or languages != set(d.content.audience.languages)
            or media.media_id != d.content.media.media_id
            or media.sha256 != d.content.media.sha256
            or d.content.media not in source.media
        ):
            raise ValueError("social audience/media mismatch")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class SocialResourceRef(StrictModel):
    step_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,31}$")
    kind: ResourceKind
    output: Literal["resource_name"] = "resource_name"


class MetaUploadImage(StrictModel):
    kind: Literal["meta_upload_image"] = "meta_upload_image"
    image: ProviderMediaBinding


class MetaCreatePausedCampaign(StrictModel):
    kind: Literal["meta_create_paused_campaign"] = "meta_create_paused_campaign"
    name: str = Field(min_length=1, max_length=120)
    configuration: MetaImagePublicationFields
    status: Literal["PAUSED"] = "PAUSED"


class MetaCreatePausedAdSet(StrictModel):
    kind: Literal["meta_create_paused_adset"] = "meta_create_paused_adset"
    name: str = Field(min_length=1, max_length=120)
    campaign: SocialResourceRef
    configuration: MetaImagePublicationFields
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    status: Literal["PAUSED"] = "PAUSED"


class MetaCreateImageCreative(StrictModel):
    kind: Literal["meta_create_image_creative"] = "meta_create_image_creative"
    name: str = Field(min_length=1, max_length=120)
    image: SocialResourceRef
    configuration: MetaImagePublicationFields
    content: MetaImage


class MetaCreatePausedAd(StrictModel):
    kind: Literal["meta_create_paused_ad"] = "meta_create_paused_ad"
    name: str = Field(min_length=1, max_length=120)
    adset: SocialResourceRef
    creative: SocialResourceRef
    status: Literal["PAUSED"] = "PAUSED"


class TikTokUploadVideo(StrictModel):
    kind: Literal["tiktok_upload_video"] = "tiktok_upload_video"
    video: ProviderMediaBinding


class TikTokUploadCover(StrictModel):
    kind: Literal["tiktok_upload_cover"] = "tiktok_upload_cover"
    cover: ProviderMediaBinding


class TikTokCreateDisabledCampaign(StrictModel):
    kind: Literal["tiktok_create_disabled_campaign"] = "tiktok_create_disabled_campaign"
    name: str = Field(min_length=1, max_length=120)
    configuration: TikTokVideoPublicationFields
    operation_status: Literal["DISABLE"] = "DISABLE"


class TikTokCreateDisabledAdGroup(StrictModel):
    kind: Literal["tiktok_create_disabled_adgroup"] = "tiktok_create_disabled_adgroup"
    name: str = Field(min_length=1, max_length=120)
    campaign: SocialResourceRef
    configuration: TikTokVideoPublicationFields
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    operation_status: Literal["DISABLE"] = "DISABLE"


class TikTokCreateDisabledVideoAd(StrictModel):
    kind: Literal["tiktok_create_disabled_video_ad"] = "tiktok_create_disabled_video_ad"
    name: str = Field(min_length=1, max_length=120)
    adgroup: SocialResourceRef
    video: SocialResourceRef
    cover: SocialResourceRef
    configuration: TikTokVideoPublicationFields
    content: TikTokVideo
    operation_status: Literal["DISABLE"] = "DISABLE"


SocialOperation = Annotated[
    MetaUploadImage
    | MetaCreatePausedCampaign
    | MetaCreatePausedAdSet
    | MetaCreateImageCreative
    | MetaCreatePausedAd
    | TikTokUploadVideo
    | TikTokUploadCover
    | TikTokCreateDisabledCampaign
    | TikTokCreateDisabledAdGroup
    | TikTokCreateDisabledVideoAd,
    Field(discriminator="kind"),
]

OUTPUT_KINDS: dict[str, ResourceKind] = {
    "meta_upload_image": "images",
    "meta_create_paused_campaign": "campaigns",
    "meta_create_paused_adset": "adsets",
    "meta_create_image_creative": "creatives",
    "meta_create_paused_ad": "ads",
    "tiktok_upload_video": "videos",
    "tiktok_upload_cover": "images",
    "tiktok_create_disabled_campaign": "campaigns",
    "tiktok_create_disabled_adgroup": "adgroups",
    "tiktok_create_disabled_video_ad": "ads",
}
REF_KINDS: dict[str, ResourceKind] = {
    "campaign": "campaigns",
    "adset": "adsets",
    "creative": "creatives",
    "adgroup": "adgroups",
    "video": "videos",
    "cover": "images",
    "image": "images",
}


def social_refs(operation: SocialOperation) -> list[SocialResourceRef]:
    refs: list[SocialResourceRef] = []
    for name, value in operation.__dict__.items():
        if isinstance(value, SocialResourceRef):
            if value.kind != REF_KINDS[name]:
                raise ValueError("wrong dependency resource kind")
            refs.append(value)
    return refs


class SocialPublishStep(StrictModel):
    step_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,31}$")
    dependencies: list[str] = Field(max_length=16)
    operation: SocialOperation

    @model_validator(mode="after")
    def media_kind(self) -> "SocialPublishStep":
        op = self.operation
        if isinstance(op, (MetaUploadImage, TikTokUploadCover)):
            binding = op.image if isinstance(op, MetaUploadImage) else op.cover
            if binding.mime == "video/mp4":
                raise ValueError("image operation requires image media")
        if isinstance(op, TikTokUploadVideo) and op.video.mime != "video/mp4":
            raise ValueError("video operation requires validated video")
        social_refs(op)
        return self


class SocialPublishPlan(StrictModel):
    schema_version: Literal["inlet.social-publish-plan.v1"] = "inlet.social-publish-plan.v1"
    compiler_id: Literal["meta_image_v26_v1", "tiktok_video_v13_v1"]
    api_version: Literal["v26.0", "v1.3"]
    review: SocialPublicationReview
    review_digest: Digest
    steps: list[SocialPublishStep] = Field(min_length=1, max_length=16)
    publication_eligible: Literal[False] = False

    @model_validator(mode="after")
    def bound_dag(self) -> "SocialPublishPlan":
        is_meta = isinstance(self.review.configuration, MetaImagePublicationFields)
        expected = ("meta_image_v26_v1", "v26.0") if is_meta else ("tiktok_video_v13_v1", "v1.3")
        prefix = "meta_" if is_meta else "tiktok_"
        if (
            self.compiler_id,
            self.api_version,
        ) != expected or self.review.digest() != self.review_digest:
            raise ValueError("social compiler/review mismatch")
        seen: dict[str, ResourceKind] = {}
        for step in self.steps:
            if (
                step.step_id in seen
                or not set(step.dependencies) <= seen.keys()
                or len(set(step.dependencies)) != len(step.dependencies)
                or not step.operation.kind.startswith(prefix)
            ):
                raise ValueError("invalid social DAG")
            op = step.operation
            source = self.review.source.definition
            if (
                getattr(op, "configuration", self.review.configuration) != self.review.configuration
                or getattr(op, "content", source.content) != source.content
                or getattr(op, "name", source.content.name) != source.content.name
                or getattr(op, "starts_at", source.starts_at) != source.starts_at
                or getattr(op, "ends_at", source.ends_at) != source.ends_at
            ):
                raise ValueError("unreviewed social operation fields")
            if isinstance(op, MetaUploadImage) and op.image != getattr(
                self.review.configuration, "image", None
            ):
                raise ValueError("unreviewed image")
            if isinstance(op, TikTokUploadVideo) and op.video != getattr(
                self.review.configuration, "video", None
            ):
                raise ValueError("unreviewed video")
            if isinstance(op, TikTokUploadCover) and op.cover != getattr(
                self.review.configuration, "cover", None
            ):
                raise ValueError("unreviewed cover")
            for ref in social_refs(step.operation):
                if ref.step_id not in step.dependencies or seen.get(ref.step_id) != ref.kind:
                    raise ValueError("unbound social resource kind")
            seen[step.step_id] = OUTPUT_KINDS[step.operation.kind]
        if len(self.model_dump_json().encode()) > 262144:
            raise ValueError("social plan exceeds bound")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


def social_resource(scope: PublicationScope, value: str, kind: ResourceKind) -> str:
    provider = {"meta_ads": "meta", "tiktok_ads": "tiktok"}.get(scope.account.platform)
    if provider is None:
        raise ValueError("unsupported social provider")
    prefix = f"{provider}/{scope.external_advertiser_id}/{kind}/"
    suffix = r"[A-Za-z0-9_.=-]{1,256}" if kind in {"images", "videos"} else r"[0-9]{1,32}"
    if not re.fullmatch(re.escape(prefix) + suffix, value):
        raise ValueError("foreign or wrong-kind social resource")
    return value[len(prefix) :]


class SocialBoundRequest(StrictModel):
    plan_id: Id
    plan_digest: Digest
    review_digest: Digest
    scope: PublicationScope
    api_version: Literal["v26.0", "v1.3"]
    step: SocialPublishStep
    resources: dict[str, str] = Field(max_length=16)
    fence: Id
    dispatched_at: AwareDatetime

    @model_validator(mode="after")
    def binding(self) -> "SocialBoundRequest":
        provider = self.scope.account.platform
        prefix, version = ("meta_", "v26.0") if provider == "meta_ads" else ("tiktok_", "v1.3")
        if (
            provider not in {"meta_ads", "tiktok_ads"}
            or self.api_version != version
            or not self.step.operation.kind.startswith(prefix)
        ):
            raise ValueError("social request provider mismatch")
        refs = social_refs(self.step.operation)
        if set(self.resources) != {ref.step_id for ref in refs}:
            raise ValueError("exact social references required")
        for ref in refs:
            social_resource(self.scope, self.resources[ref.step_id], ref.kind)
        return self

    def digest(self) -> str:
        return fingerprint("inlet.bound-social-request.v1", self.model_dump(mode="json"))


class SocialProviderReceipt(StrictModel):
    scope: PublicationScope
    plan_id: Id
    plan_digest: Digest
    step_id: str
    fence: Id
    request_digest: Digest
    outcome: Literal["verified_effect", "verified_no_effect", "unknown", "conflict"]
    resource_kind: ResourceKind
    resource_name: str | None = Field(default=None, max_length=384)
    readback_digest: Digest | None = None
    evidence: Literal["exact_readback", "unresolved", "mismatch", "authoritative_no_effect"]
    observed_at: AwareDatetime

    @model_validator(mode="after")
    def evidence_binding(self) -> "SocialProviderReceipt":
        if self.outcome == "verified_effect":
            if (
                not self.resource_name
                or not self.readback_digest
                or self.evidence != "exact_readback"
            ):
                raise ValueError("verified social readback required")
            social_resource(self.scope, self.resource_name, self.resource_kind)
        elif self.resource_name is not None or self.readback_digest is not None:
            raise ValueError("unverified social resource cannot bind dependencies")
        if self.outcome == "verified_no_effect" and self.evidence != "authoritative_no_effect":
            raise ValueError("authoritative no-effect proof required")
        return self


class SocialProviderResponse(StrictModel):
    request_digest: Digest
    resource_name: str | None = Field(default=None, max_length=384)
    outcome: Literal["acknowledged", "unknown"]


class SocialValidationEvidence(StrictModel):
    request_digest: Digest
    kind: Literal["local_schema", "provider_validate_only", "unsupported"]
    valid: bool
    publication_authorized: Literal[False] = False

    @model_validator(mode="after")
    def unsupported_is_not_validated(self) -> "SocialValidationEvidence":
        if self.kind == "unsupported" and self.valid:
            raise ValueError("unsupported validation cannot succeed")
        return self


class SocialProviderContext(StrictModel):
    scope: PublicationScope
    access_token: SecretStr = Field(exclude=True, repr=False)
    app_secret: SecretStr | None = Field(default=None, exclude=True, repr=False)
    expires_at: AwareDatetime


class ProviderMediaReader(Protocol):
    def read_verified(self, workspace_id: int, binding: ProviderMediaBinding) -> bytes: ...


class SocialPublicationTransport(Protocol):
    def validate_only(
        self, request: SocialBoundRequest, context: SocialProviderContext, now: datetime
    ) -> SocialValidationEvidence: ...
    def apply_once(
        self, request: SocialBoundRequest, context: SocialProviderContext, now: datetime
    ) -> SocialProviderResponse: ...
    def read_back(
        self,
        request: SocialBoundRequest,
        response: SocialProviderResponse,
        context: SocialProviderContext,
        now: datetime,
    ) -> SocialProviderReceipt: ...
    def reconcile(
        self,
        request: SocialBoundRequest,
        history: list[SocialProviderResponse],
        context: SocialProviderContext,
        now: datetime,
    ) -> SocialProviderReceipt: ...


def get_social_publication_transport() -> SocialPublicationTransport | None:
    return None
