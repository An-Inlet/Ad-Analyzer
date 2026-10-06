"""Strict 2025-06-30.basil projections; never persist raw Stripe/customer payloads."""

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from app.billing.contracts import CheckoutResult, CheckoutState, SubscriptionState
from app.billing.offers import BoundOfferV1, OfferProfileV1, OfferQualificationV1, digest
from app.billing.stripe import BillingProviderError, identifier

if TYPE_CHECKING:
    from app.billing.stripe import StripeBilling


def require(condition: bool) -> None:
    if not condition:
        raise BillingProviderError("commercial_offer_unqualified")


def integer(value: Any, expected: int) -> bool:
    return type(value) is int and value == expected


def single(value: Any) -> dict[str, Any]:
    require(isinstance(value, dict) and value.get("has_more") is False)
    rows = value.get("data")
    require(isinstance(rows, list) and len(rows) == 1 and isinstance(rows[0], dict))
    return dict(rows[0])


def scope(wire: "StripeBilling", profile: OfferProfileV1) -> None:
    require(wire.scope == profile.scope and wire.version == profile.api_version)


def price_document(profile: OfferProfileV1, body: dict[str, Any], *, purchase: bool = True) -> None:
    require(body.get("livemode") is (profile.scope.environment == "live"))
    recurring = body.get("recurring")
    if not isinstance(recurring, dict):
        raise BillingProviderError("commercial_offer_unqualified")
    require(
        body.get("id") == profile.price_id
        and body.get("object") == "price"
        and (body.get("active") is True if purchase else type(body.get("active")) is bool)
        and body.get("product") == profile.product_id
        and body.get("currency") == profile.currency
        and body.get("type") == "recurring"
        and body.get("billing_scheme") == "per_unit"
        and integer(body.get("unit_amount"), profile.unit_amount)
        and body.get("tax_behavior") == profile.price_tax_behavior
        and recurring.get("interval") == profile.interval
        and integer(recurring.get("interval_count"), profile.interval_count)
        and recurring.get("usage_type") == "licensed"
    )
    require(Decimal(str(body.get("unit_amount_decimal"))) == Decimal(profile.unit_amount))
    require(
        all(
            body.get(key) is None
            for key in ("custom_unit_amount", "tiers_mode", "transform_quantity")
        )
    )
    require(recurring.get("trial_period_days") is None)


def price(wire: "StripeBilling", profile: OfferProfileV1, *, purchase: bool = True) -> None:
    scope(wire, profile)
    price_document(
        profile, wire.request("GET", "/v1/prices/" + profile.price_id), purchase=purchase
    )
    product = wire.request("GET", "/v1/products/" + profile.product_id)
    require(
        product.get("id") == profile.product_id
        and product.get("object") == "product"
        and (product.get("active") is True if purchase else type(product.get("active")) is bool)
    )


def checkout_document(
    wire: "StripeBilling", bound: BoundOfferV1, customer: str, body: dict[str, Any]
) -> str:
    p = bound.profile
    scope(wire, p)
    cid = identifier(body["id"], "cs")
    require(
        body.get("object") == "checkout.session"
        and body.get("customer") == customer
        and body.get("mode") == "subscription"
        and body.get("currency") == p.currency
        and integer(body.get("amount_subtotal"), p.unit_amount)
        and integer(body.get("amount_total"), p.unit_amount)
        and (
            body.get("allow_promotion_codes") is None or body.get("allow_promotion_codes") is False
        )
        and body.get("automatic_tax", {}).get("enabled") is False
        and body.get("metadata", {}).get("inlet_offer_binding") == digest(bound)
        and body.get("metadata", {}).get("inlet_checkout_request") == bound.checkout_key
    )
    require(
        all(
            integer(body.get("total_details", {}).get(key), 0)
            for key in ("amount_discount", "amount_tax", "amount_shipping")
        )
    )
    require(
        not body.get("discounts")
        and not body.get("shipping_options")
        and not body.get("shipping_cost")
    )
    require(not body.get("adaptive_pricing", {}).get("enabled", False))
    item = single(
        wire.request(
            "GET",
            "/v1/checkout/sessions/" + cid + "/line_items",
            params={"limit": "2"},
            collection="line_items",
        )
    )
    require(
        integer(item.get("quantity"), 1)
        and item.get("price", {}).get("id") == p.price_id
        and item.get("price", {}).get("product") == p.product_id
        and item.get("currency") == p.currency
        and integer(item.get("amount_subtotal"), p.unit_amount)
        and integer(item.get("amount_total"), p.unit_amount)
        and integer(item.get("amount_discount"), 0)
        and integer(item.get("amount_tax"), 0)
    )
    price_document(p, item["price"], purchase=False)
    return cid


def checkout(
    wire: "StripeBilling",
    bound: BoundOfferV1,
    customer: str,
    return_url: str,
    *,
    recover_only: bool = False,
) -> CheckoutResult:
    p = bound.profile
    scope(wire, p)
    if recover_only or wire.expired_attempt(bound.checkout_key):
        body = wire.recover_checkout(customer, p.price_id, bound.checkout_key)
    else:
        price(wire, p)
        portal_configuration(wire, p)
        body = wire.request(
            "POST",
            "/v1/checkout/sessions",
            {
                "customer": identifier(customer, "cus"),
                "mode": "subscription",
                "line_items[0][price]": p.price_id,
                "line_items[0][quantity]": "1",
                "success_url": return_url,
                "cancel_url": return_url,
                "allow_promotion_codes": "false",
                "automatic_tax[enabled]": "false",
                "adaptive_pricing[enabled]": "false",
                "metadata[inlet_checkout_request]": bound.checkout_key,
                "metadata[inlet_offer_binding]": digest(bound),
                "subscription_data[metadata][inlet_offer_binding]": digest(bound),
            },
            bound.checkout_key,
        )
    cid = checkout_document(wire, bound, customer, body)
    return CheckoutResult(
        scope=p.scope,
        livemode=p.scope.environment == "live",
        binding_digest=digest(bound),
        id=cid,
        url=body.get("url"),
        expires_at=datetime.fromtimestamp(body["expires_at"], UTC),
    )


def checkout_state(
    wire: "StripeBilling", bound: BoundOfferV1, customer: str, cid: str, now: datetime
) -> CheckoutState:
    body = wire.request("GET", "/v1/checkout/sessions/" + identifier(cid, "cs"))
    require(checkout_document(wire, bound, customer, body) == cid)
    return CheckoutState(
        scope=bound.profile.scope,
        livemode=wire.scope.environment == "live",
        binding_digest=digest(bound),
        id=cid,
        customer_id=customer,
        status=body["status"],
        subscription_id=body.get("subscription"),
        observed_at=now,
    )


def current(
    wire: "StripeBilling", bound: BoundOfferV1, customer: str, sid: str, now: datetime
) -> SubscriptionState:
    p = bound.profile
    scope(wire, p)
    body = wire.request("GET", "/v1/subscriptions/" + identifier(sid, "sub"))
    require(
        body.get("object") == "subscription"
        and body.get("id") == sid
        and body.get("customer") == customer
    )
    item = single(body.get("items"))
    require(item.get("price", {}).get("id") == p.price_id and integer(item.get("quantity"), 1))
    start, end = item.get("current_period_start"), item.get("current_period_end")
    if (
        not isinstance(start, int)
        or not isinstance(end, int)
        or type(start) is bool
        or type(end) is bool
        or start >= end
    ):
        raise BillingProviderError("commercial_offer_unqualified")
    state = SubscriptionState(
        scope=p.scope,
        livemode=p.scope.environment == "live",
        binding_digest=digest(bound),
        customer_id=customer,
        subscription_id=sid,
        price_id=p.price_id,
        status=body["status"],
        period_end=datetime.fromtimestamp(end, UTC),
        cancel_at_period_end=body["cancel_at_period_end"],
        observed_at=now,
    )
    # Non-active snapshots preserve cancellation/delinquency evidence; never entitle.
    if state.status != "active":
        return state
    price(wire, p, purchase=False)
    price_document(p, item["price"], purchase=False)
    require(
        start <= now.timestamp() < end
        and body.get("collection_method") == "charge_automatically"
        and body.get("automatic_tax", {}).get("enabled") is False
        and body.get("metadata", {}).get("inlet_offer_binding") == digest(bound)
    )
    require(
        all(
            body.get(key) in (None, [])
            for key in (
                "discounts",
                "default_tax_rates",
                "trial_start",
                "trial_end",
                "schedule",
                "pending_update",
                "pause_collection",
            )
        )
    )
    require(not item.get("discounts") and not item.get("tax_rates"))
    invoice = wire.request("GET", "/v1/invoices/" + identifier(body["latest_invoice"], "in"))
    iid = invoice.get("id")
    require(
        invoice.get("object") == "invoice"
        and iid == body["latest_invoice"]
        and invoice.get("customer") == customer
        and invoice.get("status") == "paid"
        and invoice.get("currency") == p.currency
        and invoice.get("parent", {}).get("type") == "subscription_details"
        and invoice.get("parent", {}).get("subscription_details", {}).get("subscription") == sid
        and invoice.get("billing_reason") in {"subscription_create", "subscription_cycle"}
        and invoice.get("collection_method") == "charge_automatically"
        and invoice.get("automatic_tax", {}).get("enabled") is False
    )
    require(
        all(
            integer(invoice.get(key), p.unit_amount)
            for key in ("amount_due", "amount_paid", "subtotal", "total")
        )
    )
    require(
        all(
            integer(invoice.get(key), 0)
            for key in (
                "amount_remaining",
                "amount_overpaid",
                "amount_shipping",
                "starting_balance",
                "pre_payment_credit_notes_amount",
                "post_payment_credit_notes_amount",
            )
        )
    )
    require(invoice.get("ending_balance") in (None, 0))
    require(
        all(
            invoice.get(key) in (None, [])
            for key in ("discounts", "default_tax_rates", "total_discount_amounts", "total_taxes")
        )
    )
    line = single(invoice.get("lines"))
    details = line.get("parent", {}).get("subscription_item_details", {})
    require(
        line.get("object") == "line_item"
        and line.get("livemode") is (p.scope.environment == "live")
        and line.get("parent", {}).get("type") == "subscription_item_details"
        and details.get("subscription_item") == item.get("id")
        and details.get("subscription") == sid
        and details.get("proration") is False
        and line.get("pricing", {}).get("price_details")
        == {"price": p.price_id, "product": p.product_id}
        and line.get("currency") == p.currency
        and integer(line.get("quantity"), 1)
        and integer(line.get("amount"), p.unit_amount)
        and line.get("period") == {"start": start, "end": end}
    )
    require(
        all(
            line.get(key) in (None, [])
            for key in ("discounts", "discount_amounts", "taxes", "pretax_credit_amounts")
        )
    )
    payment = single(invoice.get("payments"))
    require(
        payment.get("object") == "invoice_payment"
        and payment.get("invoice") == iid
        and payment.get("status") == "paid"
        and payment.get("currency") == p.currency
        and integer(payment.get("amount_paid"), p.unit_amount)
        and integer(payment.get("amount_requested"), p.unit_amount)
        and payment.get("payment", {}).get("type") == "payment_intent"
        and payment.get("livemode") is (p.scope.environment == "live")
    )
    piid = identifier(payment["payment"]["payment_intent"], "pi")
    intent = wire.request("GET", "/v1/payment_intents/" + piid)
    require(
        intent.get("object") == "payment_intent"
        and intent.get("id") == piid
        and intent.get("customer") == customer
        and intent.get("status") == "succeeded"
        and intent.get("currency") == p.currency
        and integer(intent.get("amount"), p.unit_amount)
        and integer(intent.get("amount_received"), p.unit_amount)
    )
    charge = wire.request("GET", "/v1/charges/" + identifier(intent["latest_charge"], "ch"))
    require(
        charge.get("object") == "charge"
        and charge.get("id") == intent["latest_charge"]
        and charge.get("payment_intent") == piid
        and charge.get("customer") == customer
        and charge.get("paid") is True
        and charge.get("captured") is True
        and charge.get("refunded") is False
        and charge.get("disputed") is False
        and charge.get("currency") == p.currency
        and integer(charge.get("amount"), p.unit_amount)
        and integer(charge.get("amount_refunded"), 0)
    )
    projection = {
        "binding": digest(bound),
        "invoice": iid,
        "payment": payment["id"],
        "intent": piid,
        "charge": charge["id"],
        "amount": p.unit_amount,
        "currency": p.currency,
        "start": start,
        "end": end,
        "status": state.status,
        "cancel": state.cancel_at_period_end,
    }
    q = OfferQualificationV1(
        binding_id=bound.id,
        binding_digest=digest(bound),
        profile_digest=digest(p),
        scope=p.scope,
        customer_id=customer,
        subscription_id=sid,
        price_id=p.price_id,
        product_id=p.product_id,
        invoice_id=iid,
        payment_id=payment["id"],
        payment_intent_id=piid,
        charge_id=charge["id"],
        currency=p.currency,
        amount_paid=p.unit_amount,
        period_start=datetime.fromtimestamp(start, UTC),
        period_end=state.period_end,
        status="active",
        cancel_at_period_end=state.cancel_at_period_end,
        observed_at=now,
        projection_digest=hashlib.sha256(
            json.dumps(projection, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    )
    return state.model_copy(update={"qualification": q})


def portal_configuration(wire: "StripeBilling", p: OfferProfileV1) -> None:
    scope(wire, p)
    config = wire.request("GET", "/v1/billing_portal/configurations/" + p.portal.configuration_id)
    require(
        config.get("object") == "billing_portal.configuration"
        and config.get("id") == p.portal.configuration_id
        and config.get("active") is True
    )
    f = config.get("features", {})
    require(
        f.get("subscription_cancel", {}).get("enabled") is True
        and f["subscription_cancel"].get("mode") == "at_period_end"
        and f["subscription_cancel"].get("proration_behavior") == "none"
        and f.get("subscription_update", {}).get("enabled") is False
        and f.get("customer_update", {}).get("enabled") is False
        and f.get("payment_method_update", {}).get("enabled") is p.portal.payment_method_update
        and f.get("invoice_history", {}).get("enabled") is p.portal.invoice_history
    )
    require(
        not set(f)
        - {
            "subscription_cancel",
            "subscription_update",
            "customer_update",
            "payment_method_update",
            "invoice_history",
        }
    )


def portal(
    wire: "StripeBilling", bound: BoundOfferV1, customer: str, return_url: str, key: str
) -> str:
    portal_configuration(wire, bound.profile)
    return wire.portal(customer, bound.profile.portal.configuration_id, return_url, key)
