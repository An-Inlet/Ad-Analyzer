"""Workspace billing ownership and canonical-state entitlement reconciliation."""

import re
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.billing.contracts import (
    BillingManagementTransport,
    BillingPolicy,
    BillingTransport,
    SubscriptionState,
    UnavailableBilling,
)
from app.billing.models import BillingEvent, WorkspaceBilling
from app.billing.stripe import BillingReconciliationRequired
from app.mandates.service import workspace_lock
from app.shopify.security import utc


def ready(transport: BillingTransport) -> None:
    if isinstance(transport, UnavailableBilling) or transport.mode not in {
        "fixture",
        "stripe_test",
    }:
        raise HTTPException(503, "billing unavailable")


def owned(db: Session, wid: int, now: datetime | None = None) -> WorkspaceBilling:
    workspace_lock(db, wid)
    row = db.get(WorkspaceBilling, wid, populate_existing=True)
    if row is None:
        row = WorkspaceBilling(
            workspace_id=wid,
            customer_request_key=f"{int((now or datetime.now(UTC)).timestamp())}_{uuid4().hex}",
        )
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
    *,
    _state_retries: int = 0,
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
    row = owned(db, wid, now)
    if row.status in {"active", "trialing", "past_due", "unpaid", "paused", "incomplete"}:
        raise HTTPException(409, "existing subscription requires billing management")
    key, customer = row.customer_request_key, row.customer_id
    db.commit()  # Durable idempotency key exists before the provider boundary.
    if customer is None:
        try:
            customer = transport.customer(wid, key)
        except BillingReconciliationRequired:
            raise HTTPException(
                409, "billing customer recovery unresolved; retry reconciliation"
            ) from None
        except Exception:
            raise HTTPException(502, "billing customer pending; retry safely") from None
        if re.fullmatch(r"cus_[A-Za-z0-9_]{1,128}", customer) is None:
            raise HTTPException(502, "billing customer unavailable")
        row = owned(db, wid)
        if row.customer_id is not None and row.customer_id != customer:
            raise HTTPException(409, "billing customer conflict")
        row.customer_id = customer
        db.commit()
    row = owned(db, wid, now)
    if row.status in {"active", "trialing", "past_due", "unpaid", "paused", "incomplete"}:
        raise HTTPException(409, "existing subscription requires billing management")
    if row.checkout_id is not None:
        outcome = resolve_checkout(db, row, policy, transport, now)
        resolved_identity = (
            row.customer_id,
            row.checkout_key,
            row.checkout_id,
            row.subscription_id,
        )
        db.commit()
        # Canonical lookup committed and released the lock. Another caller may
        # already have installed a replacement: reload before retiring anything.
        row = owned(db, wid, now)
        if (
            row.customer_id,
            row.checkout_key,
            row.checkout_id,
            row.subscription_id,
        ) != resolved_identity:
            db.rollback()
            if _state_retries >= 2:
                raise HTTPException(409, "checkout changed; retry current billing state")
            return checkout(
                db, wid, policy, transport, return_url, now, _state_retries=_state_retries + 1
            )
        if outcome == "complete":
            if row.status not in {"canceled", "incomplete_expired"}:
                raise HTTPException(409, "checkout completed; subscription reconciled")
            # A completed checkout may be retired only after its subscription was
            # read back as terminal, never because its URL expiry elapsed.
            row.checkout_key, row.checkout_id, row.checkout_url, row.checkout_expires_at = (
                None,
                None,
                None,
                None,
            )
            # Retirement and installation of the new durable key share this
            # locked transaction; there must be no commit in between.
        if outcome == "open":
            if row.checkout_price != policy.price_id:
                raise HTTPException(409, "checkout already pending for another plan")
            if (
                not row.checkout_url
                or not row.checkout_expires_at
                or utc(row.checkout_expires_at) <= now
            ):
                raise HTTPException(409, "checkout still unresolved; retry reconciliation")
            return {"mode": transport.mode, "url": row.checkout_url, "id": row.checkout_id}
        # Only canonical expired/no-subscription proof permits a new idempotency key.
        row = owned(db, wid)
    if row.checkout_key is None:
        row.checkout_key, row.checkout_price = (
            f"{int(now.timestamp())}_{uuid4().hex}",
            policy.price_id,
        )
    if row.checkout_price != policy.price_id:
        raise HTTPException(409, "pending checkout must be reconciled")
    checkout_key = row.checkout_key
    db.commit()
    try:
        result = transport.checkout(customer, policy.price_id, checkout_key, return_url)
    except BillingReconciliationRequired:
        raise HTTPException(409, "checkout recovery unresolved; retry reconciliation") from None
    except Exception:
        raise HTTPException(502, "checkout pending; retry safely") from None
    if result.url is not None:
        location = urlsplit(result.url)
        if (
            location.scheme != "https"
            or location.netloc != "checkout.stripe.com"
            or location.username
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
    db.commit()  # Retain the recovered provider ID even if its URL has expired.
    if result.expires_at <= now or result.url is None:
        row = owned(db, wid)
        outcome = resolve_checkout(db, row, policy, transport, now)
        db.commit()
        raise HTTPException(409, "checkout " + outcome + "; retry from current billing state")
    return {"mode": transport.mode, "url": result.url, "id": result.id}


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
    try:
        target = event.subscription_id
        if row.subscription_id is not None and row.subscription_id != target:
            notified = verified_current(transport, row.customer_id, target, now)
            if notified.status in {"canceled", "incomplete_expired"}:
                # Delayed events for a terminal subscription cannot replace a
                # current purchase. Read the current purchase before acknowledging.
                target = row.subscription_id
            else:
                outcome = resolve_checkout(db, row, policy, transport, now)
                if outcome != "complete" or row.subscription_id != target:
                    raise HTTPException(409, "subscription identity requires reconciliation")
        refresh(db, wid, policy, transport, now, subscription_id=target)
    except HTTPException:
        event.error_code = "provider_read_unavailable"
        event.next_attempt_at = now + timedelta(minutes=1)
        row.next_attempt_at = event.next_attempt_at
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
    state = verified_current(transport, row.customer_id, subscription_id, now)
    row.subscription_id, row.price_id = state.subscription_id, state.price_id
    row.status, row.period_end = state.status, state.period_end
    row.cancel_at_period_end, row.verified_at = state.cancel_at_period_end, state.observed_at
    row.error_code = None if state.price_id == policy.price_id else "unrecognized_price"
    row.next_attempt_at = now + timedelta(seconds=policy.max_snapshot_age_seconds // 2)


def resolve_checkout(
    db: Session,
    row: WorkspaceBilling,
    policy: BillingPolicy,
    transport: BillingTransport,
    now: datetime,
) -> str:
    if row.checkout_id is None or row.customer_id is None:
        raise HTTPException(409, "checkout identity unavailable")
    try:
        state = transport.checkout_state(row.customer_id, row.checkout_id, now)
    except Exception:
        raise HTTPException(502, "checkout reconciliation unavailable") from None
    if (
        state.id != row.checkout_id
        or state.customer_id != row.customer_id
        or state.livemode
        or not now - timedelta(seconds=30) <= state.observed_at <= now
    ):
        raise HTTPException(409, "checkout identity mismatch")
    if state.status == "expired":
        if state.subscription_id is not None:
            raise HTTPException(409, "expired checkout has unresolved subscription")
        row.checkout_key, row.checkout_id, row.checkout_url, row.checkout_expires_at = (
            None,
            None,
            None,
            None,
        )
    elif state.status == "complete":
        if state.subscription_id is None:
            raise HTTPException(409, "completed checkout subscription unavailable")
        if row.subscription_id is not None and row.subscription_id != state.subscription_id:
            # Verify the old contract is terminal before adopting the new session's
            # subscription. A browser/event identifier alone cannot replace ownership.
            refresh(db, row.workspace_id, policy, transport, now)
            if row.status not in {"canceled", "incomplete_expired"}:
                raise HTTPException(409, "previous subscription is not terminal")
            previous_id = row.subscription_id
            row.subscription_id = None
            try:
                refresh(
                    db,
                    row.workspace_id,
                    policy,
                    transport,
                    now,
                    subscription_id=state.subscription_id,
                )
            except Exception:
                row.subscription_id = previous_id
                raise
        else:
            refresh(
                db, row.workspace_id, policy, transport, now, subscription_id=state.subscription_id
            )
    row.next_attempt_at = now + timedelta(seconds=policy.max_snapshot_age_seconds // 2)
    return state.status


def management(
    db: Session,
    wid: int,
    transport: BillingTransport,
    configuration_id: str,
    return_url: str,
    now: datetime,
) -> dict[str, str]:
    ready(transport)
    if not isinstance(transport, BillingManagementTransport):
        raise HTTPException(503, "billing management unavailable")
    location = urlsplit(return_url)
    if (
        location.scheme != "https"
        or not location.hostname
        or location.username
        or location.fragment
        or not re.fullmatch(r"bpc_[A-Za-z0-9_]{1,128}", configuration_id)
    ):
        raise HTTPException(503, "billing management configuration unavailable")
    row = owned(db, wid, now)
    if row.customer_id is None:
        raise HTTPException(409, "billing customer unavailable")
    customer = row.customer_id
    # A portal session creates no subscription or charge. Each request gets its
    # own short-lived session; provider-side subscription changes reconcile later.
    db.commit()
    try:
        url = transport.portal(
            customer, configuration_id, return_url, f"{int(now.timestamp())}_{uuid4().hex}"
        )
    except Exception:
        raise HTTPException(502, "billing management unavailable") from None
    location = urlsplit(url)
    if location.scheme != "https" or location.netloc != "billing.stripe.com":
        raise HTTPException(502, "billing management location unavailable")
    return {"mode": transport.mode, "url": url}


def verified_current(
    transport: BillingTransport, customer_id: str, subscription_id: str, now: datetime
) -> SubscriptionState:
    try:
        state = transport.current(customer_id, subscription_id, now)
    except Exception:
        raise HTTPException(502, "billing verification unavailable") from None
    if (
        state.customer_id != customer_id
        or state.subscription_id != subscription_id
        or state.observed_at < now - timedelta(seconds=30)
        or state.observed_at > now
        or state.livemode
    ):
        raise HTTPException(409, "billing verification mismatch")
    return state
