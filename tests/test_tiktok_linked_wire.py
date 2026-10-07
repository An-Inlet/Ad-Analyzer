"""Official linked Push/Pull field combinations; no external HTTP or mutations."""

import pytest
from app.publication.tiktok_linked_contracts import LinkedPullCreativeV1, LinkedPushCreativeV1
from app.publication.tiktok_linked_wire import creative_body, matches_linked_ad

from tests.test_tiktok_linked_contracts import creative


def test_push_exact_body_and_documented_deferred_post_id() -> None:
    intent = LinkedPushCreativeV1.model_validate(creative())
    body = creative_body(intent)
    assert body["operation_status"] == "DISABLE" and body["dark_post_status"] == "ON"
    assert body["image_ids"] == ["one-cover"] and body["video_id"] == "library-video"
    assert "rights_review_digest" not in body and "creative_type" not in body
    for post in ({}, {"tiktok_item_id": None}, {"tiktok_item_id": "later-reviewed-post"}):
        assert matches_linked_ad(intent, {**body, **post})
    for key, value in (
        ("video_id", "different"),
        ("image_ids", []),
        ("operation_status", "ENABLE"),
        ("dark_post_status", "OFF"),
        ("creative_authorized", 0),
    ):
        assert not matches_linked_ad(intent, {**body, key: value})


@pytest.mark.parametrize(
    "identity",
    [
        dict(identity_type="TT_USER", identity_id="identity"),
        dict(identity_type="BC_AUTH_TT", identity_id="identity", identity_authorized_bc_id="bc"),
    ],
)
def test_pull_inherits_post_and_requires_null_video(identity: dict[str, str]) -> None:
    values = {
        k: v
        for k, v in creative().items()
        if k
        not in {
            "route",
            "identity",
            "video_id",
            "image_ids",
            "ad_text",
            "media_review_digest",
            "linked_post_creation_reviewed",
        }
    }
    intent = LinkedPullCreativeV1.model_validate(
        {
            **values,
            "identity": identity,
            "route": "pull",
            "tiktok_item_id": "post",
            "owned_post_digest": "c" * 64,
            "inherited_post_copy_reviewed": True,
            "existing_post_visibility_reviewed": True,
        }
    )
    body = creative_body(intent)
    assert {"video_id", "image_ids", "ad_text", "creative_type"}.isdisjoint(body)
    assert ("identity_authorized_bc_id" in body) == (identity["identity_type"] == "BC_AUTH_TT")
    assert matches_linked_ad(intent, {**body, "video_id": None, "ad_text": "inherited"})
    assert not matches_linked_ad(intent, body)
    assert not matches_linked_ad(intent, {**body, "video_id": "new-video"})
    assert not matches_linked_ad(intent, {**body, "video_id": None, "tiktok_item_id": "foreign"})
