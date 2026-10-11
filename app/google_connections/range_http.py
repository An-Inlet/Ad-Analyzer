"""Injected closed-range aggregate observations, never selected-event or SQL authority."""

import hashlib
import re
import unicodedata
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from time import monotonic
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

import httpx
from pydantic import AwareDatetime, Field, field_serializer, field_validator, model_validator

from app.campaign_performance.aggregate import ReportingDescriptor
from app.campaign_performance.presence_contracts import (
    MAX_INTEGER_COUNT,
    MAX_MONEY_MICROS,
    CountCellV1,
    Digest,
    Frozen,
    NativeId,
    _canonical,
    _date,
    _decimal_text,
)
from app.campaign_performance.raw_cells import count_cell, exact_json, integer_cell, money_cell
from app.campaign_performance.selected_contracts import _instant, _utc
from app.executors.social_http import _private_http
from app.google_connections.selected_catalog import (
    GoogleReportingCatalogContext,
    GoogleReportingCatalogRequestV1,
)

MAX_BYTES = 32 * 1024 * 1024


class GoogleAggregateRangeRequestV1(Frozen):
    schema_version: Literal["inlet.google-aggregate-range-request.v1"] = (
        "inlet.google-aggregate-range-request.v1"
    )
    base: GoogleReportingCatalogRequestV1
    requested_starts_on: date
    requested_ends_on: date
    _dates = field_validator("requested_starts_on", "requested_ends_on", mode="before")(_date)

    @model_validator(mode="after")
    def window(self) -> "GoogleAggregateRangeRequestV1":
        if not 0 <= (self.requested_ends_on - self.requested_starts_on).days < 400 or (
            self.requested_ends_on
            >= self.base.started_at.astimezone(ZoneInfo(self.base.scope.time_zone)).date()
        ):
            raise ValueError("closed bounded range required")
        return self

    def digest(self) -> str:
        checked = GoogleAggregateRangeRequestV1.model_validate(self)
        return hashlib.sha256(
            b"inlet.google-aggregate-range-request.v1\0"
            + checked.base.digest().encode()
            + b"\0"
            + _canonical(checked)
        ).hexdigest()


class GoogleAggregateCampaignV1(Frozen):
    native_campaign_id: NativeId
    resource_name: Annotated[
        str, Field(strict=True, pattern=r"^customers/[0-9]{10}/campaigns/[0-9]{1,32}$")
    ]
    name: Annotated[str, Field(strict=True, min_length=1, max_length=255)]
    status: Literal["ENABLED", "PAUSED", "REMOVED"]
    channel: Annotated[str, Field(strict=True, pattern=r"^[A-Z][A-Z0-9_]{0,63}$")]

    @model_validator(mode="after")
    def identity(self) -> "GoogleAggregateCampaignV1":
        if (
            self.resource_name.split("/")[-1] != self.native_campaign_id
            or not self.name.strip()
            or any(unicodedata.category(c).startswith("C") for c in self.name)
        ):
            raise ValueError("invalid campaign identity")
        return self


class GoogleAggregateMetricV1(Frozen):
    native_campaign_id: NativeId
    resource_name: Annotated[
        str, Field(strict=True, pattern=r"^customers/[0-9]{10}/campaigns/[0-9]{1,32}$")
    ]
    metric_date: date
    impressions: Annotated[int, Field(strict=True, ge=0, le=MAX_INTEGER_COUNT)]
    clicks: Annotated[int, Field(strict=True, ge=0, le=MAX_INTEGER_COUNT)]
    cost_micros: Annotated[int, Field(strict=True, ge=0, le=MAX_MONEY_MICROS)]
    conversions: Decimal
    conversion_value_micros: Annotated[int, Field(strict=True, ge=0, le=MAX_MONEY_MICROS)]
    _date_field = field_validator("metric_date", mode="before")(_date)

    @field_validator("conversions", mode="before")
    @classmethod
    def exact_count(cls, value: object) -> Decimal:
        cell = CountCellV1(presence="present", value=value)
        assert cell.value is not None
        return cell.value

    @field_serializer("conversions", when_used="json")
    def decimal_json(self, value: Decimal) -> str:
        return _decimal_text(value)

    @model_validator(mode="after")
    def identity(self) -> "GoogleAggregateMetricV1":
        if self.resource_name.split("/")[-1] != self.native_campaign_id:
            raise ValueError("campaign metric identity mismatch")
        return self


class GoogleAggregateRangeV1(Frozen):
    schema_version: Literal["inlet.google-aggregate-range.v1"] = "inlet.google-aggregate-range.v1"
    request: GoogleAggregateRangeRequestV1
    request_digest: Digest
    completed_at: AwareDatetime
    expires_at: AwareDatetime
    pagination_complete: Literal[True] = True
    page_count: Annotated[int, Field(strict=True, ge=1, le=100)]
    campaigns: tuple[GoogleAggregateCampaignV1, ...] = Field(max_length=50_000)
    metrics: tuple[GoogleAggregateMetricV1, ...] = Field(max_length=50_000)
    _times = field_validator("completed_at", "expires_at", mode="before")(_instant)
    _times_utc = field_validator("completed_at", "expires_at")(_utc)

    @field_validator("pagination_complete", mode="before")
    @classmethod
    def complete(cls, value: object) -> object:
        if value is not True:
            raise ValueError("complete pagination required")
        return value

    @model_validator(mode="after")
    def graph(self) -> "GoogleAggregateRangeV1":
        req = self.request
        if (
            self.request_digest != req.digest()
            or not (
                req.base.started_at
                <= self.completed_at
                < self.expires_at
                <= req.base.started_at + timedelta(seconds=60)
            )
            or len(self.campaigns) + len(self.metrics) > 50_000
        ):
            raise ValueError("aggregate range binding unavailable")
        inventory = {c.native_campaign_id: c.resource_name for c in self.campaigns}
        if len(inventory) != len(self.campaigns) or any(
            c.resource_name
            != f"customers/{req.base.scope.native_account_id}/campaigns/{c.native_campaign_id}"
            for c in self.campaigns
        ):
            raise ValueError("aggregate inventory mismatch")
        keys: set[tuple[str, date]] = set()
        for row in self.metrics:
            key = (row.native_campaign_id, row.metric_date)
            if (
                key in keys
                or inventory.get(row.native_campaign_id) != row.resource_name
                or not (req.requested_starts_on <= row.metric_date <= req.requested_ends_on)
            ):
                raise ValueError("aggregate metric mapping mismatch")
            keys.add(key)
        if len(_canonical(self)) > MAX_BYTES:
            raise ValueError("aggregate result byte bound")
        return self

    def digest(self) -> str:
        checked = GoogleAggregateRangeV1.model_validate(self)
        ordered = checked.model_copy(
            update={
                "campaigns": tuple(sorted(checked.campaigns, key=lambda x: x.native_campaign_id)),
                "metrics": tuple(
                    sorted(checked.metrics, key=lambda x: (x.native_campaign_id, x.metric_date))
                ),
            }
        )
        return hashlib.sha256(
            b"inlet.google-aggregate-range.v1\0" + _canonical(ordered)
        ).hexdigest()


class GoogleAggregateRangeUnavailable(RuntimeError):
    pass


def _micros(value: object) -> int:
    if type(value) is str and re.fullmatch(r"(?:0|[1-9][0-9]{0,18})", value):
        value = int(value)
    if type(value) is not int or not 0 <= value <= MAX_MONEY_MICROS:
        raise ValueError("exact integer micros required")
    return value


class GoogleAggregateRangeHTTP:
    def __init__(
        self,
        context_reader: Callable[[GoogleReportingCatalogRequestV1], GoogleReportingCatalogContext],
        revalidate: Callable[[GoogleReportingCatalogRequestV1], None],
        *,
        transport: httpx.BaseTransport,
        clock: Callable[[], datetime],
    ) -> None:
        self.context_reader, self.revalidate = context_reader, revalidate
        self.transport, self.clock = transport, clock

    @property
    def performance_contract(self) -> ReportingDescriptor:
        return ReportingDescriptor("google_ads", "google.v24.campaign-day.metrics-conversions.v1")

    def _now(self) -> datetime:
        value = self.clock()
        if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("aware range clock required")
        return value.astimezone(UTC)

    def __call__(self, request: GoogleAggregateRangeRequestV1) -> GoogleAggregateRangeV1:
        private = _private_http.set(True)
        try:
            req = GoogleAggregateRangeRequestV1.model_validate(request)
            deadline = monotonic() + 60
            expires = min(
                self._now() + timedelta(seconds=60), req.base.started_at + timedelta(seconds=60)
            )

            def time_check() -> None:
                if not req.base.started_at <= self._now() < expires or monotonic() >= deadline:
                    raise ValueError("aggregate range expired")

            def check() -> None:
                time_check()
                self.revalidate(req.base)
                time_check()

            check()
            ctx = GoogleReportingCatalogContext.model_validate(self.context_reader(req.base))
            if ctx.request_digest != req.base.digest() or not (
                ctx.access_token.get_secret_value() and ctx.developer_token.get_secret_value()
            ):
                raise ValueError("range context mismatch")
            expires = min(expires, ctx.expires_at)
            check()
            aid = req.base.scope.native_account_id
            headers = {
                "Authorization": "Bearer " + ctx.access_token.get_secret_value(),
                "developer-token": ctx.developer_token.get_secret_value(),
                "Accept-Encoding": "identity",
            }
            if ctx.login_customer_id:
                headers["login-customer-id"] = ctx.login_customer_id
            pages = 0
            byte_size = 0
            with httpx.Client(
                transport=self.transport,
                timeout=httpx.Timeout(12, connect=5),
                follow_redirects=False,
                trust_env=False,
            ) as client:

                def read(query: str, cursor: str = "") -> tuple[list[dict[str, object]], str]:
                    nonlocal pages, byte_size
                    check()
                    pages += 1
                    if pages > 100:
                        raise ValueError("aggregate page bound")
                    with client.stream(
                        "POST",
                        f"https://googleads.googleapis.com/v24/customers/{aid}/googleAds:search",
                        headers=headers,
                        json={"query": query, "pageToken": cursor},
                    ) as response:
                        if response.status_code != 200:
                            raise ValueError("aggregate HTTP unavailable")
                        raw = bytearray()
                        for chunk in response.iter_bytes():
                            time_check()
                            byte_size += len(chunk)
                            if byte_size > MAX_BYTES:
                                raise ValueError("aggregate body bound")
                            raw.extend(chunk)
                    check()
                    data = exact_json(bytes(raw), limit=MAX_BYTES)
                    rows, token = data.get("results", []), data.get("nextPageToken", "")
                    if (
                        "error" in data
                        or type(rows) is not list
                        or len(rows) > 50_000
                        or any(type(row) is not dict for row in rows)
                        or type(token) is not str
                        or len(token) > 3000
                    ):
                        raise ValueError("aggregate page invalid")
                    return rows, token

                metadata, following = read(
                    "SELECT customer.id, customer.resource_name, customer.currency_code, "
                    "customer.time_zone FROM customer"
                )
                if following or metadata != [
                    {
                        "customer": {
                            "id": aid,
                            "resourceName": f"customers/{aid}",
                            "currencyCode": req.base.scope.currency,
                            "timeZone": req.base.scope.time_zone,
                        }
                    }
                ]:
                    raise ValueError("aggregate account mismatch")
                campaigns: list[GoogleAggregateCampaignV1] = []
                metrics: list[GoogleAggregateMetricV1] = []
                for phase in ("campaigns", "metrics"):
                    cursor = ""
                    seen: set[str] = set()
                    query = (
                        "SELECT campaign.id, campaign.resource_name, campaign.name, "
                        "campaign.status, campaign.advertising_channel_type FROM campaign"
                    )
                    if phase == "metrics":
                        query = (
                            "SELECT campaign.id, campaign.resource_name, segments.date, "
                            "metrics.impressions, metrics.clicks, metrics.cost_micros, "
                            "metrics.conversions, metrics.conversions_value FROM campaign "
                            "WHERE segments.date BETWEEN "
                            + f"'{req.requested_starts_on.isoformat()}' AND "
                            + f"'{req.requested_ends_on.isoformat()}'"
                        )
                    while True:
                        rows, following = read(query, cursor)
                        if len(campaigns) + len(metrics) + len(rows) > 50_000:
                            raise ValueError("aggregate row bound")
                        for row in rows:
                            campaign = row["campaign"]
                            if type(campaign) is not dict:
                                raise ValueError("invalid campaign")
                            if phase == "campaigns":
                                campaigns.append(
                                    GoogleAggregateCampaignV1(
                                        native_campaign_id=campaign["id"],
                                        resource_name=campaign["resourceName"],
                                        name=campaign["name"],
                                        status=campaign["status"],
                                        channel=campaign["advertisingChannelType"],
                                    )
                                )
                            else:
                                values, segments = row["metrics"], row["segments"]
                                if type(values) is not dict or type(segments) is not dict:
                                    raise ValueError("invalid aggregate cells")
                                # Required indexing prevents missing supported fields becoming zero.
                                for key in (
                                    "impressions",
                                    "clicks",
                                    "costMicros",
                                    "conversions",
                                    "conversionsValue",
                                ):
                                    if key not in values:
                                        raise ValueError("required aggregate cell missing")
                                metrics.append(
                                    GoogleAggregateMetricV1(
                                        native_campaign_id=campaign["id"],
                                        resource_name=campaign["resourceName"],
                                        metric_date=segments["date"],
                                        impressions=integer_cell(values, "impressions").value,
                                        clicks=integer_cell(values, "clicks").value,
                                        cost_micros=_micros(values["costMicros"]),
                                        conversions=count_cell(values, "conversions").value,
                                        conversion_value_micros=money_cell(
                                            values, "conversionsValue"
                                        ).value,
                                    )
                                )
                        if not following:
                            break
                        if following in seen:
                            raise ValueError("aggregate cursor cycle")
                        seen.add(following)
                        cursor = following
            check()
            result = GoogleAggregateRangeV1(
                request=req,
                request_digest=req.digest(),
                completed_at=self._now(),
                expires_at=expires,
                page_count=pages,
                campaigns=tuple(sorted(campaigns, key=lambda x: x.native_campaign_id)),
                metrics=tuple(sorted(metrics, key=lambda x: (x.native_campaign_id, x.metric_date))),
            )
            check()
            return result
        except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError, ArithmeticError):
            raise GoogleAggregateRangeUnavailable("google_aggregate_range_unavailable") from None
        finally:
            _private_http.reset(private)
