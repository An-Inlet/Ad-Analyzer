"""Real HTTPS customer sessions + SQL/Vault/OAuth/catalog; no live provider calls."""

import json
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any, cast

import httpx
import pytest
from app.api.customer_reporting import get_selected_customer_runtime, router
from app.campaign_performance.models import CurrentPerformance
from app.campaign_performance.selected_models import EventSelectionRow
from app.customers.access import CSRF_COOKIE, SESSION_COOKIE, digest
from app.customers.models import CustomerMembership, CustomerSession
from app.google_connections import service as google
from app.google_connections.http import GoogleHTTPRead
from app.google_connections.models import GoogleCustomerConnection
from app.google_connections.security import Vault
from app.google_connections.selected_customer import SelectedCustomerRuntime
from app.lifecycle.privacy import bump_workspace_export_revision, workspace_export_revision
from app.main import dashboard_security_headers
from app.settings import settings
from app.workspaces.models import Workspace
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_customer_identity import ORIGIN, FakeProvider, login
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_google_customer_connections import FixtureTransport, connect
from tests.test_google_customer_connections import configured as configured


class CustomerFixture:
    def __init__(
        self, engine: Engine, replicas: tuple[TestClient, TestClient, FakeProvider]
    ) -> None:
        self.engine = engine
        self.alice, self.bob, self.provider = replicas
        self.now = datetime.now(UTC)
        self.hook: Callable[[], None] = lambda: None
        self.calls: list[str] = []
        self.label = "Website purchase"
        for client in (self.alice, self.bob):
            cast(FastAPI, client.app).middleware("http")(dashboard_security_headers)
        self.actor = login(self.alice, "reporting-alice:1")
        login(self.bob, "reporting-bob:1")
        self.sid = digest(self.alice.cookies[SESSION_COOKIE])
        with Session(engine) as db:
            w = Workspace(
                slug="selected-reporting",
                name="Reporting",
                client_name="Reporting",
                status="active",
            )
            db.add(w)
            db.flush()
            self.wid = w.id
            db.add(
                CustomerMembership(
                    workspace_id=self.wid, user_id=self.actor, role="owner", status="active"
                )
            )
            db.commit()
            source, _ = connect(db, self.wid, self.sid, FixtureTransport())
            self.aid, self.source_id, self.day = source.account_id, source.id, source.window_start
        self.oauth_transport = httpx.MockTransport(self.handle)
        self.oauth = GoogleHTTPRead(
            "fixture-client",
            SecretStr("fixture-secret"),
            SecretStr("fixture-developer"),
            "v24",
            transport=self.oauth_transport,
        )
        self.runtime = SelectedCustomerRuntime(
            lambda: Session(engine),
            self.oauth,
            Vault(),
            lambda: httpx.MockTransport(self.handle),
            lambda: self.now,
        )
        for client in (self.alice, self.bob):
            application = cast(FastAPI, client.app)
            application.include_router(router)
            application.dependency_overrides[get_selected_customer_runtime] = lambda: self.runtime
        self.base = f"/api/customer/v1/workspaces/{self.wid}/reporting/google"
        self.refresh()
        self.calls.clear()

    def handle(self, req: httpx.Request) -> httpx.Response:
        self.calls.append(req.url.host or "")
        assert req.method == "POST"  # OAuth and Google read search, never an ad mutation.
        if req.url.host == "oauth2.googleapis.com":
            self.hook()
            return httpx.Response(
                200,
                json={"access_token": "fixture-access", "token_type": "Bearer", "expires_in": 30},
            )
        assert req.url.path.endswith("googleAds:search")
        query = json.loads(req.content)["query"]
        if "FROM customer" in query:
            row: dict[str, Any] = {
                "customer": {
                    "id": "1234567890",
                    "resourceName": "customers/1234567890",
                    "currencyCode": "USD",
                    "timeZone": "UTC",
                }
            }
        elif "FROM conversion_action" in query:
            row = {
                "conversionAction": {
                    "resourceName": "customers/1234567890/conversionActions/123",
                    "ownerCustomer": "customers/1234567890",
                    "name": self.label,
                    "status": "ENABLED",
                    "category": "PURCHASE",
                    "type": "WEBPAGE",
                }
            }
        elif "metrics." not in query:
            row = {
                "campaign": {
                    "id": "1",
                    "name": "Observed campaign",
                    "status": "PAUSED",
                    "advertisingChannelType": "SEARCH",
                }
            }
        else:
            row = {
                "campaign": {"id": "1", "resourceName": "customers/1234567890/campaigns/1"},
                "segments": {"date": self.day.isoformat()},
                "metrics": {
                    "impressions": "1000",
                    "clicks": "100",
                    "costMicros": "100000000",
                    "conversions": "10",
                    "conversionsValue": "0",
                },
            }
        return httpx.Response(200, json={"results": [row]})

    def refresh(self) -> None:
        with Session(self.engine) as db:
            source = db.get(GoogleCustomerConnection, self.source_id)
            assert source
            self.day = source.window_start
            for _ in range(2):
                google.tick(db, self.wid, self.source_id, source.generation, self.oauth, self.now)
            assert db.get(CurrentPerformance, self.aid)

    def post(self, path: str, body: dict[str, Any], client: TestClient | None = None) -> Any:
        c = client or self.alice
        return c.post(
            self.base + path,
            json=body,
            headers={"Origin": ORIGIN, "x-csrf-token": c.cookies[CSRF_COOKIE]},
        )

    def choice(self) -> dict[str, Any]:
        response = self.post("/event-options", {"account_id": self.aid})
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        assert len(response.json()["options"]) == 2
        return cast(dict[str, Any], response.json()["options"][0])

    def confirm(self, option: dict[str, Any], prior: dict[str, Any] | None = None) -> Any:
        return self.post(
            "/event-selection",
            {
                "account_id": self.aid,
                "option_id": option["option_id"],
                "expected_selection_id": prior["selection_id"] if prior else None,
                "expected_selection_digest": prior["selection_digest"] if prior else None,
            },
        )


@pytest.fixture
def customer(
    customer_engine: Engine, configured: None, replicas: tuple[TestClient, TestClient, FakeProvider]
) -> Iterator[CustomerFixture]:
    if customer_engine.dialect.name == "sqlite":
        with customer_engine.connect() as db:
            db.exec_driver_sql("PRAGMA foreign_keys=ON")
            db.commit()
    value = CustomerFixture(customer_engine, replicas)
    try:
        yield value
    finally:
        value.oauth_transport.close()
        value.alice.close()
        value.bob.close()


def test_actual_options_confirmation_retry_and_explicit_refresh(customer: CustomerFixture) -> None:
    f = customer
    choice = f.choice()
    with Session(f.engine) as db:
        assert db.scalar(select(func.count()).select_from(EventSelectionRow)) == 0
    response = f.confirm(choice)
    assert response.status_code == 200, response.text
    receipt = response.json()
    assert receipt["state"] == "selected" and receipt["spending_authorized"] is False
    assert f.confirm(choice, receipt).json() == receipt
    state = f.alice.get(f.base + "/event-selection", params={"account_id": f.aid})
    assert state.status_code == 200 and state.json()["label"] is None
    assert "customers/" not in response.text and "fixture-access" not in response.text
    body = {
        "account_id": f.aid,
        "expected_selection_id": receipt["selection_id"],
        "expected_selection_digest": receipt["selection_digest"],
    }
    invalid = f.post("/event-selection/invalidate", body)
    assert invalid.status_code == 200 and invalid.json()["state"] == "refresh_required"
    with Session(f.engine) as db:
        revision = workspace_export_revision(db, f.wid)
    assert f.post("/event-selection/invalidate", body).json() == invalid.json()
    with Session(f.engine) as db:
        assert workspace_export_revision(db, f.wid) == revision
    fresh_option = f.choice()
    blocked = f.confirm(fresh_option, receipt)
    assert (
        blocked.status_code == 409
        and blocked.json()["detail"] == "reporting_aggregate_refresh_required"
    )
    f.refresh()
    result = f.confirm(f.choice(), receipt)
    assert result.status_code == 200, result.text
    assert result.json()["selection_id"] != receipt["selection_id"]


@pytest.mark.parametrize("change", ["session", "role", "source", "privacy", "clock"])
def test_during_oauth_change_writes_nothing(customer: CustomerFixture, change: str) -> None:
    f = customer
    option = f.choice()

    def mutate() -> None:
        f.hook = lambda: None
        with Session(f.engine) as db:
            if change == "session":
                row = db.get(CustomerSession, f.sid)
                assert row
                row.revoked_at = 1
            elif change == "role":
                member = db.scalar(
                    select(CustomerMembership).where(
                        CustomerMembership.workspace_id == f.wid,
                        CustomerMembership.user_id == f.actor,
                    )
                )
                assert member
                member.role = "viewer"
            elif change == "source":
                source = db.get(GoogleCustomerConnection, f.source_id)
                assert source
                source.generation += 1
            elif change == "privacy":
                bump_workspace_export_revision(db, f.wid)
            else:
                from datetime import timedelta

                f.now += timedelta(hours=9)
            db.commit()

    f.hook = mutate
    result = f.confirm(option)
    assert result.status_code in {401, 403, 409}, result.text
    with Session(f.engine) as db:
        assert db.scalar(select(func.count()).select_from(EventSelectionRow)) == 0


def test_csrf_foreign_stale_rename_and_disabled(customer: CustomerFixture) -> None:
    f = customer
    assert f.alice.post(f.base + "/event-options", json={"account_id": f.aid}).status_code == 403
    foreign = f.post("/event-options", {"account_id": f.aid}, f.bob)
    assert foreign.status_code in {403, 404}
    option = f.choice()
    f.label = "Renamed purchase"
    assert f.confirm(option).status_code == 409
    receipt = f.confirm(f.choice()).json()
    assert f.confirm(f.choice()).status_code == 409
    for value in ("true", "0", "-1", "1.2", "2147483648"):
        assert (
            f.alice.get(f.base + "/event-selection", params={"account_id": value}).status_code
            == 422
        )
    cast(FastAPI, f.alice.app).dependency_overrides[get_selected_customer_runtime] = lambda: None
    assert f.post("/event-options", {"account_id": f.aid}).status_code == 503
    assert f.alice.get(f.base + "/event-selection", params={"account_id": f.aid}).status_code == 200
    invalid = f.post(
        "/event-selection/invalidate",
        {
            "account_id": f.aid,
            "expected_selection_id": receipt["selection_id"],
            "expected_selection_digest": receipt["selection_digest"],
        },
    )
    assert invalid.status_code == 200


def test_paused_read_controls_do_not_block_invalidation(
    customer: CustomerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.automation.catalog import AutomationControlKey
    from app.automation.service import AutomationControlService

    f = customer
    receipt = f.confirm(f.choice()).json()
    with Session(f.engine) as db:
        controls = AutomationControlService(db)
        controls.set_master(AutomationControlKey.ALL_DATA_SYNCS, enabled=False, actor="fixture")
        db.commit()
    blocked = f.post("/event-options", {"account_id": f.aid})
    assert blocked.status_code == 409 and blocked.headers["cache-control"] == "no-store"
    monkeypatch.setattr(settings, "billing_required", True)
    assert f.alice.get(f.base + "/event-selection", params={"account_id": f.aid}).status_code == 200
    assert (
        f.post(
            "/event-selection/invalidate",
            {
                "account_id": f.aid,
                "expected_selection_id": receipt["selection_id"],
                "expected_selection_digest": receipt["selection_digest"],
            },
        ).status_code
        == 200
    )


def test_another_owner_cannot_replay_original_confirmation(customer: CustomerFixture) -> None:
    f = customer
    receipt = f.confirm(f.choice()).json()
    bob_digest = digest(f.bob.cookies[SESSION_COOKIE])
    with Session(f.engine) as db:
        bob_session = db.get(CustomerSession, bob_digest)
        assert bob_session
        db.add(
            CustomerMembership(
                workspace_id=f.wid, user_id=bob_session.user_id, role="owner", status="active"
            )
        )
        db.commit()
    options = f.post("/event-options", {"account_id": f.aid}, f.bob)
    assert options.status_code == 200
    result = f.post(
        "/event-selection",
        {
            "account_id": f.aid,
            "option_id": options.json()["options"][0]["option_id"],
            "expected_selection_id": receipt["selection_id"],
            "expected_selection_digest": receipt["selection_digest"],
        },
        f.bob,
    )
    assert (
        result.status_code == 409
        and result.json()["detail"] == "reporting_selection_invalidation_required"
    )
    with Session(f.engine) as db:
        assert db.scalar(select(func.count()).select_from(EventSelectionRow)) == 1


def test_identity_refresh_occurs_without_active_sql_transaction(
    customer: CustomerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.planning_documents import authority
    from sqlalchemy import event

    f = customer
    active: set[int] = set()
    calls: list[bool] = []

    def begun(connection: Any) -> None:
        active.add(id(connection))

    def ended(connection: Any) -> None:
        active.discard(id(connection))

    original = authority.refresh

    def checked(principal: Any, provider: Any) -> Any:
        assert not active, "identity refresh must precede SQL transaction"
        calls.append(True)
        return original(principal, provider)

    for name, callback in (("begin", begun), ("commit", ended), ("rollback", ended)):
        event.listen(f.engine, name, callback)
    monkeypatch.setattr(authority, "refresh", checked)
    try:
        result = f.confirm(f.choice())
        assert result.status_code == 200, result.text
        assert len(calls) >= 4
    finally:
        for name, callback in (("begin", begun), ("commit", ended), ("rollback", ended)):
            event.remove(f.engine, name, callback)
