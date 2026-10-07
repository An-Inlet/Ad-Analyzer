"""Independent linked Spark creative contracts; no legacy document reinterpretation.

These records describe reviewed intent/observed facts. They are not financial
qualification and are never accepted as customer-supplied provider proof.
"""

from datetime import timedelta
from typing import Annotated, Literal

from pydantic import AwareDatetime, ConfigDict, Field, field_validator, model_validator

from app.campaign_review.contracts import CopyBase
from app.goals.schemas import StrictModel
from app.publication.contracts import fingerprint
from app.publication.provider_contracts import Digest

ProviderId = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.=-]+$")]


class Frozen(StrictModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ObservedBooleanV1(Frozen):
    presence: Literal["absent", "null", "present"]
    value: bool | None

    @model_validator(mode="after")
    def presence_matches(self) -> "ObservedBooleanV1":
        if (self.presence == "present") != (self.value is not None):
            raise ValueError("boolean presence mismatch")
        return self


class LinkedOwnerV1(Frozen):
    workspace_id: int = Field(gt=0)
    account_id: int = Field(gt=0)
    connection_id: int = Field(gt=0)
    external_advertiser_id: ProviderId
    connection_version: str = Field(min_length=1, max_length=100)


class TikTokUserIdentityV1(Frozen):
    identity_type: Literal["TT_USER"]
    identity_id: ProviderId


class TikTokBusinessIdentityV1(Frozen):
    identity_type: Literal["BC_AUTH_TT"]
    identity_id: ProviderId
    identity_authorized_bc_id: ProviderId


LinkedIdentityV1 = Annotated[
    TikTokUserIdentityV1 | TikTokBusinessIdentityV1, Field(discriminator="identity_type")
]


class IdentityInfoRequestV1(Frozen):
    schema_version: Literal["inlet.tiktok-linked-identity-info-request.v1"] = (
        "inlet.tiktok-linked-identity-info-request.v1"
    )
    owner: LinkedOwnerV1
    identity: LinkedIdentityV1

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class IdentityInfoObservationV1(Frozen):
    """Normalized identity/info facts; absence never grants permissions."""

    schema_version: Literal["inlet.tiktok-linked-identity-info.v1"] = (
        "inlet.tiktok-linked-identity-info.v1"
    )
    request: IdentityInfoRequestV1
    observed_at: AwareDatetime
    expires_at: AwareDatetime
    available_status: Literal[
        "AVAILABLE",
        "NO_VALID_BIND_ACCOUNT",
        "SCOPE_UNAVAILABLE",
        "IS_PRIVATE_ACCOUNT",
        "NOT_BUSINESS_ACCOUNT",
        "unknown",
        "absent",
        "null",
    ]
    is_gpppa: ObservedBooleanV1
    can_push_video: ObservedBooleanV1
    can_pull_video: ObservedBooleanV1
    ads_only_mode: ObservedBooleanV1

    @model_validator(mode="after")
    def bounded(self) -> "IdentityInfoObservationV1":
        if not self.observed_at < self.expires_at <= self.observed_at + timedelta(minutes=5):
            raise ValueError("bounded identity evidence required")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class AdvertiserCapabilitiesRequestV1(Frozen):
    schema_version: Literal["inlet.tiktok-advertiser-capabilities-request.v1"] = (
        "inlet.tiktok-advertiser-capabilities-request.v1"
    )
    owner: LinkedOwnerV1
    # Special response mode deliberately excludes ordinary account profile fields.
    fields: tuple[Literal["ads_only_mode", "can_use_custom_identity"], ...]

    @model_validator(mode="after")
    def exact_fields(self) -> "AdvertiserCapabilitiesRequestV1":
        if self.fields != ("ads_only_mode", "can_use_custom_identity"):
            raise ValueError("exact special capability field set required")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class AdvertiserCapabilitiesObservationV1(Frozen):
    schema_version: Literal["inlet.tiktok-advertiser-capabilities.v1"] = (
        "inlet.tiktok-advertiser-capabilities.v1"
    )
    request: AdvertiserCapabilitiesRequestV1
    observed_at: AwareDatetime
    expires_at: AwareDatetime
    ads_only_mode: ObservedBooleanV1
    can_use_custom_identity: ObservedBooleanV1

    @model_validator(mode="after")
    def bounded(self) -> "AdvertiserCapabilitiesObservationV1":
        if not self.observed_at < self.expires_at <= self.observed_at + timedelta(minutes=5):
            raise ValueError("bounded advertiser evidence required")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


def _plain_ad_text(value: str, maximum: int) -> str:
    # Supported text includes ordinary currency prices, but not emoji/variation controls.
    import unicodedata

    if not value.strip() or any(unicodedata.category(c)[0] not in "LNPSZ" for c in value):
        raise ValueError("unsupported ad text character")
    if any(
        unicodedata.category(c).startswith("S") and unicodedata.category(c) != "Sc" for c in value
    ):
        raise ValueError("noncurrency symbols and emoji are unsupported")
    weighted = sum(
        2
        if (
            "\u3040" <= c <= "\u30ff"
            or "\u3400" <= c <= "\u9fff"
            or "\uf900" <= c <= "\ufaff"
            or "\U00020000" <= c <= "\U000323af"
        )
        else 1
        for c in value
    )
    if weighted > maximum:
        raise ValueError("ad text exceeds supported weighted limit")
    return value


class LinkedCreativeBaseV1(Frozen):
    identity: LinkedIdentityV1
    ad_name: str = Field(min_length=1, max_length=512)
    ad_format: Literal["SINGLE_VIDEO"]
    dark_post_status: Literal["ON"]
    operation_status: Literal["DISABLE"]
    creative_authorized: Literal[False]
    call_to_action: Literal["SHOP_NOW"]
    landing_page_url: str = Field(min_length=1, max_length=2048, pattern=r"^https://")
    commercial_music_rights_reviewed: Literal[True]
    rights_review_digest: Digest

    @field_validator(
        "creative_authorized",
        "commercial_music_rights_reviewed",
        "linked_post_creation_reviewed",
        "inherited_post_copy_reviewed",
        "existing_post_visibility_reviewed",
        mode="before",
        check_fields=False,
    )
    @classmethod
    def explicit_boolean(cls, value: object) -> object:
        if type(value) is not bool:
            raise ValueError("explicit boolean required")
        return value

    @field_validator("landing_page_url")
    @classmethod
    def destination(cls, value: str) -> str:
        return CopyBase.destination(value)

    @field_validator("ad_name")
    @classmethod
    def name_text(cls, value: str) -> str:
        # Name has a plain 512-character provider limit, not the ad_text weight rule.
        _plain_ad_text(value, 1024)
        return value


class LinkedPushCreativeV1(LinkedCreativeBaseV1):
    schema_version: Literal["inlet.tiktok-linked-push-creative.v1"] = (
        "inlet.tiktok-linked-push-creative.v1"
    )
    route: Literal["push"]
    # Server-resolved library resources only; customer uses owned private-media refs.
    video_id: ProviderId
    image_ids: tuple[ProviderId]
    ad_text: str = Field(min_length=1, max_length=100)
    media_review_digest: Digest
    linked_post_creation_reviewed: Literal[True]

    @field_validator("ad_text")
    @classmethod
    def copy_text(cls, value: str) -> str:
        return _plain_ad_text(value, 100)

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class LinkedPullCreativeV1(LinkedCreativeBaseV1):
    schema_version: Literal["inlet.tiktok-linked-pull-creative.v1"] = (
        "inlet.tiktok-linked-pull-creative.v1"
    )
    route: Literal["pull"]
    tiktok_item_id: ProviderId
    # Immutable exact owned post/copy commitment, never caller text replacement.
    owned_post_digest: Digest
    inherited_post_copy_reviewed: Literal[True]
    existing_post_visibility_reviewed: Literal[True]

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


LinkedCreativeV1 = Annotated[
    LinkedPushCreativeV1 | LinkedPullCreativeV1, Field(discriminator="route")
]
