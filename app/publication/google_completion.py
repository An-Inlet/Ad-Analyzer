"""Owned append-only original response evidence, deliberately not ClosedOriginalRequest."""

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.publication.execution_models import GoogleOriginalCompletion
from app.publication.google_completion_contracts import (
    GoogleCapturedResponse,
    GoogleCompletionDocument,
)
from app.publication.optimization_contracts import OptimizationRequest
from app.publication.service import owner
from app.shopify.security import utc


def capture_response(
    db: Session, request: OptimizationRequest, response: GoogleCapturedResponse, now: datetime
) -> None:
    """Caller holds original evidence locks; same transaction as normalized response."""
    if response.outcome != "acknowledged" or response.request_digest != request.digest():
        raise HTTPException(409, "original Google response unavailable")
    document = GoogleCompletionDocument(capture=response.capture, recorded_at=now)
    try:
        document.bind(request, now)
    except ValueError:
        raise HTTPException(409, "original Google response binding changed") from None
    prior = db.get(GoogleOriginalCompletion, request.attempt_id)
    if prior is not None:
        try:
            old = GoogleCompletionDocument.model_validate(prior.document)
            old.bind(request, now)
            if (
                old.capture != response.capture
                or old.digest() != prior.digest
                or prior.workspace_id != request.intent.scope.workspace_id
                or prior.request_digest != request.digest()
                or prior.fence != request.fence
                or utc(prior.recorded_at) != old.recorded_at
            ):
                raise ValueError()
        except ValueError:
            raise HTTPException(409, "immutable original Google response conflict") from None
        return
    db.add(
        GoogleOriginalCompletion(
            attempt_id=request.attempt_id,
            workspace_id=request.intent.scope.workspace_id,
            fence=request.fence,
            request_digest=request.digest(),
            digest=document.digest(),
            document=document.model_dump(mode="json"),
            recorded_at=now,
        )
    )


def read_owned(
    db: Session, workspace_id: int, attempt_id: str, actor: str, now: datetime
) -> GoogleCompletionDocument | None:
    from app.publication.optimization import evidence_lock

    _, _, _, request = evidence_lock(db, workspace_id, attempt_id)
    owner(db, workspace_id, actor)
    row = db.get(GoogleOriginalCompletion, attempt_id)
    if row is None:
        return (
            None  # Legacy acknowledgments, timeout, crash before durable capture stay unavailable.
        )
    try:
        document = GoogleCompletionDocument.model_validate(row.document)
        document.bind(request, now)
        if (
            row.workspace_id != workspace_id
            or row.fence != request.fence
            or row.request_digest != request.digest()
            or row.digest != document.digest()
            or utc(row.recorded_at) != document.recorded_at
        ):
            raise ValueError()
        return document
    except ValueError:
        raise HTTPException(409, "original Google response evidence changed") from None
