"""Offline Meta authorization, partial imports, metric semantics, and isolation contracts."""

import base64
import json
import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from app.ads.enums import AdvertisingPlatform, JobRunStatus
from app.ads.models import AdSet, AdvertisingAccount, DailyMetric, JobRun
from app.automation.models import PlatformAutomationControl, WorkspaceAutomationControl
from app.meta.client import MetaClient, NoRedirect, unpack_page
from app.meta.models import MetaConnection, MetaOAuthState, MetaPendingGrant, MetaStagedMetric
from app.meta.normalize import action_value, metric_values, micros
from app.meta.reporting import connection_report
from app.meta.security import MetaError, Vault, callback_values, configuration_ready
from app.meta.service import ConnectionService, credentials
from app.meta.sync import MetaSyncService
from app.settings import Settings, settings
from app.shopify.logging import OAuthAccessFilter
from app.workspaces.models import Workspace, WorkspaceMembership
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from tests.test_business_intelligence import client as client
from tests.test_business_intelligence import csrf
from tests.test_business_intelligence import db as db

NOW = datetime(2026, 9, 6, 12, tzinfo=UTC)


@pytest.fixture()
def configuration() -> Settings:
    return Settings(
        _env_file=None,
        AD_ANALYZER_META_ENABLED=True,
        meta_client_id="100000000000001",
        meta_client_secret=SecretStr("offline-secret-" * 3),
        meta_token_encryption_key=SecretStr(base64.urlsafe_b64encode(b"m" * 32).decode()),
        meta_redirect_uri="https://example.test/dashboard/meta/callback",
    )


def workspace(db: Session, slug: str = "alpha") -> Workspace:
    row = Workspace(slug=slug, name=slug.title(), client_name=slug.title())
    db.add(row)
    db.commit()
    return row


def metadata(number: str = "101") -> dict[str, Any]:
    return {
        "account_id": number,
        "name": "Example ads",
        "currency": "USD",
        "timezone_name": "UTC",
        "account_status": 1,
    }


def page(*items: dict[str, Any], cursor: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"data": list(items)}
    if cursor:
        result["paging"] = {
            "next": "https://untrusted.test/never-follow?access_token=discard",
            "cursors": {"after": cursor},
        }
    return result


class FakeMeta(MetaClient):
    def __init__(self, configuration: Settings, pages: list[Any] | None = None) -> None:
        super().__init__(configuration)
        self.pages = list(pages or [])
        self.requests: list[tuple[str, str, str | None]] = []
        self.token_calls = 0
        self.account_id = "101"
        self.granted = ["ads_read", "public_profile"]

    def token(
        self, *, code: str | None = None, exchange_token: str | None = None
    ) -> dict[str, Any]:
        self.token_calls += 1
        return {"access_token": "offline-meta-access", "expires_in": 60 * 86400}

    def permissions(self, token: str) -> dict[str, Any]:
        return page(*[{"permission": p, "status": "granted"} for p in self.granted])

    def accounts(self, token: str, cursor: str | None = None) -> dict[str, Any]:
        return page(metadata(self.account_id))

    def account(self, account_id: str, token: str) -> dict[str, Any]:
        return metadata(account_id)

    def page(
        self, account_id: str, token: str, phase: str, cursor: str | None, start: date, end: date
    ) -> dict[str, Any]:
        self.requests.append((account_id, phase, cursor))
        response = self.pages.pop(0)
        if isinstance(response, Exception):
            raise response
        return dict(response)


def authorized(
    db: Session,
    configuration: Settings,
    workspace_id: int,
    fake: FakeMeta,
    actor: str = "owner-session",
) -> ConnectionService:
    service = ConnectionService(db, configuration, fake)
    location = service.begin(workspace_id, actor, NOW)
    nonce = parse_qs(urlsplit(location).query)["state"][0]
    pending = service.pending({"state": nonce}, actor, NOW)
    service.finish(pending, "offline-code", "owner", NOW)
    return service


def connected(
    db: Session,
    configuration: Settings,
    *,
    event: str = "",
    slug: str = "alpha",
    number: str = "101",
) -> MetaConnection:
    ws = workspace(db, slug)
    fake = FakeMeta(configuration)
    fake.account_id = number
    service = authorized(db, configuration, ws.id, fake)
    return service.select_account(ws.id, "owner-session", number, event, "owner", NOW)


def campaign(number: str = "201", account: str = "101") -> dict[str, Any]:
    return {
        "id": number,
        "account_id": account,
        "name": "Client campaign",
        "status": "ACTIVE",
        "objective": "OUTCOME_SALES",
    }


def insight(**changes: Any) -> dict[str, Any]:
    return {
        "account_id": "101",
        "campaign_id": "201",
        "campaign_name": "Client campaign",
        "account_currency": "USD",
        "date_start": "2026-09-05",
        "date_stop": "2026-09-05",
        "impressions": "1000",
        "clicks": "20",
        "spend": "10.000001",
        "actions": [
            {"action_type": "purchase", "value": "3"},
            {"action_type": "offsite_conversion.fb_pixel_purchase", "value": "2"},
            {"action_type": "lead", "value": "7"},
        ],
        "action_values": [
            {"action_type": "purchase", "value": "150.12"},
            {"action_type": "offsite_conversion.fb_pixel_purchase", "value": "100.08"},
        ],
        **changes,
    }


def complete(
    db: Session,
    configuration: Settings,
    row: MetaConnection,
    *,
    now: datetime = NOW,
    metric: dict[str, Any] | None = None,
) -> None:
    fake = FakeMeta(
        configuration,
        [
            page(campaign()),
            page(
                {
                    "id": "301",
                    "account_id": "101",
                    "campaign_id": "201",
                    "name": "Ad set",
                    "status": "ACTIVE",
                }
            ),
            page(metric or insight()),
        ],
    )
    service = MetaSyncService(db, configuration, fake)
    for expected in ("syncing", "syncing", "complete"):
        assert service.page(row.workspace_id, now=now, manual=True)["status"] == expected


def test_oauth_is_bound_single_use_and_encrypted(db: Session, configuration: Settings) -> None:
    ws = workspace(db)
    fake = FakeMeta(configuration)
    service = ConnectionService(db, configuration, fake)
    url = service.begin(ws.id, "owner-session", NOW)
    query = parse_qs(urlsplit(url).query)
    assert query["scope"] == ["ads_read"] and urlsplit(url).hostname == "www.facebook.com"
    nonce = query["state"][0]
    assert nonce != db.scalar(select(MetaOAuthState.digest))
    for actor, now in (("other-session", NOW), ("owner-session", NOW + timedelta(minutes=11))):
        with pytest.raises(MetaError, match="invalid_oauth_state"):
            service.pending({"state": nonce}, actor, now)
    pending = service.pending({"state": nonce}, "owner-session", NOW)
    service.finish(pending, "offline-code", "owner", NOW)
    with pytest.raises(MetaError, match="invalid_oauth_state"):
        service.pending({"state": nonce}, "owner-session", NOW)
    grant = db.scalar(select(MetaPendingGrant))
    assert grant and "offline-meta-access" not in grant.encrypted_credentials
    with pytest.raises(MetaError):
        Vault(configuration).open(
            ws.id + 1, "grant:" + grant.actor_digest, grant.encrypted_credentials
        )
    assert fake.token_calls == 2


def test_selection_requires_authorized_account_and_workspace_uniqueness(
    db: Session, configuration: Settings
) -> None:
    alpha, beta = workspace(db), workspace(db, "beta")
    fake = FakeMeta(configuration)
    first = authorized(db, configuration, alpha.id, fake)
    with pytest.raises(MetaError, match="meta_account_not_authorized"):
        first.select_account(alpha.id, "owner-session", "999", "", "owner", NOW)
    with pytest.raises(MetaError, match="meta_account_not_authorized"):
        first.select_account(alpha.id, "other-session", "101", "", "owner", NOW)
    first.select_account(alpha.id, "owner-session", "101", "", "owner", NOW)
    second = authorized(db, configuration, beta.id, fake)
    with pytest.raises(MetaError, match="meta_account_already_connected"):
        second.select_account(beta.id, "owner-session", "101", "", "owner", NOW)
    db.rollback()
    assert db.scalar(select(AdvertisingAccount.workspace_id)) == alpha.id


def test_write_scope_rejected_and_configuration_disabled(
    db: Session, configuration: Settings
) -> None:
    assert not configuration_ready(Settings(_env_file=None))
    fake = FakeMeta(configuration)
    fake.granted.append("ads_management")
    with pytest.raises(MetaError, match="meta_read_only_scope_required"):
        authorized(db, configuration, workspace(db).id, fake)
    assert db.scalar(select(MetaPendingGrant.id)) is None


def test_platform_event_not_double_counted_and_money_exact() -> None:
    values = metric_values(insight(), "101", "USD", date(2026, 8, 1), NOW.date(), "purchase")
    assert values["conversions"] == Decimal(3)
    assert values["conversion_value_micros"] == 150_120_000
    assert values["cost_micros"] == 10_000_001
    assert micros("0.0000005") == 1
    traffic = metric_values(insight(), "101", "USD", date(2026, 8, 1), NOW.date(), None)
    assert traffic["conversions"] == 0 and traffic["conversion_value_micros"] == 0
    with pytest.raises(MetaError):
        action_value([{"action_type": "purchase", "value": "2"}] * 2, "purchase")
    for value in ("NaN", "Infinity", "-1", "1e30", True):
        with pytest.raises(MetaError):
            micros(value)


def test_partial_pages_publish_only_complete_window_and_preserve_old_on_failure(
    db: Session, configuration: Settings
) -> None:
    row = connected(db, configuration, event="purchase")
    complete(db, configuration, row)
    old = db.scalar(select(DailyMetric))
    assert old and old.conversions == 3
    fake = FakeMeta(
        configuration,
        [
            page(campaign()),
            page(),
            page(insight(spend="20"), cursor="page2"),
            MetaError("meta_throttled", retry_after=300),
            page(),
        ],
    )
    service = MetaSyncService(db, configuration, fake)
    later = NOW + timedelta(hours=1)
    for _ in range(3):
        assert service.page(row.workspace_id, now=later, manual=True)["status"] == "syncing"
    db.expire_all()
    assert db.scalar(select(DailyMetric.cost_micros)) == 10_000_001
    assert db.scalar(select(MetaStagedMetric.cost_micros)) == 20_000_000
    assert service.page(row.workspace_id, now=later, manual=True)["status"] == "meta_throttled"
    assert (
        service.page(row.workspace_id, now=later + timedelta(minutes=1), manual=True)["status"]
        == "retry_later"
    )
    assert (
        service.page(row.workspace_id, now=later + timedelta(minutes=6), manual=True)["status"]
        == "complete"
    )
    db.expire_all()
    assert db.scalar(select(DailyMetric.cost_micros)) == 20_000_000
    assert db.scalar(select(MetaStagedMetric.connection_id)) is None
    assert fake.requests[-1][2] == "page2"


def test_meta_only_import_and_job_scoping_needs_no_other_connections(
    db: Session, configuration: Settings
) -> None:
    row = connected(db, configuration)
    complete(db, configuration, row)
    report = connection_report(db, row.workspace_id, now=NOW)
    assert (
        report["ready"] and not report["conversions_available"] and not report["revenue_available"]
    )
    assert report["covered_from"] == "2026-07-12"
    assert db.scalar(select(AdSet.name)) == "Ad set"
    job = db.scalar(select(JobRun))
    assert job and job.workspace_id == row.workspace_id and job.account_id == row.account_id
    assert job.platform == AdvertisingPlatform.META_ADS and job.status == JobRunStatus.SUCCEEDED
    assert job.job_name == "meta_ads_sync"
    assert not connection_report(db, row.workspace_id + 100, now=NOW)["connected"]
    assert "offline-meta-access" not in json.dumps(report)


def test_connection_failures_and_controls_are_independent(
    db: Session, configuration: Settings
) -> None:
    row = connected(db, configuration)
    fake = FakeMeta(configuration, [MetaError("meta_reconnect_required")])
    service = MetaSyncService(db, configuration, fake)
    db.add(
        WorkspaceAutomationControl(
            workspace_id=row.workspace_id, key="meta_ads_sync", enabled=False, updated_by="test"
        )
    )
    db.commit()
    assert service.page(row.workspace_id, now=NOW, manual=True)["status"] == "disabled"
    assert not fake.requests
    control = db.scalar(select(WorkspaceAutomationControl))
    assert control
    control.enabled = True
    db.add(PlatformAutomationControl(key="all_data_syncs", enabled=False, updated_by="test"))
    db.commit()
    assert service.page(row.workspace_id, now=NOW, manual=True)["status"] == "disabled"
    master = db.scalar(select(PlatformAutomationControl))
    assert master
    master.enabled = True
    db.commit()
    assert (
        service.page(row.workspace_id, now=NOW, manual=True)["status"] == "meta_reconnect_required"
    )
    assert row.status == "reconnect_required"


def test_reconnect_resets_event_coverage_and_disconnect_keeps_history(
    db: Session, configuration: Settings
) -> None:
    row = connected(db, configuration, event="purchase")
    complete(db, configuration, row)
    service = authorized(db, configuration, row.workspace_id, FakeMeta(configuration))
    service.select_account(row.workspace_id, "owner-session", "101", "lead", "owner", NOW)
    assert row.last_sync_at is None and row.covered_from is None
    assert db.scalar(select(DailyMetric.conversions)) == 0
    assert not connection_report(db, row.workspace_id, now=NOW)["conversions_available"]
    service.disconnect(row.workspace_id, "owner")
    assert db.scalar(select(MetaConnection.id)) is None
    assert db.scalar(select(DailyMetric.id)) is not None
    assert db.scalar(select(MetaPendingGrant.id)) is None


def test_malformed_foreign_metric_page_rolls_back(db: Session, configuration: Settings) -> None:
    row = connected(db, configuration)
    fake = FakeMeta(configuration, [page(campaign()), page(), page(insight(account_id="999"))])
    service = MetaSyncService(db, configuration, fake)
    for _ in range(2):
        service.page(row.workspace_id, now=NOW, manual=True)
    result = service.page(row.workspace_id, now=NOW, manual=True)
    assert result["status"] == "meta_account_mismatch"
    assert db.scalar(select(DailyMetric.id)) is None
    assert db.scalar(select(MetaStagedMetric.connection_id)) is None


def test_inventory_change_restarts_scan_without_losing_old_snapshot(
    db: Session, configuration: Settings
) -> None:
    row = connected(db, configuration)
    complete(db, configuration, row)
    fake = FakeMeta(
        configuration,
        [
            page(campaign()),
            page({"id": "302", "account_id": "101", "campaign_id": "202", "name": "New set"}),
            page(campaign(), campaign("202")),
        ],
    )
    service = MetaSyncService(db, configuration, fake)
    assert service.page(row.workspace_id, now=NOW, manual=True)["status"] == "syncing"
    assert (
        service.page(row.workspace_id, now=NOW, manual=True)["status"]
        == "meta_campaign_inventory_changed"
    )
    assert row.phase == "campaigns" and row.cursor is None
    assert db.scalar(select(DailyMetric.id)) is not None
    assert (
        service.page(row.workspace_id, now=NOW + timedelta(minutes=2), manual=True)["status"]
        == "syncing"
    )
    assert fake.requests[-1][1] == "campaigns"


def test_coverage_never_certifies_unimported_gap_or_stale_window(
    db: Session, configuration: Settings
) -> None:
    row = connected(db, configuration, event="purchase")
    complete(db, configuration, row)
    old_end = row.covered_through
    # A later completion may be recent while the imported reporting window is old.
    row.last_sync_at = NOW + timedelta(days=100)
    db.commit()
    assert not connection_report(db, row.workspace_id, now=NOW + timedelta(days=100))["ready"]
    bundle = credentials({"access_token": "offline-meta-access", "expires_in": 86400 * 180}, NOW)
    row.encrypted_credentials = Vault(configuration).seal(row.workspace_id, "101", bundle)
    db.commit()
    later = NOW + timedelta(days=100)
    day = (later.date() - timedelta(days=1)).isoformat()
    complete(db, configuration, row, now=later, metric=insight(date_start=day, date_stop=day))
    assert old_end and row.covered_from and row.covered_from > old_end
    assert connection_report(db, row.workspace_id, now=later)["ready"]


def test_transport_uses_fixed_reads_and_cursor_not_next_url(
    configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    from io import BytesIO

    seen = []

    class Response(BytesIO):
        pass

    class Opener:
        def open(self, request: Any, timeout: int) -> Any:
            seen.append(request)
            assert timeout == 12
            assert request.method == "GET"
            assert urlsplit(request.full_url).hostname == "graph.facebook.com"
            assert "offline-token" not in request.full_url
            return Response(json.dumps(page(insight(), cursor="next_cursor")).encode())

    monkeypatch.setattr("app.meta.client.build_opener", lambda handler: Opener())
    data = MetaClient(configuration).page(
        "101", "offline-token", "insights", None, NOW.date(), NOW.date()
    )
    assert unpack_page(data)[1] == "next_cursor"
    assert len(seen) == 1
    with pytest.raises(MetaError):
        MetaClient(configuration)._request("https://foreign.test", {})
    with pytest.raises(MetaError):
        unpack_page(data, "next_cursor")
    NoRedirect().redirect_request(None, None, 302, "", {}, "https://foreign.test")


def test_transport_sanitizes_graph_400_expiry(
    configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    from email.message import Message
    from io import BytesIO
    from urllib.error import HTTPError

    class Opener:
        def open(self, request: Any, timeout: int) -> Any:
            raise HTTPError(
                request.full_url,
                400,
                "secret upstream body",
                Message(),
                BytesIO(b'{"error":{"code":190,"message":"secret upstream body"}}'),
            )

    monkeypatch.setattr("app.meta.client.build_opener", lambda handler: Opener())
    with pytest.raises(MetaError) as error:
        MetaClient(configuration).accounts("offline-token")
    assert str(error.value) == "meta_reconnect_required"


def test_dashboard_flow_csrf_actor_binding_and_permissions(
    client: TestClient, db: Session, configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    import re
    from html import unescape

    ws = workspace(db)
    workspace(db, "beta")
    for key in type(configuration).model_fields:
        if key.startswith("meta_"):
            monkeypatch.setattr(settings, key, getattr(configuration, key))
    fake = FakeMeta(configuration)
    monkeypatch.setattr("app.meta.service.MetaClient", lambda configuration: fake)
    root = "/dashboard/workspaces/alpha/meta"
    html = client.get(root)
    assert html.status_code == 200 and "other connection is optional" in html.text
    token = csrf(html.text)
    assert client.post(root + "/connect").status_code == 403
    handoff = client.post(root + "/connect", data={"csrf_token": token})
    match = re.search(r'id="meta-authorization"[^>]*href="([^"]+)"', handoff.text)
    assert match and "form-action 'self'" in handoff.headers["content-security-policy"]
    url = unescape(match.group(1))
    nonce = parse_qs(urlsplit(url).query)["state"][0]
    path = f"/dashboard/meta/callback?code=offline-code&state={nonce}"
    assert client.get(path, follow_redirects=False).status_code == 303
    assert client.get(path, follow_redirects=False).status_code == 422
    assert "Example ads" in client.get(root).text
    assert (
        client.post(
            "/dashboard/workspaces/beta/meta/select",
            data={"csrf_token": token, "account_id": "101"},
        ).status_code
        == 422
    )
    response = client.post(
        root + "/select", data={"csrf_token": token, "account_id": "101"}, follow_redirects=False
    )
    assert response.status_code == 303
    assert client.get("/api/v1/workspaces/alpha/meta").json()["connected"]
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "iap_audience", "test-audience")
    monkeypatch.setattr(
        "app.dashboard.auth.verify_iap_jwt",
        lambda assertion, audience: {"email": "viewer@example.test"},
    )
    client.headers["x-goog-iap-jwt-assertion"] = "offline-assertion"
    db.add(
        WorkspaceMembership(
            workspace_id=ws.id, principal="viewer@example.test", role="viewer", status="active"
        )
    )
    db.commit()
    assert client.get(root).status_code == 200
    assert client.get("/dashboard/workspaces/beta/meta").status_code == 404
    assert client.post(root + "/disconnect", data={"csrf_token": token}).status_code == 403


def test_callback_input_and_access_logs_never_expose_codes() -> None:
    with pytest.raises(MetaError):
        callback_values([("state", "x" * 43), ("code", "one"), ("code", "two")])
    record = logging.LogRecord(
        "uvicorn.access", 20, "", 1, "GET /dashboard/meta/callback?code=offline-sensitive", (), None
    )
    assert not OAuthAccessFilter().filter(record)


def test_meta_migration_matches_models_and_account_workspace_constraint(db: Session) -> None:
    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine, inspect

    path = Path("migrations/versions/20260906_0019_meta_connections.py")
    spec = importlib.util.spec_from_file_location("meta_migration", path)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        assert {"meta_connections", "meta_pending_grants", "meta_staged_metrics"} <= set(
            inspect(connection).get_table_names()
        )
        assert any(
            key["constrained_columns"] == ["account_id", "workspace_id"]
            for key in inspect(connection).get_foreign_keys("meta_connections")
        )
    engine.dispose()


def test_cross_site_oauth_return_uses_flow_cookie_and_verified_identity(
    client: TestClient, db: Session, configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    import re
    from html import unescape

    from app.dashboard.auth import COOKIE_NAME
    from app.dashboard.meta import FLOW_COOKIE

    ws = workspace(db)
    for key in type(configuration).model_fields:
        if key.startswith("meta_"):
            monkeypatch.setattr(settings, key, getattr(configuration, key))
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "iap_audience", "test-audience")
    identity = {"email": "owner@example.test"}
    monkeypatch.setattr("app.dashboard.auth.verify_iap_jwt", lambda assertion, audience: identity)
    client.headers["x-goog-iap-jwt-assertion"] = "offline-assertion"
    db.add(
        WorkspaceMembership(
            workspace_id=ws.id, principal="owner@example.test", role="owner", status="active"
        )
    )
    db.commit()
    fake = FakeMeta(configuration)
    monkeypatch.setattr("app.meta.service.MetaClient", lambda configuration: fake)
    root = "/dashboard/workspaces/alpha/meta"
    html = client.get(root)
    assert html.status_code == 200
    handoff = client.post(root + "/connect", data={"csrf_token": csrf(html.text)})
    cookie_headers = handoff.headers.get_list("set-cookie")
    assert any(
        FLOW_COOKIE in value
        and "SameSite=lax" in value
        and "HttpOnly" in value
        and "Secure" in value
        and "Max-Age=600" in value
        for value in cookie_headers
    )
    assert client.cookies.get(COOKIE_NAME)
    flow = client.cookies.get(FLOW_COOKIE)
    assert flow
    match = re.search(r'id="meta-authorization"[^>]*href="([^"]+)"', handoff.text)
    assert match
    nonce = parse_qs(urlsplit(unescape(match.group(1))).query)["state"][0]
    path = f"/dashboard/meta/callback?code=offline-code&state={nonce}"
    # Browsers omit the Strict dashboard session on Meta's cross-site return.
    # The dedicated Lax flow cookie must work, while absent/wrong flows fail.
    assert client.get(path, headers={"Cookie": ""}, follow_redirects=False).status_code == 422
    assert (
        client.get(
            path, headers={"Cookie": FLOW_COOKIE + "=" + "z" * 43}, follow_redirects=False
        ).status_code
        == 422
    )
    identity["email"] = "other@example.test"
    assert (
        client.get(
            path, headers={"Cookie": FLOW_COOKIE + "=" + flow}, follow_redirects=False
        ).status_code
        == 422
    )
    assert fake.token_calls == 0
    identity["email"] = "owner@example.test"
    assert (
        client.get(
            path, headers={"Cookie": FLOW_COOKIE + "=" + flow}, follow_redirects=False
        ).status_code
        == 303
    )
    assert fake.token_calls == 2
    assert (
        client.get(
            path, headers={"Cookie": FLOW_COOKIE + "=" + flow}, follow_redirects=False
        ).status_code
        == 422
    )
    selection = client.get(root)
    assert "Example ads" in selection.text
    response = client.post(
        root + "/select",
        data={"csrf_token": csrf(selection.text), "account_id": "101"},
        follow_redirects=False,
    )
    assert response.status_code == 303 and client.cookies.get(FLOW_COOKIE) is None
    # Malformed nonsecret cookie values must never break the connection screen.
    assert client.get(root, headers={"Cookie": FLOW_COOKIE + "=malformed"}).status_code == 200
