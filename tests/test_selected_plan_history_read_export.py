"""Persisted no-selection v4 fixtures: read/export integrity, not live generation."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from app.ads.models import DailyMetric
from app.campaign_review.storage import LocalMediaStore
from app.customers.access import CustomerPrincipal
from app.lifecycle.contracts import LifecycleInputV1, LifecycleScopeV1
from app.lifecycle.export_serializers import serialize
from app.lifecycle.exports import Authority
from app.lifecycle.privacy import bump_workspace_export_revision
from app.lifecycle.service import begin
from app.planning_documents import repository
from app.planning_documents.documents import PlanVersion
from app.planning_documents.models import PlanDependencyRow, PlanInputRow, PlanRow, PlanVersionRow
from app.planning_documents.selected_inputs import (
    SELECTED_GENERATOR_VERSION,
    SELECTED_POLICY_VERSION,
)
from app.planning_documents.selected_plan_proof import SelectedRetainedProofV1
from app.planning_documents.selected_plan_retained import capture_selected_reporting_pin
from app.planning_documents.selected_plan_witnesses import capture_selected_retained_sources
from app.planning_documents.storage import canonical
from app.settings import Settings, settings
from fastapi import HTTPException
from sqlalchemy import Engine, delete, func, select, update
from sqlalchemy.orm import Session

from tests.test_customer_exports import build, unpack
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_planning_retained_sources import dependencies, prepare
from tests.test_shopify_sales import configuration as configuration


def stored_fixture(
    engine: Engine, configuration: Settings, replicas: Any, monkeypatch: pytest.MonkeyPatch
) -> tuple[PlanVersion, CustomerPrincipal]:
    _, old, principal, _, _ = prepare(engine, configuration, replicas, monkeypatch)
    with Session(engine) as db, db.begin():
        proof = SelectedRetainedProofV1(
            accounts=tuple(
                capture_selected_reporting_pin(
                    db, principal, a, old.evidence[0].privacy_revision, None, datetime.now(UTC)
                )
                for a in old.inputs.accounts
            )
        )
        inputs = old.inputs.model_copy(update={"selected_reporting": (), "plan_id": uuid4().hex})
        document = PlanVersion.model_validate(
            old.model_copy(
                update={
                    "inputs": inputs,
                    "selected_reporting_proof": proof,
                    "policy_version": SELECTED_POLICY_VERSION,
                    "generator_version": SELECTED_GENERATOR_VERSION,
                }
            )
        )
        witnesses = capture_selected_retained_sources(
            db, principal=principal, document=document, now=datetime.now(UTC)
        )
        ordinary = []
        for row in dependencies(db, old):
            if not row.kind.startswith("local_"):
                values = {c.name: getattr(row, c.name) for c in row.__table__.columns}
                values["plan_id"] = inputs.plan_id
                ordinary.append(PlanDependencyRow(**values))
        db.add(
            PlanRow(
                workspace_id=inputs.workspace_id,
                id=inputs.plan_id,
                input_head=1,
                version_head=1,
                event_sequence=0,
                created_by=inputs.created_by,
                created_at=inputs.created_at,
            )
        )
        db.flush()
        db.add(
            PlanInputRow(
                workspace_id=inputs.workspace_id,
                plan_id=inputs.plan_id,
                revision=1,
                goal_id=inputs.goal.goal_id,
                goal_revision=inputs.goal.revision,
                confirmed_preview_id=inputs.goal.confirmation_reference,
                definition_digest=inputs.goal.definition_digest,
                canonical_json=canonical(inputs),
                digest=inputs.digest(),
                actor_id=inputs.created_by,
                created_at=inputs.created_at,
            )
        )
        db.flush()
        db.add(
            PlanVersionRow(
                workspace_id=inputs.workspace_id,
                plan_id=inputs.plan_id,
                version=1,
                input_revision=1,
                parent_digest=None,
                canonical_json=canonical(document),
                digest=document.digest(),
                generator_version=document.generator_version,
                policy_version=document.policy_version,
                actor_id=document.generated_by,
                generated_at=document.generated_at,
                valid_until=document.valid_until,
                privacy_revision=old.evidence[0].privacy_revision,
            )
        )
        db.flush()
        db.add_all(ordinary + [PlanDependencyRow(**w.model_dump()) for w in witnesses])
    return document, principal


def test_saved_selected_history_and_export_require_complete_sql_graph(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    document, principal = stored_fixture(customer_engine, configuration, replicas, monkeypatch)
    wid, pid = document.inputs.workspace_id, document.inputs.plan_id
    with Session(customer_engine) as db, db.begin():
        # Saved no-selection history binds the old opaque aggregate commitment;
        # later mutable reporting values do not get presented as its old facts.
        db.execute(update(DailyMetric).values(cost_micros=DailyMetric.cost_micros + 1))
    with Session(customer_engine) as db:
        plan = repository.owned(db, wid, pid)
        row, actual = repository.version(db, plan)
        assert actual == document
        values = repository.values(row)
        exported, missing = serialize("planning_document_versions", values, db=db)
        assert not missing
        assert (
            exported["document"]["selected_reporting_proof"]
            == (document.model_dump(mode="json")["selected_reporting_proof"])
        )
        with pytest.raises(ValueError, match="owned snapshot"):
            serialize("planning_document_versions", values)
    monkeypatch.setattr(settings, "customer_export_enabled", True)
    with Session(customer_engine) as db:
        request = begin(
            db,
            principal,
            replicas[2],
            LifecycleInputV1(scope=LifecycleScopeV1(workspace_id=wid), operation="export"),
            "selected-history-export",
            datetime.now(UTC),
        )
        db.commit()
        authority = Authority(customer_engine, principal, replicas[2], wid, request.id)
    authority.claim()
    archive, _ = build(customer_engine, authority, LocalMediaStore(tmp_path / "media"))
    try:
        _, entries = unpack(archive)
        section = next(v for k, v in entries.items() if "planning_document_versions" in k)
        assert b'"selected_reporting_proof"' in section
        assert pid.encode() in section
    finally:
        archive.close()
    with Session(customer_engine) as db, db.begin():
        db.execute(
            delete(PlanDependencyRow).where(
                PlanDependencyRow.workspace_id == wid,
                PlanDependencyRow.plan_id == pid,
                PlanDependencyRow.kind == "local_reporting_v3",
            )
        )
    with Session(customer_engine) as db:
        plan = repository.owned(db, wid, pid)
        with pytest.raises(HTTPException) as error:
            repository.version(db, plan)
        assert error.value.status_code == 409
        with pytest.raises(ValueError):
            serialize("planning_document_versions", values, db=db)
    with Session(customer_engine) as db, db.begin():
        bump_workspace_export_revision(db, wid)
    with Session(customer_engine) as db:
        for model in (PlanRow, PlanInputRow, PlanVersionRow, PlanDependencyRow):
            assert not db.scalar(
                select(func.count()).select_from(model).where(model.workspace_id == wid)
            )
        with pytest.raises(ValueError):
            serialize("planning_document_versions", values, db=db)
    with pytest.raises(HTTPException):
        authority.check()
