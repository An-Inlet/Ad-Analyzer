"""Workspace-locked offer persistence; no customer-supplied commercial proof."""

from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.billing.models import BillingOfferBinding, WorkspaceBilling
from app.billing.offers import BoundOfferV1, OfferProfileV1, OfferQualificationV1, digest
from app.shopify.security import utc


def binding(db: Session, row: WorkspaceBilling, pointer: str) -> BoundOfferV1 | None:
    key = getattr(row, pointer)
    if key is None:
        return None
    saved = db.get(BillingOfferBinding, key)
    if saved is None:
        raise HTTPException(409, "commercial binding unavailable")
    try:
        profile = OfferProfileV1.model_validate(saved.profile)
        result = BoundOfferV1(
            id=saved.id,
            workspace_id=saved.workspace_id,
            checkout_key=saved.checkout_key,
            profile=profile,
            created_at=utc(saved.created_at),
        )
        if (
            saved.workspace_id != row.workspace_id
            or any(
                getattr(saved, key) != value or getattr(row, key) != value
                for key, value in profile.scope.columns().items()
            )
            or saved.profile_digest != digest(profile)
            or saved.binding_digest != digest(result)
        ):
            raise ValueError
        return result
    except ValueError:
        raise HTTPException(409, "commercial binding mismatch") from None


def install(
    db: Session, row: WorkspaceBilling, profile: OfferProfileV1, now: datetime
) -> BoundOfferV1:
    if row.checkout_key is None:
        raise HTTPException(409, "checkout request missing")
    if row.checkout_offer_binding_id is not None:
        raise HTTPException(409, "checkout offer already bound")
    result = BoundOfferV1(
        id=uuid4().hex,
        workspace_id=row.workspace_id,
        checkout_key=row.checkout_key,
        profile=profile,
        created_at=now,
    )
    db.add(
        BillingOfferBinding(
            id=result.id,
            workspace_id=result.workspace_id,
            **profile.scope.columns(),
            checkout_key=result.checkout_key,
            profile=profile.model_dump(mode="json"),
            profile_digest=digest(profile),
            binding_digest=digest(result),
            created_at=now,
        )
    )
    db.flush()
    row.checkout_offer_binding_id = result.id
    return result


def qualified(row: WorkspaceBilling, bound: BoundOfferV1, q: OfferQualificationV1) -> None:
    if (
        q.binding_id != bound.id
        or q.binding_digest != digest(bound)
        or q.profile_digest != digest(bound.profile)
        or q.scope != bound.profile.scope
        or q.customer_id != row.customer_id
        or q.subscription_id != row.subscription_id
        or q.price_id != row.price_id
        or q.product_id != bound.profile.product_id
        or q.currency != bound.profile.currency
        or q.amount_paid != bound.profile.unit_amount
        or q.status != row.status
        or q.cancel_at_period_end != row.cancel_at_period_end
        or row.period_end is None
        or q.period_end != utc(row.period_end)
        or row.verified_at is None
        or q.observed_at != utc(row.verified_at)
    ):
        raise HTTPException(409, "commercial qualification mismatch")
