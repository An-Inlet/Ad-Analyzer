"""Bounded account-wide Meta diagnostics; never a spending or finality proof source."""

import hashlib
import hmac
import json
import re
from collections.abc import Callable
from datetime import datetime, timedelta
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


class MetaNativeInventoryUnavailable(RuntimeError):
    """Fixed diagnostics only; no raw response, token, cursor or account identifier."""


class MetaNativeInventoryRequest(StrictModel):
    account: ExecutionAccount
    mandate: ProviderMandateBinding
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    time_zone: str = Field(min_length=1, max_length=64)
    period_start: AwareDatetime
    period_end: AwareDatetime

    @model_validator(mode="after")
    def bounded(self) -> "MetaNativeInventoryRequest":
        ZoneInfo(self.time_zone)
        if (
            self.account.account.platform != "meta_ads"
            or not re.fullmatch(r"[0-9]{1,32}", self.account.external_advertiser_id)
            or not timedelta(0) < self.period_end - self.period_start <= timedelta(days=366)
        ):
            raise ValueError("invalid native inventory request")
        return self

    def digest(self) -> str:
        return fingerprint("inlet.meta-native-inventory-request.v1", self.model_dump(mode="json"))


class MetaAccountObservationRequestV2(StrictModel):
    schema_version: Literal["inlet.meta-account-observation-request.v2"] = (
        "inlet.meta-account-observation-request.v2"
    )
    purpose: Literal["account_diagnostics"] = "account_diagnostics"
    spending_authority: Literal["none"] = "none"
    account: ExecutionAccount
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    time_zone: str = Field(min_length=1, max_length=64)
    period_start: AwareDatetime
    period_end: AwareDatetime

    @model_validator(mode="after")
    def bounded(self) -> "MetaAccountObservationRequestV2":
        ZoneInfo(self.time_zone)
        if (
            self.account.account.platform != "meta_ads"
            or not re.fullmatch(r"[0-9]{1,32}", self.account.external_advertiser_id)
            or not timedelta(0) < self.period_end - self.period_start <= timedelta(days=366)
        ):
            raise ValueError("invalid native inventory request")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


MetaInventoryRequest = MetaNativeInventoryRequest | MetaAccountObservationRequestV2
_request_adapter: TypeAdapter[MetaInventoryRequest] = TypeAdapter(MetaInventoryRequest)


class MetaNativeInventoryContext(OptimizationContext):
    request_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


class MetaNativeOwner(StrictModel):
    id: str = Field(pattern=r"^[0-9]{1,32}$")
    account_id: str = Field(pattern=r"^[0-9]{1,32}$")
    campaign_id: str | None = Field(pattern=r"^[0-9]{1,32}$")
    configured_status: str = Field(pattern=r"^[A-Z_]{1,64}$")
    effective_status: str = Field(pattern=r"^[A-Z_]{1,64}$")
    daily_budget_native: int | None = Field(strict=True, ge=0, le=10**15)
    lifetime_budget_native: int | None = Field(strict=True, ge=0, le=10**15)
    spend_cap_native: int | None = Field(strict=True, ge=0, le=10**15)
    starts_at: AwareDatetime | None
    ends_at: AwareDatetime | None
    budget_schedule_enabled: bool | None = Field(strict=True)
    budget_sharing_enabled: bool | None = Field(strict=True)
    budget_rebalance_enabled: bool | None = Field(strict=True)


class MetaNativeInventory(StrictModel):
    request: MetaInventoryRequest
    observation_started_at: AwareDatetime
    observed_at: AwareDatetime
    expires_at: AwareDatetime
    account_status: int = Field(strict=True, ge=0)
    amount_spent_native: int | None = Field(strict=True, ge=0, le=10**15)
    spend_cap_native: int | None = Field(strict=True, ge=0, le=10**15)
    campaigns: list[MetaNativeOwner] = Field(max_length=200)
    adsets: list[MetaNativeOwner] = Field(max_length=200)
    advertising_inventory_read_complete: bool
    status_scope: Literal["sdk_known_effective_statuses_only"] = "sdk_known_effective_statuses_only"
    all_effective_statuses_complete: Literal[False] = False
    # All counters are observations, not a period attribution or residual calculation.
    accounting_basis: Literal["unqualified"] = "unqualified"
    unit_semantics: Literal["native_integer_unqualified"] = "native_integer_unqualified"
    cap_counter_epoch: None = None
    pending_cap_changes_complete: Literal[False] = False
    historical_obligations_complete: Literal[False] = False
    reporting_watermark: None = None
    unreported_upper_micros: None = None
    unchanged_future_upper_micros: None = None
    proposed_owner_upper_micros: None = None
    cap_semantics: Literal["unqualified"] = "unqualified"
    reasons: list[str] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def consistent(self) -> "MetaNativeInventory":
        if (
            not self.observation_started_at <= self.observed_at < self.expires_at
            or self.expires_at > self.observation_started_at + timedelta(minutes=5)
            or any(
                r.account_id != self.request.account.external_advertiser_id
                for r in [*self.campaigns, *self.adsets]
            )
            or len({r.id for r in self.campaigns}) != len(self.campaigns)
            or len({r.id for r in self.adsets}) != len(self.adsets)
            or any(r.campaign_id is not None for r in self.campaigns)
            or any(r.campaign_id not in {c.id for c in self.campaigns} for r in self.adsets)
        ):
            raise ValueError("native inventory binding invalid")
        return self

    def digest(self) -> str:
        return fingerprint("inlet.meta-native-inventory.v1", self.model_dump(mode="json"))


ContextReader = Callable[[MetaInventoryRequest, datetime], MetaNativeInventoryContext]
CAMPAIGN_STATUSES = ["ACTIVE", "PAUSED", "ARCHIVED", "DELETED", "IN_PROCESS", "WITH_ISSUES"]
ADSET_STATUSES = [*CAMPAIGN_STATUSES, "CAMPAIGN_PAUSED"]
COMMON_FIELDS = (
    "id,account_id,configured_status,effective_status,daily_budget,lifetime_budget,"
    "start_time,is_budget_schedule_enabled"
)


def _amount(value: Any) -> int | None:
    if value is None:
        return None
    if type(value) is int and 0 <= value <= 10**15:
        return value
    if isinstance(value, str) and re.fullmatch(r"[0-9]{1,16}", value):
        amount = int(value)
        if amount <= 10**15:
            return amount
    raise MetaNativeInventoryUnavailable("inventory_amount_invalid")


def _owner(row: dict[str, Any], request: MetaInventoryRequest, child: bool) -> MetaNativeOwner:
    if row.get("account_id") != request.account.external_advertiser_id:
        raise MetaNativeInventoryUnavailable("inventory_owner_mismatch")
    return MetaNativeOwner(
        id=row["id"],
        account_id=row["account_id"],
        campaign_id=row["campaign_id"] if child else None,
        configured_status=row["configured_status"],
        effective_status=row["effective_status"],
        daily_budget_native=_amount(row.get("daily_budget")),
        lifetime_budget_native=_amount(row.get("lifetime_budget")),
        spend_cap_native=_amount(row.get("lifetime_spend_cap" if child else "spend_cap")),
        starts_at=row.get("start_time"),
        ends_at=row.get("end_time" if child else "stop_time"),
        budget_schedule_enabled=row.get("is_budget_schedule_enabled"),
        budget_sharing_enabled=None if child else row.get("is_adset_budget_sharing_enabled"),
        budget_rebalance_enabled=None if child else row.get("budget_rebalance_flag"),
    )


class MetaNativeInventoryHTTP:
    """Context reader must freshly resolve current generation/authorization on every call.

    No session/locks or default factory are owned here. Callers revalidate owner/mandate
    around external IO; a cached context resolver does not satisfy that integration.
    """

    def __init__(
        self,
        context_reader: ContextReader,
        *,
        clock: Callable[[], datetime],
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.context_reader, self.clock, self.transport = context_reader, clock, transport

    def __call__(self, request: MetaInventoryRequest, now: datetime, /) -> MetaNativeInventory:
        private = _private_http.set(True)
        try:
            return self._read(_request_adapter.validate_python(request.model_dump()), now)
        except MetaNativeInventoryUnavailable:
            raise
        except Exception:
            # Context resolvers and malformed provider errors can contain private material.
            raise MetaNativeInventoryUnavailable("inventory_unavailable") from None
        finally:
            _private_http.reset(private)

    def _read(self, request: MetaInventoryRequest, now: datetime) -> MetaNativeInventory:
        deadline, calls, total_bytes = monotonic() + 60, 0, 0
        expires = now + timedelta(minutes=5)

        def current() -> MetaNativeInventoryContext:
            nonlocal expires
            observed = self.clock()
            if not now <= observed < expires or monotonic() >= deadline:
                raise MetaNativeInventoryUnavailable("inventory_expired")
            context = self.context_reader(request, observed)
            expires = min(expires, context.expires_at)
            # The resolver can block; use a fresh clock after it returns.
            if (
                context.scope != request.account
                or context.request_digest != request.digest()
                or not context.access_token.get_secret_value()
                or not now <= self.clock() < expires
                or monotonic() >= deadline
            ):
                raise MetaNativeInventoryUnavailable("inventory_context_changed")
            return context

        base = "https://graph.facebook.com/v26.0/act_" + request.account.external_advertiser_id
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
                    raise MetaNativeInventoryUnavailable("inventory_call_bound")
                token = context.access_token.get_secret_value()
                query = dict(params)
                if context.app_secret is not None:
                    query["appsecret_proof"] = hmac.new(
                        context.app_secret.get_secret_value().encode(),
                        token.encode(),
                        hashlib.sha256,
                    ).hexdigest()
                with client.stream(
                    "GET",
                    base + edge,
                    params=query,
                    headers={"Authorization": "Bearer " + token, "Accept-Encoding": "identity"},
                ) as response:
                    if (
                        response.status_code != 200
                        or response.headers.get("Content-Encoding", "identity") != "identity"
                    ):
                        raise MetaNativeInventoryUnavailable("inventory_provider_unavailable")
                    raw = bytearray()
                    for chunk in response.iter_bytes():
                        raw.extend(chunk)
                        total_bytes += len(chunk)
                        if (
                            len(raw) > 1_000_000
                            or total_bytes > 4_000_000
                            or monotonic() >= deadline
                        ):
                            raise MetaNativeInventoryUnavailable("inventory_response_bound")
                current()  # revoked or rotated generation after IO cannot return old evidence
                data = json.loads(raw)
                if not isinstance(data, dict) or "error" in data:
                    raise MetaNativeInventoryUnavailable("inventory_response_invalid")
                return data

            account = get(
                "",
                {
                    "fields": "account_id,currency,timezone_name,account_status,"
                    "amount_spent,spend_cap"
                },
            )
            if (
                account.get("account_id") != request.account.external_advertiser_id
                or account.get("currency") != request.currency
                or account.get("timezone_name") != request.time_zone
                or type(account.get("account_status")) is not int
            ):
                raise MetaNativeInventoryUnavailable("inventory_account_mismatch")

            def inventory(child: bool) -> list[MetaNativeOwner]:
                fields = COMMON_FIELDS + (
                    ",campaign_id,end_time,lifetime_spend_cap"
                    if child
                    else ",stop_time,spend_cap,is_adset_budget_sharing_enabled,"
                    "budget_rebalance_flag"
                )
                params = {
                    "fields": fields,
                    "limit": "100",
                    "effective_status": json.dumps(ADSET_STATUSES if child else CAMPAIGN_STATUSES),
                }
                rows: list[MetaNativeOwner] = []
                identifiers: set[str] = set()
                cursors: set[str] = set()
                for _ in range(10):
                    data = get("/adsets" if child else "/campaigns", params)
                    batch = data.get("data")
                    if not isinstance(batch, list):
                        raise MetaNativeInventoryUnavailable("inventory_response_invalid")
                    for raw in batch:
                        if not isinstance(raw, dict):
                            raise MetaNativeInventoryUnavailable("inventory_response_invalid")
                        row = _owner(raw, request, child)
                        if row.id in identifiers:
                            raise MetaNativeInventoryUnavailable("inventory_duplicate")
                        identifiers.add(row.id)
                        rows.append(row)
                        if len(rows) > 200:
                            raise MetaNativeInventoryUnavailable("inventory_row_bound")
                    paging = data.get("paging", {})
                    if not isinstance(paging, dict):
                        raise MetaNativeInventoryUnavailable("inventory_pagination_invalid")
                    if not paging.get("next"):
                        return rows
                    cursor_map = paging.get("cursors")
                    cursor = cursor_map.get("after") if isinstance(cursor_map, dict) else None
                    if (
                        not isinstance(cursor, str)
                        or not 1 <= len(cursor) <= 1024
                        or cursor in cursors
                    ):
                        raise MetaNativeInventoryUnavailable("inventory_pagination_invalid")
                    cursors.add(cursor)
                    params["after"] = cursor
                raise MetaNativeInventoryUnavailable("inventory_page_bound")

            campaigns, adsets = inventory(False), inventory(True)
            if any(row.campaign_id not in {c.id for c in campaigns} for row in adsets):
                raise MetaNativeInventoryUnavailable("inventory_parent_missing")
            known = all(
                row.effective_status in (ADSET_STATUSES if row.campaign_id else CAMPAIGN_STATUSES)
                and row.configured_status in {"ACTIVE", "PAUSED", "ARCHIVED", "DELETED"}
                for row in [*campaigns, *adsets]
            )
            reasons = [
                "accounting_basis_unqualified",
                "cap_epoch_unavailable",
                "pending_cap_history_unavailable",
                "historical_obligations_unproven",
                "reporting_completeness_unproven",
                "external_writer_boundary_unproven",
                "native_snapshot_not_atomic",
            ]
            if not known:
                reasons.append("native_status_unknown")
            current()
            return MetaNativeInventory(
                request=request,
                observation_started_at=now,
                observed_at=self.clock(),
                expires_at=expires,
                account_status=account["account_status"],
                amount_spent_native=_amount(account.get("amount_spent")),
                spend_cap_native=_amount(account.get("spend_cap")),
                campaigns=campaigns,
                adsets=adsets,
                advertising_inventory_read_complete=known,
                reasons=reasons,
            )
