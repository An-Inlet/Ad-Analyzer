"""Pure, untrusted report evidence. No authority, persistence or supported capture."""

import hashlib
from datetime import date
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, Field, field_validator, model_validator

from app.campaign_performance.presence_contracts import (
    CountCellV1,
    Digest,
    Frozen,
    NativeId,
    Positive,
    _canonical,
    _date,
)
from app.campaign_performance.selected_contracts import ReportingScopeV1

PROFILE = "tiktok.website-payment-count.campaign-day.v1"
MAX_BODY = 1024 * 1024
MAX_PAGES = 100
PAGE_SIZE = 100


class CampaignScopeV1(Frozen):
    native_id: NativeId
    local_id: Positive
    # A supplied description is not independently verified native inventory evidence.
    kind: Literal["regular_auction"]
    origin: Literal["TT_ADS_PLATFORM"]


class TikTokCountQueryV1(Frozen):
    schema_version: Literal["inlet.tiktok-count-query.v1"] = "inlet.tiktok-count-query.v1"
    profile: Literal["tiktok.website-payment-count.campaign-day.v1"] = (
        "tiktok.website-payment-count.campaign-day.v1"
    )
    request_digest: Digest
    scope: ReportingScopeV1
    campaigns: tuple[CampaignScopeV1, ...] = Field(min_length=1, max_length=100)
    starts_on: date
    ends_on: date
    started_at: AwareDatetime
    event: Literal["complete_payment"] = "complete_payment"
    api: Literal["v1.3"] = "v1.3"
    service_type: Literal["AUCTION"] = "AUCTION"
    report_type: Literal["BASIC"] = "BASIC"
    data_level: Literal["AUCTION_CAMPAIGN"] = "AUCTION_CAMPAIGN"
    dimensions: tuple[Literal["campaign_id"], Literal["stat_time_day"]] = (
        "campaign_id",
        "stat_time_day",
    )
    query_lifetime: Literal[False] = False
    campaign_status: Literal["STATUS_ALL"] = "STATUS_ALL"
    page_size: Literal[100] = 100

    _dates = field_validator("starts_on", "ends_on", mode="before")(_date)

    @field_validator("page_size", "query_lifetime", mode="before")
    @classmethod
    def no_coercion(cls, value: object) -> object:
        if type(value) not in (int, bool):
            raise ValueError("exact query scalar required")
        if (type(value) is int and value != 100) or (type(value) is bool and value):
            raise ValueError("exact query scalar required")
        return value

    @model_validator(mode="after")
    def coherent(self) -> "TikTokCountQueryV1":
        if (
            self.scope.platform != "tiktok_ads"
            or not 0 <= (self.ends_on - self.starts_on).days < 30
        ):
            raise ValueError("bounded TikTok dates required")
        if self.ends_on >= self.started_at.astimezone(ZoneInfo(self.scope.time_zone)).date():
            raise ValueError("account-local dates must be closed")
        if len({c.native_id for c in self.campaigns}) != len(self.campaigns) or len(
            {c.local_id for c in self.campaigns}
        ) != len(self.campaigns):
            raise ValueError("one-to-one campaign partition required")
        return self

    def digest(self) -> str:
        return hashlib.sha256(b"inlet.tiktok-count-query.v1\x00" + _canonical(self)).hexdigest()


class TikTokCountRowV1(Frozen):
    native_campaign_id: NativeId
    campaign_id: Positive
    metric_date: date
    count: CountCellV1

    _date = field_validator("metric_date", mode="before")(_date)

    @model_validator(mode="after")
    def count_only(self) -> "TikTokCountRowV1":
        if self.count.presence not in {"present", "missing"}:
            raise ValueError("returned row count must be present or missing")
        return self


class TikTokCountPageV1(Frozen):
    query_digest: Digest
    page: Annotated[int, Field(strict=True, ge=1, le=100)]
    page_size: Annotated[int, Field(strict=True, ge=100, le=100)]
    total_number: Annotated[int, Field(strict=True, ge=1, le=10_000)]
    total_page: Annotated[int, Field(strict=True, ge=1, le=100)]
    request_id: Annotated[str, Field(strict=True, pattern=r"^[A-Za-z0-9_-]{1,128}$")]
    throttle: Literal["absent", "present_unqualified"]
    body_digest: Digest
    acquired_at: AwareDatetime
    rows: tuple[TikTokCountRowV1, ...] = Field(max_length=100)

    @model_validator(mode="after")
    def pagination(self) -> "TikTokCountPageV1":
        if self.total_page != (self.total_number + PAGE_SIZE - 1) // PAGE_SIZE:
            raise ValueError("inconsistent total pages")
        expected = min(PAGE_SIZE, self.total_number - (self.page - 1) * PAGE_SIZE)
        if self.page > self.total_page or len(self.rows) != expected:
            raise ValueError("inconsistent page row count")
        if len({(r.native_campaign_id, r.metric_date) for r in self.rows}) != len(self.rows):
            raise ValueError("duplicate campaign/day")
        return self


class TikTokCountProofV1(Frozen):
    """Retainable proposal only; no justified positive uncapped state exists yet."""

    schema_version: Literal["inlet.tiktok-count-proof.v1"] = "inlet.tiktok-count-proof.v1"
    query: TikTokCountQueryV1
    pages: tuple[TikTokCountPageV1, ...] = Field(min_length=1, max_length=100)
    uncapped: Literal["unknown", "warning_present"]
    provenance: Literal["no_qualified_uncapped_evidence"] = "no_qualified_uncapped_evidence"
    capability: Literal["unknown"] = "unknown"
    effective_attribution: Literal["unknown"] = "unknown"
    value: Literal["unsupported"] = "unsupported"

    @model_validator(mode="after")
    def verify(self) -> "TikTokCountProofV1":
        first = self.pages[0]
        mapping = {c.native_id: c.local_id for c in self.query.campaigns}
        keys: set[tuple[str, date]] = set()
        if len(self.pages) != first.total_page:
            raise ValueError("page coverage incomplete")
        warning = any(p.throttle != "absent" for p in self.pages)
        if self.uncapped != ("warning_present" if warning else "unknown"):
            raise ValueError("uncapped evidence cannot be invented")
        for number, page in enumerate(self.pages, 1):
            if (
                page.query_digest != self.query.digest()
                or page.page != number
                or (page.total_number, page.total_page) != (first.total_number, first.total_page)
                or not 0 <= (page.acquired_at - self.query.started_at).total_seconds() < 60
                or (number > 1 and page.acquired_at < self.pages[number - 2].acquired_at)
            ):
                raise ValueError("page scope or acquisition changed")
            for row in page.rows:
                key = (row.native_campaign_id, row.metric_date)
                if (
                    key in keys
                    or mapping.get(row.native_campaign_id) != row.campaign_id
                    or not self.query.starts_on <= row.metric_date <= self.query.ends_on
                ):
                    raise ValueError("foreign or repeated row")
                keys.add(key)
        if len(keys) != first.total_number:
            raise ValueError("returned provider row total mismatch")
        return self

    def require_complete_capture(self) -> None:
        raise ValueError("positive uncapped completeness evidence unavailable")
