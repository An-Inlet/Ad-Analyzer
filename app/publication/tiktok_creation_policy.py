"""Forward-only new-ad policy; historical evidence and optimization stay readable."""

from fastapi import HTTPException

from app.publication.social_contracts import SocialPublishPlan, TikTokVideoPublicationFields


def new_creation_allowed(plan: object) -> None:
    """No scenario exception: Inlet's legacy profile includes TikTok placement.

    The provider's Pangle/GAB-only exceptions are outside this supported profile.
    Do not call this from parse/readback/reconciliation or existing optimization.
    """
    if (
        isinstance(plan, SocialPublishPlan)
        and isinstance(plan.review.configuration, TikTokVideoPublicationFields)
        and plan.review.configuration.identity_type == "CUSTOMIZED_USER"
        and "PLACEMENT_TIKTOK" in plan.review.configuration.placements
    ):
        raise HTTPException(409, "tiktok_new_custom_identity_creation_unavailable")
