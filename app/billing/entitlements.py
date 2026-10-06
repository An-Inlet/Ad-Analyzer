"""Shared optional rollout gate for customer mutation paths and workers."""

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ads.models import AdvertisingAccount
from app.billing.contracts import BillingPolicy
from app.billing.service import require_entitlement
from app.settings import settings
from app.workspaces.models import WorkspaceIntegration


def policy() -> BillingPolicy:
    if not settings.billing_price_id:
        raise HTTPException(503, "commercial configuration unavailable")
    try:
        return BillingPolicy(
            price_id=settings.billing_price_id, max_accounts=settings.billing_max_accounts
        )
    except ValueError:
        raise HTTPException(503, "commercial configuration unavailable") from None


def paid_work(db: Session, wid: int, now: datetime) -> None:
    if not settings.billing_required:
        return
    from app.mandates.service import workspace_lock

    workspace_lock(db, wid)
    count = (
        db.scalar(
            select(func.count())
            .select_from(AdvertisingAccount)
            .join(WorkspaceIntegration, AdvertisingAccount.connection_id == WorkspaceIntegration.id)
            .where(AdvertisingAccount.workspace_id == wid, WorkspaceIntegration.status == "active")
        )
        or 0
    )
    require_entitlement(db, wid, policy(), now, account_count=count)
