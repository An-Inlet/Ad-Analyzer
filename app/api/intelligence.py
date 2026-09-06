from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.auth import require_api_token
from app.api.schemas import ApiErrorResponse
from app.database.session import get_db
from app.intelligence.repository import ContextConflict, ContextNotFound, IntelligenceRepository
from app.intelligence.schemas import (
    AnalystQuestion,
    Decision,
    RecordKind,
    RecordResponse,
    SaveRecord,
    ScenarioRequest,
)
from app.intelligence.service import IntelligenceService
from app.workspaces.models import Workspace
from app.workspaces.repository import WorkspaceRepository

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_slug}/intelligence",
    tags=["business context and decision support"],
    dependencies=[Depends(require_api_token)],
    responses={code: {"model": ApiErrorResponse} for code in (401, 404, 409, 422, 503)},
)


def workspace_or_404(db: Session, slug: str) -> Workspace:
    workspace = WorkspaceRepository(db).get_by_slug(slug)
    if workspace is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    return workspace


def save_context(
    db: Session,
    workspace_id: int,
    kind: RecordKind,
    command: SaveRecord,
    *,
    actor_role: str,
    record_id: int | None = None,
) -> RecordResponse:
    try:
        if kind == RecordKind.DECISION:
            decision = Decision.model_validate(command.payload)
            previous = (
                IntelligenceRepository(db).get(workspace_id, record_id) if record_id else None
            )
            accepting = decision.status == "accepted" and (
                previous is None or previous.data.get("status") != "accepted"
            )
            if record_id is None or accepting:
                report = IntelligenceService(db).report(workspace_id)
                suggestion = next(
                    (
                        r
                        for r in report["recommendations"]
                        if r["key"] == decision.recommendation_key
                    ),
                    None,
                )
                if (
                    suggestion is None
                    or suggestion["evidence_fingerprint"] != decision.evidence_fingerprint
                ):
                    raise ContextConflict(
                        "Recommendation evidence changed. Reload before reviewing."
                    )
                if record_id is None:
                    command = command.model_copy(
                        update={
                            "payload": {
                                **command.payload,
                                "evidence_snapshot": suggestion,
                            }
                        }
                    )
        record = IntelligenceRepository(db).save(
            workspace_id, kind, command, actor_role=actor_role, record_id=record_id
        )
        db.commit()
        return RecordResponse.model_validate(record)
    except ContextNotFound:
        db.rollback()
        raise HTTPException(status_code=404, detail="business record not found") from None
    except ContextConflict:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="record or evidence changed; reload before saving"
        ) from None
    except (ValidationError, ValueError):
        db.rollback()
        raise HTTPException(
            status_code=422,
            detail="invalid business context; check dates, amounts, and required fields",
        ) from None


@router.get("")
def report(workspace_slug: str, db: Annotated[Session, Depends(get_db)]) -> dict[str, Any]:
    workspace = workspace_or_404(db, workspace_slug)
    return IntelligenceService(db).report(workspace.id)


@router.get("/records/{kind}")
def records(
    workspace_slug: str,
    kind: RecordKind,
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10_000),
) -> dict[str, Any]:
    workspace = workspace_or_404(db, workspace_slug)
    repository = IntelligenceRepository(db)
    return {
        "items": [
            RecordResponse.model_validate(r)
            for r in repository.list_records(workspace.id, kind, limit=limit, offset=offset)
        ],
        "total": repository.count(workspace.id, kind),
        "limit": limit,
        "offset": offset,
    }


@router.post("/records/{kind}", response_model=RecordResponse, status_code=201)
def create_record(
    workspace_slug: str,
    kind: RecordKind,
    command: SaveRecord,
    db: Annotated[Session, Depends(get_db)],
) -> RecordResponse:
    workspace = workspace_or_404(db, workspace_slug)
    return save_context(db, workspace.id, kind, command, actor_role="operator")


@router.put("/records/{kind}/{record_id}", response_model=RecordResponse)
def update_record(
    workspace_slug: str,
    kind: RecordKind,
    record_id: int,
    command: SaveRecord,
    db: Annotated[Session, Depends(get_db)],
) -> RecordResponse:
    workspace = workspace_or_404(db, workspace_slug)
    return save_context(db, workspace.id, kind, command, actor_role="operator", record_id=record_id)


@router.post("/ask")
def ask(
    workspace_slug: str, question: AnalystQuestion, db: Annotated[Session, Depends(get_db)]
) -> dict[str, Any]:
    workspace = workspace_or_404(db, workspace_slug)
    service = IntelligenceService(db)
    return service.answer(service.report(workspace.id), question.question)


@router.post("/scenario")
def scenario(
    workspace_slug: str, command: ScenarioRequest, db: Annotated[Session, Depends(get_db)]
) -> dict[str, Any]:
    workspace = workspace_or_404(db, workspace_slug)
    service = IntelligenceService(db)
    try:
        return service.scenario(service.report(workspace.id), command)
    except ValueError:
        raise HTTPException(
            status_code=422, detail="save a strategy before modeling a budget"
        ) from None
