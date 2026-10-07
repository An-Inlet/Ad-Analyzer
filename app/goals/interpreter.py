"""Offline-only injectable interpretation. No provider client or network adapter exists."""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.goals.models import Goal, GoalUsage, UsagePolicy
from app.goals.schemas import InterpretationInput, InterpretationOutput


class InterpretationLimits(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    workspace_daily_calls: int = Field(default=100, ge=0, le=10000)
    global_daily_calls: int = Field(default=1000, ge=0, le=100000)
    user_hourly_calls: int = Field(default=20, ge=0, le=1000)
    timeout_seconds: float = Field(default=2, gt=0, le=10)
    output_bytes: int = Field(default=8192, ge=256, le=16384)
    enabled: bool = True


class GoalInterpreter:
    """Only trusted offline adapters may be injected; never constructed from user data."""

    external = False
    reserved_cost_micros = 0
    version = "offline-clarification-v1"

    def interpret(self, milestone: str) -> str:
        # Do not pretend a mock understands arbitrary free text.
        return InterpretationOutput(
            status="needs_clarification",
            missing_fields=[
                "metric",
                "target",
                "time_basis",
                "window",
                "deadline",
                "source",
                "baseline",
            ],
            questions=[
                "Choose a monthly or cumulative target and enter its dates, source "
                "and historical baseline in the editable goal."
            ],
        ).model_dump_json()


def get_interpreter() -> GoalInterpreter:
    return GoalInterpreter()


def policy(db: Session, scope: str, default_calls: int) -> UsagePolicy:
    row = db.get(UsagePolicy, scope)
    if row is None:
        row = UsagePolicy(scope=scope, call_limit=default_calls, cost_limit_micros=0, version=1)
        db.add(row)
        db.flush()
    return row


def reserve(
    db: Session,
    goal: Goal,
    user_id: str,
    body: InterpretationInput,
    adapter: GoalInterpreter,
    limits: InterpretationLimits,
    now: datetime,
) -> GoalUsage:
    from app.goals.service import expect

    expect(goal, body.expected_revision)
    # This release has no route for opting into external processing or spending.
    if not limits.enabled or adapter.external or adapter.reserved_cost_micros != 0:
        raise HTTPException(503, "external or paid interpretation is disabled")
    global_policy = db.scalar(
        select(UsagePolicy).where(UsagePolicy.scope == "global").with_for_update()
    )
    if global_policy is None:
        raise HTTPException(503, "interpretation limits unavailable")
    workspace_policy = policy(db, f"workspace:{goal.workspace_id}", limits.workspace_daily_calls)
    fingerprint = sha256(f"{goal.id}:{goal.revision}:{body.milestone}".encode()).hexdigest()
    existing = db.get(GoalUsage, (goal.workspace_id, body.idempotency_key))
    if existing is not None:
        if existing.fingerprint != fingerprint:
            raise HTTPException(409, "idempotency conflict")
        raise HTTPException(
            409, {"code": "interpretation_already_reserved", "state": existing.state}
        )
    day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    for scope, cap in [
        (None, min(global_policy.call_limit, limits.global_daily_calls)),
        (goal.workspace_id, min(workspace_policy.call_limit, limits.workspace_daily_calls)),
    ]:
        query = select(func.count()).select_from(GoalUsage).where(GoalUsage.created_at >= day)
        if scope is not None:
            query = query.where(GoalUsage.workspace_id == scope)
        if (db.scalar(query) or 0) >= cap:
            raise HTTPException(429, "interpretation quota exhausted")
    user_count = (
        db.scalar(
            select(func.count())
            .select_from(GoalUsage)
            .where(
                GoalUsage.workspace_id == goal.workspace_id,
                GoalUsage.user_id == user_id,
                GoalUsage.created_at >= now - timedelta(hours=1),
            )
        )
        or 0
    )
    if user_count >= limits.user_hourly_calls:
        raise HTTPException(429, "interpretation rate limit")
    if db.scalar(
        select(GoalUsage.request_key)
        .where(GoalUsage.goal_id == goal.id, GoalUsage.state.in_(["reserved", "uncertain"]))
        .limit(1)
    ):
        raise HTTPException(409, "interpretation outcome pending")
    row = GoalUsage(
        workspace_id=goal.workspace_id,
        request_key=body.idempotency_key,
        goal_id=goal.id,
        user_id=user_id,
        revision=goal.revision,
        fingerprint=fingerprint,
        created_at=now,
        state="reserved",
        reserved_micros=0,
        charged_micros=0,
        policy_version=workspace_policy.version,
    )
    db.add(row)
    db.commit()  # Durable reservation precedes the call; no DB locks held by the adapter.
    return row


def run(
    db: Session,
    goal: Goal,
    user_id: str,
    body: InterpretationInput,
    adapter: GoalInterpreter,
    limits: InterpretationLimits | None = None,
    *,
    authorize_result: Callable[[], None] | None = None,
) -> dict[str, Any]:
    limits = limits or InterpretationLimits()
    row = reserve(db, goal, user_id, body, adapter, limits, datetime.now(UTC))
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(adapter.interpret, body.milestone)
    try:
        raw = future.result(timeout=limits.timeout_seconds)
        if len(raw.encode()) > limits.output_bytes:
            raise ValueError("oversized output")
        result = InterpretationOutput.model_validate_json(raw)
        state = "completed"
        output = result.model_dump(mode="json")
    except TimeoutError:
        state = "uncertain"
        output = {"status": "unavailable", "reason": "interpretation_outcome_pending"}
    except (ValidationError, ValueError, TypeError, AttributeError):
        state = "invalid"
        output = {"status": "unavailable", "reason": "invalid_interpretation"}
    except Exception:
        state = "uncertain"
        output = {"status": "unavailable", "reason": "interpretation_outcome_pending"}
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
    # A completed call remains counted even if its result cannot be delivered.
    # Do not dirty the usage row before the workspace-first authorization callback.
    denied: HTTPException | None = None
    if authorize_result is not None:
        try:
            authorize_result()
        except HTTPException as error:
            denied = error
            db.rollback()
    row.state = state
    db.commit()
    if denied is not None:
        raise denied
    if authorize_result is not None:
        authorize_result()  # commit released locks: recheck before returning the result.
    return {
        **output,
        "goal_revision": body.expected_revision,
        "usage_state": row.state,
        "adapter_version": adapter.version,
        "spending_authorized": False,
    }
