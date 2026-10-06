"""Bounded operational facts, never job recovery or execution authority."""

from datetime import datetime
from typing import Literal, Protocol

from pydantic import AwareDatetime, Field, model_validator

from app.goals.schemas import StrictModel

Component = Literal["scheduler_loop", "private_media_local", "private_media_gcs"]
Slot = Literal["latest_start", "latest_completion", "latest_failure"]
Outcome = Literal[
    "scheduler_cycle_started",
    "scheduler_cycle_completed",
    "scheduler_cycle_failed",
    "scheduler_stage_failed",
    "scheduler_interrupted",
    "media_read_started",
    "media_write_started",
    "media_initialized",
    "media_read_completed",
    "media_write_completed",
    "media_init_failed",
    "media_read_failed",
    "media_write_failed",
]


class OperationalObservation(StrictModel):
    component: Component
    slot: Slot
    outcome: Outcome
    observed_at: AwareDatetime
    expected_next_at: AwareDatetime | None = None
    process_epoch: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    epoch_started_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def consistent(self) -> "OperationalObservation":
        if self.component == "scheduler_loop":
            if (
                not self.outcome.startswith("scheduler_")
                or self.process_epoch is None
                or self.epoch_started_at is None
                or self.epoch_started_at > self.observed_at
            ):
                raise ValueError("scheduler epoch required")
        elif not self.outcome.startswith("media_") or any(
            v is not None
            for v in (self.process_epoch, self.epoch_started_at, self.expected_next_at)
        ):
            raise ValueError("invalid private media observation")
        expected = (
            "latest_start"
            if self.outcome.endswith("started")
            else "latest_failure"
            if self.outcome.endswith(("failed", "interrupted"))
            else "latest_completion"
        )
        if self.slot != expected or (
            self.expected_next_at is not None and self.expected_next_at < self.observed_at
        ):
            raise ValueError("invalid observation slot or next time")
        return self


class ObservationSink(Protocol):
    def record(self, observation: OperationalObservation, /) -> None: ...


class ObservationClock(Protocol):
    def __call__(self) -> datetime: ...
