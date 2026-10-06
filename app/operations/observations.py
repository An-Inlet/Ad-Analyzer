"""Best-effort independent operational recording; no worker recovery side effects."""

import logging
from datetime import UTC, datetime
from functools import lru_cache

from sqlalchemy import Engine, create_engine, func, select, text
from sqlalchemy.orm import Session

from app.operations.models import OperationalObservationRecord
from app.operations.observation_contracts import ObservationSink, OperationalObservation
from app.settings import settings

logger = logging.getLogger(__name__)


def record_safely(sink: ObservationSink | None, event: OperationalObservation) -> None:
    if sink is None:
        return
    try:
        sink.record(event)
    except Exception:
        logger.warning("operational_observation_unavailable")


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class DatabaseObservationSink:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def record(self, observation: OperationalObservation, /) -> None:
        event = OperationalObservation.model_validate(observation.model_dump())
        with Session(self.engine) as db:
            if self.engine.dialect.name == "postgresql":
                db.execute(select(func.set_config("statement_timeout", "250", True)))
                db.execute(select(func.set_config("lock_timeout", "200", True)))
                # Fixed global telemetry lock, never workspace/provider authority locks.
                db.execute(text("SELECT pg_advisory_xact_lock(739214081)"))
            elif self.engine.dialect.name == "sqlite":
                db.execute(text("PRAGMA busy_timeout=250"))
                db.execute(text("BEGIN IMMEDIATE"))
            else:
                raise ValueError("unsupported operational evidence database")
            if event.component == "scheduler_loop":
                current = db.get(OperationalObservationRecord, (event.component, "latest_start"))
                if current is not None:
                    assert (
                        event.epoch_started_at is not None and current.epoch_started_at is not None
                    )
                    if event.epoch_started_at < utc(current.epoch_started_at):
                        return
                    if (
                        event.slot != "latest_start"
                        and event.process_epoch != current.process_epoch
                    ):
                        return
                elif event.slot != "latest_start":
                    return
            row = db.get(OperationalObservationRecord, (event.component, event.slot))
            if row is not None and utc(row.observed_at) > event.observed_at:
                return
            if row is None:
                row = OperationalObservationRecord(**event.model_dump(), occurrence_count=1)
                db.add(row)
            else:
                for key, value in event.model_dump().items():
                    setattr(row, key, value)
                row.occurrence_count = min(2147483647, row.occurrence_count + 1)
            db.commit()


@lru_cache(maxsize=1)
def _postgres_sink(database_url: str) -> DatabaseObservationSink:
    # Lazy Engine creation opens no socket. Only record() checks out a connection.
    return DatabaseObservationSink(
        create_engine(
            database_url,
            pool_size=1,
            max_overflow=0,
            pool_timeout=0.25,
            connect_args={"connect_timeout": 1},
        )
    )


def get_observation_sink() -> ObservationSink | None:
    if not settings.operational_observations_enabled:
        return None
    try:
        url = settings.resolved_database_url
        if url.get_backend_name() != "postgresql":
            return None
        return _postgres_sink(url.render_as_string(hide_password=False))
    except Exception:
        logger.warning("operational_observation_unavailable")
        return None
