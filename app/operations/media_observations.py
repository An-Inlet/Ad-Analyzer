"""Observe actual private-media calls without probing, retrying or retaining scope."""

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Literal

from app.campaign_review.contracts import MediaStore
from app.operations.observation_contracts import (
    ObservationClock,
    ObservationSink,
    OperationalObservation,
    Outcome,
    Slot,
)
from app.operations.observations import record_safely

MediaComponent = Literal["private_media_local", "private_media_gcs"]


def now_utc() -> datetime:
    return datetime.now(UTC)


class ObservedMediaStore:
    def __init__(
        self,
        store: MediaStore,
        sink: ObservationSink,
        component: MediaComponent,
        clock: ObservationClock = now_utc,
    ) -> None:
        self.store, self.sink, self.component, self.clock = store, sink, component, clock

    def _record(self, slot: Slot, outcome: Outcome) -> None:
        record_safely(
            self.sink,
            OperationalObservation(
                component=self.component, slot=slot, outcome=outcome, observed_at=self.clock()
            ),
        )

    def put_if_absent(
        self, workspace_id: int, sha256: str, size: int, chunks: Iterable[bytes]
    ) -> None:
        self._record("latest_start", "media_write_started")
        try:
            self.store.put_if_absent(workspace_id, sha256, size, chunks)
        except Exception:
            self._record("latest_failure", "media_write_failed")
            raise
        self._record("latest_completion", "media_write_completed")

    def read_exact(self, workspace_id: int, sha256: str, size: int) -> bytes:
        self._record("latest_start", "media_read_started")
        try:
            result = self.store.read_exact(workspace_id, sha256, size)
        except Exception:
            self._record("latest_failure", "media_read_failed")
            raise
        self._record("latest_completion", "media_read_completed")
        return result
