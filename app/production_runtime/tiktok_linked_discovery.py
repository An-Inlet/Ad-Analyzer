"""Actual owned linked identity reads plus separately scoped pixel/profile evidence."""

from collections.abc import Callable
from datetime import datetime
from time import monotonic

import httpx
from fastapi import HTTPException

from app.collectors.tiktok_linked_capabilities import TikTokLinkedCapabilities
from app.collectors.tiktok_owned_discovery import TikTokOwnedDiscovery
from app.production_runtime.owned_tiktok_contexts import OwnedTikTokContexts
from app.production_runtime.tiktok_linked_configuration import TikTokLinkedConfigurationBundleV1
from app.publication.social_catalog import SocialCatalog, SocialCatalogRequest, TikTokCatalogOption
from app.publication.tiktok_linked_catalog import LinkedPushCatalogV1, LinkedPushOptionV1
from app.publication.tiktok_linked_contracts import IdentityInfoObservationV1, TikTokUserIdentityV1


def discover_linked(
    request: SocialCatalogRequest,
    now: datetime,
    *,
    contexts: OwnedTikTokContexts,
    transport: Callable[[], httpx.MockTransport],
    bundle: TikTokLinkedConfigurationBundleV1,
    pixels: Callable[[SocialCatalogRequest, datetime], SocialCatalog],
    clock: Callable[[], datetime],
) -> LinkedPushCatalogV1:
    deadline = monotonic() + 30
    original_token, original_expiry = contexts.credentials(request.account)

    def current() -> None:
        token, expiry = contexts.credentials(request.account)
        if (
            token != original_token
            or clock() >= min(expiry, original_expiry)
            or monotonic() > deadline
        ):
            raise HTTPException(409, "linked_configuration_changed")

    profiles = {p.digest(): p for p in bundle.profiles}
    identities = TikTokOwnedDiscovery(request.account, contexts, transport(), clock).identities(
        "TT_USER"
    )
    current()
    rows = [row for page in identities.pages for row in page.identities]
    if len(rows) > 10:
        raise HTTPException(409, "linked_configuration_capacity_unavailable")
    pixel_catalog = SocialCatalog.model_validate_json(pixels(request, clock()).model_dump_json())
    current()
    if (
        pixel_catalog.request != request
        or pixel_catalog.currency != "USD"
        or not pixel_catalog.observed_at <= clock() < pixel_catalog.expires_at
    ):
        raise HTTPException(409, "linked_configuration_changed")
    advertiser = TikTokLinkedCapabilities(
        request.account, contexts, transport(), clock
    ).advertiser()
    current()
    observations: list[IdentityInfoObservationV1] = []
    choices: list[LinkedPushOptionV1] = []
    for row in rows:
        identity = TikTokUserIdentityV1(identity_type="TT_USER", identity_id=row.identity_id)
        info = TikTokLinkedCapabilities(request.account, contexts, transport(), clock).identity(
            identity
        )
        current()
        observations.append(info)
        if (
            info.available_status != "AVAILABLE"
            or info.is_gpppa.value is not False
            or info.can_push_video.value is not True
        ):
            continue
        seen_pixels: set[tuple[str, str]] = set()
        for pixel in pixel_catalog.options:
            if not isinstance(pixel, TikTokCatalogOption) or pixel.profile_digest not in profiles:
                continue
            key = (pixel.profile_digest, pixel.pixel_id)
            if key in seen_pixels:
                continue
            seen_pixels.add(key)
            label = row.display_name.value or "Linked TikTok Account"
            choices.append(
                LinkedPushOptionV1(
                    identity=identity,
                    pixel_id=pixel.pixel_id,
                    profile_digest=pixel.profile_digest,
                    label=(label[:70] + " · " + profiles[pixel.profile_digest].label[:70]),
                )
            )
            if len(choices) > 50:
                raise HTTPException(409, "linked_configuration_capacity_unavailable")
    current()
    result = LinkedPushCatalogV1(
        request=request,
        observed_at=now,
        expires_at=min(
            original_expiry,
            pixel_catalog.expires_at,
            advertiser.expires_at,
            *(value.expires_at for value in observations),
        ),
        currency="USD",
        account_timezone=pixel_catalog.account_timezone,
        options=tuple(choices),
        identities=tuple(observations),
        advertiser=advertiser,
        qualification_blockers=tuple(pixel_catalog.qualification_blockers),
        unavailable_reasons=() if choices else ("linked_identity_unavailable",),
    )
    current()
    return result
