"""Customer intent APIs; no ad execution or external model endpoints."""

from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select

from app.customers.access import Database, MutationPrincipal, Principal, customer_workspace
from app.goals import service
from app.goals.interpreter import GoalInterpreter, get_interpreter, run
from app.goals.models import Goal, GoalRevision, GoalUsage
from app.goals.schemas import ConfirmInput, DraftInput, EditInput, InterpretationInput, PreviewInput

router = APIRouter(prefix="/api/customer/v1/workspaces/{workspace_id}/goals", tags=["customer"])


def access(
    db: Database,
    user_id: str,
    workspace_id: int,
    response: Response,
    *,
    confirm: bool = False,
    edit: bool = False,
) -> None:
    _, role = customer_workspace(db, user_id, workspace_id)
    response.headers["Cache-Control"] = "no-store"
    if (confirm and role not in {"owner", "admin"}) or (
        edit and role not in {"owner", "admin", "analyst"}
    ):
        raise HTTPException(403, "insufficient role")


@router.post("", status_code=201)
def create(
    workspace_id: int,
    body: DraftInput,
    principal: MutationPrincipal,
    db: Database,
    response: Response,
) -> dict[str, Any]:
    access(db, principal.user.id, workspace_id, response, edit=True)
    item = Goal(id=uuid4().hex, workspace_id=workspace_id, revision=0)
    db.add(item)
    db.flush()
    service.revise(db, item, body.definition, principal.user.id, datetime.now(UTC))
    db.commit()
    return service.serialize(db, item)


@router.get("")
def listing(
    workspace_id: int, principal: Principal, db: Database, response: Response
) -> list[dict[str, Any]]:
    access(db, principal.user.id, workspace_id, response)
    return [
        service.serialize(db, g)
        for g in db.scalars(select(Goal).where(Goal.workspace_id == workspace_id))
    ]


@router.get("/usage")
def usage(
    workspace_id: int, principal: Principal, db: Database, response: Response
) -> dict[str, Any]:
    access(db, principal.user.id, workspace_id, response)
    day = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    rows = list(
        db.scalars(
            select(GoalUsage).where(
                GoalUsage.workspace_id == workspace_id, GoalUsage.created_at >= day
            )
        )
    )
    return {
        "calls_reserved_today": len(rows),
        "pending": sum(r.state in {"reserved", "uncertain"} for r in rows),
        "authorized_model_spend_micros": 0,
        "external_model_calls_enabled": False,
    }


@router.get("/{goal_id}")
def read(
    workspace_id: int, goal_id: str, principal: Principal, db: Database, response: Response
) -> dict[str, Any]:
    access(db, principal.user.id, workspace_id, response)
    return service.serialize(db, service.owned(db, workspace_id, goal_id))


@router.get("/{goal_id}/history")
def history(
    workspace_id: int, goal_id: str, principal: Principal, db: Database, response: Response
) -> list[dict[str, Any]]:
    access(db, principal.user.id, workspace_id, response)
    service.owned(db, workspace_id, goal_id)
    return [
        {
            "revision": r.revision,
            "definition": r.definition,
            "confirmed_at": r.confirmed_at,
            "confirmed_by": r.confirmed_by,
        }
        for r in db.scalars(
            select(GoalRevision)
            .where(GoalRevision.goal_id == goal_id)
            .order_by(GoalRevision.revision)
        )
    ]


@router.put("/{goal_id}")
def edit(
    workspace_id: int,
    goal_id: str,
    body: EditInput,
    principal: MutationPrincipal,
    db: Database,
    response: Response,
) -> dict[str, Any]:
    access(db, principal.user.id, workspace_id, response, edit=True)
    item = service.owned(db, workspace_id, goal_id)
    service.expect(item, body.expected_revision)
    service.revise(db, item, body.definition, principal.user.id, datetime.now(UTC))
    db.commit()
    return service.serialize(db, item)


@router.post("/{goal_id}/preview")
def preview(
    workspace_id: int,
    goal_id: str,
    body: PreviewInput,
    principal: MutationPrincipal,
    db: Database,
    response: Response,
) -> dict[str, Any]:
    access(db, principal.user.id, workspace_id, response, edit=True)
    item = service.owned(db, workspace_id, goal_id)
    service.expect(item, body.expected_revision)
    p = service.preview(db, item, datetime.now(UTC))
    db.commit()
    return {
        "preview_id": p.id,
        "revision": p.revision,
        "snapshot_id": p.snapshot_id,
        "spending_authorized": False,
    }


@router.post("/{goal_id}/confirm")
def confirm(
    workspace_id: int,
    goal_id: str,
    body: ConfirmInput,
    principal: MutationPrincipal,
    db: Database,
    response: Response,
) -> dict[str, Any]:
    access(db, principal.user.id, workspace_id, response, confirm=True)
    item = service.owned(db, workspace_id, goal_id)
    service.confirm(db, item, body, datetime.now(UTC), actor_id=principal.user.id)
    db.commit()
    return service.serialize(db, item)


@router.post("/{goal_id}/interpret")
def interpret(
    workspace_id: int,
    goal_id: str,
    body: InterpretationInput,
    principal: MutationPrincipal,
    db: Database,
    response: Response,
    adapter: Annotated[GoalInterpreter, Depends(get_interpreter)],
) -> dict[str, Any]:
    access(db, principal.user.id, workspace_id, response, edit=True)
    item = service.owned(db, workspace_id, goal_id)
    service.expect(item, body.expected_revision)
    return run(db, item, principal.user.id, body, adapter)
