"""Recovery after uncertain billing creates and provider idempotency expiration."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event, Lock
from typing import Any

import pytest
from app.billing.contracts import CheckoutResult, CheckoutState
from app.billing.models import WorkspaceBilling
from app.billing.service import checkout
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_billing import POLICY, FixtureBilling
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_google_customer_connections import setup


def test_concurrent_terminal_checkout_retirement_converges_on_one_purchase(
    customer_engine: Engine,
) -> None:
    if customer_engine.dialect.name != "postgresql":
        pytest.skip("row-lock interleaving requires PostgreSQL")
    resolved, replacement_returned = Event(), Event()

    class Provider(FixtureBilling):
        def __init__(self) -> None:
            super().__init__()
            self.created: dict[str, CheckoutResult] = {}
            self.lock = Lock()
            self.state = self.state.model_copy(
                update={"subscription_id": "sub_old", "status": "canceled"}
            )

        def checkout(
            self, customer_id: str, price_id: str, idempotency_key: str, return_url: str
        ) -> CheckoutResult:
            with self.lock:
                if idempotency_key not in self.created:
                    cid = "cs_new" + str(len(self.created) + 1)
                    self.created[idempotency_key] = CheckoutResult(
                        id=cid,
                        url="https://checkout.stripe.com/" + cid,
                        expires_at=NOW + timedelta(hours=1),
                    )
                return self.created[idempotency_key]

        def checkout_state(self, customer_id: str, checkout_id: str, now: object) -> CheckoutState:
            return CheckoutState(
                id=checkout_id,
                customer_id=customer_id,
                status="complete" if checkout_id == "cs_old" else "open",
                subscription_id="sub_old" if checkout_id == "cs_old" else None,
                observed_at=NOW,
            )

    class PausedSession(Session):
        commits = 0

        def commit(self) -> None:
            super().commit()
            self.commits += 1
            if self.commits == 2:
                resolved.set()
                assert replacement_returned.wait(15), "replacement did not finish"

    provider = Provider()
    with Session(customer_engine) as db:
        wid, _ = setup(db, "concurrent-retirement")
        db.add(
            WorkspaceBilling(
                workspace_id=wid,
                customer_request_key="existing",
                customer_id="cus_fixture",
                subscription_id="sub_old",
                status="canceled",
                checkout_id="cs_old",
                checkout_key="old-key",
                checkout_price=POLICY.price_id,
                checkout_url="https://checkout.stripe.com/old",
                checkout_expires_at=NOW - timedelta(hours=1),
            )
        )
        db.commit()

    def first() -> dict[str, object]:
        with PausedSession(customer_engine) as db:
            return checkout(db, wid, POLICY, provider, "https://inlet.example/app/settings", NOW)

    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(first)
        try:
            assert resolved.wait(15), "first caller did not reach reconciliation commit"
            with Session(customer_engine) as db:
                second = checkout(
                    db, wid, POLICY, provider, "https://inlet.example/app/settings", NOW
                )
        finally:
            replacement_returned.set()
        original = pending.result(timeout=15)
    assert original["id"] == second["id"]
    assert len(provider.created) == 1
    with Session(customer_engine) as db:
        row = db.get(WorkspaceBilling, wid)
        assert row is not None and row.checkout_id == second["id"]
        assert row.checkout_key in provider.created


@pytest.mark.parametrize("fault", [None, "empty", "duplicate", "foreign", "cycle", "price", "live"])
def test_expired_checkout_recovery_uses_only_bounded_owned_reads(fault: str | None) -> None:
    import httpx
    from app.billing.stripe import BillingProviderError, StripeBilling
    from pydantic import SecretStr

    key = f"{int(NOW.timestamp())}_{'b' * 32}"
    seen: list[str] = []
    session = {
        "id": "cs_found",
        "livemode": False,
        "customer": "cus_fixture",
        "mode": "subscription",
        "metadata": {"inlet_checkout_request": key},
        "url": None,
        "expires_at": int((NOW + timedelta(hours=1)).timestamp()),
    }

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET", "expired key must never reach a create endpoint"
        seen.append(request.url.path)
        if request.url.path == "/v1/checkout/sessions":
            assert request.url.params["customer"] == "cus_fixture"
            assert request.url.params["limit"] == "100"
            rows = [dict(session)]
            if fault == "empty":
                rows = []
            if fault == "duplicate":
                rows.append({**session, "id": "cs_duplicate"})
            if fault == "foreign":
                rows[0]["customer"] = "cus_other"
            return httpx.Response(
                200, json={"object": "list", "has_more": fault == "cycle", "data": rows}
            )
        if request.url.path.endswith("/line_items"):
            return httpx.Response(
                200,
                json={
                    "object": "list",
                    "has_more": False,
                    "data": [
                        {
                            "quantity": 1,
                            "price": {
                                "id": "price_wrong" if fault == "price" else POLICY.price_id,
                                "livemode": fault == "live",
                            },
                        }
                    ],
                },
            )
        return httpx.Response(200, json=session)

    wire = StripeBilling(
        SecretStr("sk_test_synthetic"),
        "2025-03-31.basil",
        http_transport=httpx.MockTransport(respond),
        clock=lambda: NOW + timedelta(days=2),
    )
    if fault:
        with pytest.raises(BillingProviderError):
            wire.checkout("cus_fixture", POLICY.price_id, key, "https://inlet.example/app/settings")
    else:
        result = wire.checkout(
            "cus_fixture", POLICY.price_id, key, "https://inlet.example/app/settings"
        )
        assert result.id == "cs_found" and result.url is None
    assert len(seen) <= 3


@pytest.mark.parametrize("fault", [None, "empty", "duplicate", "owner", "metadata"])
def test_expired_customer_recovery_does_not_treat_search_absence_as_permission(
    fault: str | None,
) -> None:
    import httpx
    from app.billing.stripe import BillingProviderError, StripeBilling
    from pydantic import SecretStr

    key = f"{int(NOW.timestamp())}_{'c' * 32}"
    customer: dict[str, Any] = {
        "id": "cus_found",
        "livemode": False,
        "metadata": {"inlet_workspace_id": "42", "inlet_customer_request": key},
    }

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        if request.url.path.endswith("/search"):
            assert (
                "inlet_workspace_id" in request.url.params["query"]
                and key in request.url.params["query"]
            )
            rows = [] if fault == "empty" else [customer]
            if fault == "duplicate":
                rows.append({**customer, "id": "cus_other"})
            return httpx.Response(
                200, json={"object": "search_result", "has_more": False, "data": rows}
            )
        result = {**customer, "metadata": dict(customer["metadata"])}
        if fault == "owner":
            result["metadata"]["inlet_workspace_id"] = "43"
        if fault == "metadata":
            result["metadata"]["inlet_customer_request"] = "different"
        return httpx.Response(200, json=result)

    wire = StripeBilling(
        SecretStr("sk_test_synthetic"),
        "2025-03-31.basil",
        http_transport=httpx.MockTransport(respond),
        clock=lambda: NOW + timedelta(days=2),
    )
    if fault:
        with pytest.raises(BillingProviderError):
            wire.customer(42, key)
    else:
        assert wire.customer(42, key) == "cus_found"


def test_lost_checkout_post_then_two_day_recovery_adopts_purchase_without_second_post(
    customer_engine: Engine,
) -> None:
    from urllib.parse import parse_qs

    import httpx
    from app.billing.service import require_entitlement
    from app.billing.stripe import StripeBilling
    from fastapi import HTTPException
    from pydantic import SecretStr

    now = NOW
    post_keys: list[str] = []
    saved: dict[str, object] = {}

    def respond(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/v1/customers":
            return httpx.Response(200, json={"id": "cus_fixture", "livemode": False})
        if request.method == "POST":
            body = parse_qs(request.content.decode())
            key = request.headers["idempotency-key"]
            post_keys.append(key)
            assert body["metadata[inlet_checkout_request]"] == [key]
            saved.update(
                id="cs_created",
                customer="cus_fixture",
                livemode=False,
                mode="subscription",
                metadata={"inlet_checkout_request": key},
                status="complete",
                subscription="sub_created",
                expires_at=int((NOW + timedelta(hours=1)).timestamp()),
                url=None,
            )
            raise httpx.ReadTimeout("synthetic lost response", request=request)
        if request.url.path == "/v1/checkout/sessions":
            return httpx.Response(200, json={"object": "list", "has_more": False, "data": [saved]})
        if request.url.path.endswith("/line_items"):
            return httpx.Response(
                200,
                json={
                    "object": "list",
                    "has_more": False,
                    "data": [{"quantity": 1, "price": {"id": POLICY.price_id, "livemode": False}}],
                },
            )
        if request.url.path == "/v1/subscriptions/sub_created":
            return httpx.Response(
                200,
                json={
                    "id": "sub_created",
                    "customer": "cus_fixture",
                    "livemode": False,
                    "status": "active",
                    "cancel_at_period_end": False,
                    "items": {
                        "has_more": False,
                        "data": [
                            {
                                "quantity": 1,
                                "price": {"id": POLICY.price_id},
                                "current_period_end": int((NOW + timedelta(days=30)).timestamp()),
                            }
                        ],
                    },
                },
            )
        assert request.url.path == "/v1/checkout/sessions/cs_created"
        return httpx.Response(200, json=saved)

    wire = StripeBilling(
        SecretStr("sk_test_synthetic"),
        "2025-03-31.basil",
        http_transport=httpx.MockTransport(respond),
        clock=lambda: now,
    )
    with Session(customer_engine) as db:
        wid, _ = setup(db, "expired-recovery")
        with pytest.raises(HTTPException, match="pending"):
            checkout(db, wid, POLICY, wire, "https://inlet.example/app/settings", now)
        now = NOW + timedelta(days=2)
        with pytest.raises(HTTPException, match="complete"):
            checkout(db, wid, POLICY, wire, "https://inlet.example/app/settings", now)
        row = db.get(WorkspaceBilling, wid)
        assert row is not None and row.subscription_id == "sub_created" and row.status == "active"
        require_entitlement(db, wid, POLICY, now)
        assert len(post_keys) == 1
