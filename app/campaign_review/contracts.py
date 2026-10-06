import hashlib
import json
import unicodedata
from collections.abc import Iterable
from typing import Annotated, Any, Literal, Protocol
from urllib.parse import urlsplit

from pydantic import AwareDatetime, Field, ValidationInfo, field_validator, model_validator

from app.goals.schemas import StrictModel
from app.mandates.schemas import AccountScope

MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_PIXELS = 16_000_000
MAX_LIBRARY_BYTES = 128 * 1024 * 1024


def digest(value: dict[str, Any]) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(b"inlet.campaign-review.v1\0" + data).hexdigest()


class MediaRef(StrictModel):
    media_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class MediaStore(Protocol):
    def put_if_absent(
        self, workspace_id: int, sha256: str, size: int, chunks: Iterable[bytes]
    ) -> None: ...
    def read_exact(self, workspace_id: int, sha256: str, size: int) -> bytes: ...


class Audience(StrictModel):
    countries: list[str] = Field(min_length=1, max_length=20)
    languages: list[str] = Field(min_length=1, max_length=10)

    @field_validator("countries", "languages")
    @classmethod
    def codes(cls, values: list[str]) -> list[str]:
        import re

        if len(set(values)) != len(values) or any(
            not re.fullmatch(r"[A-Za-z-]{2,10}", v) for v in values
        ):
            raise ValueError("invalid audience codes")
        return values


class CopyBase(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    landing_page: str = Field(min_length=1, max_length=2048)
    audience: Audience

    @field_validator("name", "landing_page", "headline", "text", check_fields=False)
    @classmethod
    def normalized(cls, value: str) -> str:
        value = unicodedata.normalize("NFC", value)
        if any(ord(c) < 32 for c in value):
            raise ValueError("control characters unavailable")
        return value

    @field_validator("landing_page")
    @classmethod
    def destination(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.fragment
        ):
            raise ValueError("HTTPS destination required")
        return value


class GoogleSearch(CopyBase):
    kind: Literal["google_search_v1"]
    objective: Literal["website_sales"]
    headlines: list[str] = Field(min_length=3, max_length=15)
    descriptions: list[str] = Field(min_length=2, max_length=4)
    exact_keywords: list[str] = Field(min_length=1, max_length=50)

    @field_validator("headlines", "descriptions", "exact_keywords")
    @classmethod
    def supplied_copy(cls, values: list[str], info: ValidationInfo) -> list[str]:
        values = [unicodedata.normalize("NFC", value) for value in values]
        limit = {"headlines": 30, "descriptions": 90, "exact_keywords": 80}[info.field_name or ""]
        for value in values:
            width = (
                len(value)
                if info.field_name == "exact_keywords"
                else sum(
                    2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1 for char in value
                )
            )
            if (
                not value.strip()
                or width > limit
                or any(ord(c) < 32 for c in value)
                or any(c in value for c in "{}")
                or (info.field_name == "exact_keywords" and len(value.split()) > 10)
            ):
                raise ValueError("invalid supplied copy")
        if len(set(values)) != len(values):
            raise ValueError("duplicate supplied copy")
        return values


class MetaImage(CopyBase):
    kind: Literal["meta_website_sales_image_v1"]
    objective: Literal["website_sales"]
    headline: str = Field(min_length=1, max_length=90)
    text: str = Field(min_length=1, max_length=500)
    media: MediaRef
    call_to_action: Literal["SHOP_NOW"]


class TikTokVideo(CopyBase):
    kind: Literal["tiktok_website_conversion_video_v1"]
    objective: Literal["website_conversion"]
    text: str = Field(min_length=1, max_length=100)
    media: MediaRef
    call_to_action: Literal["SHOP_NOW"]


Content = Annotated[GoogleSearch | MetaImage | TikTokVideo, Field(discriminator="kind")]


class RevisionInput(StrictModel):
    account: AccountScope
    mandate_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    mandate_revision: int = Field(strict=True, ge=1)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    budget_micros: int = Field(strict=True, gt=0, le=10**15)
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    content: Content

    @model_validator(mode="after")
    def bounded(self) -> "RevisionInput":
        platform = {
            "google_search_v1": "google_ads",
            "meta_website_sales_image_v1": "meta_ads",
            "tiktok_website_conversion_video_v1": "tiktok_ads",
        }[self.content.kind]
        if platform != self.account.platform or self.starts_at >= self.ends_at:
            raise ValueError("account/content or schedule mismatch")
        if len(self.model_dump_json().encode()) > 65536:
            raise ValueError("draft exceeds bound")
        return self


class RevisionEdit(StrictModel):
    expected_revision: int = Field(strict=True, ge=1)
    definition: RevisionInput


class ExactApproval(StrictModel):
    expected_revision: int = Field(strict=True, ge=1)
    review_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


class ReviewArtifact(StrictModel):
    schema_version: Literal["inlet.campaign-review.v1"] = "inlet.campaign-review.v1"
    draft_id: str
    revision: int
    workspace_id: int
    definition: RevisionInput
    connection_version: str
    media: list[MediaRef]
    offline_reviewable: bool
    publication_eligible: Literal[False] = False
    publication_blockers: list[str] = Field(
        default_factory=lambda: [
            "capability_manifest_unqualified",
            "tracking_conversion_binding_required",
            "bidding_configuration_required",
            "publish_plan_unavailable",
            "provider_publication_disabled",
        ]
    )
    blockers: list[str]

    def fingerprint(self) -> str:
        return digest(self.model_dump(mode="json"))
