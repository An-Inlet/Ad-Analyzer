from collections.abc import Generator
from functools import lru_cache

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.crm.publisher import EventPublisher, GooglePubSubPublisher
from app.crm.replay import InMemoryReplayGuard, ReplayGuard
from app.database.session import get_db
from app.settings import settings


@lru_cache
def get_publisher() -> EventPublisher:
    if not settings.crm_pubsub_project_id or not settings.crm_pubsub_topic_id:
        raise RuntimeError("CRM publisher is not configured")
    return GooglePubSubPublisher(settings.crm_pubsub_project_id, settings.crm_pubsub_topic_id)


_replay_guard = InMemoryReplayGuard()


def get_replay_guard() -> ReplayGuard:
    return _replay_guard


def get_ingress_db() -> Generator[Session, None, None]:
    """Never send the formerly publish-only gateway to the development database default."""
    configured = (
        settings.cloud_sql_configuration_complete
        if settings.uses_cloud_sql_socket
        else "database_url" in settings.model_fields_set and bool(settings.database_url.strip())
    )
    if not configured:
        raise HTTPException(503, "crm_ownership_database_not_configured")
    try:
        yield from get_db()
    except SQLAlchemyError:
        raise HTTPException(503, "crm_ownership_database_unavailable") from None
