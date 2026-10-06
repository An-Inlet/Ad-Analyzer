"""All billing identity resolution includes immutable provider/environment/merchant scope."""

from typing import Any

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.billing.models import BillingEvent, WorkspaceBilling
from app.billing.scope import BillingScopeV1


def billing(db: Session, wid: int, scope: BillingScopeV1) -> WorkspaceBilling | None:
    return db.get(WorkspaceBilling, scope.key(wid), populate_existing=True)


def event(db: Session, eid: str, scope: BillingScopeV1) -> BillingEvent | None:
    return db.get(BillingEvent, scope.key(eid), populate_existing=True)


def scoped(model: Any, scope: BillingScopeV1) -> Any:
    return and_(*(getattr(model, key) == value for key, value in scope.columns().items()))


def customer_join() -> Any:
    return and_(
        WorkspaceBilling.customer_id == BillingEvent.customer_id,
        WorkspaceBilling.provider == BillingEvent.provider,
        WorkspaceBilling.environment == BillingEvent.environment,
        WorkspaceBilling.merchant_account_id == BillingEvent.merchant_account_id,
    )


def transport_scope(transport: object) -> BillingScopeV1:
    # Compatibility is explicitly limited to historical test/fixture transports.
    # A live implementation without a qualified immutable scope is unavailable.
    from fastapi import HTTPException

    from app.billing.scope import LEGACY_TEST_SCOPE

    value = getattr(transport, "scope", None)
    if value is None and getattr(transport, "mode", None) in {"fixture", "stripe_test"}:
        return LEGACY_TEST_SCOPE
    if not isinstance(value, BillingScopeV1):
        raise HTTPException(503, "billing identity unavailable")
    if (getattr(transport, "mode", None) == "stripe_live") != (value.environment == "live"):
        raise HTTPException(503, "billing identity mode mismatch")
    return value
