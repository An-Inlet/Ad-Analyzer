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
    def acquire(self: PostgreSQLAdvisoryLock) -> bool:
        self.acquired = True
        return True

    monkeypatch.setattr(PostgreSQLAdvisoryLock, "try_acquire", acquire)
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

    def sync_authoritative(
        self: Any, job_run: JobRun, **_kwargs: object
    ) -> GoogleAdsSyncResult:
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


def test_unknown_commit_with_lock_loss_does_not_replacement_finalize(
    tmp_path: Any,
    relaxed_lock: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sqlite_engine = create_engine(f"sqlite:///{(tmp_path / 'unknown-lock-loss.db').as_posix()}")
    Base.metadata.create_all(sqlite_engine)
    calls = 0
    fresh_finalize_calls = 0

    def unknown_and_lost(
        self: Any, _job_run: JobRun, **_kwargs: object
    ) -> GoogleAdsSyncResult:
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
            Settings(DENTICODE_SYNC_MAX_ATTEMPTS=3),
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
            Settings(DENTICODE_SYNC_MAX_ATTEMPTS=3),
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
        (
            "Google Ads synchronization interrupted before retry.",
            "Google Ads synchronization interrupted before retry.",
        ),
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
            Settings(DENTICODE_SYNC_MAX_ATTEMPTS=2, DENTICODE_SYNC_RETRY_BASE_SECONDS=1),
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

    def unknown_create(_session: Session) -> JobRun:
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
        "owns_current_connection",
        lambda _self: next(checks, False),
    )

    with pytest.raises(Exception, match="advisory-lock"):
        run_cycle(Settings(), sqlite_engine)

    assert account_calls == 1
    assert campaign_calls == 0
    Base.metadata.drop_all(sqlite_engine)
    sqlite_engine.dispose()
