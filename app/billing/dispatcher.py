"""Offline billing notification processing and freshness refresh; scheduler wiring is gated."""

from collections.abc import Callable
from datetime import datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.billing.contracts import BillingPolicy, BillingTransport
from app.billing.models import BillingEvent, WorkspaceBilling
from app.billing.service import reconcile, refresh, resolve_checkout
from app.workspaces.models import Workspace


def run(
    factory: Callable[[], Session],
    policy: BillingPolicy,
    transport: BillingTransport,
    now: datetime,
    limit: int = 10,
) -> dict[str, int]:
    with factory() as db:
        pending = list(
            db.execute(
                select(WorkspaceBilling.workspace_id, BillingEvent.id)
                .join(BillingEvent, BillingEvent.customer_id == WorkspaceBilling.customer_id)
                .join(Workspace, Workspace.id == WorkspaceBilling.workspace_id)
                .where(
                    Workspace.status == "active",
                    BillingEvent.state == "pending",
                    or_(
                        BillingEvent.next_attempt_at.is_(None), BillingEvent.next_attempt_at <= now
                    ),
                )
                .order_by(BillingEvent.received_at, BillingEvent.id)
                .limit(limit)
            ).all()
        )
        stale = list(
            db.scalars(
                select(WorkspaceBilling.workspace_id)
                .join(Workspace)
                .where(
                    Workspace.status == "active",
                    WorkspaceBilling.workspace_id.not_in([wid for wid, _ in pending]),
                    or_(
                        WorkspaceBilling.subscription_id.is_not(None),
                        WorkspaceBilling.checkout_id.is_not(None),
                    ),
                    or_(
                        WorkspaceBilling.next_attempt_at.is_(None),
                        WorkspaceBilling.next_attempt_at <= now,
                    ),
                    or_(
                        WorkspaceBilling.verified_at.is_(None),
                        WorkspaceBilling.verified_at
                        <= now - timedelta(seconds=policy.max_snapshot_age_seconds // 2),
                    ),
                )
                .order_by(
                    WorkspaceBilling.verified_at.asc().nulls_first(), WorkspaceBilling.workspace_id
                )
                .limit(limit)
            )
        )
    counts = {"events": 0, "refreshes": 0, "failed": 0}
    for wid, event_id in pending:
        with factory() as db:
            try:
                counts["events"] += int(reconcile(db, wid, event_id, policy, transport, now))
            except Exception:
                db.rollback()
                counts["failed"] += 1
    for wid in stale:
        with factory() as db:
            try:
                row = db.get(WorkspaceBilling, wid)
                if (
                    row is not None
                    and row.checkout_id is not None
                    and (
                        row.subscription_id is None
                        or row.status in {"canceled", "incomplete_expired"}
                    )
                ):
                    from app.billing.service import owned

                    row = owned(db, wid)
                    resolve_checkout(db, row, policy, transport, now)
                else:
                    refresh(db, wid, policy, transport, now)
                db.commit()
                counts["refreshes"] += 1
            except Exception:
                db.rollback()
                row = db.get(WorkspaceBilling, wid)
                if row is not None:
                    row.next_attempt_at = now + timedelta(minutes=1)
                    db.commit()
                counts["failed"] += 1
    return counts
