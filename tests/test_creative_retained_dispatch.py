"""Generic retained-source v5 dispatch, not public generation/runtime activation."""

from datetime import UTC, datetime
from typing import Any

import pytest
from app.ads.models import DailyMetric
from app.billing.models import WorkspaceBilling
from app.campaign_review.models import MediaObject
from app.customers.models import CustomerMembership, CustomerSession
from app.goals.models import Goal
from app.lifecycle.privacy import bump_workspace_export_revision, database_utc_now
from app.planning_documents import creative_retained_sources as combined
from app.planning_documents import retained_sources as retained
from app.planning_documents.creative_history import creative_local_witness
from app.planning_documents.models import PlanDependencyRow
from app.planning_documents.selected_plan_history import validate_selected_plan_history
from app.planning_documents.selected_plan_witnesses import capture_selected_retained_sources
from fastapi import HTTPException
from sqlalchemy import Engine, delete, select, update
from sqlalchemy.orm import Session

from tests.test_creative_currentness import ready as ready
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_shopify_sales import configuration as configuration


def dependencies(db: Session, document: Any) -> tuple[PlanDependencyRow, ...]:
    return tuple(
        db.scalars(
            select(PlanDependencyRow).where(
                PlanDependencyRow.workspace_id == document.inputs.workspace_id,
                PlanDependencyRow.plan_id == document.inputs.plan_id,
                PlanDependencyRow.version == document.version,
            )
        )
    )


@pytest.mark.parametrize("ready", [0, 1, 2], indirect=True)
def test_actual_generic_v5_viewer_unpaid_complete_witnesses(
    customer_engine: Engine,
    ready: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document, store, reader, f = ready
    original = document.model_dump_json(), document.digest()
    with Session(customer_engine) as db, db.begin():
        db.execute(
            update(CustomerMembership)
            .where(CustomerMembership.user_id == reader.principal.user.id)
            .values(role="viewer")
        )
        db.execute(
            update(WorkspaceBilling)
            .where(WorkspaceBilling.workspace_id == f.wid)
            .values(status="canceled")
        )

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("retained SQL must not read bytes/provider or commit")

    monkeypatch.setattr(store, "read_exact", forbidden)
    monkeypatch.setattr(reader.provider, "check_active", forbidden)
    with Session(customer_engine) as db, db.begin():
        monkeypatch.setattr(db, "commit", forbidden)
        saved = dependencies(db, document)
        root, connection = db.get_transaction(), db.connection()
        transaction = connection.get_transaction()
        current = retained.capture_retained_sources(
            db, principal=reader.principal, document=document, now=datetime.now(UTC)
        )
        assert len(current) == len(document.inputs.accounts) + 2
        assert current[-1] == creative_local_witness(document)
        assert current[-2].kind == "local_commerce_v1"
        assert all(x.kind == "local_reporting_v3" for x in current[:-2])
        retained.recheck_retained_sources(
            db,
            principal=reader.principal,
            document=document,
            dependencies=saved,
            now=datetime.now(UTC),
        )
        validate_selected_plan_history(db, document)
        assert db.get_transaction() is root and connection.get_transaction() is transaction
        assert original == (document.model_dump_json(), document.digest())
        assert not db.new and not db.dirty and not db.deleted
        with pytest.raises(retained.RetainedSourcesChanged, match="proof_unavailable"):
            capture_selected_retained_sources(
                db, principal=reader.principal, document=document, now=datetime.now(UTC)
            )


def test_complete_set_refuses_every_missing_or_extra_dependency(
    customer_engine: Engine,
    ready: Any,
) -> None:
    document, _, reader, _ = ready
    with Session(customer_engine) as db, db.begin():
        original = dependencies(db, document)
        sets = [tuple(row for row in original if row is not missing) for missing in original]
        sets += [(*original, original[-1])]
        values = {c.name: getattr(original[-1], c.name) for c in original[-1].__table__.columns}
        values["evidence_key"] = "unknown:extra"
        sets += [(*original, PlanDependencyRow(**values))]
        for changed in sets:
            with pytest.raises(retained.RetainedSourcesChanged, match="proof_unavailable"):
                retained.recheck_retained_sources(
                    db,
                    principal=reader.principal,
                    document=document,
                    dependencies=changed,
                    now=datetime.now(UTC),
                )


@pytest.mark.parametrize("change", ["image", "reporting", "goal", "privacy", "session"])
def test_actual_current_sources_block_generic_recheck(
    customer_engine: Engine,
    ready: Any,
    change: str,
) -> None:
    document, _, reader, f = ready
    with Session(customer_engine) as db, db.begin():
        saved = tuple(
            PlanDependencyRow(**{c.name: getattr(row, c.name) for c in row.__table__.columns})
            for row in dependencies(db, document)
        )
        if change == "image":
            db.execute(delete(MediaObject).where(MediaObject.workspace_id == f.wid))
        elif change == "reporting":
            db.execute(update(DailyMetric).values(clicks=DailyMetric.clicks + 1))
        elif change == "goal":
            db.execute(
                update(Goal)
                .where(Goal.id == document.inputs.goal.goal_id)
                .values(confirmed_preview_id=None)
            )
        elif change == "privacy":
            bump_workspace_export_revision(db, f.wid)
        else:
            db.execute(
                update(CustomerSession)
                .where(CustomerSession.digest == reader.principal.session.digest)
                .values(revoked_at=1)
            )
    with Session(customer_engine) as db, db.begin():
        expected = HTTPException if change == "session" else retained.RetainedSourcesChanged
        with pytest.raises(expected):
            retained.recheck_retained_sources(
                db,
                principal=reader.principal,
                document=document,
                dependencies=saved,
                now=datetime.now(UTC),
            )
        if change == "image":
            validate_selected_plan_history(db, document)


def test_root_clean_preflight_and_delegated_error_boundaries(
    customer_engine: Engine,
    ready: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document, _, reader, f = ready
    with Session(customer_engine) as db:
        original = tuple(
            PlanDependencyRow(**{c.name: getattr(row, c.name) for c in row.__table__.columns})
            for row in dependencies(db, document)
        )
    for attack in (
        "no_root",
        "dirty",
        "nested",
        "rollback",
        "connection",
        "runtime",
        "validation",
        "http",
    ):
        with Session(customer_engine) as db, monkeypatch.context() as patch:
            if attack != "no_root":
                db.begin()
            if attack == "dirty":
                row = db.scalar(select(MediaObject).where(MediaObject.workspace_id == f.wid))
                assert row is not None
                row.width = 2
            elif attack == "nested":
                db.begin_nested()
            if attack in {"rollback", "connection", "runtime", "validation", "http"}:

                def failure(*args: Any, _attack: str = attack, **kwargs: Any) -> Any:
                    if _attack == "runtime":
                        raise RuntimeError("delegate failure")
                    if _attack == "validation":
                        raise ValueError("invalid delegate proof")
                    if _attack == "http":
                        raise HTTPException(403, "revoked")
                    if _attack == "rollback":
                        db.rollback()
                        db.begin()
                    else:
                        connection = db.connection()
                        connection.rollback()
                        connection.begin()
                    return ()

                patch.setattr(combined, "capture_selected_reporting_sources", failure)
            expected = (
                RuntimeError
                if attack == "runtime"
                else HTTPException
                if attack == "http"
                else retained.RetainedSourcesChanged
            )
            with pytest.raises(expected):
                retained.recheck_retained_sources(
                    db,
                    principal=reader.principal,
                    document=document,
                    dependencies=original,
                    now=datetime.now(UTC),
                )
            db.rollback()
    with Session(customer_engine) as db:
        row = db.scalar(select(MediaObject).where(MediaObject.workspace_id == f.wid))
        assert row is not None and row.width == 4


def test_final_database_clock_cannot_replace_connection_transaction(
    customer_engine: Engine,
    ready: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document, _, reader, _ = ready
    original = database_utc_now
    calls = 0

    def clock(db: Session) -> datetime:
        nonlocal calls
        calls += 1
        value = original(db)
        if calls == 6:
            connection = db.connection()
            connection.rollback()
            connection.begin()
        return value

    monkeypatch.setattr(combined, "database_utc_now", clock)
    with Session(customer_engine) as db:
        db.begin()
        with pytest.raises(retained.RetainedSourcesChanged, match="source_changed"):
            retained.capture_retained_sources(
                db, principal=reader.principal, document=document, now=datetime.now(UTC)
            )
        assert calls == 6
        db.rollback()
