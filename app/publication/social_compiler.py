"""Canonical bounded social graphs; compilation is never publication authority."""

from datetime import datetime

from app.campaign_review.contracts import MetaImage, TikTokVideo
from app.publication.social_contracts import (
    OUTPUT_KINDS,
    MetaCreateImageCreative,
    MetaCreatePausedAd,
    MetaCreatePausedAdSet,
    MetaCreatePausedCampaign,
    MetaImagePublicationFields,
    MetaUploadImage,
    ResourceKind,
    SocialBoundRequest,
    SocialOperation,
    SocialProviderReceipt,
    SocialPublicationReview,
    SocialPublishPlan,
    SocialPublishStep,
    SocialResourceRef,
    TikTokCreateDisabledAdGroup,
    TikTokCreateDisabledCampaign,
    TikTokCreateDisabledVideoAd,
    TikTokUploadCover,
    TikTokUploadVideo,
    social_refs,
)


def compile_social(review: SocialPublicationReview) -> SocialPublishPlan:
    review = SocialPublicationReview.model_validate(review.model_dump())
    d, f = review.source.definition, review.configuration
    steps: list[SocialPublishStep] = []

    def ref(step: str, kind: ResourceKind) -> SocialResourceRef:
        return SocialResourceRef(step_id=step, kind=kind)

    def add(key: str, op: SocialOperation, dependencies: list[str]) -> None:
        steps.append(SocialPublishStep(step_id=key, operation=op, dependencies=dependencies))

    if isinstance(f, MetaImagePublicationFields):
        assert isinstance(d.content, MetaImage)
        add("image", MetaUploadImage(image=f.image), [])
        add("campaign", MetaCreatePausedCampaign(name=d.content.name, configuration=f), ["image"])
        add(
            "adset",
            MetaCreatePausedAdSet(
                name=d.content.name,
                configuration=f,
                campaign=ref("campaign", "campaigns"),
                starts_at=d.starts_at,
                ends_at=d.ends_at,
            ),
            ["campaign"],
        )
        add(
            "creative",
            MetaCreateImageCreative(
                name=d.content.name,
                configuration=f,
                image=ref("image", "images"),
                content=d.content,
            ),
            ["image", "adset"],
        )
        add(
            "ad",
            MetaCreatePausedAd(
                name=d.content.name,
                adset=ref("adset", "adsets"),
                creative=ref("creative", "creatives"),
            ),
            [s.step_id for s in steps],
        )
        compiler, version = "meta_image_v26_v1", "v26.0"
    else:
        assert isinstance(d.content, TikTokVideo)
        add("video", TikTokUploadVideo(video=f.video), [])
        add("cover", TikTokUploadCover(cover=f.cover), ["video"])
        add(
            "campaign",
            TikTokCreateDisabledCampaign(name=d.content.name, configuration=f),
            ["video", "cover"],
        )
        add(
            "adgroup",
            TikTokCreateDisabledAdGroup(
                name=d.content.name,
                configuration=f,
                campaign=ref("campaign", "campaigns"),
                starts_at=d.starts_at,
                ends_at=d.ends_at,
            ),
            ["campaign"],
        )
        add(
            "ad",
            TikTokCreateDisabledVideoAd(
                name=d.content.name,
                configuration=f,
                adgroup=ref("adgroup", "adgroups"),
                video=ref("video", "videos"),
                cover=ref("cover", "images"),
                content=d.content,
            ),
            [s.step_id for s in steps],
        )
        compiler, version = "tiktok_video_v13_v1", "v1.3"
    return SocialPublishPlan.model_validate(
        dict(
            compiler_id=compiler,
            api_version=version,
            review=review,
            review_digest=review.digest(),
            steps=steps,
        )
    )


def materialize_social(
    plan: SocialPublishPlan,
    plan_id: str,
    step_id: str,
    receipts: dict[str, SocialProviderReceipt],
    requests: dict[str, SocialBoundRequest],
    fence: str,
    now: datetime,
) -> SocialBoundRequest:
    """Dependencies come from the immutable coordinator archive, never customer JSON."""
    plan = SocialPublishPlan.model_validate(plan.model_dump())
    if compile_social(plan.review) != plan:
        raise ValueError("noncanonical social plan")
    step = next((s for s in plan.steps if s.step_id == step_id), None)
    if step is None:
        raise ValueError("unknown social step")
    resources: dict[str, str] = {}
    refs = {ref.step_id for ref in social_refs(step.operation)}
    for dependency in step.dependencies:
        receipt, request = receipts.get(dependency), requests.get(dependency)
        if receipt is None or request is None:
            raise ValueError("verified social dependency required")
        receipt = SocialProviderReceipt.model_validate(receipt.model_dump())
        request = SocialBoundRequest.model_validate(request.model_dump())
        original = next(s for s in plan.steps if s.step_id == dependency)
        if (
            receipt.outcome != "verified_effect"
            or receipt.scope != plan.review.scope
            or receipt.plan_id != plan_id
            or receipt.plan_digest != plan.digest()
            or receipt.step_id != dependency
            or receipt.fence != request.fence
            or receipt.request_digest != request.digest()
            or receipt.resource_kind != OUTPUT_KINDS[original.operation.kind]
            or request.plan_id != plan_id
            or request.plan_digest != plan.digest()
            or request.scope != plan.review.scope
            or request.step != original
            or request.review_digest != plan.review_digest
            or request.api_version != plan.api_version
            or not request.dispatched_at <= receipt.observed_at <= now
        ):
            raise ValueError("stale or foreign social dependency")
        if dependency in refs:
            assert receipt.resource_name is not None
            resources[dependency] = receipt.resource_name
    return SocialBoundRequest(
        plan_id=plan_id,
        plan_digest=plan.digest(),
        review_digest=plan.review_digest,
        scope=plan.review.scope,
        api_version=plan.api_version,
        step=step,
        resources=resources,
        fence=fence,
        dispatched_at=now,
    )
