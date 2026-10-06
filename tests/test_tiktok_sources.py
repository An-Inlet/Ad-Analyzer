"""Offline TikTok onboarding/import/report isolation; no provider network calls."""

import logging
from datetime import date, timedelta
from typing import Any, Literal
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest
from app.ads.enums import AdvertisingPlatform
from app.ads.models import DailyMetric, JobRun
from app.analysis.platform_evidence import has_platform_conversion_metrics
from app.customers.oauth import callback_relay
from app.settings import settings
from app.shopify.logging import OAuthAccessFilter
from app.sources import advertising, service
from app.sources.contracts import SourceAccount, SourceGrant, UnavailableSource
from app.sources.models import SourceConnection
from cryptography.fernet import Fernet
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_google_customer_connections import setup


class TikTokFixture:
    mode: Literal["fixture"] = "fixture"

    def __init__(self) -> None:
        self.calls = 0
        self.fail = False
        self.wrong = False

    def authorize_url(self, state: str, redirect_uri: str) -> str:
        return "https://business-api.tiktok.com/portal/auth?" + urlencode(
            {"state": state, "redirect_uri": redirect_uri}
        )

    def exchange(self, code: str, redirect_uri: str) -> SourceGrant:
        self.calls += 1
        return SourceGrant(
            access_token=SecretStr("synthetic-tiktok-token"),
            expires_at=NOW + timedelta(days=1),
            accounts=[
                SourceAccount(
                    external_id="123456", name="Fixture TikTok", currency="USD", time_zone="UTC"
                )
            ],
        )

    def read(
        self, account: str, token: str, start: date, end: date, cursor: str | None
    ) -> dict[str, Any]:
        self.calls += 1
        if self.fail:
            raise RuntimeError("fixture-only private error detail")
        page: dict[str, Any] = {"account_id": "999" if self.wrong else account, "currency": "USD"}
        if cursor is None:
            page.update(
                campaigns=[
                    {
                        "id": "1",
                        "name": "Fixture campaign",
                        "status": "PAUSED",
                        "objective": "CONVERSIONS",
                    }
                ],
                groups=[
                    {"id": "2", "campaign_id": "1", "name": "Fixture group", "status": "PAUSED"}
                ],
                ads=[{"id": "3", "group_id": "2", "name": "Fixture ad", "status": "PAUSED"}],
                next_cursor="metrics",
            )
        else:
            page["metrics"] = [
                {
                    "level": level,
                    "id": entity,
                    "day": end.isoformat(),
                    "impressions": 100,
                    "clicks": 10,
                    "cost_micros": 100_000_000,
                    "conversions": "1.25",
                    "conversion_value_micros": 0,
                }
                for level, entity in [("campaign", "1"), ("ad_group", "2"), ("ad", "3")]
            ]
        return page


@pytest.fixture()
def configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        settings, "source_token_encryption_key", SecretStr(Fernet.generate_key().decode())
    )
    monkeypatch.setattr(settings, "customer_app_origin", "https://inlet.example")


def connect(
    db: Session, wid: int, sid: str, fixture: TikTokFixture
) -> tuple[SourceConnection, str]:
    nonce = parse_qs(urlsplit(service.begin(db, "tiktok_ads", wid, sid, fixture, NOW)).query)[
        "state"
    ][0]
    service.finish(db, "tiktok_ads", nonce, sid, "fixture-code", fixture, NOW)
    return service.select_account(db, "tiktok_ads", nonce, sid, "123456", NOW), nonce


def test_unrelated_customers_partial_retry_reconnect_and_disabled_transport(
    customer_engine: Engine, configured: None
) -> None:
    from app.api.repository import ReadOnlyAdsRepository

    with Session(customer_engine) as db:
        one, sid = setup(db, "one")
        two, sid2 = setup(db, "two")
        fixture = TikTokFixture()
        with pytest.raises(HTTPException) as error:
            service.begin(db, "tiktok_ads", one, sid, UnavailableSource(), NOW)
        assert error.value.status_code == 503
        a, nonce = connect(db, one, sid, fixture)
        b, _ = connect(db, two, sid2, fixture)
        assert a.account_id != b.account_id
        with pytest.raises(HTTPException):
            service.authorization(db, "tiktok_ads", nonce, sid2, NOW)
        with pytest.raises(HTTPException):
            service.finish(db, "tiktok_ads", nonce, sid, "fixture-code", fixture, NOW)
        assert service.select_account(db, "tiktok_ads", nonce, sid, "123456", NOW).id == a.id
        assert advertising.tick(db, one, a.id, a.generation, fixture, NOW) is None
        assert db.scalar(select(func.count()).select_from(DailyMetric)) == 0
        fixture.fail = True
        with pytest.raises(HTTPException, match="source read unavailable"):
            advertising.tick(db, one, a.id, a.generation, fixture, NOW)
        assert a.cursor == "metrics"
        fixture.fail = False
        jobid = advertising.tick(db, one, a.id, a.generation, fixture, NOW)
        job = db.get(JobRun, jobid)
        assert job is not None and job.workspace_id == one and job.connection_id == a.integration_id
        assert db.scalar(select(func.count()).select_from(DailyMetric)) == 3
        assert a.account_id is not None
        totals = ReadOnlyAdsRepository(db).account_metric_totals(
            a.account_id, a.window_start, a.window_end
        )
        assert totals["cost_micros"] == 100_000_000  # Not three overlapping grains added.
        assert not has_platform_conversion_metrics(db, a.account_id, AdvertisingPlatform.TIKTOK_ADS)
        assert b.last_sync_at is None
        generation = a.generation
        service.disconnect(db, a)
        assert a.encrypted_grant is None
        with pytest.raises(HTTPException):
            advertising.tick(db, one, a.id, generation, fixture, NOW)
        renewed, _ = connect(db, one, sid, fixture)
        assert (
            renewed.id == a.id and renewed.generation > generation and renewed.covered_from is None
        )
        with pytest.raises(HTTPException):
            advertising.tick(db, one, a.id, generation, fixture, NOW)
        fixture.wrong = True
        with pytest.raises(HTTPException, match="account/currency mismatch"):
            advertising.tick(db, one, a.id, a.generation, fixture, NOW)


def test_callback_redaction_and_content_security() -> None:
    guard = OAuthAccessFilter()
    for path in (
        "/api/customer/v1/google/callback",
        "/api/customer/v1/sources/tiktok_ads/callback",
    ):
        record = logging.LogRecord(
            "uvicorn.access",
            logging.INFO,
            "",
            1,
            path + "?auth_code=fixture-secret&state=fixture-state",
            (),
            None,
        )
        assert guard.filter(record) is False
    response = callback_relay()
    assert "sha256-" in response.headers["content-security-policy"]
    assert response.headers["referrer-policy"] == "no-referrer"
    assert b"history.replaceState" in response.body and b"auth_code" in response.body


def test_tiktok_wire_paths_pages_and_metrics() -> None:
    from app.tiktok.wire import TikTokReadAdapter

    requests: list[tuple[str, str]] = []

    def io(method: str, path: str, params: dict[str, Any], token: str | None) -> dict[str, Any]:
        requests.append((method, path))
        if "oauth2/access_token" in path:
            assert params["auth_code"] == "fixture-code"
            return {
                "code": 0,
                "data": {"access_token": "fixture-token", "advertiser_ids": ["123456"]},
            }
        if "advertiser/info" in path:
            return {
                "code": 0,
                "data": {
                    "list": [
                        {
                            "advertiser_id": "123456",
                            "name": "Fixture",
                            "currency": "USD",
                            "timezone": "UTC",
                        }
                    ]
                },
            }
        assert method == "GET" and token == "fixture-token"
        rows: list[dict[str, Any]]
        if path.endswith("campaign/get/"):
            rows = [
                {
                    "campaign_id": "1",
                    "campaign_name": "Fixture",
                    "operation_status": "DISABLE",
                    "objective_type": "CONVERSIONS",
                }
            ]
        elif path.endswith("adgroup/get/"):
            rows = [
                {
                    "adgroup_id": "2",
                    "campaign_id": "1",
                    "adgroup_name": "Fixture",
                    "operation_status": "DISABLE",
                }
            ]
        elif path.endswith("ad/get/"):
            rows = [
                {
                    "ad_id": "3",
                    "adgroup_id": "2",
                    "ad_name": "Fixture",
                    "operation_status": "DISABLE",
                }
            ]
        else:
            assert (
                path.endswith("report/integrated/get/") and params["enable_total_metrics"] is False
            )
            key = params["dimensions"][0]
            entity = {"campaign_id": "1", "adgroup_id": "2", "ad_id": "3"}[key]
            rows = [
                {
                    "dimensions": {key: entity, "stat_time_day": "2026-10-04 00:00:00"},
                    "metrics": {
                        "impressions": "100",
                        "clicks": "10",
                        "spend": "12.34",
                        "conversion": "1.5",
                    },
                }
            ]
        return {"code": 0, "data": {"list": rows, "page_info": {"page": 1, "total_page": 1}}}

    adapter = TikTokReadAdapter(io, "fixture-app", SecretStr("fixture-secret"))
    assert "state=fixture" in adapter.authorize_url("fixture", "https://inlet.example/callback")
    grant = adapter.exchange("fixture-code", "https://inlet.example/callback")
    assert grant.accounts[0].external_id == "123456"
    cursor = None
    pages = []
    for _ in range(6):
        result = adapter.read(
            "123456", "fixture-token", date(2026, 10, 1), date(2026, 10, 4), cursor
        )
        pages.append(result)
        cursor = result["next_cursor"]
    assert cursor is None and pages[-1]["metrics"][0]["cost_micros"] == 12_340_000
    assert all(method == "GET" for method, path in requests if "oauth2" not in path)


def test_customer_sources_api_scope_csrf_and_expiry(
    customer_engine: Engine, configured: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from collections.abc import Generator
    from unittest.mock import Mock

    from app.api import customer_sources as api
    from app.api.customer import router as auth_router
    from app.customers.access import CSRF_COOKIE
    from app.customers.identity import get_identity_provider
    from app.customers.models import CustomerMembership
    from app.database.session import get_db
    from app.sources.contracts import get_source_transport
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from tests.test_customer_identity import ORIGIN, FakeProvider, login

    clock = Mock()
    clock.now.return_value = NOW
    monkeypatch.setattr(api, "datetime", clock)
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(api.router)
    fixture = TikTokFixture()

    def database() -> Generator[Session, None, None]:
        with Session(customer_engine) as db:
            yield db

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_identity_provider] = lambda: FakeProvider()
    app.dependency_overrides[get_source_transport] = lambda: fixture
    owner, outsider = TestClient(app, base_url=ORIGIN), TestClient(app, base_url=ORIGIN)
    user = login(owner, "owner:1")
    login(outsider, "outsider:1")
    with Session(customer_engine) as db:
        wid, _ = setup(db, "one")
        db.add(CustomerMembership(user_id=user, workspace_id=wid, role="owner", status="active"))
        db.commit()
    prefix = f"/api/customer/v1/workspaces/{wid}/sources/tiktok_ads"
    headers = {"Origin": ORIGIN, "X-CSRF-Token": owner.cookies[CSRF_COOKIE]}
    assert outsider.get(prefix).status_code == 404
    assert owner.post(prefix + "/authorize").status_code == 403
    response = owner.post(prefix + "/authorize", headers=headers)
    assert response.status_code == 200
    nonce = parse_qs(urlsplit(response.json()["authorization_url"]).query)["state"][0]
    callback = "/api/customer/v1/sources/tiktok_ads/callback"
    assert (
        owner.post(
            callback, json={"state": nonce, "code": "fixture-code"}, headers=headers
        ).status_code
        == 200
    )
    response = owner.post(
        prefix + "/select", json={"state": nonce, "external_id": "123456"}, headers=headers
    )
    assert response.status_code == 200 and response.json()["live_verified"] is False
    cid = response.json()["id"]
    report = owner.get(prefix + f"/{cid}/report?start=2026-10-01&end=2026-10-04")
    assert report.status_code == 200 and report.json()["spend_micros"] is None
    with Session(customer_engine) as db:
        row = service.owned(db, wid, "tiktok_ads", cid)
        with pytest.raises(HTTPException, match="refresh/reconnect"):
            advertising.tick(db, wid, cid, row.generation, fixture, NOW + timedelta(days=2))
        assert row.status == "reconnect_required"
    assert owner.delete(prefix + "/" + cid, headers=headers).status_code == 200


def test_source_migration_refuses_to_orphan_tiktok_accounts(
    customer_engine: Engine, configured: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    if customer_engine.dialect.name != "postgresql":
        return
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text

    with Session(customer_engine) as db:
        wid, sid = setup(db, "one")
        row, _ = connect(db, wid, sid, TikTokFixture())
        cid = row.id
    with customer_engine.connect() as connection:
        schema = connection.scalar(text("SELECT current_schema()"))
    url = customer_engine.url.update_query_dict({"options": f"-csearch_path={schema}"})
    monkeypatch.setattr(settings, "database_url", url.render_as_string(hide_password=False))
    config = Config("alembic.ini")
    command.stamp(config, "head")
    with pytest.raises(RuntimeError, match="preservation plan"):
        command.downgrade(config, "20261006_0029")
    with Session(customer_engine) as db:
        assert db.get(SourceConnection, cid) is not None
