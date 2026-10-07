"""Pinned Stripe profile qualification uses only deterministic HTTP fixtures."""

from copy import deepcopy
from datetime import timedelta
from typing import Any
from urllib.parse import parse_qs

import httpx
import pytest
from app.billing import repository
from app.billing.contracts import BillingPolicy
from app.billing.dispatcher import run
from app.billing.models import BillingOfferBinding
from app.billing.offers import BoundOfferV1, OfferProfileV1, digest
from app.billing.scope import BillingScopeV1
from app.billing.service import checkout, management, owned, require_entitlement
from app.billing.stripe import BillingProviderError, StripeBilling
from app.billing.webhooks import receive
from app.settings import settings
from fastapi import HTTPException
from pydantic import SecretStr, ValidationError
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_billing import SECRET, signature
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_google_customer_connections import setup

LIVE = BillingScopeV1(environment="live", merchant_account_id="acct_fixture")
TEST = BillingScopeV1(environment="test", merchant_account_id="acct_fixture")
PROFILE = OfferProfileV1(
    scope=LIVE,
    api_version="2025-06-30.basil",
    price_id="price_fixture",
    product_id="prod_fixture",
    currency="usd",
    unit_amount=1000,
    interval="month",
    interval_count=1,
    quantity=1,
    billing_scheme="per_unit",
    usage_type="licensed",
    tax_policy="disabled_no_rates",
    price_tax_behavior="exclusive",
    trial_policy="none",
    discount_policy="none",
    promotion_codes=False,
    credit_policy="none",
    entitlement_payment_policy="paid_latest_invoice",
    portal={
        "configuration_id": "bpc_fixture",
        "cancellation_mode": "at_period_end",
        "cancellation_proration": "none",
        "subscription_update": False,
        "customer_update": False,
        "payment_method_update": True,
        "invoice_history": True,
    },
    max_advertising_accounts=3,
    operator_review_reference="offline-release-fixture",
)
POLICY = BillingPolicy(price_id=PROFILE.price_id, max_accounts=3)


class StripeOfferFixture:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.post_keys: list[str] = []
        self.binding_digest = "a" * 64
        self.checkout_key = ""
        self.lost = False
        self.status = "active"
        self.mutations: dict[str, dict[str, Any]] = {}
        self.clock = NOW
        self.wire = StripeBilling(
            SecretStr("sk_live_offline_fixture"),
            PROFILE.api_version,
            scope=LIVE,
            http_transport=httpx.MockTransport(self.respond),
            clock=lambda: self.clock,
        )

    def price(self) -> dict[str, Any]:
        return {
            "id": PROFILE.price_id,
            "object": "price",
            "active": True,
            "livemode": True,
            "product": PROFILE.product_id,
            "currency": "usd",
            "type": "recurring",
            "billing_scheme": "per_unit",
            "unit_amount": 1000,
            "unit_amount_decimal": "1000",
            "tax_behavior": "exclusive",
            "recurring": {
                "interval": "month",
                "interval_count": 1,
                "usage_type": "licensed",
                "trial_period_days": None,
            },
            "custom_unit_amount": None,
            "tiers_mode": None,
            "transform_quantity": None,
        }

    def document(self, path: str) -> dict[str, Any]:
        start, end = int(NOW.timestamp()), int((NOW + timedelta(days=31)).timestamp())
        checkout_item = {
            "quantity": 1,
            "price": self.price(),
            "currency": "usd",
            "amount_subtotal": 1000,
            "amount_total": 1000,
            "amount_discount": 0,
            "amount_tax": 0,
        }
        session = {
            "id": "cs_fixture",
            "object": "checkout.session",
            "customer": "cus_fixture",
            "mode": "subscription",
            "livemode": True,
            "currency": "usd",
            "amount_subtotal": 1000,
            "amount_total": 1000,
            "allow_promotion_codes": False,
            "automatic_tax": {"enabled": False},
            "metadata": {
                "inlet_offer_binding": self.binding_digest,
                "inlet_checkout_request": self.checkout_key,
            },
            "total_details": {"amount_discount": 0, "amount_tax": 0, "amount_shipping": 0},
            "status": "complete",
            "subscription": "sub_fixture",
            "url": "https://checkout.stripe.com/c/fixture",
            "expires_at": int((NOW + timedelta(hours=1)).timestamp()),
        }
        payment = {
            "id": "inpay_fixture",
            "object": "invoice_payment",
            "invoice": "in_fixture",
            "status": "paid",
            "currency": "usd",
            "amount_paid": 1000,
            "amount_requested": 1000,
            "payment": {"type": "payment_intent", "payment_intent": "pi_fixture"},
            "livemode": True,
        }
        line = {
            "object": "line_item",
            "livemode": True,
            "parent": {
                "type": "subscription_item_details",
                "subscription_item_details": {
                    "subscription_item": "si_fixture",
                    "subscription": "sub_fixture",
                    "proration": False,
                },
            },
            "pricing": {
                "price_details": {"price": PROFILE.price_id, "product": PROFILE.product_id}
            },
            "currency": "usd",
            "quantity": 1,
            "amount": 1000,
            "period": {"start": start, "end": end},
            "discounts": [],
            "discount_amounts": [],
            "taxes": [],
            "pretax_credit_amounts": [],
        }
        documents: dict[str, dict[str, Any]] = {
            "/v1/account": {"object": "account", "id": LIVE.merchant_account_id},
            "/v1/customers": {"id": "cus_fixture", "livemode": True},
            "/v1/prices/price_fixture": self.price(),
            "/v1/products/prod_fixture": {
                "id": "prod_fixture",
                "object": "product",
                "active": True,
                "livemode": True,
            },
            "/v1/checkout/sessions": session,
            "/v1/checkout/sessions/cs_fixture": session,
            "/v1/checkout/sessions/cs_fixture/line_items": {
                "object": "list",
                "has_more": False,
                "data": [checkout_item],
            },
            "/v1/subscriptions/sub_fixture": {
                "object": "subscription",
                "id": "sub_fixture",
                "customer": "cus_fixture",
                "livemode": True,
                "status": self.status,
                "cancel_at_period_end": False,
                "items": {
                    "has_more": False,
                    "data": [
                        {
                            "id": "si_fixture",
                            "price": self.price(),
                            "quantity": 1,
                            "current_period_start": start,
                            "current_period_end": end,
                            "discounts": [],
                            "tax_rates": [],
                        }
                    ],
                },
                "collection_method": "charge_automatically",
                "automatic_tax": {"enabled": False},
                "metadata": {"inlet_offer_binding": self.binding_digest},
                "discounts": [],
                "default_tax_rates": [],
                "trial_start": None,
                "trial_end": None,
                "schedule": None,
                "pending_update": None,
                "pause_collection": None,
                "latest_invoice": "in_fixture",
            },
            "/v1/invoices/in_fixture": {
                "object": "invoice",
                "id": "in_fixture",
                "livemode": True,
                "customer": "cus_fixture",
                "status": "paid",
                "currency": "usd",
                "parent": {
                    "type": "subscription_details",
                    "subscription_details": {"subscription": "sub_fixture"},
                },
                "billing_reason": "subscription_create",
                "collection_method": "charge_automatically",
                "automatic_tax": {"enabled": False},
                "amount_due": 1000,
                "amount_paid": 1000,
                "subtotal": 1000,
                "total": 1000,
                "amount_remaining": 0,
                "amount_overpaid": 0,
                "amount_shipping": 0,
                "starting_balance": 0,
                "ending_balance": 0,
                "pre_payment_credit_notes_amount": 0,
                "post_payment_credit_notes_amount": 0,
                "discounts": [],
                "default_tax_rates": [],
                "total_discount_amounts": [],
                "total_taxes": [],
                "lines": {"has_more": False, "data": [line]},
                "payments": {"has_more": False, "data": [payment]},
            },
            "/v1/payment_intents/pi_fixture": {
                "object": "payment_intent",
                "id": "pi_fixture",
                "customer": "cus_fixture",
                "status": "succeeded",
                "livemode": True,
                "currency": "usd",
                "amount": 1000,
                "amount_received": 1000,
                "latest_charge": "ch_fixture",
            },
            "/v1/charges/ch_fixture": {
                "object": "charge",
                "id": "ch_fixture",
                "customer": "cus_fixture",
                "payment_intent": "pi_fixture",
                "livemode": True,
                "paid": True,
                "captured": True,
                "refunded": False,
                "disputed": False,
                "amount": 1000,
                "amount_refunded": 0,
                "currency": "usd",
            },
            "/v1/billing_portal/configurations/bpc_fixture": {
                "object": "billing_portal.configuration",
                "id": "bpc_fixture",
                "active": True,
                "livemode": True,
                "features": {
                    "subscription_cancel": {
                        "enabled": True,
                        "mode": "at_period_end",
                        "proration_behavior": "none",
                    },
                    "subscription_update": {"enabled": False},
                    "customer_update": {"enabled": False},
                    "payment_method_update": {"enabled": True},
                    "invoice_history": {"enabled": True},
                },
            },
            "/v1/billing_portal/sessions": {
                "customer": "cus_fixture",
                "configuration": "bpc_fixture",
                "livemode": True,
                "url": "https://billing.stripe.com/p/session/fixture",
            },
        }
        result = documents[path]
        result.update(deepcopy(self.mutations.get(path, {})))
        return result

    def respond(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.calls.append((request.method, path))
        if path == "/v1/checkout/sessions" and request.method == "POST":
            values = parse_qs(request.content.decode())
            self.checkout_key = request.headers["Idempotency-Key"]
            self.post_keys.append(self.checkout_key)
            self.binding_digest = values["metadata[inlet_offer_binding]"][0]
            assert values["line_items[0][quantity]"] == ["1"]
            assert values["automatic_tax[enabled]"] == ["false"]
            if self.lost:
                raise httpx.ReadTimeout("synthetic lost response", request=request)
        body = self.document(path)
        if path == "/v1/checkout/sessions" and request.method == "GET":
            body = {"object": "list", "has_more": False, "data": [body]}
        return httpx.Response(200, json=body)


def configure(monkeypatch: pytest.MonkeyPatch, profile: OfferProfileV1 = PROFILE) -> None:
    monkeypatch.setattr(settings, "billing_provider_mode", "stripe_live")
    monkeypatch.setattr(settings, "billing_live_enabled", True)
    monkeypatch.setattr(settings, "billing_api_version", profile.api_version)
    monkeypatch.setattr(settings, "billing_merchant_account_id", LIVE.merchant_account_id)
    monkeypatch.setattr(settings, "billing_offer_profile", profile.model_dump_json())


def qualified_journey(customer_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    configure(monkeypatch)
    fixture = StripeOfferFixture()
    with Session(customer_engine) as db:
        wid, _ = setup(db, "live")
        other, _ = setup(db, "test")
        row = owned(db, other, NOW, scope=TEST)
        row.customer_id = "cus_fixture"
        db.commit()
        assert (
            checkout(db, wid, POLICY, fixture.wire, "https://inlet.example/settings", NOW)["mode"]
            == "stripe_live"
        )
        import json

        for scope in (TEST, LIVE):
            body = json.dumps(
                {
                    "id": "evt_identical",
                    "type": "customer.subscription.updated",
                    "livemode": scope.environment == "live",
                    "data": {"object": {"id": "sub_fixture", "customer": "cus_fixture"}},
                }
            ).encode()
            receive(db, body, signature(body), SECRET, NOW, scope=scope)
    assert run(lambda: Session(customer_engine), POLICY, fixture.wire, NOW)["events"] == 1
    with Session(customer_engine) as db:
        require_entitlement(db, wid, POLICY, NOW, scope=LIVE)
        saved = repository.billing(db, wid, LIVE)
        assert saved is not None and saved.qualification is not None
        assert saved.qualification["invoice_id"] == "in_fixture"
        from app.database.session import Base
        from app.lifecycle.export_serializers import serialize

        mapping = (
            db.execute(
                select(Base.metadata.tables["customer_workspace_billing"]).where(
                    Base.metadata.tables["customer_workspace_billing"].c.workspace_id == wid
                )
            )
            .mappings()
            .one()
        )
        exported, missing = serialize("customer_workspace_billing", dict(mapping))
        assert missing == [] and exported["qualification"]["invoice_id"] == "in_fixture"
        binding_mapping = (
            db.execute(select(Base.metadata.tables["customer_billing_offer_bindings"]))
            .mappings()
            .one()
        )
        document, missing = serialize("customer_billing_offer_bindings", dict(binding_mapping))
        assert missing == [] and document["profile"]["unit_amount"] == 1000
        forged = dict(binding_mapping)
        forged["profile"] = PROFILE.model_copy(update={"unit_amount": 2000}).model_dump(mode="json")
        assert serialize("customer_billing_offer_bindings", forged)[1] == ["profile"]
        changed = PROFILE.model_copy(update={"operator_review_reference": "changed-review"})
        configure(monkeypatch, changed)
        with pytest.raises(HTTPException, match="qualified paid offer unavailable"):
            require_entitlement(db, wid, POLICY, NOW, scope=LIVE)
        configure(monkeypatch)
        assert repository.event(db, "evt_identical", TEST).state == "pending"  # type: ignore[union-attr]
        assert (
            management(db, wid, fixture.wire, "bpc_fixture", "https://inlet.example/settings", NOW)[
                "mode"
            ]
            == "stripe_live"
        )
    fixture.status = "canceled"
    assert (
        run(lambda: Session(customer_engine), POLICY, fixture.wire, NOW + timedelta(minutes=3))[
            "refreshes"
        ]
        == 1
    )
    with Session(customer_engine) as db, pytest.raises(HTTPException):
        require_entitlement(db, wid, POLICY, NOW + timedelta(minutes=3), scope=LIVE)
    assert len(fixture.post_keys) == 1


def test_qualified_journey(customer_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    qualified_journey(customer_engine, monkeypatch)


def bound() -> BoundOfferV1:
    return BoundOfferV1(
        id="a" * 32,
        workspace_id=1,
        checkout_key=f"{int(NOW.timestamp())}_" + "a" * 32,
        profile=PROFILE,
        created_at=NOW,
    )


@pytest.mark.parametrize(
    "path,field,value",
    [
        ("/v1/prices/price_fixture", "unit_amount", 999),
        ("/v1/prices/price_fixture", "currency", "eur"),
        ("/v1/prices/price_fixture", "product", "prod_other"),
        ("/v1/prices/price_fixture", "tax_behavior", "unspecified"),
        ("/v1/prices/price_fixture", "transform_quantity", {"divide_by": 10}),
        ("/v1/subscriptions/sub_fixture", "trial_end", 9999999999),
        ("/v1/subscriptions/sub_fixture", "schedule", "sub_sched_other"),
        ("/v1/subscriptions/sub_fixture", "discounts", ["di_other"]),
        ("/v1/invoices/in_fixture", "status", "open"),
        ("/v1/invoices/in_fixture", "amount_paid", 999),
        ("/v1/invoices/in_fixture", "starting_balance", 100),
        ("/v1/invoices/in_fixture", "post_payment_credit_notes_amount", 100),
        ("/v1/invoices/in_fixture", "currency", "eur"),
        ("/v1/payment_intents/pi_fixture", "status", "processing"),
        ("/v1/payment_intents/pi_fixture", "customer", "cus_other"),
        ("/v1/charges/ch_fixture", "refunded", True),
        ("/v1/charges/ch_fixture", "disputed", True),
    ],
)
def test_consequential_provider_mismatch_rejected(path: str, field: str, value: Any) -> None:
    fixture = StripeOfferFixture()
    fixture.binding_digest = digest(bound())
    fixture.mutations[path] = {field: value}
    with pytest.raises(BillingProviderError):
        fixture.wire.current_bound(bound(), "cus_fixture", "sub_fixture", NOW)


def test_profile_has_no_commercial_defaults() -> None:
    with pytest.raises(ValidationError):
        OfferProfileV1(scope=LIVE)  # type: ignore[call-arg]


def test_config_change_recovers_original_key_without_reposting(
    customer_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    configure(monkeypatch)
    fixture = StripeOfferFixture()
    fixture.lost = True
    with Session(customer_engine) as db:
        wid, _ = setup(db, "lost")
        with pytest.raises(HTTPException, match="retry safely"):
            checkout(db, wid, POLICY, fixture.wire, "https://inlet.example/settings", NOW)
        original = db.scalar(select(BillingOfferBinding))
        assert original is not None
        original_id = original.id
        changed = PROFILE.model_copy(
            update={"unit_amount": 2000, "operator_review_reference": "new-review"}
        )
        configure(monkeypatch, changed)
        fixture.lost = False
        result = checkout(db, wid, POLICY, fixture.wire, "https://inlet.example/settings", NOW)
        assert result["id"] == "cs_fixture" and len(fixture.post_keys) == 1
        assert db.scalar(select(BillingOfferBinding.id)) == original_id
        assert original.profile_digest == digest(PROFILE)


@pytest.mark.parametrize(
    "mutation",
    [
        {"recurring": {"interval": "year", "interval_count": 1, "usage_type": "licensed"}},
        {"recurring": {"interval": "month", "interval_count": 2, "usage_type": "licensed"}},
        {"recurring": {"interval": "month", "interval_count": 1, "usage_type": "metered"}},
    ],
)
def test_price_recurring_terms_are_exact(mutation: dict[str, Any]) -> None:
    fixture = StripeOfferFixture()
    fixture.mutations["/v1/prices/price_fixture"] = mutation
    with pytest.raises(BillingProviderError):
        fixture.wire.qualify_offer(PROFILE)
    assert not any(method == "POST" for method, _ in fixture.calls)


@pytest.mark.parametrize(
    "section,mutation",
    [
        (
            "subscription_cancel",
            {"enabled": True, "mode": "immediately", "proration_behavior": "none"},
        ),
        (
            "subscription_cancel",
            {"enabled": True, "mode": "at_period_end", "proration_behavior": "create_prorations"},
        ),
        ("subscription_update", {"enabled": True}),
        ("customer_update", {"enabled": True}),
    ],
)
def test_unsupported_portal_policy_blocks_new_purchase(
    section: str, mutation: dict[str, Any]
) -> None:
    fixture = StripeOfferFixture()
    features = fixture.document("/v1/billing_portal/configurations/bpc_fixture")["features"]
    features[section] = mutation
    fixture.mutations["/v1/billing_portal/configurations/bpc_fixture"] = {"features": features}
    with pytest.raises(BillingProviderError):
        fixture.wire.checkout_bound(bound(), "cus_fixture", "https://inlet.example/settings")
    assert not any(method == "POST" for method, _ in fixture.calls)


@pytest.mark.parametrize(
    "case",
    [
        "foreign_invoice",
        "foreign_payment",
        "wrong_period",
        "proration",
        "multiple_lines",
        "partial_payment",
        "test_line",
    ],
)
def test_invoice_payment_and_period_lineage(case: str) -> None:
    fixture = StripeOfferFixture()
    fixture.binding_digest = digest(bound())
    invoice = fixture.document("/v1/invoices/in_fixture")
    if case == "foreign_invoice":
        invoice["parent"]["subscription_details"]["subscription"] = "sub_other"
    elif case == "foreign_payment":
        invoice["payments"]["data"][0]["invoice"] = "in_other"
    elif case == "wrong_period":
        invoice["lines"]["data"][0]["period"]["end"] += 1
    elif case == "proration":
        invoice["lines"]["data"][0]["parent"]["subscription_item_details"]["proration"] = True
    elif case == "multiple_lines":
        invoice["lines"]["data"].append(deepcopy(invoice["lines"]["data"][0]))
    elif case == "test_line":
        invoice["lines"]["data"][0]["livemode"] = False
    else:
        invoice["payments"]["data"][0]["amount_paid"] = 999
    fixture.mutations["/v1/invoices/in_fixture"] = invoice
    with pytest.raises(BillingProviderError):
        fixture.wire.current_bound(bound(), "cus_fixture", "sub_fixture", NOW)


def test_offer_binding_is_immutable_and_owner_fk_is_enforced(customer_engine: Engine) -> None:
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    if customer_engine.dialect.name == "sqlite":
        with customer_engine.connect() as connection:
            connection.execute(text("PRAGMA foreign_keys=ON"))
    with Session(customer_engine) as db:
        wid, _ = setup(db, "first")
        other, _ = setup(db, "other")
        first = owned(db, wid, NOW, scope=LIVE)
        first.checkout_key = bound().checkout_key
        from app.billing.offer_bindings import install

        installed = install(db, first, PROFILE, NOW)
        db.commit()
        second = owned(db, other, NOW, scope=LIVE)
        second.checkout_offer_binding_id = installed.id
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        stored = db.get(BillingOfferBinding, installed.id)
        assert stored is not None
        stored.profile_digest = "0" * 64
        with pytest.raises(ValueError, match="immutable"):
            db.commit()
        db.rollback()


def test_failed_new_qualification_invalidates_recent_entitlement(
    customer_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.billing.service import refresh

    configure(monkeypatch)
    fixture = StripeOfferFixture()
    with Session(customer_engine) as db:
        wid, _ = setup(db, "requalification")
        checkout(db, wid, POLICY, fixture.wire, "https://inlet.example/settings", NOW)
        refresh(db, wid, POLICY, fixture.wire, NOW, subscription_id="sub_fixture")
        db.commit()
        require_entitlement(db, wid, POLICY, NOW, scope=LIVE)
    fixture.mutations["/v1/invoices/in_fixture"] = {"amount_paid": 999}
    later = NOW + timedelta(minutes=3)
    assert run(lambda: Session(customer_engine), POLICY, fixture.wire, later)["failed"] == 1
    with Session(customer_engine) as db, pytest.raises(HTTPException):
        require_entitlement(db, wid, POLICY, later, scope=LIVE)


@pytest.mark.parametrize(
    "mutation",
    [
        {"currency": "eur"},
        {"amount_total": 999},
        {"automatic_tax": {"enabled": True}},
        {"allow_promotion_codes": True},
        {"total_details": {"amount_discount": 1, "amount_tax": 0, "amount_shipping": 0}},
        {"metadata": {"inlet_offer_binding": "f" * 64}},
    ],
)
def test_checkout_projection_is_qualified(mutation: dict[str, Any]) -> None:
    fixture = StripeOfferFixture()
    fixture.mutations["/v1/checkout/sessions"] = mutation
    with pytest.raises(BillingProviderError):
        fixture.wire.checkout_bound(bound(), "cus_fixture", "https://inlet.example/settings")
    assert len(fixture.post_keys) == 1


def test_existing_unbound_checkout_is_not_retroactively_qualified(
    customer_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    configure(monkeypatch)
    fixture = StripeOfferFixture()
    with Session(customer_engine) as db:
        wid, _ = setup(db, "legacy-request")
        row = owned(db, wid, NOW, scope=LIVE)
        row.customer_id = "cus_fixture"
        row.checkout_key = bound().checkout_key
        row.checkout_price = PROFILE.price_id
        db.commit()
        with pytest.raises(HTTPException, match="pending checkout offer unavailable"):
            checkout(db, wid, POLICY, fixture.wire, "https://inlet.example/settings", NOW)
        assert db.scalar(select(BillingOfferBinding.id)) is None
    assert fixture.calls == []


@pytest.mark.parametrize(
    "field,value", [("quantity", True), ("promotion_codes", 0), ("unit_amount", True)]
)
def test_offer_policy_does_not_coerce_boolean_and_numeric_values(field: str, value: Any) -> None:
    raw = PROFILE.model_dump(mode="json")
    raw[field] = value
    with pytest.raises(ValidationError):
        OfferProfileV1.model_validate(raw)


def test_retired_price_blocks_new_purchase_but_keeps_original_paid_evidence() -> None:
    fixture = StripeOfferFixture()
    fixture.binding_digest = digest(bound())
    fixture.mutations["/v1/prices/price_fixture"] = {"active": False}
    fixture.mutations["/v1/products/prod_fixture"] = {"active": False}
    state = fixture.wire.current_bound(bound(), "cus_fixture", "sub_fixture", NOW)
    assert state.qualification is not None
    with pytest.raises(BillingProviderError):
        fixture.wire.checkout_bound(bound(), "cus_fixture", "https://inlet.example/settings")
    assert not fixture.post_keys
