"""Closing-workspace billing inbox lane; retain notices without provider calls/entitlements."""

from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.billing.models import BillingEvent, WorkspaceBilling
from app.lifecycle.models import LifecycleRequest
from app.workspaces.models import Workspace


def retain_pending(factory: Callable[[], Session], limit: int = 10) -> int:
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("invalid closure inbox bound")
    with factory() as db:
        candidates = list(
            db.execute(
                select(WorkspaceBilling.workspace_id, BillingEvent.id)
                .join(BillingEvent, BillingEvent.customer_id == WorkspaceBilling.customer_id)
                .join(Workspace, Workspace.id == WorkspaceBilling.workspace_id)
                .where(Workspace.status == "closing", BillingEvent.state == "pending")
                .order_by(BillingEvent.received_at, BillingEvent.id)
                .limit(limit)
            )
        )
    retained = 0
    for wid, event_id in candidates:
        with factory() as db:
            workspace = db.scalar(select(Workspace).where(Workspace.id == wid).with_for_update())
            if workspace is None or workspace.status != "closing":
                continue
            request = db.scalar(
                select(LifecycleRequest.id)
                .where(
                    LifecycleRequest.workspace_id == wid,
                    LifecycleRequest.operation == "close",
                    LifecycleRequest.state == "blocked",
                )
                .limit(1)
            )
            billing = db.get(WorkspaceBilling, wid)
            event = db.scalar(
                select(BillingEvent).where(BillingEvent.id == event_id).with_for_update()
            )
            if (
                request is None
                or billing is None
                or event is None
                or event.state != "pending"
                or event.customer_id != billing.customer_id
            ):
                continue
            event.state, event.error_code = "closure_pending", "closure_requires_reconciliation"
            event.next_attempt_at = None
            db.commit()
            retained += 1
    return retained
