# ruff: noqa: F811
"""Bounded telemetry on actual runtime calls, entirely offline."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Event
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from app.campaign_review import storage
from app.jobs import google_ads_scheduler as scheduler
from app.operations.media_observations import ObservedMediaStore
from app.operations.models import OperationalObservationRecord as Record
from app.operations.observation_contracts import OperationalObservation
from app.operations.observations import DatabaseObservationSink, get_observation_sink, record_safely
from app.settings import settings
from fastapi import HTTPException
from sqlalchemy import Engine, select, text
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine  # noqa: F401
from tests.test_gcs_media_storage import DATA, SHA, fixture_store

NOW = datetime(2026, 10, 6, tzinfo=UTC)


def media_event() -> OperationalObservation:
    return OperationalObservation(
        component="private_media_gcs",
        slot="latest_failure",
        outcome="media_write_failed",
        observed_at=NOW,
    )


def test_fixed_slot_updates_and_no_payload(customer_engine: Engine) -> None:
    sink = DatabaseObservationSink(customer_engine)
    for _ in range(3):
        sink.record(media_event())
    with Session(customer_engine) as db:
        rows = db.scalars(select(Record)).all()
        assert len(rows) == 1
        assert rows[0].occurrence_count == 3
        assert rows[0].outcome == "media_write_failed"
        assert rows[0].process_epoch is None


def test_concurrent_recording_and_customer_rollback(customer_engine: Engine) -> None:
    if customer_engine.dialect.name != "postgresql":
        pytest.skip("independent connections and concurrent transactions require PostgreSQL")
    sink = DatabaseObservationSink(customer_engine)
    with Session(customer_engine) as customer:
        customer.execute(text("SELECT 1"))
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda _: sink.record(media_event()), range(8)))
        customer.rollback()
    with Session(customer_engine) as db:
        row = db.get(Record, ("private_media_gcs", "latest_failure"))
        assert row is not None and row.occurrence_count == 8


def test_stale_scheduler_epoch_cannot_replace_current(customer_engine: Engine) -> None:
    sink = DatabaseObservationSink(customer_engine)

    def event(
        epoch: str, started: datetime, observed: datetime, completion: bool = False
    ) -> OperationalObservation:
        return OperationalObservation(
            component="scheduler_loop",
            slot="latest_completion" if completion else "latest_start",
            outcome="scheduler_cycle_completed" if completion else "scheduler_cycle_started",
            observed_at=observed,
            process_epoch=epoch * 32,
            epoch_started_at=started,
        )

    sink.record(event("a", NOW, NOW))
    sink.record(event("b", NOW + timedelta(seconds=1), NOW + timedelta(seconds=1)))
    sink.record(event("a", NOW, NOW + timedelta(seconds=2), True))
    sink.record(event("a", NOW, NOW + timedelta(seconds=3)))
    with Session(customer_engine) as db:
        row = db.get(Record, ("scheduler_loop", "latest_start"))
        assert row is not None and row.process_epoch == "b" * 32
        assert db.get(Record, ("scheduler_loop", "latest_completion")) is None


def test_telemetry_failure_preserves_customer_transaction(customer_engine: Engine) -> None:
    broken = MagicMock()
    broken.record.side_effect = RuntimeError("private provider credential fixture")
    with Session(customer_engine) as db:
        assert db.scalar(text("SELECT 7")) == 7
        record_safely(broken, media_event())
        assert db.scalar(text("SELECT 8")) == 8
        db.commit()


def test_actual_gcs_calls_record_without_extra_io_or_retry() -> None:
    store, client, _, blob = fixture_store()
    sink = MagicMock()
    wrapped = ObservedMediaStore(store, sink, "private_media_gcs", lambda: NOW)
    wrapped.put_if_absent(42, SHA, len(DATA), [DATA])
    assert wrapped.read_exact(42, SHA, len(DATA)) == DATA
    assert blob.upload_from_file.call_count == 1
    assert blob.download_to_file.call_count == 2
    assert client.get_bucket.call_count == 5
    assert [c.args[0].outcome for c in sink.record.call_args_list] == [
        "media_write_started",
        "media_write_completed",
        "media_read_started",
        "media_read_completed",
    ]
    blob.download_to_file.side_effect = RuntimeError("secret fixture")
    sink.record.side_effect = RuntimeError("telemetry secret fixture")
    with pytest.raises(OSError, match="private media read unavailable"):
        wrapped.read_exact(42, SHA, len(DATA))
    assert sink.record.call_args.args[0].outcome == "media_read_failed"


def test_media_factory_records_init_failure_without_probing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sink = MagicMock()
    monkeypatch.setattr(storage, "get_observation_sink", lambda: sink)
    monkeypatch.setattr(settings, "media_storage_mode", "local_dev")
    monkeypatch.setattr(settings, "media_local_directory", "relative-invalid")
    with pytest.raises(HTTPException, match="private media storage unavailable"):
        storage.get_media_store()
    assert sink.record.call_args.args[0].outcome == "media_init_failed"
    monkeypatch.setattr(settings, "media_storage_mode", "disabled")
    sink.reset_mock()
    with pytest.raises(HTTPException):
        storage.get_media_store()
    sink.record.assert_not_called()


def test_default_factory_opens_no_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "operational_observations_enabled", False)
    assert get_observation_sink() is None


@pytest.mark.parametrize("fail", [False, True])
def test_actual_scheduler_invocation_records_useful_completion_or_failure(fail: bool) -> None:
    sink = MagicMock()
    stop = Event()

    class StopAfterCycle(Event):
        def is_set(self) -> bool:
            return stop.is_set()

        def wait(self, timeout: float | None = None) -> bool:
            stop.set()
            return True

    def cycle(*args: Any, **kwargs: Any) -> None:
        if fail:
            raise RuntimeError("private fixture")

    runtime = SimpleNamespace(sync_interval_minutes=1, sync_run_immediately=True)
    scheduler.main(
        StopAfterCycle(),
        lambda: (runtime, object(), cycle),
        lambda *_: None,
        observation_factory=lambda: sink,
    )
    outcomes = [c.args[0].outcome for c in sink.record.call_args_list]
    assert outcomes == [
        "scheduler_cycle_started",
        "scheduler_cycle_failed" if fail else "scheduler_cycle_completed",
    ]
    if not fail:
        assert sink.record.call_args.args[0].expected_next_at is not None


def test_real_tick_reports_swallowed_stage_failure(
    monkeypatch: pytest.MonkeyPatch, customer_engine: Engine
) -> None:
    for path in (
        "app.shopify.privacy.purge_expired_facts",
        "app.shopify.privacy.run_privacy_tick",
        "app.shopify.sync.run_shopify_tick",
        "app.meta.sync.run_meta_tick",
        "app.analysis.cadence.run_analysis_tick",
    ):
        monkeypatch.setattr(path, lambda *_: None)
    monkeypatch.setattr("app.jobs.customer_runtime.run_customer_tick", lambda *_: {"crm": "failed"})
    assert scheduler._run_analysis_tick(customer_engine, None) is False


def test_operator_projection_is_explicitly_unobserved_then_sanitized(
    customer_engine: Engine,
) -> None:
    from app.operations.attention import attention

    with Session(customer_engine) as db:
        assert attention(db, NOW).runtime_observation_status == "unobserved"
    DatabaseObservationSink(customer_engine).record(media_event())
    with Session(customer_engine) as db:
        report = attention(db, NOW)
        assert report.runtime_observation_status == "observed"
        assert len(report.runtime_observations) == 1
        assert report.runtime_observations[0].outcome == "media_write_failed"
        assert "process_epoch" not in report.model_dump_json()
        assert "storage_observations_incomplete" in report.observation_gaps


def test_actual_sink_timeout_does_not_rollback_customer_work(customer_engine: Engine) -> None:
    if customer_engine.dialect.name != "postgresql":
        pytest.skip("actual independent telemetry lock timeout requires PostgreSQL")
    from app.workspaces.models import Workspace

    with Session(customer_engine) as blocker, Session(customer_engine) as customer:
        blocker.execute(text("SELECT pg_advisory_xact_lock(739214081)"))
        row = Workspace(
            slug="telemetry-rollback", name="fixture", client_name="fixture", status="active"
        )
        customer.add(row)
        customer.flush()
        record_safely(DatabaseObservationSink(customer_engine), media_event())
        customer.commit()
        assert customer.get(Workspace, row.id) is not None
        blocker.rollback()
    with Session(customer_engine) as db:
        assert db.get(Record, ("private_media_gcs", "latest_failure")) is None


def test_all_nine_slots_remain_bounded(customer_engine: Engine) -> None:
    sink = DatabaseObservationSink(customer_engine)
    for component in ("scheduler_loop", "private_media_local", "private_media_gcs"):
        for slot, suffix in (
            ("latest_start", "started"),
            ("latest_completion", "completed"),
            ("latest_failure", "failed"),
        ):
            values = dict(
                component=component,
                slot=slot,
                observed_at=NOW,
                outcome=("scheduler_cycle_" if component == "scheduler_loop" else "media_read_")
                + suffix,
            )
            if component == "scheduler_loop":
                values.update(process_epoch="a" * 32, epoch_started_at=NOW)
            observation = OperationalObservation.model_validate(values)
            sink.record(observation)
            sink.record(observation)
    with Session(customer_engine) as db:
        rows = list(db.scalars(select(Record)))
        assert len(rows) == 9
        assert all(row.occurrence_count == 2 for row in rows)


def test_scheduler_import_keeps_settings_inside_sanitized_startup() -> None:
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import app.jobs.google_ads_scheduler; "
            "assert 'app.settings' not in sys.modules",
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
