"""Bounded workspace history from persisted evidence; never an execution endpoint."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select, text

from app.campaign_review.models import CampaignRevision
from app.customers.access import Database, Principal, customer_workspace
from app.goals.models import GoalRevision
from app.publication.coordinator import read_owned_outcome_receipt
from app.publication.execution_models import ProviderExecutionAttempt
from app.shopify.security import utc

router = APIRouter(prefix="/api/customer/v1/workspaces/{workspace_id}", tags=["customer"])
REVISION_LIMIT = 20
ATTEMPT_LIMIT = 10


class ActivityItem(BaseModel):
    source: Literal["goal", "campaign", "provider_receipt"]
    event: Literal[
        "saved",
        "confirmed",
        "approved",
        "verified_effect",
        "verified_target_state",
        "verified_no_effect",
        "unknown",
        "conflict",
    ]
    recorded_at: datetime
    revision: int | None = None
    environment: Literal["contract_test", "live"] | None = None
    evidence: (
        Literal["exact_readback", "authoritative_no_effect", "unresolved", "mismatch"] | None
    ) = None


class ActivityView(BaseModel):
    schema_version: Literal["inlet.customer.activity.v1"] = "inlet.customer.activity.v1"
    workspace_id: int
    items: list[ActivityItem]
    truncated: bool
    receipt_coverage: Literal["latest_for_recent_attempts", "owner_only"]
    receipt_unavailable: int
    coverage: Literal["recent_revisions_and_latest_receipts"] = (
        "recent_revisions_and_latest_receipts"
    )


@router.get("/activity")
def activity(
    workspace_id: int, principal: Principal, db: Database, response: Response
) -> ActivityView:
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT set_config('statement_timeout', '2000', true)"))
    _, role = customer_workspace(db, principal.user.id, workspace_id)
    response.headers["Cache-Control"] = "no-store"
    items: list[ActivityItem] = []
    truncated = False
    # Fixed source limits and stable primary-key ties; this is a recent sample,
    # not a complete event journal. Never read definition/artifact JSON here.
    for model, source, key, stamp in (
        (GoalRevision, "goal", GoalRevision.goal_id, GoalRevision.confirmed_at),
        (CampaignRevision, "campaign", CampaignRevision.draft_id, CampaignRevision.approved_at),
    ):
        for event, time_column in (
            ("saved", model.created_at),
            ("confirmed" if source == "goal" else "approved", stamp),
        ):
            rows = list(
                db.execute(
                    select(time_column, model.revision, key)
                    .where(model.workspace_id == workspace_id, time_column.is_not(None))
                    .order_by(time_column.desc(), key.desc(), model.revision.desc())
                    .limit(REVISION_LIMIT + 1)
                )
            )
            truncated |= len(rows) > REVISION_LIMIT
            for recorded_at, revision, _ in rows[:REVISION_LIMIT]:
                items.append(
                    ActivityItem(
                        source=source, event=event, recorded_at=utc(recorded_at), revision=revision
                    )
                )
    unavailable = 0
    if role == "owner":
        attempts = list(
            db.execute(
                select(ProviderExecutionAttempt.id, ProviderExecutionAttempt.dispatched_at)
                .where(ProviderExecutionAttempt.workspace_id == workspace_id)
                .order_by(
                    ProviderExecutionAttempt.dispatched_at.desc(),
                    ProviderExecutionAttempt.id.desc(),
                )
                .limit(ATTEMPT_LIMIT + 1)
            )
        )
        truncated |= len(attempts) > ATTEMPT_LIMIT
        for attempt_id, _ in attempts[:ATTEMPT_LIMIT]:
            try:
                receipt = read_owned_outcome_receipt(
                    db, workspace_id, attempt_id, principal.user.id
                )
            except HTTPException as error:
                if error.status_code not in {404, 409}:
                    raise
                unavailable += 1
                continue
            if receipt is None:
                unavailable += 1
                continue
            items.append(
                ActivityItem(
                    source="provider_receipt",
                    event=receipt.outcome,
                    recorded_at=receipt.observed_at,
                    environment=receipt.environment,
                    evidence=receipt.evidence,
                )
            )
    # Stable sorting retains per-source primary-key tie order without exposing IDs.
    items.sort(key=lambda row: row.recorded_at, reverse=True)
    return ActivityView(
        workspace_id=workspace_id,
        items=items,
        truncated=truncated,
        receipt_coverage="latest_for_recent_attempts" if role == "owner" else "owner_only",
        receipt_unavailable=unavailable,
    )
