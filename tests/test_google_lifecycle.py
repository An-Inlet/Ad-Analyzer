from datetime import timedelta
from typing import Any
from urllib.parse import parse_qs

import httpx
import pytest
from app.ads.models import DailyMetric
from app.google_connections import service as s
from app.google_connections.contracts import GoogleAuthorizationUnavailable, GoogleGrantLifecycle
from app.google_connections.dispatcher import run_imports
from app.google_connections.http import GoogleReadError
from fastapi import HTTPException
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_google_customer_connections import (
    FixtureTransport,
    connect,
    setup,
)
from tests.test_google_customer_connections import (
    configured as configured,
)
from tests.test_google_http_runtime import DAY, TOKEN, A, runtime


@pytest.mark.parametrize(
    "status,body,expired",
    [
        (400, {"error": "invalid_grant", "error_description": "private-response"}, True),
        (400, {"error": "invalid_client"}, False),
        (429, {"error": "temporary"}, False),
        (503, {"error": "temporary"}, False),
    ],
)
def test_refresh_failure_classification(status: int, body: dict[str, Any], expired: bool) -> None:
    error = GoogleAuthorizationUnavailable if expired else GoogleReadError
    with pytest.raises(error) as caught:
        runtime(lambda _: httpx.Response(status, json=body)).page(
            "fixture-refresh", A, DAY, DAY, None
        )
    assert "private-response" not in str(caught.value)


def test_ads_unauthenticated_is_current_grant_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return (
            httpx.Response(200, json=TOKEN)
            if request.url.host == "oauth2.googleapis.com"
            else httpx.Response(401, json={"error": "private-response"})
        )

    with pytest.raises(GoogleAuthorizationUnavailable):
        runtime(handler).page("fixture-refresh", A, DAY, DAY, None)


@pytest.mark.parametrize("status", [200, 400, 302, 429, 500])
def test_remote_revoke_fixed_endpoint_body_and_result(status: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://oauth2.googleapis.com/revoke"
        assert request.method == "POST"
        assert parse_qs(request.content.decode()) == {"token": ["fixture-refresh"]}
        assert request.headers["content-type"] == "application/x-www-form-urlencoded"
        assert request.extensions["timeout"]["connect"] == 5
        return httpx.Response(status, content=b"")

    adapter = runtime(handler)
    assert isinstance(adapter, GoogleGrantLifecycle)
    if status == 200:
        adapter.revoke("fixture-refresh")
    else:
        with pytest.raises(GoogleReadError, match="revocation_unconfirmed"):
            adapter.revoke("fixture-refresh")


def test_revocation_timeout_is_unconfirmed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("private-response", request=request)

    with pytest.raises(GoogleReadError, match="revocation_unconfirmed"):
        runtime(handler).revoke("fixture-refresh")


def test_invalid_grant_stops_jobs_and_reconnect_fences_old_work(
    customer_engine: Engine,
    configured: None,
) -> None:
    class Revoked(FixtureTransport):
        def page(self, *args: Any, **kwargs: Any) -> Any:
            self.calls += 1
            raise GoogleAuthorizationUnavailable("google_customer_authorization_unavailable")

    normal, revoked = FixtureTransport(), Revoked()
    with Session(customer_engine) as db:
        wid, sid = setup(db, "revoked")
        row, _ = connect(db, wid, sid, normal)
        cid, old_generation = row.id, row.generation
        assert s.tick(db, wid, cid, old_generation, normal, NOW) is None
        assert row.cursor is not None and row.staged
        with pytest.raises(HTTPException, match="fresh consent"):
            s.tick(db, wid, cid, old_generation, revoked, NOW)
        db.rollback()  # terminal transition already persisted, like failed API/job cleanup
    with Session(customer_engine) as db:
        row = s.owned(db, wid, cid)
        assert row.status == "reconnect_required"
        assert row.encrypted_grant is None and row.cursor is None and row.staged == {}
        assert row.next_attempt_at is None and row.generation == old_generation + 1
        assert db.scalar(select(func.count()).select_from(DailyMetric)) == 0
        db.commit()
    assert run_imports(customer_engine, revoked, NOW + timedelta(hours=1))["selected"] == 0
    calls = revoked.calls
    with Session(customer_engine) as db:
        new, _ = connect(db, wid, sid, normal)
        assert new.generation > old_generation and new.status == "connected"
        generation, encrypted = new.generation, new.encrypted_grant
        with pytest.raises(HTTPException, match="replaced"):
            s.tick(db, wid, cid, old_generation, revoked, NOW)
        db.rollback()
        fresh = s.owned(db, wid, cid)
        assert fresh.generation == generation and fresh.encrypted_grant == encrypted
        assert fresh.status == "connected" and revoked.calls == calls


def test_disconnect_is_local_even_with_revoker_and_stale_session(
    customer_engine: Engine,
    configured: None,
) -> None:
    class CannotRevoke(FixtureTransport):
        def revoke(self, token: str) -> None:
            pytest.fail("Per-account disconnect/reconnect must not revoke broader Google grant")

    transport = CannotRevoke()
    with Session(customer_engine) as first:
        wid, sid = setup(first, "disconnect")
        row, _ = connect(first, wid, sid, transport)
        cid, generation = row.id, row.generation
        first.commit()
        with Session(customer_engine) as other:
            newer, _ = connect(other, wid, sid, transport)
            generation = newer.generation
        s.disconnect(first, row)
        assert row.generation == generation + 1
        first.rollback()
    with Session(customer_engine) as db:
        fresh = s.owned(db, wid, cid)
        assert fresh.status == "disconnected" and fresh.encrypted_grant is None
        assert fresh.cursor is None and fresh.staged == {} and fresh.next_attempt_at is None


def test_cloud_project_oauth_without_legacy_developer_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.google_connections.contracts import UnavailableTransport, get_transport
    from app.google_connections.http import GoogleHTTPRead
    from app.settings import settings
    from pydantic import SecretStr

    monkeypatch.setattr(settings, "google_customer_runtime_mode", "google_read")
    monkeypatch.setattr(settings, "google_customer_client_id", "fixture-client")
    monkeypatch.setattr(settings, "google_customer_client_secret", SecretStr("fixture-secret"))
    monkeypatch.setattr(settings, "google_customer_developer_token", None)
    monkeypatch.setattr(settings, "google_customer_api_version", "v25")
    assert isinstance(get_transport(), GoogleHTTPRead)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth2.googleapis.com":
            assert parse_qs(request.content.decode())["client_id"] == ["fixture-client"]
            return httpx.Response(200, json=TOKEN)
        assert request.headers["Authorization"] == "Bearer fixture-access"
        assert "developer-token" not in request.headers
        return httpx.Response(200, json={"results": []})

    reader = GoogleHTTPRead(
        "fixture-client",
        SecretStr("fixture-secret"),
        None,
        "v25",
        transport=httpx.MockTransport(handler),
    )
    assert reader.page("fixture-refresh", A, DAY, DAY, None).next_cursor == "metrics:"
    monkeypatch.setattr(settings, "google_customer_client_secret", None)
    assert isinstance(get_transport(), UnavailableTransport)


def test_project_permission_denial_without_legacy_token_fails_closed() -> None:
    from app.google_connections.http import GoogleHTTPRead
    from pydantic import SecretStr

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json=TOKEN)
        return httpx.Response(
            403, json={"error": {"message": "private-response", "status": "PERMISSION_DENIED"}}
        )

    reader = GoogleHTTPRead(
        "fixture-client",
        SecretStr("fixture-secret"),
        None,
        "v25",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(GoogleReadError):
        reader.page("fixture-refresh", A, DAY, DAY, None)


def test_changed_inventory_resets_failed_window_and_allows_healthy_customer(
    customer_engine: Engine,
    configured: None,
) -> None:
    from datetime import date

    from app.google_connections.contracts import CampaignRow, MetricRow, Page
    from app.google_connections.models import GoogleCustomerConnection
    from app.shopify.security import utc

    class Changed(FixtureTransport):
        bad_token = ""

        def page(
            self,
            refresh_token: str,
            account_id: str,
            start: date,
            end: date,
            cursor: str | None,
            login_customer_id: str | None = None,
        ) -> Page:
            if refresh_token == self.bad_token and cursor:
                return Page(
                    external_account_id=account_id,
                    campaigns=[],
                    metrics=[
                        MetricRow(
                            campaign_external_id="2",
                            day=end,
                            impressions=100,
                            clicks=100,
                            cost_micros=100_000_000,
                            conversions="10",
                            conversion_value_micros=100,
                        )
                    ],
                )
            return Page(
                external_account_id=account_id,
                metrics=[],
                campaigns=[
                    CampaignRow(external_id="1", name="Fixture", status="ENABLED", channel="SEARCH")
                ],
            )

    from app.google_connections.security import Vault

    transport = Changed()
    with Session(customer_engine) as db:
        wid, sid = setup(db, "bad-inventory")
        bad, _ = connect(db, wid, sid, transport)
        good_wid, good_sid = setup(db, "healthy")
        good, _ = connect(db, good_wid, good_sid, transport)
        initial = FixtureTransport()
        s.tick(db, wid, bad.id, bad.generation, initial, NOW)
        s.tick(db, wid, bad.id, bad.generation, initial, NOW)
        published_count = db.scalar(select(func.count()).select_from(DailyMetric))
        assert published_count == 2
        # Give the bad account a distinct grant; provider metrics can change after inventory.
        bad.encrypted_grant = Vault().seal(wid, bad.id, "bad-fixture")
        transport.bad_token = "bad-fixture"
        bad.cursor = "metrics:"
        bad.staged = {
            "pages": [
                Page(
                    external_account_id=bad.external_account_id,
                    metrics=[],
                    campaigns=[
                        CampaignRow(
                            external_id="1", name="Fixture", status="ENABLED", channel="SEARCH"
                        )
                    ],
                ).model_dump(mode="json")
            ],
            "cursors": ["metrics:"],
        }
        bad.error_code = "read_unavailable"  # Previous attempt must not decide this failure class.
        bad.next_attempt_at = NOW - timedelta(minutes=2)
        good.next_attempt_at = NOW - timedelta(minutes=1)
        bad_id, good_id = bad.id, good.id
        last_sync = bad.last_sync_at
        db.commit()
    assert run_imports(customer_engine, transport, NOW, limit=1)["failed"] == 1
    with Session(customer_engine) as db:
        loaded_bad = db.get(GoogleCustomerConnection, bad_id)
        assert loaded_bad is not None
        bad = loaded_bad
        assert bad is not None and bad.cursor is None and bad.staged == {}
        assert bad.error_code == "import_rejected"
        assert bad.last_sync_at and last_sync and utc(bad.last_sync_at) == utc(last_sync)
        assert db.scalar(select(func.count()).select_from(DailyMetric)) == published_count
        assert bad.next_attempt_at and utc(bad.next_attempt_at) == NOW + timedelta(minutes=5)
    assert run_imports(customer_engine, transport, NOW, limit=1)["completed_windows"] == 1
    with Session(customer_engine) as db:
        loaded_good = db.get(GoogleCustomerConnection, good_id)
        assert loaded_good is not None
        good = loaded_good
        assert good is not None and good.last_sync_at is not None


def test_transient_dispatch_failure_preserves_pages_and_retry_backoff(
    customer_engine: Engine,
    configured: None,
) -> None:
    from app.google_connections.models import GoogleCustomerConnection
    from app.shopify.security import utc

    transport = FixtureTransport()
    with Session(customer_engine) as db:
        wid, sid = setup(db, "transient")
        row, _ = connect(db, wid, sid, transport)
        s.tick(db, wid, row.id, row.generation, transport, NOW)
        cid, staged, cursor = row.id, row.staged, row.cursor
    transport.fail = True
    assert run_imports(customer_engine, transport, NOW, limit=1)["failed"] == 1
    with Session(customer_engine) as db:
        loaded = db.get(GoogleCustomerConnection, cid)
        assert loaded is not None
        row = loaded
        assert row is not None and row.cursor == cursor and row.staged == staged
        assert row.error_code == "read_unavailable"
        assert row.next_attempt_at and utc(row.next_attempt_at) == NOW + timedelta(minutes=5)


def test_dispatch_failure_does_not_poison_new_generation(
    customer_engine: Engine,
    configured: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.google_connections import dispatcher
    from app.google_connections.models import GoogleCustomerConnection

    transport = FixtureTransport()
    with Session(customer_engine) as db:
        wid, sid = setup(db, "changed-generation")
        row, _ = connect(db, wid, sid, transport)
        cid, old_generation = row.id, row.generation

    def replaced_then_failed(db: Session, *args: Any, **kwargs: Any) -> None:
        fresh, _ = connect(db, wid, sid, transport)
        assert fresh.generation > old_generation
        raise HTTPException(409, "old queued task failed")

    monkeypatch.setattr(dispatcher, "tick", replaced_then_failed)
    assert run_imports(customer_engine, transport, NOW, limit=1)["failed"] == 1
    with Session(customer_engine) as db:
        fresh_row = db.get(GoogleCustomerConnection, cid)
        assert fresh_row is not None
        row = fresh_row
        assert row is not None and row.generation == old_generation + 1
        assert row.status == "connected" and row.error_code is None
        assert row.next_attempt_at is None and row.encrypted_grant is not None


@pytest.mark.parametrize("change", ["disconnect", "reconnect"])
def test_pending_analysis_discard_is_scoped_to_replaced_connection(
    customer_engine: Engine,
    configured: None,
    change: str,
) -> None:
    from app.google_connections.models import GoogleImportCompletion

    transport = FixtureTransport()
    with Session(customer_engine) as db:
        wid, sid = setup(db, "outbox-old")
        one, _ = connect(db, wid, sid, transport)
        wid2, sid2 = setup(db, "outbox-other")
        two, _ = connect(db, wid2, sid2, transport)
        jobs = []
        for connection in (one, two):
            s.tick(
                db, connection.workspace_id, connection.id, connection.generation, transport, NOW
            )
            job = s.tick(
                db, connection.workspace_id, connection.id, connection.generation, transport, NOW
            )
            assert job is not None
            jobs.append(job)
        assert db.get(GoogleImportCompletion, jobs[0]) is not None
        if change == "disconnect":
            s.disconnect(db, one)
        else:
            connect(db, wid, sid, transport)
        db.expire_all()
        assert db.get(GoogleImportCompletion, jobs[0]) is None
        assert db.get(GoogleImportCompletion, jobs[1]) is not None
