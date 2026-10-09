"""Explicit October-2026-only Q16 archive experiment; not default collection."""

import io
import json
from collections.abc import Generator
from pathlib import Path
from typing import Any, BinaryIO, cast

import pytest
from app.api import customer_exports
from app.billing.models import BillingEvent, WorkspaceBilling
from app.campaign_review.storage import LocalMediaStore
from app.customers.models import CustomerMembership
from app.database.session import Base
from app.lifecycle import archive
from app.lifecycle.privacy import bump_workspace_export_revision
from app.settings import Settings, settings
from app.workspaces.models import Workspace, WorkspaceConfiguration
from sqlalchemy import Engine, Table, create_engine, event, select
from sqlalchemy.orm import Session

from tests import test_customer_identity as identity
from tests.q16_fixture import IMAGE, prepare_q16_case
from tests.test_customer_exports import unpack
from tests.test_customer_identity import login
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary
base_engine = identity.customer_engine


@pytest.fixture
def customer_engine(base_engine: Engine, tmp_path: Path) -> Generator[Engine, None, None]:
    if base_engine.dialect.name != "sqlite":
        yield base_engine
        return
    engine = create_engine(
        f"sqlite:///{tmp_path / 'archive.db'}", connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine, "connect")
    def foreign_keys(connection: Any, _: Any) -> None:
        connection.execute("PRAGMA foreign_keys=ON")

    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA journal_mode=WAL")
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


def finance(engine: Engine) -> str:
    with Session(engine) as db:
        assert db.scalar(select(WorkspaceBilling)) is not None
        assert db.scalar(select(BillingEvent)) is not None
        return repr(
            [
                [
                    tuple(getattr(row, c.name) for c in model.__table__.columns)
                    for row in db.scalars(
                        select(model).order_by(*cast(Table, model.__table__).primary_key.columns)
                    )
                ]
                for model in (WorkspaceBilling, BillingEvent)
            ]
        )


def test_dated_q16_real_archive_privacy_delivery(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[str] = []
    ids = prepare_q16_case(
        customer_engine,
        configuration,
        replicas,
        monkeypatch,
        tmp_path / "media",
        branch="privacy",
        native_calls=calls,
    )
    alice, other, _ = replicas
    alice.app.include_router(customer_exports.router)
    other.app.include_router(customer_exports.router)
    monkeypatch.setattr(settings, "customer_export_enabled", True)
    monkeypatch.setattr(
        customer_exports, "get_media_store", lambda: LocalMediaStore(tmp_path / "media")
    )
    foreign_actor = login(other, "q16-foreign:1")
    with Session(customer_engine) as db:
        workspace = Workspace(
            slug="q16-foreign", name="Foreign", client_name="Foreign", status="active"
        )
        db.add(workspace)
        db.flush()
        foreign_id = workspace.id
        db.add(CustomerMembership(workspace_id=foreign_id, user_id=foreign_actor, role="owner"))
        db.add(
            WorkspaceConfiguration(
                workspace_id=foreign_id,
                analysis={"marker": "untouched"},
                automation={},
                notifications={},
                branding={},
            )
        )
        db.commit()
    baseline_finance = finance(customer_engine)
    native_count = len(calls)
    path = f"/api/customer/v1/workspaces/{ids.workspace_id}/exports"

    def request(key: str) -> str:
        response = alice.post(path, json={}, headers={**headers(alice), "idempotency-key": key})
        assert response.status_code == 200, response.text
        return str(response.json()["request_id"])

    first = request("q16-archive-before")
    assert other.get(f"{path}/{first}/download").status_code in (403, 404)
    downloaded = alice.get(f"{path}/{first}/download")
    assert downloaded.status_code == 200, downloaded.text
    manifest, entries = unpack(io.BytesIO(downloaded.content))
    (tmp_path / "before-manifest.json").write_text(json.dumps(manifest, indent=2))
    (tmp_path / "before-plan-versions.jsonl").write_bytes(
        entries["data/planning_document_versions.jsonl"]
    )
    assert manifest["supported_customer_data_complete"] is True, manifest
    assert manifest["media_archive_complete"] is True
    assert manifest["delivery"] == "unconfirmed"
    assert entries[f"media/{ids.media_id}.png"] == IMAGE.read_bytes()
    versions = [
        json.loads(line) for line in entries["data/planning_document_versions.jsonl"].splitlines()
    ]
    assert len(versions) == 1 and versions[0]["plan_id"] == ids.plan_id
    assert [json.loads(line)["id"] for line in entries["data/workspaces.jsonl"].splitlines()] == [
        ids.workspace_id
    ]
    pending = request("q16-archive-erased-before-send")
    original_build = archive.build
    captured: list[dict[str, Any]] = []
    files: list[BinaryIO] = []

    def erase_after_real_snapshot(*args: Any, **kwargs: Any) -> Any:
        file, result = original_build(*args, **kwargs)
        captured.append(result)
        files.append(file)
        with Session(customer_engine) as db:
            bump_workspace_export_revision(db, ids.workspace_id)
            db.commit()
        return file, result

    with monkeypatch.context() as race:
        race.setattr(archive, "build", erase_after_real_snapshot)
        rejected = alice.get(f"{path}/{pending}/download")
    assert captured and captured[0]["supported_customer_data_complete"] is True
    assert rejected.status_code == 409, rejected.text
    assert rejected.headers["content-type"].startswith("application/json")
    assert files and all(file.closed for file in files)
    interrupted = alice.get(f"{path}/{pending}")
    assert interrupted.status_code == 200, interrupted.text
    assert interrupted.json()["state"] == "interrupted"
    assert interrupted.json()["manifest_sha256"] is None
    after = request("q16-archive-after-erasure")
    refreshed = alice.get(f"{path}/{after}/download")
    assert refreshed.status_code == 200, refreshed.text
    new_manifest, new_entries = unpack(io.BytesIO(refreshed.content))
    (tmp_path / "after-manifest.json").write_text(json.dumps(new_manifest, indent=2))
    (tmp_path / "after-plan-sections.json").write_text(
        json.dumps(
            {
                name: value.decode()
                for name, value in new_entries.items()
                if name.startswith("data/planning_")
            },
            indent=2,
        )
    )
    assert new_manifest["supported_customer_data_complete"] is True
    for table in (
        "planning_documents",
        "planning_input_revisions",
        "planning_document_versions",
        "planning_document_dependencies",
        "planning_document_events",
        "planning_document_requests",
    ):
        assert new_entries[f"data/{table}.jsonl"] == b""
    assert all(ids.plan_id.encode() not in value for value in new_entries.values())
    assert all(b'"untouched"' not in value for value in new_entries.values())
    assert finance(customer_engine) == baseline_finance
    with Session(customer_engine) as db:
        foreign = db.get(WorkspaceConfiguration, foreign_id)
        assert foreign and foreign.analysis == {"marker": "untouched"}
    assert len(calls) == native_count
    assert alice.delete("/api/customer/v1/session", headers=headers(alice)).status_code == 204
    assert alice.get(f"{path}/{after}/download").status_code == 401
