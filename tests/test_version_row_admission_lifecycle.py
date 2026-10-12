"""Real retained row fallback and local admission lifecycle; no clock substitutions."""

from typing import Any

import pytest
from app.planning_documents import repository
from app.planning_documents import version_row_admission as admission
from app.planning_documents.documents import PlanVersion
from app.planning_documents.models import PlanVersionRow
from app.planning_documents.storage import document_for_row
from sqlalchemy import Engine, event, select
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_owner_review_retained_dispatch import ready as ready
from tests.test_shopify_sales import configuration as configuration


def _closed(db: Session, proof: Any) -> None:
    assert proof.consumed and proof.row is None and proof.document is None
    assert proof.db is None and proof.connection is None and proof.root is None
    assert proof.transaction is None
    assert proof.permitted_statement is None and not proof.permit_active
    assert not event.contains(db, "before_flush", proof.invalidate)
    assert not event.contains(db, "do_orm_execute", proof.orm_read)


@pytest.mark.parametrize("fault", ["none", "document", "row", "orm_read", "nested"])
def test_real_row_match_or_original_fallback(
    customer_engine: Engine, ready: Any, fault: str
) -> None:
    expected, _, _, _ = ready
    with Session(customer_engine) as db, db.begin():
        stored = db.get(
            PlanVersionRow,
            (expected.inputs.workspace_id, expected.inputs.plan_id, expected.version),
        )
        assert stored is not None
        initial = repository.values(stored)
        document = document_for_row("planning_document_versions", initial)
        assert isinstance(document, PlanVersion)
        proof = admission._make_version_row_admission(db=db, row=initial, document=document)
        assert proof is not None
        # The mapped predicates mark this Select ORM-aware. Permit exactly this
        # original statement once, matching the production second-read boundary.
        statement = select(PlanVersionRow.__table__).where(
            PlanVersionRow.workspace_id == expected.inputs.workspace_id,
            PlanVersionRow.plan_id == expected.inputs.plan_id,
            PlanVersionRow.version == expected.version,
        )
        with proof.reading_statement(statement):
            result = db.execute(statement)
        fresh = dict(result.mappings().one())
        nested = None
        if fault == "document":
            object.__setattr__(document, "__pydantic_private__", {})
        elif fault == "row":
            fresh["digest"] = "0" * 64
        elif fault == "orm_read":
            db.execute(select(PlanVersionRow)).scalars().all()
        elif fault == "nested":
            nested = db.begin_nested()
        matched = admission._matches_admitted_version_row(
            db=db, row=fresh, document=document, admission=proof
        )
        _closed(db, proof)
        if nested is not None:
            nested.rollback()
        if fault == "none":
            assert matched is True
        else:
            assert matched is None
            if fault == "row":
                with pytest.raises(ValueError):
                    document_for_row("planning_document_versions", fresh)
            else:
                decoded = document_for_row("planning_document_versions", fresh)
                assert (decoded == document) is (fault != "document")
        assert (
            admission._matches_admitted_version_row(
                db=db, row=fresh, document=document, admission=proof
            )
            is None
        )
        _closed(db, proof)


@pytest.mark.parametrize("install_second", [False, True])
def test_partial_listener_setup_preserves_error_and_removes_registered_listeners(
    customer_engine: Engine, ready: Any, monkeypatch: pytest.MonkeyPatch, install_second: bool
) -> None:
    expected, _, _, _ = ready
    original_listen = event.listen
    callbacks: list[tuple[Any, str, Any]] = []
    failure = RuntimeError("controlled second-listener setup failure")

    def listen(target: Any, name: str, callback: Any, *args: Any, **kwargs: Any) -> None:
        if name == "do_orm_execute":
            if install_second:
                original_listen(target, name, callback, *args, **kwargs)
                callbacks.append((target, name, callback))
            raise failure
        original_listen(target, name, callback, *args, **kwargs)
        callbacks.append((target, name, callback))

    with Session(customer_engine) as db, db.begin():
        row = db.get(
            PlanVersionRow,
            (expected.inputs.workspace_id, expected.inputs.plan_id, expected.version),
        )
        assert row is not None
        raw = repository.values(row)
        document = document_for_row("planning_document_versions", raw)
        assert isinstance(document, PlanVersion)
        monkeypatch.setattr(event, "listen", listen)
        with pytest.raises(RuntimeError) as error:
            admission._make_version_row_admission(db=db, row=raw, document=document)
        assert error.value is failure
        assert len(callbacks) == (2 if install_second else 1)
        for target, name, callback in callbacks:
            assert not event.contains(target, name, callback)


@pytest.mark.parametrize("fault", ["flush", "root", "connection", "matcher_error"])
def test_completed_scope_fault_or_exception_closes_local_proof(
    customer_engine: Engine, ready: Any, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    from app.planning_documents.models import PlanRow

    expected, _, _, _ = ready
    with Session(customer_engine) as db:
        db.begin()
        row = db.get(
            PlanVersionRow,
            (expected.inputs.workspace_id, expected.inputs.plan_id, expected.version),
        )
        assert row is not None
        raw = repository.values(row)
        document = document_for_row("planning_document_versions", raw)
        assert isinstance(document, PlanVersion)
        plan = db.get(PlanRow, (expected.inputs.workspace_id, expected.inputs.plan_id))
        assert plan is not None
        proof = admission._make_version_row_admission(db=db, row=raw, document=document)
        assert proof is not None
        failure = RuntimeError("controlled matcher snapshot failure")
        if fault == "flush":
            plan.event_sequence += 1
            db.flush()
            assert not db.new and not db.dirty and not db.deleted
        elif fault == "root":
            db.rollback()
            db.begin()
        elif fault == "connection":
            connection = db.connection()
            connection.rollback()
            connection.begin()
        else:

            def fail(*args: Any, **kwargs: Any) -> Any:
                raise failure

            monkeypatch.setattr(admission, "_snapshot_row", fail)
        if fault == "matcher_error":
            with pytest.raises(RuntimeError) as error:
                admission._matches_admitted_version_row(
                    db=db, row=raw, document=document, admission=proof
                )
            assert error.value is failure
        else:
            assert (
                admission._matches_admitted_version_row(
                    db=db, row=raw, document=document, admission=proof
                )
                is None
            )
            # Scope invalidation declines optimization, not original decoding.
            assert document_for_row("planning_document_versions", raw) == document
        _closed(db, proof)
        db.rollback()


@pytest.mark.parametrize("event_name", ["before_flush", "do_orm_execute"])
def test_preexisting_listener_declines_without_removing_original_listener(
    customer_engine: Engine, ready: Any, event_name: str
) -> None:
    expected, _, _, _ = ready
    with Session(customer_engine) as db, db.begin():
        row = db.get(
            PlanVersionRow,
            (expected.inputs.workspace_id, expected.inputs.plan_id, expected.version),
        )
        assert row is not None
        raw = repository.values(row)
        document = document_for_row("planning_document_versions", raw)
        assert isinstance(document, PlanVersion)

        def listener(*args: Any, **kwargs: Any) -> None:
            return None

        event.listen(db, event_name, listener)
        try:
            assert admission._make_version_row_admission(db=db, row=raw, document=document) is None
            assert event.contains(db, event_name, listener)
            assert document_for_row("planning_document_versions", raw) == document
        finally:
            event.remove(db, event_name, listener)
        proof = admission._make_version_row_admission(db=db, row=raw, document=document)
        assert proof is not None
        proof.close()
        _closed(db, proof)


@pytest.mark.parametrize("mode", ["once", "replay", "reopen", "different", "exception"])
def test_exact_select_permit_is_single_use_and_cleared_on_exit(
    customer_engine: Engine, ready: Any, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    expected, _, _, _ = ready
    with Session(customer_engine) as db, db.begin():
        row = db.get(
            PlanVersionRow,
            (expected.inputs.workspace_id, expected.inputs.plan_id, expected.version),
        )
        assert row is not None
        raw = repository.values(row)
        document = document_for_row("planning_document_versions", raw)
        assert isinstance(document, PlanVersion)
        proof = admission._make_version_row_admission(db=db, row=raw, document=document)
        assert proof is not None
        statement = select(PlanVersionRow.__table__).where(
            PlanVersionRow.workspace_id == expected.inputs.workspace_id,
            PlanVersionRow.plan_id == expected.inputs.plan_id,
            PlanVersionRow.version == expected.version,
        )
        original_execute = Session.execute
        failure = RuntimeError("controlled original execute failure")
        executed: list[bool] = []

        def execute(session: Session, actual: Any, *args: Any, **kwargs: Any) -> Any:
            result = original_execute(session, actual, *args, **kwargs)
            if actual is statement:
                executed.append(True)
                if mode == "exception":
                    raise failure
            return result

        monkeypatch.setattr(Session, "execute", execute)
        try:
            if mode == "exception":
                with pytest.raises(RuntimeError) as error, proof.reading_statement(statement):
                    db.execute(statement)
                assert error.value is failure
                assert executed == [True]
            else:
                with proof.reading_statement(statement):
                    actual = (
                        statement.where(PlanVersionRow.version == expected.version)
                        if mode == "different"
                        else statement
                    )
                    fresh = dict(db.execute(actual).mappings().one())
                    if mode == "replay":
                        db.execute(statement).all()
                if mode == "reopen":
                    with proof.reading_statement(statement):
                        db.execute(statement).all()
                matched = admission._matches_admitted_version_row(
                    db=db, row=fresh, document=document, admission=proof
                )
                assert matched is (True if mode == "once" else None)
                assert document_for_row("planning_document_versions", fresh) == document
            assert proof.permitted_statement is None
            assert not proof.permit_active and proof.permit_used
        finally:
            proof.close()
        _closed(db, proof)
