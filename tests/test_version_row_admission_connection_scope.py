"""Optional scope faults: real Session/Connection wrappers, not DBAPI isolation.

OptionEngine shares the existing fixture pool, including
SQLite StaticPool; no alternate database, extra query or physical isolation claim.
"""

from typing import Any

import pytest
from app.planning_documents import repository
from app.planning_documents import version_row_admission as admission
from app.planning_documents.documents import PlanVersion
from app.planning_documents.models import PlanVersionRow
from app.planning_documents.storage import document_for_row
from sqlalchemy import Engine, event
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_owner_review_retained_dispatch import ready as ready
from tests.test_shopify_sales import configuration as configuration


def _closed(original: Session, proof: Any) -> None:
    assert proof.consumed and proof.row is None and proof.document is None
    assert proof.db is None and proof.root is None and proof.connection is None
    assert proof.transaction is None and proof.permitted_statement is None
    assert not proof.permit_active
    assert not event.contains(original, "before_flush", proof.invalidate)
    assert not event.contains(original, "do_orm_execute", proof.orm_read)


@pytest.mark.parametrize("fault", ["different_session", "different_connection_wrapper"])
def test_actual_scope_identity_declines_only_optimization(
    customer_engine: Engine, ready: Any, fault: str
) -> None:
    expected, _, _, _ = ready
    # Different OptionEngine identity, same approved underlying pool/database.
    alternate_bind = customer_engine.execution_options()
    assert alternate_bind is not customer_engine
    assert alternate_bind.pool is customer_engine.pool
    with Session(customer_engine) as db:
        try:
            db.begin()
            row = db.get(
                PlanVersionRow,
                (expected.inputs.workspace_id, expected.inputs.plan_id, expected.version),
            )
            assert row is not None
            raw = repository.values(row)
            document = document_for_row("planning_document_versions", raw)
            assert isinstance(document, PlanVersion)
            root = db.get_transaction()
            original_connection = db.connection()
            original_transaction = original_connection.get_transaction()
            assert root is not None and root.is_active
            assert original_transaction is not None and original_transaction.is_active
            proof = admission._make_version_row_admission(db=db, row=raw, document=document)
            assert proof is not None
            try:
                if fault == "different_session":
                    with Session(customer_engine) as other, other.begin():
                        assert other is not db
                        assert other.get_transaction() is not root
                        # Observe any accidental connection acquisition without
                        # substituting Session.connection or fabricating a result.
                        acquired: list[bool] = []

                        def began(*args: Any) -> None:
                            acquired.append(True)

                        event.listen(other, "after_begin", began)
                        try:
                            matched = admission._matches_admitted_version_row(
                                db=other, row=raw, document=document, admission=proof
                            )
                            assert matched is None
                            assert acquired == []
                        finally:
                            event.remove(other, "after_begin", began)
                else:
                    original_bind = db.bind
                    try:
                        db.bind = alternate_bind
                        replacement = db.connection()  # Real original multi-bind path.
                        assert db.get_transaction() is root and root.is_active
                        assert replacement is not original_connection
                        assert replacement.engine is alternate_bind
                        assert (
                            replacement.in_transaction()
                            and not replacement.in_nested_transaction()
                        )
                        assert original_connection.get_transaction() is original_transaction
                        assert original_transaction.is_active
                        # No SQL executes on replacement; identity mismatch alone
                        # declines optimization while original decoding remains.
                        matched = admission._matches_admitted_version_row(
                            db=db, row=raw, document=document, admission=proof
                        )
                        assert matched is None
                    finally:
                        db.bind = original_bind
                assert db.get_transaction() is root and root.is_active
                assert original_connection.get_transaction() is original_transaction
                assert original_transaction.is_active
                _closed(db, proof)
                assert document_for_row("planning_document_versions", raw) == document
            finally:
                proof.close()
            _closed(db, proof)
        finally:
            db.rollback()
    # Do not dispose alternate_bind: it shares the fixture's pool.
