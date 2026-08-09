import asyncio
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from importlib import import_module
from pathlib import Path
from secrets import token_urlsafe
from sqlite3 import Connection as SQLiteConnection

import pytest
from app.ads.enums import AdvertisingPlatform, JobRunStatus
from app.ads.models import AdGroup, AdvertisingAccount, Campaign, DailyMetric, JobRun
from app.ads.schemas import AdvertisingAccountCreate
from app.api.auth import require_api_token
from app.collectors import google_ads
from app.database.session import Base, get_db
from app.main import app
from app.settings import settings
from app.workspaces.models import Workspace
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, event
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import ConnectionPoolEntry, StaticPool
from sqlalchemy.schema import CreateIndex
from starlette.types import Message, Scope

RawResponse = tuple[int, list[tuple[bytes, bytes]], bytes]


def enable_fk(dbapi_connection: SQLiteConnection, _connection_record: ConnectionPoolEntry) -> None:
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


def operator_token() -> str:
    return token_urlsafe(48)


def seed(db: Session) -> dict[str, int]:
    workspace = Workspace(
        slug="denticode",
        name="Denticode Ad Analyzer",
        client_name="Denticode",
        status="active",
        is_default=True,
    )
    db.add(workspace)
    db.flush()
    a1 = AdvertisingAccount(
        workspace_id=workspace.id,
        platform=AdvertisingPlatform.GOOGLE_ADS,
        external_account_id="100",
        name="Denticode",
        currency_code="USD",
        time_zone="UTC",
    )
    a2 = AdvertisingAccount(
        workspace_id=workspace.id,
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
                ad_group_id=ag1.id,
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
                workspace_id=workspace.id,
                platform=a1.platform,
                account_id=a1.id,
                job_name="sync",
                status=JobRunStatus.SUCCEEDED,
                started_at=now - timedelta(days=1),
                finished_at=now - timedelta(days=1),
                records_processed=7,
            ),
            JobRun(
                workspace_id=workspace.id,
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
    return {
        "workspace": workspace.id,
        "a1": a1.id,
        "a2": a2.id,
        "c1": c1.id,
        "c2": c2.id,
        "ag1": ag1.id,
    }


@contextmanager
def make_client(
    *, foreign_keys: bool = True, bypass_auth: bool = True
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
    if bypass_auth:
        app.dependency_overrides[require_api_token] = lambda: None
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
        campaign_performance = client.get(
            f"/api/v1/accounts/{ids['a1']}/campaign-performance"
            "?date_from=2026-07-01&date_to=2026-07-02"
        ).json()
        assert campaign_performance["total"] == 2
        campaign_row = campaign_performance["items"][0]
        assert campaign_row["entity_type"] == "campaign"
        assert campaign_row["entity_id"] == ids["c1"]
        assert campaign_row["current"]["clicks"] == 10
        assert campaign_row["current"]["cost_micros"] == 1_000_000
        assert campaign_row["current"]["platform_conversions"] == "2.500000"
        assert "external_campaign_id" not in str(campaign_performance)
        ad_group_performance = client.get(
            f"/api/v1/campaigns/{ids['c1']}/ad-group-performance"
            "?date_from=2026-07-01&date_to=2026-07-02"
        ).json()
        assert ad_group_performance["total"] == 1
        ad_group_row = ad_group_performance["items"][0]
        assert ad_group_row["entity_type"] == "ad_group"
        assert ad_group_row["entity_id"] == ids["ag1"]
        assert ad_group_row["current"]["clicks"] == 999
        assert ad_group_row["current"]["cost_micros"] == 999_000_000
        assert "search_term" not in str(ad_group_performance).lower()
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
    app.dependency_overrides[require_api_token] = lambda: None
    try:
        response = TestClient(app, raise_server_exceptions=False).get("/api/v1/accounts")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 503
    assert response.json() == {"detail": "database temporarily unavailable"}


def test_api_v1_requires_bearer_authentication_for_every_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = operator_token()
    monkeypatch.setattr(settings, "denticode_api_token", SecretStr(token))
    client = TestClient(app, raise_server_exceptions=False)
    protected_routes = [
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/v1")
    ]
    for route in protected_routes:
        path = route.path.replace("{account_id}", "1").replace("{campaign_id}", "1")
        response = client.get(path)
        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"
        assert response.json() == {"detail": "authentication failed"}

    invalid = client.get("/api/v1/accounts", headers={"Authorization": "Bearer invalid"})
    malformed = client.get("/api/v1/accounts", headers={"Authorization": "Basic invalid"})
    assert invalid.status_code == 401 and malformed.status_code == 401
    assert all(
        response.headers["WWW-Authenticate"] == "Bearer" for response in (invalid, malformed)
    )
    assert token not in invalid.text and token not in malformed.text
    assert token not in client.get("/openapi.json").text


@pytest.mark.parametrize(
    "credential",
    [
        b"a" * 42,
        b"a" * 129,
        b"a" * 42 + b" ",
        b"a" * 42 + b"\t",
        b"a" * 42 + b"\n",
        b"a" * 42 + b"\x00",
        b"a" * 42 + b".",
        b"a" * 42 + b"\xff",
    ],
)
def test_invalid_raw_bearer_headers_return_generic_401(
    monkeypatch: pytest.MonkeyPatch, credential: bytes
) -> None:
    token = operator_token()
    monkeypatch.setattr(settings, "denticode_api_token", SecretStr(token))
    messages: list[Message] = []
    scope: Scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/api/v1/accounts",
        "raw_path": b"/api/v1/accounts",
        "query_string": b"",
        "headers": [(b"authorization", b"Bearer " + credential)],
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
    }

    async def receive() -> Message:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: Message) -> None:
        messages.append(message)

    asyncio.run(app(scope, receive, send))
    response_start = next(
        message for message in messages if message["type"] == "http.response.start"
    )
    response_body = b"".join(
        message.get("body", b"") for message in messages if message["type"] == "http.response.body"
    )
    assert response_start["status"] == 401
    assert (b"www-authenticate", b"Bearer") in response_start["headers"]
    assert response_body == b'{"detail":"authentication failed"}'
    assert token.encode() not in response_body and credential not in response_body


def raw_api_response(headers: list[tuple[bytes, bytes]]) -> RawResponse:
    messages: list[Message] = []
    scope: Scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/api/v1/accounts",
        "raw_path": b"/api/v1/accounts",
        "query_string": b"",
        "headers": headers,
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
    }

    async def receive() -> Message:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: Message) -> None:
        messages.append(message)

    asyncio.run(app(scope, receive, send))
    response_start = next(
        message for message in messages if message["type"] == "http.response.start"
    )
    response_body = b"".join(
        message.get("body", b"") for message in messages if message["type"] == "http.response.body"
    )
    return response_start["status"], response_start["headers"], response_body


def test_duplicate_authorization_headers_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    token = operator_token()
    other_token = operator_token()
    monkeypatch.setattr(settings, "denticode_api_token", SecretStr(token))
    valid = b"Bearer " + token.encode()
    invalid = b"Bearer invalid"
    duplicate_cases: tuple[list[tuple[bytes, bytes]], ...] = (
        [],
        [(b"authorization", valid), (b"authorization", invalid)],
        [(b"authorization", invalid), (b"authorization", valid)],
        [(b"authorization", valid), (b"authorization", valid)],
        [(b"authorization", valid), (b"authorization", b"Bearer " + other_token.encode())],
        [(b"authorization", valid), (b"authorization", b"Basic ignored")],
        [(b"Authorization", valid), (b"aUtHoRiZaTiOn", invalid)],
    )
    for headers in duplicate_cases:
        status, response_headers, response_body = raw_api_response(headers)
        assert status == 401
        assert (b"www-authenticate", b"Bearer") in response_headers
        assert response_body == b'{"detail":"authentication failed"}'
        assert token.encode() not in response_body and other_token.encode() not in response_body


def test_duplicate_non_authorization_headers_do_not_change_authentication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = operator_token()
    monkeypatch.setattr(settings, "denticode_api_token", SecretStr(token))
    status, _headers, body = raw_api_response(
        [
            (b"authorization", b"Bearer " + token.encode()),
            (b"x-request-id", b"one"),
            (b"X-Request-ID", b"two"),
        ]
    )
    assert status != 401
    assert token.encode() not in body


def test_raw_authorization_header_name_casing_authenticates_consistently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = operator_token()
    monkeypatch.setattr(settings, "denticode_api_token", SecretStr(token))
    with make_client(bypass_auth=False) as (_client, _db, _ids):
        for header_name in (b"authorization", b"AUTHORIZATION", b"aUtHoRiZaTiOn"):
            status, _headers, _body = raw_api_response([(header_name, b"bEaReR " + token.encode())])
            assert status == 200
        status, response_headers, body = raw_api_response([(b"AUTHORIZATION", b"Bearer invalid")])
        assert status == 401
        assert (b"www-authenticate", b"Bearer") in response_headers
        assert body == b'{"detail":"authentication failed"}'


@pytest.mark.parametrize(
    "authorization_value",
    [
        b"Basic ignored",
        b"Bearer",
        b"Bearer ",
        b"Bearer  token",
        b"Bearer\ttoken",
        b"Bearer token extra",
        b"Bearer \x00",
        b"Bearer \xff",
    ],
)
def test_malformed_raw_bearer_format_returns_generic_401(
    monkeypatch: pytest.MonkeyPatch, authorization_value: bytes
) -> None:
    monkeypatch.setattr(settings, "denticode_api_token", SecretStr(operator_token()))
    status, response_headers, body = raw_api_response([(b"aUtHoRiZaTiOn", authorization_value)])
    assert status == 401
    assert (b"www-authenticate", b"Bearer") in response_headers
    assert body == b'{"detail":"authentication failed"}'


def test_api_v1_valid_auth_and_invalid_configuration_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = operator_token()
    monkeypatch.setattr(settings, "denticode_api_token", SecretStr(token))
    with make_client(bypass_auth=False) as (client, _db, _ids):
        response = client.get("/api/v1/accounts", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
    monkeypatch.setattr(settings, "denticode_api_token", None)
    unavailable = TestClient(app, raise_server_exceptions=False).get("/api/v1/accounts")
    assert unavailable.status_code == 503
    assert unavailable.json() == {"detail": "service temporarily unavailable"}
    for invalid_token in (
        "a" * 42,
        "a" * 129,
        "a" * 42 + " ",
        "a" * 42 + "\t",
        "a" * 42 + "\n",
        "a" * 42 + "\x00",
        "a" * 42 + ".",
        "a" * 42 + "\u00e9",
    ):
        monkeypatch.setattr(settings, "denticode_api_token", SecretStr(invalid_token))
        invalid_configuration = TestClient(app, raise_server_exceptions=False).get(
            "/api/v1/accounts"
        )
        assert invalid_configuration.status_code == 503
        assert invalid_configuration.json() == {"detail": "service temporarily unavailable"}
        assert invalid_token not in invalid_configuration.text
    assert TestClient(app).get("/").status_code == 200
    assert TestClient(app).get("/health").status_code == 200


def test_job_run_error_messages_are_replaced_at_the_http_boundary() -> None:
    malicious_error = (
        "client_secret=do-not-expose refresh_token=do-not-expose "
        "Authorization: Bearer do-not-expose postgresql://operator:password@host/db "
        "Traceback customer-identifier " + "x" * 10_000
    )
    with make_client() as (client, db, ids):
        account = db.get(AdvertisingAccount, ids["a1"])
        assert account is not None
        db.add(
            JobRun(
                platform=account.platform,
                account_id=account.id,
                job_name="sync",
                status=JobRunStatus.FAILED,
                started_at=datetime(2026, 7, 30, tzinfo=UTC),
                finished_at=datetime(2026, 7, 30, tzinfo=UTC),
                records_processed=0,
                error_message=malicious_error,
            )
        )
        db.commit()
        listed = client.get("/api/v1/job-runs").json()
        latest = client.get("/api/v1/job-runs/latest").json()

    public_payload = f"{listed}{latest}"
    for sensitive_fragment in (
        "client_secret",
        "refresh_token",
        "Authorization",
        "postgresql://",
        "Traceback",
        "customer-identifier",
        "do-not-expose",
    ):
        assert sensitive_fragment not in public_payload
    assert latest["error_message"] == "Google Ads synchronization failed."
    public_messages = {None, "Google Ads synchronization failed."}
    assert all(item["error_message"] in public_messages for item in listed["items"])


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
        assert (
            client.get(
                f"/api/v1/campaigns/{ids['c1']}/metrics?date_from=2026-07-01&date_to=2026-07-03&limit=101"
            ).status_code
            == 422
        )


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


def test_job_run_account_delete_is_restricted_and_unscoped_runs_are_valid() -> None:
    with make_client() as (_client, db, ids):
        account = db.get(AdvertisingAccount, ids["a1"])
        assert account is not None
        db.delete(account)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        db.add(
            JobRun(
                platform=AdvertisingPlatform.GOOGLE_ADS,
                account_id=None,
                job_name="platform-sync",
                status=JobRunStatus.SUCCEEDED,
                started_at=datetime(2026, 7, 20, tzinfo=UTC),
                finished_at=datetime(2026, 7, 20, tzinfo=UTC),
                records_processed=1,
            )
        )
        db.commit()


def test_legacy_cross_platform_job_runs_are_detached_before_constraint_creation() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        connection.exec_driver_sql(
            "CREATE TABLE advertising_accounts ("
            "id INTEGER PRIMARY KEY, platform TEXT NOT NULL, UNIQUE (id, platform))"
        )
        connection.exec_driver_sql(
            "CREATE TABLE job_runs (id INTEGER PRIMARY KEY, platform TEXT NOT NULL, "
            "account_id INTEGER)"
        )
        connection.exec_driver_sql(
            "INSERT INTO advertising_accounts (id, platform) VALUES (1, 'google_ads')"
        )
        connection.exec_driver_sql(
            "INSERT INTO job_runs (id, platform, account_id) VALUES "
            "(1, 'google_ads', 1), (2, 'meta_ads', 1), (3, 'meta_ads', NULL)"
        )
        migration = import_module(
            "migrations.versions.20260717_0004_job_run_account_platform_foreign_key"
        )
        migration.cleanup_legacy_cross_platform_job_runs(connection)
        rows = connection.exec_driver_sql(
            "SELECT id, account_id FROM job_runs ORDER BY id"
        ).fetchall()
        assert [(row[0], row[1]) for row in rows] == [(1, 1), (2, None), (3, None)]

        connection.exec_driver_sql(
            "CREATE TABLE scoped_job_runs ("
            "id INTEGER PRIMARY KEY, platform TEXT NOT NULL, account_id INTEGER, "
            "FOREIGN KEY (account_id, platform) REFERENCES advertising_accounts (id, platform) "
            "ON DELETE RESTRICT)"
        )
        connection.exec_driver_sql(
            "INSERT INTO scoped_job_runs (id, platform, account_id) "
            "SELECT id, platform, account_id FROM job_runs"
        )


def test_sync_status_indexes_and_openapi_error_schemas_are_documented() -> None:
    indexes = Base.metadata.tables["job_runs"].indexes
    latest_index = next(
        index for index in indexes if index.name == "ix_job_runs_account_platform_started_id"
    )
    success_index = next(
        index for index in indexes if index.name == "ix_job_runs_account_platform_status_finished"
    )
    latest_index_sql = str(
        CreateIndex(latest_index).compile(
            dialect=postgresql.dialect()  # type: ignore[no-untyped-call]
        )
    )
    success_index_sql = str(
        CreateIndex(success_index).compile(
            dialect=postgresql.dialect()  # type: ignore[no-untyped-call]
        )
    )
    assert "account_id, platform, started_at DESC, id DESC" in latest_index_sql
    assert "account_id, platform, status, finished_at DESC" in success_index_sql
    assert "WHERE account_id IS NOT NULL" in latest_index_sql
    foreign_keys = Base.metadata.tables["job_runs"].foreign_key_constraints
    job_run_account_fk = next(
        fk for fk in foreign_keys if fk.name == "fk_job_runs_account_platform"
    )
    assert [column.name for column in job_run_account_fk.columns] == ["account_id", "platform"]
    assert job_run_account_fk.ondelete == "RESTRICT"
    migration = Path("migrations/versions/20260717_0003_job_run_sync_status_indexes.py").read_text()
    assert "ix_job_runs_account_platform_started_id" in migration
    assert "ix_job_runs_account_platform_status_finished" in migration
    composite_fk_migration = Path(
        "migrations/versions/20260717_0004_job_run_account_platform_foreign_key.py"
    ).read_text()
    assert "fk_job_runs_account_platform" in composite_fk_migration
    assert "job_runs_account_id_fkey" in composite_fk_migration
    assert "cleanup_legacy_cross_platform_job_runs" in composite_fk_migration
    assert 'ondelete="RESTRICT"' in composite_fk_migration

    schema = TestClient(app).get("/openapi.json").json()
    assert "ApiErrorResponse" in schema["components"]["schemas"]
    expected = {
        "/api/v1/accounts/{account_id}",
        "/api/v1/accounts/{account_id}/campaigns",
        "/api/v1/accounts/{account_id}/campaign-performance",
        "/api/v1/campaigns/{campaign_id}",
        "/api/v1/campaigns/{campaign_id}/ad-groups",
        "/api/v1/campaigns/{campaign_id}/ad-group-performance",
        "/api/v1/campaigns/{campaign_id}/metrics",
        "/api/v1/accounts/{account_id}/metrics/summary",
        "/api/v1/job-runs/latest",
    }
    for path in expected:
        responses = schema["paths"][path]["get"]["responses"]
        assert {"401", "404", "422", "503"} <= set(responses)
        assert responses["404"]["content"]["application/json"]["schema"]["$ref"].endswith(
            "/ApiErrorResponse"
        )
    for path in {"/api/v1/accounts", "/api/v1/job-runs", "/api/v1/sync-status"}:
        responses = schema["paths"][path]["get"]["responses"]
        assert {"401", "422", "503"} <= set(responses)
    for path, operations in schema["paths"].items():
        if path.startswith("/api/v1"):
            assert operations["get"]["security"] == [{"BearerAuth": []}]
