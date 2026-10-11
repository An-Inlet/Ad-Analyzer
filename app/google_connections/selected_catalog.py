"""Injected reporting-only Google catalog. DTOs are not customer authorization."""

import hashlib
import re
import unicodedata
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import Annotated, Literal

import httpx
from pydantic import AwareDatetime, Field, SecretStr, field_validator, model_validator

from app.campaign_performance.presence_contracts import Digest, Frozen, Id, _canonical
from app.campaign_performance.raw_cells import exact_json
from app.campaign_performance.selected_contracts import ReportingScopeV1
from app.executors.social_http import _private_http
from app.google_connections.selected_presence import query_profile_digest

Family = Literal["conversions", "all_conversions"]


class GoogleReportingCatalogRequestV1(Frozen):
    schema_version: Literal["inlet.google-reporting-catalog-request.v1"] = (
        "inlet.google-reporting-catalog-request.v1"
    )
    scope: ReportingScopeV1
    actor_id: Id
    original_session_digest: Digest = Field(repr=False)
    started_at: AwareDatetime
    api_version: Literal["v24"] = "v24"

    @model_validator(mode="after")
    def google(self) -> "GoogleReportingCatalogRequestV1":
        if self.scope.platform != "google_ads":
            raise ValueError("Google reporting scope required")
        return self

    def digest(self) -> str:
        return hashlib.sha256(
            b"inlet.google-reporting-catalog-request.v1\0" + _canonical(self)
        ).hexdigest()


class GoogleReportingOptionV1(Frozen):
    resource_name: Annotated[
        str, Field(pattern=r"^customers/[0-9]{10}/conversionActions/[0-9]{1,32}$")
    ]
    owner_customer_id: Annotated[str, Field(pattern=r"^[0-9]{10}$")]
    label: Annotated[str, Field(strict=True, min_length=1, max_length=160)]
    status: Literal["ENABLED"]
    category: Annotated[str, Field(strict=True, min_length=1, max_length=100)]
    action_type: Annotated[str, Field(strict=True, min_length=1, max_length=100)]
    metric_family: Family
    query_profile_digest: Digest

    @model_validator(mode="after")
    def consistent(self) -> "GoogleReportingOptionV1":
        if (
            self.resource_name.split("/")[1] != self.owner_customer_id
            or self.query_profile_digest != query_profile_digest(self.metric_family)
            or not self.label.strip()
            or any(unicodedata.category(c).startswith("C") for c in self.label)
            or re.search(r"customers/[0-9]+/", self.label)
            or any(
                re.fullmatch(r"[A-Z][A-Z0-9_]*", x) is None
                for x in (self.category, self.action_type)
            )
        ):
            raise ValueError("invalid reporting option")
        return self

    def identifier(self, request: GoogleReportingCatalogRequestV1) -> str:
        req = GoogleReportingCatalogRequestV1.model_validate(request)
        option = GoogleReportingOptionV1.model_validate(self)
        if option.owner_customer_id != req.scope.native_account_id:
            raise ValueError("foreign reporting option")
        stable = req.model_copy(update={"started_at": datetime(2000, 1, 1, tzinfo=UTC)})
        return hashlib.sha256(
            b"inlet.google-reporting-option.v1\0" + _canonical(stable) + b"\0" + _canonical(option)
        ).hexdigest()


class GoogleReportingCatalogV1(Frozen):
    schema_version: Literal["inlet.google-reporting-catalog.v1"] = (
        "inlet.google-reporting-catalog.v1"
    )
    request: GoogleReportingCatalogRequestV1 = Field(repr=False)
    request_digest: Digest
    observed_at: AwareDatetime
    expires_at: AwareDatetime
    pagination_complete: Literal[True] = True
    page_count: Annotated[int, Field(strict=True, ge=1, le=100)]
    options: tuple[GoogleReportingOptionV1, ...] = Field(max_length=2000)

    @field_validator("pagination_complete", mode="before")
    @classmethod
    def strict_complete(cls, value: object) -> object:
        if value is not True:
            raise ValueError("complete pagination required")
        return value

    @model_validator(mode="after")
    def graph(self) -> "GoogleReportingCatalogV1":
        if self.request_digest != self.request.digest() or not (
            self.request.started_at
            <= self.observed_at
            < self.expires_at
            <= self.observed_at + timedelta(minutes=5)
        ):
            raise ValueError("catalog binding expired")
        grouped: dict[str, list[GoogleReportingOptionV1]] = {}
        for item in self.options:
            item.identifier(self.request)
            grouped.setdefault(item.resource_name, []).append(item)
        for pair in grouped.values():
            if len(pair) != 2 or {p.metric_family for p in pair} != {
                "conversions",
                "all_conversions",
            }:
                raise ValueError("catalog requires both explicit metric choices")
            if pair[0].model_dump(exclude={"metric_family", "query_profile_digest"}) != pair[
                1
            ].model_dump(exclude={"metric_family", "query_profile_digest"}):
                raise ValueError("option metadata mismatch")
        if len(_canonical(self)) > 256 * 1024:
            raise ValueError("catalog byte bound")
        return self

    def digest(self) -> str:
        checked = GoogleReportingCatalogV1.model_validate(self)
        return hashlib.sha256(
            b"inlet.google-reporting-catalog.v1\0" + _canonical(checked)
        ).hexdigest()


class GoogleReportingCatalogContext(Frozen):
    request_digest: Digest
    expires_at: AwareDatetime
    access_token: SecretStr = Field(exclude=True, repr=False)
    developer_token: SecretStr = Field(exclude=True, repr=False)
    login_customer_id: Annotated[str, Field(strict=True, pattern=r"^[0-9]{10}$")] | None = Field(
        default=None, exclude=True, repr=False
    )


class GoogleReportingCatalogUnavailable(RuntimeError):
    pass


class GoogleReportingCatalogHTTP:
    def __init__(
        self,
        context_reader: Callable[[GoogleReportingCatalogRequestV1], GoogleReportingCatalogContext],
        revalidate: Callable[[GoogleReportingCatalogRequestV1], None],
        *,
        transport: httpx.BaseTransport,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.context_reader, self.revalidate = context_reader, revalidate
        self.transport, self.clock = transport, clock

    def __call__(self, request: GoogleReportingCatalogRequestV1) -> GoogleReportingCatalogV1:
        private = _private_http.set(True)
        try:
            req = GoogleReportingCatalogRequestV1.model_validate(request)
            deadline = monotonic() + 60
            limit = self.clock() + timedelta(seconds=60)
            self.revalidate(req)
            ctx = GoogleReportingCatalogContext.model_validate(self.context_reader(req))
            if ctx.request_digest != req.digest() or not (
                ctx.access_token.get_secret_value() and ctx.developer_token.get_secret_value()
            ):
                raise ValueError("context mismatch")
            limit = min(limit, ctx.expires_at)

            def time_check() -> None:
                if not req.started_at <= self.clock() < limit or monotonic() >= deadline:
                    raise ValueError("catalog deadline")

            def check() -> None:
                time_check()
                self.revalidate(req)
                time_check()

            check()
            native = req.scope.native_account_id
            headers = {
                "Authorization": "Bearer " + ctx.access_token.get_secret_value(),
                "developer-token": ctx.developer_token.get_secret_value(),
                "Accept-Encoding": "identity",
            }
            if ctx.login_customer_id:
                headers["login-customer-id"] = ctx.login_customer_id
            size = 0
            with httpx.Client(
                transport=self.transport,
                timeout=httpx.Timeout(12, connect=5),
                follow_redirects=False,
                trust_env=False,
            ) as client:

                def read(query: str, cursor: str = "") -> dict[str, object]:
                    nonlocal size
                    check()
                    with client.stream(
                        "POST",
                        f"https://googleads.googleapis.com/v24/customers/{native}/googleAds:search",
                        headers=headers,
                        json={"query": query, "pageToken": cursor},
                    ) as response:
                        if response.status_code != 200:
                            raise ValueError("catalog HTTP unavailable")
                        body = bytearray()
                        for chunk in response.iter_bytes():
                            time_check()
                            size += len(chunk)
                            if size > 8_000_000:
                                raise ValueError("catalog body bound")
                            body.extend(chunk)
                    check()
                    data = exact_json(bytes(body), limit=8_000_000)
                    if "error" in data:
                        raise ValueError("catalog provider error")
                    return data

                meta = read(
                    "SELECT customer.id, customer.resource_name, customer.currency_code, "
                    "customer.time_zone FROM customer"
                )
                if meta.get("nextPageToken", "") != "" or meta.get("results") != [
                    {
                        "customer": {
                            "id": native,
                            "resourceName": f"customers/{native}",
                            "currencyCode": req.scope.currency,
                            "timeZone": req.scope.time_zone,
                        }
                    }
                ]:
                    raise ValueError("account metadata mismatch")
                cursor = ""
                seen: set[str] = set()
                resources: set[str] = set()
                options: list[GoogleReportingOptionV1] = []
                for _page_count in range(1, 101):
                    data = read(
                        "SELECT conversion_action.resource_name, conversion_action.owner_customer, "
                        "conversion_action.name, conversion_action.status, "
                        "conversion_action.category, "
                        "conversion_action.type FROM conversion_action "
                        "WHERE conversion_action.status = 'ENABLED'",
                        cursor,
                    )
                    rows = data.get("results", [])
                    if type(rows) is not list or len(rows) > 1000:
                        raise ValueError("catalog rows bound")
                    for row in rows:
                        action = row["conversionAction"]
                        if action["ownerCustomer"] != f"customers/{native}":
                            raise ValueError("foreign owner")
                        families: tuple[Family, Family] = ("conversions", "all_conversions")
                        for family in families:
                            option = GoogleReportingOptionV1(
                                resource_name=action["resourceName"],
                                owner_customer_id=action["ownerCustomer"].removeprefix(
                                    "customers/"
                                ),
                                label=action["name"],
                                status=action["status"],
                                category=action["category"],
                                action_type=action["type"],
                                metric_family=family,
                                query_profile_digest=query_profile_digest(family),
                            )
                            option.identifier(req)
                            options.append(option)
                        if option.resource_name in resources:
                            raise ValueError("duplicate action")
                        resources.add(option.resource_name)
                        if len(resources) > 1000:
                            raise ValueError("catalog action bound")
                    following = data.get("nextPageToken", "")
                    if (
                        type(following) is not str
                        or len(following) > 3000
                        or (following and following in seen)
                    ):
                        raise ValueError("catalog cursor invalid")
                    if not following:
                        break
                    seen.add(following)
                    cursor = following
                else:
                    raise ValueError("catalog page bound")
            check()
            result = GoogleReportingCatalogV1(
                request=req,
                request_digest=req.digest(),
                observed_at=self.clock(),
                expires_at=limit,
                page_count=_page_count,
                options=tuple(sorted(options, key=lambda x: (x.resource_name, x.metric_family))),
            )
            check()
            return result
        except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError, ArithmeticError):
            raise GoogleReportingCatalogUnavailable(
                "google_reporting_catalog_unavailable"
            ) from None
        finally:
            _private_http.reset(private)
