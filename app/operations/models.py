"""Nine fixed global telemetry slots; no customer data or execution ownership."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class OperationalObservationRecord(Base):
    __tablename__ = "operational_observations"
    __table_args__ = (
        CheckConstraint(
            "component IN ('scheduler_loop','private_media_local','private_media_gcs')",
            name="ck_observation_component",
        ),
        CheckConstraint(
            "slot IN ('latest_start','latest_completion','latest_failure')",
            name="ck_observation_slot",
        ),
        CheckConstraint("occurrence_count BETWEEN 1 AND 2147483647", name="ck_observation_count"),
        CheckConstraint(
            "expected_next_at IS NULL OR expected_next_at >= observed_at",
            name="ck_observation_next",
        ),
        CheckConstraint(
            "(component = 'scheduler_loop' AND process_epoch IS NOT NULL AND epoch_started_at "
            "IS NOT NULL AND epoch_started_at <= observed_at) OR (component != "
            "'scheduler_loop' AND process_epoch IS NULL AND epoch_started_at IS NULL AND "
            "expected_next_at IS NULL)",
            name="ck_observation_epoch",
        ),
        CheckConstraint(
            "(component = 'scheduler_loop' AND ((slot = 'latest_start' AND outcome = "
            "'scheduler_cycle_started') OR (slot = 'latest_completion' AND outcome = "
            "'scheduler_cycle_completed') OR (slot = 'latest_failure' AND outcome IN "
            "('scheduler_cycle_failed','scheduler_stage_failed','scheduler_interrupted')))) "
            "OR (component != 'scheduler_loop' AND ((slot = 'latest_start' AND outcome IN "
            "('media_read_started','media_write_started')) OR (slot = 'latest_completion' AND "
            "outcome IN ('media_initialized','media_read_completed','media_write_completed')) "
            "OR (slot = 'latest_failure' AND outcome IN "
            "('media_init_failed','media_read_failed','media_write_failed'))))",
            name="ck_observation_outcome",
        ),
    )
    component: Mapped[str] = mapped_column(String(32), primary_key=True)
    slot: Mapped[str] = mapped_column(String(24), primary_key=True)
    outcome: Mapped[str] = mapped_column(String(32))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expected_next_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    process_epoch: Mapped[str | None] = mapped_column(String(32))
    epoch_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1)
