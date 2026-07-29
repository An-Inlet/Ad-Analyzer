import threading
from datetime import UTC, datetime, timedelta
from typing import Protocol


class ReplayGuard(Protocol):
    def claim(self, event_id: str, *, now: datetime) -> bool: ...
    def release(self, event_id: str) -> None: ...


class InMemoryReplayGuard:
    """Process-local guard for development/tests; production uses Pub/Sub worker idempotency too."""

    def __init__(self, retention: timedelta = timedelta(hours=24)) -> None:
        self._claims: dict[str, datetime] = {}
        self._retention = retention
        self._lock = threading.Lock()

    def claim(self, event_id: str, *, now: datetime | None = None) -> bool:
        current = now or datetime.now(UTC)
        with self._lock:
            cutoff = current - self._retention
            self._claims = {key: value for key, value in self._claims.items() if value >= cutoff}
            if event_id in self._claims:
                return False
            self._claims[event_id] = current
            return True

    def release(self, event_id: str) -> None:
        with self._lock:
            self._claims.pop(event_id, None)
