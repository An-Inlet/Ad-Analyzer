"""Documented TikTok regular campaign/ad-group diagnostics, never a financial proof."""

import json
import re
from collections.abc import Callable
from datetime import datetime, timedelta
from decimal import Decimal
from time import monotonic
from typing import Any, Literal
from zoneinfo import ZoneInfo

import httpx
from pydantic import AwareDatetime, Field, TypeAdapter, model_validator

from app.executors.social_http import _private_http
from app.goals.schemas import StrictModel
from app.publication.contracts import fingerprint
from app.publication.execution_contracts import ExecutionAccount, ProviderMandateBinding
from app.publication.optimization_contracts import OptimizationContext


class TikTokNativeInventoryUnavailable(RuntimeError):
    """Fixed private diagnostics only."""


class TikTokNativeInventoryRequest(StrictModel):
    account: ExecutionAccount
    mandate: ProviderMandateBinding
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    time_zone: str = Field(min_length=1, max_length=64)
    period_start: AwareDatetime
    period_end: AwareDatetime

    @model_validator(mode="after")
    def bounded(self) -> "TikTokNativeInventoryRequest":
        ZoneInfo(self.time_zone)
        if (
            self.account.account.platform != "tiktok_ads"
            or not re.fullmatch(r"[0-9]{1,32}", self.account.external_advertiser_id)
            or not timedelta(0) < self.period_end - self.period_start <= timedelta(days=366)
        ):
            raise ValueError("invalid native inventory request")
        return self

    def digest(self) -> str:
        return fingerprint("inlet.tiktok-native-inventory-request.v1", self.model_dump(mode="json"))


class TikTokAccountObservationRequestV2(StrictModel):
    schema_version: Literal["inlet.tiktok-account-observation-request.v2"] = (
        "inlet.tiktok-account-observation-request.v2"
    )
    purpose: Literal["account_diagnostics"] = "account_diagnostics"
    spending_authority: Literal["none"] = "none"
    account: ExecutionAccount
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    time_zone: str = Field(min_length=1, max_length=64)
    period_start: AwareDatetime
    period_end: AwareDatetime

    @model_validator(mode="after")
    def bounded(self) -> "TikTokAccountObservationRequestV2":
        ZoneInfo(self.time_zone)
        if (
            self.account.account.platform != "tiktok_ads"
            or not re.fullmatch(r"[0-9]{1,32}", self.account.external_advertiser_id)
            or not timedelta(0) < self.period_end - self.period_start <= timedelta(days=366)
        ):
            raise ValueError("invalid native inventory request")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


TikTokInventoryRequest = TikTokNativeInventoryRequest | TikTokAccountObservationRequestV2
_request_adapter: TypeAdapter[TikTokInventoryRequest] = TypeAdapter(TikTokInventoryRequest)


class TikTokNativeInventoryContext(OptimizationContext):
    request_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


class TikTokNativeOwner(StrictModel):
    id: str = Field(pattern=r"^[0-9]{1,32}$")
    advertiser_id: str = Field(pattern=r"^[0-9]{1,32}$")
    campaign_id: str = Field(pattern=r"^[0-9]{1,32}$")
    operation_status: str = Field(pattern=r"^[A-Z_]{1,64}$")
    secondary_status: str | None = Field(default=None, pattern=r"^[A-Z_]{1,64}$")
    budget_native: str | None = Field(pattern=r"^[0-9]{1,16}(?:\.[0-9]{1,6})?$")
    budget_mode: str | None = Field(pattern=r"^[A-Z_]{1,64}$")
    budget_optimize_on: bool | None = Field(strict=True)
    campaign_type: str | None = Field(pattern=r"^[A-Z_]{1,64}$")
    objective_type: str | None = Field(pattern=r"^[A-Z_]{1,64}$")
    promotion_type: str | None = Field(pattern=r"^[A-Z_]{1,64}$")
    schedule_type: str | None = Field(pattern=r"^[A-Z_]{1,64}$")
    schedule_start_native: str | None = Field(max_length=40)
    schedule_end_native: str | None = Field(max_length=40)


class TikTokNativeInventory(StrictModel):
    request: TikTokInventoryRequest
    observation_started_at: AwareDatetime
    observed_at: AwareDatetime
    expires_at: AwareDatetime
    advertiser_status: str = Field(pattern=r"^[A-Z_]{1,64}$")
    campaigns: list[TikTokNativeOwner] = Field(max_length=200)
    adgroups: list[TikTokNativeOwner] = Field(max_length=200)
    regular_inventory_read_complete: Literal[True] = True
    all_campaign_families_complete: Literal[False] = False
    historical_obligations_complete: Literal[False] = False
    pending_cap_changes_complete: Literal[False] = False
    accounting_basis: Literal["unqualified"] = "unqualified"
    unit_semantics: Literal["native_decimal_unqualified"] = "native_decimal_unqualified"
    account_cap: None = None
    cap_counter_epoch: None = None
    original_request_terminality: None = None
    reporting_watermark: None = None
    unreported_upper_micros: None = None
    unchanged_future_upper_micros: None = None
    proposed_owner_upper_micros: None = None
    cap_semantics: Literal["unqualified"] = "unqualified"
    reasons: list[str] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def consistent(self) -> "TikTokNativeInventory":
        campaign_ids = {r.id for r in self.campaigns}
        if (
            not self.observation_started_at <= self.observed_at < self.expires_at
            or self.expires_at > self.observation_started_at + timedelta(minutes=5)
            or any(
                r.advertiser_id != self.request.account.external_advertiser_id
                for r in [*self.campaigns, *self.adgroups]
            )
            or len(campaign_ids) != len(self.campaigns)
            or len({r.id for r in self.adgroups}) != len(self.adgroups)
            or any(r.campaign_id != r.id for r in self.campaigns)
            or any(r.campaign_id not in campaign_ids for r in self.adgroups)
        ):
            raise ValueError("native inventory binding invalid")
        return self

    def digest(self) -> str:
        return fingerprint("inlet.tiktok-native-inventory.v1", self.model_dump(mode="json"))


ContextReader = Callable[[TikTokInventoryRequest, datetime], TikTokNativeInventoryContext]


def _budget(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, str | int | Decimal):
        raise TikTokNativeInventoryUnavailable("inventory_budget_invalid")
    raw = str(value)
    if not re.fullmatch(r"[0-9]{1,16}(?:\.[0-9]{1,6})?", raw) or Decimal(raw) > 10**15:
        raise TikTokNativeInventoryUnavailable("inventory_budget_invalid")
    return raw


def _owner(row: dict[str, Any], req: TikTokInventoryRequest, child: bool) -> TikTokNativeOwner:
    if row.get("advertiser_id") != req.account.external_advertiser_id:
        raise TikTokNativeInventoryUnavailable("inventory_owner_mismatch")
    return TikTokNativeOwner(
        id=row["adgroup_id" if child else "campaign_id"],
        advertiser_id=row["advertiser_id"],
        campaign_id=row["campaign_id"],
        operation_status=row["operation_status"],
        secondary_status=row.get("secondary_status"),
        budget_native=_budget(row.get("budget")),
        budget_mode=row.get("budget_mode"),
        budget_optimize_on=None if child else row.get("budget_optimize_on"),
        campaign_type=None if child else row.get("campaign_type"),
        objective_type=None if child else row.get("objective_type"),
        promotion_type=row.get("promotion_type") if child else None,
        schedule_type=row.get("schedule_type") if child else None,
        schedule_start_native=row.get("schedule_start_time") if child else None,
        schedule_end_native=row.get("schedule_end_time") if child else None,
    )


class TikTokNativeInventoryHTTP:
    """Fresh context callback required around IO; no DB or enabled runtime factory."""

    def __init__(
        self,
        context_reader: ContextReader,
        *,
        clock: Callable[[], datetime],
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.context_reader, self.clock, self.transport = context_reader, clock, transport

    def __call__(self, request: TikTokInventoryRequest, now: datetime, /) -> TikTokNativeInventory:
        private = _private_http.set(True)
        try:
            return self._read(_request_adapter.validate_python(request.model_dump()), now)
        except TikTokNativeInventoryUnavailable:
            raise
        except Exception:
            raise TikTokNativeInventoryUnavailable("inventory_unavailable") from None
        finally:
            _private_http.reset(private)

    def _read(self, request: TikTokInventoryRequest, now: datetime) -> TikTokNativeInventory:
        deadline, calls, total_bytes = monotonic() + 60, 0, 0
        expires = now + timedelta(minutes=5)

        def current() -> TikTokNativeInventoryContext:
            nonlocal expires
            observed = self.clock()
            if not now <= observed < expires or monotonic() >= deadline:
                raise TikTokNativeInventoryUnavailable("inventory_expired")
            context = self.context_reader(request, observed)
            expires = min(expires, context.expires_at)
            if (
                context.scope != request.account
                or context.request_digest != request.digest()
                or not context.access_token.get_secret_value()
                or not now <= self.clock() < expires
                or monotonic() >= deadline
            ):
                raise TikTokNativeInventoryUnavailable("inventory_context_changed")
            return context

        with httpx.Client(
            transport=self.transport,
            timeout=httpx.Timeout(12, connect=5),
            follow_redirects=False,
            trust_env=False,
        ) as client:

            def get(edge: str, params: dict[str, str]) -> dict[str, Any]:
                nonlocal calls, total_bytes
                context = current()
                calls += 1
                if calls > 21:
                    raise TikTokNativeInventoryUnavailable("inventory_call_bound")
                with client.stream(
                    "GET",
                    "https://business-api.tiktok.com/open_api/v1.3/" + edge + "/",
                    params=params,
                    headers={
                        "Access-Token": context.access_token.get_secret_value(),
                        "Accept-Encoding": "identity",
                    },
                ) as response:
                    if (
                        response.status_code != 200
                        or response.headers.get("Content-Encoding", "identity") != "identity"
                    ):
                        raise TikTokNativeInventoryUnavailable("inventory_provider_unavailable")
                    raw = bytearray()
                    for chunk in response.iter_bytes():
                        raw.extend(chunk)
                        total_bytes += len(chunk)
                        if (
                            len(raw) > 1_000_000
                            or total_bytes > 4_000_000
                            or monotonic() >= deadline
                        ):
                            raise TikTokNativeInventoryUnavailable("inventory_response_bound")
                current()
                data = json.loads(raw, parse_float=Decimal)
                if (
                    not isinstance(data, dict)
                    or type(data.get("code")) is not int
                    or data["code"] != 0
                    or not isinstance(data.get("data"), dict)
                ):
                    raise TikTokNativeInventoryUnavailable("inventory_response_invalid")
                return dict(data["data"])

            account_data = get(
                "advertiser/info",
                dict(
                    advertiser_ids=json.dumps([request.account.external_advertiser_id]),
                    fields=json.dumps(["advertiser_id", "currency", "timezone", "status"]),
                ),
            )
            accounts = account_data.get("list")
            if (
                not isinstance(accounts, list)
                or len(accounts) != 1
                or not isinstance(accounts[0], dict)
            ):
                raise TikTokNativeInventoryUnavailable("inventory_account_mismatch")
            account = accounts[0]
            if (
                account.get("advertiser_id") != request.account.external_advertiser_id
                or account.get("currency") != request.currency
                or account.get("timezone") != request.time_zone
            ):
                raise TikTokNativeInventoryUnavailable("inventory_account_mismatch")

            def inventory(child: bool) -> list[TikTokNativeOwner]:
                fields = [
                    "advertiser_id",
                    "campaign_id",
                    "operation_status",
                    "secondary_status",
                    "budget",
                    "budget_mode",
                ]
                fields += (
                    [
                        "adgroup_id",
                        "promotion_type",
                        "schedule_type",
                        "schedule_start_time",
                        "schedule_end_time",
                    ]
                    if child
                    else ["campaign_type", "objective_type", "budget_optimize_on"]
                )
                rows: list[TikTokNativeOwner] = []
                ids: set[str] = set()
                expected_pages: int | None = None
                expected_total: int | None = None
                for page in range(1, 11):
                    data = get(
                        "adgroup/get" if child else "campaign/get",
                        dict(
                            advertiser_id=request.account.external_advertiser_id,
                            filtering=json.dumps({"primary_status": "STATUS_ALL"}),
                            fields=json.dumps(fields),
                            page=str(page),
                            page_size="100",
                        ),
                    )
                    batch, paging = data.get("list"), data.get("page_info")
                    if (
                        not isinstance(batch, list)
                        or len(batch) > 100
                        or not isinstance(paging, dict)
                        or type(paging.get("page")) is not int
                        or paging["page"] != page
                        or type(paging.get("total_page")) is not int
                        or not 0 <= paging["total_page"] <= 10
                    ):
                        raise TikTokNativeInventoryUnavailable("inventory_pagination_invalid")
                    pages, total = paging["total_page"], paging.get("total_number")
                    if total is not None and (type(total) is not int or not 0 <= total <= 200):
                        raise TikTokNativeInventoryUnavailable("inventory_pagination_invalid")
                    if expected_pages is not None and (
                        pages != expected_pages or total != expected_total
                    ):
                        raise TikTokNativeInventoryUnavailable("inventory_pagination_changed")
                    expected_pages, expected_total = pages, total
                    if pages == 0:
                        if page == 1 and not batch and total == 0:
                            return []
                        raise TikTokNativeInventoryUnavailable("inventory_pagination_invalid")
                    for raw in batch:
                        if not isinstance(raw, dict):
                            raise TikTokNativeInventoryUnavailable("inventory_response_invalid")
                        row = _owner(raw, request, child)
                        if row.id in ids:
                            raise TikTokNativeInventoryUnavailable("inventory_duplicate")
                        ids.add(row.id)
                        rows.append(row)
                        if len(rows) > 200:
                            raise TikTokNativeInventoryUnavailable("inventory_row_bound")
                    if page == pages:
                        if total is not None and len(rows) != total:
                            raise TikTokNativeInventoryUnavailable("inventory_count_mismatch")
                        return rows
                raise TikTokNativeInventoryUnavailable("inventory_page_bound")

            campaigns, adgroups = inventory(False), inventory(True)
            if any(r.campaign_id not in {c.id for c in campaigns} for r in adgroups):
                raise TikTokNativeInventoryUnavailable("inventory_parent_missing")
            current()
            return TikTokNativeInventory(
                request=request,
                observation_started_at=now,
                observed_at=self.clock(),
                expires_at=expires,
                advertiser_status=account["status"],
                campaigns=campaigns,
                adgroups=adgroups,
                reasons=[
                    "accounting_basis_unqualified",
                    "account_cap_schema_unavailable",
                    "cap_epoch_unavailable",
                    "pending_cap_history_unavailable",
                    "other_campaign_families_unproven",
                    "historical_obligations_unproven",
                    "reporting_completeness_unproven",
                    "external_writer_boundary_unproven",
                    "native_snapshot_not_atomic",
                    "original_request_terminality_unavailable",
                ],
            )
