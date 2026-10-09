"""Customer authorization must survive a slow upload and a blocked mutation."""

import asyncio
import time
from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import httpx
import pytest
from app.api.customer import router as customer_router
from app.api.customer_campaign_review import router
from app.campaign_review.models import MediaObject
from app.campaign_review.storage import LocalMediaStore, get_media_store
from app.customers.access import CSRF_COOKIE, SESSION_COOKIE, digest
from app.customers.identity import get_identity_provider
from app.customers.models import CustomerMembership, CustomerSession
from app.database.session import get_db
from app.settings import Settings, settings
from app.workspaces.models import Workspace
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.campaign_review_retained_fixture import (
    RetainedCampaignReviewIds,
    current_binding,
)
from tests.campaign_review_retained_fixture import (
    retained_campaign_binding as retained_campaign_binding,
)
from tests.test_campaign_review import png
from tests.test_customer_identity import ORIGIN, FakeProvider, login
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize("revocation", ["session", "membership", "provider", "timeout", "expiry"])
def test_upload_rechecks_authority_after_actual_asgi_body_wait(
    customer_engine: Engine, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, revocation: str
) -> None:
    monkeypatch.setattr(settings, "customer_app_origin", ORIGIN)
    app = FastAPI()
    app.include_router(customer_router)
    app.include_router(router)
    provider = FakeProvider()
    if revocation == "timeout":
        from app.api import customer_campaign_review as api

        monkeypatch.setattr(api, "UPLOAD_TIMEOUT_SECONDS", 0.05)

    def database() -> Generator[Session, None, None]:
        with Session(customer_engine) as db:
            yield db

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_identity_provider] = lambda: provider
    app.dependency_overrides[get_media_store] = lambda: LocalMediaStore(tmp_path)
    client = TestClient(app, base_url=ORIGIN)
    uid = login(client, "owner:1")
    with Session(customer_engine) as db:
        workspace = Workspace(
            slug="upload-race", name="Upload", client_name="Synthetic", status="active"
        )
        db.add(workspace)
        db.flush()
        wid = workspace.id
        db.add(CustomerMembership(user_id=uid, workspace_id=wid, role="owner", status="active"))
        db.commit()

    async def exercise() -> httpx.Response:
        paused, release = asyncio.Event(), asyncio.Event()

        async def body() -> AsyncGenerator[bytes, None]:
            data = png()
            yield data[:10]
            paused.set()
            await release.wait()
            yield data[10:]

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url=ORIGIN) as http:
            request = asyncio.create_task(
                http.post(
                    f"/api/customer/v1/workspaces/{wid}/media",
                    headers={
                        "Origin": ORIGIN,
                        "X-CSRF-Token": client.cookies[CSRF_COOKIE],
                        "Cookie": "; ".join(f"{k}={v}" for k, v in client.cookies.items()),
                    },
                    content=body(),
                )
            )
            await asyncio.wait_for(paused.wait(), 5)
            if revocation == "timeout":
                return await asyncio.wait_for(request, 2)
            with Session(customer_engine) as db:
                if revocation == "session":
                    row = db.get(CustomerSession, digest(client.cookies[SESSION_COOKIE]))
                    assert row is not None
                    row.revoked_at = int(time.time())
                elif revocation == "membership":
                    membership = db.get(CustomerMembership, (uid, wid))
                    assert membership is not None
                    db.delete(membership)
                elif revocation == "expiry":
                    from app.customers import access

                    expires = int(time.time()) + access.TTL_SECONDS + 1

                    def expire(_subject: str, _authenticated_at: int) -> None:
                        monkeypatch.setattr(time, "time", lambda: expires)

                    monkeypatch.setattr(provider, "check_active", expire)
                else:
                    provider.disabled.add("owner")
                db.commit()
            release.set()
            return await asyncio.wait_for(request, 5)

    response = asyncio.run(exercise())
    assert response.status_code in ({408} if revocation == "timeout" else {401, 403, 404})
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(MediaObject)) == 0
    assert not list(tmp_path.rglob("*"))


@pytest.mark.planning_boundary
@pytest.mark.parametrize("revocation", ["session", "membership"])
def test_approval_rechecks_after_waiting_for_workspace_lock(
    customer_engine: Engine,
    configuration: Settings,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    revocation: str,
    retained_campaign_binding: tuple[Engine, RetainedCampaignReviewIds],
) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from datetime import datetime
    from threading import Event

    from app.api import customer_campaign_review as api
    from app.campaign_review import service
    from app.campaign_review.models import CampaignRevision
    from sqlalchemy import event

    from tests.test_campaign_review import definition
    from tests.test_commerce_measurement import NOW

    if customer_engine.dialect.name != "postgresql":
        pytest.skip("authorization lock interleaving requires PostgreSQL")
    customer_engine, source_ids = retained_campaign_binding
    monkeypatch.setattr(settings, "customer_app_origin", ORIGIN)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[no-untyped-def]
            return NOW

    monkeypatch.setattr(api, "datetime", Clock)
    app = FastAPI()
    app.include_router(customer_router)
    app.include_router(router)
    provider, store = FakeProvider(), LocalMediaStore(tmp_path)

    def database() -> Generator[Session, None, None]:
        with Session(customer_engine) as db:
            yield db

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_identity_provider] = lambda: provider
    app.dependency_overrides[get_media_store] = lambda: store
    client = TestClient(app, base_url=ORIGIN)
    uid = login(client, "owner:1")
    with Session(customer_engine) as db:
        mandate, scope = current_binding(db, source_ids)
        wid = mandate.workspace_id
        revision = service.revise(db, wid, definition(db, mandate, scope), uid, store, NOW)
        draft_id, review_digest = revision.draft_id, revision.digest
        db.add(CustomerMembership(user_id=uid, workspace_id=wid, role="owner", status="active"))
        db.commit()
    attempted = Event()

    def before(_conn, _cursor, statement, _params, _context, _many):  # type: ignore[no-untyped-def]
        if "FROM workspaces" in statement and (
            "FOR UPDATE" in statement or "FOR NO KEY UPDATE" in statement
        ):
            attempted.set()

    with Session(customer_engine) as blocker:
        blocker.scalar(select(Workspace).where(Workspace.id == wid).with_for_update())
        event.listen(customer_engine, "before_cursor_execute", before)
        try:
            with ThreadPoolExecutor(max_workers=1) as workers:
                response = workers.submit(
                    client.post,
                    f"/api/customer/v1/workspaces/{wid}/campaign-drafts/{draft_id}/approve",
                    headers={"Origin": ORIGIN, "X-CSRF-Token": client.cookies[CSRF_COOKIE]},
                    json={"expected_revision": 1, "review_digest": review_digest},
                )
                if not attempted.wait(5):
                    blocker.rollback()
                    raise AssertionError("approval did not reach workspace lock")
                with Session(customer_engine) as db:
                    if revocation == "session":
                        row = db.get(CustomerSession, digest(client.cookies[SESSION_COOKIE]))
                        assert row is not None
                        row.revoked_at = int(time.time())
                    else:
                        member = db.get(CustomerMembership, (uid, wid))
                        assert member is not None
                        db.delete(member)
                    db.commit()
                blocker.commit()
                assert response.result(timeout=5).status_code in {401, 403, 404}
        finally:
            blocker.rollback()
            event.remove(customer_engine, "before_cursor_execute", before)
    with Session(customer_engine) as db:
        saved = db.get(CampaignRevision, (draft_id, 1))
        assert saved is not None and saved.approved_by is None
