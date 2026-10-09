"""Native archives of real offline Meta review and reported-feedback journeys."""

import os
import re
from datetime import datetime
from pathlib import Path

import pytest
from app.lifecycle.contracts import LifecycleScopeV1
from app.lifecycle.inventory import export_section
from app.lifecycle.privacy import bump_workspace_export_revision
from app.workspaces.models import Workspace
from fastapi import HTTPException
from scripts import inlet_restore_drill as drill
from sqlalchemy import Engine, create_engine, func, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from tests.migration_engine import migration_customer_engine as migration_customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_shopify_sales import configuration as configuration


@pytest.fixture
def customer_engine(migration_customer_engine: Engine) -> Engine:
    if migration_customer_engine.dialect.name != "postgresql":
        pytest.skip("native PostgreSQL archive requires PostgreSQL")
    return migration_customer_engine


def roundtrip(engine: Engine) -> None:
    """Only drop the fixture-owned schema after verifying the native server identity."""
    url = drill.target()
    tools = drill.PostgresTools(url, os.environ.get("INLET_RESTORE_POSTGRES_CONTAINER"))
    with engine.connect() as db:
        tools.prove_server(db)
        schema = db.scalar(text("SELECT current_schema()"))
        assert isinstance(schema, str)
        assert re.fullmatch(r"inlet_migration_fixture_[a-f0-9]{32}", schema)
        before = drill.fingerprint(db, schema)
    archive = tools.run("pg_dump", ["--format=custom", "--no-owner", f"--schema={schema}"])
    assert archive.startswith(b"PGDMP") and len(archive) < 20_000_000
    engine.dispose()
    admin = create_engine(url)
    try:
        with admin.begin() as db:
            tools.prove_server(db)
            db.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        tools.run(
            "pg_restore", ["--exit-on-error", "--no-owner", f"--dbname={url.database}"], archive
        )
        with engine.connect() as db:
            assert drill.fingerprint(db, schema) == before
    finally:
        admin.dispose()


def test_native_restore_real_protected_meta_review(
    customer_engine: Engine,
    tmp_path: Path,
) -> None:
    from app.initial_planning.review_models import InitialPreviewReviewLink
    from app.publication.execution_models import ProviderExecutionAttempt, ProviderExecutionReview

    from tests.retired_producer_fixture import retained_review_fixture
    from tests.test_initial_review_lifecycle import exported

    with retained_review_fixture(customer_engine, tmp_path / "seed") as (engine, result):
        with Session(engine) as db:
            original = exported(db, result.review_id)
        roundtrip(engine)
        with Session(engine) as db:
            assert exported(db, result.review_id) == original
            assert not export_section(
                db,
                LifecycleScopeV1(workspace_id=result.workspace_id + 1),
                "initial_preview_reviews",
            )["rows"]
            with pytest.raises(DBAPIError), db.begin_nested():
                db.execute(update(InitialPreviewReviewLink).values(evidence_digest="e" * 64))
            bump_workspace_export_revision(db, result.workspace_id)
            db.commit()
            saved = exported(db, result.review_id)
            assert saved["preview_id"] is None
            assert saved["review_digest"] == original["review_digest"]
            review = db.get(ProviderExecutionReview, result.review_id)
            assert review and review.initial_preview_origin_id == result.preview_id
            assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 1
        assert result.provider_posts == 1


def test_native_restore_real_reported_graph(customer_engine: Engine, tmp_path: Path) -> None:
    from app.customers.models import CustomerSession
    from app.meta.models import MetaConnection
    from app.meta.security import utc
    from app.publication.execution_models import (
        ProviderExecutionReceipt,
        ProviderExposureReservation,
    )
    from app.reported_feedback.models import ReportedActionComparison, ReportedFeedbackSlot
    from app.reported_feedback.service import (
        validate_preview_dependencies,
    )

    from tests.reported_restore_retained_fixture import retained_reported_restore_fixture

    result = retained_reported_restore_fixture(customer_engine, tmp_path / "reported-source")
    wid, source_id, slot_id = result.workspace_id, result.source_id, result.slot_id
    session_id = result.session_digest
    receipt_count, hold_count = result.receipt_count, result.hold_count
    observed_at = datetime.fromisoformat(result.observed_at)
    roundtrip(customer_engine)
    with Session(customer_engine) as db:
        db.scalar(select(Workspace).where(Workspace.id == wid).with_for_update(key_share=True))
        slot = db.get(ReportedFeedbackSlot, slot_id)
        assert slot
        assert validate_preview_dependencies(db, slot, observed_at).digest() == result.slot_digest
        for table in ("reported_feedback_jobs", "reported_feedback_slots"):
            rows = export_section(db, LifecycleScopeV1(workspace_id=wid), table)["rows"]
            assert rows and session_id not in repr(rows)
            assert not export_section(db, LifecycleScopeV1(workspace_id=wid + 1), table)["rows"]
        with pytest.raises(HTTPException):
            validate_preview_dependencies(db, slot, utc(slot.expires_at))
        db.rollback()
        db.scalar(select(Workspace).where(Workspace.id == wid).with_for_update(key_share=True))
        source = db.get(MetaConnection, source_id)
        assert source
        source.generation += 1
        db.flush()
        with pytest.raises(HTTPException):
            validate_preview_dependencies(db, slot, observed_at)
        db.rollback()
        db.scalar(select(Workspace).where(Workspace.id == wid).with_for_update(key_share=True))
        with pytest.raises(DBAPIError), db.begin_nested():
            db.execute(update(ReportedFeedbackSlot).values(document_digest="e" * 64))
        session = db.get(CustomerSession, session_id)
        assert session
        session.revoked_at = 1
        db.flush()
        with pytest.raises(HTTPException):
            validate_preview_dependencies(db, slot, observed_at)
        db.rollback()
        db.scalar(select(Workspace).where(Workspace.id == wid).with_for_update(key_share=True))
        bump_workspace_export_revision(db, wid)
        db.commit()
        assert db.scalar(select(func.count()).select_from(ReportedFeedbackSlot)) == 0
        assert db.scalar(select(func.count()).select_from(ReportedActionComparison)) == 0
        assert (
            db.scalar(select(func.count()).select_from(ProviderExecutionReceipt)) == receipt_count
        )
        assert (
            db.scalar(select(func.count()).select_from(ProviderExposureReservation)) == hold_count
        )
    assert result.provider_posts == 1
