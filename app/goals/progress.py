"""Read-only, current-revision closed-day sales; no persisted snapshots or authority."""

from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.commerce.ledger import lock_store, retention_floor
from app.commerce.reporting import MeasurementWindow, measurement
from app.customers.access import CustomerPrincipal, guard_customer_mutation, lock_customer_mutation
from app.customers.identity import IdentityProvider
from app.goals import service
from app.goals.progress_contracts import ClosedDayCoverageV1, GoalSalesProgressV1
from app.goals.schemas import GoalDefinition
from app.lifecycle.privacy import database_utc_now
from app.publication.contracts import fingerprint
from app.shopify.security import ShopifyError, utc

READ_ROLES = frozenset({"owner", "admin", "analyst", "viewer"})


def boundary(day: date, zone: ZoneInfo) -> datetime:
    local = datetime.combine(day, time.min)
    first = local.replace(tzinfo=zone, fold=0).astimezone(UTC)
    second = local.replace(tzinfo=zone, fold=1).astimezone(UTC)
    if first != second or first.astimezone(zone).replace(tzinfo=None) != local:
        raise ValueError("ambiguous_local_boundary")
    return first


def read_goal_progress(
    db: Session,
    principal: CustomerPrincipal,
    provider: IdentityProvider,
    workspace_id: int,
    goal_id: str,
    expected_revision: int,
    *,
    clock: Callable[[], datetime],
) -> GoalSalesProgressV1:
    lock_customer_mutation(db, principal, workspace_id, provider, allowed_roles=READ_ROLES)
    goal = service.owned(db, workspace_id, goal_id)
    db.refresh(goal)
    service.expect(goal, expected_revision)
    revision = service.current(db, goal)
    db.refresh(revision)
    now = max(utc(clock()), database_utc_now(db))
    values: dict[str, Any] = dict(
        workspace_id=workspace_id,
        goal_id=goal.id,
        revision=goal.revision,
        definition_digest=None,
        status="unavailable",
        target_window=None,
        target_micros=None,
        store_id=None,
        currency=None,
        time_zone=None,
        coverage=None,
        net_sales_micros=None,
        source_watermark=None,
        source_revision=None,
        import_in_progress=None,
        as_of=now,
        reasons=(),
    )

    def result(*reasons: str, status: str = "unavailable") -> GoalSalesProgressV1:
        guard_customer_mutation(db, principal, workspace_id, allowed_roles=READ_ROLES)
        final = max(utc(clock()), database_utc_now(db))
        if principal.session.expires_at <= final.timestamp():
            raise HTTPException(401, "customer authentication required")
        final_reasons = list(reasons)
        if values["net_sales_micros"] is not None:
            if not timedelta(0) <= final - values["source_watermark"] <= timedelta(hours=24):
                final_reasons.append("stale_source")
            if values["coverage"].starts_at < retention_floor(final, values["time_zone"]):
                final_reasons.append("outside_retention")
            if final_reasons:
                values["net_sales_micros"] = None
                status = "unavailable"
        values.update(status=status, reasons=tuple(dict.fromkeys(final_reasons)), as_of=final)
        return GoalSalesProgressV1.model_validate(values)

    if revision.definition is None:
        return result("goal_definition_unavailable")
    definition = GoalDefinition.model_validate(revision.definition)
    window = definition.target_window
    values.update(
        definition_digest=fingerprint(
            "inlet.goal-progress-definition.v1", definition.model_dump(mode="json")
        ),
        target_window=window,
        target_micros=definition.target_micros,
        store_id=definition.store_id,
        currency=window.currency,
        time_zone=window.time_zone,
    )
    if revision.confirmed_at is None:
        return result("goal_not_confirmed")
    try:
        store = lock_store(db, definition.store_id, workspace_id)
    except ShopifyError:
        return result("source_unavailable")
    if (store.currency, store.time_zone) != (window.currency, window.time_zone):
        return result("measurement_basis_changed")
    # All blocking locks and provider identity checks precede the effective clock.
    now = max(utc(clock()), database_utc_now(db))
    zone = ZoneInfo(window.time_zone)
    today = now.astimezone(zone).date()
    watermark = utc(store.last_sync_at) if store.last_sync_at else None
    values.update(
        source_watermark=watermark,
        source_revision=store.revision,
        import_in_progress=store.window_end is not None,
    )
    if today < window.start:
        return result("no_closed_days", status="not_started")
    if watermark is None:
        return result("missing_history")
    end = min(window.end, today, watermark.astimezone(zone).date())
    if end <= window.start:
        return result("no_closed_days")
    try:
        start_at, end_at = boundary(window.start, zone), boundary(end, zone)
    except ValueError:
        return result("ambiguous_local_boundary")
    prefix = MeasurementWindow(
        start=window.start,
        end=end,
        time_basis="cumulative",
        currency=window.currency,
        time_zone=window.time_zone,
    )
    measured = measurement(db, workspace_id, store.id, prefix, now=now, snapshot=False)
    values["coverage"] = ClosedDayCoverageV1(
        starts_on=window.start,
        ends_on_exclusive=end,
        starts_at=start_at,
        ends_at_exclusive=end_at,
        closed_day_count=(end - window.start).days,
        extent="full_window_as_of" if end == window.end else "partial_period",
    )
    guard_customer_mutation(db, principal, workspace_id, allowed_roles=READ_ROLES)
    final = max(utc(clock()), database_utc_now(db))
    reasons = list(measured["reasons"])
    if not timedelta(0) <= final - watermark <= timedelta(hours=24):
        reasons.append("stale_source")
    if start_at < retention_floor(final, store.time_zone):
        reasons.append("outside_retention")
    if reasons:
        return result(*reasons)
    values["net_sales_micros"] = measured["net_sales_micros"]
    return result(status="available_as_of")
