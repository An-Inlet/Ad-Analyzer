"""Owned erasure graphs, strict serializers and preserved original financial evidence."""

import json
from typing import Any

import pytest
from app.initial_planning.invalidation import invalidate_account_calibrations
from app.lifecycle.export_serializers import serialize
from app.lifecycle.privacy import bump_workspace_export_revision, workspace_export_revision
from app.publication.execution_models import ProviderExecutionReceipt, ProviderExposureReservation
from app.reported_feedback.models import (
    ReportedActionComparison,
    ReportedComparisonDependency,
    ReportedFeedbackJob,
    ReportedFeedbackSlot,
    ReportedWindowCapsule,
)
from sqlalchemy import Engine, delete, select, text
from sqlalchemy.orm import Session

from tests.reported_feedback_lifecycle_fixture import graph
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_shopify_sales import configuration as configuration

MODELS = (
    ReportedFeedbackJob,
    ReportedWindowCapsule,
    ReportedActionComparison,
    ReportedComparisonDependency,
    ReportedFeedbackSlot,
)


@pytest.fixture(autouse=True)
def foreign_keys(customer_engine: Engine) -> None:
    if customer_engine.dialect.name == "sqlite":
        with customer_engine.connect() as connection:
            connection.execute(text("PRAGMA foreign_keys=ON"))
            connection.commit()


@pytest.mark.parametrize(
    "erase", ["other_comparison", "dependency", "capsule", "privacy", "correction"]
)
def test_cross_contributor_erasure_retracts_numeric_slot_and_preserves_finance(
    customer_engine: Engine,
    configuration: Any,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    erase: str,
) -> None:
    data = graph(customer_engine, configuration, monkeypatch, replicas)
    with Session(customer_engine) as db:
        db.execute(text("SELECT id FROM workspaces WHERE id=:wid"), {"wid": data["wid"]})
        before = workspace_export_revision(db, data["wid"])
        if erase == "other_comparison":
            db.execute(
                delete(ReportedActionComparison).where(
                    ReportedActionComparison.id == data["comparisons"][1]
                )
            )
        elif erase == "dependency":
            db.execute(
                delete(ReportedComparisonDependency).where(
                    ReportedComparisonDependency.comparison_id == data["comparisons"][1]
                )
            )
        elif erase == "capsule":
            db.execute(
                delete(ReportedWindowCapsule).where(ReportedWindowCapsule.id == data["capsule"])
            )
        elif erase == "correction":
            invalidate_account_calibrations(db, data["wid"], data["account"])
        else:
            db.execute(
                text("UPDATE workspaces SET status='closing' WHERE id=:wid"), {"wid": data["wid"]}
            )
            bump_workspace_export_revision(db, data["wid"])
        db.commit()
        assert db.get(ReportedFeedbackSlot, data["slot"]) is None
        assert workspace_export_revision(db, data["wid"]) > before
        assert db.get(ProviderExecutionReceipt, data["receipt"])
        assert db.scalar(
            select(ProviderExposureReservation.id).where(
                ProviderExposureReservation.workspace_id == data["wid"],
                ProviderExposureReservation.state == "held",
            )
        )
        if erase == "privacy":
            for model in MODELS:
                assert not list(db.scalars(select(model).where(model.workspace_id == data["wid"])))
        elif erase == "correction":
            assert db.get(ReportedFeedbackJob, data["job"])
            assert db.get(ReportedWindowCapsule, data["capsule"])


def test_owned_strict_exports_hide_session_and_reject_scope_forgery(
    customer_engine: Engine,
    configuration: Any,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
) -> None:
    data = graph(customer_engine, configuration, monkeypatch, replicas)
    with Session(customer_engine) as db:
        for model in MODELS:
            for row in db.scalars(select(model).where(model.workspace_id == data["wid"])):
                raw = {col.name: getattr(row, col.name) for col in model.__table__.columns}
                output, missing = serialize(model.__tablename__, raw)
                assert not missing
                assert "original_session_digest" not in output
                assert data["session"] not in json.dumps(output, default=str)
                if "document" in raw:
                    assert output["document"] == raw["document"]
                    _, missing = serialize(model.__tablename__, {**raw, "workspace_id": 999999})
                    assert "document" in missing
                    _, missing = serialize(
                        model.__tablename__, {**raw, "document_digest": "0" * 64}
                    )
                    assert "document" in missing


def test_persisted_expiry_prunes_request_with_capture_off_and_workspace_closing(
    customer_engine: Engine,
    configuration: Any,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
) -> None:
    from datetime import timedelta

    from app.reported_feedback.contracts import ReportedWindowCapsuleV1
    from app.reported_feedback.retention import purge_expired_feedback
    from app.reported_feedback.runtime import get_reported_feedback_runtime

    data = graph(customer_engine, configuration, monkeypatch, replicas)
    assert get_reported_feedback_runtime() is None
    # Ahead application time alone must not qualify for DB-expired deletion.
    assert (
        purge_expired_feedback(
            lambda: Session(customer_engine), clock=lambda: data["now"] + timedelta(days=2)
        )
        == 0
    )
    with Session(customer_engine) as db:
        capsule = db.get(ReportedWindowCapsule, data["capsule"])
        assert capsule
        raw = {col.name: getattr(capsule, col.name) for col in capsule.__table__.columns}
        document = ReportedWindowCapsuleV1.model_validate(raw["document"])
        past = data["now"] - timedelta(hours=2)
        document = ReportedWindowCapsuleV1.model_validate(
            document.model_copy(
                update={
                    "acquisition_started_at": past,
                    "acquisition_completed_at": past,
                    "captured_at": past,
                    "expires_at": past + timedelta(hours=1),
                }
            ).model_dump()
        )
        db.delete(capsule)
        db.flush()
        db.add(
            ReportedWindowCapsule(
                **{
                    **raw,
                    "document": document.model_dump(mode="json"),
                    "document_digest": document.digest(),
                    "expires_at": document.expires_at,
                    "acquisition_started_at": past,
                    "acquisition_completed_at": past,
                    "captured_at": past,
                }
            )
        )
        db.execute(
            text("UPDATE workspaces SET status='closing' WHERE id=:wid"), {"wid": data["wid"]}
        )
        db.commit()
    assert purge_expired_feedback(lambda: Session(customer_engine)) == 1
    with Session(customer_engine) as db:
        for model in MODELS:
            assert not list(db.scalars(select(model).where(model.workspace_id == data["wid"])))
        assert db.get(ProviderExecutionReceipt, data["receipt"])
    assert purge_expired_feedback(lambda: Session(customer_engine)) == 0


def test_actual_0077_graph_triggers_and_foreign_parent_constraints(
    customer_engine: Engine,
    configuration: Any,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
) -> None:
    import importlib
    from uuid import uuid4

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from app.workspaces.models import Workspace
    from sqlalchemy import insert
    from sqlalchemy.exc import DBAPIError, IntegrityError

    migration = importlib.import_module("migrations.versions.20261006_0077_reported_feedback")
    revisions = importlib.import_module(
        "migrations.versions.20261007_0078_reported_preview_revisions"
    )
    rules = importlib.import_module("migrations.versions.20261007_0083_reported_rule_dependencies")
    with (
        customer_engine.begin() as connection,
        Operations.context(MigrationContext.configure(connection)),
    ):
        rules.downgrade()
        revisions.downgrade()
        migration.downgrade()
        migration.upgrade()
        revisions.upgrade()
        rules.upgrade()
    data = graph(customer_engine, configuration, monkeypatch, replicas)
    with Session(customer_engine) as db:
        for model in MODELS:
            with pytest.raises(DBAPIError, match="immutable reported feedback"):
                db.execute(text(f"UPDATE {model.__tablename__} SET workspace_id=workspace_id+1"))
            db.rollback()
        job = db.get(ReportedFeedbackJob, data["job"])
        assert job
        job.state = "waiting"
        db.commit()  # Progress updates remain possible without rewriting original input.
        other = Workspace(name="Unrelated", client_name="Unrelated", slug="unrelated-rf")
        db.add(other)
        db.commit()
        original = db.get(ReportedWindowCapsule, data["capsule"])
        assert original
        raw = {col.name: getattr(original, col.name) for col in original.__table__.columns}
        with pytest.raises(IntegrityError):
            db.execute(
                insert(ReportedWindowCapsule).values(
                    **{**raw, "id": uuid4().hex, "workspace_id": other.id, "environment": "live"}
                )
            )
        db.rollback()
        before = workspace_export_revision(db, other.id)
        db.execute(
            delete(ReportedComparisonDependency).where(
                ReportedComparisonDependency.comparison_id == data["comparisons"][1]
            )
        )
        db.commit()
        assert db.get(ReportedActionComparison, data["comparisons"][1]) is None
        assert db.get(ReportedActionComparison, data["comparisons"][0])
        assert db.get(ReportedFeedbackSlot, data["slot"]) is None
        assert workspace_export_revision(db, other.id) == before
        assert db.get(ProviderExecutionReceipt, data["receipt"])


def test_raw_erasure_fails_fast_behind_workspace_fence(
    customer_engine: Engine,
    configuration: Any,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
) -> None:
    from sqlalchemy.exc import DBAPIError

    if customer_engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL workspace row lock")
    data = graph(customer_engine, configuration, monkeypatch, replicas)
    with customer_engine.connect() as owner, customer_engine.connect() as eraser:
        owner.execute(
            text("SELECT id FROM workspaces WHERE id=:wid FOR UPDATE"), {"wid": data["wid"]}
        )
        eraser.execute(text("SET LOCAL statement_timeout='1000ms'"))
        with pytest.raises(DBAPIError) as caught:
            eraser.execute(
                text("DELETE FROM reported_action_comparisons WHERE id=:id"),
                {"id": data["comparisons"][1]},
            )
        assert getattr(caught.value.orig, "sqlstate", None) == "55P03"
        eraser.rollback()
        owner.rollback()
    with Session(customer_engine) as db:
        assert db.get(ReportedFeedbackSlot, data["slot"])
        assert db.get(ProviderExecutionReceipt, data["receipt"])
