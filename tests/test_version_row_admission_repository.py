"""Actual repository entry and second SQL-row boundary, with original history checks."""

from typing import Any, cast

import pytest
from app.planning_documents import repository, selected_plan_history
from app.planning_documents import version_row_admission as admission
from app.planning_documents.models import PlanRow, PlanVersionRow
from fastapi import HTTPException
from sqlalchemy import Engine, event
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_owner_review_retained_dispatch import ready as ready
from tests.test_shopify_sales import configuration as configuration


def test_original_and_admitted_history_have_same_sql_order_and_value(
    customer_engine: Engine, ready: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    document, _, _, _ = ready
    original_factory = admission._make_version_row_admission
    original_decoder = cast(Any, selected_plan_history).document_for_row
    statements: list[str] = []
    decodes: list[bool] = []

    def sql(connection: Any, cursor: Any, statement: str, *args: Any) -> None:
        statements.append(statement)

    def decode(*args: Any, **kwargs: Any) -> Any:
        decodes.append(True)
        return original_decoder(*args, **kwargs)

    monkeypatch.setattr(selected_plan_history, "document_for_row", decode)
    results: list[tuple[str, tuple[str, ...], int]] = []
    for enabled in (False, True):
        with Session(customer_engine) as db, db.begin():
            plan = db.get(PlanRow, (document.inputs.workspace_id, document.inputs.plan_id))
            assert plan is not None
            monkeypatch.setattr(
                admission,
                "_make_version_row_admission",
                original_factory if enabled else lambda **kwargs: None,
            )
            statements.clear()
            decodes.clear()
            event.listen(db.connection(), "before_cursor_execute", sql)
            try:
                _, actual = repository.version(db, plan)
            finally:
                event.remove(db.connection(), "before_cursor_execute", sql)
            results.append((actual.model_dump_json(), tuple(statements), len(decodes)))
    # Compare privately: never print SQL or bindings in assertion explanations.
    same_sql = results[0][1] == results[1][1]
    assert same_sql, "admitted history SQL order differs from original public path"
    assert results[0][0] == results[1][0] == document.model_dump_json()
    assert (results[0][2], results[1][2]) == (1, 0)


@pytest.mark.parametrize("fault", ["fresh_row", "current_document"])
def test_repository_second_read_mutation_keeps_original_integrity_refusal(
    customer_engine: Engine, ready: Any, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    document, _, _, _ = ready
    original_factory = admission._make_version_row_admission
    original_match = admission._matches_admitted_version_row
    original_execute = Session.execute
    original_decode = cast(Any, selected_plan_history).document_for_row
    armed: list[bool] = []
    changed: list[bool] = []
    fallback: list[bool] = []

    def factory(**kwargs: Any) -> Any:
        proof = original_factory(**kwargs)
        assert proof is not None
        armed.append(True)
        return proof

    def execute(db: Session, statement: Any, *args: Any, **kwargs: Any) -> Any:
        result = original_execute(db, statement, *args, **kwargs)
        if fault != "fresh_row" or not armed or changed:
            return result
        if not getattr(statement, "is_select", False):
            return result
        tables = statement.get_final_froms()
        if len(tables) != 1 or tables[0] is not PlanVersionRow.__table__:
            return result

        class ChangedResult:
            def mappings(self) -> "ChangedResult":
                return self

            def one_or_none(self) -> Any:
                raw = result.mappings().one_or_none()
                assert raw is not None
                changed.append(True)
                return dict(raw, digest="0" * 64)

        return ChangedResult()

    def match(**kwargs: Any) -> Any:
        if fault == "current_document":
            assert not changed
            object.__setattr__(kwargs["document"], "__pydantic_private__", {})
            changed.append(True)
        return original_match(**kwargs)

    def decode(*args: Any, **kwargs: Any) -> Any:
        fallback.append(True)
        return original_decode(*args, **kwargs)

    monkeypatch.setattr(admission, "_make_version_row_admission", factory)
    monkeypatch.setattr(admission, "_matches_admitted_version_row", match)
    monkeypatch.setattr(Session, "execute", execute)
    monkeypatch.setattr(selected_plan_history, "document_for_row", decode)
    with Session(customer_engine) as db, db.begin():
        plan = db.get(PlanRow, (document.inputs.workspace_id, document.inputs.plan_id))
        assert plan is not None
        with pytest.raises(HTTPException) as error:
            repository.version(db, plan)
        assert error.value.status_code == 409
        assert error.value.detail == "selected plan historical integrity unavailable"
        assert armed == changed == fallback == [True]
        assert not db.new and not db.dirty and not db.deleted


def test_actual_nested_version_read_invalidates_outer_admission_without_listener_reentry(
    customer_engine: Engine, ready: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    document, _, _, _ = ready
    original_factory = admission._make_version_row_admission
    original_decode = cast(Any, selected_plan_history).document_for_row
    entered: list[bool] = []
    proofs: list[Any] = []
    decoded: list[bool] = []
    nested_values: list[str] = []
    with Session(customer_engine) as db, db.begin():
        plan = db.get(PlanRow, (document.inputs.workspace_id, document.inputs.plan_id))
        assert plan is not None

        def factory(**kwargs: Any) -> Any:
            proof = original_factory(**kwargs)
            if entered:
                assert proof is None
                return proof
            assert proof is not None
            entered.append(True)
            proofs.append(proof)
            _, nested = repository.version(db, plan)
            nested_values.append(nested.model_dump_json())
            return proof

        def decode(*args: Any, **kwargs: Any) -> Any:
            decoded.append(True)
            return original_decode(*args, **kwargs)

        monkeypatch.setattr(admission, "_make_version_row_admission", factory)
        monkeypatch.setattr(selected_plan_history, "document_for_row", decode)
        _, outer = repository.version(db, plan)
        assert nested_values == [outer.model_dump_json()]
        assert outer.model_dump_json() == document.model_dump_json()
        assert decoded == [True, True]
        assert len(proofs) == 1
        proof = proofs[0]
        assert proof.consumed and proof.db is None and proof.transaction is None
        assert not event.contains(db, "before_flush", proof.invalidate)
        assert not event.contains(db, "do_orm_execute", proof.orm_read)
