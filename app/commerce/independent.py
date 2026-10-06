"""Fresh bounded Shopify acquisition. No factory, scheduler, persistence or maturity.

The injected authority must resolve the original caller and every scope/privacy
fence from current server state on each invocation; a cached permit is not an
acceptable production adapter. Only aggregate in-window observations leave here.
"""

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from app.commerce import queries
from app.commerce.evidence import digest
from app.commerce.independent_contracts import (
    ScanAuthority,
    ScanCompletion,
    ScanLimits,
    ScanPermit,
    ScanRequest,
    ScanUnavailable,
)
from app.commerce.ledger import DEFINITION, MEASUREMENT_SCOPES, normalized_entries, retention_floor
from app.commerce.models import CommerceStore
from app.commerce.source import connection_page, gid
from app.executors.social_http import _private_http
from app.outcomes.contracts import Window
from app.outcomes.maturity import ReconciledDay
from app.shopify.security import API_VERSION, ShopifyError, Vault, shop_domain

AUTHORITY = """
query InletIndependentAuthority {
 shop { id currencyCode ianaTimezone }
 currentAppInstallation { accessScopes { handle } }
}
"""
ORDERS = """
query InletIndependentOrders($after: String) {
 orders(first: 50, after: $after, sortKey: ID) {
  pageInfo { hasNextPage endCursor }
  nodes { id createdAt updatedAt test customer { id } }
 }
}
"""
AGREEMENTS = queries.AGREEMENTS.replace(
    "order(id: $id) { agreements", "order(id: $id) { id agreements"
)
SALES = queries.SALES.replace("order(id: $order) { agreements", "order(id: $order) { id agreements")
ORDER_CHECK = """
query InletIndependentOrderCheck($id: ID!) {
 order(id: $id) { id createdAt updatedAt test customer { id } }
}
"""


class _HashOnlyVault(Vault):
    """Only inherited normalization's identity digest is supported."""

    def __init__(self, key: str) -> None:
        self._hash_key = key.encode()


def _identity(value: Any, kind: str) -> str:
    result = gid(value)
    if not result.startswith(f"gid://shopify/{kind}/"):
        raise ScanUnavailable("source_identity_invalid")
    return result


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ScanUnavailable("source_time_invalid")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None:
            raise ValueError()
        return result.astimezone(UTC)
    except ValueError:
        raise ScanUnavailable("source_time_invalid") from None


class IndependentAcquirer:
    def __init__(
        self,
        authority: ScanAuthority,
        *,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        monotonic_clock: Callable[[], float] = monotonic,
        limits: ScanLimits | None = None,
    ) -> None:
        self.authority, self.transport, self.clock = authority, transport, clock
        self.monotonic, self.limits = monotonic_clock, limits or ScanLimits()

    def acquire(self, request: ScanRequest) -> ScanCompletion:
        # State belongs to one invocation; a shared adapter never reuses its cursor.
        request = ScanRequest.model_validate(request.model_dump())
        state = _Scan(self, request)
        try:
            return state.acquire()
        except (KeyError, TypeError, ValueError, ShopifyError, OverflowError, AttributeError):
            raise ScanUnavailable("source_data_invalid") from None


class _Scan:
    def __init__(self, adapter: IndependentAcquirer, request: ScanRequest) -> None:
        self.adapter, self.request, self.limits = adapter, request, adapter.limits
        self.started = adapter.clock()
        self.deadline = adapter.monotonic() + self.limits.lifetime_seconds
        self.calls = self.bytes = self.orders = self.agreements = self.sales = 0
        self.binding: tuple[str, ...] | None = None
        self.window = Window.local(request.start, request.end, request.scope.time_zone)
        self.seen_sales: set[str] = set()
        self.seen_agreements: set[str] = set()
        self.totals: dict[Any, list[int]] = {}
        self.client: httpx.Client

    def permit(self) -> ScanPermit:
        now = self.adapter.clock()
        if now.tzinfo is None or now < self.started:
            raise ScanUnavailable("acquisition_clock_invalid")
        if self.adapter.monotonic() >= self.deadline:
            raise ScanUnavailable("acquisition_deadline_exceeded")
        if (
            self.window.start_utc < retention_floor(now, self.request.scope.time_zone)
            or self.window.end_utc > now
        ):
            raise ScanUnavailable("acquisition_window_unavailable")
        permit = self.adapter.authority(self.request, now)
        if (
            permit.request_digest != self.request.request_digest
            or not permit.active
            or permit.expires_at <= now
        ):
            raise ScanUnavailable("acquisition_authority_changed")
        if not permit.privacy_resolved:
            raise ScanUnavailable("acquisition_privacy_unresolved")
        domain = shop_domain(permit.shop_domain)
        if domain != permit.shop_domain or len(permit.identifier_key.get_secret_value()) < 32:
            raise ScanUnavailable("acquisition_source_invalid")
        key = permit.identifier_key.get_secret_value()
        binding = (
            domain,
            permit.shop_id,
            permit.shop_key,
            hashlib.sha256(key.encode()).hexdigest(),
        )
        if self.binding is not None and self.binding != binding:
            raise ScanUnavailable("acquisition_source_changed")
        self.binding = binding
        return permit

    def query(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        permit = self.permit()
        if self.calls >= self.limits.requests:
            raise ScanUnavailable("acquisition_request_limit")
        self.calls += 1
        remaining = self.deadline - self.adapter.monotonic()
        private = _private_http.set(True)
        try:
            with self.client.stream(
                "POST",
                f"https://{permit.shop_domain}/admin/api/{API_VERSION}/graphql.json",
                json={"query": query, "variables": variables},
                headers={"X-Shopify-Access-Token": permit.token.get_secret_value()},
                timeout=min(15, remaining),
            ) as response:
                if response.status_code == 429:
                    delay = response.headers.get("retry-after", "60")
                    raise ScanUnavailable(
                        "acquisition_throttled",
                        retry_after=int(delay) if delay.isdigit() and len(delay) < 8 else 60,
                    )
                if response.status_code in {401, 403}:
                    raise ScanUnavailable("acquisition_access_unavailable")
                if response.status_code != 200:
                    raise ScanUnavailable("acquisition_http_unavailable")
                if response.headers.get("content-encoding", "identity") != "identity":
                    raise ScanUnavailable("acquisition_encoding_unavailable")
                raw = bytearray()
                for chunk in response.iter_bytes(chunk_size=65536):
                    self.permit()
                    self.bytes += len(chunk)
                    if (
                        len(raw) + len(chunk) > self.limits.response_bytes
                        or self.bytes > self.limits.total_bytes
                    ):
                        raise ScanUnavailable("acquisition_byte_limit")
                    raw.extend(chunk)
                data = json.loads(raw)
        except (httpx.HTTPError, OSError):
            raise ScanUnavailable("acquisition_transport_unavailable") from None
        finally:
            _private_http.reset(private)
        self.permit()  # Reauthorize original caller and privacy after blocking I/O.
        if not isinstance(data, dict):
            raise ScanUnavailable("source_data_invalid")
        if data.get("errors"):
            errors = data["errors"]
            if isinstance(errors, list) and any(
                isinstance(e, dict) and (e.get("extensions") or {}).get("code") == "THROTTLED"
                for e in errors
            ):
                raise ScanUnavailable("acquisition_throttled", retry_after=60)
            raise ScanUnavailable("acquisition_graphql_unavailable")
        result = data.get("data")
        if not isinstance(result, dict):
            raise ScanUnavailable("source_data_invalid")
        return result

    def proof(self) -> None:
        data = self.query(AUTHORITY, {})
        permit = self.permit()
        shop = data["shop"]
        if (shop["id"], shop["currencyCode"], shop["ianaTimezone"]) != (
            permit.shop_id,
            self.request.scope.currency,
            self.request.scope.time_zone,
        ):
            raise ScanUnavailable("acquisition_shop_mismatch")
        scopes = data["currentAppInstallation"]["accessScopes"]
        if not isinstance(scopes, list) or len(scopes) > 250:
            raise ScanUnavailable("acquisition_scope_invalid")
        handles = {scope["handle"] for scope in scopes}
        if not handles >= MEASUREMENT_SCOPES:
            raise ScanUnavailable("acquisition_historical_access_required")

    def order_binding(self, source: dict[str, Any]) -> tuple[Any, ...]:
        order_id = _identity(source["id"], "Order")
        if type(source["test"]) is not bool:
            raise ScanUnavailable("source_test_flag_invalid")
        created, updated = _timestamp(source["createdAt"]), _timestamp(source["updatedAt"])
        if created > updated or updated > self.adapter.clock():
            raise ScanUnavailable("source_time_invalid")
        customer = source["customer"]
        customer_id = _identity(customer["id"], "Customer") if customer is not None else None
        return order_id, created, updated, source["test"], customer_id

    def read_order(self, source: dict[str, Any]) -> None:
        before = self.order_binding(source)
        order_id = before[0]
        begin = self.calls
        cursor = None
        cursors: set[str] = set()
        agreements = []
        while True:
            if self.calls - begin >= self.limits.nested_requests_per_order:
                raise ScanUnavailable("acquisition_nested_limit")
            result = self.query(AGREEMENTS, {"id": order_id, "after": cursor})
            if (result.get("order") or {}).get("id") != order_id:
                raise ScanUnavailable("source_order_parent_invalid")
            nodes, after = connection_page((result.get("order") or {}).get("agreements"))
            # Existing query requests one agreement; reject extra ambiguous parents.
            if len(nodes) > 1:
                raise ScanUnavailable("source_agreement_parent_invalid")
            for item in nodes:
                agreement_id = gid(item["id"])
                if agreement_id in self.seen_agreements:
                    raise ScanUnavailable("source_duplicate_agreement")
                self.seen_agreements.add(agreement_id)
                self.agreements += 1
                sales, sale_cursor = connection_page(item["sales"])
                sale_cursors: set[str] = set()
                while sale_cursor:
                    if (
                        self.calls - begin >= self.limits.nested_requests_per_order
                        or sale_cursor in sale_cursors
                    ):
                        raise ScanUnavailable("acquisition_nested_limit")
                    sale_cursors.add(sale_cursor)
                    more = self.query(
                        SALES,
                        {
                            "order": order_id,
                            "agreementBefore": cursor,
                            "after": sale_cursor,
                        },
                    )
                    if (more.get("order") or {}).get("id") != order_id:
                        raise ScanUnavailable("source_order_parent_invalid")
                    matches = (more.get("order") or {}).get("agreements", {}).get("nodes", [])
                    if len(matches) != 1 or matches[0].get("id") != agreement_id:
                        raise ScanUnavailable("source_agreement_parent_invalid")
                    extra, sale_cursor = connection_page(matches[0].get("sales"))
                    sales.extend(extra)
                for sale in sales:
                    sale_id = gid(sale["id"])
                    if sale_id in self.seen_sales:
                        raise ScanUnavailable("source_duplicate_sale")
                    self.seen_sales.add(sale_id)
                self.sales += len(sales)
                agreements.append({**item, "sales": sales})
            if after is None:
                break
            if after in cursors:
                raise ScanUnavailable("source_cursor_repeated")
            cursors.add(after)
            cursor = after
        check = self.query(ORDER_CHECK, {"id": order_id}).get("order")
        if not isinstance(check, dict) or self.order_binding(check) != before:
            raise ScanUnavailable("source_order_changed")
        if before[3]:  # Test orders excluded only after supported, complete traversal.
            return
        permit = self.permit()
        store = CommerceStore(
            id=self.request.scope.store_id,
            workspace_id=self.request.scope.workspace_id,
            shop_key=permit.shop_key,
            currency=self.request.scope.currency,
        )
        entries, quality = normalized_entries(
            agreements, store, _HashOnlyVault(permit.identifier_key.get_secret_value())
        )
        if quality != "complete":
            raise ScanUnavailable("source_metric_unresolved")
        zone = ZoneInfo(self.request.scope.time_zone)
        for entry in entries.values():
            day = entry["happened_at"].astimezone(zone).date()
            if self.request.start <= day < self.request.end:
                totals = self.totals.setdefault(day, [0, 0])
                totals[0] += entry["net_micros"]
                totals[1] += 1

    def acquire(self) -> ScanCompletion:
        if self.request.scope.metric_definition_digest != digest(DEFINITION):
            raise ScanUnavailable("acquisition_metric_mismatch")
        self.permit()
        with httpx.Client(
            transport=self.adapter.transport,
            trust_env=False,
            follow_redirects=False,
            headers={"Accept": "application/json", "Accept-Encoding": "identity"},
        ) as self.client:
            self.proof()
            cursor = None
            cursors: set[str] = set()
            previous = 0
            while True:
                nodes, after = connection_page(self.query(ORDERS, {"after": cursor}).get("orders"))
                for source in nodes:
                    number = int(_identity(source["id"], "Order").rsplit("/", 1)[1])
                    if number <= previous:
                        raise ScanUnavailable("source_order_sequence_invalid")
                    previous = number
                    self.orders += 1
                    if self.orders > self.limits.orders:
                        raise ScanUnavailable("acquisition_order_limit")
                    self.read_order(source)
                if after is None:
                    break
                if not nodes or after in cursors:
                    raise ScanUnavailable("source_cursor_repeated")
                cursors.add(after)
                cursor = after
            self.proof()  # The same token must still prove shop, basis and granted history.
        self.permit()
        days = []
        for offset in range((self.request.end - self.request.start).days):
            day = self.request.start + timedelta(days=offset)
            amount, count = self.totals.get(day, [0, 0])
            days.append(
                ReconciledDay(
                    day=day,
                    state="complete",
                    value_micros=amount,
                    entry_count=count,
                )
            )
        return ScanCompletion(
            request=self.request,
            started_at=self.started,
            completed_at=self.adapter.clock(),
            orders_enumerated=self.orders,
            agreements_enumerated=self.agreements,
            sales_enumerated=self.sales,
            requests_completed=self.calls,
            response_bytes=self.bytes,
            days=tuple(days),
        )
