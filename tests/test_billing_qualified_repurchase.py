"""Replacement subscriptions must come from the exact owned, bound checkout."""

import json
from typing import Any

import httpx
import pytest
from app.billing import offer_bindings, repository, service
from app.billing.models import BillingEvent, WorkspaceBilling
from app.billing.webhooks import receive
from fastapi import HTTPException
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.test_billing_offers import LIVE, POLICY, PROFILE, StripeOfferFixture, bound, configure
from tests.test_commerce_measurement import NOW
from tests.test_customer_billing import SECRET, signature
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_google_customer_connections import setup


@pytest.mark.parametrize("case", ["owned", "old_active", "open", "foreign", "unpaid"])
def test_qualified_repurchase_preserves_original_binding(
    customer_engine: Engine, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    configure(monkeypatch)
    fixture = StripeOfferFixture()
    original_respond = fixture.respond

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/subscriptions/sub_old":
            document = fixture.document("/v1/subscriptions/sub_fixture")
            document["id"] = "sub_old"
            document["status"] = "active" if case == "old_active" else "canceled"
            return httpx.Response(200, json=document)
        return original_respond(request)

    fixture.wire.http_transport = httpx.MockTransport(respond)
    with Session(customer_engine) as db:
        wid, _ = setup(db, "qualified-repurchase")
        row: WorkspaceBilling | None = service.owned(db, wid, NOW, scope=LIVE)
        assert row is not None
        row.customer_id, row.checkout_key = "cus_fixture", bound().checkout_key
        old = offer_bindings.install(db, row, PROFILE, NOW)
        row.subscription_offer_binding_id, row.subscription_id = old.id, "sub_old"
        row.status = "canceled"
        row.checkout_key, row.checkout_offer_binding_id = None, None
        db.commit()
        service.checkout(db, wid, POLICY, fixture.wire, "https://inlet.example/settings", NOW)
        row = repository.billing(db, wid, LIVE)
        assert row is not None
        new_binding = row.checkout_offer_binding_id
        assert new_binding is not None and new_binding != old.id
        if case == "open":
            fixture.mutations["/v1/checkout/sessions/cs_fixture"] = {
                "status": "open",
                "subscription": None,
            }
        elif case == "foreign":
            fixture.mutations["/v1/checkout/sessions/cs_fixture"] = {"customer": "cus_foreign"}
        elif case == "unpaid":
            fixture.mutations["/v1/invoices/in_fixture"] = {"amount_paid": 0}
        body: dict[str, Any] = {
            "id": "evt_new_owned",
            "livemode": True,
            "type": "customer.subscription.updated",
            "data": {"object": {"id": "sub_fixture", "customer": "cus_fixture"}},
        }
        raw = json.dumps(body).encode()
        receive(db, raw, signature(raw), SECRET, NOW, scope=LIVE)
        if case == "owned":
            assert service.reconcile(db, wid, "evt_new_owned", POLICY, fixture.wire, NOW)
            service.require_entitlement(db, wid, POLICY, NOW, scope=LIVE)
            row = repository.billing(db, wid, LIVE)
            assert row is not None and row.subscription_id == "sub_fixture"
            assert row.subscription_offer_binding_id == new_binding
            assert row.qualification is not None and row.qualification["binding_id"] == new_binding
            # A delayed old-terminal notification cannot revert the replacement.
            body["id"] = "evt_late_old"
            body["data"]["object"]["id"] = "sub_old"
            raw = json.dumps(body).encode()
            receive(db, raw, signature(raw), SECRET, NOW, scope=LIVE)
            assert service.reconcile(db, wid, "evt_late_old", POLICY, fixture.wire, NOW)
            row = repository.billing(db, wid, LIVE)
            assert row is not None and row.subscription_id == "sub_fixture"
            assert row.subscription_offer_binding_id == new_binding
        else:
            with pytest.raises(HTTPException):
                service.reconcile(db, wid, "evt_new_owned", POLICY, fixture.wire, NOW)
            db.rollback()
            row = repository.billing(db, wid, LIVE)
            assert row is not None and row.subscription_id == "sub_old"
            assert row.subscription_offer_binding_id == old.id
            with pytest.raises(HTTPException):
                service.require_entitlement(db, wid, POLICY, NOW, scope=LIVE)
            event = db.get(BillingEvent, LIVE.key("evt_new_owned"))
            assert event is not None and event.state == "pending"
        assert len(fixture.post_keys) == 1
