"""Discovery traversal evidence; no publication, account-wide or financial authority."""

from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from app.collectors.tiktok_discovery_contracts import (
    Frozen,
    TikTokIdentityPageV1,
    TikTokPixelPageV1,
)
from app.publication.execution_contracts import ExecutionAccount


class TikTokDiscoveryScopeV1(Frozen):
    workspace_id: int = Field(gt=0)
    account_id: int = Field(gt=0)
    connection_id: int = Field(gt=0)
    external_advertiser_id: str = Field(pattern=r"^[0-9]{1,32}$")
    connection_version: str = Field(min_length=1, max_length=100)
    platform: Literal["tiktok_ads"] = "tiktok_ads"

    @classmethod
    def from_account(cls, account: ExecutionAccount) -> "TikTokDiscoveryScopeV1":
        if account.account.platform != "tiktok_ads":
            raise ValueError("TikTok scope required")
        return cls(
            workspace_id=account.workspace_id,
            account_id=account.account.account_id,
            connection_id=account.account.connection_id,
            external_advertiser_id=account.external_advertiser_id,
            connection_version=account.connection_version,
            platform=account.account.platform,
        )


class DiscoveryV1(Frozen):
    scope: TikTokDiscoveryScopeV1
    environment: Literal["contract_test"] = "contract_test"
    observed_started_at: AwareDatetime
    observed_ended_at: AwareDatetime
    traversal_completeness: Literal["complete_requested_scope"] = "complete_requested_scope"
    publication_eligibility: Literal["not_assessed"] = "not_assessed"
    spending_authority: Literal["none"] = "none"

    @model_validator(mode="after")
    def time_order(self) -> "DiscoveryV1":
        if self.observed_ended_at < self.observed_started_at:
            raise ValueError("discovery time reversed")
        return self


class TikTokIdentityDiscoveryV1(DiscoveryV1):
    schema_version: Literal["inlet.tiktok-identity-discovery.v1"] = (
        "inlet.tiktok-identity-discovery.v1"
    )
    pages: tuple[TikTokIdentityPageV1, ...] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def complete(self) -> "TikTokIdentityDiscoveryV1":
        validate_pages(self.scope, self.pages)
        return self


class TikTokPixelDiscoveryV1(DiscoveryV1):
    schema_version: Literal["inlet.tiktok-pixel-discovery.v1"] = "inlet.tiktok-pixel-discovery.v1"
    pages: tuple[TikTokPixelPageV1, ...] = Field(min_length=1, max_length=10)
    scalar_shape_qualification: Literal["unverified"] = "unverified"

    @model_validator(mode="after")
    def complete(self) -> "TikTokPixelDiscoveryV1":
        validate_pages(self.scope, self.pages)
        return self


def validate_pages(
    scope: TikTokDiscoveryScopeV1,
    pages: tuple[TikTokIdentityPageV1 | TikTokPixelPageV1, ...],
) -> None:
    first = pages[0]
    total, size = first.page_info.total_number, first.page_info.page_size
    expected_pages = (total + size - 1) // size
    if len(pages) != max(1, expected_pages) or (
        first.page_info.total_page != expected_pages
        and not (total == 0 and first.page_info.total_page == 1)
    ):
        raise ValueError("discovery incomplete")
    seen: set[tuple[type[str] | type[int], str | int]] = set()
    for number, page in enumerate(pages, 1):
        if (
            page.request.advertiser_id != scope.external_advertiser_id
            or page.request.page != number
            or page.page_info.page != number
            or page.page_info.total_number != total
            or page.page_info.total_page != first.page_info.total_page
            or page.request.page_size != size
            or page.page_info.page_size != size
            or page.request.model_dump(exclude={"page"})
            != first.request.model_dump(exclude={"page"})
        ):
            raise ValueError("discovery scope changed")
        ids: list[str | int] = []
        if isinstance(page, TikTokIdentityPageV1):
            if page.request.keyword is not None:
                raise ValueError("filtered identity discovery unsupported")
            for identity in page.identities:
                if identity.identity_type.value != page.request.identity_type:
                    raise ValueError("identity type unknown or changed")
                ids.append(identity.identity_id)
        else:
            if any((page.request.code, page.request.pixel_id, page.request.name)) or (
                page.request.available_for_catalog_only
            ):
                raise ValueError("filtered pixel discovery unsupported")
            for pixel in page.pixels:
                if pixel.pixel_id.value is None:
                    raise ValueError("pixel identity unavailable")
                ids.append(pixel.pixel_id.value)
        if len(ids) != min(size, total - (number - 1) * size):
            raise ValueError("discovery cardinality changed")
        for identifier in ids:
            key = (type(identifier), identifier)
            if key in seen:
                raise ValueError("duplicate discovery identity")
            seen.add(key)
