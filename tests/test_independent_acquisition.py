import json
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
import pytest
from app.commerce.evidence import digest
from app.commerce.independent import IndependentAcquirer
from app.commerce.independent_contracts import ScanLimits, ScanPermit, ScanRequest, ScanUnavailable
from app.commerce.ledger import DEFINITION, MEASUREMENT_SCOPES
from pydantic import SecretStr

from tests.test_independent_acquisition_contracts import request

NOW = datetime(2026, 10, 3, 12, tzinfo=UTC)


def page(nodes: list[Any], cursor: str | None = None) -> dict[str, Any]:
    return {"nodes": nodes, "pageInfo": {"hasNextPage": cursor is not None, "endCursor": cursor}}


def order(number: int = 1) -> dict[str, Any]:
    return {
        "id": f"gid://shopify/Order/{number}",
        "createdAt": "2020-01-01T00:00:00Z",
        "updatedAt": "2026-10-01T12:00:00Z",
        "test": False,
        "customer": {"id": "gid://shopify/Customer/1"},
    }


def sale(number: int = 1, **changes: Any) -> dict[str, Any]:
    return {
        "id": f"gid://shopify/ProductSale/{number}",
        "actionType": "RETURN",
        "lineType": "PRODUCT",
        "totalAmount": {"shopMoney": {"amount": "11", "currencyCode": "USD"}},
        "totalTaxAmount": {"shopMoney": {"amount": "1", "currencyCode": "USD"}},
        **changes,
    }


def agreement() -> dict[str, Any]:
    return {
        "id": "gid://shopify/RefundAgreement/1",
        "__typename": "RefundAgreement",
        "reason": "REFUND",
        "happenedAt": "2020-01-02T00:00:00Z",
        "refund": {"processedAt": "2026-10-01T12:00:00Z"},
        "sales": page([sale()]),
    }


class Fixture:
    def __init__(self) -> None:
        original = request()
        self.request = original.model_copy(
            update={
                "scope": original.scope.model_copy(
                    update={"metric_definition_digest": digest(DEFINITION)}
                )
            }
        )
        self.now = NOW
        self.active = self.privacy = True
        self.bind_digest: str | None = None
        self.scopes = sorted(MEASUREMENT_SCOPES)
        self.orders = [order()]
        self.agreement = agreement()
        self.changed = False
        self.parent = "gid://shopify/Order/1"
        self.sale_parent = self.agreement["id"]
        self.cursor: str | None = None
        self.seen: list[dict[str, Any]] = []
        self.after: Any = None
        self.status = 200
        self.errors: Any = None
        self.extra: dict[str, Any] = {}

    def authority(self, request: ScanRequest, now: datetime) -> ScanPermit:
        return ScanPermit(
            request_digest=self.bind_digest or request.request_digest,
            expires_at=NOW + timedelta(days=2),
            shop_domain="synthetic.myshopify.com",
            shop_id="gid://shopify/Shop/1",
            shop_key="a" * 64,
            token=SecretStr("synthetic-private-token"),
            identifier_key=SecretStr("k" * 32),
            active=self.active,
            privacy_resolved=self.privacy,
        )

    def handle(self, request: httpx.Request) -> httpx.Response:
        assert request.url == "https://synthetic.myshopify.com/admin/api/2026-07/graphql.json"
        assert request.headers["x-shopify-access-token"] == "synthetic-private-token"
        body = json.loads(request.content)
        self.seen.append(body)
        query, variables = body["query"], body["variables"]
        if "InletIndependentAuthority" in query:
            data = {
                "shop": {
                    "id": "gid://shopify/Shop/1",
                    "currencyCode": "USD",
                    "ianaTimezone": self.request.scope.time_zone,
                },
                "currentAppInstallation": {"accessScopes": [{"handle": s} for s in self.scopes]},
            }
        elif "InletIndependentOrders" in query:
            assert "query" not in variables  # No created/updated/processed lower bound.
            data = {"orders": page(self.orders, self.cursor)}
        elif "InletIndependentOrderCheck" in query:
            found = next(o for o in self.orders if o["id"] == variables["id"])
            data = {
                "order": {
                    **found,
                    **({"updatedAt": "2026-10-02T00:00:00Z"} if self.changed else {}),
                }
            }
        elif "InletAgreementSales" in query:
            data = {
                "order": {
                    "id": self.parent,
                    "agreements": {"nodes": [{"id": self.sale_parent, "sales": page([sale(2)])}]},
                }
            }
        else:
            assert "InletAgreements" in query
            data = {"order": {"id": self.parent, "agreements": page([self.agreement])}}
        if self.after:
            self.after(query)
        return httpx.Response(
            self.status,
            json={"data": data, **self.extra, **({"errors": self.errors} if self.errors else {})},
            headers={"Retry-After": "999999"},
        )

    def run(self, limits: ScanLimits | None = None) -> Any:
        return IndependentAcquirer(
            self.authority,
            transport=httpx.MockTransport(self.handle),
            clock=lambda: self.now,
            limits=limits,
        ).acquire(self.request)


def test_actual_http_ancient_order_refund_processing_day_only() -> None:
    fixture = Fixture()
    result = fixture.run()
    assert result.days[0].value_micros == -10_000_000
    assert result.days[0].entry_count == 1
    assert result.correction_state == "unresolved" and result.maturity == "unqualified"
    assert result.orders_enumerated == result.agreements_enumerated == result.sales_enumerated == 1
    assert "gid://" not in result.model_dump_json()
    assert "synthetic" not in result.model_dump_json()
    assert "2020" not in result.model_dump_json()
    assert len(result.completion_digest) == 64
    # A second acquisition starts at the beginning, never a cached/incremental cursor.
    fixture.seen.clear()
    fixture.run()
    assert fixture.seen[1]["variables"] == {"after": None}


def test_zero_requires_complete_history_and_current_privacy() -> None:
    fixture = Fixture()
    fixture.orders = []
    assert fixture.run().days[0].value_micros == 0
    fixture.privacy = False
    with pytest.raises(ScanUnavailable, match="privacy_unresolved"):
        fixture.run()


@pytest.mark.parametrize("scope", sorted(MEASUREMENT_SCOPES))
def test_actual_granted_scopes_required(scope: str) -> None:
    fixture = Fixture()
    fixture.scopes.remove(scope)
    with pytest.raises(ScanUnavailable, match="historical_access_required"):
        fixture.run()
    assert len(fixture.seen) == 1


@pytest.mark.parametrize(
    "change,code",
    [
        ("mutation", "source_order_changed"),
        ("parent", "source_order_parent_invalid"),
        ("sale_parent", "source_agreement_parent_invalid"),
        ("cursor", "source_order_sequence_invalid"),
        ("unsupported", "source_metric_unresolved"),
        ("currency", "source_data_invalid"),
        ("session", "authority_changed"),
        ("privacy", "privacy_unresolved"),
        ("generation", "authority_changed"),
        ("retention", "window_unavailable"),
    ],
)
def test_incomplete_acquisitions_never_publish_values(change: str, code: str) -> None:
    fixture = Fixture()
    if change == "mutation":
        fixture.changed = True
    if change == "parent":
        fixture.parent = "gid://shopify/Order/99"
    if change == "sale_parent":
        fixture.agreement["sales"] = page([sale()], "more")
        fixture.sale_parent = "gid://shopify/RefundAgreement/99"
    if change == "cursor":
        fixture.cursor = "repeated"
    if change == "unsupported":
        fixture.agreement["__typename"] = "ReturnAgreement"
    if change == "currency":
        fixture.agreement["sales"]["nodes"][0]["totalAmount"]["shopMoney"]["currencyCode"] = "EUR"

    def after(query: str) -> None:
        if "InletAgreements" not in query:
            return
        if change == "session":
            fixture.active = False
        if change == "privacy":
            fixture.privacy = False
        if change == "generation":
            fixture.bind_digest = "f" * 64
        if change == "retention":
            fixture.now = datetime(2028, 1, 1, tzinfo=UTC)

    fixture.after = after
    with pytest.raises(ScanUnavailable, match=code):
        fixture.run()


@pytest.mark.parametrize(
    "limits,code",
    [
        (ScanLimits(requests=2), "request_limit"),
        (ScanLimits(response_bytes=100), "byte_limit"),
        (ScanLimits(total_bytes=100), "byte_limit"),
    ],
)
def test_explicit_http_bounds(limits: ScanLimits, code: str) -> None:
    with pytest.raises(ScanUnavailable, match=code):
        Fixture().run(limits)


def test_nested_sales_complete_and_bounded() -> None:
    fixture = Fixture()
    fixture.agreement["sales"] = page([sale()], "more")
    result = fixture.run()
    assert result.days[0].value_micros == -20_000_000
    assert result.sales_enumerated == 2
    with pytest.raises(ScanUnavailable, match="nested_limit"):
        fixture.run(ScanLimits(nested_requests_per_order=1))


@pytest.mark.parametrize(
    "status,code",
    [
        (401, "access_unavailable"),
        (403, "access_unavailable"),
        (429, "throttled"),
        (302, "http_unavailable"),
        (500, "http_unavailable"),
    ],
)
def test_http_failures_are_sanitized(status: int, code: str) -> None:
    fixture = Fixture()
    fixture.status = status
    with pytest.raises(ScanUnavailable, match=code) as error:
        fixture.run()
    assert "synthetic" not in str(error.value)
    if status == 429:
        assert error.value.retry_after == 3600


def test_partial_graphql_data_is_rejected() -> None:
    fixture = Fixture()
    fixture.errors = [{"message": "private provider detail", "extensions": {"code": "THROTTLED"}}]
    with pytest.raises(ScanUnavailable, match="throttled") as error:
        fixture.run()
    assert "private" not in str(error.value)


def test_metric_timestamp_and_exclusions_match_existing_normalizer() -> None:
    fixture = Fixture()
    fixture.agreement["__typename"], fixture.agreement["reason"] = "OrderAgreement", "ORDER"
    fixture.agreement["sales"] = page([sale(actionType="ORDER")])
    assert fixture.run().days[0].value_micros == 0  # ancient sale, recent order update
    fixture.agreement["happenedAt"] = "2026-10-01T12:00:00Z"
    assert fixture.run().days[0].value_micros == 10_000_000
    fixture.agreement["sales"] = page([sale(lineType="SHIPPING")])
    assert fixture.run().days[0].entry_count == 0


def test_dst_local_day_uses_refund_processing_timestamp() -> None:
    fixture = Fixture()
    fixture.now = datetime(2026, 3, 10, tzinfo=UTC)
    fixture.request = fixture.request.model_copy(
        update={"start": date(2026, 3, 8), "end": date(2026, 3, 9)}
    )
    fixture.orders[0]["updatedAt"] = "2026-03-09T06:00:00Z"
    fixture.agreement["refund"]["processedAt"] = "2026-03-09T03:30:00Z"
    assert fixture.run().days[0].value_micros == -10_000_000
    fixture.agreement["refund"]["processedAt"] = "2026-03-09T04:00:00Z"
    assert fixture.run().days[0].value_micros == 0


def test_order_limit_and_actual_continuation_are_distinct() -> None:
    fixture = Fixture()
    fixture.orders = [order(1), order(2)]
    with pytest.raises(ScanUnavailable, match="order_limit"):
        fixture.run(ScanLimits(orders=1))


def test_complete_multiple_order_pages_retain_no_old_source_ids() -> None:
    fixture = Fixture()
    original = fixture.handle

    def transport(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if "InletIndependentOrders" in body["query"]:
            if body["variables"]["after"] is None:
                fixture.orders, fixture.cursor = [order(1)], "page2"
            else:
                assert body["variables"]["after"] == "page2"
                fixture.orders, fixture.cursor = [order(2)], None
                fixture.parent = "gid://shopify/Order/2"
                fixture.agreement["id"] = "gid://shopify/RefundAgreement/2"
                fixture.agreement["sales"] = page([sale(2)])
        return original(request)

    result = IndependentAcquirer(
        fixture.authority,
        transport=httpx.MockTransport(transport),
        clock=lambda: NOW,
    ).acquire(fixture.request)
    assert result.orders_enumerated == 2
    assert result.days[0].value_micros == -20_000_000
    assert "Order/" not in result.model_dump_json()


@pytest.mark.parametrize("change", ["shop", "scope_end", "clock", "deadline", "no_customer"])
def test_late_proof_and_identity_failures(change: str) -> None:
    fixture = Fixture()
    real = fixture.handle
    ticks = [0.0]

    def transport(request: httpx.Request) -> httpx.Response:
        response = real(request)
        query = json.loads(request.content)["query"]
        if change == "shop" and "Authority" in query:
            data = response.json()
            data["data"]["shop"]["id"] = "gid://shopify/Shop/99"
            return httpx.Response(200, json=data)
        if "OrderCheck" in query:
            if change == "scope_end":
                fixture.scopes = []
            if change == "clock":
                fixture.now = NOW - timedelta(seconds=1)
            if change == "deadline":
                ticks[0] = 1801
            if change == "no_customer":
                data = response.json()
                del data["data"]["order"]["customer"]
                return httpx.Response(200, json=data)
        return response

    with pytest.raises(ScanUnavailable):
        IndependentAcquirer(
            fixture.authority,
            transport=httpx.MockTransport(transport),
            clock=lambda: fixture.now,
            monotonic_clock=lambda: ticks[0],
        ).acquire(fixture.request)


def test_untrusted_error_body_never_logged(caplog: pytest.LogCaptureFixture) -> None:
    import logging

    fixture = Fixture()
    fixture.errors = [{"message": "synthetic-sensitive-provider-message"}]
    with caplog.at_level(logging.DEBUG), pytest.raises(ScanUnavailable):
        fixture.run()
    assert "synthetic-sensitive-provider-message" not in caplog.text
    assert "synthetic-private-token" not in caplog.text
    assert "synthetic.myshopify.com" not in caplog.text
