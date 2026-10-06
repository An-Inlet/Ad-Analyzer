"""Shared optional rollout gate for customer mutation paths and workers."""

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ads.models import AdvertisingAccount
from app.billing.contracts import BillingPolicy
from app.billing.scope import configured_scope
from app.billing.service import require_entitlement
from app.settings import settings
from app.workspaces.models import WorkspaceIntegration


def policy() -> BillingPolicy:
    if not settings.billing_price_id:
        raise HTTPException(503, "commercial configuration unavailable")
    max_accounts = (
        settings.billing_live_max_accounts
        if settings.billing_provider_mode == "stripe_live"
        else settings.billing_max_accounts
    )
    if max_accounts is None:
        raise HTTPException(503, "commercial configuration unavailable")
    try:
        return BillingPolicy(price_id=settings.billing_price_id, max_accounts=max_accounts)
    except ValueError:
        raise HTTPException(503, "commercial configuration unavailable") from None


def paid_work(db: Session, wid: int, now: datetime) -> None:
    if settings.billing_provider_mode == "stripe_live":
        live_paid_work(db, wid, now)
        return
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
    # Configured runtime never falls back to pre-migration fixture rows.
    try:
        scope = configured_scope()
    except ValueError:
        from app.billing.scope import LEGACY_TEST_SCOPE

        if settings.billing_provider_mode != "disabled":
            raise HTTPException(503, "billing scope unavailable") from None
        scope = LEGACY_TEST_SCOPE
    require_entitlement(db, wid, policy(), now, account_count=count, scope=scope)


def live_paid_work(db: Session, wid: int, now: datetime) -> None:
    """Mandatory production gate: cannot be disabled through the legacy rollout flag."""
    try:
        scope = configured_scope()
    except ValueError:
        raise HTTPException(503, "live billing qualification unavailable") from None
    if scope.environment != "live" or not scope.qualified:
        raise HTTPException(503, "live billing qualification unavailable")
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
    require_entitlement(db, wid, policy(), now, account_count=count, scope=scope)
