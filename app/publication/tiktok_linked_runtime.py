"""Request-owned linked profile discovery; no global runtime or customer proofs."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.publication.social_catalog import SocialCatalogRequest, TikTokConfigurationProfile
from app.publication.social_review_contracts import SocialRequirements
from app.publication.tiktok_linked_catalog import LinkedPushCatalogV1


@dataclass(frozen=True)
class LinkedPushReviewRuntime:
    environment: Literal["contract_test"]
    catalog: Callable[[SocialCatalogRequest, datetime], LinkedPushCatalogV1]
    profiles: tuple[TikTokConfigurationProfile, ...]
    requirements: dict[str, SocialRequirements]
    clock: Callable[[], datetime]
