"""Current privacy on retained authentic financial/social evidence; never forwarding."""

import hashlib
import io
import json
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.api import customer_execution, customer_exports, customer_lifecycle
from app.api.customer import router as customer_router
from app.campaign_review.storage import LocalMediaStore
from app.customers.access import CSRF_COOKIE
from app.customers.identity import get_identity_provider
from app.database.session import get_db
from app.lifecycle.quiescing import preview_digest
from app.settings import settings
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.archive_financial_social_privacy import (
    closure_delta,
    creation_delta,
    download_delta,
    login_delta,
    same,
)
from tests.archive_financial_social_retained_fixture import graph, retained_archive_source
from tests.test_customer_exports import unpack
from tests.test_customer_identity import ORIGIN, FakeProvider, login
from tests.test_customer_identity import customer_engine as customer_engine


def test_current_archive_and_closure(
    customer_engine: Engine,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with retained_archive_source(customer_engine, tmp_path / "archive-original") as (engine, ids):
        store = LocalMediaStore(tmp_path / "archive-original" / "media")
        monkeypatch.setattr(settings, "customer_app_origin", ORIGIN)
        monkeypatch.setattr(settings, "customer_export_enabled", True)
        monkeypatch.setattr(customer_exports, "get_media_store", lambda: store)
        provider = FakeProvider()
        provider.email = "mock@example.invalid"
        app = FastAPI()
        for router in (
            customer_router,
            customer_exports.router,
            customer_lifecycle.router,
            customer_execution.router,
        ):
            app.include_router(router)

        def database() -> Generator[Session, None, None]:
            with Session(engine) as db:
                yield db

        app.dependency_overrides[get_db] = database
        app.dependency_overrides[get_identity_provider] = lambda: provider
        source = graph(engine)
        a, b = ids.brand_a, ids.brand_b
        assert a.social
        media = next(r for r in source["customer_media_objects"] if r["id"] == a.social.media_id)
        original_image = store.read_exact(a.workspace_id, media["sha256"], media["size"])
        with TestClient(app, base_url=ORIGIN) as alice, TestClient(app, base_url=ORIGIN) as bob:
            started = datetime.now(UTC)
            assert login(alice, "brand-a:1") == a.actor_id
            assert login(bob, "brand-b:1") == b.actor_id
            login_delta(source, graph(engine), ids, alice, bob, started, datetime.now(UTC))
            for client, brand in ((alice, a), (bob, b)):
                before = graph(engine)
                denied = client.post(
                    f"/api/customer/v1/workspaces/{brand.workspace_id}/execution/runs/{brand.successor_run_id}/advance",
                    headers={"Origin": ORIGIN, "X-CSRF-Token": client.cookies[CSRF_COOKIE]},
                )
                assert denied.status_code == 409 and denied.json() == {
                    "detail": "advertising_writes_disabled_in_planning_mvp"
                }
                same(graph(engine), before)
            headers = {
                "Origin": ORIGIN,
                "X-CSRF-Token": alice.cookies[CSRF_COOKIE],
                "Idempotency-Key": "archive-replacement-social",
            }
            base = f"/api/customer/v1/workspaces/{a.workspace_id}"
            before, started = graph(engine), datetime.now(UTC)
            response = alice.post(base + "/exports", json={}, headers=headers)
            assert response.status_code == 200, response.text
            export_id = response.json()["request_id"]
            creation_delta(
                before, graph(engine), ids, export_id, "export", started, datetime.now(UTC)
            )
            download = base + f"/exports/{export_id}/download"
            before = graph(engine)
            assert bob.get(download).status_code in {403, 404}
            same(graph(engine), before)
            started = datetime.now(UTC)
            response = alice.get(download)
            assert response.status_code == 200, response.text
            manifest, entries = unpack(io.BytesIO(response.content))
            download_delta(before, graph(engine), export_id, manifest, started, datetime.now(UTC))
            assert manifest["supported_customer_data_complete"]
            assert manifest["media_archive_complete"]
            for entry, payload in entries.items():
                if entry.startswith("data/") and entry.endswith(".jsonl"):
                    for line in payload.splitlines():
                        record = json.loads(line)
                        if "workspace_id" in record:
                            assert record["workspace_id"] == a.workspace_id, entry
            for table, field in (
                ("provider_reservation_replacements", "document"),
                ("customer_social_configuration_reviews", "document"),
                ("customer_social_configuration_approvals", "digest"),
            ):
                exported = [
                    json.loads(line) for line in entries[f"data/{table}.jsonl"].splitlines()
                ]
                expected = [r for r in source[table] if r["workspace_id"] == a.workspace_id]
                assert len(exported) == len(expected) == 1
                assert exported[0][field] == expected[0][field]
            assert (
                a.social.review_id.encode()
                in entries["data/customer_social_configuration_reviews.jsonl"]
            )
            assert b.successor_run_id.encode() not in b"".join(entries.values())
            assert any(
                hashlib.sha256(value).hexdigest() == media["sha256"] for value in entries.values()
            )
            headers["Idempotency-Key"] = "closure-replacement-social"
            before, started = graph(engine), datetime.now(UTC)
            preview = alice.post(base + "/closure-preview", json={}, headers=headers)
            assert preview.status_code == 200, preview.text
            data = preview.json()
            creation_delta(
                before,
                graph(engine),
                ids,
                data["request_id"],
                "close",
                started,
                datetime.now(UTC),
                data["inventory_digest"],
            )
            with Session(engine) as db:
                assert preview_digest(db, a.workspace_id) == data["inventory_digest"]
            before, started = graph(engine), datetime.now(UTC)
            closed = alice.post(
                base + f"/closures/{data['request_id']}/confirm",
                headers=headers,
                json={
                    "expected_revision": data["revision"],
                    "inventory_digest": data["inventory_digest"],
                    "confirm_workspace_id": a.workspace_id,
                },
            )
            assert closed.status_code == 200, closed.text
            assert closed.json()["state"] == "blocked" and closed.json()["closed"] is False
            closure_delta(
                before, graph(engine), ids, data["request_id"], started, datetime.now(UTC)
            )
            before = graph(engine)
            assert alice.get("/api/customer/v1/session").status_code == 200
            assert bob.get("/api/customer/v1/session").status_code == 200
            assert bob.get(base + f"/closures/{data['request_id']}").status_code in {403, 404}
            status = alice.get(base + f"/closures/{data['request_id']}")
            assert status.status_code == 200 and status.json()["closed"] is False
            same(graph(engine), before)
            for client, brand in ((alice, a), (bob, b)):
                before = graph(engine)
                denied = client.post(
                    f"/api/customer/v1/workspaces/{brand.workspace_id}/execution/runs/{brand.successor_run_id}/advance",
                    headers={"Origin": ORIGIN, "X-CSRF-Token": client.cookies[CSRF_COOKIE]},
                )
                if brand == a:
                    assert denied.status_code == 404 and denied.json() == {
                        "detail": "workspace not found"
                    }
                else:
                    assert denied.status_code == 409 and denied.json() == {
                        "detail": "advertising_writes_disabled_in_planning_mvp"
                    }
                same(graph(engine), before)
            assert (
                store.read_exact(a.workspace_id, media["sha256"], media["size"]) == original_image
            )
