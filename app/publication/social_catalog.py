"""Server-only social discovery ports. Catalog membership is not native qualification."""

import json
import re
from datetime import datetime, timedelta
from typing import Annotated, Literal, Protocol
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, Field, model_validator

from app.goals.schemas import StrictModel
from app.publication.contracts import fingerprint
from app.publication.execution_contracts import ExecutionAccount
from app.publication.provider_contracts import Digest, Id
from app.publication.social_contracts import MetaAttribution, NumericId, OpaqueId


class SocialCatalogRequest(StrictModel):
    account: ExecutionAccount
    draft_id: Id
    draft_revision: int = Field(strict=True, ge=1)
    source_digest: Digest
    countries: list[str] = Field(min_length=1, max_length=20)
    languages: list[str] = Field(min_length=1, max_length=10)
    content_kind: Literal["meta_website_sales_image_v1", "tiktok_website_conversion_video_v1"]

    @model_validator(mode="after")
    def bounded(self) -> "SocialCatalogRequest":
        platform = "meta_ads" if self.content_kind.startswith("meta_") else "tiktok_ads"
        if (
            self.account.account.platform != platform
            or not re.fullmatch(r"[0-9]{1,32}", self.account.external_advertiser_id)
            or len(set(self.countries)) != len(self.countries)
            or len(set(self.languages)) != len(self.languages)
            or any(not re.fullmatch(r"[A-Z]{2}", c) for c in self.countries)
            or any(not re.fullmatch(r"[a-z]{2,3}(?:[-_][A-Za-z]{2,4})?", c) for c in self.languages)
        ):
            raise ValueError("invalid social catalog request")
        return self

    def digest(self) -> str:
        return fingerprint("inlet.social-catalog-request.v1", self.model_dump(mode="json"))


class MetaConfigurationProfile(StrictModel):
    """Explicit server configuration, never native capability or spending evidence."""

    kind: Literal["meta_image_v26"] = "meta_image_v26"
    profile_id: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=120)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    currency_exponent: int = Field(strict=True, ge=0, le=3)
    language_locale_ids: dict[str, int] = Field(min_length=1, max_length=10)
    attribution: list[MetaAttribution] = Field(min_length=1, max_length=2)
    age_min: int = Field(strict=True, ge=18, le=65)
    age_max: int = Field(strict=True, ge=18, le=65)
    dsa_required: bool = Field(strict=True)
    url_tags: str = Field(max_length=2048)

    @model_validator(mode="after")
    def bounded(self) -> "MetaConfigurationProfile":
        if (
            self.age_min > self.age_max
            or any(type(v) is not int or v <= 0 for v in self.language_locale_ids.values())
            or len({a.event_type for a in self.attribution}) != len(self.attribution)
        ):
            raise ValueError("invalid explicit Meta profile")
        return self

    def digest(self) -> str:
        return fingerprint("inlet.meta-customer-profile.v1", self.model_dump(mode="json"))


class TikTokConfigurationProfile(StrictModel):
    kind: Literal["tiktok_video_v13"] = "tiktok_video_v13"
    profile_id: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=120)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    currency_exponent: int = Field(strict=True, ge=0, le=3)
    location_ids_by_country: dict[str, list[NumericId]] = Field(min_length=1, max_length=20)
    language_codes: dict[str, str] = Field(min_length=1, max_length=10)
    age_groups: list[Literal["AGE_18_24", "AGE_25_34", "AGE_35_44", "AGE_45_54", "AGE_55_100"]] = (
        Field(min_length=1, max_length=5)
    )
    click_attribution_window: Literal["ONE_DAY", "SEVEN_DAYS"]
    view_attribution_window: Literal["OFF", "ONE_DAY"]
    engaged_view_attribution_window: Literal["OFF", "ONE_DAY"]
    comment_disabled: bool = Field(strict=True)
    share_disabled: bool = Field(strict=True)
    video_download_disabled: bool = Field(strict=True)

    def digest(self) -> str:
        return fingerprint("inlet.tiktok-customer-profile.v1", self.model_dump(mode="json"))


class Option(StrictModel):
    label: str = Field(min_length=1, max_length=160)
    profile_digest: Digest

    def identifier(self, request: SocialCatalogRequest) -> str:
        return fingerprint(
            "inlet.social-catalog-option.v1",
            {"request": request.digest(), "option": self.model_dump(mode="json")},
        )


class MetaCatalogOption(Option):
    kind: Literal["meta_image_v26"] = "meta_image_v26"
    page_id: NumericId
    pixel_id: NumericId
    conversion_event: Literal["PURCHASE"] = "PURCHASE"


class TikTokCatalogOption(Option):
    kind: Literal["tiktok_video_v13"] = "tiktok_video_v13"
    identity_id: OpaqueId
    identity_type: Literal["CUSTOMIZED_USER"] = "CUSTOMIZED_USER"
    pixel_id: NumericId
    conversion_event: Literal["SHOPPING"] = "SHOPPING"


SocialCatalogOption = Annotated[
    MetaCatalogOption | TikTokCatalogOption, Field(discriminator="kind")
]


class SocialCatalog(StrictModel):
    request: SocialCatalogRequest
    observed_at: AwareDatetime
    expires_at: AwareDatetime
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    account_timezone: str = Field(min_length=1, max_length=64)
    options: list[SocialCatalogOption] = Field(max_length=50)
    unavailable_reasons: list[str] = Field(max_length=20)
    qualification_blockers: list[str] = Field(min_length=1, max_length=32)
    discovery_evidence: Literal["meta_account_edges", "tiktok_decoded_contract_only"]

    @model_validator(mode="after")
    def bounded(self) -> "SocialCatalog":
        ZoneInfo(self.account_timezone)
        kind = (
            "meta_image_v26"
            if self.request.account.account.platform == "meta_ads"
            else "tiktok_video_v13"
        )
        evidence = (
            "meta_account_edges" if kind == "meta_image_v26" else "tiktok_decoded_contract_only"
        )
        ids = [o.identifier(self.request) for o in self.options]
        if (
            not self.observed_at < self.expires_at <= self.observed_at + timedelta(minutes=5)
            or len(json.dumps(self.model_dump(mode="json")).encode()) > 65536
            or len(set(ids)) != len(ids)
            or any(o.kind != kind for o in self.options)
            or self.discovery_evidence != evidence
            or (
                kind == "tiktok_video_v13"
                and "tiktok_native_catalog_parser_unverified" not in self.qualification_blockers
            )
        ):
            raise ValueError("invalid bounded social catalog")
        return self


class SocialCatalogReader(Protocol):
    def __call__(self, request: SocialCatalogRequest, now: datetime, /) -> SocialCatalog: ...


class MetaDeclaration(StrictModel):
    """Returned by an audited server reader, never accepted as customer-supplied proof."""

    request_digest: Digest
    audit_record_id: Id
    confirmed_by: str = Field(min_length=1, max_length=160)
    confirmed_at: AwareDatetime
    special_ad_category_declaration: Literal["none_applicable"]
    dsa_beneficiary: str | None = Field(max_length=200)
    dsa_payor: str | None = Field(max_length=200)


class MetaDeclarationReader(Protocol):
    def __call__(self, request: SocialCatalogRequest, now: datetime, /) -> MetaDeclaration: ...
