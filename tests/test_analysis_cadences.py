from collections.abc import Generator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from sqlite3 import Connection as SQLiteConnection

import pytest
from app.ads.enums import AdvertisingPlatform, JobRunStatus
from app.ads.models import AdvertisingAccount, Campaign, DailyMetric, JobRun
from app.ads.services import GoogleAdsSyncResult
from app.analysis.cadence import (
    _nightly_schedule,
    _weekly_schedule,
    run_analysis_tick,
    run_due_analyses,
    run_post_sync_analysis,
)
from app.analysis.enums import AnalysisCadence, AnalysisRunStatus
from app.analysis.models import AnalysisRun
from app.analysis.policy import AnalysisCadencePolicy, AnalysisCadencePolicyError
from app.analysis.service import AnalysisRunService
from app.database.session import Base, get_db
from app.jobs.google_ads_sync_once import SUCCESS_EXIT_CODE
from app.jobs.google_ads_sync_once import main as sync_once_main
from app.jobs.reliability import CycleOutcome
from app.main import app
from app.settings import settings
from app.workspaces.models import Workspace, WorkspaceConfiguration
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine, create_engine, event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import ConnectionPoolEntry, StaticPool


def enable_sqlite_foreign_keys(
    dbapi_connection: SQLiteConnection,
    _connection_record: ConnectionPoolEntry,
) -> None:
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


@pytest.fixture()
def database() -> Generator[tuple[Session, Engine], None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    event.listen(engine, "connect", enable_sqlite_foreign_keys)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session, engine
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def seed_workspace(
    db: Session,
    *,
    slug: str = "denticode",
    analysis: dict[str, object] | None = None,
    with_metrics: bool = True,
    as_of: datetime = datetime(2026, 8, 8, 12, tzinfo=UTC),
) -> tuple[Workspace, AdvertisingAccount, JobRun]:
    workspace = Workspace(
        slug=slug,
        name=f"{slug.title()} Ad Analyzer",
        client_name=slug.title(),
        status="active",
        is_default=slug == "denticode",
    )
    db.add(workspace)
    db.flush()
    db.add(
        WorkspaceConfiguration(
            workspace_id=workspace.id,
            analysis=analysis or {},
            automation={"live_writes_enabled": False},
            notifications={},
            branding={"workspace_name": workspace.name},
        )
    )
    account = AdvertisingAccount(
        workspace_id=workspace.id,
        platform=AdvertisingPlatform.GOOGLE_ADS,
        external_account_id=f"{slug}-account",
        name=f"{slug.title()} Google Ads",
        currency_code="USD",
        time_zone="America/Los_Angeles",
    )
    db.add(account)
    db.flush()
    campaign = Campaign(
        account_id=account.id,
        platform=AdvertisingPlatform.GOOGLE_ADS,
        external_campaign_id=f"{slug}-campaign",
        name=f"{slug.title()} Search",
        status="ENABLED",
        channel_type="SEARCH",
    )
    db.add(campaign)
    db.flush()
    if with_metrics:
        metric_end = as_of.date() - timedelta(days=1)
        for day_offset in range(7):
            metric_date = metric_end - timedelta(days=day_offset)
            db.add(
                DailyMetric(
                    platform=AdvertisingPlatform.GOOGLE_ADS,
                    metric_date=metric_date,
                    entity_type="campaign",
                    entity_id=campaign.id,
                    campaign_id=campaign.id,
                    impressions=1_000,
                    clicks=5,
                    cost_micros=2_000_000,
                    conversions=Decimal("0"),
                    conversion_value_micros=0,
                )
            )
    job = JobRun(
        workspace_id=workspace.id,
        platform=AdvertisingPlatform.GOOGLE_ADS,
        account_id=account.id,
        job_name="google_ads_read_only_sync",
        status=JobRunStatus.SUCCEEDED,
        started_at=as_of - timedelta(minutes=2),
        finished_at=as_of - timedelta(minutes=1),
        records_processed=8,
    )
    db.add(job)
    db.commit()
    return workspace, account, job


def test_policy_defaults_and_workspace_overrides() -> None:
    defaults = AnalysisCadencePolicy.from_workspace_analysis({"target_cpa_micros": 1})
    assert defaults.post_sync.window_days == 7
    assert defaults.nightly.hour_utc == 2
    assert defaults.nightly.window_days == 30
    assert defaults.weekly.weekday_utc == 0
    assert defaults.weekly.hour_utc == 3
    assert defaults.weekly.window_days == 90

    customized = AnalysisCadencePolicy.from_workspace_analysis(
        {
            "cadences": {
                "version": "v1",
                "post_sync": {"enabled": False, "window_days": 14},
                "nightly": {"enabled": True, "hour_utc": 5, "window_days": 45},
                "weekly": {
                    "enabled": True,
                    "weekday_utc": 4,
                    "hour_utc": 6,
                    "window_days": 120,
                },
            }
        }
    )
    assert customized.post_sync.enabled is False
    assert customized.nightly.window_days == 45
    assert customized.weekly.weekday_utc == 4


@pytest.mark.parametrize(
    "analysis",
    [
        {"cadences": "nightly"},
        {"cadences": {"nightly": {"hour_utc": 24}}},
        {"cadences": {"weekly": {"weekday_utc": 7}}},
        {"cadences": {"unknown": {"enabled": True}}},
    ],
)
def test_invalid_policy_fails_closed_without_echoing_values(analysis: object) -> None:
    with pytest.raises(AnalysisCadencePolicyError) as exc_info:
        AnalysisCadencePolicy.from_workspace_analysis(analysis)
    assert str(exc_info.value) == "Invalid workspace analysis cadence configuration."


def test_schedule_boundaries_are_utc_and_do_not_run_early() -> None:
    before_nightly = datetime(2026, 8, 8, 1, 59, tzinfo=UTC)
    at_nightly = datetime(2026, 8, 8, 2, 0, tzinfo=UTC)
    assert _nightly_schedule(before_nightly, 2) is None
    assert _nightly_schedule(at_nightly, 2) == at_nightly

    monday_before = datetime(2026, 8, 10, 2, 59, tzinfo=UTC)
    monday_at = datetime(2026, 8, 10, 3, 0, tzinfo=UTC)
    assert _weekly_schedule(monday_before, 0, 3) is None
    assert _weekly_schedule(monday_at, 0, 3) == monday_at


def test_post_sync_analysis_is_idempotent_and_aggregate_only(
    database: tuple[Session, Engine],
) -> None:
    db, engine = database
    _workspace, account, job = seed_workspace(db)
    as_of = datetime(2026, 8, 8, 12, tzinfo=UTC)

    first = run_post_sync_analysis(engine, job.id, as_of=as_of)
    second = run_post_sync_analysis(engine, job.id, as_of=as_of)

    assert first is not None
    assert second is not None
    assert first.id == second.id
    assert first.account_id == account.id
    assert first.cadence == AnalysisCadence.POST_SYNC
    assert first.status == AnalysisRunStatus.SUCCEEDED
    assert first.accounts_analyzed == 1
    assert first.findings_count == 2
    assert first.high_severity_findings_count == 1
    assert first.outcome_analysis_ready is False
    assert first.blocking_reasons == ["measurement_contract_missing"]
    assert db.scalar(select(func.count()).select_from(AnalysisRun)) == 1


def test_due_tick_runs_nightly_and_weekly_once_per_workspace_period(
    database: tuple[Session, Engine],
) -> None:
    db, engine = database
    seed_workspace(db, with_metrics=False)
    as_of = datetime(2026, 8, 10, 4, tzinfo=UTC)

    first_ids, invalid = run_due_analyses(engine, as_of=as_of)
    second_ids, second_invalid = run_due_analyses(engine, as_of=as_of)
    rows = list(db.scalars(select(AnalysisRun).order_by(AnalysisRun.cadence.asc())).all())

    assert invalid == second_invalid == 0
    assert first_ids == second_ids
    assert len(rows) == 2
    assert {row.cadence for row in rows} == {
        AnalysisCadence.NIGHTLY,
        AnalysisCadence.WEEKLY,
    }
    assert all(row.status == AnalysisRunStatus.SUCCEEDED for row in rows)
    assert all(row.account_id is None for row in rows)
    assert all(row.source_job_run_id is None for row in rows)


def test_disabled_cadences_and_invalid_workspace_policy_are_not_run(
    database: tuple[Session, Engine],
) -> None:
    db, engine = database
    _workspace, _account, job = seed_workspace(
        db,
        analysis={
            "cadences": {
                "post_sync": {"enabled": False},
                "nightly": {"enabled": False},
                "weekly": {"enabled": False},
            }
        },
        with_metrics=False,
    )
    invalid_workspace, _invalid_account, _invalid_job = seed_workspace(
        db,
        slug="invalid",
        analysis={"cadences": {"nightly": {"hour_utc": 99}}},
        with_metrics=False,
    )

    assert run_post_sync_analysis(engine, job.id) is None
    ids, invalid_count = run_due_analyses(
        engine,
        as_of=datetime(2026, 8, 10, 4, tzinfo=UTC),
    )
    assert ids == ()
    assert invalid_count == 1
    assert invalid_workspace.id is not None
    assert db.scalar(select(func.count()).select_from(AnalysisRun)) == 0


def test_analysis_failure_is_sanitized_and_does_not_call_external_boundaries(
    database: tuple[Session, Engine],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    db, _engine = database
    workspace, _account, _job = seed_workspace(db, with_metrics=False)

    def fail_report(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("Bearer private-token")

    monkeypatch.setattr("app.measurement.unified.UnifiedOutcomeService.report", fail_report)
    monkeypatch.setattr(
        "app.collectors.google_ads.collect_account",
        lambda: pytest.fail("analysis must not call the Google Ads collector"),
    )
    monkeypatch.setattr(
        "app.executors.google_executor.live_google_ads_mutation_boundary",
        lambda *_args, **_kwargs: pytest.fail("analysis must not call a mutation boundary"),
    )
    row = AnalysisRunService(db).execute(
        workspace_id=workspace.id,
        cadence=AnalysisCadence.NIGHTLY,
        run_key="nightly:2026-08-08",
        scheduled_for=datetime(2026, 8, 8, 2, tzinfo=UTC),
        window_days=30,
        as_of=datetime(2026, 8, 8, 12, tzinfo=UTC),
    )

    assert row.status == AnalysisRunStatus.FAILED
    assert row.error_code == "analysis_failed"
    assert row.blocking_reasons == ["analysis_failed"]
    assert "private-token" not in caplog.text


def test_database_rejects_cross_workspace_analysis_sources(
    database: tuple[Session, Engine],
) -> None:
    db, _engine = database
    first, _first_account, _first_job = seed_workspace(db, slug="first", with_metrics=False)
    _second, second_account, second_job = seed_workspace(db, slug="second", with_metrics=False)
    db.add(
        AnalysisRun(
            workspace_id=first.id,
            account_id=second_account.id,
            source_job_run_id=second_job.id,
            run_key="post_sync:cross-workspace",
            cadence=AnalysisCadence.POST_SYNC,
            status=AnalysisRunStatus.RUNNING,
            schedule_policy_version="v1",
            scheduled_for=datetime(2026, 8, 8, 12, tzinfo=UTC),
            metric_date_from=date(2026, 8, 1),
            metric_date_to=date(2026, 8, 7),
            outcome_date_from=date(2026, 5, 1),
            outcome_date_to=date(2026, 5, 7),
            started_at=datetime(2026, 8, 8, 12, tzinfo=UTC),
            blocking_reasons=[],
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_api_and_dashboard_list_only_the_requested_workspace_runs(
    database: tuple[Session, Engine],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, _engine = database
    denticode, _account, _job = seed_workspace(db, with_metrics=False)
    other, _other_account, _other_job = seed_workspace(db, slug="other", with_metrics=False)
    as_of = datetime(2026, 8, 8, 12, tzinfo=UTC)
    AnalysisRunService(db).execute(
        workspace_id=denticode.id,
        cadence=AnalysisCadence.NIGHTLY,
        run_key="nightly:2026-08-08",
        scheduled_for=datetime(2026, 8, 8, 2, tzinfo=UTC),
        window_days=30,
        as_of=as_of,
    )
    AnalysisRunService(db).execute(
        workspace_id=other.id,
        cadence=AnalysisCadence.WEEKLY,
        run_key="weekly:2026-08-03",
        scheduled_for=datetime(2026, 8, 3, 3, tzinfo=UTC),
        window_days=90,
        as_of=as_of,
    )
    token = "a" * 48
    monkeypatch.setattr(settings, "denticode_api_token", SecretStr(token))
    monkeypatch.setattr(settings, "app_env", "development")

    def override_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app, base_url="https://testserver")
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get(
            "/api/v1/workspaces/denticode/analysis-runs",
            headers=headers,
        )
        client.get("/dashboard", headers=headers)
        dashboard = client.get("/dashboard/workspaces/denticode")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["workspace_id"] == denticode.id
    assert response.json()["items"][0]["cadence"] == "nightly"
    assert dashboard.status_code == 200
    assert "Analysis cadence history" in dashboard.text
    assert "nightly" in dashboard.text
    assert "<td>weekly</td>" not in dashboard.text
    assert "run_key" not in response.text


def test_sync_worker_invokes_post_sync_analysis_without_changing_sync_success() -> None:
    called: list[int] = []
    outcome = CycleOutcome(
        skipped=False,
        result=GoogleAdsSyncResult(
            job_run_id=41,
            records_processed=5,
            status=JobRunStatus.SUCCEEDED,
        ),
        attempts=1,
    )

    def run_cycle(*_args: object, **_kwargs: object) -> CycleOutcome:
        return outcome

    def analysis_hook(_engine: object, source_job_run_id: int) -> None:
        called.append(source_job_run_id)

    assert (
        sync_once_main(
            lambda: (settings, object(), run_cycle, JobRunStatus),
            analysis_hook,
        )
        == SUCCESS_EXIT_CODE
    )
    assert called == [41]


def test_analysis_tick_runs_due_cadences_even_without_a_successful_sync(
    database: tuple[Session, Engine],
) -> None:
    db, engine = database
    seed_workspace(db, with_metrics=False)
    result = run_analysis_tick(
        engine,
        None,
        as_of=datetime(2026, 8, 10, 4, tzinfo=UTC),
    )
    assert result.post_sync_run_id is None
    assert len(result.scheduled_run_ids) == 2
    assert result.invalid_policy_count == 0
