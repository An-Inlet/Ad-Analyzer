"""Current rereads versus mutation epochs; no prepared-currentness optimization."""

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from app.ads.models import Campaign
from app.campaign_performance.range_receipt_models import RangeReceiptRow
from app.campaign_performance.range_receipts import store_range_receipt
from app.campaign_performance.selected_storage import lock_scope
from app.lifecycle.privacy import workspace_export_revision
from app.planning_documents.selected_plan_reader import load_selected_plan_graph
from app.planning_documents.selected_traffic import RawRangeTrafficGraphV1
from app.planning_documents.selected_traffic_reader import load_raw_range_traffic
from fastapi import HTTPException
from sqlalchemy import create_engine, delete, event, func, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from tests.test_selected_customer_api import CustomerFixture
from tests.test_selected_traffic_reader import configured as configured
from tests.test_selected_traffic_reader import customer as customer
from tests.test_selected_traffic_reader import customer_engine as customer_engine
from tests.test_selected_traffic_reader import range_customer as range_customer
from tests.test_selected_traffic_reader import ready
from tests.test_selected_traffic_reader import replicas as replicas


def record(path: Path, **values: Any) -> None:
    path.write_text(json.dumps(values, sort_keys=True) + "\n")


def test_receipt_insert_membership_is_not_privacy_epoch(
    range_customer: CustomerFixture, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    f = range_customer
    contexts, args, _ = ready(f, monkeypatch=monkeypatch)
    with contexts.open() as db:
        original = load_raw_range_traffic(db, **args)
        assert isinstance(original, RawRangeTrafficGraphV1)
        before = workspace_export_revision(db, f.wid)
    second = original.receipt.model_copy(update={"request_id": uuid4().hex})
    with Session(f.engine) as db, db.begin():
        # Actual normal storage writer, not raw insertion bypassing its scope locks.
        store_range_receipt(db, second)
    with contexts.open() as db:
        assert workspace_export_revision(db, f.wid) == before
        count = db.scalar(
            select(func.count())
            .select_from(RangeReceiptRow)
            .where(
                RangeReceiptRow.workspace_id == f.wid,
                RangeReceiptRow.account_id == f.aid,
                RangeReceiptRow.completion_id == original.receipt.completion_id,
            )
        )
        assert count == 2
        with pytest.raises(HTTPException) as error:
            load_raw_range_traffic(db, **args)
        assert error.value.status_code == 409
    with Session(f.engine) as db:
        stored = db.get(RangeReceiptRow, second.request_id)
        assert stored is not None
        before_digest = stored.payload_digest
        with pytest.raises(DBAPIError, match="immutable range receipt"):
            db.execute(
                update(RangeReceiptRow)
                .where(RangeReceiptRow.request_id == second.request_id)
                .values(payload_digest="f" * 64)
            )
        db.rollback()
        unchanged = db.get(RangeReceiptRow, second.request_id, populate_existing=True)
        assert unchanged is not None and unchanged.payload_digest == before_digest
        db.execute(delete(RangeReceiptRow).where(RangeReceiptRow.request_id == second.request_id))
        db.commit()
        after_delete = workspace_export_revision(db, f.wid)
        assert after_delete > before
    with contexts.open() as db:
        with pytest.raises(HTTPException) as error:
            load_raw_range_traffic(db, **args)
        assert error.value.status_code == 409
    record(
        tmp_path / "dependency-contract.json",
        dialect=f.engine.dialect.name,
        contract="receipt_membership",
        normal_writer_insert_count=2,
        insert_privacy_unchanged=True,
        current_reread_refused=True,
        immutable_update_refused=True,
        delete_privacy_advanced=True,
    )


def test_campaign_insert_changes_whole_selected_map(
    range_customer: CustomerFixture, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    f = range_customer
    contexts, args, _ = ready(f, monkeypatch=monkeypatch)
    with contexts.open() as db:
        original = load_raw_range_traffic(db, **args)
        assert isinstance(original, RawRangeTrafficGraphV1)
        before = workspace_export_revision(db, f.wid)
    with Session(f.engine) as db, db.begin():
        account = lock_scope(db, f.wid, f.aid)
        db.add(
            Campaign(
                account_id=f.aid,
                platform=account.platform,
                external_campaign_id="998877",
                name="Synthetic membership probe",
            )
        )
    with contexts.open() as db:
        assert workspace_export_revision(db, f.wid) == before
        current = load_selected_plan_graph(
            db,
            account=args["account"],
            expected_source=args["expected_source"],
            capture_id=args["selected_pin"].capture_id,
        )
        assert current.pin().campaign_map_digest != args["selected_pin"].campaign_map_digest
        assert len(current.campaigns) == len(original.campaigns) + 1
        with pytest.raises(HTTPException) as error:
            load_raw_range_traffic(db, **args)
        assert error.value.status_code == 409
    record(
        tmp_path / "dependency-contract.json",
        dialect=f.engine.dialect.name,
        contract="campaign_membership",
        insert_privacy_unchanged=True,
        complete_map_changed=True,
        current_reread_refused=True,
    )


def test_scope_lock_requires_physical_sqlite_transaction(
    range_customer: CustomerFixture, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    f = range_customer
    contexts, args, _ = ready(f, monkeypatch=monkeypatch)
    with contexts.open() as db:
        original = load_raw_range_traffic(db, **args)
        assert isinstance(original, RawRangeTrafficGraphV1)
    sqlite = f.engine.dialect.name == "sqlite"
    if sqlite:
        path = tmp_path / "independent-connections.sqlite"
        raw = f.engine.raw_connection()
        try:
            source = raw.driver_connection
            assert source is not None
            with closing(sqlite3.connect(path)) as destination:
                source.backup(destination)
        finally:
            raw.close()
        engine = create_engine(
            f"sqlite:///{path}", poolclass=NullPool, connect_args={"timeout": 0.25}
        )

        @event.listens_for(engine, "connect")
        def foreign_keys(connection: Any, _: Any) -> None:
            connection.execute("PRAGMA foreign_keys=ON")
    else:
        engine = f.engine
    ordinary_select_locked = not sqlite
    try:
        if sqlite:
            with Session(engine) as reader, reader.begin():
                lock_scope(reader, f.wid, f.aid)
                connection = reader.connection().connection.driver_connection
                assert connection is not None and connection.in_transaction is False
                with Session(engine) as writer, writer.begin():
                    store_range_receipt(
                        writer, original.receipt.model_copy(update={"request_id": uuid4().hex})
                    )
        with Session(engine) as reader:
            if sqlite:
                reader.execute(text("BEGIN IMMEDIATE"))
                physical = reader.connection().connection.driver_connection
                assert physical is not None and physical.in_transaction
            lock_scope(reader, f.wid, f.aid)
            with Session(engine) as writer:
                if not sqlite:
                    writer.execute(text("SET LOCAL lock_timeout = '250ms'"))
                with pytest.raises(DBAPIError) as error:
                    store_range_receipt(
                        writer, original.receipt.model_copy(update={"request_id": uuid4().hex})
                    )
                if sqlite:
                    assert "database is locked" in str(error.value.orig)
                else:
                    assert getattr(error.value.orig, "sqlstate", None) == "55P03"
                writer.rollback()
            reader.rollback()
        with Session(engine) as writer, writer.begin():
            store_range_receipt(
                writer, original.receipt.model_copy(update={"request_id": uuid4().hex})
            )
    finally:
        if sqlite:
            engine.dispose()
    record(
        tmp_path / "dependency-contract.json",
        dialect=f.engine.dialect.name,
        contract="physical_scope_lock",
        ordinary_select_locks_writer=ordinary_select_locked,
        explicit_scope_fence_blocks_writer=True,
        writer_succeeds_after_release=True,
        production_transaction_changed=False,
    )
