import json
from collections.abc import Mapping
from typing import Protocol


class EventPublisher(Protocol):
    def publish(self, event: Mapping[str, object], *, event_id: str) -> None: ...


class GooglePubSubPublisher:
    """Publish normalized JSON; event ID is an idempotency attribute for consumers."""

    def __init__(self, project_id: str, topic_id: str) -> None:
        from google.cloud import pubsub_v1  # type: ignore[import-untyped]

        self._client = pubsub_v1.PublisherClient()
        self._topic = self._client.topic_path(project_id, topic_id)

    def publish(self, event: Mapping[str, object], *, event_id: str) -> None:
        payload = json.dumps(event, separators=(",", ":"), sort_keys=True, default=str).encode()
        # Waiting exposes failure; a retried request remains safe through the stable event ID.
        self._client.publish(self._topic, payload, event_id=event_id).result(timeout=10)


class FakeEventPublisher:
    def __init__(self, *, fail: bool = False) -> None:
        self.events: list[dict[str, object]] = []
        self.fail = fail

    def publish(self, event: Mapping[str, object], *, event_id: str) -> None:
        if self.fail:
            raise RuntimeError("publication failed")
        self.events.append(dict(event))
