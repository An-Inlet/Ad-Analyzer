from functools import lru_cache

from app.crm.publisher import EventPublisher, GooglePubSubPublisher
from app.crm.replay import InMemoryReplayGuard, ReplayGuard
from app.settings import settings


@lru_cache
def get_publisher() -> EventPublisher:
    if not settings.crm_pubsub_project_id or not settings.crm_pubsub_topic_id:
        raise RuntimeError("CRM publisher is not configured")
    return GooglePubSubPublisher(settings.crm_pubsub_project_id, settings.crm_pubsub_topic_id)


_replay_guard = InMemoryReplayGuard()


def get_replay_guard() -> ReplayGuard:
    return _replay_guard
