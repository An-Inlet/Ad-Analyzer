"""Strict nonpersonal social configuration reviews; no DSA-name capture port."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from app.goals.schemas import StrictModel
from app.publication.contracts import fingerprint
from app.publication.provider_contracts import Digest
from app.publication.social_catalog import SocialCatalogRequest
from app.publication.social_contracts import ProviderMediaBinding


class MetaNoDSAAnswer(StrictModel):
    kind: Literal["meta_no_dsa"] = "meta_no_dsa"
    special_category_answer: Literal["none_applicable", "applicable", "unsure"]


class TikTokCoverAnswer(StrictModel):
    kind: Literal["tiktok_cover"] = "tiktok_cover"
    reviewed_pair: Literal[True]


SocialAnswer = Annotated[MetaNoDSAAnswer | TikTokCoverAnswer, Field(discriminator="kind")]


class SocialRequirements(StrictModel):
    """Server-owned reviewed rules; a profile's boolean alone is not rule evidence."""

    profile_digest: Digest
    requirements_digest: Digest
    wording_version: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_.-]+$")
    verified: Literal[True]
    dsa_required: Literal[False]


class SocialConfigurationDocument(StrictModel):
    schema_version: Literal["inlet.social-configuration-review.v1"] = (
        "inlet.social-configuration-review.v1"
    )
    request: SocialCatalogRequest
    environment: Literal["contract_test", "live"]
    option_id: Digest
    requirements: SocialRequirements
    primary: ProviderMediaBinding
    cover: ProviderMediaBinding | None
    answer: SocialAnswer

    @model_validator(mode="after")
    def exact_media(self) -> "SocialConfigurationDocument":
        if isinstance(self.answer, MetaNoDSAAnswer):
            if (
                self.request.account.account.platform != "meta_ads"
                or self.cover is not None
                or not self.primary.mime.startswith("image/")
            ):
                raise ValueError("exact Meta image configuration required")
        elif (
            self.request.account.account.platform != "tiktok_ads"
            or self.cover is None
            or not self.cover.mime.startswith("image/")
            or self.primary.mime != "video/mp4"
        ):
            raise ValueError("exact TikTok video and cover required")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))

    def blockers(self) -> list[str]:
        if isinstance(self.answer, MetaNoDSAAnswer) and (
            self.answer.special_category_answer != "none_applicable"
        ):
            return ["special_category_requires_unsupported_configuration"]
        return []
