import math
import os
from collections.abc import Callable, Generator
from pathlib import Path
from threading import Event
from typing import Any

import pytest
from app.ads.enums import JobRunStatus
from app.ads.models import JobRun
from app.ads.repository import AdvertisingMetricsRepository
from app.ads.services import (
    FAILED_JOB_RUN_UNKNOWN_COMMIT_OUTCOME_ERROR,
    GoogleAdsSyncError,
    GoogleAdsSyncResult,
    GoogleAdsSyncService,
    SyncFailureClassification,
)
from app.automation import AutomationControlKey, AutomationControlService
from app.database.session import Base
from app.jobs import google_ads_scheduler, google_ads_sync_once
from app.jobs.reliability import (
    LOCK_LOST_SYNC_ERROR,
    AdvisoryLockLostError,
    CycleOutcome,
    CycleSkipReason,
    PostgreSQLAdvisoryLock,
    retry_delay,
    run_cycle,
)
from app.settings import (
    InvalidSyncAdvisoryLockConfigError,
    Settings,
    SyncAdvisoryLockConfigError,
    _is_sync_lock_key_name,
    _resolve_lock_key_values,
)
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from tests.import_scope_helpers import seed_google_scope


@pytest.fixture(autouse=True)
def configured_import_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in {
        "INLET_GOOGLE_ADS_WORKSPACE_ID": "1",
        "INLET_GOOGLE_ADS_CONNECTION_ID": "1",
        "INLET_GOOGLE_ADS_ACCOUNT_ID": "1",
        "INLET_GOOGLE_ADS_CREDENTIALS_REFERENCE": "fixture-google-v1",
        "GOOGLE_ADS_CUSTOMER_ID": "acct-1",
    }.items():
        monkeypatch.setenv(name, value)


@pytest.fixture()
def sqlite_engine() -> Generator[Any, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_google_scope(session)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def relaxed_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    def acquire(self: PostgreSQLAdvisoryLock) -> bool:
        self.acquired = True
        return True

    monkeypatch.setattr(PostgreSQLAdvisoryLock, "try_acquire", acquire)
    monkeypatch.setattr(PostgreSQLAdvisoryLock, "release", lambda self: None)


def test_retry_delay_clamps_untrusted_jitter_values() -> None:
    settings = Settings(
        AD_ANALYZER_SYNC_RETRY_BASE_SECONDS=5,
        AD_ANALYZER_SYNC_RETRY_MAX_SECONDS=20,
    )
    values: list[Any] = [0, 1, -5, 100, True, math.nan, math.inf, -math.inf, "bad"]

    def jitter_source(value: Any) -> Callable[[], Any]:
        def jitter() -> Any:
            return value

        return jitter

    delays = [retry_delay(1, settings, jitter_source(value)) for value in values]

    assert delays == [5.0, 5.5, 5.0, 5.5, 5.0, 5.0, 5.0, 5.0, 5.0]
    assert all(math.isfinite(delay) and 0 <= delay <= 20 for delay in delays)


def test_retry_delay_caps_exponential_without_unbounded_intermediate() -> None:
    settings = Settings(
        AD_ANALYZER_SYNC_RETRY_BASE_SECONDS=5,
        AD_ANALYZER_SYNC_RETRY_MAX_SECONDS=20,
    )

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


def test_one_shot_master_disabled_is_a_successful_no_op() -> None:
    def run_cycle(*_args: object, **_kwargs: object) -> CycleOutcome:
        return CycleOutcome(
            skipped=True,
            result=None,
            attempts=0,
            skip_reason=CycleSkipReason.DISABLED,
        )

    assert (
        google_ads_sync_once.main(
            lambda: (Settings(), object(), run_cycle, JobRunStatus),
            lambda *_args: pytest.fail("a disabled sync must not start post-sync analysis"),
        )
        == google_ads_sync_once.SUCCESS_EXIT_CODE
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


def test_failed_google_cycle_still_runs_independent_source_and_analysis_tick(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = object()
    ticks: list[object] = []

    def fail(*_args: object, **_kwargs: object) -> CycleOutcome:
        raise RuntimeError("source unavailable")

    monkeypatch.setattr(
        google_ads_scheduler, "_run_analysis_tick", lambda value, _: ticks.append(value)
    )
    result = google_ads_sync_once.main(lambda: (Settings(), engine, fail, JobRunStatus))
    assert result == google_ads_sync_once.FAILURE_EXIT_CODE
    assert ticks == [engine]


def test_scheduler_delays_first_cycle_when_immediate_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    settings = Settings(AD_ANALYZER_SYNC_RUN_IMMEDIATELY=False, AD_ANALYZER_SYNC_INTERVAL_MINUTES=5)
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

    assert (
        google_ads_scheduler.main(StopBeforeDeadline(), lambda: (settings, object(), run_cycle))
        == 0
    )
    assert calls == 1


def test_scheduler_runs_immediately_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0
    settings = Settings(AD_ANALYZER_SYNC_RUN_IMMEDIATELY=True, AD_ANALYZER_SYNC_INTERVAL_MINUTES=5)
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


def test_scheduler_disabled_cycle_still_runs_local_analysis_tick(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(AD_ANALYZER_SYNC_RUN_IMMEDIATELY=True, AD_ANALYZER_SYNC_INTERVAL_MINUTES=5)
    monkeypatch.setattr("app.jobs.google_ads_scheduler.time.monotonic", lambda: 100.0)
    disabled = CycleOutcome(
        skipped=True,
        result=None,
        attempts=0,
        skip_reason=CycleSkipReason.DISABLED,
    )
    analysis_outcomes: list[CycleOutcome | None] = []

    def run_once(*_args: object, **_kwargs: object) -> CycleOutcome:
        return disabled

    class StopAfterCycle(Event):
        def wait(self, timeout: float | None = None) -> bool:
            assert timeout == 300.0
            self.set()
            return True

    assert (
        google_ads_scheduler.main(
            StopAfterCycle(),
            lambda: (settings, object(), run_once),
            lambda _engine, outcome: analysis_outcomes.append(outcome),
        )
        == google_ads_scheduler.SUCCESS_EXIT_CODE
    )
    assert analysis_outcomes == [disabled]


def test_master_sync_control_blocks_cycle_before_lock_or_job_run(
    sqlite_engine: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with Session(sqlite_engine) as session:
        AutomationControlService(session).set_master(
            AutomationControlKey.ALL_DATA_SYNCS,
            enabled=False,
            actor="platform@example.com",
        )
        session.commit()

    monkeypatch.setattr(
        PostgreSQLAdvisoryLock,
        "try_acquire",
        lambda _lock: pytest.fail("disabled sync must not acquire its worker lock"),
    )

    outcome = run_cycle(Settings(), sqlite_engine)

    assert outcome == CycleOutcome(
        skipped=True,
        result=None,
        attempts=0,
        skip_reason=CycleSkipReason.DISABLED,
    )
    with Session(sqlite_engine) as session:
        assert session.scalars(select(JobRun)).all() == []


def test_run_cycle_uses_one_authoritative_job_run_across_retry(
    sqlite_engine: Any,
    relaxed_lock: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def sync_authoritative(self: Any, job_run: JobRun, **_kwargs: object) -> GoogleAdsSyncResult:
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
            AD_ANALYZER_SYNC_MAX_ATTEMPTS=3,
            AD_ANALYZER_SYNC_RETRY_BASE_SECONDS=1,
            AD_ANALYZER_SYNC_RETRY_MAX_SECONDS=1,
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
    def always_fail(self: Any, _job_run: JobRun, **_kwargs: object) -> GoogleAdsSyncResult:
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
                AD_ANALYZER_SYNC_MAX_ATTEMPTS=2,
                AD_ANALYZER_SYNC_RETRY_BASE_SECONDS=1,
                AD_ANALYZER_SYNC_RETRY_MAX_SECONDS=1,
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
    with Session(engine) as scoped_session:
        seed_google_scope(scoped_session)
    calls = 0

    def lose_lock(self: Any, _job_run: JobRun, **_kwargs: object) -> GoogleAdsSyncResult:
        nonlocal calls
        calls += 1
        raise GoogleAdsSyncError(
            "Google Ads synchronization lost advisory-lock ownership.",
            classification=SyncFailureClassification.TRANSIENT_DATABASE,
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

    def unknown_commit(self: Any, _job_run: JobRun, **_kwargs: object) -> GoogleAdsSyncResult:
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
            Settings(AD_ANALYZER_SYNC_MAX_ATTEMPTS=3),
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

    def transient(self: Any, _job_run: JobRun, **_kwargs: object) -> GoogleAdsSyncResult:
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
            Settings(AD_ANALYZER_SYNC_MAX_ATTEMPTS=3),
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
                workspace_id=1,
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
    env["AD_ANALYZER_SYNC_INTERVAL_MINUTES"] = "1"
    env["AD_ANALYZER_API_TOKEN"] = "super-secret-token-value"

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


def test_unknown_commit_with_lock_loss_does_not_replacement_finalize(
    tmp_path: Any,
    relaxed_lock: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sqlite_engine = create_engine(f"sqlite:///{(tmp_path / 'unknown-lock-loss.db').as_posix()}")
    Base.metadata.create_all(sqlite_engine)
    with Session(sqlite_engine) as scoped_session:
        seed_google_scope(scoped_session)
    calls = 0
    fresh_finalize_calls = 0

    def unknown_and_lost(self: Any, _job_run: JobRun, **_kwargs: object) -> GoogleAdsSyncResult:
        nonlocal calls
        calls += 1
        raise GoogleAdsSyncError(
            "Google Ads sync commit outcome is unknown; verify the latest job run before retrying",
            classification=SyncFailureClassification.UNKNOWN_COMMIT_OUTCOME,
            lock_lost=True,
        )

    def fail_if_replacement_finalize(*_args: object, **_kwargs: object) -> None:
        nonlocal fresh_finalize_calls
        fresh_finalize_calls += 1
        pytest.fail("unknown commit outcome must not use replacement finalization")

    monkeypatch.setattr(
        "app.jobs.reliability.GoogleAdsSyncService.sync_authoritative_job_run",
        unknown_and_lost,
    )
    monkeypatch.setattr(
        "app.jobs.reliability._finalize_failed_job_run_on_engine",
        fail_if_replacement_finalize,
    )

    with pytest.raises(GoogleAdsSyncError) as exc_info:
        run_cycle(
            Settings(AD_ANALYZER_SYNC_MAX_ATTEMPTS=3),
            sqlite_engine,
            sleep=lambda _delay: pytest.fail("unknown commit must not retry"),
        )

    assert exc_info.value.classification is SyncFailureClassification.UNKNOWN_COMMIT_OUTCOME
    assert calls == 1
    assert fresh_finalize_calls == 0
    with Session(sqlite_engine) as session:
        job_runs = session.scalars(select(JobRun)).all()
    assert len(job_runs) == 1
    assert job_runs[0].status is JobRunStatus.RUNNING
    Base.metadata.drop_all(sqlite_engine)
    sqlite_engine.dispose()


def test_stop_requested_before_lock_acquisition_skips_all_work(
    sqlite_engine: Any,
    relaxed_lock: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.jobs.reliability.GoogleAdsSyncService.sync_authoritative_job_run",
        lambda *_args, **_kwargs: pytest.fail("collector must not run after stop"),
    )

    with pytest.raises(Exception, match="interrupted"):
        run_cycle(Settings(), sqlite_engine, stop_requested=lambda: True)

    with Session(sqlite_engine) as session:
        assert session.scalars(select(JobRun)).all() == []


def test_stop_requested_after_running_job_run_prevents_first_collector(
    sqlite_engine: Any,
    relaxed_lock: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checks = iter([False, True])
    monkeypatch.setattr(
        "app.jobs.reliability.GoogleAdsSyncService.sync_authoritative_job_run",
        lambda *_args, **_kwargs: pytest.fail("collector must not run after stop"),
    )

    with pytest.raises(Exception, match="interrupted"):
        run_cycle(Settings(), sqlite_engine, stop_requested=lambda: next(checks, True))

    with Session(sqlite_engine) as session:
        job_run = session.scalars(select(JobRun)).one()
        assert job_run.status is JobRunStatus.FAILED
        assert job_run.error_message == "Google Ads synchronization interrupted before retry."


def test_stop_requested_after_retry_wait_prevents_later_collector(
    sqlite_engine: Any,
    relaxed_lock: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    stopped = False

    def transient(self: Any, _job_run: JobRun, **_kwargs: object) -> GoogleAdsSyncResult:
        nonlocal calls
        calls += 1
        raise GoogleAdsSyncError(
            "Google Ads read-only sync failed (GoogleAdsRateLimitError)",
            classification=SyncFailureClassification.TRANSIENT_RATE_LIMIT,
        )

    def wait(_delay: float) -> bool:
        nonlocal stopped
        stopped = True
        return False

    monkeypatch.setattr(
        "app.jobs.reliability.GoogleAdsSyncService.sync_authoritative_job_run",
        transient,
    )

    with pytest.raises(Exception, match="interrupted"):
        run_cycle(
            Settings(AD_ANALYZER_SYNC_MAX_ATTEMPTS=3),
            sqlite_engine,
            wait=wait,
            stop_requested=lambda: stopped,
            random_value=lambda: 0,
        )

    assert calls == 1
    with Session(sqlite_engine) as session:
        job_run = session.scalars(select(JobRun)).one()
        assert job_run.status is JobRunStatus.FAILED


@pytest.mark.parametrize(
    ("stored_message", "expected"),
    [
        ("Google Ads synchronization interrupted before retry.", None),
        (
            "Google Ads sync commit outcome is unknown; verify the latest job run before retrying",
            None,
        ),
        ("Google Ads read-only sync failed (GoogleAdsRateLimitError); attempts=2", None),
        ("Google Ads read-only sync failed (GoogleAdsAuthenticationError)", None),
        ("Google Ads read-only sync failed (/home/app/.env password=hunter2)", None),
        ("Google Ads read-only sync failed (api_key=abc)", None),
        ("Google Ads read-only sync failed (Bearer secret)", None),
        ("SELECT * FROM credentials", None),
        ("Traceback ...", None),
        (r"C:\secrets\.env", None),
        ("https://example.test/?token=secret", None),
        ("x" * 1000, None),
        ("Google Ads synchronization interrupted before retry.x", None),
    ],
)
def test_public_failure_summary_allows_only_exact_safe_messages(
    stored_message: str,
    expected: str | None,
) -> None:
    from app.ads.operations import public_failure_summary

    generic = "Google Ads synchronization failed."
    assert public_failure_summary(stored_message) == (expected or generic)


@pytest.mark.parametrize(
    ("raw_error", "expected_calls"),
    [
        (RuntimeError("RESOURCE_EXHAUSTED quota exceeded"), 2),
        (RuntimeError("500 internal server error"), 2),
        (RuntimeError("502 backend error"), 2),
        (RuntimeError("503 unavailable"), 2),
        (RuntimeError("504 deadline exceeded"), 2),
        (TimeoutError("request timeout secret-token"), 2),
        (OSError("temporary transport failure"), 2),
        (RuntimeError("UNAUTHENTICATED invalid credentials"), 1),
        (RuntimeError("PERMISSION_DENIED customer not authorized"), 1),
        (RuntimeError("INVALID_CUSTOMER_ID"), 1),
        (RuntimeError("unknown raw google payload secret"), 1),
    ],
)
def test_run_cycle_preserves_collector_normalization_attempt_counts(
    sqlite_engine: Any,
    relaxed_lock: None,
    monkeypatch: pytest.MonkeyPatch,
    raw_error: Exception,
    expected_calls: int,
) -> None:
    from app.collectors import google_ads

    calls = 0

    class FailingService:
        def search(self, **_kwargs: object) -> list[object]:
            nonlocal calls
            calls += 1
            raise raw_error

    monkeypatch.setattr(
        google_ads, "_google_ads_service", lambda _settings: (FailingService(), "1")
    )
    monkeypatch.setattr(google_ads, "collect_campaigns", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(google_ads, "collect_ad_groups", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(google_ads, "collect_ads", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(google_ads, "collect_keywords", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(google_ads, "collect_search_terms", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(google_ads, "collect_metrics", lambda *_args, **_kwargs: [])

    with pytest.raises(GoogleAdsSyncError) as exc_info:
        run_cycle(
            Settings(AD_ANALYZER_SYNC_MAX_ATTEMPTS=2, AD_ANALYZER_SYNC_RETRY_BASE_SECONDS=1),
            sqlite_engine,
            sleep=lambda _delay: None,
            random_value=lambda: 0,
        )

    assert calls == expected_calls
    assert "secret" not in str(exc_info.value)
    with Session(sqlite_engine) as session:
        job_run = session.scalars(select(JobRun)).one()
        assert job_run.status is JobRunStatus.FAILED
        assert "secret" not in (job_run.error_message or "")


def test_initial_running_commit_unknown_is_primary_and_not_unlocked(
    sqlite_engine: Any,
    relaxed_lock: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unlock_calls = 0

    def unknown_create(_session: Session, _scope: object) -> JobRun:
        raise GoogleAdsSyncError(
            "Google Ads sync commit outcome is unknown; verify the latest job run before retrying",
            classification=SyncFailureClassification.UNKNOWN_COMMIT_OUTCOME,
            lock_lost=True,
        )

    def release(self: PostgreSQLAdvisoryLock) -> None:
        nonlocal unlock_calls
        unlock_calls += 1
        if self.acquired:
            pytest.fail("must not unlock after invalidated unknown initial commit")

    monkeypatch.setattr("app.jobs.reliability._create_authoritative_job_run", unknown_create)
    monkeypatch.setattr(PostgreSQLAdvisoryLock, "release", release)
    monkeypatch.setattr(
        "app.jobs.reliability.GoogleAdsSyncService.sync_authoritative_job_run",
        lambda *_args, **_kwargs: pytest.fail("collector must not run after unknown create"),
    )

    with pytest.raises(GoogleAdsSyncError) as exc_info:
        run_cycle(Settings(), sqlite_engine)

    assert exc_info.value.classification is SyncFailureClassification.UNKNOWN_COMMIT_OUTCOME
    assert unlock_calls == 1


def test_failed_finalization_unknown_is_primary_and_no_replacement_finalize(
    sqlite_engine: Any,
    relaxed_lock: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collector_calls = 0
    replacement_calls = 0

    def permanent(self: Any, _job_run: JobRun, **_kwargs: object) -> GoogleAdsSyncResult:
        nonlocal collector_calls
        collector_calls += 1
        raise GoogleAdsSyncError(
            "Google Ads read-only sync failed (ValueError)",
            classification=SyncFailureClassification.PERMANENT_VALIDATION,
        )

    def unknown_finalize(*_args: object, **_kwargs: object) -> None:
        raise GoogleAdsSyncError(
            "Google Ads sync failed; the failure-record commit outcome is unknown "
            "and must be verified before retrying",
            classification=SyncFailureClassification.UNKNOWN_COMMIT_OUTCOME,
            lock_lost=True,
        )

    def replacement(*_args: object, **_kwargs: object) -> None:
        nonlocal replacement_calls
        replacement_calls += 1
        pytest.fail("unknown finalization must not use replacement finalization")

    monkeypatch.setattr(
        "app.jobs.reliability.GoogleAdsSyncService.sync_authoritative_job_run", permanent
    )
    monkeypatch.setattr("app.jobs.reliability._finalize_failed_job_run", unknown_finalize)
    monkeypatch.setattr("app.jobs.reliability._finalize_failed_job_run_on_engine", replacement)

    with pytest.raises(GoogleAdsSyncError) as exc_info:
        run_cycle(Settings(), sqlite_engine)

    assert exc_info.value.classification is SyncFailureClassification.UNKNOWN_COMMIT_OUTCOME
    assert collector_calls == 1
    assert replacement_calls == 0


def test_stop_after_account_collector_prevents_campaign_collector(
    sqlite_engine: Any,
    relaxed_lock: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.ads.enums import AdvertisingPlatform
    from app.ads.schemas import AdvertisingAccountCreate
    from app.collectors import google_ads

    account_calls = 0
    campaign_calls = 0

    def collect_account(*_args: object, **_kwargs: object) -> AdvertisingAccountCreate:
        nonlocal account_calls
        account_calls += 1
        return AdvertisingAccountCreate(
            workspace_id=1,
            platform=AdvertisingPlatform.GOOGLE_ADS,
            external_account_id="acct-1",
            name="Acct",
            currency_code="USD",
            time_zone="UTC",
        )

    def collect_campaigns(*_args: object, **_kwargs: object) -> list[object]:
        nonlocal campaign_calls
        campaign_calls += 1
        pytest.fail("campaign collector must not run after stop")

    monkeypatch.setattr(google_ads, "collect_account", collect_account)
    monkeypatch.setattr(google_ads, "collect_campaigns", collect_campaigns)

    with pytest.raises(Exception, match="interrupted"):
        run_cycle(
            Settings(),
            sqlite_engine,
            stop_requested=lambda: account_calls > 0,
        )

    assert account_calls == 1
    assert campaign_calls == 0


def test_lock_loss_after_account_collector_prevents_campaign_collector(
    tmp_path: Any,
    relaxed_lock: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sqlite_engine = create_engine(f"sqlite:///{(tmp_path / 'collector-lock-loss.db').as_posix()}")
    Base.metadata.create_all(sqlite_engine)
    with Session(sqlite_engine) as scoped_session:
        seed_google_scope(scoped_session)
    from app.ads.enums import AdvertisingPlatform
    from app.ads.schemas import AdvertisingAccountCreate
    from app.collectors import google_ads

    checks = iter([True, False])
    account_calls = 0
    campaign_calls = 0

    def collect_account(*_args: object, **_kwargs: object) -> AdvertisingAccountCreate:
        nonlocal account_calls
        account_calls += 1
        return AdvertisingAccountCreate(
            workspace_id=1,
            platform=AdvertisingPlatform.GOOGLE_ADS,
            external_account_id="acct-1",
            name="Acct",
            currency_code="USD",
            time_zone="UTC",
        )

    def collect_campaigns(*_args: object, **_kwargs: object) -> list[object]:
        nonlocal campaign_calls
        campaign_calls += 1
        pytest.fail("campaign collector must not run after lock loss")

    monkeypatch.setattr(google_ads, "collect_account", collect_account)
    monkeypatch.setattr(google_ads, "collect_campaigns", collect_campaigns)
    monkeypatch.setattr(
        PostgreSQLAdvisoryLock,
        "owns_current_session",
        lambda _self, _session: next(checks, False),
    )

    with pytest.raises(Exception, match="advisory-lock"):
        run_cycle(Settings(), sqlite_engine)

    assert account_calls == 1
    assert campaign_calls == 0
    Base.metadata.drop_all(sqlite_engine)
    sqlite_engine.dispose()


@pytest.fixture()
def sqlite_file_engine(tmp_path: Path) -> Generator[Any, None, None]:
    engine = create_engine(f"sqlite:///{tmp_path / 'phase7.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_google_scope(session)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_failed_finalization_pre_commit_lock_loss_uses_fresh_connection(
    sqlite_file_engine: Any,
    relaxed_lock: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collector_calls = 0
    finalize_calls = 0
    unlock_calls = 0
    real_finalize = __import__(
        "app.jobs.reliability", fromlist=["_finalize_failed_job_run"]
    )._finalize_failed_job_run

    def permanent(self: Any, _job_run: JobRun, **_kwargs: object) -> GoogleAdsSyncResult:
        nonlocal collector_calls
        collector_calls += 1
        raise GoogleAdsSyncError(
            "Google Ads read-only sync failed (ValueError)",
            classification=SyncFailureClassification.PERMANENT_VALIDATION,
        )

    def flaky_finalize(
        session: Session, job_run: JobRun, exc: BaseException, attempts: int
    ) -> None:
        nonlocal finalize_calls
        finalize_calls += 1
        if finalize_calls == 1:
            raise AdvisoryLockLostError(LOCK_LOST_SYNC_ERROR)
        real_finalize(session, job_run, exc, attempts)

    def release(self: PostgreSQLAdvisoryLock) -> None:
        nonlocal unlock_calls
        unlock_calls += 1
        if self.acquired:
            pytest.fail("invalidated lock must not be unlocked")

    monkeypatch.setattr(
        "app.jobs.reliability.GoogleAdsSyncService.sync_authoritative_job_run", permanent
    )
    monkeypatch.setattr("app.jobs.reliability._finalize_failed_job_run", flaky_finalize)
    monkeypatch.setattr(PostgreSQLAdvisoryLock, "release", release)

    with pytest.raises(GoogleAdsSyncError):
        run_cycle(Settings(), sqlite_file_engine)

    assert collector_calls == 1
    assert finalize_calls == 2
    assert unlock_calls == 1
    with Session(sqlite_file_engine) as session:
        job_runs = session.scalars(select(JobRun)).all()
        assert len(job_runs) == 1
        assert job_runs[0].status is JobRunStatus.FAILED
        assert job_runs[0].error_message is not None
        assert job_runs[0].error_message == (
            "Google Ads read-only sync failed (ValueError); attempts=1"
        )
        assert "secret" not in job_runs[0].error_message


def test_failed_finalization_post_commit_unknown_does_not_replace_or_retry(
    sqlite_file_engine: Any,
    relaxed_lock: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collector_calls = 0
    replacement_calls = 0

    def permanent(self: Any, _job_run: JobRun, **_kwargs: object) -> GoogleAdsSyncResult:
        nonlocal collector_calls
        collector_calls += 1
        raise GoogleAdsSyncError(
            "Google Ads read-only sync failed (ValueError)",
            classification=SyncFailureClassification.PERMANENT_VALIDATION,
        )

    def unknown_finalize(
        _session: Session, _job_run: JobRun, _exc: BaseException, _attempts: int
    ) -> None:
        raise GoogleAdsSyncError(
            FAILED_JOB_RUN_UNKNOWN_COMMIT_OUTCOME_ERROR,
            classification=SyncFailureClassification.UNKNOWN_COMMIT_OUTCOME,
            lock_lost=True,
        )

    def replacement(*_args: object, **_kwargs: object) -> None:
        nonlocal replacement_calls
        replacement_calls += 1
        pytest.fail("unknown commit outcome must not be replacement-finalized")

    monkeypatch.setattr(
        "app.jobs.reliability.GoogleAdsSyncService.sync_authoritative_job_run", permanent
    )
    monkeypatch.setattr("app.jobs.reliability._finalize_failed_job_run", unknown_finalize)
    monkeypatch.setattr("app.jobs.reliability._finalize_failed_job_run_on_engine", replacement)

    with pytest.raises(GoogleAdsSyncError) as exc_info:
        run_cycle(Settings(), sqlite_file_engine)

    assert exc_info.value.classification is SyncFailureClassification.UNKNOWN_COMMIT_OUTCOME
    assert collector_calls == 1
    assert replacement_calls == 0
    with Session(sqlite_file_engine) as session:
        job_runs = session.scalars(select(JobRun)).all()
        assert len(job_runs) == 1
        assert job_runs[0].status is JobRunStatus.RUNNING


def test_fresh_replacement_unknown_outcome_is_primary_and_not_retried(
    sqlite_file_engine: Any,
    relaxed_lock: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collector_calls = 0
    finalize_calls = 0
    real_finalize = __import__(
        "app.jobs.reliability", fromlist=["_finalize_failed_job_run"]
    )._finalize_failed_job_run

    def permanent(self: Any, _job_run: JobRun, **_kwargs: object) -> GoogleAdsSyncResult:
        nonlocal collector_calls
        collector_calls += 1
        raise GoogleAdsSyncError(
            "Google Ads read-only sync failed (ValueError)",
            classification=SyncFailureClassification.PERMANENT_VALIDATION,
        )

    def flaky_finalize(
        session: Session, job_run: JobRun, exc: BaseException, attempts: int
    ) -> None:
        nonlocal finalize_calls
        finalize_calls += 1
        if finalize_calls == 1:
            raise AdvisoryLockLostError(LOCK_LOST_SYNC_ERROR)
        if finalize_calls == 2:
            raise GoogleAdsSyncError(
                FAILED_JOB_RUN_UNKNOWN_COMMIT_OUTCOME_ERROR,
                classification=SyncFailureClassification.UNKNOWN_COMMIT_OUTCOME,
                lock_lost=True,
            )
        real_finalize(session, job_run, exc, attempts)

    monkeypatch.setattr(
        "app.jobs.reliability.GoogleAdsSyncService.sync_authoritative_job_run", permanent
    )
    monkeypatch.setattr("app.jobs.reliability._finalize_failed_job_run", flaky_finalize)

    with pytest.raises(GoogleAdsSyncError) as exc_info:
        run_cycle(Settings(), sqlite_file_engine)

    assert exc_info.value.classification is SyncFailureClassification.UNKNOWN_COMMIT_OUTCOME
    assert collector_calls == 1
    assert finalize_calls == 2
    with Session(sqlite_file_engine) as session:
        assert len(session.scalars(select(JobRun)).all()) == 1


def test_job_run_response_schema_accepts_generic_public_failure_message() -> None:
    from app.ads.operations import PUBLIC_SYNC_FAILURE_SUMMARY
    from app.api.schemas import JobRunResponse

    response = JobRunResponse(
        workspace_id=1,
        id=1,
        platform="google_ads",
        account_id=None,
        job_name="google_ads_read_only_sync",
        status="failed",
        started_at="2026-07-18T00:00:00Z",
        finished_at="2026-07-18T00:01:00Z",
        records_processed=0,
        error_message=PUBLIC_SYNC_FAILURE_SUMMARY,
    )

    assert response.error_message == "Google Ads synchronization failed."
    with pytest.raises(ValidationError):
        JobRunResponse(
            workspace_id=1,
            id=1,
            platform="google_ads",
            account_id=None,
            job_name="google_ads_read_only_sync",
            status="failed",
            started_at="2026-07-18T00:00:00Z",
            finished_at="2026-07-18T00:01:00Z",
            records_processed=0,
            error_message="x" * 161,
        )


def test_job_run_response_uses_shared_public_failure_summary() -> None:
    from datetime import UTC, datetime

    from app.ads.enums import AdvertisingPlatform
    from app.ads.operations import PUBLIC_SYNC_FAILURE_SUMMARY
    from app.api.v1 import job_run_response

    job_run = JobRun(
        workspace_id=1,
        id=1,
        platform=AdvertisingPlatform.GOOGLE_ADS,
        account_id=None,
        job_name="google_ads_read_only_sync",
        status=JobRunStatus.FAILED,
        started_at=datetime(2026, 7, 18, tzinfo=UTC),
        finished_at=datetime(2026, 7, 18, tzinfo=UTC),
        records_processed=0,
        error_message="Google Ads read-only sync failed (Bearer secret)",
    )

    response = job_run_response(job_run)

    assert response.error_message == PUBLIC_SYNC_FAILURE_SUMMARY
    assert response.error_message != "Advertising sync failed."


def test_pre_attempt_shutdown_finalizes_authoritative_job_run_once(
    sqlite_engine: Any,
    relaxed_lock: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checks = 0
    finalize_calls = 0
    real_finalize = __import__(
        "app.jobs.reliability", fromlist=["_finalize_failed_job_run"]
    )._finalize_failed_job_run

    def stop_requested() -> bool:
        nonlocal checks
        checks += 1
        return checks >= 2

    def finalize_once(session: Session, job_run: JobRun, exc: BaseException, attempts: int) -> None:
        nonlocal finalize_calls
        finalize_calls += 1
        if finalize_calls > 1:
            raise GoogleAdsSyncError(
                FAILED_JOB_RUN_UNKNOWN_COMMIT_OUTCOME_ERROR,
                classification=SyncFailureClassification.UNKNOWN_COMMIT_OUTCOME,
            )
        real_finalize(session, job_run, exc, attempts)

    monkeypatch.setattr("app.jobs.reliability._finalize_failed_job_run", finalize_once)
    monkeypatch.setattr(
        "app.jobs.reliability.GoogleAdsSyncService.sync_authoritative_job_run",
        lambda *_args, **_kwargs: pytest.fail("collector must not run after shutdown"),
    )

    with pytest.raises(Exception, match="interrupted"):
        run_cycle(Settings(), sqlite_engine, stop_requested=stop_requested)

    assert finalize_calls == 1
    with Session(sqlite_engine) as session:
        job_run = session.scalars(select(JobRun)).one()
        assert job_run.status is JobRunStatus.FAILED
        assert job_run.error_message == "Google Ads synchronization interrupted before retry."


@pytest.mark.parametrize(
    ("error", "expected_fragment"),
    [
        (
            GoogleAdsSyncError(
                "Google Ads read-only sync failed (GoogleAdsRateLimitError)",
                classification=SyncFailureClassification.TRANSIENT_RATE_LIMIT,
            ),
            "GoogleAdsRateLimitError",
        ),
        (
            GoogleAdsSyncError(
                "Google Ads read-only sync failed (TimeoutError)",
                classification=SyncFailureClassification.TRANSIENT_NETWORK,
            ),
            "TimeoutError",
        ),
        (
            GoogleAdsSyncError(
                "Google Ads read-only sync failed (GoogleAdsAuthenticationError)",
                classification=SyncFailureClassification.PERMANENT_AUTH,
            ),
            "GoogleAdsAuthenticationError",
        ),
        (
            GoogleAdsSyncError(
                "Google Ads read-only sync failed (ValueError)",
                classification=SyncFailureClassification.PERMANENT_VALIDATION,
            ),
            "ValueError",
        ),
        (
            GoogleAdsSyncError(
                "Google Ads read-only sync failed (GoogleAdsRateLimitError)",
                classification=SyncFailureClassification.TRANSIENT_RATE_LIMIT,
            ),
            "attempts=3",
        ),
    ],
)
def test_google_ads_sync_error_internal_summary_is_preserved(
    error: GoogleAdsSyncError,
    expected_fragment: str,
) -> None:
    from app.jobs.reliability import _safe_failure_summary

    summary = _safe_failure_summary(error, 3)

    assert expected_fragment in summary
    assert "GoogleAdsSyncError" not in summary
    assert len(summary) <= 120


@pytest.mark.parametrize(
    "error",
    [
        ValueError("refresh_token=secret-value"),
        RuntimeError("Authorization: Bearer secret-value"),
        __import__("sqlalchemy.exc", fromlist=["OperationalError"]).OperationalError(
            "SELECT * FROM credentials WHERE token='secret'", {}, Exception("secret")
        ),
    ],
)
def test_raw_exception_internal_summary_never_copies_secret_text(error: Exception) -> None:
    from app.jobs.reliability import _safe_failure_summary

    summary = _safe_failure_summary(error, 1)

    assert "secret" not in summary
    assert "SELECT" not in summary
    assert "Authorization" not in summary
    assert "refresh_token" not in summary
    assert len(summary) <= 120


class _FakeDialect:
    name = "postgresql"


class _FakeAdvisoryConnection:
    dialect = _FakeDialect()
    invalidated = False

    def __init__(self, scalars: list[object], *, commit_fails: bool = False) -> None:
        self.scalars = scalars
        self.commit_fails = commit_fails
        self.commits = 0
        self.rollbacks = 0
        self.invalidations = 0
        self._in_transaction = False

    def scalar(self, *_args: object, **_kwargs: object) -> object:
        self._in_transaction = True
        return self.scalars.pop(0)

    def in_transaction(self) -> bool:
        return self._in_transaction

    def commit(self) -> None:
        self.commits += 1
        if self.commit_fails:
            raise RuntimeError("commit failed")
        self._in_transaction = False

    def rollback(self) -> None:
        self.rollbacks += 1
        self._in_transaction = False

    def invalidate(self) -> None:
        self.invalidated = True
        self.invalidations += 1
        self._in_transaction = False


def test_advisory_lock_acquisition_and_unlock_end_raw_transactions() -> None:
    connection = _FakeAdvisoryConnection([True, 123, True])
    lock = PostgreSQLAdvisoryLock(connection, 12345)  # type: ignore[arg-type]

    assert lock.try_acquire() is True
    assert lock.acquired is True
    assert lock.backend_pid == 123
    assert connection.commits == 1
    assert connection.in_transaction() is False

    lock.release()

    assert lock.acquired is False
    assert connection.commits == 2
    assert connection.in_transaction() is False
    assert connection.invalidations == 0


def test_advisory_lock_overlap_skip_ends_raw_transaction() -> None:
    connection = _FakeAdvisoryConnection([False])
    lock = PostgreSQLAdvisoryLock(connection, 12345)  # type: ignore[arg-type]

    assert lock.try_acquire() is False
    assert lock.acquired is False
    assert connection.commits == 1
    assert connection.in_transaction() is False


def test_advisory_lock_acquisition_commit_failure_invalidates_connection() -> None:
    connection = _FakeAdvisoryConnection([True, 123], commit_fails=True)
    lock = PostgreSQLAdvisoryLock(connection, 12345)  # type: ignore[arg-type]

    with pytest.raises(RuntimeError, match="commit failed"):
        lock.try_acquire()

    assert connection.invalidations >= 1
    assert connection.in_transaction() is False


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        (0, (0, 0)),
        (1, (0, 1)),
        (-1, (0xFFFFFFFF, 0xFFFFFFFF)),
        (2**63 - 1, (0x7FFFFFFF, 0xFFFFFFFF)),
        (-(2**63), (0x80000000, 0)),
    ],
)
def test_advisory_lock_key_parts_map_signed_bigints(key: int, expected: tuple[int, int]) -> None:
    from app.jobs.reliability import _advisory_lock_key_parts

    assert _advisory_lock_key_parts(key) == expected


@pytest.mark.parametrize("key", [2**63, -(2**63) - 1])
def test_advisory_lock_key_parts_reject_out_of_range_values(key: int) -> None:
    from app.jobs.reliability import _advisory_lock_key_parts

    with pytest.raises(ValueError):
        _advisory_lock_key_parts(key)


class _FakeOwnershipSession:
    def __init__(self, values: list[object]) -> None:
        self.values = values
        self.scalar_calls = 0

    def scalar(self, *_args: object, **_kwargs: object) -> object:
        self.scalar_calls += 1
        return self.values.pop(0)


def test_ownership_check_through_session_does_not_commit_or_rollback_connection() -> None:
    connection = _FakeAdvisoryConnection([])
    lock = PostgreSQLAdvisoryLock(connection, -1)  # type: ignore[arg-type]
    lock.acquired = True
    lock.backend_pid = 123
    session = _FakeOwnershipSession([123, True])

    assert lock.owns_current_session(session) is True  # type: ignore[arg-type]

    assert session.scalar_calls == 2
    assert connection.commits == 0
    assert connection.rollbacks == 0
    assert connection.invalidations == 0


def test_raw_ownership_check_with_active_transaction_fails_without_cleanup() -> None:
    connection = _FakeAdvisoryConnection([123, True])
    connection._in_transaction = True
    lock = PostgreSQLAdvisoryLock(connection, 12345)  # type: ignore[arg-type]
    lock.acquired = True
    lock.backend_pid = 123

    with pytest.raises(RuntimeError, match="no active transaction"):
        lock.owns_current_connection()

    assert connection.scalars == [123, True]
    assert connection.commits == 0
    assert connection.rollbacks == 0
    assert connection.invalidations == 0


def test_scheduler_stop_before_runtime_loading_prevents_cycle() -> None:
    stop = Event()
    stop.set()

    def loader() -> tuple[object, object, object]:
        pytest.fail("runtime loader must not run after startup stop")

    assert google_ads_scheduler.main(stop, loader) == google_ads_scheduler.FAILURE_EXIT_CODE


def test_scheduler_stop_during_runtime_loading_prevents_cycle() -> None:
    stop = Event()

    def run_cycle(*_args: object, **_kwargs: object) -> None:
        pytest.fail("run_cycle must not run after startup stop")

    def loader() -> tuple[Settings, object, object]:
        stop.set()
        return Settings(), object(), run_cycle

    assert google_ads_scheduler.main(stop, loader) == google_ads_scheduler.FAILURE_EXIT_CODE


def test_scheduler_runtime_loader_failure_restores_handlers_and_sanitizes_output(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    installed = False
    restored: dict[int, object] | None = None

    def install(stop: Event) -> dict[int, object]:
        nonlocal installed
        installed = True
        return {1: object()}

    def restore(previous: dict[int, object]) -> None:
        nonlocal restored
        restored = previous

    def loader() -> tuple[object, object, object]:
        raise RuntimeError("secret database-url password=hunter2")

    monkeypatch.setattr(google_ads_scheduler, "_install_signal_handlers", install)
    monkeypatch.setattr(google_ads_scheduler, "_restore_signal_handlers", restore)

    assert google_ads_scheduler.main(None, loader) == google_ads_scheduler.FAILURE_EXIT_CODE
    captured = capsys.readouterr()

    assert installed is True
    assert restored is not None
    assert "hunter2" not in captured.out + captured.err
    assert "database-url" not in captured.out + captured.err


def test_direct_google_ads_sync_fails_closed_before_collectors_or_job_run(
    sqlite_engine: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.collectors import google_ads

    monkeypatch.setattr(
        google_ads,
        "collect_account",
        lambda *_args, **_kwargs: pytest.fail("direct sync must not call collectors"),
    )

    with Session(sqlite_engine) as session:
        with pytest.raises(GoogleAdsSyncError, match="Phase 7 worker") as exc_info:
            GoogleAdsSyncService(session).sync()
        assert exc_info.value.classification is SyncFailureClassification.PERMANENT_CONFIGURATION
        assert session.scalars(select(JobRun)).all() == []


def test_legacy_sync_script_delegates_to_one_shot_worker() -> None:
    from scripts import sync_google_ads

    calls = 0

    def worker_main() -> int:
        nonlocal calls
        calls += 1
        return google_ads_sync_once.OVERLAP_EXIT_CODE

    assert sync_google_ads.main(worker_main) == google_ads_sync_once.OVERLAP_EXIT_CODE
    assert calls == 1


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({"AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY": "0"}, 0),
        ({"AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY": "42"}, 42),
        ({"AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY": "-42"}, -42),
        ({"AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY": str(2**63 - 1)}, 2**63 - 1),
        ({"AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY": str(-(2**63))}, -(2**63)),
        ({"AD_ANALYZER_SYNC_LOCK_KEY": "99"}, 99),
        ({"AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY": "123", "AD_ANALYZER_SYNC_LOCK_KEY": "123"}, 123),
    ],
)
def test_sync_advisory_lock_key_environment_aliases(
    monkeypatch: pytest.MonkeyPatch, env: dict[str, str], expected: int
) -> None:
    monkeypatch.delenv("AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY", raising=False)
    monkeypatch.delenv("AD_ANALYZER_SYNC_LOCK_KEY", raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    assert Settings().sync_lock_key == expected


@pytest.mark.parametrize(
    "env",
    [
        {"AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY": str(2**63)},
        {"AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY": str(-(2**63) - 1)},
        {"AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY": "not-an-int"},
        {"AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY": ""},
        {"AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY": "1", "AD_ANALYZER_SYNC_LOCK_KEY": "2"},
    ],
)
def test_sync_advisory_lock_key_invalid_environment_fails_closed(
    monkeypatch: pytest.MonkeyPatch, env: dict[str, str]
) -> None:
    monkeypatch.delenv("AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY", raising=False)
    monkeypatch.delenv("AD_ANALYZER_SYNC_LOCK_KEY", raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    with pytest.raises((InvalidSyncAdvisoryLockConfigError, SyncAdvisoryLockConfigError)):
        Settings()


def test_default_sync_advisory_lock_key_is_documented_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY", raising=False)
    monkeypatch.delenv("AD_ANALYZER_SYNC_LOCK_KEY", raising=False)

    assert Settings().sync_lock_key == 719_042_711


@pytest.mark.parametrize(
    ("env_key", "expected"),
    [
        ("ad_analyzer_sync_advisory_lock_key", 901),
        ("Ad_AnAlYzEr_SyNc_AdViSoRy_LoCk_KeY", 902),
        ("ad_analyzer_sync_lock_key", 903),
        ("Ad_AnAlYzEr_SyNc_LoCk_KeY", 904),
    ],
)
def test_sync_advisory_lock_key_accepts_case_insensitive_environment_forms(
    monkeypatch: pytest.MonkeyPatch, env_key: str, expected: int
) -> None:
    for key in (
        "AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY",
        "ad_analyzer_sync_advisory_lock_key",
        "Ad_AnAlYzEr_SyNc_AdViSoRy_LoCk_KeY",
        "AD_ANALYZER_SYNC_LOCK_KEY",
        "ad_analyzer_sync_lock_key",
        "Ad_AnAlYzEr_SyNc_LoCk_KeY",
        "sync_lock_key",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv(env_key, str(expected))

    assert Settings(_env_file=None).sync_lock_key == expected


@pytest.mark.parametrize(
    ("dotenv_text", "expected"),
    [
        ("ad_analyzer_sync_advisory_lock_key=905\n", 905),
        ("Ad_AnAlYzEr_SyNc_AdViSoRy_LoCk_KeY=906\n", 906),
        ("ad_analyzer_sync_lock_key=907\n", 907),
        ("Ad_AnAlYzEr_SyNc_LoCk_KeY=908\n", 908),
    ],
)
def test_sync_advisory_lock_key_accepts_case_insensitive_dotenv_forms(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, dotenv_text: str, expected: int
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY", raising=False)
    monkeypatch.delenv("AD_ANALYZER_SYNC_LOCK_KEY", raising=False)
    (tmp_path / ".env").write_text(dotenv_text)

    assert Settings().sync_lock_key == expected


@pytest.mark.parametrize(
    "kwargs",
    [
        {"sync_lock_key": "909"},
        {"AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY": "909"},
        {"AD_ANALYZER_SYNC_LOCK_KEY": "909"},
    ],
)
def test_sync_advisory_lock_key_accepts_direct_pydantic_forms(kwargs: dict[str, str]) -> None:
    assert Settings(_env_file=None, **kwargs).sync_lock_key == 909


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("sync_lock_key", "secret-lock-not-an-int"),
        ("AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY", "secret-lock-not-an-int"),
        ("AD_ANALYZER_SYNC_LOCK_KEY", "secret-lock-not-an-int"),
        ("ad_analyzer_sync_advisory_lock_key", "secret-lock-not-an-int"),
        ("ad_analyzer_sync_lock_key", "secret-lock-not-an-int"),
        ("AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY", ""),
        ("AD_ANALYZER_SYNC_LOCK_KEY", ""),
        ("AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY", str(-(2**63) - 1)),
        ("AD_ANALYZER_SYNC_LOCK_KEY", str(2**63)),
    ],
)
def test_sync_advisory_lock_key_malformed_accepted_forms_are_sanitized(
    monkeypatch: pytest.MonkeyPatch, key: str, value: str
) -> None:
    for env_key in (
        "AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY",
        "ad_analyzer_sync_advisory_lock_key",
        "AD_ANALYZER_SYNC_LOCK_KEY",
        "ad_analyzer_sync_lock_key",
        "sync_lock_key",
    ):
        monkeypatch.delenv(env_key, raising=False)
    if key == "sync_lock_key":

        def build_settings() -> Settings:
            return Settings(_env_file=None, sync_lock_key=value)
    else:
        monkeypatch.setenv(key, value)

        def build_settings() -> Settings:
            return Settings(_env_file=None)

    with pytest.raises(InvalidSyncAdvisoryLockConfigError) as exc_info:
        build_settings()

    rendered = str(exc_info.value)
    assert rendered == "Invalid sync advisory lock key setting."
    assert "secret-lock-not-an-int" not in rendered
    assert "input_value" not in rendered


def test_sync_advisory_lock_key_detects_case_variant_conflicts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ad_analyzer_sync_advisory_lock_key", "910")
    monkeypatch.setenv("Ad_AnAlYzEr_SyNc_LoCk_KeY", "911")

    with pytest.raises(SyncAdvisoryLockConfigError) as exc_info:
        Settings(_env_file=None)

    assert str(exc_info.value) == "Conflicting sync advisory lock key settings."
    assert "910" not in str(exc_info.value)
    assert "911" not in str(exc_info.value)


def test_sync_advisory_lock_key_direct_field_conflicts_with_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY", "912")

    with pytest.raises(SyncAdvisoryLockConfigError) as exc_info:
        Settings(_env_file=None, sync_lock_key="913")

    assert str(exc_info.value) == "Conflicting sync advisory lock key settings."


@pytest.mark.parametrize(
    ("first_key", "first_value", "second_key", "second_value", "error_type"),
    [
        (
            "AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY",
            "123",
            "ad_analyzer_sync_advisory_lock_key",
            "secret-case-bad",
            InvalidSyncAdvisoryLockConfigError,
        ),
        (
            "AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY",
            "secret-case-bad",
            "ad_analyzer_sync_advisory_lock_key",
            "123",
            InvalidSyncAdvisoryLockConfigError,
        ),
        (
            "AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY",
            "123",
            "ad_analyzer_sync_advisory_lock_key",
            "124",
            SyncAdvisoryLockConfigError,
        ),
        (
            "AD_ANALYZER_SYNC_LOCK_KEY",
            "125",
            "ad_analyzer_sync_lock_key",
            "secret-case-bad",
            InvalidSyncAdvisoryLockConfigError,
        ),
        (
            "AD_ANALYZER_SYNC_LOCK_KEY",
            "125",
            "ad_analyzer_sync_lock_key",
            "126",
            SyncAdvisoryLockConfigError,
        ),
    ],
)
def test_sync_advisory_lock_key_synthetic_case_collisions_are_not_hidden(
    first_key: str,
    first_value: str,
    second_key: str,
    second_value: str,
    error_type: type[Exception],
) -> None:
    values: list[object] = [
        value
        for key, value in ((first_key, first_value), (second_key, second_value))
        if _is_sync_lock_key_name(key)
    ]

    with pytest.raises(error_type) as exc_info:
        _resolve_lock_key_values(values)

    rendered = str(exc_info.value)
    assert rendered in {
        "Invalid sync advisory lock key setting.",
        "Conflicting sync advisory lock key settings.",
    }
    assert "secret-case-bad" not in rendered
    assert "123" not in rendered
    assert "124" not in rendered
    assert "input_value" not in rendered


def test_sync_advisory_lock_key_synthetic_matching_case_variants_are_allowed() -> None:
    values: list[object] = [
        value
        for key, value in (
            ("AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY", "127"),
            ("ad_analyzer_sync_advisory_lock_key", "127"),
            ("Ad_Analyzer_Sync_Advisory_Lock_Key", "127"),
        )
        if _is_sync_lock_key_name(key)
    ]

    assert _resolve_lock_key_values(values) == 127


@pytest.mark.skipif(
    os.name == "nt",
    reason="Windows cannot represent duplicate environment names that differ only by case.",
)
def test_sync_advisory_lock_key_process_environment_case_collisions_are_not_hidden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY", "123")
    monkeypatch.setenv("ad_analyzer_sync_advisory_lock_key", "secret-case-bad")

    with pytest.raises(InvalidSyncAdvisoryLockConfigError) as exc_info:
        Settings(_env_file=None)

    rendered = str(exc_info.value)
    assert rendered == "Invalid sync advisory lock key setting."
    assert "secret-case-bad" not in rendered
    assert "input_value" not in rendered


@pytest.mark.skipif(
    os.name == "nt",
    reason="Windows cannot represent duplicate environment names that differ only by case.",
)
def test_sync_advisory_lock_key_matching_environment_case_variants_are_allowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY", "127")
    monkeypatch.setenv("ad_analyzer_sync_advisory_lock_key", "127")
    monkeypatch.setenv("Ad_Analyzer_Sync_Advisory_Lock_Key", "127")

    assert Settings(_env_file=None).sync_lock_key == 127


@pytest.mark.parametrize(
    ("dotenv_text", "error_type"),
    [
        (
            "AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY=128\n"
            "ad_analyzer_sync_advisory_lock_key=secret-dotenv-bad\n",
            InvalidSyncAdvisoryLockConfigError,
        ),
        (
            "AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY=secret-dotenv-bad\n"
            "ad_analyzer_sync_advisory_lock_key=128\n",
            InvalidSyncAdvisoryLockConfigError,
        ),
        (
            "AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY=128\nad_analyzer_sync_advisory_lock_key=129\n",
            SyncAdvisoryLockConfigError,
        ),
        (
            "AD_ANALYZER_SYNC_LOCK_KEY=130\nad_analyzer_sync_lock_key=131\n",
            SyncAdvisoryLockConfigError,
        ),
    ],
)
def test_sync_advisory_lock_key_dotenv_case_collisions_are_not_hidden(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    dotenv_text: str,
    error_type: type[Exception],
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY", raising=False)
    monkeypatch.delenv("ad_analyzer_sync_advisory_lock_key", raising=False)
    monkeypatch.delenv("AD_ANALYZER_SYNC_LOCK_KEY", raising=False)
    monkeypatch.delenv("ad_analyzer_sync_lock_key", raising=False)
    (tmp_path / ".env").write_text(dotenv_text)

    with pytest.raises(error_type) as exc_info:
        Settings()

    rendered = str(exc_info.value)
    assert rendered in {
        "Invalid sync advisory lock key setting.",
        "Conflicting sync advisory lock key settings.",
    }
    assert "secret-dotenv-bad" not in rendered
    assert "input_value" not in rendered


def test_sync_advisory_lock_key_matching_dotenv_case_variants_are_allowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY", raising=False)
    monkeypatch.delenv("ad_analyzer_sync_advisory_lock_key", raising=False)
    (tmp_path / ".env").write_text(
        "AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY=132\n"
        "ad_analyzer_sync_advisory_lock_key=132\n"
        "Ad_Analyzer_Sync_Advisory_Lock_Key=132\n"
    )

    assert Settings().sync_lock_key == 132


@pytest.mark.parametrize(
    ("env_key", "env_value", "dotenv_text", "error_type"),
    [
        (
            "AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY",
            "133",
            "ad_analyzer_sync_advisory_lock_key=secret-mixed-bad\n",
            InvalidSyncAdvisoryLockConfigError,
        ),
        (
            "AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY",
            "133",
            "ad_analyzer_sync_advisory_lock_key=134\n",
            SyncAdvisoryLockConfigError,
        ),
    ],
)
def test_sync_advisory_lock_key_environment_dotenv_case_collisions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    env_key: str,
    env_value: str,
    dotenv_text: str,
    error_type: type[Exception],
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(env_key, env_value)
    (tmp_path / ".env").write_text(dotenv_text)

    with pytest.raises(error_type) as exc_info:
        Settings()

    rendered = str(exc_info.value)
    assert "secret-mixed-bad" not in rendered
    assert "input_value" not in rendered


def test_sync_advisory_lock_key_direct_case_collision_is_not_hidden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY", raising=False)

    with pytest.raises(SyncAdvisoryLockConfigError) as exc_info:
        Settings(_env_file=None, **{"sync_lock_key": "135", "SYNC_LOCK_KEY": "136"})

    assert str(exc_info.value) == "Conflicting sync advisory lock key settings."


@pytest.mark.skipif(
    os.name == "nt",
    reason="Windows cannot represent duplicate environment names that differ only by case.",
)
@pytest.mark.parametrize("value", [str(-(2**63)), str(2**63 - 1)])
def test_sync_advisory_lock_key_case_collision_accepts_signed_bounds(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY", value)
    monkeypatch.setenv("ad_analyzer_sync_advisory_lock_key", value)

    assert Settings(_env_file=None).sync_lock_key == int(value)


@pytest.mark.parametrize("guard", [None, (lambda: None), object()])
def test_authoritative_sync_rejects_missing_or_arbitrary_capability_before_collectors(
    sqlite_engine: Any,
    monkeypatch: pytest.MonkeyPatch,
    guard: object,
) -> None:
    from app.collectors import google_ads

    monkeypatch.setattr(
        google_ads,
        "collect_account",
        lambda *_args, **_kwargs: pytest.fail("rejected capability must not collect"),
    )
    with Session(sqlite_engine) as session:
        job_run = JobRun(
            workspace_id=1,
            platform="google_ads",
            job_name="google_ads_read_only_sync",
            status=JobRunStatus.RUNNING,
        )
        with pytest.raises((GoogleAdsSyncError, TypeError)):
            if guard is None:
                GoogleAdsSyncService(session).sync_authoritative_job_run(job_run)  # type: ignore[call-arg]
            else:
                GoogleAdsSyncService(session).sync_authoritative_job_run(
                    job_run,
                    capability=guard,  # type: ignore[arg-type]
                )
        assert session.scalars(select(JobRun)).all() == []


def test_reliability_exposes_no_constructible_worker_capability_class() -> None:
    from app.jobs import reliability

    assert not hasattr(reliability, "_WorkerPhase7SyncCapability")


def test_google_ads_sync_service_has_no_production_unlocked_sync_bypass() -> None:
    assert not hasattr(GoogleAdsSyncService, "_sync_without_worker_for_tests")
    import app.ads.services as services_module

    assert not hasattr(services_module, "_CAPABILITY_TOKEN")
    assert not hasattr(services_module, "_new_phase7_sync_capability")
    production_text = "\n".join(path.read_text() for path in Path("app").rglob("*.py"))
    assert "_sync_without_worker_for_tests" not in production_text


def test_fabricated_phase7_capability_cannot_reach_collectors(
    sqlite_engine: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.ads.services import Phase7SyncCapability
    from app.collectors import google_ads

    monkeypatch.setattr(
        google_ads,
        "collect_account",
        lambda *_args, **_kwargs: pytest.fail("fabricated capability must not collect"),
    )
    fabricated = object.__new__(Phase7SyncCapability)
    with Session(sqlite_engine) as session:
        job_run = JobRun(
            workspace_id=1,
            platform="google_ads",
            job_name="google_ads_read_only_sync",
            status=JobRunStatus.RUNNING,
        )
        with pytest.raises(GoogleAdsSyncError):
            GoogleAdsSyncService(session).sync_authoritative_job_run(job_run, capability=fabricated)
        assert session.scalars(select(JobRun)).all() == []


def test_sync_advisory_lock_key_conflict_inside_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY", raising=False)
    monkeypatch.delenv("AD_ANALYZER_SYNC_LOCK_KEY", raising=False)
    (tmp_path / ".env").write_text(
        "AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY=1\nAD_ANALYZER_SYNC_LOCK_KEY=2\n"
    )

    with pytest.raises(SyncAdvisoryLockConfigError) as exc_info:
        Settings()
    assert str(exc_info.value) == "Conflicting sync advisory lock key settings."


def test_sync_advisory_lock_key_matching_dotenv_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY", raising=False)
    monkeypatch.delenv("AD_ANALYZER_SYNC_LOCK_KEY", raising=False)
    (tmp_path / ".env").write_text(
        "AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY=123\nAD_ANALYZER_SYNC_LOCK_KEY=123\n"
    )

    assert Settings().sync_lock_key == 123


@pytest.mark.parametrize(
    ("env_key", "env_value", "dotenv_text"),
    [
        (
            "AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY",
            "10",
            "AD_ANALYZER_SYNC_LOCK_KEY=11\n",
        ),
        (
            "AD_ANALYZER_SYNC_LOCK_KEY",
            "10",
            "AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY=11\n",
        ),
    ],
)
def test_sync_advisory_lock_key_mixed_source_conflicts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    env_key: str,
    env_value: str,
    dotenv_text: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY", raising=False)
    monkeypatch.delenv("AD_ANALYZER_SYNC_LOCK_KEY", raising=False)
    monkeypatch.setenv(env_key, env_value)
    (tmp_path / ".env").write_text(dotenv_text)

    with pytest.raises(SyncAdvisoryLockConfigError) as exc_info:
        Settings()
    assert str(exc_info.value) == "Conflicting sync advisory lock key settings."


def test_sync_advisory_lock_key_matching_mixed_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY", raising=False)
    monkeypatch.delenv("AD_ANALYZER_SYNC_LOCK_KEY", raising=False)
    monkeypatch.setenv("AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY", "77")
    (tmp_path / ".env").write_text("AD_ANALYZER_SYNC_LOCK_KEY=77\n")

    assert Settings().sync_lock_key == 77


def test_sync_advisory_lock_key_direct_construction_conflict() -> None:
    with pytest.raises(SyncAdvisoryLockConfigError) as exc_info:
        Settings(AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY="1", AD_ANALYZER_SYNC_LOCK_KEY="2")
    assert str(exc_info.value) == "Conflicting sync advisory lock key settings."


def test_phase7_capability_public_construction_and_copied_values_fail(
    sqlite_engine: Any,
) -> None:
    from app.ads.services import Phase7SyncCapability
    from app.jobs import reliability

    assert not hasattr(reliability, "_WorkerPhase7SyncCapability")
    with pytest.raises(RuntimeError):
        Phase7SyncCapability()

    with Session(sqlite_engine) as session:
        copied = object.__new__(Phase7SyncCapability)
        with pytest.raises(GoogleAdsSyncError):
            copied.validate(session)


def test_worker_entrypoints_do_not_log_lock_conflict_values(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from app.settings import SyncAdvisoryLockConfigError

    secret_value = "lock-secret-12345"

    def fail_loader() -> object:
        _ = secret_value
        raise SyncAdvisoryLockConfigError()

    with caplog.at_level("ERROR"):
        assert google_ads_sync_once.main(fail_loader) == google_ads_sync_once.FAILURE_EXIT_CODE
        assert google_ads_scheduler.main(runtime_loader=fail_loader) == 1

    assert secret_value not in caplog.text
    assert "input_value" not in caplog.text
    assert "Conflicting sync advisory lock key settings" not in caplog.text


@pytest.mark.parametrize(
    ("dotenv_text", "expected_error"),
    [
        (
            "AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY=lock-secret-bad\n",
            InvalidSyncAdvisoryLockConfigError,
        ),
        ("AD_ANALYZER_SYNC_LOCK_KEY=\n", InvalidSyncAdvisoryLockConfigError),
        (
            f"AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY={2**63}\n",
            InvalidSyncAdvisoryLockConfigError,
        ),
    ],
)
def test_sync_advisory_lock_key_invalid_dotenv_values_are_sanitized(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    dotenv_text: str,
    expected_error: type[Exception],
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY", raising=False)
    monkeypatch.delenv("AD_ANALYZER_SYNC_LOCK_KEY", raising=False)
    (tmp_path / ".env").write_text(dotenv_text)

    with pytest.raises(expected_error) as exc_info:
        Settings()

    assert str(exc_info.value) == "Invalid sync advisory lock key setting."
    assert "lock-secret-bad" not in str(exc_info.value)
    assert "input_value" not in str(exc_info.value)


def test_sync_advisory_lock_key_malformed_direct_construction_is_sanitized() -> None:
    with pytest.raises(InvalidSyncAdvisoryLockConfigError) as exc_info:
        Settings(AD_ANALYZER_SYNC_ADVISORY_LOCK_KEY="direct-secret-bad")

    assert str(exc_info.value) == "Invalid sync advisory lock key setting."
    assert "direct-secret-bad" not in str(exc_info.value)


def test_worker_entrypoints_do_not_log_invalid_lock_key_values(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret_value = "invalid-lock-secret-12345"

    def fail_loader() -> object:
        _ = secret_value
        raise InvalidSyncAdvisoryLockConfigError()

    with caplog.at_level("ERROR"):
        assert google_ads_sync_once.main(fail_loader) == google_ads_sync_once.FAILURE_EXIT_CODE
        assert google_ads_scheduler.main(runtime_loader=fail_loader) == 1

    assert secret_value not in caplog.text
    assert "input_value" not in caplog.text
    assert "Invalid sync advisory lock key setting" not in caplog.text
