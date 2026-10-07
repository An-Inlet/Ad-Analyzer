"""Owned linked choices. Discovery is not financial or publication qualification."""

from datetime import timedelta
from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from app.goals.schemas import StrictModel
from app.publication.contracts import fingerprint
from app.publication.provider_contracts import Digest
from app.publication.social_catalog import SocialCatalogRequest
from app.publication.social_contracts import NumericId
from app.publication.tiktok_linked_contracts import (
    AdvertiserCapabilitiesObservationV1,
    IdentityInfoObservationV1,
    LinkedOwnerV1,
    TikTokUserIdentityV1,
)


class LinkedPushOptionV1(StrictModel):
    kind: Literal["tiktok_linked_push"] = "tiktok_linked_push"
    identity: TikTokUserIdentityV1
    pixel_id: NumericId
    profile_digest: Digest
    label: str = Field(min_length=1, max_length=160)

    def identifier(self, request: SocialCatalogRequest) -> str:
        return fingerprint(
            "inlet.tiktok-linked-push-choice.v1",
            {
                "request": request.digest(),
                "choice": self.model_dump(mode="json"),
            },
        )


class LinkedPushCatalogV1(StrictModel):
    schema_version: Literal["inlet.tiktok-linked-push-catalog.v1"] = (
        "inlet.tiktok-linked-push-catalog.v1"
    )
    request: SocialCatalogRequest
    observed_at: AwareDatetime
    expires_at: AwareDatetime
    currency: Literal["USD"]
    account_timezone: str = Field(min_length=1, max_length=64)
    options: tuple[LinkedPushOptionV1, ...] = Field(max_length=50)
    identities: tuple[IdentityInfoObservationV1, ...] = Field(max_length=10)
    advertiser: AdvertiserCapabilitiesObservationV1
    qualification_blockers: tuple[str, ...] = Field(min_length=1, max_length=32)
    unavailable_reasons: tuple[str, ...] = Field(max_length=20)
    financial_qualification: Literal["not_assessed"] = "not_assessed"

    @model_validator(mode="after")
    def bounded(self) -> "LinkedPushCatalogV1":
        from zoneinfo import ZoneInfo

        ZoneInfo(self.account_timezone)
        account = self.request.account
        owner = LinkedOwnerV1(
            workspace_id=account.workspace_id,
            account_id=account.account.account_id,
            connection_id=account.account.connection_id,
            external_advertiser_id=account.external_advertiser_id,
            connection_version=account.connection_version,
        )
        keys = [option.identifier(self.request) for option in self.options]
        ids = [item.request.identity for item in self.identities]
        if (
            self.request.account.account.platform != "tiktok_ads"
            or not self.observed_at < self.expires_at <= self.observed_at + timedelta(minutes=5)
            or self.advertiser.request.owner != owner
            or any(item.request.owner != owner for item in self.identities)
            or len({item.request.identity.identity_id for item in self.identities})
            != len(self.identities)
            or self.expires_at > self.advertiser.expires_at
            or any(self.expires_at > item.expires_at for item in self.identities)
            or len(set(keys)) != len(keys)
            or any(option.identity not in ids for option in self.options)
            or "tiktok_native_catalog_parser_unverified" not in self.qualification_blockers
            or len(self.model_dump_json().encode()) > 262144
        ):
            raise ValueError("bounded owned linked catalog required")
        return self
