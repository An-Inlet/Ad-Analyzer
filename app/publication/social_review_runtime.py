"""Optional server-owned configuration discovery. No provider factory is installed."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.publication.social_catalog import (
    MetaConfigurationProfile,
    SocialCatalogReader,
    TikTokConfigurationProfile,
)
from app.publication.social_review_contracts import SocialRequirements


@dataclass(frozen=True)
class SocialReviewRuntime:
    environment: Literal["contract_test", "live"]
    catalog: SocialCatalogReader
    profiles: tuple[MetaConfigurationProfile | TikTokConfigurationProfile, ...]
    requirements: Mapping[str, SocialRequirements]
    clock: Callable[[], datetime]


def get_social_review_runtime() -> SocialReviewRuntime | None:
    return None
