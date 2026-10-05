import hashlib
import hmac
import json
import logging
import re
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.crm.dependencies import get_publisher, get_replay_guard
from app.crm.ownership import SecretReader, connection_for_scope, get_secret_reader
from app.crm.publisher import EventPublisher
from app.crm.replay import ReplayGuard
from app.crm.schemas import CrmEvent, CrmReceipt
from app.database.session import get_db
from app.imports.scope import ImportScopeError
from app.workspaces.models import WorkspaceIntegration

router = APIRouter(prefix="/v1/crm", tags=["crm"])
logger = logging.getLogger(__name__)
PUBLISHER_DEPENDENCY = Depends(get_publisher)
DATABASE_DEPENDENCY = Depends(get_db)
SECRET_READER_DEPENDENCY = Depends(get_secret_reader)
REPLAY_GUARD_DEPENDENCY = Depends(get_replay_guard)
_EVENT_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_SIGNATURE = re.compile(r"^(?:sha256=)?([0-9a-fA-F]{64})$")


def _error(status: int, code: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"detail": code})


@router.post("/events")
def reject_unscoped_event() -> JSONResponse:
    return _error(422, "explicit_connection_scope_required")


@router.post(
    "/workspaces/{workspace_id}/connections/{connection_id}/events",
    response_model=CrmReceipt,
    status_code=202,
)
async def receive_crm_event(
    request: Request,
    workspace_id: int,
    connection_id: int,
    db: Session = DATABASE_DEPENDENCY,
    secret_reader: SecretReader = SECRET_READER_DEPENDENCY,
    publisher: EventPublisher = PUBLISHER_DEPENDENCY,
    replay_guard: ReplayGuard = REPLAY_GUARD_DEPENDENCY,
) -> CrmReceipt | JSONResponse:
    event_id = request.headers.get("X-AnInlet-Event-Id")
    timestamp_text = request.headers.get("X-AnInlet-Timestamp")
    signature_text = request.headers.get("X-AnInlet-Signature")
    if not event_id or not timestamp_text or not signature_text:
        return _error(401, "authentication_required")
    match = _SIGNATURE.fullmatch(signature_text)
    if not _EVENT_ID.fullmatch(event_id) or match is None:
        return _error(401, "invalid_authentication")
    try:
        timestamp = datetime.fromtimestamp(int(timestamp_text), tz=UTC)
    except (ValueError, OverflowError, OSError):
        return _error(401, "invalid_authentication")
    now = datetime.now(UTC)
    if abs(now - timestamp) > timedelta(minutes=5):
        return _error(401, "expired_request")

    body = await request.body()
    try:
        connection = connection_for_scope(db, workspace_id, connection_id)
        integration = db.get(WorkspaceIntegration, connection_id)
        if integration is None:
            raise ImportScopeError("CRM ownership unavailable")
    except ImportScopeError:
        return _error(401, "invalid_authentication")
    try:
        secret = secret_reader.read(connection.secret_manager_reference)
    except Exception:
        logger.warning("CRM connection secret unavailable (details omitted)")
        return _error(503, "service_unavailable")
    signed_scope = f"v2:{workspace_id}:{connection_id}:{timestamp_text}.".encode()
    expected = hmac.new(secret.encode(), signed_scope + body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, match.group(1).lower()):
        return _error(401, "invalid_authentication")
    try:
        event = CrmEvent.model_validate(json.loads(body))
    except (json.JSONDecodeError, UnicodeDecodeError, ValidationError):
        return _error(422, "invalid_event")
    if event.event_id != event_id:
        return _error(422, "invalid_event")
    replay_key = hashlib.sha256(f"{workspace_id}:{connection_id}:{event_id}".encode()).hexdigest()
    if not replay_guard.claim(replay_key, now=now):
        return _error(409, "duplicate_event")
    normalized = event.model_dump(mode="json", exclude_none=True)
    normalized.update(
        payload_version=2,
        workspace_id=workspace_id,
        connection_id=connection_id,
        provider=integration.provider,
    )
    try:
        publisher.publish(normalized, event_id=event_id)
    except Exception:
        replay_guard.release(replay_key)
        logger.warning("CRM event publication failed (payload omitted)")
        return _error(503, "service_unavailable")
    return CrmReceipt(receipt_id=f"rcpt_{uuid.uuid4().hex}")
