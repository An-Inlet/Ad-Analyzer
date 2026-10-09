"""Explicit October-2026-only Q16 archive experiment; not default collection."""

import io
import json
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO, Literal, cast

import pytest
from app.api import customer_exports, customer_planning_documents
from app.billing.models import BillingEvent, WorkspaceBilling
from app.campaign_review.storage import LocalMediaStore
from app.customers.models import CustomerMembership
from app.database.session import Base
from app.goals.models import GoalConfirmation, GoalPreview
from app.lifecycle import archive
from app.lifecycle.privacy import bump_workspace_export_revision
from app.settings import Settings, settings
from app.workspaces.models import Workspace, WorkspaceConfiguration
from sqlalchemy import Engine, Table, create_engine, event, select
from sqlalchemy.orm import Session

from tests import test_customer_identity as identity
from tests.q16_clock_feasibility_probe import issue_at, paid
from tests.q16_exact_acceptance import retained_counts
from tests.q16_fixture import IMAGE, import_progress_stage, prepare_q16_case
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


@pytest.mark.parametrize("generation_stage", ["nov3", "october"])
def test_dated_q16_real_archive_privacy_delivery(
    customer_engine: Engine,
    generation_stage: Literal["nov3", "october"],
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
        generation_stage=generation_stage,
    )
    alice, other, provider = replicas
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
    plan_url = f"/api/customer/v1/workspaces/{ids.workspace_id}/planning/plans/{ids.plan_id}"
    current = alice.get(plan_url)
    assert current.status_code == 200, current.text
    value = current.json()
    assert value["freshness"] == "current"
    action = value["document"]["actions"][0]
    binding = dict(
        expected_version=1,
        expected_event_sequence=0,
        document_digest=value["document_digest"],
        action_key=action["key"],
        action_digest=value["action_digests"][action["key"]],
        supersedes_event_id=None,
    )
    decision = alice.post(
        plan_url + "/decisions",
        headers=headers(alice),
        json={
            **binding,
            "decision": "accepted_for_manual_application",
            "reason": "Customer review only; no advertising authority",
            "request_key": "q16-archive-decision",
        },
    )
    assert decision.status_code == 200, decision.text
    assert decision.json()["event_sequence"] == 1
    # Keep the rejected November chronology alongside the natural October chronology.
    assertion = alice.post(
        plan_url + "/assertions",
        headers=headers(alice),
        json={
            **binding,
            "expected_event_sequence": 1,
            "assertion": "customer_reports_applied",
            "reported_applied_at": value["document"]["generated_at"],
            "statement": "Customer report, not independently verified",
            "request_key": "q16-archive-report",
        },
    )
    if generation_stage == "nov3":
        assert assertion.status_code == 422, assertion.text
        assert "nonfuture reported application time required" in assertion.text
        expected_events = 1
    else:
        assert assertion.status_code == 200, assertion.text
        assert assertion.json()["event_sequence"] == 2
        expected_events = 2
        generated_at = datetime.fromisoformat(
            value["document"]["generated_at"].replace("Z", "+00:00")
        )
        assert generated_at.month == 10 and generated_at <= datetime.now(UTC)
        with Session(customer_engine) as db:
            confirmation = db.scalar(
                select(GoalConfirmation).where(GoalConfirmation.goal_id == ids.goal_id)
            )
            assert confirmation is not None
            assert confirmation.preview_id == ids.confirmation_id
            preview = db.get(GoalPreview, ids.confirmation_id)
            assert preview and preview.created_at.replace(tzinfo=UTC) <= generated_at
    events = alice.get(plan_url + "/events")
    assert events.status_code == 200 and len(events.json()["items"]) == expected_events
    original_events = events.json()["items"]
    if generation_stage == "october":
        native_before_progress = len(calls)
        stages: tuple[
            tuple[Literal["initial_day", "later_day", "refund_correction"], str, int], ...
        ] = (
            ("initial_day", "0", 2),
            ("later_day", "25000000", 3),
            ("refund_correction", "20000000", 3),
        )
        for stage, expected, days in stages:
            now = import_progress_stage(customer_engine, configuration, ids, stage=stage)
            paid(customer_engine, ids.workspace_id, now, monkeypatch, initial=False)
            monkeypatch.setattr(customer_planning_documents, "utc_now", lambda now=now: now)
            if stage != "refund_correction":
                expired = alice.get(plan_url + "/progress", params={"version": 1})
                assert expired.status_code == 401, expired.text
            issue_at(alice, provider, "q16-owner", now)
            counts = retained_counts(customer_engine)
            progress = alice.get(plan_url + "/progress", params={"version": 1})
            assert progress.status_code == 200, progress.text
            projection = progress.json()
            assert projection["net_sales_micros_exact"] == expected
            assert projection["sales"]["coverage"]["closed_day_count"] == days
            assert projection["manual_application"] == "not_assessed"
            assert projection["attribution"] == "unavailable"
            assert projection["goal"] == value["document"]["inputs"]["goal"]
            assert projection["document_digest"] == ids.document_digest
            unchanged = alice.get(plan_url, params={"version": 1})
            assert unchanged.status_code == 200, unchanged.text
            assert unchanged.json()["document"] == value["document"]
            retained = alice.get(plan_url + "/events")
            assert retained.status_code == 200 and retained.json()["items"] == original_events
            assert retained_counts(customer_engine) == counts
            (tmp_path / f"{stage}-progress.json").write_text(json.dumps(projection, indent=2))
        assert len(calls) == native_before_progress
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
    event_rows = [
        json.loads(line) for line in entries["data/planning_document_events.jsonl"].splitlines()
    ]
    assert len(event_rows) == expected_events and all(
        row["plan_id"] == ids.plan_id for row in event_rows
    )
    (tmp_path / "before-plan-events.jsonl").write_bytes(
        entries["data/planning_document_events.jsonl"]
    )
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
