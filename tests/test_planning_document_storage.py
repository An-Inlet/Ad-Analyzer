"""Actual0087 DDL and erasable scoped planning graph, without service authority claims."""

import importlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.goals.models import Goal, GoalPreview, GoalRevision
from app.lifecycle.contracts import LifecycleScopeV1
from app.lifecycle.export_serializers import serialize
from app.lifecycle.inventory import export_section, verify_registry
from app.lifecycle.privacy import bump_workspace_export_revision
from app.planning_documents.documents import PlanVersion
from app.planning_documents.models import (
    PlanDependencyRow,
    PlanEventRow,
    PlanInputRow,
    PlanRequestRow,
    PlanRow,
    PlanVersionRow,
)
from app.planning_documents.storage import canonical
from app.workspaces.models import Workspace
from sqlalchemy import Engine, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from tests.migration_engine import migration_customer_engine as migration_customer_engine
from tests.test_customer_exports import export_engine as export_engine
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_planning_document_contracts import packet

pytestmark = pytest.mark.planning_boundary


def rows(db: Session, wid: int) -> tuple[PlanInputRow, PlanVersionRow]:
    data = packet()
    # This fixture seeds stored graph ownership, not a customer workflow or source proof.
    data["inputs"]["workspace_id"] = wid
    data["inputs"]["goal"]["workspace_id"] = wid
    data["inputs"]["goal"]["goal_id"] = f"{wid:032x}"
    data["inputs"]["goal"]["confirmation_reference"] = f"{wid + 10:032x}"
    for item in data["inputs"]["accounts"]:
        item["workspace_id"] = wid
    data["evidence"][0]["workspace_id"] = wid
    document = PlanVersion.model_validate(data)
    inputs = document.inputs
    now = datetime.now(UTC)
    if db.get(Workspace, wid) is None:
        db.add(Workspace(id=wid, slug=f"plan-{wid}", name="Plan", client_name="Test"))
    db.flush()
    db.add(Goal(id=inputs.goal.goal_id, workspace_id=wid, revision=1))
    db.flush()
    db.add(
        GoalRevision(
            goal_id=inputs.goal.goal_id,
            revision=1,
            workspace_id=wid,
            definition=inputs.goal.definition.model_dump(mode="json"),
            editor_id=inputs.created_by,
            created_at=now,
        )
    )
    db.flush()
    db.add(
        GoalPreview(
            id=inputs.goal.confirmation_reference,
            goal_id=inputs.goal.goal_id,
            revision=1,
            snapshot_id=None,
            created_at=now,
        )
    )
    db.add(
        PlanRow(
            workspace_id=wid,
            id=inputs.plan_id,
            input_head=1,
            version_head=1,
            event_sequence=0,
            created_by=inputs.created_by,
            created_at=now,
        )
    )
    db.flush()
    source = PlanInputRow(
        workspace_id=wid,
        plan_id=inputs.plan_id,
        revision=1,
        goal_id=inputs.goal.goal_id,
        goal_revision=1,
        confirmed_preview_id=inputs.goal.confirmation_reference,
        definition_digest=inputs.goal.definition_digest,
        canonical_json=canonical(inputs),
        digest=inputs.digest(),
        actor_id=inputs.created_by,
        created_at=inputs.created_at,
    )
    db.add(source)
    db.flush()
    version = PlanVersionRow(
        workspace_id=wid,
        plan_id=inputs.plan_id,
        version=1,
        input_revision=1,
        parent_digest=None,
        digest=document.digest(),
        canonical_json=canonical(document),
        generator_version=document.generator_version,
        policy_version=document.policy_version,
        actor_id=document.generated_by,
        generated_at=document.generated_at,
        valid_until=document.valid_until,
        privacy_revision=0,
    )
    db.add(version)
    db.flush()
    db.add(
        PlanRequestRow(
            workspace_id=wid,
            actor_id=inputs.created_by,
            operation="generate",
            request_key="same-key",
            request_digest="a" * 64,
            plan_id=inputs.plan_id,
            result_kind="version",
            input_revision=None,
            version=1,
            event_sequence=None,
        )
    )
    db.flush()
    db.add(
        PlanDependencyRow(
            workspace_id=wid,
            plan_id=inputs.plan_id,
            version=1,
            evidence_key="context",
            account_id=None,
            connection_id=None,
            store_id=None,
            kind="customer_context",
            source_binding_digest="a" * 64,
            document_digest=inputs.digest(),
            source_revision="1",
            observed_at=document.generated_at,
            expires_at=document.valid_until,
            privacy_revision=0,
        )
    )
    from app.planning_documents.events import CustomerDecision

    previous = None
    for sequence in (1, 2):
        event = CustomerDecision.model_validate(
            dict(
                workspace_id=wid,
                plan_id=inputs.plan_id,
                version=1,
                document_digest=document.digest(),
                action_key="inspect",
                action_digest=document.actions[0].digest(),
                event_id=f"{wid + sequence * 1000:032x}",
                actor_id=inputs.created_by,
                recorded_at=document.generated_at,
                decision="deferred",
                reason="Review later",
                supersedes_event_id=previous,
            )
        )
        db.add(
            PlanEventRow(
                workspace_id=wid,
                plan_id=inputs.plan_id,
                sequence=sequence,
                event_id=event.event_id,
                version=1,
                action_key="inspect",
                action_digest=event.action_digest,
                kind="decision",
                actor_id=inputs.created_by,
                recorded_at=event.recorded_at,
                prior_sequence=sequence - 1 if sequence > 1 else None,
                canonical_json=canonical(event),
                digest=event.digest(),
            )
        )
        db.flush()
        previous = event.event_id
    return source, version


def test_actual0087_immutable_scoped_receipts_export_erasure(
    migration_customer_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = migration_customer_engine
    migration = importlib.import_module("migrations.versions.20261008_0087_planning_documents")
    if engine.dialect.name == "sqlite":
        with engine.begin() as connection:
            for name in reversed(migration.TABLES):
                connection.execute(text(f"DROP TABLE {name}"))
            connection.execute(text("PRAGMA foreign_keys=ON"))
            with monkeypatch.context() as patch:
                patch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
                migration.upgrade()
    with Session(engine) as db:
        _, version = rows(db, 501)
        rows(db, 502)
        db.commit()
        stored = {c.name: getattr(version, c.name) for c in version.__table__.columns}
        exported, missing = serialize("planning_document_versions", stored)
        assert not missing and exported["document"]["inputs"]["workspace_id"] == 501
        verify_registry()
        section = export_section(
            db, LifecycleScopeV1(workspace_id=501), "planning_document_versions"
        )
        assert len(section["rows"]) == 1
        for model, field in (
            (PlanDependencyRow, "document_digest"),
            (PlanEventRow, "digest"),
            (PlanRequestRow, "request_digest"),
        ):
            with pytest.raises(DBAPIError), db.begin_nested():
                db.execute(
                    update(model).where(model.workspace_id == 501).values(**{field: "b" * 64})
                )
        for statement in (
            update(PlanInputRow).where(PlanInputRow.workspace_id == 501).values(digest="b" * 64),
            update(PlanVersionRow)
            .where(PlanVersionRow.workspace_id == 501)
            .values(digest="b" * 64),
        ):
            with pytest.raises(DBAPIError), db.begin_nested():
                db.execute(statement)
        with pytest.raises(DBAPIError), db.begin_nested():
            db.add(
                PlanRequestRow(
                    workspace_id=501,
                    actor_id="a" * 32,
                    operation="bad",
                    request_key="bad",
                    request_digest="a" * 64,
                    plan_id=version.plan_id,
                    result_kind="version",
                    input_revision=1,
                    version=1,
                    event_sequence=None,
                )
            )
            db.flush()
        with pytest.raises(DBAPIError), db.begin_nested():
            db.add(
                PlanRequestRow(
                    workspace_id=501,
                    actor_id="a" * 32,
                    operation="bad",
                    request_key="missing-version",
                    request_digest="a" * 64,
                    plan_id=version.plan_id,
                    result_kind="version",
                    input_revision=None,
                    version=2,
                    event_sequence=None,
                )
            )
            db.flush()
        with pytest.raises(RuntimeError, match="cannot discard"), monkeypatch.context() as patch:
            patch.setattr(migration, "op", Operations(MigrationContext.configure(db.connection())))
            migration.downgrade()
        bump_workspace_export_revision(db, 501)
        db.commit()
        for name in migration.TABLES:
            assert db.scalar(text(f"SELECT count(*) FROM {name} WHERE workspace_id=501")) == 0
        assert (
            db.scalar(select(PlanVersionRow).where(PlanVersionRow.workspace_id == 502)) is not None
        )
        workspace = db.get(Workspace, 501)
        assert workspace is not None and workspace.export_privacy_revision == 1
        with pytest.raises(ValueError, match="digest"):
            serialize("planning_document_versions", {**stored, "digest": "0" * 64})


def test_maximum_canonical_plan_export_and_overbound_refusal() -> None:
    from app.planning_documents.common import MAX_DOCUMENT_BYTES

    data = packet()
    base = data["actions"][0]
    data["actions"] = [
        {**base, "key": f"item_{i}", "priority": i + 1, "manual_steps": ["x"] * 20}
        for i in range(26)
    ]
    low, high = 1, 2000
    while low < high:
        middle = (low + high + 1) // 2
        for action in data["actions"]:
            action["manual_steps"] = ["x" * middle] * 20
        try:
            PlanVersion.model_validate(data)
        except ValueError:
            high = middle - 1
        else:
            low = middle
    for action in data["actions"]:
        action["manual_steps"] = ["x" * low] * 20
    document = PlanVersion.model_validate(data)
    remaining = MAX_DOCUMENT_BYTES - len(canonical(document).encode())
    data["summary"] += "x" * remaining
    document = PlanVersion.model_validate(data)
    assert len(canonical(document).encode()) == MAX_DOCUMENT_BYTES
    row: dict[str, Any] = dict(
        workspace_id=document.inputs.workspace_id,
        plan_id=document.inputs.plan_id,
        version=1,
        input_revision=1,
        parent_digest=None,
        digest=document.digest(),
        canonical_json=canonical(document),
        generator_version=document.generator_version,
        policy_version=document.policy_version,
        actor_id=document.generated_by,
        generated_at=document.generated_at,
        valid_until=document.valid_until,
        privacy_revision=0,
    )
    exported, omitted = serialize("planning_document_versions", row)
    assert not omitted and exported["document"]["summary"] == data["summary"]
    with pytest.raises(ValueError, match="exceeds bound"):
        serialize(
            "planning_document_versions", {**row, "canonical_json": row["canonical_json"] + " "}
        )
    with pytest.raises(ValueError, match="content mismatch"):
        serialize("planning_document_versions", {**row, "generated_at": datetime.now(UTC)})


def test_actual_archive_includes_planning_graph_and_privacy_fences_delivery(
    export_engine: Engine, tmp_path: Path
) -> None:
    import json

    from app.campaign_review.storage import LocalMediaStore
    from fastapi import HTTPException

    from tests.test_customer_exports import build, prepared, unpack

    authority, wid = prepared(export_engine)
    with Session(export_engine) as db:
        rows(db, wid)
        db.commit()
    file, manifest = build(export_engine, authority, LocalMediaStore(tmp_path / "media"))
    try:
        _, entries = unpack(file)
        exported = [
            json.loads(line)
            for line in entries["data/planning_document_versions.jsonl"].splitlines()
        ]
        assert len(exported) == 1 and exported[0]["document"]["inputs"]["workspace_id"] == wid
        receipt = json.loads(entries["data/planning_document_requests.jsonl"].splitlines()[0])
        assert "request_key" not in receipt and "request_digest" not in receipt
        assert manifest["supported_customer_data_complete"] is True
        with Session(export_engine) as db:
            bump_workspace_export_revision(db, wid)
            db.commit()
        with pytest.raises(HTTPException):
            authority.check()
    finally:
        file.close()


def test_stored_version_privacy_scalar_and_mixed_evidence_are_rejected() -> None:
    from app.planning_documents.storage import document_for_row

    document = PlanVersion.model_validate(packet())
    row = dict(
        workspace_id=document.inputs.workspace_id,
        plan_id=document.inputs.plan_id,
        version=1,
        input_revision=1,
        parent_digest=None,
        digest=document.digest(),
        canonical_json=canonical(document),
        generator_version=document.generator_version,
        policy_version=document.policy_version,
        actor_id=document.generated_by,
        generated_at=document.generated_at,
        valid_until=document.valid_until,
        privacy_revision=1,
    )
    with pytest.raises(ValueError, match="privacy binding"):
        document_for_row("planning_document_versions", row)
    other = document.evidence[0].model_copy(update={"key": "other", "privacy_revision": 1})
    mixed = PlanVersion.model_validate(
        document.model_copy(update={"evidence": (*document.evidence, other)})
    )
    row.update(privacy_revision=0, canonical_json=canonical(mixed), digest=mixed.digest())
    with pytest.raises(ValueError, match="privacy binding"):
        document_for_row("planning_document_versions", row)
