"""0092 storage over actual Google aggregate HTTP; dedicated range-job metadata fixture.

This does not claim the range publisher or a 61-day customer API acquisition.
"""

import importlib
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.ads.enums import AdvertisingPlatform, JobRunStatus
from app.ads.models import AdvertisingAccount, Campaign, DailyMetric, JobRun
from app.campaign_performance.models import CurrentPerformance, PerformanceCompletion
from app.campaign_performance.range_receipt_models import RangeReceiptRow
from app.campaign_performance.range_receipts import (
    RangeReceiptV1,
    export_range_receipt,
    read_range_receipt,
    store_range_receipt,
    values,
)
from app.campaign_performance.selected_contracts import ReportingScopeV1
from app.campaign_performance.selected_storage import SelectedReportingUnavailable
from app.campaign_review.storage import LocalMediaStore
from app.customers.access import CustomerPrincipal
from app.customers.models import CustomerSession, CustomerUser
from app.database.session import Base
from app.google_connections.models import GoogleCustomerConnection
from app.lifecycle.contracts import LifecycleInputV1, LifecycleScopeV1
from app.lifecycle.exports import Authority
from app.lifecycle.privacy import bump_workspace_export_revision, workspace_export_revision
from app.lifecycle.service import begin
from app.settings import settings
from app.shopify.security import utc
from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from tests.test_customer_exports import build, unpack
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_google_customer_connections import configured as configured
from tests.test_selected_customer_api import CustomerFixture
from tests.test_selected_customer_api import customer as customer


def ready(db: Session, f: CustomerFixture) -> RangeReceiptV1:
    current = db.get(CurrentPerformance, f.aid)
    assert current
    completion = db.get(PerformanceCompletion, current.completion_id)
    source = db.get(GoogleCustomerConnection, f.source_id)
    account = db.get(AdvertisingAccount, f.aid)
    assert completion and source and account
    scope = ReportingScopeV1(
        workspace_id=f.wid,
        account_id=f.aid,
        connection_id=account.connection_id,
        platform="google_ads",
        source_connection_ref=source.id,
        generation=source.generation,
        privacy_revision=completion.privacy_revision,
        native_account_id=account.external_account_id,
        currency=account.currency_code,
        time_zone=account.time_zone,
    )
    # Dedicated job metadata is scoped here; atomic creation by the actual range
    # publisher is a separate acceptance test, not manufactured by this storage port.
    job = JobRun(
        workspace_id=f.wid,
        account_id=f.aid,
        connection_id=account.connection_id,
        platform=AdvertisingPlatform.GOOGLE_ADS,
        status=JobRunStatus.SUCCEEDED,
        job_name="google_customer_range_read",
        started_at=completion.completed_at,
        finished_at=completion.completed_at,
        records_processed=completion.row_count,
    )
    db.add(job)
    db.flush()
    return RangeReceiptV1(
        request_id=uuid4().hex,
        initiating_customer_id=f.actor,
        requested_starts_on=completion.starts_on,
        requested_ends_on=completion.ends_on,
        original_scope=scope,
        final_scope=scope,
        completion_id=completion.id,
        manifest_digest=completion.manifest_digest,
        query_version=completion.query_version,
        completed_at=utc(completion.completed_at),
        row_count=completion.row_count,
        acquisition_digest="a" * 64,
        job_id=job.id,
    )


def test_owned_store_retry_current_history_and_immutable(customer: CustomerFixture) -> None:
    f = customer
    with Session(f.engine) as db:
        receipt = ready(db, f)
        store_range_receipt(db, receipt)
        db.commit()
        store_range_receipt(db, receipt)
        assert read_range_receipt(db, f.wid, f.aid, receipt.request_id) == receipt
        with pytest.raises(SelectedReportingUnavailable):
            read_range_receipt(db, f.wid + 1, f.aid, receipt.request_id)
        with pytest.raises(SelectedReportingUnavailable, match="replay"):
            store_range_receipt(db, receipt.model_copy(update={"acquisition_digest": "b" * 64}))
        db.rollback()
        with pytest.raises(DBAPIError):
            db.execute(update(RangeReceiptRow).values(payload_digest="f" * 64))
        db.rollback()
        metric = db.scalar(select(DailyMetric).join(Campaign).where(Campaign.account_id == f.aid))
        assert metric
        metric.cost_micros += 1
        db.commit()
        assert read_range_receipt(db, f.wid, f.aid, receipt.request_id, False) == receipt
        with pytest.raises((SelectedReportingUnavailable, HTTPException)):
            read_range_receipt(db, f.wid, f.aid, receipt.request_id)
        assert export_range_receipt(db, values(receipt))["currentness"] == "historical_as_observed"


@pytest.mark.parametrize(
    "kind", ["job_name", "job_status", "completion_rows", "completion_time", "foreign_job"]
)
def test_actual_raw_insert_dependency_binding(customer: CustomerFixture, kind: str) -> None:
    f = customer
    with Session(f.engine) as db:
        receipt = ready(db, f)
        if kind == "job_name":
            job = db.get(JobRun, receipt.job_id)
            assert job
            job.job_name = "google_customer_fixture_sync"
        elif kind == "job_status":
            job = db.get(JobRun, receipt.job_id)
            assert job
            job.status = JobRunStatus.FAILED
        elif kind == "foreign_job":
            receipt = receipt.model_copy(update={"job_id": 999999})
        elif kind == "completion_rows":
            receipt = receipt.model_copy(update={"row_count": receipt.row_count + 1})
        else:
            from datetime import timedelta

            receipt = receipt.model_copy(
                update={"completed_at": receipt.completed_at + timedelta(seconds=1)}
            )
        db.flush()
        db.add(RangeReceiptRow(**values(receipt)))
        with pytest.raises(DBAPIError):
            db.flush()
        db.rollback()
        assert db.get(RangeReceiptRow, receipt.request_id) is None


def test_actual_archive_raw_erasure_and_semantic_privacy(
    customer: CustomerFixture, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    f = customer
    monkeypatch.setattr(settings, "customer_export_enabled", True)
    with Session(f.engine) as db:
        receipt = ready(db, f)
        store_range_receipt(db, receipt)
        db.commit()
        user = db.get(CustomerUser, f.actor)
        session = db.get(CustomerSession, f.sid)
        assert user and session
        principal = CustomerPrincipal(user, session)
        request = begin(
            db,
            principal,
            f.provider,
            LifecycleInputV1(scope=LifecycleScopeV1(workspace_id=f.wid), operation="export"),
            "range-receipt-export-001",
            datetime.now(UTC),
        )
        db.commit()
        authority = Authority(f.engine, principal, f.provider, f.wid, request.id)
    authority.claim()
    output, manifest = build(f.engine, authority, LocalMediaStore(tmp_path / "media"))
    try:
        _, entries = unpack(output)
        assert manifest["supported_customer_data_complete"] is True
        assert b"historical_as_observed" in entries["data/google_reporting_range_receipts.jsonl"]
    finally:
        output.close()
    with Session(f.engine) as db:
        before = workspace_export_revision(db, f.wid)
        db.execute(delete(RangeReceiptRow).where(RangeReceiptRow.request_id == receipt.request_id))
        db.commit()
        assert workspace_export_revision(db, f.wid) > before
    with pytest.raises(HTTPException, match="invalidated"):
        authority.check()
    # Independent fresh fixture acquisition after erasure is required, not restamping.
    f.refresh()
    with Session(f.engine) as db:
        second = ready(db, f)
        store_range_receipt(db, second)
        db.commit()
        bump_workspace_export_revision(db, f.wid)
        db.commit()
        assert db.get(RangeReceiptRow, second.request_id) is None


def test_actual0092_metadata_parity_and_populated_downgrade(customer: CustomerFixture) -> None:
    from app.campaign_performance.range_receipt_triggers import statements
    from sqlalchemy.schema import CreateTable

    f = customer
    migration = importlib.import_module("migrations.versions.20261011_0092_google_range_receipts")
    expected = (
        str(CreateTable(Base.metadata.tables[RangeReceiptRow.__tablename__]).compile(dialect=f.engine.dialect)),
        *statements(f.engine.dialect.name),
    )
    assert migration.SQL[f.engine.dialect.name] == expected
    Base.metadata.tables[RangeReceiptRow.__tablename__].drop(f.engine)
    with (
        f.engine.begin() as connection,
        Operations.context(MigrationContext.configure(connection)),
    ):
        migration.upgrade()
    with Session(f.engine) as db:
        receipt = ready(db, f)
        store_range_receipt(db, receipt)
        db.commit()
    with (
        f.engine.begin() as connection,
        Operations.context(MigrationContext.configure(connection)),
        pytest.raises(RuntimeError, match="erased"),
    ):
        migration.downgrade()
    with Session(f.engine) as db:
        assert read_range_receipt(db, f.wid, f.aid, receipt.request_id) == receipt
        db.execute(delete(RangeReceiptRow))
        db.commit()
    with (
        f.engine.begin() as connection,
        Operations.context(MigrationContext.configure(connection)),
    ):
        migration.downgrade()
        migration.upgrade()


@pytest.mark.parametrize(
    ("field", "bad"),
    [("selected_event", "purchase"), ("semantics", "changed"), ("reporting_basis", "changed")],
)
def test_historical_metadata_semantics_and_insert_binding(
    customer: CustomerFixture, field: str, bad: str
) -> None:
    # Metadata-created schema permits adversarial completion mutation; the deployed
    # 0074 immutable trigger is an additional defense, not a reader assumption.
    f = customer
    with Session(f.engine) as db:
        receipt = ready(db, f)
        store_range_receipt(db, receipt)
        db.commit()
        db.execute(
            update(PerformanceCompletion)
            .where(PerformanceCompletion.id == receipt.completion_id)
            .values({field: bad})
        )
        db.flush()
        with pytest.raises(SelectedReportingUnavailable, match="dependency"):
            read_range_receipt(db, f.wid, f.aid, receipt.request_id, False)
        with pytest.raises(SelectedReportingUnavailable, match="dependency"):
            export_range_receipt(db, values(receipt))
        replacement = receipt.model_copy(update={"request_id": uuid4().hex})
        db.add(RangeReceiptRow(**values(replacement)))
        with pytest.raises(DBAPIError):
            db.flush()
        db.rollback()
        assert read_range_receipt(db, f.wid, f.aid, receipt.request_id) == receipt
        assert db.get(RangeReceiptRow, replacement.request_id) is None
