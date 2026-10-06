from datetime import timedelta
from typing import Any

import httpx
import pytest
from app.ads.models import DailyMetric
from app.sources import advertising, service
from app.sources.dispatcher import run_tiktok
from app.sources.models import SourceConnection
from app.tiktok.http import (
    TikTokAuthorizationUnavailable,
    TikTokProviderRejected,
    TikTokReadError,
    TikTokTransientError,
)
from fastapi import HTTPException
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_google_customer_connections import setup
from tests.test_tiktok_http_runtime import DAY, META, A, adapter, response
from tests.test_tiktok_sources import TikTokFixture, connect
from tests.test_tiktok_sources import configured as configured


@pytest.mark.parametrize(
    "status,error",
    [
        (401, TikTokAuthorizationUnavailable),
        (403, TikTokAuthorizationUnavailable),
        (429, TikTokTransientError),
        (500, TikTokTransientError),
        (503, TikTokTransientError),
        (400, TikTokReadError),
    ],
)
def test_http_failure_classification(status: int, error: type[Exception]) -> None:
    with pytest.raises(error) as caught:
        adapter(lambda _: httpx.Response(status, text="private-response")).read(
            A, "fixture", DAY, DAY, None
        )
    assert "private-response" not in str(caught.value)


@pytest.mark.parametrize("code", [40001, 40104, 40105, 50000])
def test_unqualified_numeric_codes_are_preserved_without_guessing_meaning(code: int) -> None:
    with pytest.raises(TikTokProviderRejected) as caught:
        adapter(
            lambda _: httpx.Response(200, json={"code": code, "message": "private-response"})
        ).read(A, "fixture", DAY, DAY, None)
    assert caught.value.provider_code == code
    assert "private-response" not in str(caught.value)
    assert not isinstance(caught.value, TikTokTransientError)
    assert not isinstance(caught.value, TikTokAuthorizationUnavailable)


def test_unused_refresh_material_not_retained() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return response(
            {
                "access_token": "fixture",
                "refresh_token": "unqualified-material",
                "advertiser_ids": [A],
            }
            if request.method == "POST"
            else {"list": [META]}
        )

    grant = adapter(handler).exchange("fixture", "https://inlet.example/callback")
    assert grant.refresh_token is None and grant.expires_at is None


@pytest.mark.parametrize("failure", ["auth", "expired"])
def test_terminal_authorization_stops_jobs_and_fences_reconnect(
    customer_engine: Engine,
    configured: None,
    failure: str,
) -> None:
    class Revoked(TikTokFixture):
        def read(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            self.calls += 1
            raise TikTokAuthorizationUnavailable("tiktok_authorization_unavailable")

    good, revoked = TikTokFixture(), Revoked()
    with Session(customer_engine) as db:
        wid, sid = setup(db, "auth-terminal")
        row, _ = connect(db, wid, sid, good)
        cid, generation = row.id, row.generation
        advertising.tick(db, wid, cid, generation, good, NOW)
        assert row.cursor and row.staged
        with pytest.raises(HTTPException):
            advertising.tick(
                db,
                wid,
                cid,
                generation,
                revoked,
                NOW if failure == "auth" else NOW + timedelta(days=2),
            )
        db.rollback()
    with Session(customer_engine) as db:
        row = service.owned(db, wid, "tiktok_ads", cid)
        assert row.status == "reconnect_required" and row.generation == generation + 1
        assert row.encrypted_grant is None and row.cursor is None and row.staged == {}
        assert row.next_attempt_at is None
        assert db.scalar(select(func.count()).select_from(DailyMetric)) == 0
        db.commit()
    assert run_tiktok(customer_engine, revoked, NOW + timedelta(hours=1))["selected"] == 0
    calls = revoked.calls
    with Session(customer_engine) as db:
        fresh, _ = connect(db, wid, sid, good)
        assert fresh.status == "connected"
        new_generation = fresh.generation
        with pytest.raises(HTTPException):
            advertising.tick(db, wid, cid, generation, revoked, NOW)
        db.rollback()
        fresh = service.owned(db, wid, "tiktok_ads", cid)
        assert fresh.generation == new_generation and fresh.status == "connected"
        assert revoked.calls == calls


@pytest.mark.parametrize("transient", [False, True])
def test_current_failure_type_controls_staging_and_fairness(
    customer_engine: Engine,
    configured: None,
    transient: bool,
) -> None:
    class Failed(TikTokFixture):
        def read(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            if transient:
                raise TikTokTransientError("tiktok_read_temporarily_unavailable")
            raise TikTokProviderRejected(40001)

    good, failed = TikTokFixture(), Failed()
    with Session(customer_engine) as db:
        wid, sid = setup(db, "bad-source")
        bad, _ = connect(db, wid, sid, good)
        advertising.tick(db, wid, bad.id, bad.generation, good, NOW)
        cid, staged, cursor = bad.id, bad.staged, bad.cursor
        bad.error_code = "import_rejected" if transient else "read_unavailable"
        bad.next_attempt_at = NOW - timedelta(minutes=2)
        wid2, sid2 = setup(db, "healthy-source")
        healthy, _ = connect(db, wid2, sid2, good)
        healthy.next_attempt_at = NOW - timedelta(minutes=1)
        healthy_id = healthy.id
        db.commit()
    assert run_tiktok(customer_engine, failed, NOW, limit=1)["failed"] == 1
    with Session(customer_engine) as db:
        row = db.get(SourceConnection, cid)
        assert row is not None
        assert row.staged == (staged if transient else {})
        assert row.cursor == (cursor if transient else None)
        assert row.error_code == ("read_unavailable" if transient else "provider_rejected_40001")
        assert row.status == ("connected" if transient else "provider_error")
    assert run_tiktok(customer_engine, good, NOW, limit=1)["failed"] == 0
    with Session(customer_engine) as db:
        row = service.owned(db, wid2, "tiktok_ads", healthy_id)
        assert row.cursor == "metrics"


@pytest.mark.parametrize("kind", ["auth", "provider"])
def test_terminal_failure_preserves_published_data_and_other_outbox(
    customer_engine: Engine,
    configured: None,
    kind: str,
) -> None:
    from app.google_connections.models import GoogleImportCompletion

    class Failed(TikTokFixture):
        def read(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            if kind == "auth":
                raise TikTokAuthorizationUnavailable("tiktok_authorization_unavailable")
            raise TikTokProviderRejected(40001)

    fixture = TikTokFixture()
    with Session(customer_engine) as db:
        wid, sid = setup(db, "published")
        row, _ = connect(db, wid, sid, fixture)
        other_wid, other_sid = setup(db, "other-published")
        other, _ = connect(db, other_wid, other_sid, fixture)
        jobs = []
        for connection in (row, other):
            advertising.tick(
                db, connection.workspace_id, connection.id, connection.generation, fixture, NOW
            )
            job = advertising.tick(
                db, connection.workspace_id, connection.id, connection.generation, fixture, NOW
            )
            assert job is not None
            jobs.append(job)
        count = db.scalar(select(func.count()).select_from(DailyMetric))
        assert count == 6
        with pytest.raises(HTTPException):
            advertising.tick(db, wid, row.id, row.generation, Failed(), NOW)
        db.rollback()
        assert db.scalar(select(func.count()).select_from(DailyMetric)) == count
        assert db.get(GoogleImportCompletion, jobs[0]) is None
        assert db.get(GoogleImportCompletion, jobs[1]) is not None
        assert other.status == "connected"
