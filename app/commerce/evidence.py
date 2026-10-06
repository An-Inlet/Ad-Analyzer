"""Owned, terminal-only aggregate publications and source privacy fences.

Callers commit. No provider calls, order/customer identifiers, or maturity inference.
"""

import hashlib
import json
from datetime import UTC, datetime, time, timedelta
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.commerce.models import (
    CommerceEntry,
    CommerceEvidenceState,
    CommerceMeasurementPublication,
    CommerceOrder,
    CommerceStore,
    CommerceSuppression,
)
from app.shopify.security import ShopifyError, utc
from app.workspaces.models import Workspace


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def lock_workspace(db: Session, workspace_id: int, *, active: bool = False) -> Workspace:
    row = db.scalar(
        select(Workspace)
        .where(Workspace.id == workspace_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None or (active and row.status != "active"):
        raise ShopifyError("commerce_ownership_unavailable")
    return row


def state(db: Session, store: CommerceStore, now: datetime) -> CommerceEvidenceState:
    row = db.scalar(
        select(CommerceEvidenceState)
        .where(
            CommerceEvidenceState.store_id == store.id,
            CommerceEvidenceState.workspace_id == store.workspace_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None:
        row = CommerceEvidenceState(
            store_id=store.id,
            workspace_id=store.workspace_id,
            generation=1,
            privacy_epoch=1,
            publication_revision=0,
            updated_at=now,
        )
        db.add(row)
        db.flush()
    return row


def invalidate(
    db: Session,
    store: CommerceStore,
    now: datetime,
    *,
    rebind: bool = False,
    clear_history: bool = True,
) -> None:
    """Requires workspace/native/store fences; retains no old aggregate or digest."""
    from app.lifecycle.privacy import bump_workspace_export_revision

    bump_workspace_export_revision(db, store.workspace_id)
    fence = state(db, store, now)
    fence.privacy_epoch += 1
    if rebind:
        fence.generation += 1
    if clear_history:
        fence.history_from = None
    fence.updated_at = now
    db.execute(
        delete(CommerceMeasurementPublication).where(
            CommerceMeasurementPublication.store_id == store.id,
            CommerceMeasurementPublication.workspace_id == store.workspace_id,
        )
    )
    db.flush()


def workspace_privacy_stamp(db: Session, workspace_id: int) -> str:
    """Bounded-memory digest, including store-set changes; no locks or lazy writes.

    Capture in the export snapshot; compare from a fresh transaction at each
    delivery checkpoint. Not a promise to recall bytes already delivered.
    """
    result = hashlib.sha256(b"inlet.commerce-privacy-stamp.v1\0")
    query = (
        select(
            CommerceStore.id, CommerceEvidenceState.generation, CommerceEvidenceState.privacy_epoch
        )
        .outerjoin(
            CommerceEvidenceState,
            (CommerceEvidenceState.store_id == CommerceStore.id)
            & (CommerceEvidenceState.workspace_id == CommerceStore.workspace_id),
        )
        .where(CommerceStore.workspace_id == workspace_id)
        .order_by(CommerceStore.id)
    )
    for record in db.execute(query).yield_per(100):
        result.update(json.dumps(list(record), separators=(",", ":")).encode() + b"\n")
    return result.hexdigest()


def publish(
    db: Session,
    store: CommerceStore,
    start: datetime,
    end: datetime,
    now: datetime,
    api_version: str,
) -> CommerceMeasurementPublication:
    from app.commerce.ledger import DEFINITION, retention_floor
    from app.shopify.privacy_identity import markers

    lock_workspace(db, store.workspace_id, active=True)
    fence = state(db, store, now)
    floor = retention_floor(now, store.time_zone)
    if fence.history_from is None and utc(start) <= floor:
        fence.history_from = floor
    key = digest(
        [
            "inlet.commerce-completion.v1",
            store.id,
            fence.generation,
            fence.privacy_epoch,
            utc(start).isoformat(),
            utc(end).isoformat(),
            store.revision,
        ]
    )
    existing = db.scalar(
        select(CommerceMeasurementPublication).where(
            CommerceMeasurementPublication.store_id == store.id,
            CommerceMeasurementPublication.completion_digest == key,
        )
    )
    if existing:
        return existing
    zone = ZoneInfo(store.time_zone)
    first = floor.astimezone(zone).date()
    last = utc(end).astimezone(zone).date()  # current partial local day is not complete
    if not 0 <= (last - first).days <= 400:
        raise ShopifyError("commerce_publication_window_invalid")
    suppressed = (
        bool(markers(db, store))
        or db.scalar(
            select(CommerceSuppression.object_key)
            .where(
                CommerceSuppression.workspace_id == store.workspace_id,
                CommerceSuppression.shop_key == store.shop_key,
            )
            .limit(1)
        )
        is not None
    )
    unreconciled = (
        db.scalar(
            select(CommerceOrder.order_key)
            .where(CommerceOrder.store_id == store.id, CommerceOrder.quality != "complete")
            .limit(1)
        )
        is not None
    )
    totals: dict[str, int] = {}
    counts: dict[str, int] = {}
    for happened, amount in db.execute(
        select(CommerceEntry.happened_at, CommerceEntry.net_micros).where(
            CommerceEntry.store_id == store.id,
            CommerceEntry.happened_at >= floor,
            CommerceEntry.happened_at < end,
        )
    ).yield_per(1000):
        day_key = utc(happened).astimezone(zone).date().isoformat()
        totals[day_key] = totals.get(day_key, 0) + amount
        counts[day_key] = counts.get(day_key, 0) + 1
    partitions = []
    for offset in range((last - first).days):
        day = first + timedelta(days=offset)
        instant = datetime.combine(day, time.min, zone).astimezone(UTC)
        complete = (
            fence.history_from is not None
            and utc(fence.history_from) <= instant
            and not unreconciled
            and not suppressed
        )
        value = totals.get(day.isoformat(), 0) if complete else None
        partitions.append(
            {
                "day": day.isoformat(),
                "state": "suppressed"
                if suppressed
                else (
                    "missing"
                    if not complete
                    else "complete_zero"
                    if value == 0
                    else "complete_nonzero"
                ),
                "net_sales_micros": value,
                "entry_count": counts.get(day.isoformat(), 0) if complete else None,
            }
        )
    previous = db.scalar(
        select(CommerceMeasurementPublication)
        .where(CommerceMeasurementPublication.store_id == store.id)
        .order_by(CommerceMeasurementPublication.publication_revision.desc())
        .limit(1)
    )
    from app.optimization_candidates.invalidation import erase_source_candidates

    erase_source_candidates(db, store.workspace_id, store.id)
    fence.publication_revision += 1
    fence.updated_at = now
    payload = {
        "schema_version": "inlet.commerce-publication.v1",
        "workspace_id": store.workspace_id,
        "store_id": store.id,
        "generation": fence.generation,
        "privacy_epoch": fence.privacy_epoch,
        "publication_revision": fence.publication_revision,
        "source_revision": store.revision,
        "source": "shopify",
        "source_api_version": api_version,
        "source_range_semantics": "updated_at_inclusive",
        "source_window_start": utc(start).isoformat(),
        "source_window_end": utc(end).isoformat(),
        "source_watermark": utc(end).isoformat(),
        "as_of": utc(now).isoformat(),
        "definition": DEFINITION,
        "definition_digest": digest(DEFINITION),
        "currency": store.currency,
        "time_zone": store.time_zone,
        "unit": "monetary_micros",
        "grain": "store_local_day",
        "attribution": "not_applicable_store_total",
        "maturity": "unavailable",
        "comparison_reasons": ["maturity_policy_unavailable"],
        "partitions": partitions,
        "predecessor_digest": previous.manifest_digest if previous else None,
        "correction_status": "settled_as_of" if not unreconciled else "unknown",
    }
    row = CommerceMeasurementPublication(
        id=uuid4().hex,
        workspace_id=store.workspace_id,
        store_id=store.id,
        generation=fence.generation,
        privacy_epoch=fence.privacy_epoch,
        publication_revision=fence.publication_revision,
        source_revision=store.revision,
        source_window_start=start,
        source_window_end=end,
        published_at=now,
        earliest_source_day=first,
        completion_digest=key,
        manifest_digest=digest(payload),
        manifest=payload,
    )
    db.add(row)
    db.flush()
    return row


def read_publication(
    db: Session,
    workspace_id: int,
    store_id: str,
    publication_id: str | None = None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    from app.commerce.ledger import lock_store, retention_floor

    lock_workspace(db, workspace_id, active=True)
    store = lock_store(db, store_id, workspace_id)
    fence = db.get(CommerceEvidenceState, store.id)
    query = select(CommerceMeasurementPublication).where(
        CommerceMeasurementPublication.workspace_id == workspace_id,
        CommerceMeasurementPublication.store_id == store.id,
    )
    if publication_id is not None:
        query = query.where(CommerceMeasurementPublication.id == publication_id)
    row = db.scalar(
        query.order_by(CommerceMeasurementPublication.publication_revision.desc()).limit(1)
    )
    if (
        row is None
        or fence is None
        or (row.generation, row.privacy_epoch) != (fence.generation, fence.privacy_epoch)
    ):
        raise ShopifyError("commerce_publication_unavailable")
    evaluated_at = utc(now or datetime.now(UTC))
    if (
        row.earliest_source_day
        < retention_floor(evaluated_at, store.time_zone)
        .astimezone(ZoneInfo(store.time_zone))
        .date()
    ):
        raise ShopifyError("commerce_publication_outside_retention")
    if digest(row.manifest) != row.manifest_digest:
        raise ShopifyError("commerce_publication_invalid")
    return {
        "publication_id": row.id,
        "manifest_digest": row.manifest_digest,
        "manifest": json.loads(json.dumps(row.manifest)),
        "import_in_progress": store.window_end is not None,
        "comparison_available": False,
        "stale_source": evaluated_at - utc(row.source_window_end) > timedelta(hours=24),
    }
