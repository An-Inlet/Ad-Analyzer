"""Bounded receipt refresh from original bindings, independent of current offers."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.billing import offer_bindings, repository
from app.billing.contracts import CheckoutState, SubscriptionState
from app.billing.models import BillingEvent, WorkspaceBilling
from app.billing.offers import BoundOfferV1, digest
from app.billing.receipt_reader import BillingReceiptReader
from app.billing.scope import BillingScopeV1
from app.workspaces.models import Workspace


@dataclass(frozen=True)
class Original:
    workspace_id: int
    customer_id: str
    subscription_id: str | None
    checkout_id: str | None
    checkout_key: str | None
    bound: BoundOfferV1
    observation: tuple[str, ...]


def original(db: Session, wid: int, scope: BillingScopeV1) -> Original | None:
    workspace = db.scalar(
        select(Workspace)
        .where(Workspace.id == wid)
        .with_for_update(key_share=True)
        .execution_options(populate_existing=True)
    )
    if workspace is None or workspace.status != "active":
        return None
    row = repository.billing(db, wid, scope)
    if row is None or row.customer_id is None:
        return None
    bound = offer_bindings.binding(
        db,
        row,
        "subscription_offer_binding_id" if row.subscription_id else "checkout_offer_binding_id",
    )
    if bound is None or (row.subscription_id is None and row.checkout_id is None):
        return None
    if row.subscription_id is None and bound.checkout_key != row.checkout_key:
        raise ValueError("original checkout binding changed")
    observation = tuple(
        str(getattr(row, field))
        for field in (
            "status",
            "price_id",
            "period_end",
            "verified_at",
            "next_attempt_at",
            "error_code",
            "qualification_digest",
            "checkout_offer_binding_id",
            "subscription_offer_binding_id",
        )
    )
    return Original(
        wid,
        row.customer_id,
        row.subscription_id,
        row.checkout_id,
        row.checkout_key,
        bound,
        observation,
    )


def read(
    reader: BillingReceiptReader, saved: Original, now: datetime
) -> tuple[SubscriptionState | None, CheckoutState | None]:
    sid = saved.subscription_id
    checkout: CheckoutState | None = None
    if sid is None:
        if saved.checkout_id is None:
            raise ValueError("unknown checkout remains unresolved")
        checkout = reader.checkout_state_bound(
            saved.bound, saved.customer_id, saved.checkout_id, now
        )
        if (
            checkout.id != saved.checkout_id
            or checkout.customer_id != saved.customer_id
            or checkout.scope != reader.scope
            or checkout.binding_digest != digest(saved.bound)
            or not now - timedelta(seconds=30) <= checkout.observed_at <= now
        ):
            raise ValueError("original checkout mismatch")
        if checkout.status != "complete":
            if checkout.subscription_id is not None:
                raise ValueError("checkout has unresolved subscription")
            return None, checkout
        sid = checkout.subscription_id
    if sid is None:
        raise ValueError("subscription identity unavailable")
    state = reader.current_bound(saved.bound, saved.customer_id, sid, now)
    if (
        state.customer_id != saved.customer_id
        or state.subscription_id != sid
        or state.scope != reader.scope
        or state.binding_digest != digest(saved.bound)
        or not now - timedelta(seconds=30) <= state.observed_at <= now
    ):
        raise ValueError("original subscription mismatch")
    if state.status == "active" and state.qualification is None:
        raise ValueError("paid original offer proof unavailable")
    return state, checkout


def run(
    factory: Callable[[], Session],
    reader: BillingReceiptReader,
    *,
    limit: int = 10,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> dict[str, int]:
    if type(limit) is not int or not 1 <= limit <= 100 or not reader.scope.qualified:
        raise ValueError("invalid receipt scope or bound")
    from app.lifecycle.billing_receipts import retain_pending

    retain_pending(factory, limit)
    now = clock()
    with factory() as db:
        candidates = list(
            db.scalars(
                select(WorkspaceBilling.workspace_id)
                .join(Workspace)
                .where(
                    Workspace.status == "active",
                    repository.scoped(WorkspaceBilling, reader.scope),
                    or_(
                        WorkspaceBilling.subscription_id.is_not(None),
                        WorkspaceBilling.checkout_id.is_not(None),
                    ),
                    or_(
                        WorkspaceBilling.next_attempt_at.is_(None),
                        WorkspaceBilling.next_attempt_at <= now,
                    ),
                )
                .order_by(
                    WorkspaceBilling.verified_at.asc().nulls_first(), WorkspaceBilling.workspace_id
                )
                .limit(limit)
            )
        )
    counts = {"refreshes": 0, "failed": 0, "changed": 0}
    for wid in candidates:
        saved: Original | None = None
        try:
            with factory() as db:
                saved = original(db, wid, reader.scope)
                db.commit()
            if saved is None:
                continue
            state, checkout = read(reader, saved, clock())
            with factory() as db:
                current = original(db, wid, reader.scope)
                now = clock()  # Fresh after the final ownership lock, not before provider IO.
                if current != saved:
                    counts["changed"] += 1
                    continue
                row = repository.billing(db, wid, reader.scope)
                assert row is not None
                if state is not None:
                    if not now - timedelta(seconds=30) <= state.observed_at <= now:
                        raise ValueError("original evidence stale after read")
                    row.subscription_id, row.price_id = state.subscription_id, state.price_id
                    row.status, row.period_end = state.status, state.period_end
                    row.cancel_at_period_end, row.verified_at = (
                        state.cancel_at_period_end,
                        state.observed_at,
                    )
                    row.subscription_offer_binding_id = saved.bound.id
                    row.qualification, row.qualification_digest = None, None
                    if state.qualification is not None:
                        offer_bindings.qualified(row, saved.bound, state.qualification)
                        row.qualification = state.qualification.model_dump(mode="json")
                        row.qualification_digest = digest(state.qualification)
                    row.error_code = None
                    events = db.scalars(
                        select(BillingEvent)
                        .where(
                            repository.scoped(BillingEvent, reader.scope),
                            BillingEvent.customer_id == saved.customer_id,
                            BillingEvent.subscription_id == state.subscription_id,
                            BillingEvent.state == "pending",
                            BillingEvent.received_at <= state.observed_at,
                        )
                        .order_by(BillingEvent.received_at, BillingEvent.id)
                        .limit(limit)
                    )
                    for event in events:
                        event.state, event.processed_at, event.error_code = "processed", now, None
                        event.next_attempt_at = None
                elif checkout is not None:
                    if not now - timedelta(seconds=30) <= checkout.observed_at <= now:
                        raise ValueError("original checkout stale after read")
                    # Retain original attempt identity; this lane never starts/replays a purchase.
                    row.error_code = "checkout_expired" if checkout.status == "expired" else None
                row.next_attempt_at = now + timedelta(seconds=150)
                db.commit()
                counts["refreshes"] += 1
        except Exception:
            counts["failed"] += 1
            if saved is not None:
                try:
                    with factory() as db:
                        if original(db, wid, reader.scope) == saved:
                            row = repository.billing(db, wid, reader.scope)
                            assert row is not None
                            row.error_code = "commercial_qualification_unavailable"
                            row.next_attempt_at = clock() + timedelta(minutes=1)
                            db.commit()
                except Exception:
                    # A now-invalid/replaced binding is not authority to overwrite it.
                    pass
    return counts
