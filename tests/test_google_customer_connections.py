"""B08 acceptance uses synthetic grants and isolated databases, never Google endpoints."""

from datetime import date, timedelta
from typing import Literal
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
from app.ads.models import Campaign, DailyMetric, JobRun
from app.customers.models import CustomerSession, CustomerUser
from app.google_connections import service as s
from app.google_connections.contracts import (
    Account,
    CampaignRow,
    Grant,
    MetricRow,
    Page,
    UnavailableTransport,
)
from app.google_connections.models import GoogleAuthorization, GoogleCustomerConnection
from app.google_connections.security import Vault
from app.settings import settings
from app.workspaces.models import Workspace
from cryptography.fernet import Fernet
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine


class FixtureTransport:
    mode: Literal["fixture"] = "fixture"

    def __init__(self) -> None:
        self.calls = 0
        self.fail = False
        self.wrong_account = False
        self.accounts = [
            Account(
                external_id="1234567890", name="Fixture account", currency="USD", time_zone="UTC"
            )
        ]

    def exchange(self, code: str, redirect_uri: str) -> Grant:
        self.calls += 1
        return Grant(refresh_token=SecretStr("synthetic-fixture-value"), accounts=self.accounts)

    def page(
        self,
        refresh_token: str,
        account_id: str,
        start: date,
        end: date,
        cursor: str | None,
        login_customer_id: str | None = None,
    ) -> Page:
        self.calls += 1
        if self.fail:
            raise RuntimeError("synthetic failure with sensitive text that must not escape")
        return Page(
            external_account_id="9999999999" if self.wrong_account else account_id,
            campaigns=[
                CampaignRow(external_id="1", name="Fixture", status="PAUSED", channel="SEARCH")
            ],
            metrics=[
                MetricRow(
                    campaign_external_id="1",
                    day=start if cursor is None else end,
                    impressions=100,
                    clicks=10,
                    cost_micros=100,
                    conversions="1.5",
                    conversion_value_micros=300,
                )
            ],
            next_cursor="page-two" if cursor is None else None,
        )


@pytest.fixture()
def configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        settings, "google_customer_encryption_key", SecretStr(Fernet.generate_key().decode())
    )
    monkeypatch.setattr(settings, "google_customer_client_id", "fixture-client")
    monkeypatch.setattr(settings, "customer_app_origin", "https://inlet.example")


def setup(db: Session, name: str) -> tuple[int, str]:
    wid = Workspace(slug=name, name=name, client_name=name, status="active")
    user = CustomerUser(
        id=uuid4().hex, issuer="fixture", subject=name, email="fixture@example.test"
    )
    db.add_all([wid, user])
    db.flush()
    sid = uuid4().hex * 2
    db.add(
        CustomerSession(
            digest=sid,
            user_id=user.id,
            csrf_digest="a" * 64,
            created_at=1,
            expires_at=2**40,
            authenticated_at=1,
        )
    )
    db.commit()
    return wid.id, sid


def connect(
    db: Session, wid: int, sid: str, transport: FixtureTransport
) -> tuple[GoogleCustomerConnection, str]:
    nonce = parse_qs(urlsplit(s.start(db, wid, sid, NOW, transport)).query)["state"][0]
    s.finish(db, nonce, sid, "fixture-code", NOW, transport)
    return s.choose(db, nonce, sid, "1234567890", NOW), nonce


def test_two_customers_partial_import_reconnect_and_revocation(
    customer_engine: Engine, configured: None
) -> None:
    with Session(customer_engine) as db:
        one, sid = setup(db, "one")
        two, sid2 = setup(db, "two")
        t = FixtureTransport()
        a, nonce = connect(db, one, sid, t)
        b, _ = connect(db, two, sid2, t)
        assert a.account_id != b.account_id and a.integration_id != b.integration_id
        assert s.choose(db, nonce, sid, a.external_account_id, NOW).id == a.id
        assert "synthetic" not in (a.encrypted_grant or "")
        with pytest.raises(HTTPException):
            Vault().open(two, a.id, a.encrypted_grant or "")
        with pytest.raises(HTTPException):
            s.owned(db, two, a.id)
        assert s.tick(db, one, a.id, a.generation, t, NOW) is None
        assert db.scalar(select(func.count()).select_from(DailyMetric)) == 0
        t.fail = True
        with pytest.raises(HTTPException, match="Google read unavailable"):
            s.tick(db, one, a.id, a.generation, t, NOW)
        assert a.cursor == "page-two" and a.staged
        t.fail = False
        jobid = s.tick(db, one, a.id, a.generation, t, NOW)
        job = db.get(JobRun, jobid)
        assert job is not None and job.workspace_id == one and job.connection_id == a.integration_id
        assert db.scalar(select(func.count()).select_from(DailyMetric)) == 2
        assert a.phase == "history" and b.last_sync_at is None
        generation = a.generation
        s.disconnect(db, a)
        assert a.encrypted_grant is None and not a.staged
        with pytest.raises(HTTPException):
            s.tick(db, one, a.id, generation, t, NOW)
        reconnected, _ = connect(db, one, sid, t)
        assert reconnected.id == a.id and reconnected.generation > generation
        assert reconnected.status == "connected"
        with pytest.raises(HTTPException):
            s.tick(db, one, a.id, generation, t, NOW)


def test_state_binding_single_use_expiry_unavailable_and_wrong_account(
    customer_engine: Engine, configured: None
) -> None:
    with Session(customer_engine) as db:
        wid, sid = setup(db, "one")
        _, sid2 = setup(db, "two")
        t = FixtureTransport()
        with pytest.raises(HTTPException) as error:
            s.start(db, wid, sid, NOW, UnavailableTransport())
        assert error.value.status_code == 503
        nonce = parse_qs(urlsplit(s.start(db, wid, sid, NOW, t)).query)["state"][0]
        with pytest.raises(HTTPException):
            s.finish(db, nonce, sid2, "fixture-code", NOW, t)
        assert t.calls == 0
        with pytest.raises(HTTPException):
            s.finish(db, nonce, sid, "fixture-code", NOW + timedelta(minutes=11), t)
        s.finish(db, nonce, sid, "fixture-code", NOW, t)
        with pytest.raises(HTTPException):
            s.finish(db, nonce, sid, "fixture-code", NOW, t)
        assert t.calls == 1
        with pytest.raises(HTTPException):
            s.choose(db, nonce, sid, "9999999999", NOW)
        a = s.choose(db, nonce, sid, "1234567890", NOW)
        t.wrong_account = True
        with pytest.raises(HTTPException, match="collector ownership mismatch"):
            s.tick(db, wid, a.id, a.generation, t, NOW)
        db.rollback()
        assert db.scalar(select(func.count()).select_from(DailyMetric)) == 0
        row = db.scalar(
            select(GoogleAuthorization).where(GoogleAuthorization.selected_connection_id == a.id)
        )
        assert row is not None and row.encrypted_grant is None and not row.accounts


def test_backfill_completion_outbox_and_independent_dispatch(
    customer_engine: Engine, configured: None
) -> None:
    from app.google_connections.dispatcher import deliver_analysis, run_imports
    from app.google_connections.models import GoogleImportCompletion

    t = FixtureTransport()
    with Session(customer_engine) as db:
        wid, sid = setup(db, "one")
        connection, _ = connect(db, wid, sid, t)
        cid = connection.id
    assert run_imports(customer_engine, t, NOW)["completed_windows"] == 0
    assert run_imports(customer_engine, t, NOW)["completed_windows"] == 1
    calls = t.calls

    def failing(engine: Engine, job_id: int) -> None:
        raise RuntimeError("analysis offline")

    assert deliver_analysis(customer_engine, failing) == 0
    assert t.calls == calls
    delivered = []
    assert deliver_analysis(customer_engine, lambda engine, job: delivered.append(job)) == 1
    assert deliver_analysis(customer_engine, lambda engine, job: delivered.append(job)) == 0
    with Session(customer_engine) as db:
        connection = s.owned(db, wid, cid)
        # Continue seven-day windows down to the fixed 90-day floor.
        for _ in range(30):
            if connection.phase == "current":
                break
            s.tick(db, wid, cid, connection.generation, t, NOW)
        assert connection.phase == "current"
        calls = t.calls
        assert s.tick(db, wid, cid, connection.generation, t, NOW) is None
        assert t.calls == calls + 1
        assert connection.phase == "refresh"
        assert db.scalar(select(func.count()).select_from(GoogleImportCompletion)) == 13
        assert len(delivered) == 1


def test_customer_api_session_csrf_roles_and_callback_replay(
    customer_engine: Engine, configured: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from collections.abc import Generator
    from unittest.mock import Mock

    from app.api import customer_google as api
    from app.api.customer import router as auth_router
    from app.customers.access import CSRF_COOKIE
    from app.customers.identity import get_identity_provider
    from app.customers.models import CustomerMembership
    from app.database.session import get_db
    from app.google_connections.contracts import get_transport
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from tests.test_customer_identity import ORIGIN, FakeProvider, login

    clock = Mock()
    clock.now.return_value = NOW
    monkeypatch.setattr(api, "datetime", clock)
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(api.router)

    def database() -> Generator[Session, None, None]:
        with Session(customer_engine) as db:
            yield db

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_identity_provider] = lambda: FakeProvider()
    transport = FixtureTransport()
    app.dependency_overrides[get_transport] = lambda: transport
    owner, stranger = TestClient(app, base_url=ORIGIN), TestClient(app, base_url=ORIGIN)
    uid = login(owner, "owner:1")
    login(stranger, "stranger:1")
    with Session(customer_engine) as db:
        wid, _ = setup(db, "one")
        db.add(CustomerMembership(user_id=uid, workspace_id=wid, role="owner", status="active"))
        db.commit()
    prefix = f"/api/customer/v1/workspaces/{wid}/google"
    headers = {"Origin": ORIGIN, "X-CSRF-Token": owner.cookies[CSRF_COOKIE]}
    assert stranger.get(prefix + "/connections").status_code == 404
    assert owner.post(prefix + "/authorize").status_code == 403
    response = owner.post(prefix + "/authorize", headers=headers)
    assert response.status_code == 200
    nonce = parse_qs(urlsplit(response.json()["authorization_url"]).query)["state"][0]
    body = {"state": nonce, "code": "fixture-code"}
    callback = "/api/customer/v1/google/callback"
    stranger_headers = {"Origin": ORIGIN, "X-CSRF-Token": stranger.cookies[CSRF_COOKIE]}
    assert stranger.post(callback, json=body, headers=stranger_headers).status_code == 404
    assert owner.post(callback, json=body, headers=headers).status_code == 200
    assert owner.post(callback, json=body, headers=headers).status_code == 409
    response = owner.post(
        prefix + "/select",
        json={"state": nonce, "external_account_id": "1234567890"},
        headers=headers,
    )
    assert response.status_code == 200 and response.json()["live_verified"] is False
    cid = response.json()["id"]
    with Session(customer_engine) as db:
        membership = db.get(CustomerMembership, (uid, wid))
        assert membership is not None
        membership.role = "viewer"
        db.commit()
    assert owner.get(prefix + "/connections").status_code == 200
    assert owner.delete(prefix + "/connections/" + cid, headers=headers).status_code == 403


def test_google_wire_manager_context_paging_and_token_request() -> None:
    from types import SimpleNamespace as NS
    from typing import Any

    from app.google_connections.wire import GoogleReadWireAdapter, OAuthCodeExchange

    calls: list[tuple[str, dict[str, str]]] = []

    def post(url: str, fields: dict[str, str]) -> dict[str, Any]:
        calls.append((url, fields))
        return {
            "refresh_token": "synthetic-refresh",
            "scope": "https://www.googleapis.com/auth/adwords",
        }

    class SDK:
        login_customer_id: str | None = None

        def get_service(self, name: str) -> Any:
            assert name in {"CustomerService", "GoogleAdsService"}
            return self

        def list_accessible_customers(self) -> Any:
            return NS(resource_names=["customers/1111111111"])

        def search(self, **kwargs: Any) -> Any:
            if "request" not in kwargs:
                query, account = kwargs["query"], kwargs["customer_id"]
                if "customer_client" in query:
                    return [NS(customer_client=NS(id=2222222222))]
                if account == "2222222222":
                    assert self.login_customer_id == "1111111111"
                return [
                    NS(
                        customer=NS(
                            id=int(account),
                            descriptive_name="Fixture",
                            currency_code="USD",
                            time_zone="UTC",
                            manager=account == "1111111111",
                        )
                    )
                ]
            request = kwargs["request"]
            assert request["customer_id"] == "2222222222" and self.login_customer_id == "1111111111"
            if "segments.date" not in request["query"]:
                row = NS(
                    campaign=NS(
                        id=3,
                        name="Fixture",
                        status=NS(name="PAUSED"),
                        advertising_channel_type=NS(name="SEARCH"),
                    )
                )
            else:
                row = NS(
                    campaign=NS(id=3),
                    segments=NS(date="2026-10-01"),
                    metrics=NS(
                        impressions=100,
                        clicks=10,
                        cost_micros=100,
                        conversions=1.25,
                        conversions_value=3.5,
                    ),
                )
            return NS(pages=[NS(results=[row], next_page_token="")])

    adapter = GoogleReadWireAdapter(
        OAuthCodeExchange(post, "fixture-client", SecretStr("fixture-secret")), lambda token: SDK()
    )
    grant = adapter.exchange(
        "fixture-code", "https://inlet.example/api/customer/v1/google/callback"
    )
    assert len(grant.accounts) == 1 and grant.accounts[0].login_customer_id == "1111111111"
    assert calls[0][0] == "https://oauth2.googleapis.com/token"
    assert calls[0][1]["grant_type"] == "authorization_code"
    first = adapter.page(
        "synthetic-refresh", "2222222222", date(2026, 10, 1), date(2026, 10, 2), None, "1111111111"
    )
    assert len(first.campaigns) == 1 and first.next_cursor == "metrics:"
    last = adapter.page(
        "synthetic-refresh",
        "2222222222",
        date(2026, 10, 1),
        date(2026, 10, 2),
        first.next_cursor,
        "1111111111",
    )
    assert last.next_cursor is None and last.metrics[0].conversions == "1.250000"
    assert last.metrics[0].conversion_value_micros == 3_500_000


def test_late_conversion_refresh_covers_window_and_catches_new_days(
    customer_engine: Engine, configured: None
) -> None:
    from decimal import Decimal

    class Delayed(FixtureTransport):
        conversions = "0"
        windows: list[tuple[date, date]] = []

        def page(
            self,
            refresh_token: str,
            account_id: str,
            start: date,
            end: date,
            cursor: str | None,
            login_customer_id: str | None = None,
        ) -> Page:
            self.windows.append((start, end))
            return Page(
                external_account_id=account_id,
                campaigns=[
                    CampaignRow(external_id="1", name="Fixture", status="ENABLED", channel="SEARCH")
                ],
                metrics=[
                    MetricRow(
                        campaign_external_id="1",
                        day=end,
                        impressions=100,
                        clicks=100,
                        cost_micros=100_000_000,
                        conversions=self.conversions,
                        conversion_value_micros=int(Decimal(self.conversions) * 10_000_000),
                    )
                ],
            )

    with Session(customer_engine) as db:
        transport = Delayed()
        wid, sid = setup(db, "late")
        row, _ = connect(db, wid, sid, transport)
        other_wid, other_sid = setup(db, "other")
        other, _ = connect(db, other_wid, other_sid, transport)
        yesterday = NOW.date() - timedelta(days=1)
        for connection in (row, other):
            connection.phase = "current"
            connection.window_start = yesterday
            connection.window_end = yesterday
        db.commit()
        s.tick(db, wid, row.id, row.generation, transport, NOW)
        s.tick(db, other_wid, other.id, other.generation, transport, NOW)
        other_metric = db.scalar(
            select(DailyMetric).where(
                DailyMetric.campaign_id.in_(
                    select(Campaign.id).where(Campaign.account_id == other.account_id)
                )
            )
        )
        assert other_metric is not None and other_metric.conversions == 0
        transport.conversions = "10"
        transport.windows = []
        s.tick(db, wid, row.id, row.generation, transport, NOW)
        assert row.phase == "refresh"
        current = db.scalar(
            select(DailyMetric).where(
                DailyMetric.metric_date == yesterday, DailyMetric.id != other_metric.id
            )
        )
        assert current is not None and current.conversions == 10
        assert current.conversion_value_micros == 100_000_000
        for _ in range(12):
            s.tick(db, wid, row.id, row.generation, transport, NOW)
        assert row.phase == "current"
        assert len(transport.windows) == 13
        assert transport.windows[-1][0] == yesterday - timedelta(days=89)
        assert all((end - start).days <= 6 for start, end in transport.windows)
        db.refresh(other_metric)
        assert other_metric.conversions == 0
        s.tick(db, wid, row.id, row.generation, transport, NOW + timedelta(days=2))
        assert transport.windows[-1] == (
            yesterday + timedelta(days=1),
            yesterday + timedelta(days=2),
        )

        transport.conversions = "0"
        s.tick(db, wid, row.id, row.generation, transport, NOW + timedelta(days=2))
        corrected = db.scalar(
            select(DailyMetric)
            .join(Campaign, DailyMetric.campaign_id == Campaign.id)
            .where(
                Campaign.account_id == row.account_id,
                DailyMetric.metric_date == yesterday + timedelta(days=2),
            )
        )
        assert corrected is not None and corrected.conversions == 0
        assert corrected.conversion_value_micros == 0
        assert row.phase == "refresh"
        db.refresh(other_metric)
        assert other_metric.conversions == 0
