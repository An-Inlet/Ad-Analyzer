"""Workspace billing ownership and canonical-state entitlement reconciliation."""

import re
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.billing.contracts import BillingPolicy, BillingTransport, UnavailableBilling
from app.billing.models import BillingEvent, WorkspaceBilling
from app.mandates.service import workspace_lock
from app.shopify.security import utc


def ready(transport: BillingTransport) -> None:
    if isinstance(transport, UnavailableBilling) or transport.mode != "fixture":
        raise HTTPException(503, "billing unavailable")


def owned(db: Session, wid: int) -> WorkspaceBilling:
    workspace_lock(db, wid)
    row = db.get(WorkspaceBilling, wid, populate_existing=True)
    if row is None:
        row = WorkspaceBilling(workspace_id=wid, customer_request_key=uuid4().hex)
        db.add(row)
        db.flush()
    return row


def checkout(
    db: Session,
    wid: int,
    policy: BillingPolicy,
    transport: BillingTransport,
    return_url: str,
    now: datetime,
) -> dict[str, Any]:
    ready(transport)
    redirect = urlsplit(return_url)
    if (
        redirect.scheme != "https"
        or not redirect.hostname
        or redirect.username
        or redirect.fragment
    ):
        raise HTTPException(503, "billing return unavailable")
    row = owned(db, wid)
    if row.status in {"active", "trialing", "past_due", "unpaid", "paused", "incomplete"}:
        raise HTTPException(409, "existing subscription requires billing management")
    key, customer = row.customer_request_key, row.customer_id
    db.commit()  # Durable idempotency key exists before the provider boundary.
    if customer is None:
        try:
            customer = transport.customer(wid, key)
        except Exception:
            raise HTTPException(502, "billing customer pending; retry safely") from None
        if re.fullmatch(r"cus_[A-Za-z0-9_]{1,128}", customer) is None:
            raise HTTPException(502, "billing customer unavailable")
        row = owned(db, wid)
        if row.customer_id is not None and row.customer_id != customer:
            raise HTTPException(409, "billing customer conflict")
        row.customer_id = customer
        db.commit()
    row = owned(db, wid)
    if row.status in {"active", "trialing", "past_due", "unpaid", "paused", "incomplete"}:
        raise HTTPException(409, "existing subscription requires billing management")
    if row.checkout_url and row.checkout_expires_at and utc(row.checkout_expires_at) > now:
        if row.checkout_price != policy.price_id:
            raise HTTPException(409, "checkout already pending for another plan")
        return {"mode": "fixture", "url": row.checkout_url, "id": row.checkout_id}
    if row.checkout_id is not None:
        row.checkout_key, row.checkout_id, row.checkout_url = None, None, None
    if row.checkout_key is None:
        row.checkout_key, row.checkout_price = uuid4().hex, policy.price_id
    if row.checkout_price != policy.price_id:
        raise HTTPException(409, "pending checkout must be reconciled")
    checkout_key = row.checkout_key
    db.commit()
    try:
        result = transport.checkout(customer, policy.price_id, checkout_key, return_url)
    except Exception:
        raise HTTPException(502, "checkout pending; retry safely") from None
    location = urlsplit(result.url)
    if (
        location.scheme != "https"
        or location.netloc != "checkout.stripe.com"
        or location.username
        or result.expires_at <= now
    ):
        raise HTTPException(502, "checkout result unavailable")
    row = owned(db, wid)
    if row.checkout_key != checkout_key or row.customer_id != customer:
        raise HTTPException(409, "checkout ownership changed")
    if row.checkout_id is not None and row.checkout_id != result.id:
        raise HTTPException(409, "checkout result conflict")
    row.checkout_id, row.checkout_url, row.checkout_expires_at = (
        result.id,
        result.url,
        result.expires_at,
    )
    db.commit()
    return {"mode": "fixture", "url": result.url, "id": result.id}


def reconcile(
    db: Session,
    wid: int,
    event_id: str,
    policy: BillingPolicy,
    transport: BillingTransport,
    now: datetime,
) -> bool:
    ready(transport)
    row = owned(db, wid)
    event = db.get(BillingEvent, event_id, populate_existing=True)
    if event is None or row.customer_id is None or event.customer_id != row.customer_id:
        raise HTTPException(404, "billing event unavailable")
    if event.state == "processed":
        return False
    if row.subscription_id is not None and row.subscription_id != event.subscription_id:
        event.state, event.error_code = "unresolved", "subscription_identity_conflict"
        db.commit()
        raise HTTPException(409, "subscription identity requires reconciliation")
    try:
        refresh(db, wid, policy, transport, now, subscription_id=event.subscription_id)
    except HTTPException:
        event.error_code = "provider_read_unavailable"
        event.next_attempt_at = now + timedelta(minutes=1)
        db.commit()
        raise
    event.state, event.processed_at, event.error_code = "processed", now, None
    event.next_attempt_at = None
    db.commit()
    return True


def require_entitlement(
    db: Session,
    wid: int,
    policy: BillingPolicy,
    now: datetime,
    *,
    account_count: int = 0,
) -> None:
    row = owned(db, wid)
    allowed = {"active", "trialing"} if policy.trial_allowed else {"active"}
    if (
        row.status not in allowed
        or row.price_id != policy.price_id
        or row.error_code
        or row.verified_at is None
        or not now - timedelta(seconds=policy.max_snapshot_age_seconds)
        <= utc(row.verified_at)
        <= now
        or row.period_end is None
        or utc(row.period_end) <= now
        or account_count < 0
        or account_count > policy.max_accounts
    ):
        raise HTTPException(402, "paid workspace entitlement unavailable")


def refresh(
    db: Session,
    wid: int,
    policy: BillingPolicy,
    transport: BillingTransport,
    now: datetime,
    *,
    subscription_id: str | None = None,
) -> None:
    ready(transport)
    row = owned(db, wid)
    subscription_id = subscription_id or row.subscription_id
    if row.customer_id is None or subscription_id is None:
        raise HTTPException(409, "billing identity unavailable")
    if row.subscription_id is not None and row.subscription_id != subscription_id:
        raise HTTPException(409, "billing identity conflict")
    try:
        state = transport.current(row.customer_id, subscription_id, now)
    except Exception:
        raise HTTPException(502, "billing verification unavailable") from None
    if (
        state.customer_id != row.customer_id
        or state.subscription_id != subscription_id
        or state.observed_at < now - timedelta(seconds=30)
        or state.observed_at > now
        or state.livemode
    ):
        raise HTTPException(409, "billing verification mismatch")
    row.subscription_id, row.price_id = state.subscription_id, state.price_id
    row.status, row.period_end = state.status, state.period_end
    row.cancel_at_period_end, row.verified_at = state.cancel_at_period_end, state.observed_at
    row.error_code = None if state.price_id == policy.price_id else "unrecognized_price"
    row.next_attempt_at = now + timedelta(seconds=policy.max_snapshot_age_seconds // 2)
