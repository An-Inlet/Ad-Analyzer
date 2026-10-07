"""Raw-body signature validation and minimal event projection, no entitlement from snapshots."""

import hashlib
import hmac
import json
import re
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.billing.models import BillingEvent
from app.billing.scope import LEGACY_TEST_SCOPE, BillingScopeV1


def verify(
    payload: bytes,
    signature: str,
    secret: str,
    now: datetime,
    *,
    scope: BillingScopeV1 = LEGACY_TEST_SCOPE,
) -> dict[str, Any]:
    if len(payload) > 262144 or len(signature) > 2048 or not secret:
        raise HTTPException(400, "invalid billing event")
    parts: dict[str, list[str]] = {}
    for part in signature.split(","):
        key, sep, value = part.partition("=")
        if sep:
            parts.setdefault(key, []).append(value)
    try:
        stamps = parts["t"]
        if len(stamps) != 1:
            raise ValueError
        timestamp = int(stamps[0])
        if abs(now.timestamp() - timestamp) > 300:
            raise ValueError
        expected = hmac.new(
            secret.encode(), stamps[0].encode() + b"." + payload, hashlib.sha256
        ).hexdigest()
        if not any(hmac.compare_digest(expected, value) for value in parts.get("v1", [])):
            raise ValueError
        event = json.loads(payload)
        if not isinstance(event, dict) or event.get("livemode") is not (
            scope.environment == "live"
        ):
            raise ValueError
        if event.get("account") is not None and event["account"] != scope.merchant_account_id:
            raise ValueError
        return event
    except (KeyError, ValueError, TypeError):
        raise HTTPException(400, "invalid billing event") from None


def receive(
    db: Session,
    payload: bytes,
    signature: str,
    secret: str,
    now: datetime,
    *,
    scope: BillingScopeV1 = LEGACY_TEST_SCOPE,
) -> bool:
    event = verify(payload, signature, secret, now, scope=scope)
    supported = {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
        "checkout.session.completed",
    }
    if event.get("type") not in supported:
        return False
    try:
        obj = event["data"]["object"]
        eid, customer = event["id"], obj["customer"]
        subscription = (
            obj["subscription"] if event["type"] == "checkout.session.completed" else obj["id"]
        )
        for value, prefix in ((eid, "evt"), (customer, "cus"), (subscription, "sub")):
            if (
                not isinstance(value, str)
                or re.fullmatch(prefix + r"_[A-Za-z0-9_]{1,128}", value) is None
            ):
                raise ValueError
    except (KeyError, ValueError, TypeError):
        raise HTTPException(400, "invalid billing resource") from None
    digest = hashlib.sha256(payload).hexdigest()
    existing = db.get(BillingEvent, scope.key(eid))
    if existing is not None:
        if existing.body_hash != digest:
            raise HTTPException(409, "conflicting billing event")
        return False
    try:
        with db.begin_nested():
            db.add(
                BillingEvent(
                    id=eid,
                    **scope.columns(),
                    body_hash=digest,
                    customer_id=customer,
                    subscription_id=subscription,
                    event_type=event["type"],
                    received_at=now,
                    state="pending",
                )
            )
            db.flush()
    except IntegrityError:
        existing = db.get(BillingEvent, scope.key(eid), populate_existing=True)
        if existing is None or existing.body_hash != digest:
            raise HTTPException(409, "conflicting billing event") from None
        return False
    db.commit()
    return True
