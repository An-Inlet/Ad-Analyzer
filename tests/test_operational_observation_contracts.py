from datetime import UTC, datetime, timedelta

import pytest
from app.operations.observation_contracts import OperationalObservation

NOW = datetime(2026, 10, 6, tzinfo=UTC)


def test_media_event_has_no_scope_or_payload_fields() -> None:
    event = OperationalObservation(
        component="private_media_gcs",
        slot="latest_failure",
        outcome="media_read_failed",
        observed_at=NOW,
    )
    for field in ("workspace_id", "message", "exception", "bucket", "object_key"):
        with pytest.raises(ValueError):
            OperationalObservation.model_validate({**event.model_dump(), field: "private"})


@pytest.mark.parametrize("change", ["slot", "epoch", "time", "provider"])
def test_scheduler_observations_are_typed_and_not_arbitrary(change: str) -> None:
    values = dict(
        component="scheduler_loop",
        slot="latest_start",
        outcome="scheduler_cycle_started",
        observed_at=NOW,
        process_epoch="a" * 32,
        epoch_started_at=NOW,
    )
    if change == "slot":
        values["slot"] = "latest_completion"
    elif change == "epoch":
        values["process_epoch"] = None
    elif change == "time":
        values["epoch_started_at"] = NOW + timedelta(seconds=1)
    else:
        values["component"] = "private_media_gcs"
    with pytest.raises(ValueError):
        OperationalObservation.model_validate(values)
