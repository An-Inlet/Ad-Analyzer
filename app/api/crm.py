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

from app.crm.dependencies import get_publisher, get_replay_guard
from app.crm.publisher import EventPublisher
from app.crm.replay import ReplayGuard
from app.crm.schemas import CrmEvent, CrmReceipt
from app.settings import settings

router = APIRouter(prefix="/v1/crm", tags=["crm"])
logger = logging.getLogger(__name__)
PUBLISHER_DEPENDENCY = Depends(get_publisher)
REPLAY_GUARD_DEPENDENCY = Depends(get_replay_guard)
_EVENT_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_SIGNATURE = re.compile(r"^(?:sha256=)?([0-9a-fA-F]{64})$")


def _error(status: int, code: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"detail": code})


@router.post("/events", response_model=CrmReceipt, status_code=202)
async def receive_crm_event(
    request: Request,
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
    secret = settings.crm_webhook_secret
    if secret is None:
        logger.error("CRM webhook secret is not configured")
        return _error(503, "service_unavailable")
    expected = hmac.new(
        secret.get_secret_value().encode(), timestamp_text.encode() + b"." + body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, match.group(1).lower()):
        return _error(401, "invalid_authentication")
    try:
        event = CrmEvent.model_validate(json.loads(body))
    except (json.JSONDecodeError, UnicodeDecodeError, ValidationError):
        return _error(422, "invalid_event")
    if event.event_id != event_id:
        return _error(422, "invalid_event")
    if not replay_guard.claim(event_id, now=now):
        return _error(409, "duplicate_event")
    normalized = event.model_dump(mode="json", exclude_none=True)
    normalized["payload_version"] = 1
    try:
        publisher.publish(normalized, event_id=event_id)
    except Exception:
        replay_guard.release(event_id)
        logger.exception("CRM event publication failed (payload omitted)")
        return _error(503, "service_unavailable")
    return CrmReceipt(receipt_id=f"rcpt_{uuid.uuid4().hex}")
