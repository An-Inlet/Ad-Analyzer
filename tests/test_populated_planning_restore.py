"""Native archives of real offline Meta review and reported-feedback journeys."""

import os
import re
from pathlib import Path
from typing import Any

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
from tests.test_customer_identity import FakeProvider
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
    customer_engine: Engine, configuration: Any, monkeypatch: pytest.MonkeyPatch, replicas: Any
) -> None:
    from app.initial_planning.review_bridge import prepare_preview_review
    from app.initial_planning.review_models import InitialPreviewReviewLink
    from app.publication.execution_models import ProviderExecutionReview

    from tests.test_initial_preview_review import ready
    from tests.test_initial_review_lifecycle import exported

    wid, preview, principal, provider, runtime, server, _ = ready(
        customer_engine, configuration, monkeypatch, replicas
    )
    prepared = prepare_preview_review(
        runtime, principal, provider, wid, preview.id, preview.digest()
    )
    with Session(customer_engine) as db:
        original = exported(db, prepared.review_id)
    roundtrip(customer_engine)
    with Session(customer_engine) as db:
        assert exported(db, prepared.review_id) == original
        assert not export_section(
            db, LifecycleScopeV1(workspace_id=wid + 1), "initial_preview_reviews"
        )["rows"]
        with pytest.raises(DBAPIError), db.begin_nested():
            db.execute(update(InitialPreviewReviewLink).values(evidence_digest="e" * 64))
        bump_workspace_export_revision(db, wid)
        db.commit()
        saved = exported(db, prepared.review_id)
        assert saved["preview_id"] is None
        assert saved["review_digest"] == original["review_digest"]
        review = db.get(ProviderExecutionReview, prepared.review_id)
        assert review and review.initial_preview_origin_id == preview.id
    with pytest.raises(HTTPException):
        prepare_preview_review(runtime, principal, provider, wid, preview.id, preview.digest())
    assert not server.posts


def test_native_restore_real_reported_graph(
    customer_engine: Engine, configuration: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.customers.models import CustomerSession
    from app.meta.models import MetaConnection
    from app.meta.security import utc
    from app.publication.execution_models import (
        ProviderExecutionReceipt,
        ProviderExposureReservation,
    )
    from app.reported_feedback.contracts import FeedbackPreviewIntentV1
    from app.reported_feedback.models import ReportedActionComparison, ReportedFeedbackSlot
    from app.reported_feedback.service import (
        apply_feedback_preview,
        read_comparison,
        validate_preview_dependencies,
    )

    from tests.reported_feedback_journey_fixture import acquired, baseline

    with Session(customer_engine) as db:
        data, runtime, observation = acquired(db, configuration, tmp_path, monkeypatch)
        wid, principal, _, job, _, source, clock, _, _, _, server = data
        source_id = source.id
        runtime, initial = baseline(db, data, runtime, observation)
        comparison = read_comparison(db, principal, FakeProvider(), wid, job.id, runtime)
        assert comparison.status == "operational_reported_as_of"
        result = apply_feedback_preview(
            db,
            principal,
            FakeProvider(),
            wid,
            FeedbackPreviewIntentV1(comparison_id=comparison.id, baseline_preview_id=initial.id),
            runtime,
        )
        db.commit()
        assert result.proposed_budget_micros == 47000000
        slot_id = result.id
        session_id = principal.session.digest
        receipt_count = db.scalar(select(func.count()).select_from(ProviderExecutionReceipt))
        hold_count = db.scalar(select(func.count()).select_from(ProviderExposureReservation))
        assert receipt_count and hold_count
    roundtrip(customer_engine)
    with Session(customer_engine) as db:
        db.scalar(select(Workspace).where(Workspace.id == wid).with_for_update(key_share=True))
        slot = db.get(ReportedFeedbackSlot, slot_id)
        assert slot
        assert validate_preview_dependencies(db, slot, clock[0]).digest() == result.digest()
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
            validate_preview_dependencies(db, slot, clock[0])
        db.rollback()
        db.scalar(select(Workspace).where(Workspace.id == wid).with_for_update(key_share=True))
        with pytest.raises(DBAPIError), db.begin_nested():
            db.execute(update(ReportedFeedbackSlot).values(document_digest="e" * 64))
        session = db.get(CustomerSession, session_id)
        assert session
        session.revoked_at = 1
        db.flush()
        with pytest.raises(HTTPException):
            validate_preview_dependencies(db, slot, clock[0])
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
    assert len(server.posts) == 1
