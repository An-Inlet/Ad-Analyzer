"""0078 real acquired previews, exact pointer constraints and populated DDL."""

import importlib
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.reported_feedback.contracts import FeedbackPreviewIntentV1
from app.reported_feedback.models import ReportedFeedbackCurrent, ReportedFeedbackSlot
from app.reported_feedback.service import apply_feedback_preview, read_comparison
from app.settings import Settings
from sqlalchemy import Engine, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from tests.reported_feedback_journey_fixture import acquired, baseline
from tests.test_customer_identity import FakeProvider
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_shopify_sales import configuration as configuration


@pytest.fixture(autouse=True)
def enforced_foreign_keys(customer_engine: Engine) -> None:
    if customer_engine.dialect.name == "sqlite":
        with customer_engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")


def ready(
    db: Session, configuration: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Any:
    data, runtime, observation = acquired(db, configuration, tmp_path, monkeypatch)
    wid, principal, _, job, *_ = data
    runtime, initial = baseline(db, data, runtime, observation)
    comparison = read_comparison(db, principal, FakeProvider(), wid, job.id, runtime)
    intent = FeedbackPreviewIntentV1(comparison_id=comparison.id, baseline_preview_id=initial.id)
    first = apply_feedback_preview(db, principal, FakeProvider(), wid, intent, runtime)
    db.commit()
    return data, runtime, intent, first


def test_populated0078_roundtrip_preserves_bytes_and_refuses_lossy_history(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = importlib.import_module(
        "migrations.versions.20261007_0078_reported_preview_revisions"
    )
    with Session(customer_engine) as db:
        data, runtime, intent, first = ready(db, configuration, tmp_path, monkeypatch)
        row = db.get(ReportedFeedbackSlot, first.id)
        assert row
        exact = (row.document, row.document_digest, row.revision)
        exact_bytes = db.scalar(
            text("SELECT CAST(document AS TEXT) FROM reported_feedback_slots WHERE id=:id"),
            {"id": first.id},
        )
        actor, session_digest = data[1].user.id, data[1].session.digest
    with (
        customer_engine.begin() as connection,
        Operations.context(MigrationContext.configure(connection)),
    ):
        migration.downgrade()
        migration.upgrade()
    with Session(customer_engine) as db:
        row = db.get(ReportedFeedbackSlot, first.id)
        assert row and (row.document, row.document_digest, row.revision) == exact
        assert (
            db.scalar(
                text("SELECT CAST(document AS TEXT) FROM reported_feedback_slots WHERE id=:id"),
                {"id": first.id},
            )
            == exact_bytes
        )
        pointer = db.scalar(select(ReportedFeedbackCurrent))
        assert pointer and pointer.slot_id == first.id and pointer.revision == exact[2]
        assert runtime.feedback_policy
        changed = replace(
            runtime, feedback_policy=runtime.feedback_policy.model_copy(update={"revision": 2})
        )
        from app.customers.access import CustomerPrincipal
        from app.customers.models import CustomerSession, CustomerUser

        user, session = db.get(CustomerUser, actor), db.get(CustomerSession, session_digest)
        assert user and session
        second = apply_feedback_preview(
            db, CustomerPrincipal(user, session), FakeProvider(), data[0], intent, changed
        )
        db.commit()
        assert second.id != first.id
    with (
        pytest.raises(RuntimeError, match="retained reported feedback revision history"),
        customer_engine.begin() as connection,
        Operations.context(MigrationContext.configure(connection)),
    ):
        migration.downgrade()
    with Session(customer_engine) as db:
        assert db.get(ReportedFeedbackSlot, first.id) and db.get(ReportedFeedbackSlot, second.id)


@pytest.mark.parametrize(
    "mutation",
    [
        "workspace_id=workspace_id+1",
        "revision=revision",
        "revision=revision+2",
        "slot_id='bad', revision=revision+1",
    ],
)
def test_pointer_only_accepts_exact_next_owned_revision(
    mutation: str,
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with Session(customer_engine) as db:
        ready(db, configuration, tmp_path, monkeypatch)
        with pytest.raises(DBAPIError):
            db.execute(text(f"UPDATE reported_feedback_current SET {mutation}"))
        db.rollback()


def test_retained_revision_capacity_fails_before_insert(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.reported_feedback import revisions
    from fastapi import HTTPException

    with Session(customer_engine) as db:
        data, runtime, intent, first = ready(db, configuration, tmp_path, monkeypatch)
        monkeypatch.setattr(revisions, "MAX_RETAINED_REVISIONS", 1)
        assert runtime.feedback_policy
        changed = replace(
            runtime, feedback_policy=runtime.feedback_policy.model_copy(update={"revision": 2})
        )
        with pytest.raises(HTTPException, match="capacity_reached"):
            apply_feedback_preview(db, data[1], FakeProvider(), data[0], intent, changed)
        db.rollback()
        assert list(db.scalars(select(ReportedFeedbackSlot.id))) == [first.id]
        assert db.scalar(select(ReportedFeedbackCurrent.slot_id)) == first.id


@pytest.mark.parametrize("different", [False, True])
def test_concurrent_replacement_serializes_and_exact_retry_reuses_current(
    different: bool,
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from app.customers.access import CustomerPrincipal
    from app.customers.models import CustomerSession, CustomerUser

    if customer_engine.dialect.name != "postgresql":
        pytest.skip("independent concurrent sessions require PostgreSQL")
    with Session(customer_engine) as db:
        data, runtime, intent, first = ready(db, configuration, tmp_path, monkeypatch)
        actor, session_digest = data[1].user.id, data[1].session.digest
    assert runtime.feedback_policy
    barrier = Barrier(2)

    def run(number: int) -> str:
        assert runtime.feedback_policy
        changed = replace(
            runtime, feedback_policy=runtime.feedback_policy.model_copy(update={"revision": number})
        )
        with Session(customer_engine) as db:
            user, session = db.get(CustomerUser, actor), db.get(CustomerSession, session_digest)
            assert user and session
            barrier.wait(timeout=10)
            value = apply_feedback_preview(
                db, CustomerPrincipal(user, session), FakeProvider(), data[0], intent, changed
            )
            db.commit()
            return value.id

    with ThreadPoolExecutor(max_workers=2) as pool:
        one, two = pool.submit(run, 2), pool.submit(run, 3 if different else 2)
        ids = [one.result(timeout=25), two.result(timeout=25)]
    with Session(customer_engine) as db:
        rows = list(
            db.scalars(select(ReportedFeedbackSlot).order_by(ReportedFeedbackSlot.revision))
        )
        pointer = db.scalar(select(ReportedFeedbackCurrent))
        assert pointer and pointer.slot_id == rows[-1].id
        assert [r.revision for r in rows] == list(range(1, 4 if different else 3))
        assert (ids[0] != ids[1]) == different
        assert first.id == rows[0].id


def test_final_authority_failure_rolls_back_revision_and_pointer(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.reported_feedback import revisions
    from fastapi import HTTPException

    with Session(customer_engine) as db:
        data, runtime, intent, first = ready(db, configuration, tmp_path, monkeypatch)
        assert runtime.feedback_policy
        changed = replace(
            runtime, feedback_policy=runtime.feedback_policy.model_copy(update={"revision": 2})
        )
        real_append = revisions.append_revision

        def revoke_after_append(session: Session, saved: ReportedFeedbackSlot) -> None:
            real_append(session, saved)
            data[1].session.revoked_at = 1
            session.flush()

        monkeypatch.setattr(revisions, "append_revision", revoke_after_append)
        with pytest.raises(HTTPException):
            apply_feedback_preview(db, data[1], FakeProvider(), data[0], intent, changed)
        db.rollback()
        assert list(db.scalars(select(ReportedFeedbackSlot.id))) == [first.id]
        assert db.scalar(select(ReportedFeedbackCurrent.slot_id)) == first.id


def test_real_new_unadjusted_baseline_appends_without_compounding(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.initial_planning import preview
    from app.initial_planning.contracts import PreviewIntentV1
    from app.initial_planning.models import PreviewRow
    from app.reported_feedback.service import read_feedback_preview

    with Session(customer_engine) as db:
        data, runtime, intent, first = ready(db, configuration, tmp_path, monkeypatch)
        initial_row = db.get(PreviewRow, first.baseline_preview_id)
        assert initial_row
        original = PreviewIntentV1.model_validate(initial_row.intent)
        db.commit()
        new_initial = preview.prepare_preview(data[1], FakeProvider(), original, runtime.initial)
        assert new_initial.id != first.baseline_preview_id
        new_intent = intent.model_copy(update={"baseline_preview_id": new_initial.id})
        second = apply_feedback_preview(db, data[1], FakeProvider(), data[0], new_intent, runtime)
        db.commit()
        assert second.id != first.id
        assert second.baseline_preview_id == new_initial.id
        assert second.baseline_budget_micros == first.baseline_budget_micros
        assert second.proposed_budget_micros == first.proposed_budget_micros
        assert (
            read_feedback_preview(db, data[1], FakeProvider(), data[0], second.id, runtime)
            == second
        )


def test_downgrade_cannot_reintroduce_a_deleted_current_pointer(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = importlib.import_module(
        "migrations.versions.20261007_0078_reported_preview_revisions"
    )
    with Session(customer_engine) as db:
        _, _, _, first = ready(db, configuration, tmp_path, monkeypatch)
        pointer = db.scalar(select(ReportedFeedbackCurrent))
        assert pointer
        db.delete(pointer)
        db.commit()
    with (
        pytest.raises(RuntimeError, match="missing reported feedback current pointer"),
        customer_engine.begin() as connection,
        Operations.context(MigrationContext.configure(connection)),
    ):
        migration.downgrade()
    with Session(customer_engine) as db:
        assert db.get(ReportedFeedbackSlot, first.id)
        assert db.scalar(select(ReportedFeedbackCurrent.id)) is None
