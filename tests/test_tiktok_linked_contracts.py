"""Reviewed independent linked profiles: no emitted actions or permission inference."""

from datetime import UTC, datetime, timedelta

import pytest
from app.publication.tiktok_linked_contracts import (
    AdvertiserCapabilitiesObservationV1,
    AdvertiserCapabilitiesRequestV1,
    IdentityInfoObservationV1,
    IdentityInfoRequestV1,
    LinkedCreativeV1,
    LinkedOwnerV1,
    LinkedPullCreativeV1,
    LinkedPushCreativeV1,
    ObservedBooleanV1,
    TikTokBusinessIdentityV1,
    TikTokUserIdentityV1,
)
from pydantic import TypeAdapter, ValidationError

NOW = datetime(2026, 10, 7, tzinfo=UTC)


def creative() -> dict[str, object]:
    return dict(
        route="push",
        identity=TikTokUserIdentityV1(identity_type="TT_USER", identity_id="identity"),
        ad_name="Reviewed Product",
        ad_format="SINGLE_VIDEO",
        dark_post_status="ON",
        operation_status="DISABLE",
        creative_authorized=False,
        call_to_action="SHOP_NOW",
        landing_page_url="https://example.test/product",
        commercial_music_rights_reviewed=True,
        rights_review_digest="a" * 64,
        video_id="library-video",
        image_ids=("one-cover",),
        ad_text="Reviewed copy",
        media_review_digest="b" * 64,
        linked_post_creation_reviewed=True,
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("identity", {"identity_type": "CUSTOMIZED_USER", "identity_id": "old"}),
        ("identity", {"identity_type": "AUTH_CODE", "identity_id": "code"}),
        ("identity", {"identity_type": "BC_AUTH_TT", "identity_id": "bc"}),
        ("image_ids", ()),
        ("image_ids", ("a", "b")),
        ("tiktok_item_id", "pull"),
        ("operation_status", "ENABLE"),
        ("dark_post_status", "OFF"),
        ("creative_authorized", True),
        ("creative_authorized", 0),
        ("commercial_music_rights_reviewed", False),
        ("ad_text", "Emoji 😀"),
        ("ad_text", "購" * 51),
        ("ad_text", "a" * 101),
        ("landing_page_url", "https://user:password@example.test/"),
        ("landing_page_url", "https:///missing-host"),
        ("call_to_action_id", "override"),
    ],
)
def test_push_rejects_unsupported_or_unreviewed_fields(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        LinkedPushCreativeV1.model_validate({**creative(), field: value})


def test_linked_profiles_roundtrip_without_old_optional_fields() -> None:
    push = LinkedPushCreativeV1.model_validate({**creative(), "ad_text": "購" * 50})
    assert (
        TypeAdapter(LinkedCreativeV1).validate_json(push.model_dump_json()).digest()
        == push.digest()
    )
    pull_fields = {
        k: v
        for k, v in creative().items()
        if k
        not in {
            "route",
            "video_id",
            "image_ids",
            "ad_text",
            "media_review_digest",
            "linked_post_creation_reviewed",
        }
    }
    pull = LinkedPullCreativeV1.model_validate(
        {
            **pull_fields,
            "route": "pull",
            "tiktok_item_id": "post",
            "owned_post_digest": "c" * 64,
            "inherited_post_copy_reviewed": True,
            "existing_post_visibility_reviewed": True,
        }
    )
    assert "ad_text" not in pull.model_dump() and "video_id" not in pull.model_dump()
    assert (
        TypeAdapter(LinkedCreativeV1).validate_json(pull.model_dump_json()).digest()
        == pull.digest()
    )
    with pytest.raises(ValidationError):
        LinkedPullCreativeV1.model_validate({**pull.model_dump(), "image_ids": ("cover",)})
    field = "ad_name"
    with pytest.raises(ValidationError):
        setattr(push, field, "changed")


def test_special_capabilities_keep_missing_and_false_distinct() -> None:
    owner = LinkedOwnerV1(
        workspace_id=1,
        account_id=2,
        connection_id=3,
        external_advertiser_id="123",
        connection_version="generation-1",
    )
    absent = ObservedBooleanV1(presence="absent", value=None)
    false = ObservedBooleanV1(presence="present", value=False)
    request = AdvertiserCapabilitiesRequestV1(
        owner=owner, fields=("ads_only_mode", "can_use_custom_identity")
    )
    observation = AdvertiserCapabilitiesObservationV1(
        request=request,
        observed_at=NOW,
        expires_at=NOW + timedelta(minutes=1),
        ads_only_mode=absent,
        can_use_custom_identity=false,
    )
    assert observation.ads_only_mode != observation.can_use_custom_identity
    for value in (0, 1, "true", "false"):
        with pytest.raises(ValidationError):
            ObservedBooleanV1.model_validate(dict(presence="present", value=value))
    with pytest.raises(ValidationError):
        AdvertiserCapabilitiesRequestV1.model_validate(
            dict(owner=owner, fields=("ads_only_mode", "currency"))
        )
    identity = IdentityInfoRequestV1(
        owner=owner,
        identity=TikTokBusinessIdentityV1(
            identity_type="BC_AUTH_TT", identity_id="id", identity_authorized_bc_id="bc"
        ),
    )
    facts = IdentityInfoObservationV1(
        request=identity,
        observed_at=NOW,
        expires_at=NOW + timedelta(minutes=1),
        available_status="AVAILABLE",
        is_gpppa=absent,
        can_push_video=false,
        can_pull_video=absent,
        ads_only_mode=absent,
    )
    # AVAILABLE does not fill missing GPPPA or override denied push permission.
    assert facts.can_push_video.value is False and facts.is_gpppa.value is None
    assert "username" not in facts.model_dump_json()
