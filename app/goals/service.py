"""Scoped goal state transitions. Callers authorize membership and commit."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.commerce.models import CommerceSnapshot
from app.commerce.reporting import measurement
from app.goals.models import Goal, GoalConfirmation, GoalCreation, GoalPreview, GoalRevision
from app.goals.schemas import ConfirmInput, GoalDefinition
from app.shopify.security import ShopifyError, utc


def create(
    db: Session,
    workspace_id: int,
    user_id: str,
    request_key: str,
    definition: GoalDefinition | None,
    now: datetime,
) -> Goal:
    fingerprint = hashlib.sha256(
        json.dumps(
            definition.model_dump(mode="json") if definition else None,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    identity = (workspace_id, user_id, request_key)
    receipt = db.get(GoalCreation, identity)
    if receipt is None:
        # SQLite's legacy driver does not start a transaction for SELECT/SAVEPOINT.
        # Ensure releasing our savepoint cannot commit ahead of the API transaction.
        if db.get_bind().dialect.name == "sqlite":
            connection = db.connection()
            driver = connection.connection.driver_connection
            assert driver is not None
            if not driver.in_transaction:
                connection.exec_driver_sql("BEGIN")
        try:
            # The unique receipt arbitrates concurrent attempts. Its losing savepoint
            # removes both goal and revision; no orphan or duplicate can commit.
            with db.begin_nested():
                item = Goal(id=uuid4().hex, workspace_id=workspace_id, revision=0)
                db.add(item)
                db.flush()
                revise(db, item, definition, user_id, now)
                receipt = GoalCreation(
                    workspace_id=workspace_id,
                    user_id=user_id,
                    request_key=request_key,
                    fingerprint=fingerprint,
                    goal_id=item.id,
                )
                db.add(receipt)
                db.flush()
        except IntegrityError:
            receipt = db.get(GoalCreation, identity)
            if receipt is None:
                raise
    if receipt.fingerprint != fingerprint:
        raise HTTPException(409, "creation key is bound to different input")
    return owned(db, workspace_id, receipt.goal_id)


def owned(db: Session, workspace_id: int, goal_id: str) -> Goal:
    item = db.scalar(
        select(Goal).where(Goal.id == goal_id, Goal.workspace_id == workspace_id).with_for_update()
    )
    if item is None:
        raise HTTPException(404, "goal not found")
    return item


def current(db: Session, goal: Goal) -> GoalRevision:
    item = db.get(GoalRevision, (goal.id, goal.revision))
    assert item is not None
    return item


def expect(goal: Goal, revision: int) -> None:
    if goal.revision != revision:
        raise HTTPException(409, "goal revision changed")


def revise(
    db: Session, goal: Goal, definition: GoalDefinition | None, editor: str, now: datetime
) -> GoalRevision:
    # Source existence/ownership is checked even for drafts. Data quality can be unavailable.
    if definition:
        from app.commerce.models import CommerceStore

        store = db.scalar(
            select(CommerceStore).where(
                CommerceStore.id == definition.store_id,
                CommerceStore.workspace_id == goal.workspace_id,
            )
        )
        if store is None:
            raise HTTPException(404, "measurement source unavailable")
        if (store.currency, store.time_zone) != (
            definition.target_window.currency,
            definition.target_window.time_zone,
        ):
            raise HTTPException(422, "measurement basis does not match store")
    goal.revision += 1
    goal.confirmed_preview_id = None
    revision = GoalRevision(
        goal_id=goal.id,
        workspace_id=goal.workspace_id,
        revision=goal.revision,
        definition=definition.model_dump(mode="json") if definition else None,
        editor_id=editor,
        created_at=now,
    )
    db.add(revision)
    db.flush()
    return revision


def baseline(
    db: Session, goal: Goal, definition: GoalDefinition, now: datetime, *, persist: bool = False
) -> dict[str, Any]:
    local_today = now.astimezone(ZoneInfo(definition.baseline_window.time_zone)).date()
    if definition.baseline_window.end > local_today:
        raise HTTPException(409, "historical baseline required")
    try:
        result = measurement(
            db,
            goal.workspace_id,
            definition.store_id,
            definition.baseline_window,
            now=now,
            snapshot=persist,
        )
    except ShopifyError:
        raise HTTPException(409, "measurement source unavailable") from None
    except ValueError:
        raise HTTPException(422, "measurement basis does not match store") from None
    if result["quality"] != "complete":
        raise HTTPException(409, {"code": "baseline_unavailable", "reasons": result["reasons"]})
    return result


def preview(db: Session, goal: Goal, now: datetime) -> GoalPreview:
    revision = current(db, goal)
    if revision.definition is None:
        raise HTTPException(409, "goal definition incomplete")
    definition = GoalDefinition.model_validate(revision.definition)
    if definition.deadline < now.astimezone(ZoneInfo(definition.target_window.time_zone)).date():
        raise HTTPException(409, "goal deadline has passed")
    result = baseline(db, goal, definition, now, persist=True)
    item = GoalPreview(
        id=uuid4().hex,
        goal_id=goal.id,
        revision=goal.revision,
        snapshot_id=result["snapshot_id"],
        created_at=now,
    )
    db.add(item)
    db.flush()
    return item


def assessment(db: Session, goal: Goal, now: datetime) -> str:
    if goal.confirmed_preview_id is None:
        return "draft"
    p = db.get(GoalPreview, goal.confirmed_preview_id)
    if p is None or p.snapshot_id is None or db.get(CommerceSnapshot, p.snapshot_id) is None:
        return "baseline_unavailable"
    try:
        baseline(db, goal, GoalDefinition.model_validate(current(db, goal).definition), now)
    except (HTTPException, ValueError):
        return "baseline_unavailable"
    return "confirmed"


def confirm(db: Session, goal: Goal, body: ConfirmInput, now: datetime, *, actor_id: str) -> None:
    expect(goal, body.expected_revision)
    receipt = db.get(GoalConfirmation, (goal.id, body.idempotency_key))
    if receipt is not None:
        if (receipt.revision, receipt.preview_id) != (body.expected_revision, body.preview_id):
            raise HTTPException(409, "idempotency conflict")
        return
    p = db.get(GoalPreview, body.preview_id)
    if p is None or (p.goal_id, p.revision) != (goal.id, goal.revision) or p.snapshot_id is None:
        raise HTTPException(409, "baseline preview unavailable")
    if not timedelta(0) <= now - utc(p.created_at) <= timedelta(minutes=15):
        raise HTTPException(409, "baseline preview expired")
    snap = db.get(CommerceSnapshot, p.snapshot_id)
    revision = current(db, goal)
    definition = GoalDefinition.model_validate(revision.definition)
    fresh = baseline(db, goal, definition, now)
    if definition.deadline < now.astimezone(ZoneInfo(definition.target_window.time_zone)).date():
        raise HTTPException(409, "goal deadline has passed")
    if snap is None or any(
        snap.result.get(k) != fresh.get(k)
        for k in (
            "store_id",
            "definition",
            "currency",
            "time_zone",
            "window",
            "revision",
            "source_watermark",
            "net_sales_micros",
            "quality",
        )
    ):
        raise HTTPException(409, "baseline changed; review a new preview")
    if goal.confirmed_preview_id is not None and goal.confirmed_preview_id != p.id:
        raise HTTPException(409, "revision already confirmed")
    if goal.confirmed_preview_id is None:
        goal.confirmed_preview_id, revision.confirmed_at = p.id, now
        revision.confirmed_by = actor_id
    # A second key for the same confirmed preview is a replay receipt, not a
    # new approval. Preserve the original customer and timestamp immutably.
    db.add(
        GoalConfirmation(
            goal_id=goal.id,
            request_key=body.idempotency_key,
            revision=goal.revision,
            preview_id=p.id,
        )
    )


def serialize(db: Session, goal: Goal, now: datetime | None = None) -> dict[str, Any]:
    revision = current(db, goal)
    preview = db.get(GoalPreview, goal.confirmed_preview_id) if goal.confirmed_preview_id else None
    snapshot = (
        db.get(CommerceSnapshot, preview.snapshot_id) if preview and preview.snapshot_id else None
    )
    return {
        "id": goal.id,
        "confirmed_preview_id": goal.confirmed_preview_id,
        "baseline_snapshot_id": snapshot.id if snapshot else None,
        "confirmed_at": revision.confirmed_at,
        "confirmed_by": revision.confirmed_by,
        "workspace_id": goal.workspace_id,
        "revision": goal.revision,
        "definition": revision.definition,
        "confirmation_recorded": goal.confirmed_preview_id is not None,
        "assessment": assessment(db, goal, now or datetime.now(UTC)),
        "spending_authorized": False,
        "aggressiveness_policy_validated": False,
    }
