"""Real database snapshots and HTTP exports; storage/identity are offline provider seams."""

import hashlib
import io
import json
import tarfile
import tempfile
import time
from collections.abc import Generator
from pathlib import Path
from typing import Any, BinaryIO, cast
from uuid import uuid4

import pytest
from app.api.customer import router as customer_router
from app.api.customer_exports import router
from app.campaign_review.models import MediaObject
from app.campaign_review.storage import LocalMediaStore
from app.customers.access import CSRF_COOKIE, CustomerPrincipal
from app.customers.identity import get_identity_provider
from app.customers.models import CustomerMembership, CustomerSession, CustomerUser
from app.database.session import Base, get_db
from app.lifecycle import archive
from app.lifecycle.contracts import LifecycleInputV1, LifecycleScopeV1
from app.lifecycle.exports import SLOTS, Authority, Download
from app.lifecycle.models import LifecycleRequest, LifecycleStep
from app.lifecycle.service import begin
from app.settings import settings
from app.workspaces.models import Workspace, WorkspaceConfiguration
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session
from starlette.requests import ClientDisconnect

from tests.test_customer_identity import ORIGIN, FakeProvider, login
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_lifecycle import KEY, NOW, seed


@pytest.fixture
def export_engine(customer_engine: Engine, tmp_path: Path) -> Generator[Engine, None, None]:
    if customer_engine.dialect.name != "sqlite":
        yield customer_engine
        return
    engine = create_engine(
        f"sqlite:///{tmp_path / 'export.db'}", connect_args={"check_same_thread": False}
    )
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA journal_mode=WAL")
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


def prepared(engine: Engine, provider: FakeProvider | None = None) -> tuple[Authority, int]:
    with Session(engine) as db:
        principal, wid = seed(db)
        row = begin(
            db,
            principal,
            provider or FakeProvider(),
            LifecycleInputV1(scope=LifecycleScopeV1(workspace_id=wid), operation="export"),
            KEY,
            NOW,
        )
        db.commit()
        authority = Authority(engine, principal, provider or FakeProvider(), wid, row.id)
    authority.claim()
    return authority, wid


def build(
    engine: Engine, authority: Authority, store: LocalMediaStore
) -> tuple[BinaryIO, dict[str, Any]]:
    assert authority.revision is not None
    return archive.build(
        engine,
        authority.wid,
        authority.request_id,
        authority.revision,
        lambda: store,
        authority.check,
    )


def unpack(file: Any) -> tuple[dict[str, Any], dict[str, bytes]]:
    with tarfile.open(fileobj=file) as tar:
        assert all(not item.name.startswith("/") and ".." not in item.name for item in tar)
        entries = {}
        for item in tar:
            if item.isfile():
                member = tar.extractfile(item)
                assert member is not None
                entries[item.name] = member.read()
    return json.loads(entries["manifest.json"]), entries


def test_archive_snapshot_media_and_secret_exclusion(export_engine: Engine, tmp_path: Path) -> None:
    authority, wid = prepared(export_engine)
    store = LocalMediaStore(tmp_path / "media")
    data, identifier = b"fixture media bytes", uuid4().hex
    digest = hashlib.sha256(data).hexdigest()
    store.put_if_absent(wid, digest, len(data), [data])
    with Session(export_engine) as db:
        _, other = seed(db, "foreign")
        db.add(
            MediaObject(
                id=identifier,
                workspace_id=wid,
                sha256=digest,
                size=len(data),
                mime="image/png",
                width=1,
                height=1,
                created_by=authority.user_id,
                created_at=NOW,
            )
        )
        db.add(
            WorkspaceConfiguration(
                workspace_id=wid,
                analysis={"test": "owned-value"},
                automation={},
                notifications={},
                branding={},
            )
        )
        db.commit()
    file, manifest = build(export_engine, authority, store)
    try:
        parsed, entries = unpack(file)
        assert parsed == manifest
        assert entries[f"media/{identifier}.png"] == data
        assert manifest["media_archive_complete"] is True
        assert manifest["supported_customer_data_complete"] is True
        assert manifest["all_stored_workspace_data_complete"] is False
        assert manifest["delivery"] == "unconfirmed"
        assert b'"owned-value"' in entries["data/workspace_configurations.jsonl"]
        rows = [json.loads(line) for line in entries["data/workspaces.jsonl"].splitlines()]
        assert [row["id"] for row in rows] == [wid] and wid != other
        assert "data/customer_sessions.jsonl" not in entries
        for section in manifest["sections"]:
            assert hashlib.sha256(entries[section["path"]]).hexdigest() == section["sha256"]
        authority.finish(manifest)
        with Session(export_engine) as db:
            receipt = db.get(LifecycleRequest, authority.request_id)
            assert receipt is not None and receipt.state == "archive_built"
            assert receipt.blockers[0]["snapshot_as_of"] == manifest["snapshot_as_of"]
    finally:
        file.close()


@pytest.mark.parametrize("failure", ["session", "membership", "provider", "expired"])
def test_fresh_stream_revocation_and_cleanup(
    export_engine: Engine, tmp_path: Path, failure: str
) -> None:
    provider = FakeProvider()
    authority, wid = prepared(export_engine, provider)
    file, manifest = build(export_engine, authority, LocalMediaStore(tmp_path / "media"))
    authority.finish(manifest)
    assert SLOTS.acquire(blocking=False)
    download = Download(file, authority)
    stream = download.chunks()
    assert next(stream)
    with Session(export_engine) as db:
        session = db.get(CustomerSession, authority.session_digest)
        member = db.get(CustomerMembership, (authority.user_id, wid))
        assert session is not None and member is not None
        if failure == "session":
            session.revoked_at = int(time.time())
        elif failure == "membership":
            member.status = "suspended"
        elif failure == "expired":
            session.expires_at = int(time.time()) - 1
        else:
            provider.disabled.add("one")
        db.commit()
    with pytest.raises(HTTPException):
        next(stream)
    assert file.closed
    download.close()
    assert SLOTS.acquire(blocking=False)
    SLOTS.release()


def test_nested_secrets_mark_incomplete_and_snapshot_is_consistent(
    export_engine: Engine, tmp_path: Path
) -> None:
    authority, wid = prepared(export_engine)
    with Session(export_engine) as db:
        db.add(
            WorkspaceConfiguration(
                workspace_id=wid,
                analysis={"access_token": "never-export"},
                automation={},
                notifications={},
                branding={},
            )
        )
        db.commit()
    calls = 0
    original = authority.check

    def change() -> None:
        nonlocal calls
        original()
        calls += 1
        if calls == 3:
            with Session(export_engine) as db:
                workspace = db.get(Workspace, wid)
                assert workspace is not None
                workspace.name = "changed after snapshot"
                db.commit()

    authority.check = change  # type: ignore[method-assign]
    file, manifest = build(export_engine, authority, LocalMediaStore(tmp_path / "media"))
    try:
        _, entries = unpack(file)
        assert b"never-export" not in b"".join(entries.values())
        assert b"changed after snapshot" not in entries["data/workspaces.jsonl"]
        assert not manifest["supported_customer_data_complete"]
        section = next(
            s for s in manifest["sections"] if s["path"].endswith("workspace_configurations.jsonl")
        )
        assert "analysis" in section["unsupported_fields"]
    finally:
        file.close()


@pytest.mark.parametrize(
    "bound", ["MAX_ROWS", "MAX_ROW_BYTES", "MAX_DATA_BYTES", "MAX_ARCHIVE_BYTES", "MAX_SECONDS"]
)
def test_bounds_do_not_produce_complete_archive(
    export_engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bound: str
) -> None:
    authority, _ = prepared(export_engine)
    monkeypatch.setattr(archive, bound, 0)
    with pytest.raises(ValueError):
        build(export_engine, authority, LocalMediaStore(tmp_path / "media"))
    authority.finish(None)
    with Session(export_engine) as db:
        row = db.get(LifecycleRequest, authority.request_id)
        step = db.get(LifecycleStep, (authority.request_id, "export_build"))
        assert row is not None and row.state == "interrupted"
        assert step is not None and step.evidence_digest is None


def test_actual_http_create_replay_download_foreign_owner_and_logout(
    export_engine: Engine, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from app.api import customer_exports

    monkeypatch.setattr(settings, "customer_app_origin", ORIGIN)
    monkeypatch.setattr(
        customer_exports, "get_media_store", lambda: LocalMediaStore(tmp_path / "media")
    )
    app = FastAPI()
    app.include_router(customer_router)
    app.include_router(router)
    provider = FakeProvider()

    def database() -> Generator[Session, None, None]:
        with Session(export_engine) as db:
            yield db

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_identity_provider] = lambda: provider
    with TestClient(app, base_url=ORIGIN) as client, TestClient(app, base_url=ORIGIN) as other:
        uid, other_uid = login(client, "owner:1"), login(other, "another:1")
        with Session(export_engine) as db:
            workspace = Workspace(slug="test", name="test", client_name="test", status="active")
            db.add(workspace)
            db.flush()
            wid = workspace.id
            db.add_all(
                [
                    CustomerMembership(
                        workspace_id=wid, user_id=user, role="owner", status="active"
                    )
                    for user in [uid, other_uid]
                ]
            )
            db.commit()
        headers = {
            "origin": ORIGIN,
            "x-csrf-token": client.cookies[CSRF_COOKIE],
            "idempotency-key": KEY,
        }
        path = f"/api/customer/v1/workspaces/{wid}/exports"
        assert client.post(path, json={}).status_code == 403
        assert client.post(path, json={"include_media": False}, headers=headers).status_code == 422
        response = client.post(path, json={}, headers=headers)
        assert response.status_code == 200, response.text
        rid = response.json()["request_id"]
        assert client.post(path, json={}, headers=headers).json()["request_id"] == rid
        assert other.get(f"{path}/{rid}").status_code == 404
        response = client.get(f"{path}/{rid}/download")
        assert response.status_code == 200, response.text
        manifest, _ = unpack(io.BytesIO(response.content))
        assert manifest["snapshot_revision"] == 2
        status = client.get(f"{path}/{rid}").json()
        assert status["state"] == "archive_built" and status["delivery"] == "unconfirmed"
        assert client.delete("/api/customer/v1/session", headers=headers).status_code == 204
        assert client.get(f"{path}/{rid}/download").status_code == 401


@pytest.mark.parametrize("failure", ["missing", "hash", "path"])
def test_invalid_media_never_produces_complete_archive(
    export_engine: Engine, tmp_path: Path, failure: str
) -> None:
    authority, wid = prepared(export_engine)
    data = b"original"
    sha = hashlib.sha256(data).hexdigest()
    store = LocalMediaStore(tmp_path / "media")
    if failure != "missing":
        store.put_if_absent(wid, sha, len(data), [data])
    with Session(export_engine) as db:
        db.add(
            MediaObject(
                id="../bad" if failure == "path" else uuid4().hex,
                workspace_id=wid,
                sha256=sha,
                size=len(data),
                mime="image/png",
                width=1,
                height=1,
                created_by=authority.user_id,
                created_at=NOW,
            )
        )
        db.commit()
    if failure == "hash":
        store.read_exact = lambda *args: b"corrupt!"  # type: ignore[method-assign]
    with pytest.raises((ValueError, HTTPException, FileNotFoundError)):
        build(export_engine, authority, store)
    authority.finish(None)


def test_superseded_attempt_and_expired_stream_never_claim_delivery(
    export_engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.lifecycle import exports

    authority, _ = prepared(export_engine)
    with pytest.raises(HTTPException, match="already running"):
        authority.claim()
    file, manifest = build(export_engine, authority, LocalMediaStore(tmp_path / "media"))
    authority.finish(manifest)
    assert SLOTS.acquire(blocking=False)
    download = Download(file, authority)
    monkeypatch.setattr(exports, "STREAM_SECONDS", 0)
    with pytest.raises(RuntimeError, match="expired"):
        next(download.chunks())
    assert file.closed
    old_revision, old_fence = authority.revision, authority.fence
    authority.claim()
    authority.revision, authority.fence = old_revision, old_fence
    with pytest.raises(HTTPException, match="superseded"):
        authority.check()


def test_build_revocation_cleans_temporary_files(
    export_engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    authority, _ = prepared(export_engine)
    files: list[BinaryIO] = []
    original = tempfile.TemporaryFile

    def tracked(*args: Any, **kwargs: Any) -> BinaryIO:
        file = cast(BinaryIO, original(*args, **kwargs))
        files.append(file)
        return file

    monkeypatch.setattr(tempfile, "TemporaryFile", tracked)
    calls = 0
    fresh = authority.check

    def revoke() -> None:
        nonlocal calls
        calls += 1
        if calls == 4:
            with Session(export_engine) as db:
                row = db.get(CustomerSession, authority.session_digest)
                assert row is not None
                row.revoked_at = int(time.time())
                db.commit()
        fresh()

    authority.check = revoke  # type: ignore[method-assign]
    with pytest.raises(HTTPException):
        build(export_engine, authority, LocalMediaStore(tmp_path / "media"))
    assert files and all(file.closed for file in files)
    authority.finish(None)


def test_response_send_failure_closes_unstarted_resource(
    export_engine: Engine, tmp_path: Path
) -> None:
    import asyncio

    from app.api.customer_exports import ExportResponse

    authority, _ = prepared(export_engine)
    file, manifest = build(export_engine, authority, LocalMediaStore(tmp_path / "media"))
    authority.finish(manifest)
    assert SLOTS.acquire(blocking=False)
    resource = Download(file, authority)

    async def send(message: Any) -> None:
        raise OSError("offline client")

    async def receive() -> Any:
        return {"type": "http.disconnect"}

    with pytest.raises(ClientDisconnect):
        asyncio.run(
            ExportResponse(resource, authority.request_id)(
                {"type": "http", "asgi": {"spec_version": "2.4"}}, receive, send
            )
        )
    assert file.closed
    resource.close()


def test_revocation_during_provider_check_is_observed(export_engine: Engine) -> None:
    authority, _ = prepared(export_engine)

    class RevokingProvider(FakeProvider):
        def check_active(self, subject: str, authenticated_at: int) -> None:
            with Session(export_engine) as db:
                row = db.get(CustomerSession, authority.session_digest)
                assert row is not None
                row.revoked_at = int(time.time())
                db.commit()

    authority.provider = RevokingProvider()
    with pytest.raises(HTTPException):
        authority.check()


def test_closing_workspace_export_and_admin_denial(export_engine: Engine) -> None:
    authority, wid = prepared(export_engine)
    authority.finish(None)
    with Session(export_engine) as db:
        workspace = db.get(Workspace, wid)
        assert workspace is not None
        workspace.status = "closing"
        db.commit()
        principal = CustomerPrincipal(
            db.get(CustomerUser, authority.user_id),  # type: ignore[arg-type]
            db.get(CustomerSession, authority.session_digest),  # type: ignore[arg-type]
        )
        row = begin(
            db,
            principal,
            FakeProvider(),
            LifecycleInputV1(scope=LifecycleScopeV1(workspace_id=wid), operation="export"),
            "closing-workspace-export",
            NOW,
        )
        db.commit()
        assert row.operation == "export"
        member = db.get(CustomerMembership, (authority.user_id, wid))
        assert member is not None
        member.role = "admin"
        db.commit()
    with pytest.raises(HTTPException):
        authority.check()


def test_postgres_concurrent_claim_has_single_winner(export_engine: Engine) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    if export_engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL row lock contention")
    authority, _ = prepared(export_engine)
    authority.finish(None)
    barrier = Barrier(2)

    def claim() -> str:
        with Session(export_engine) as db:
            user = db.get(CustomerUser, authority.user_id)
            session = db.get(CustomerSession, authority.session_digest)
            assert user is not None and session is not None
            independent = Authority(
                export_engine,
                CustomerPrincipal(user, session),
                FakeProvider(),
                authority.wid,
                authority.request_id,
            )
        barrier.wait(timeout=10)
        try:
            independent.claim()
            return "claimed"
        except HTTPException as error:
            assert error.status_code == 409
            return "busy"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: claim(), range(2)))
    assert sorted(results) == ["busy", "claimed"]


def test_supported_schema_has_explicit_field_dispositions() -> None:
    from app.lifecycle.export_serializers import exclusion, fields
    from app.lifecycle.registry import TABLES

    for name, policy in TABLES.items():
        if policy.scope in {"identity_global", "platform_global", "unclassified"}:
            continue
        for column in Base.metadata.tables[name].c.keys():
            assert column in fields(name) or exclusion(name, column) == "security_or_internal", (
                name,
                column,
            )
