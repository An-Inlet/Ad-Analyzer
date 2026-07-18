import math
from collections.abc import Callable, Generator
from pathlib import Path
from threading import Event
from typing import Any

import pytest
from app.ads.enums import JobRunStatus
from app.ads.models import JobRun
from app.ads.repository import AdvertisingMetricsRepository
from app.ads.services import (
    GoogleAdsSyncError,
    GoogleAdsSyncResult,
    GoogleAdsSyncService,
    SyncFailureClassification,
)
from app.database.session import Base
from app.jobs import google_ads_scheduler, google_ads_sync_once
from app.jobs.reliability import (
    CycleOutcome,
    PostgreSQLAdvisoryLock,
    retry_delay,
    run_cycle,
)
from app.settings import Settings
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


@pytest.fixture()
def sqlite_engine() -> Generator[Any, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def relaxed_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PostgreSQLAdvisoryLock, "try_acquire", lambda self: True)
    monkeypatch.setattr(PostgreSQLAdvisoryLock, "release", lambda self: None)


def test_retry_delay_clamps_untrusted_jitter_values() -> None:
    settings = Settings(DENTICODE_SYNC_RETRY_BASE_SECONDS=5, DENTICODE_SYNC_RETRY_MAX_SECONDS=20)
    values: list[Any] = [0, 1, -5, 100, True, math.nan, math.inf, -math.inf, "bad"]

    def jitter_source(value: Any) -> Callable[[], Any]:
        def jitter() -> Any:
            return value

        return jitter

    delays = [retry_delay(1, settings, jitter_source(value)) for value in values]

    assert delays == [5.0, 5.5, 5.0, 5.5, 5.0, 5.0, 5.0, 5.0, 5.0]
    assert all(math.isfinite(delay) and 0 <= delay <= 20 for delay in delays)


def test_retry_delay_caps_exponential_without_unbounded_intermediate() -> None:
    settings = Settings(DENTICODE_SYNC_RETRY_BASE_SECONDS=5, DENTICODE_SYNC_RETRY_MAX_SECONDS=20)

    assert retry_delay(1, settings, lambda: 0) == 5.0
    assert retry_delay(2, settings, lambda: 0) == 10.0
    assert retry_delay(3, settings, lambda: 0) == 20.0
    assert retry_delay(10_000, settings, lambda: 1) == 20.0


def test_one_shot_overlap_skip_returns_documented_exit_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def run_cycle(*_args: object, **_kwargs: object) -> CycleOutcome:
        return CycleOutcome(skipped=True, result=None, attempts=0)

    assert (
        google_ads_sync_once.main(lambda: (Settings(), object(), run_cycle, JobRunStatus))
        == google_ads_sync_once.OVERLAP_EXIT_CODE
    )


def test_one_shot_success_returns_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    def run_cycle(*_args: object, **_kwargs: object) -> CycleOutcome:
        return CycleOutcome(
            skipped=False,
            result=GoogleAdsSyncResult(1, 0, JobRunStatus.SUCCEEDED),
            attempts=1,
        )

    assert (
        google_ads_sync_once.main(lambda: (Settings(), object(), run_cycle, JobRunStatus))
        == google_ads_sync_once.SUCCESS_EXIT_CODE
    )


def test_one_shot_failure_returns_one(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*_args: object, **_kwargs: object) -> CycleOutcome:
        raise GoogleAdsSyncError("Google Ads read-only sync failed (RuntimeError)")

    assert (
        google_ads_sync_once.main(lambda: (Settings(), object(), fail, JobRunStatus))
        == google_ads_sync_once.FAILURE_EXIT_CODE
    )


def test_scheduler_delays_first_cycle_when_immediate_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    settings = Settings(DENTICODE_SYNC_RUN_IMMEDIATELY=False, DENTICODE_SYNC_INTERVAL_MINUTES=5)
    monkeypatch.setattr("app.jobs.google_ads_scheduler.time.monotonic", lambda: 100.0)

    def run_cycle(*_args: object, **_kwargs: object) -> CycleOutcome:
        pytest.fail("cycle should not run before deadline")

    class StopBeforeDeadline(Event):
        def wait(self, timeout: float | None = None) -> bool:
            nonlocal calls
            calls += 1
            assert timeout == 300.0
            self.set()
            return True

    assert google_ads_scheduler.main(
        StopBeforeDeadline(), lambda: (settings, object(), run_cycle)
    ) == 0
    assert calls == 1


def test_scheduler_runs_immediately_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0
    settings = Settings(DENTICODE_SYNC_RUN_IMMEDIATELY=True, DENTICODE_SYNC_INTERVAL_MINUTES=5)
    monkeypatch.setattr("app.jobs.google_ads_scheduler.time.monotonic", lambda: 100.0)

    def run_once(*_args: object, **_kwargs: object) -> CycleOutcome:
        nonlocal calls
        calls += 1
        return CycleOutcome(skipped=True, result=None, attempts=0)

    class StopAfterCycle(Event):
        def wait(self, timeout: float | None = None) -> bool:
            assert timeout == 300.0
            self.set()
            return True

    assert google_ads_scheduler.main(StopAfterCycle(), lambda: (settings, object(), run_once)) == 0
    assert calls == 1


def test_run_cycle_uses_one_authoritative_job_run_across_retry(
    sqlite_engine: Any,
    relaxed_lock: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def sync_authoritative(self: Any, job_run: JobRun) -> GoogleAdsSyncResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise GoogleAdsSyncError(
                "Google Ads read-only sync failed (GoogleAdsRateLimitError)",
                classification=SyncFailureClassification.TRANSIENT_RATE_LIMIT,
            )
        AdvertisingMetricsRepository(self.session).finish_job_run(
            job_run,
            status=JobRunStatus.SUCCEEDED,
            records_processed=7,
        )
        self.session.commit()
        return GoogleAdsSyncResult(job_run.id, 7, JobRunStatus.SUCCEEDED)

    monkeypatch.setattr(
        "app.jobs.reliability.GoogleAdsSyncService.sync_authoritative_job_run",
        sync_authoritative,
    )

    outcome = run_cycle(
        Settings(
            DENTICODE_SYNC_MAX_ATTEMPTS=3,
            DENTICODE_SYNC_RETRY_BASE_SECONDS=1,
            DENTICODE_SYNC_RETRY_MAX_SECONDS=1,
        ),
        sqlite_engine,
        sleep=lambda _delay: None,
        random_value=lambda: 0,
    )

    assert outcome.attempts == 2
    with Session(sqlite_engine) as session:
        job_runs = session.scalars(select(JobRun)).all()
    assert [(job.status, job.records_processed) for job in job_runs] == [
        (JobRunStatus.SUCCEEDED, 7)
    ]


def test_run_cycle_retry_exhaustion_finalizes_one_failed_job_run(
    sqlite_engine: Any,
    relaxed_lock: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def always_fail(self: Any, _job_run: JobRun) -> GoogleAdsSyncResult:
        raise GoogleAdsSyncError(
            "Google Ads read-only sync failed (GoogleAdsRateLimitError)",
            classification=SyncFailureClassification.TRANSIENT_RATE_LIMIT,
        )

    monkeypatch.setattr(
        "app.jobs.reliability.GoogleAdsSyncService.sync_authoritative_job_run",
        always_fail,
    )

    with pytest.raises(GoogleAdsSyncError):
        run_cycle(
            Settings(
                DENTICODE_SYNC_MAX_ATTEMPTS=2,
                DENTICODE_SYNC_RETRY_BASE_SECONDS=1,
                DENTICODE_SYNC_RETRY_MAX_SECONDS=1,
            ),
            sqlite_engine,
            sleep=lambda _delay: None,
            random_value=lambda: 0,
        )

    with Session(sqlite_engine) as session:
        job_runs = session.scalars(select(JobRun)).all()
    assert len(job_runs) == 1
    assert job_runs[0].status is JobRunStatus.FAILED
    assert "attempts=2" in (job_runs[0].error_message or "")


def test_run_cycle_aborts_without_retry_after_lock_connection_loss(
    tmp_path: Any,
    relaxed_lock: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine(f"sqlite:///{(tmp_path / 'lock-loss.db').as_posix()}")
    Base.metadata.create_all(engine)
    calls = 0

    def lose_lock(self: Any, _job_run: JobRun) -> GoogleAdsSyncResult:
        nonlocal calls
        calls += 1
        raise GoogleAdsSyncError(
            "Google Ads synchronization lost advisory-lock ownership.",
            classification=SyncFailureClassification.UNKNOWN_COMMIT_OUTCOME,
            lock_lost=True,
        )

    monkeypatch.setattr(
        "app.jobs.reliability.GoogleAdsSyncService.sync_authoritative_job_run",
        lose_lock,
    )

    with pytest.raises(Exception, match="advisory-lock"):
        run_cycle(Settings(), engine, sleep=lambda _delay: pytest.fail("no retry sleep"))

    assert calls == 1
    with Session(engine) as session:
        job_run = session.scalars(select(JobRun)).one()
        assert job_run.status is JobRunStatus.FAILED
        assert job_run.error_message == "Google Ads synchronization lost advisory-lock ownership."
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_unknown_commit_outcome_does_not_retry_or_create_contradictory_failure(
    sqlite_engine: Any,
    relaxed_lock: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def unknown_commit(self: Any, _job_run: JobRun) -> GoogleAdsSyncResult:
        nonlocal calls
        calls += 1
        raise GoogleAdsSyncError(
            "Google Ads sync commit outcome is unknown; verify the latest job run before retrying",
            classification=SyncFailureClassification.UNKNOWN_COMMIT_OUTCOME,
        )

    monkeypatch.setattr(
        "app.jobs.reliability.GoogleAdsSyncService.sync_authoritative_job_run",
        unknown_commit,
    )

    with pytest.raises(GoogleAdsSyncError):
        run_cycle(
            Settings(DENTICODE_SYNC_MAX_ATTEMPTS=3),
            sqlite_engine,
            sleep=lambda _delay: pytest.fail("unknown commit must not retry"),
        )

    assert calls == 1
    with Session(sqlite_engine) as session:
        job_runs = session.scalars(select(JobRun)).all()
    assert len(job_runs) == 1
    assert job_runs[0].status is JobRunStatus.RUNNING


def test_stop_event_during_backoff_finalizes_and_prevents_next_attempt(
    sqlite_engine: Any,
    relaxed_lock: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def transient(self: Any, _job_run: JobRun) -> GoogleAdsSyncResult:
        nonlocal calls
        calls += 1
        raise GoogleAdsSyncError(
            "Google Ads read-only sync failed (GoogleAdsRateLimitError)",
            classification=SyncFailureClassification.TRANSIENT_RATE_LIMIT,
        )

    monkeypatch.setattr(
        "app.jobs.reliability.GoogleAdsSyncService.sync_authoritative_job_run",
        transient,
    )

    with pytest.raises(Exception, match="interrupted"):
        run_cycle(
            Settings(DENTICODE_SYNC_MAX_ATTEMPTS=3),
            sqlite_engine,
            wait=lambda _delay: True,
            random_value=lambda: 0,
        )

    assert calls == 1
    with Session(sqlite_engine) as session:
        job_run = session.scalars(select(JobRun)).one()
        assert job_run.status is JobRunStatus.FAILED
        assert job_run.error_message == "Google Ads synchronization interrupted before retry."


def test_service_maps_collector_retry_metadata_to_sync_classification() -> None:
    from app.collectors.google_ads import GoogleAdsIntegrationError

    service = GoogleAdsSyncService(Session(create_engine("sqlite://")))
    error = GoogleAdsIntegrationError(
        "Google Ads read-only request failed",
        retry_classification="TRANSIENT_NETWORK",
    )

    assert service._classify_failure(error) is SyncFailureClassification.TRANSIENT_NETWORK


def test_operational_health_resanitizes_legacy_failure_text(
    sqlite_engine: Any,
) -> None:
    from datetime import UTC, datetime

    from app.ads.enums import AdvertisingPlatform
    from app.ads.operations import sync_health

    secret = "client_secret=secret refresh_token=token Authorization: Bearer abc sql=SELECT *"
    with Session(sqlite_engine) as session:
        session.add(
            JobRun(
                platform=AdvertisingPlatform.GOOGLE_ADS,
                job_name="google_ads_read_only_sync",
                status=JobRunStatus.FAILED,
                started_at=datetime.now(UTC),
                finished_at=datetime.now(UTC),
                error_message=secret,
            )
        )
        session.commit()
        health = sync_health(session, Settings())

    assert health.last_failure_summary == "Google Ads synchronization failed."
    assert "secret" not in (health.last_failure_summary or "")
    assert "Bearer" not in (health.last_failure_summary or "")


def test_one_shot_startup_failure_is_sanitized() -> None:
    import os
    import subprocess
    import sys

    env = os.environ.copy()
    env["DENTICODE_SYNC_INTERVAL_MINUTES"] = "1"
    env["DENTICODE_API_TOKEN"] = "super-secret-token-value"

    completed = subprocess.run(
        [sys.executable, "-m", "app.jobs.google_ads_sync_once"],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    combined = completed.stdout + completed.stderr
    assert completed.returncode == google_ads_sync_once.FAILURE_EXIT_CODE
    assert "Traceback" not in combined
    assert "super-secret-token-value" not in combined
    assert "ValidationError" in combined
