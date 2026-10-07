"""Exact linked creative payload; no defaults, authorization or provider calls."""

from typing import Any

from app.publication.tiktok_linked_contracts import (
    LinkedCreativeV1,
    LinkedPullCreativeV1,
    LinkedPushCreativeV1,
    TikTokBusinessIdentityV1,
)


def creative_body(creative: LinkedCreativeV1) -> dict[str, Any]:
    """Only a coordinator-resolved reviewed creative belongs at this server boundary."""
    if isinstance(creative, LinkedPushCreativeV1):
        creative = LinkedPushCreativeV1.model_validate_json(creative.model_dump_json())
    elif isinstance(creative, LinkedPullCreativeV1):
        creative = LinkedPullCreativeV1.model_validate_json(creative.model_dump_json())
    else:
        raise ValueError("unsupported linked creative")
    identity = creative.identity
    body: dict[str, Any] = {
        "ad_name": creative.ad_name,
        "identity_type": identity.identity_type,
        "identity_id": identity.identity_id,
        "ad_format": creative.ad_format,
        "dark_post_status": creative.dark_post_status,
        "operation_status": creative.operation_status,
        "creative_authorized": creative.creative_authorized,
        "call_to_action": creative.call_to_action,
        "landing_page_url": creative.landing_page_url,
    }
    if isinstance(identity, TikTokBusinessIdentityV1):
        body["identity_authorized_bc_id"] = identity.identity_authorized_bc_id
    if isinstance(creative, LinkedPushCreativeV1):
        body.update(
            video_id=creative.video_id, image_ids=list(creative.image_ids), ad_text=creative.ad_text
        )
    else:
        body["tiktok_item_id"] = creative.tiktok_item_id
    return body


def matches_linked_ad(creative: LinkedCreativeV1, observed: dict[str, Any]) -> bool:
    """Exact selected fields only. This never proves delivery or spend.

    A Push post ID may be absent/null before ad review, so it is deliberately not
    required or invented. Pull instead requires its exact existing post and an
    explicitly null library-video field; inherited copy is not overwritten.
    """
    expected = creative_body(creative)
    for key, value in expected.items():
        if key not in observed or type(observed[key]) is not type(value) or observed[key] != value:
            return False
    if creative.identity.identity_type == "TT_USER" and observed.get(
        "identity_authorized_bc_id"
    ) not in (None, ""):
        return False
    if isinstance(creative, LinkedPullCreativeV1):
        if "video_id" not in observed or observed["video_id"] is not None:
            return False
        # Pull must not silently become a separate uploaded creative.
        if observed.get("image_ids") not in (None, []):
            return False
    return True
