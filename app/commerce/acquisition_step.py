"""One bounded provider read, reduced to private checkpoint data. No database IO."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from time import monotonic
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from app.commerce.acquisition_contracts import (
    AcquisitionProfile,
    Checkpoint,
    DayTotal,
    NativeHandles,
    PendingAgreement,
    PendingOrder,
)
from app.commerce.independent import (
    AGREEMENTS,
    ORDER_CHECK,
    ORDERS,
    SALES,
    IndependentAcquirer,
    _HashOnlyVault,
    _identity,
    _Scan,
    _timestamp,
)
from app.commerce.independent_contracts import ScanAuthority, ScanRequest, ScanUnavailable
from app.commerce.ledger import normalized_entries
from app.commerce.models import CommerceStore
from app.commerce.source import connection_page, gid
from app.shopify.security import ShopifyError


@dataclass(frozen=True)
class StepResult:
    checkpoint: Checkpoint
    handles: NativeHandles
    seen: tuple[tuple[str, str], ...]
    response_bytes: int


class _Reducer:
    def __init__(
        self, request: ScanRequest, checkpoint: Checkpoint, handles: NativeHandles, scan: _Scan
    ) -> None:
        self.request, self.scan = request, scan
        self.state = checkpoint.model_dump()
        self.handles = handles.model_dump()
        self.seen: list[tuple[str, str]] = []
        permit = scan.permit()
        self.vault = _HashOnlyVault(permit.identifier_key.get_secret_value())
        self.store = CommerceStore(
            id=request.scope.store_id,
            workspace_id=request.scope.workspace_id,
            shop_key=permit.shop_key,
            currency=request.scope.currency,
        )

        nested = checkpoint.phase in {"agreement_page", "sale_page", "order_check"}
        if bool(checkpoint.pending_orders) != nested:
            raise ScanUnavailable("acquisition_checkpoint_invalid")
        for pending, identifier in zip(checkpoint.pending_orders, handles.order_ids, strict=True):
            if pending.identity_digest != self.key("order", identifier):
                raise ScanUnavailable("acquisition_checkpoint_invalid")
        if checkpoint.phase == "sale_page":
            if (
                checkpoint.agreement is None
                or handles.agreement_id is None
                or handles.sale_cursor is None
                or checkpoint.agreement.identity_digest
                != self.key("agreement", handles.agreement_id)
            ):
                raise ScanUnavailable("acquisition_checkpoint_invalid")
        elif checkpoint.agreement is not None or handles.agreement_id is not None:
            raise ScanUnavailable("acquisition_checkpoint_invalid")

    def key(self, kind: str, value: str) -> str:
        return self.vault.digest(
            f"acquisition:{self.request.scope.workspace_id}:{self.request.scope.store_id}:"
            f"{self.request.acquisition_id}:{kind}",
            value,
        )

    def mark(self, kind: str, value: str) -> None:
        pair = (kind, self.key(kind, value))
        if pair in self.seen:
            raise ScanUnavailable("source_duplicate_identity")
        self.seen.append(pair)

    def cursor(self, kind: str, parent: str, value: str | None) -> None:
        if value is not None:
            self.mark("cursor", f"{kind}\0{parent}\0{value}")

    def order(self, value: dict[str, Any]) -> PendingOrder:
        order, created, updated, test, customer = self.scan.order_binding(value)
        return PendingOrder(
            identity_digest=self.key("order", order),
            created_at=created,
            updated_at=updated,
            test=test,
            customer_digest=self.key("customer", customer) if customer else None,
        )

    def order_page(self, data: dict[str, Any]) -> None:
        nodes, after = connection_page(data.get("orders"))
        if after is not None and not nodes:
            raise ScanUnavailable("source_cursor_repeated")
        previous = int(self.handles["last_order_number"])
        orders, ids = [], []
        for node in nodes:
            identifier = _identity(node["id"], "Order")
            number = int(identifier.rsplit("/", 1)[1])
            if number <= previous:
                raise ScanUnavailable("source_order_sequence_invalid")
            previous = number
            self.mark("order", identifier)
            orders.append(self.order(node).model_dump())
            ids.append(identifier)
        count = self.state["orders_enumerated"] + len(nodes)
        if count > self.scan.limits.orders:
            raise ScanUnavailable("acquisition_order_limit")
        self.cursor("orders", "", after)
        self.state.update(
            pending_orders=orders,
            orders_enumerated=count,
            orders_more=after is not None,
            phase="agreement_page" if nodes else "authority_after",
        )
        self.handles.update(order_ids=ids, order_cursor=after, last_order_number=str(previous))

    def parent(self, data: dict[str, Any]) -> dict[str, Any]:
        parent = data.get("order")
        if not isinstance(parent, dict) or parent.get("id") != self.handles["order_ids"][0]:
            raise ScanUnavailable("source_order_parent_invalid")
        return parent

    def add_sales(self, sales: list[dict[str, Any]]) -> None:
        current = PendingAgreement.model_validate(self.state["agreement"])
        for sale in sales:
            self.mark("sale", gid(sale["id"]))
        raw = {
            "__typename": current.kind,
            "reason": current.reason,
            "happenedAt": current.happened_at.isoformat(),
            "refund": {"processedAt": current.happened_at.isoformat()},
            "sales": sales,
        }
        entries, quality = normalized_entries([raw], self.store, self.vault)
        if quality != "complete":
            raise ScanUnavailable("source_metric_unresolved")
        totals = {v["day"]: [v["value_micros"], v["entry_count"]] for v in self.state["tentative"]}
        for entry in entries.values():
            day = entry["happened_at"].astimezone(ZoneInfo(self.request.scope.time_zone)).date()
            if entry["happened_at"] > self.scan.adapter.clock():
                raise ScanUnavailable("source_time_invalid")
            if self.request.start <= day < self.request.end:
                total = totals.setdefault(day, [0, 0])
                total[0] += entry["net_micros"]
                total[1] += 1
        self.state["tentative"] = [
            DayTotal(day=d, value_micros=v[0], entry_count=v[1]).model_dump()
            for d, v in sorted(totals.items())
        ]
        self.state["sales_enumerated"] += len(sales)

    def advance_agreement(self) -> None:
        self.state["phase"] = "agreement_page" if self.state["agreements_more"] else "order_check"
        self.state["agreement"] = None
        self.handles.update(
            agreement_cursor=self.handles["agreement_next_cursor"],
            agreement_next_cursor=None,
            agreement_id=None,
            sale_cursor=None,
        )

    def agreement_page(self, data: dict[str, Any]) -> None:
        nodes, after = connection_page(self.parent(data).get("agreements"))
        if len(nodes) > 1 or (not nodes and after is not None):
            raise ScanUnavailable("source_agreement_parent_invalid")
        self.state["order_nested_requests"] += 1
        self.state["agreements_more"] = after is not None
        self.cursor("agreements", self.handles["order_ids"][0], after)
        self.handles["agreement_next_cursor"] = after
        if not nodes:
            self.state["phase"] = "order_check"
            return
        item = nodes[0]
        identifier = gid(item["id"])
        self.mark("agreement", identifier)
        happened = (
            (item.get("refund") or {}).get("processedAt")
            if item["__typename"] == "RefundAgreement"
            else item["happenedAt"]
        )
        agreement = PendingAgreement.model_validate(
            {
                "identity_digest": self.key("agreement", identifier),
                "kind": item["__typename"],
                "reason": item["reason"],
                "happened_at": _timestamp(happened),
            }
        )
        self.state.update(
            agreement=agreement.model_dump(),
            order_has_agreement=True,
            agreements_enumerated=self.state["agreements_enumerated"] + 1,
        )
        self.handles["agreement_id"] = identifier
        sales, cursor = connection_page(item["sales"])
        self.add_sales(sales)
        self.cursor("sales", identifier, cursor)
        self.handles["sale_cursor"] = cursor
        self.state["sales_more"] = cursor is not None
        if cursor is not None:
            self.state["phase"] = "sale_page"
        else:
            self.advance_agreement()

    def sale_page(self, data: dict[str, Any]) -> None:
        matches = self.parent(data).get("agreements", {}).get("nodes", [])
        if len(matches) != 1 or matches[0].get("id") != self.handles["agreement_id"]:
            raise ScanUnavailable("source_agreement_parent_invalid")
        sales, cursor = connection_page(matches[0].get("sales"))
        if not sales and cursor is not None:
            raise ScanUnavailable("source_cursor_repeated")
        self.state["order_nested_requests"] += 1
        self.add_sales(sales)
        self.cursor("sales", self.handles["agreement_id"], cursor)
        self.handles["sale_cursor"] = cursor
        self.state["sales_more"] = cursor is not None
        if cursor is None:
            self.advance_agreement()

    def order_check(self, data: dict[str, Any]) -> None:
        original = PendingOrder.model_validate(self.state["pending_orders"][0])
        if self.order(self.parent(data)) != original:
            raise ScanUnavailable("source_order_changed")
        if not original.test:
            if not self.state["order_has_agreement"]:
                raise ScanUnavailable("source_metric_unresolved")
            totals = {
                v["day"]: [v["value_micros"], v["entry_count"]] for v in self.state["committed"]
            }
            for row in self.state["tentative"]:
                total = totals.setdefault(row["day"], [0, 0])
                total[0] += row["value_micros"]
                total[1] += row["entry_count"]
            self.state["committed"] = [
                DayTotal(day=d, value_micros=v[0], entry_count=v[1]).model_dump()
                for d, v in sorted(totals.items())
            ]
        self.state.update(
            pending_orders=self.state["pending_orders"][1:],
            tentative=(),
            order_has_agreement=False,
            order_nested_requests=0,
            agreements_more=False,
            sales_more=False,
            agreement=None,
        )
        self.handles.update(
            order_ids=self.handles["order_ids"][1:],
            agreement_cursor=None,
            agreement_next_cursor=None,
            agreement_id=None,
            sale_cursor=None,
        )
        self.state["phase"] = (
            "agreement_page"
            if self.state["pending_orders"]
            else "order_page"
            if self.state["orders_more"]
            else "authority_after"
        )


def _execute_step(
    request: ScanRequest,
    checkpoint: Checkpoint,
    handles: NativeHandles,
    authority: ScanAuthority,
    profile: AcquisitionProfile,
    *,
    transport: httpx.BaseTransport,
    client: httpx.Client,
    clock: Callable[[], datetime],
    started_at: datetime,
    deadline_at: datetime,
    monotonic_clock: Callable[[], float] = monotonic,
) -> StepResult:
    """Exactly one GraphQL read. Caller owns all lease and persistent-state fencing."""
    request = ScanRequest.model_validate_json(request.model_dump_json())
    checkpoint = Checkpoint.model_validate_json(checkpoint.model_dump_json())
    handles = NativeHandles.model_validate_json(handles.model_dump_json())
    if (
        checkpoint.request_digest != request.request_digest
        or checkpoint.profile_digest != profile.digest()
    ):
        raise ScanUnavailable("acquisition_checkpoint_invalid")
    if checkpoint.phase == "publish":
        raise ScanUnavailable("acquisition_phase_invalid")
    if (
        checkpoint.phase in {"agreement_page", "sale_page"}
        and checkpoint.order_nested_requests >= profile.limits.nested_requests_per_order
    ):
        raise ScanUnavailable("acquisition_nested_limit")
    if len(handles.order_ids) != len(checkpoint.pending_orders):
        raise ScanUnavailable("acquisition_checkpoint_invalid")
    remaining = min((deadline_at - clock()).total_seconds(), profile.step_io_timeout_seconds)
    if remaining <= 0:
        raise ScanUnavailable("acquisition_expired")
    adapter = IndependentAcquirer(
        authority,
        transport=transport,
        clock=clock,
        monotonic_clock=monotonic_clock,
        limits=profile.limits,
    )
    scan = _Scan(adapter, request)
    scan.started = started_at
    scan.deadline = monotonic_clock() + remaining
    try:
        reducer = _Reducer(request, checkpoint, handles, scan)
        scan.client = client
        if checkpoint.phase in {"authority_before", "authority_after"}:
            scan.proof()
            reducer.state["phase"] = (
                "order_page" if checkpoint.phase == "authority_before" else "publish"
            )
        else:
            identifier = handles.order_ids[0] if handles.order_ids else None
            if checkpoint.phase == "order_page":
                reducer.order_page(scan.query(ORDERS, {"after": handles.order_cursor}))
            elif checkpoint.phase == "agreement_page":
                reducer.agreement_page(
                    scan.query(AGREEMENTS, {"id": identifier, "after": handles.agreement_cursor})
                )
            elif checkpoint.phase == "sale_page":
                reducer.sale_page(
                    scan.query(
                        SALES,
                        {
                            "order": identifier,
                            "agreementBefore": handles.agreement_cursor,
                            "after": handles.sale_cursor,
                        },
                    )
                )
            else:
                reducer.order_check(scan.query(ORDER_CHECK, {"id": identifier}))
        scan.permit()
        reducer.state["sequence"] += 1
        return StepResult(
            Checkpoint.model_validate(reducer.state),
            NativeHandles.model_validate(reducer.handles),
            tuple(reducer.seen),
            scan.bytes,
        )
    except (
        KeyError,
        TypeError,
        ValueError,
        ShopifyError,
        OverflowError,
        IndexError,
        AttributeError,
    ):
        raise ScanUnavailable("source_data_invalid") from None


def execute_step(
    request: ScanRequest,
    checkpoint: Checkpoint,
    handles: NativeHandles,
    authority: ScanAuthority,
    profile: AcquisitionProfile,
    *,
    transport: httpx.BaseTransport,
    clock: Callable[[], datetime],
    started_at: datetime,
    deadline_at: datetime,
    monotonic_clock: Callable[[], float] = monotonic,
) -> StepResult:
    """Own the supplied transport, including failed local validation before any IO."""
    with httpx.Client(
        transport=transport,
        trust_env=False,
        follow_redirects=False,
        headers={"Accept": "application/json", "Accept-Encoding": "identity"},
    ) as client:
        return _execute_step(
            request,
            checkpoint,
            handles,
            authority,
            profile,
            transport=transport,
            client=client,
            clock=clock,
            started_at=started_at,
            deadline_at=deadline_at,
            monotonic_clock=monotonic_clock,
        )
