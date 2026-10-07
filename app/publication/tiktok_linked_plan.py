"""Independent linked Push graph contracts; old social v1 remains unchanged."""

import re
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, field_validator, model_validator

from app.campaign_review.contracts import ReviewArtifact, TikTokVideo
from app.goals.schemas import StrictModel
from app.publication.contracts import PublicationScope, fingerprint
from app.publication.provider_contracts import Digest, Id, Micros
from app.publication.social_contracts import (
    NumericId,
    ProviderMediaBinding,
    SocialConfigurationApprovalRef,
    SocialFields,
    SocialProviderReceipt,
    SocialResourceRef,
    TikTokUploadCover,
    TikTokUploadVideo,
    social_resource,
)
from app.publication.tiktok_linked_contracts import LinkedIdentityV1, LinkedPushCreativeV1


class LinkedPushConfigurationV1(SocialFields):
    kind: Literal["tiktok_linked_push_v13"] = "tiktok_linked_push_v13"
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
    identity: LinkedIdentityV1
    rights_review_digest: Digest
    identity_observation_digest: Digest
    advertiser_observation_digest: Digest
    commercial_music_rights_reviewed: Literal[True]
    linked_post_creation_reviewed: Literal[True]
    dark_post_status: Literal["ON"]
    creative_authorized: Literal[False]
    creative_material_mode: Literal["CUSTOM"]
    ad_format: Literal["SINGLE_VIDEO"]
    video: ProviderMediaBinding
    cover: ProviderMediaBinding
    tracking_pixel_id: NumericId
    click_tracking_url: Literal[None]
    impression_tracking_url: Literal[None]

    @field_validator(
        "commercial_music_rights_reviewed",
        "linked_post_creation_reviewed",
        "creative_authorized",
        mode="before",
    )
    @classmethod
    def strict_rights(cls, value: object) -> object:
        if type(value) is not bool:
            raise ValueError("explicit reviewed boolean required")
        return value

    @model_validator(mode="after")
    def bounded_tiktok(self) -> "LinkedPushConfigurationV1":
        if (
            self.lifetime_budget_micros > self.reservation_micros
            or self.lifetime_budget_micros % (10 ** (6 - self.currency_decimal_places))
            or self.tracking_pixel_id != self.pixel_id
            or self.video.mime != "video/mp4"
            or self.cover.mime == "video/mp4"
            or self.video.media_id == self.cover.media_id
            or self.video.width * self.cover.height != self.cover.width * self.video.height
            or len(set(self.age_groups)) != len(self.age_groups)
            or any(not 1 <= len(v) <= 100 for v in self.location_ids_by_country.values())
            or any(not re.fullmatch(r"[A-Za-z_-]{2,16}", v) for v in self.language_codes.values())
        ):
            raise ValueError("invalid bounded TikTok profile")
        return self


class LinkedPushPublicationReviewV1(StrictModel):
    schema_version: Literal["inlet.tiktok-linked-push-review.v1"] = (
        "inlet.tiktok-linked-push-review.v1"
    )
    source: ReviewArtifact
    source_digest: Digest
    scope: PublicationScope
    configuration: LinkedPushConfigurationV1
    configuration_review: SocialConfigurationApprovalRef
    qualification_blockers: list[str] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def exact(self) -> "LinkedPushPublicationReviewV1":
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
            or scope.account.platform != "tiktok_ads"
            or not isinstance(d.content, TikTokVideo)
            or set(config.location_ids_by_country) != set(d.content.audience.countries)
            or set(config.language_codes) != set(d.content.audience.languages)
            or config.video.media_id != d.content.media.media_id
            or config.video.sha256 != d.content.media.sha256
            or d.content.media not in source.media
        ):
            raise ValueError("linked Push source/configuration mismatch")
        # Validate the exact reviewed copy/rights without guessing provider resource IDs.
        creative_for(self, "validation-video", "validation-cover")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


def creative_for(
    review: LinkedPushPublicationReviewV1, video_id: str, cover_id: str
) -> LinkedPushCreativeV1:
    content, config = review.source.definition.content, review.configuration
    if not isinstance(content, TikTokVideo):
        raise ValueError("linked Push video source required")
    return LinkedPushCreativeV1(
        route="push",
        identity=config.identity,
        ad_name=content.name,
        ad_format="SINGLE_VIDEO",
        dark_post_status=config.dark_post_status,
        operation_status="DISABLE",
        creative_authorized=config.creative_authorized,
        call_to_action=content.call_to_action,
        landing_page_url=content.landing_page,
        commercial_music_rights_reviewed=config.commercial_music_rights_reviewed,
        rights_review_digest=config.rights_review_digest,
        video_id=video_id,
        image_ids=(cover_id,),
        ad_text=content.text,
        media_review_digest=fingerprint(
            "inlet.linked-push-media.v1",
            {
                "video": config.video.model_dump(mode="json"),
                "cover": config.cover.model_dump(mode="json"),
            },
        ),
        linked_post_creation_reviewed=config.linked_post_creation_reviewed,
    )


class LinkedPushCampaignV1(StrictModel):
    kind: Literal["tiktok_linked_push_campaign"] = "tiktok_linked_push_campaign"
    name: str
    configuration: LinkedPushConfigurationV1
    operation_status: Literal["DISABLE"] = "DISABLE"


class LinkedPushAdGroupV1(StrictModel):
    kind: Literal["tiktok_linked_push_adgroup"] = "tiktok_linked_push_adgroup"
    name: str
    campaign: SocialResourceRef
    configuration: LinkedPushConfigurationV1
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    operation_status: Literal["DISABLE"] = "DISABLE"


class LinkedPushAdV1(StrictModel):
    kind: Literal["tiktok_linked_push_ad"] = "tiktok_linked_push_ad"
    adgroup: SocialResourceRef
    video: SocialResourceRef
    cover: SocialResourceRef


LinkedPushOperationV1 = Annotated[
    TikTokUploadVideo
    | TikTokUploadCover
    | LinkedPushCampaignV1
    | LinkedPushAdGroupV1
    | LinkedPushAdV1,
    Field(discriminator="kind"),
]
LINKED_OUTPUTS: dict[str, Literal["videos", "images", "campaigns", "adgroups", "ads"]] = {
    "tiktok_upload_video": "videos",
    "tiktok_upload_cover": "images",
    "tiktok_linked_push_campaign": "campaigns",
    "tiktok_linked_push_adgroup": "adgroups",
    "tiktok_linked_push_ad": "ads",
}


class LinkedPushStepV1(StrictModel):
    step_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,31}$")
    dependencies: list[str] = Field(max_length=5)
    operation: LinkedPushOperationV1


class LinkedPushPlanV1(StrictModel):
    schema_version: Literal["inlet.tiktok-linked-push-plan.v1"] = "inlet.tiktok-linked-push-plan.v1"
    compiler_id: Literal["tiktok_linked_push_v13_v1"] = "tiktok_linked_push_v13_v1"
    api_version: Literal["v1.3"] = "v1.3"
    review: LinkedPushPublicationReviewV1
    review_digest: Digest
    steps: list[LinkedPushStepV1] = Field(min_length=5, max_length=5)
    publication_eligible: Literal[False] = False

    @model_validator(mode="after")
    def exact_graph(self) -> "LinkedPushPlanV1":
        if self.review.digest() != self.review_digest or self.steps != canonical_steps(self.review):
            raise ValueError("exact reviewed linked graph required")
        if len(self.model_dump_json().encode()) > 262144:
            raise ValueError("linked graph exceeds bound")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


def canonical_steps(review: LinkedPushPublicationReviewV1) -> list[LinkedPushStepV1]:
    c, d = review.configuration, review.source.definition

    def ref(
        name: str, kind: Literal["campaigns", "adgroups", "videos", "images"]
    ) -> SocialResourceRef:
        return SocialResourceRef(step_id=name, kind=kind)

    return [
        LinkedPushStepV1(
            step_id="video", dependencies=[], operation=TikTokUploadVideo(video=c.video)
        ),
        LinkedPushStepV1(
            step_id="cover", dependencies=["video"], operation=TikTokUploadCover(cover=c.cover)
        ),
        LinkedPushStepV1(
            step_id="campaign",
            dependencies=["video", "cover"],
            operation=LinkedPushCampaignV1(name=d.content.name, configuration=c),
        ),
        LinkedPushStepV1(
            step_id="adgroup",
            dependencies=["campaign"],
            operation=LinkedPushAdGroupV1(
                name=d.content.name,
                campaign=ref("campaign", "campaigns"),
                configuration=c,
                starts_at=d.starts_at,
                ends_at=d.ends_at,
            ),
        ),
        LinkedPushStepV1(
            step_id="ad",
            dependencies=["video", "cover", "campaign", "adgroup"],
            operation=LinkedPushAdV1(
                adgroup=ref("adgroup", "adgroups"),
                video=ref("video", "videos"),
                cover=ref("cover", "images"),
            ),
        ),
    ]


def compile_linked_push(review: LinkedPushPublicationReviewV1) -> LinkedPushPlanV1:
    review = LinkedPushPublicationReviewV1.model_validate_json(review.model_dump_json())
    return LinkedPushPlanV1(
        review=review, review_digest=review.digest(), steps=canonical_steps(review)
    )


class LinkedPushBoundRequestV1(StrictModel):
    schema_version: Literal["inlet.tiktok-linked-push-request.v1"] = (
        "inlet.tiktok-linked-push-request.v1"
    )
    plan_id: Id
    plan_digest: Digest
    review_digest: Digest
    scope: PublicationScope
    api_version: Literal["v1.3"] = "v1.3"
    step: LinkedPushStepV1
    # The exact review is required for ad-copy/identity binding at serializer time.
    review: LinkedPushPublicationReviewV1
    resources: dict[str, str] = Field(max_length=4)
    fence: Id
    dispatched_at: AwareDatetime

    @model_validator(mode="after")
    def original(self) -> "LinkedPushBoundRequestV1":
        plan = compile_linked_push(self.review)
        if (
            self.scope != self.review.scope
            or self.review.digest() != self.review_digest
            or plan.digest() != self.plan_digest
            or self.step not in plan.steps
        ):
            raise ValueError("linked request requires exact reviewed original graph")
        refs = {
            v.step_id: v
            for v in self.step.operation.__dict__.values()
            if isinstance(v, SocialResourceRef)
        }
        if self.resources.keys() != refs.keys():
            raise ValueError("exact linked dependencies required")
        for name, ref in refs.items():
            social_resource(self.scope, self.resources[name], ref.kind)
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


def materialize_linked_push(
    plan: LinkedPushPlanV1,
    plan_id: str,
    step_id: str,
    receipts: dict[str, SocialProviderReceipt],
    requests: dict[str, LinkedPushBoundRequestV1],
    fence: str,
    now: datetime,
) -> LinkedPushBoundRequestV1:
    """Resolve only exact, verified original dependencies from the durable archive."""
    plan = LinkedPushPlanV1.model_validate_json(plan.model_dump_json())
    step = next((value for value in plan.steps if value.step_id == step_id), None)
    if step is None:
        raise ValueError("unknown linked step")
    refs = {
        value.step_id
        for value in step.operation.__dict__.values()
        if isinstance(value, SocialResourceRef)
    }
    resources: dict[str, str] = {}
    for dependency in step.dependencies:
        receipt, request = receipts.get(dependency), requests.get(dependency)
        if receipt is None or request is None:
            raise ValueError("verified linked dependency required")
        receipt = SocialProviderReceipt.model_validate_json(receipt.model_dump_json())
        request = LinkedPushBoundRequestV1.model_validate_json(request.model_dump_json())
        original = next(value for value in plan.steps if value.step_id == dependency)
        if (
            receipt.outcome != "verified_effect"
            or receipt.scope != plan.review.scope
            or receipt.plan_id != plan_id
            or receipt.plan_digest != plan.digest()
            or receipt.step_id != dependency
            or receipt.fence != request.fence
            or receipt.request_digest != request.digest()
            or receipt.resource_kind != LINKED_OUTPUTS[original.operation.kind]
            or request.plan_id != plan_id
            or request.plan_digest != plan.digest()
            or request.scope != plan.review.scope
            or request.step != original
            or request.review_digest != plan.review_digest
            or request.api_version != plan.api_version
            or not request.dispatched_at <= receipt.observed_at <= now
        ):
            raise ValueError("stale or foreign linked dependency")
        if dependency in refs:
            assert receipt.resource_name is not None
            resources[dependency] = receipt.resource_name
    return LinkedPushBoundRequestV1(
        plan_id=plan_id,
        plan_digest=plan.digest(),
        review_digest=plan.review_digest,
        scope=plan.review.scope,
        step=step,
        review=plan.review,
        resources=resources,
        fence=fence,
        dispatched_at=now,
    )
