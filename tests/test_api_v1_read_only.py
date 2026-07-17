from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from sqlite3 import Connection as SQLiteConnection

from app.ads.enums import AdvertisingPlatform, JobRunStatus
from app.ads.models import AdGroup, AdvertisingAccount, Campaign, DailyMetric, JobRun
from app.ads.schemas import AdvertisingAccountCreate
from app.collectors import google_ads
from app.database.session import Base, get_db
from app.main import app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import ConnectionPoolEntry, StaticPool


def enable_fk(dbapi_connection: SQLiteConnection, _connection_record: ConnectionPoolEntry) -> None:
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


def seed(db: Session) -> dict[str, int]:
    a1 = AdvertisingAccount(
        platform=AdvertisingPlatform.GOOGLE_ADS,
        external_account_id="100",
        name="Denticode",
        currency_code="USD",
        time_zone="UTC",
    )
    a2 = AdvertisingAccount(
        platform=AdvertisingPlatform.GOOGLE_ADS,
        external_account_id="200",
        name="Empty",
        currency_code="USD",
        time_zone="UTC",
    )
    db.add_all([a1, a2])
    db.flush()
    c1 = Campaign(
        account_id=a1.id,
        platform=a1.platform,
        external_campaign_id="c1",
        name="Implants",
        status="ENABLED",
        channel_type="SEARCH",
    )
    c2 = Campaign(
        account_id=a1.id,
        platform=a1.platform,
        external_campaign_id="c2",
        name="Crowns",
        status="PAUSED",
        channel_type="SEARCH",
    )
    db.add_all([c1, c2])
    db.flush()
    ag1 = AdGroup(
        campaign_id=c1.id,
        platform=c1.platform,
        external_ad_group_id="ag1",
        name="Exact",
        status="ENABLED",
    )
    ag2 = AdGroup(
        campaign_id=c2.id,
        platform=c2.platform,
        external_ad_group_id="ag2",
        name="Other",
        status="ENABLED",
    )
    db.add_all([ag1, ag2])
    db.flush()
    db.add_all(
        [
            DailyMetric(
                platform=c1.platform,
                metric_date=date(2026, 7, 1),
                entity_type="campaign",
                entity_id=c1.id,
                campaign_id=c1.id,
                impressions=100,
                clicks=10,
                cost_micros=1_000_000,
                conversions=Decimal("2.5"),
                conversion_value_micros=5_000_000,
            ),
            DailyMetric(
                platform=c1.platform,
                metric_date=date(2026, 7, 2),
                entity_type="campaign",
                entity_id=c1.id,
                campaign_id=c1.id,
                impressions=0,
                clicks=0,
                cost_micros=0,
                conversions=Decimal("0"),
                conversion_value_micros=0,
            ),
            DailyMetric(
                platform=c1.platform,
                metric_date=date(2026, 7, 1),
                entity_type="ad_group",
                entity_id=ag1.id,
                campaign_id=c1.id,
                impressions=999,
                clicks=999,
                cost_micros=999_000_000,
                conversions=Decimal("99"),
                conversion_value_micros=999_000_000,
            ),
        ]
    )
    now = datetime(2026, 7, 16, tzinfo=UTC)
    db.add_all(
        [
            JobRun(
                platform=a1.platform,
                account_id=a1.id,
                job_name="sync",
                status=JobRunStatus.SUCCEEDED,
                started_at=now - timedelta(days=1),
                finished_at=now - timedelta(days=1),
                records_processed=7,
            ),
            JobRun(
                platform=a1.platform,
                account_id=a1.id,
                job_name="sync",
                status=JobRunStatus.FAILED,
                started_at=now,
                finished_at=now,
                records_processed=3,
                error_message="sanitized failure",
            ),
        ]
    )
    db.commit()
    return {"a1": a1.id, "a2": a2.id, "c1": c1.id, "c2": c2.id}


@contextmanager
def make_client(
    *, foreign_keys: bool = True
) -> Generator[tuple[TestClient, Session, dict[str, int]], None, None]:
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    if foreign_keys:
        event.listen(engine, "connect", enable_fk)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    ids = seed(db)

    def override_get_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app), db, ids
    finally:
        app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(engine)


def test_accounts_campaigns_scoping_metrics_jobs_and_sync_status() -> None:
    with make_client() as (client, _db, ids):
        accounts = client.get("/api/v1/accounts").json()
        assert accounts["limit"] == 25 and accounts["offset"] == 0 and accounts["total"] == 2
        assert [item["id"] for item in accounts["items"]] == [ids["a1"], ids["a2"]]
        assert client.get(f"/api/v1/accounts/{ids['a1']}").json()["name"] == "Denticode"
        assert client.get(f"/api/v1/accounts/{ids['a2']}/campaigns").json()["items"] == []
        assert (
            client.get(f"/api/v1/accounts/{ids['a1']}/campaigns?status=ENABLED").json()["total"]
            == 1
        )
        assert client.get(f"/api/v1/campaigns/{ids['c1']}").json()["account"]["id"] == ids["a1"]
        ad_groups = client.get(f"/api/v1/campaigns/{ids['c1']}/ad-groups").json()
        assert ad_groups["total"] == 1 and ad_groups["items"][0]["campaign_id"] == ids["c1"]
        metrics = client.get(
            f"/api/v1/campaigns/{ids['c1']}/metrics?date_from=2026-07-01&date_to=2026-07-02"
        ).json()
        assert metrics["total"] == 2
        assert [row["metric_date"] for row in metrics["items"]] == ["2026-07-01", "2026-07-02"]
        summary = client.get(
            f"/api/v1/accounts/{ids['a1']}/metrics/summary?date_from=2026-07-01&date_to=2026-07-02"
        ).json()
        assert summary["impressions"] == 100 and summary["clicks"] == 10
        assert summary["ctr"] == "0.1" and summary["average_cpc_micros"] == "100000"
        zero = client.get(
            f"/api/v1/accounts/{ids['a2']}/metrics/summary?date_from=2026-07-01&date_to=2026-07-02"
        ).json()
        assert zero["ctr"] == "0" and zero["cost_per_conversion_micros"] == "0"
        assert client.get("/api/v1/job-runs").json()["total"] == 2
        assert client.get("/api/v1/job-runs/latest").json()["status"] == "failed"
        assert client.get("/api/v1/sync-status").json()["items"][0]["latest_status"] == "failed"


def test_errors_pagination_limits_no_collectors_and_no_writes() -> None:
    with make_client() as (client, db, ids):
        called = False
        original = google_ads.collect_account

        def fail_collect(*_args: object, **_kwargs: object) -> AdvertisingAccountCreate:
            nonlocal called
            called = True
            raise AssertionError("collector called")

        google_ads.collect_account = fail_collect
        statements: list[str] = []

        def before_cursor_execute(_conn, _cursor, statement: str, _params, _context, _many) -> None:  # type: ignore[no-untyped-def]
            statements.append(statement.strip().upper())

        event.listen(db.get_bind(), "before_cursor_execute", before_cursor_execute)
        try:
            assert client.get("/api/v1/accounts/999999").status_code == 404
            assert client.get("/api/v1/campaigns/999999").status_code == 404
            assert client.get("/api/v1/job-runs/latest?account_id=999999").status_code == 404
            assert (
                client.get(
                    f"/api/v1/campaigns/{ids['c1']}/metrics?date_from=2026-07-02&date_to=2026-07-01"
                ).status_code
                == 422
            )
            assert (
                client.get(
                    f"/api/v1/campaigns/{ids['c1']}/metrics?date_from=2025-01-01&date_to=2026-07-16"
                ).status_code
                == 422
            )
            assert client.get("/api/v1/accounts?limit=101").status_code == 422
            assert client.get("/api/v1/accounts?limit=100").json()["limit"] == 100
            assert not called
            assert not any(s.startswith(("INSERT", "UPDATE", "DELETE")) for s in statements)
        finally:
            event.remove(db.get_bind(), "before_cursor_execute", before_cursor_execute)
            google_ads.collect_account = original


def test_database_failure_returns_sanitized_503() -> None:
    def broken_get_db() -> Generator[Session, None, None]:
        class BrokenSession:
            def scalar(self, *_args: object, **_kwargs: object) -> object:
                raise OperationalError("SELECT secret", {"password": "secret"}, Exception("boom"))

            def close(self) -> None:
                pass

        yield BrokenSession()  # type: ignore[misc]

    app.dependency_overrides[get_db] = broken_get_db
    try:
        response = TestClient(app, raise_server_exceptions=False).get("/api/v1/accounts")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 503
    assert response.json() == {"detail": "database temporarily unavailable"}


def test_campaign_metrics_are_canonical_and_paginated() -> None:
    with make_client() as (client, db, ids):
        campaign = db.get(Campaign, ids["c1"])
        assert campaign is not None
        db.add(
            DailyMetric(
                platform=campaign.platform,
                metric_date=date(2026, 7, 3),
                entity_type="campaign",
                entity_id=campaign.id,
                campaign_id=campaign.id,
                impressions=5,
                clicks=1,
                cost_micros=100,
                conversions=Decimal("0"),
                conversion_value_micros=0,
            )
        )
        db.commit()

        first_page = client.get(
            f"/api/v1/campaigns/{ids['c1']}/metrics?date_from=2026-07-01&date_to=2026-07-03&limit=1"
        ).json()
        second_page = client.get(
            f"/api/v1/campaigns/{ids['c1']}/metrics?date_from=2026-07-01&date_to=2026-07-03&limit=1&offset=1"
        ).json()

        assert first_page["limit"] == 1 and first_page["offset"] == 0 and first_page["total"] == 3
        assert first_page["items"][0]["impressions"] == 100
        assert second_page["items"][0]["metric_date"] == "2026-07-02"
        assert client.get(
            f"/api/v1/campaigns/{ids['c1']}/metrics?date_from=2026-07-01&date_to=2026-07-03&limit=101"
        ).status_code == 422


def test_sync_status_is_account_scoped_paginated_and_uses_latest_timestamp() -> None:
    with make_client() as (client, db, ids):
        a1 = db.get(AdvertisingAccount, ids["a1"])
        a2 = db.get(AdvertisingAccount, ids["a2"])
        assert a1 is not None and a2 is not None
        same_start = datetime(2026, 7, 17, tzinfo=UTC)
        db.add_all(
            [
                JobRun(
                    platform=a1.platform,
                    account_id=a1.id,
                    job_name="sync",
                    status=JobRunStatus.SUCCEEDED,
                    started_at=same_start,
                    finished_at=same_start,
                    records_processed=8,
                ),
                JobRun(
                    platform=a1.platform,
                    account_id=a1.id,
                    job_name="sync",
                    status=JobRunStatus.FAILED,
                    started_at=same_start,
                    finished_at=same_start,
                    records_processed=9,
                ),
                JobRun(
                    platform=a2.platform,
                    account_id=a2.id,
                    job_name="sync",
                    status=JobRunStatus.SUCCEEDED,
                    started_at=datetime(2026, 7, 15, tzinfo=UTC),
                    finished_at=datetime(2026, 7, 15, tzinfo=UTC),
                    records_processed=4,
                ),
                JobRun(
                    platform=a1.platform,
                    account_id=a1.id,
                    job_name="backfill",
                    status=JobRunStatus.SUCCEEDED,
                    started_at=datetime(2026, 7, 14, tzinfo=UTC),
                    finished_at=datetime(2026, 7, 14, tzinfo=UTC),
                    records_processed=11,
                ),
                JobRun(
                    platform=a1.platform,
                    account_id=None,
                    job_name="platform-sync",
                    status=JobRunStatus.FAILED,
                    started_at=datetime(2026, 7, 18, tzinfo=UTC),
                    finished_at=datetime(2026, 7, 18, tzinfo=UTC),
                    records_processed=0,
                ),
            ]
        )
        db.commit()

        first = client.get("/api/v1/sync-status?limit=1").json()
        second = client.get("/api/v1/sync-status?limit=1&offset=1").json()
        latest = client.get(f"/api/v1/job-runs/latest?account_id={ids['a1']}").json()

        assert first["total"] == 2 and first["items"][0]["account_id"] == ids["a1"]
        assert first["items"][0]["latest_status"] == "failed"
        assert first["items"][0]["records_processed"] == 9
        assert second["items"][0]["account_id"] == ids["a2"]
        assert second["items"][0]["latest_status"] == "succeeded"
        assert latest["records_processed"] == 9


def test_sync_status_uses_a_bounded_set_based_query() -> None:
    with make_client() as (client, db, _ids):
        statements: list[str] = []

        def before_cursor_execute(_conn, _cursor, statement: str, _params, _context, _many) -> None:  # type: ignore[no-untyped-def]
            statements.append(statement)

        event.listen(db.get_bind(), "before_cursor_execute", before_cursor_execute)
        try:
            response = client.get("/api/v1/sync-status")
        finally:
            event.remove(db.get_bind(), "before_cursor_execute", before_cursor_execute)
        assert response.status_code == 200
        selects = [
            statement for statement in statements if statement.lstrip().upper().startswith("SELECT")
        ]
        assert len(selects) <= 2
        assert "ROW_NUMBER() OVER" in selects[-1].upper()


def test_sync_status_ignores_cross_platform_job_runs() -> None:
    with make_client(foreign_keys=False) as (client, db, ids):
        google_account = db.get(AdvertisingAccount, ids["a1"])
        assert google_account is not None
        meta_account = AdvertisingAccount(
            platform=AdvertisingPlatform.META_ADS,
            external_account_id="meta-100",
            name="Meta account",
            currency_code="USD",
            time_zone="UTC",
        )
        db.add(meta_account)
        db.flush()
        correct_success = datetime(2026, 7, 17, tzinfo=UTC)
        db.add_all(
            [
                JobRun(
                    platform=AdvertisingPlatform.GOOGLE_ADS,
                    account_id=google_account.id,
                    job_name="sync",
                    status=JobRunStatus.SUCCEEDED,
                    started_at=correct_success,
                    finished_at=correct_success,
                    records_processed=12,
                ),
                JobRun(
                    platform=AdvertisingPlatform.META_ADS,
                    account_id=google_account.id,
                    job_name="malformed",
                    status=JobRunStatus.FAILED,
                    started_at=datetime(2026, 7, 20, tzinfo=UTC),
                    finished_at=datetime(2026, 7, 20, tzinfo=UTC),
                    records_processed=100,
                ),
                JobRun(
                    platform=AdvertisingPlatform.META_ADS,
                    account_id=meta_account.id,
                    job_name="sync",
                    status=JobRunStatus.SUCCEEDED,
                    started_at=correct_success,
                    finished_at=correct_success,
                    records_processed=13,
                ),
                JobRun(
                    platform=AdvertisingPlatform.META_ADS,
                    account_id=meta_account.id,
                    job_name="sync",
                    status=JobRunStatus.FAILED,
                    started_at=datetime(2026, 7, 18, tzinfo=UTC),
                    finished_at=datetime(2026, 7, 18, tzinfo=UTC),
                    records_processed=14,
                ),
                JobRun(
                    platform=AdvertisingPlatform.GOOGLE_ADS,
                    account_id=meta_account.id,
                    job_name="malformed",
                    status=JobRunStatus.SUCCEEDED,
                    started_at=datetime(2026, 7, 20, tzinfo=UTC),
                    finished_at=datetime(2026, 7, 20, tzinfo=UTC),
                    records_processed=101,
                ),
                JobRun(
                    platform=AdvertisingPlatform.GOOGLE_ADS,
                    account_id=None,
                    job_name="platform-sync",
                    status=JobRunStatus.FAILED,
                    started_at=datetime(2026, 7, 21, tzinfo=UTC),
                    finished_at=datetime(2026, 7, 21, tzinfo=UTC),
                    records_processed=102,
                ),
            ]
        )
        db.commit()

        response = client.get("/api/v1/sync-status").json()
        statuses = {item["account_id"]: item for item in response["items"]}

        assert statuses[google_account.id]["latest_status"] == "succeeded"
        assert statuses[google_account.id]["records_processed"] == 12
        assert statuses[google_account.id]["last_success_at"].startswith("2026-07-17")
        assert statuses[meta_account.id]["latest_status"] == "failed"
        assert statuses[meta_account.id]["records_processed"] == 14
        assert statuses[meta_account.id]["last_success_at"].startswith("2026-07-17")


def test_sync_status_indexes_and_openapi_error_schemas_are_documented() -> None:
    index_names = {index.name for index in Base.metadata.tables["job_runs"].indexes}
    assert {"ix_job_runs_account_started_id", "ix_job_runs_account_status_finished"} <= index_names
    foreign_keys = Base.metadata.tables["job_runs"].foreign_key_constraints
    job_run_account_fk = next(
        fk for fk in foreign_keys if fk.name == "fk_job_runs_account_platform"
    )
    assert [column.name for column in job_run_account_fk.columns] == ["account_id", "platform"]
    migration = Path("migrations/versions/20260717_0003_job_run_sync_status_indexes.py").read_text()
    assert "ix_job_runs_account_started_id" in migration
    assert "ix_job_runs_account_status_finished" in migration
    composite_fk_migration = Path(
        "migrations/versions/20260717_0004_job_run_account_platform_foreign_key.py"
    ).read_text()
    assert "fk_job_runs_account_platform" in composite_fk_migration
    assert "job_runs_account_id_fkey" in composite_fk_migration

    schema = TestClient(app).get("/openapi.json").json()
    assert "ApiErrorResponse" in schema["components"]["schemas"]
    expected = {
        "/api/v1/accounts/{account_id}",
        "/api/v1/accounts/{account_id}/campaigns",
        "/api/v1/campaigns/{campaign_id}",
        "/api/v1/campaigns/{campaign_id}/ad-groups",
        "/api/v1/campaigns/{campaign_id}/metrics",
        "/api/v1/accounts/{account_id}/metrics/summary",
        "/api/v1/job-runs/latest",
    }
    for path in expected:
        responses = schema["paths"][path]["get"]["responses"]
        assert {"404", "422", "503"} <= set(responses)
        assert responses["404"]["content"]["application/json"]["schema"]["$ref"].endswith(
            "/ApiErrorResponse"
        )
    for path in {"/api/v1/accounts", "/api/v1/job-runs", "/api/v1/sync-status"}:
        responses = schema["paths"][path]["get"]["responses"]
        assert {"422", "503"} <= set(responses)
