"""Database parent cascades over actual offline published range evidence."""

from typing import Any

import pytest
from app.ads.models import AdvertisingAccount, JobRun
from app.campaign_performance.models import CurrentPerformance, PerformanceCompletion
from app.campaign_performance.presence_models import MetricPresenceRow, ReportingSemanticsRow
from app.campaign_performance.range_receipt_models import RangeReceiptRow
from app.campaign_performance.selected_models import SelectedCaptureRow, SelectedFactRow
from app.lifecycle.privacy import bump_workspace_export_revision, workspace_export_revision
from app.planning_documents.catalog_receipt_models import (
    CatalogReceiptRow,
    CatalogReceiptSelectionRow,
    InputCatalogReceiptRow,
)
from app.planning_documents.models import PlanInputRow, PlanVersionRow
from app.planning_documents.selected_traffic import RawRangeTrafficGraphV1
from app.planning_documents.selected_traffic_reader import load_raw_range_traffic
from fastapi import HTTPException
from sqlalchemy import Engine, delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.migration_engine import migration_customer_engine as migration_customer_engine
from tests.test_catalog_receipt_storage import actual_ddl, seed
from tests.test_selected_customer_api import CustomerFixture
from tests.test_selected_traffic_reader import configured as configured
from tests.test_selected_traffic_reader import customer as customer
from tests.test_selected_traffic_reader import customer_engine as customer_engine
from tests.test_selected_traffic_reader import range_customer as range_customer
from tests.test_selected_traffic_reader import ready
from tests.test_selected_traffic_reader import replicas as replicas

MODELS = (
    RangeReceiptRow,
    CurrentPerformance,
    PerformanceCompletion,
    SelectedCaptureRow,
    SelectedFactRow,
    ReportingSemanticsRow,
    MetricPresenceRow,
)


def counts(db: Session, wid: int) -> dict[str, Any]:
    return {
        model.__tablename__: db.scalar(
            select(func.count()).select_from(model).where(model.workspace_id == wid)
        )
        for model in MODELS
    }


def test_range_parent_cascades_rollback_and_current_reader_refusal(
    range_customer: CustomerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    f = range_customer
    contexts, args, _ = ready(f, monkeypatch=monkeypatch)
    with contexts.open() as db:
        if f.engine.dialect.name == "sqlite":
            assert db.scalar(text("PRAGMA foreign_keys")) == 1
        original = load_raw_range_traffic(db, **args)
        assert isinstance(original, RawRangeTrafficGraphV1)
        before = counts(db, f.wid)
        privacy = workspace_export_revision(db, f.wid)
        completion_id = original.receipt.completion_id
        capture_ids = list(
            db.scalars(
                select(SelectedCaptureRow.id).where(
                    SelectedCaptureRow.workspace_id == f.wid,
                    SelectedCaptureRow.completion_id == completion_id,
                )
            )
        )
        target = {}
        for child in MODELS:
            if child is PerformanceCompletion:
                predicate = child.id == completion_id
            elif child is SelectedFactRow:
                predicate = child.capture_id.in_(capture_ids)
            else:
                predicate = child.__table__.c.completion_id == completion_id
            target[child.__tablename__] = db.scalar(
                select(func.count())
                .select_from(child)
                .where(
                    child.workspace_id == f.wid,
                    predicate,
                )
            )
        assert target[RangeReceiptRow.__tablename__] == 1
        assert target[PerformanceCompletion.__tablename__] == 1
        remaining = {name: before[name] - target[name] for name in before}
    for model, key in (
        (JobRun, original.receipt.job_id),
        (PerformanceCompletion, original.receipt.completion_id),
    ):
        with Session(f.engine) as db:
            # Deliberately direct parent DML: qualifies DB cascades, not a customer
            # deletion endpoint or a blanket normal-writer lock contract.
            db.execute(delete(model).where(model.id == key))
            after = counts(db, f.wid)
            assert after[RangeReceiptRow.__tablename__] == 0
            assert workspace_export_revision(db, f.wid) > privacy
            if model is PerformanceCompletion:
                assert after == remaining
            else:
                for child in MODELS[1:]:
                    assert after[child.__tablename__] == before[child.__tablename__]
            with pytest.raises(HTTPException) as error:
                load_raw_range_traffic(db, **args)
            assert error.value.status_code == 409
            db.rollback()
        with contexts.open() as db:
            assert counts(db, f.wid) == before
            assert workspace_export_revision(db, f.wid) == privacy
            assert load_raw_range_traffic(db, **args) == original
    with Session(f.engine) as db:
        with pytest.raises(IntegrityError) as fk_error:
            db.execute(delete(AdvertisingAccount).where(AdvertisingAccount.id == f.aid))
        if f.engine.dialect.name == "postgresql":
            assert getattr(fk_error.value.orig, "sqlstate", None) == "23503"
        else:
            assert "FOREIGN KEY constraint failed" in str(fk_error.value)
        db.rollback()
        assert counts(db, f.wid) == before
        assert workspace_export_revision(db, f.wid) == privacy
        db.execute(
            delete(PerformanceCompletion).where(
                PerformanceCompletion.id == original.receipt.completion_id
            )
        )
        db.commit()
    with contexts.open() as db:
        assert counts(db, f.wid) == remaining
        assert workspace_export_revision(db, f.wid) > privacy
        with pytest.raises(HTTPException) as error:
            load_raw_range_traffic(db, **args)
        assert error.value.status_code == 409


def test_catalog_parent_restrictions_and_ordered_semantic_erasure(
    migration_customer_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Actual catalog DDL; seeded owned planning graph, not a native observation.
    engine = migration_customer_engine
    actual_ddl(engine, monkeypatch)
    with Session(engine) as db:
        if engine.dialect.name == "sqlite":
            assert db.scalar(text("PRAGMA foreign_keys")) == 1
        first, link = seed(db, 501)
        extra = {**first, "id": "e" * 32, "composite_digest": "e" * 64}
        db.add_all((CatalogReceiptRow(**first), CatalogReceiptRow(**extra)))
        db.flush()
        for index, header in enumerate((first, extra)):
            db.add(
                CatalogReceiptSelectionRow(
                    workspace_id=501,
                    account_id=first["account_id"],
                    selection_key=str(index + 1) * 64,
                    receipt_id=header["id"],
                    connection_id=first["connection_id"],
                    canonical_entity_key="b" * 64,
                )
            )
        db.flush()
        db.add(InputCatalogReceiptRow(**link))
        db.commit()
        privacy = workspace_export_revision(db, 501)
        for statement in (
            delete(CatalogReceiptRow).where(CatalogReceiptRow.id == first["id"]),
            delete(PlanInputRow).where(PlanInputRow.workspace_id == 501),
        ):
            with pytest.raises(IntegrityError) as error, db.begin_nested():
                db.execute(statement)
            if engine.dialect.name == "postgresql":
                assert getattr(error.value.orig, "sqlstate", None) == "23503"
            else:
                assert "FOREIGN KEY constraint failed" in str(error.value)
            assert db.scalar(select(func.count()).select_from(CatalogReceiptRow)) == 2
            assert db.scalar(select(func.count()).select_from(InputCatalogReceiptRow)) == 1
            assert db.scalar(select(func.count()).select_from(PlanInputRow)) == 1
        db.execute(delete(CatalogReceiptRow).where(CatalogReceiptRow.id == extra["id"]))
        assert db.scalar(select(func.count()).select_from(CatalogReceiptSelectionRow)) == 1
        # Catalog delete has no intrinsic privacy epoch: do not infer currentness.
        assert workspace_export_revision(db, 501) == privacy
        db.rollback()
        assert db.scalar(select(func.count()).select_from(CatalogReceiptSelectionRow)) == 2
        bump_workspace_export_revision(db, 501)
        for model in (
            CatalogReceiptRow,
            CatalogReceiptSelectionRow,
            InputCatalogReceiptRow,
            PlanInputRow,
            PlanVersionRow,
        ):
            assert db.scalar(select(func.count()).select_from(model)) == 0
        assert workspace_export_revision(db, 501) > privacy
        db.rollback()
        assert db.scalar(select(func.count()).select_from(CatalogReceiptSelectionRow)) == 2
        assert workspace_export_revision(db, 501) == privacy
        bump_workspace_export_revision(db, 501)
        db.commit()
    with Session(engine) as db:
        for model in (
            CatalogReceiptRow,
            CatalogReceiptSelectionRow,
            InputCatalogReceiptRow,
            PlanInputRow,
            PlanVersionRow,
        ):
            assert db.scalar(select(func.count()).select_from(model)) == 0
        assert workspace_export_revision(db, 501) > privacy
