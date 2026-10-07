"""Private endpoints used by authenticated Google Cloud service identities."""

import base64
import binascii
import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy.orm import Session

from app.crm.push_auth import require_crm_push_identity
from app.crm.worker import CrmEventProcessor, record_scope_rejection
from app.database.session import get_db
from app.imports.scope import ImportScopeError

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/internal/pubsub",
    include_in_schema=False,
    dependencies=[Depends(require_crm_push_identity)],
)


class PubSubMessage(BaseModel):
    """Fields needed from the standard Pub/Sub push message."""

    model_config = ConfigDict(extra="ignore")

    data: str
    message_id: str | None = None


class PubSubPushEnvelope(BaseModel):
    """Standard wrapped Pub/Sub push request."""

    model_config = ConfigDict(extra="ignore")

    message: PubSubMessage
    subscription: str | None = None


@router.post("/crm-events", status_code=204)
def receive_crm_event(
    envelope: PubSubPushEnvelope, db: Annotated[Session, Depends(get_db)]
) -> Response:
    """Process one push delivery, acknowledging only successful or duplicate events.

    Application OIDC authentication runs before this processor. Cloud Run IAM remains
    defense in depth, not the sole worker identity boundary.
    Any non-2xx response causes Pub/Sub to apply the subscription retry/dead-letter policy.
    """
    try:
        decoded = base64.b64decode(envelope.message.data, validate=True)
        payload = json.loads(decoded)
        if not isinstance(payload, dict):
            raise ValueError("event must be an object")
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        logger.warning("CRM push delivery contained an invalid event (payload omitted)")
        return JSONResponse(status_code=400, content={"detail": "invalid_event"})

    try:
        CrmEventProcessor(db).process(payload)
    except ImportScopeError:
        record_scope_rejection(db, decoded)
        return JSONResponse(status_code=400, content={"detail": "scope_rejected"})
    except (ValidationError, ValueError):
        db.rollback()
        logger.warning("CRM push delivery failed event validation (payload omitted)")
        return JSONResponse(status_code=400, content={"detail": "invalid_event"})
    except Exception as exc:
        db.rollback()
        logger.warning("CRM push processing failed: %s (payload omitted)", exc.__class__.__name__)
        return JSONResponse(status_code=503, content={"detail": "processing_failed"})

    return Response(status_code=204)
