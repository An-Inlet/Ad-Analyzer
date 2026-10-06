from datetime import timedelta
from typing import Any

import pytest
from app.campaign_review.contracts import ReviewArtifact
from app.publication.social_contracts import (
    MetaImagePublicationFields,
    ProviderMediaBinding,
    SocialBoundRequest,
    SocialPublicationReview,
    SocialPublishPlan,
    SocialPublishStep,
    SocialValidationEvidence,
    get_social_publication_transport,
    social_resource,
)
from pydantic import ValidationError

from tests.test_provider_publication_contracts import NOW, review


def image() -> ProviderMediaBinding:
    return ProviderMediaBinding(
        media_id="e" * 32,
        sha256="f" * 64,
        byte_size=100,
        mime="image/png",
        width=100,
        height=100,
        validation_version="image_v1",
        validation_digest="a" * 64,
    )


def meta_fields() -> MetaImagePublicationFields:
    return MetaImagePublicationFields(
        kind="meta_image_v26",
        account_timezone="UTC",
        currency="USD",
        currency_minor_unit_exponent=2,
        reservation_micros=200_000_000,
        adset_lifetime_budget_micros=200_000_000,
        budget_semantics="lifetime_budget_not_independent_hard_cap",
        activation_policy="separate_exact_approval",
        automation_omission_policy="no_optional_assets_or_automation_requested",
        page_id="100",
        pixel_id="101",
        conversion_event="PURCHASE",
        objective="OUTCOME_SALES",
        buying_type="AUCTION",
        bid_strategy="LOWEST_COST_WITHOUT_CAP",
        optimization_goal="OFFSITE_CONVERSIONS",
        billing_event="IMPRESSIONS",
        destination_type="WEBSITE",
        attribution=[{"event_type": "CLICK_THROUGH", "window_days": 7}],
        attribution_count_type="ALL_CONVERSIONS",
        countries=["US"],
        language_locale_ids={"en": 1001},
        age_min=18,
        age_max=65,
        publisher_platforms=["facebook"],
        facebook_positions=["feed"],
        advantage_audience=0,
        dynamic_creative=False,
        is_adset_budget_sharing_enabled=False,
        special_ad_categories=[],
        special_ad_category_declaration="none_applicable",
        dsa_beneficiary=None,
        dsa_payor=None,
        url_tags="",
        image=image(),
    )


def meta_review() -> SocialPublicationReview:
    original = review()
    source = original.source.model_dump()
    source["definition"]["account"]["platform"] = "meta_ads"
    source["definition"]["content"] = {
        "kind": "meta_website_sales_image_v1",
        "objective": "website_sales",
        "name": "Review name",
        "landing_page": "https://example.invalid/product",
        "audience": {"countries": ["US"], "languages": ["en"]},
        "headline": "Reviewed headline",
        "text": "Reviewed text",
        "call_to_action": "SHOP_NOW",
        "media": {"media_id": image().media_id, "sha256": image().sha256},
    }
    source["media"] = [source["definition"]["content"]["media"]]
    artifact = ReviewArtifact.model_validate(source)
    scope = original.scope.model_dump()
    scope["account"]["platform"] = "meta_ads"
    return SocialPublicationReview(
        source=artifact,
        source_digest=artifact.fingerprint(),
        scope=scope,
        configuration=meta_fields(),
        qualification_blockers=["provider_combination_unqualified"],
    )


def test_additive_meta_review_paused_plan_preserves_exact_semantics() -> None:
    r = meta_review()
    plan = SocialPublishPlan(
        compiler_id="meta_image_v26_v1",
        api_version="v26.0",
        review=r,
        review_digest=r.digest(),
        steps=[
            {
                "step_id": "image",
                "dependencies": [],
                "operation": {"kind": "meta_upload_image", "image": image()},
            },
            {
                "step_id": "campaign",
                "dependencies": [],
                "operation": {
                    "kind": "meta_create_paused_campaign",
                    "name": "Review name",
                    "configuration": meta_fields(),
                    "status": "PAUSED",
                },
            },
        ],
    )
    assert not plan.publication_eligible and get_social_publication_transport() is None
    altered = plan.model_dump()
    altered["steps"][1]["operation"]["name"] = "Not reviewed"
    with pytest.raises(ValidationError):
        SocialPublishPlan.model_validate(altered)
    altered["steps"][1]["operation"]["name"] = "Review name"
    altered["steps"][1]["operation"]["status"] = "ACTIVE"
    with pytest.raises(ValidationError):
        SocialPublishPlan.model_validate(altered)


@pytest.mark.parametrize(
    "field,value",
    [
        ("age_min", 13),
        ("adset_lifetime_budget_micros", 200_000_001),
        ("publisher_platforms", ["instagram"]),
        ("advantage_audience", 1),
        ("dynamic_creative", True),
    ],
)
def test_unsupported_meta_profile_rejected(field: str, value: Any) -> None:
    data = meta_fields().model_dump()
    data[field] = value
    with pytest.raises(ValueError):
        MetaImagePublicationFields.model_validate(data)


@pytest.mark.parametrize("change", ["image", "country", "provider", "revision"])
def test_foreign_review_bindings_rejected(change: str) -> None:
    data = meta_review().model_dump()
    if change == "image":
        data["configuration"]["image"]["sha256"] = "b" * 64
    elif change == "country":
        data["configuration"]["countries"] = ["GB"]
    elif change == "provider":
        data["scope"]["account"]["platform"] = "tiktok_ads"
    else:
        data["scope"]["mandate_revision"] += 1
    with pytest.raises(ValueError):
        SocialPublicationReview.model_validate(data)


def test_typed_resource_kind_and_foreign_namespace_rejected() -> None:
    r = meta_review()
    assert (
        social_resource(r.scope, "meta/1234567890/images/opaque.hash_01", "images")
        == "opaque.hash_01"
    )
    for value in [
        "meta/9999999999/images/hash",
        "tiktok/1234567890/images/hash",
        "meta/1234567890/ads/1",
        "meta/1234567890/images/https://example.invalid",
    ]:
        with pytest.raises(ValueError):
            social_resource(r.scope, value, "images")
    with pytest.raises(ValueError):
        SocialPublishStep(
            step_id="ad",
            dependencies=["set", "creative"],
            operation={
                "kind": "meta_create_paused_ad",
                "name": "Review name",
                "adset": {"step_id": "set", "kind": "campaigns"},
                "creative": {"step_id": "creative", "kind": "creatives"},
            },
        )


def test_video_cannot_be_substituted_with_image_or_missing_validation() -> None:
    with pytest.raises(ValueError):
        SocialPublishStep(
            step_id="video",
            dependencies=[],
            operation={"kind": "tiktok_upload_video", "video": image()},
        )
    data = image().model_dump()
    data.update(mime="video/mp4", validation_version="video_v1")
    with pytest.raises(ValueError):
        ProviderMediaBinding.model_validate(data)
    data.update(duration_ms=30000)
    assert ProviderMediaBinding.model_validate(data).mime == "video/mp4"


def test_validation_kind_does_not_claim_provider_validation_or_publication() -> None:
    local = SocialValidationEvidence(request_digest="a" * 64, kind="local_schema", valid=True)
    assert not local.publication_authorized
    with pytest.raises(ValueError):
        SocialValidationEvidence(request_digest="a" * 64, kind="unsupported", valid=True)


def test_request_api_version_and_parent_kind_are_bound() -> None:
    r = meta_review()
    body = {
        "plan_id": "a" * 32,
        "plan_digest": "b" * 64,
        "review_digest": r.digest(),
        "scope": r.scope,
        "api_version": "v26.0",
        "step": {
            "step_id": "adset",
            "dependencies": ["campaign"],
            "operation": {
                "kind": "meta_create_paused_adset",
                "name": "Review name",
                "campaign": {"step_id": "campaign", "kind": "campaigns"},
                "configuration": meta_fields(),
                "starts_at": NOW,
                "ends_at": NOW + timedelta(days=1),
            },
        },
        "resources": {"campaign": "meta/1234567890/campaigns/1"},
        "fence": "c" * 32,
        "dispatched_at": NOW,
    }
    valid = SocialBoundRequest.model_validate(body)
    for field, value in [
        ("api_version", "v1.3"),
        ("resources", {"campaign": "meta/1234567890/adsets/1"}),
    ]:
        changed = valid.model_dump()
        changed[field] = value
        with pytest.raises(ValueError):
            SocialBoundRequest.model_validate(changed)
