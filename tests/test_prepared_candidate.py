"""Prepared candidate pure work counts, ownership and ordinary fallback."""

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext, suppress
from contextvars import copy_context
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from app.planning_documents import prepared_candidate as replay
from app.planning_documents.documents import PlanVersion
from app.planning_documents.prepared_generation import prepare_generation_checks
from app.planning_documents.storage import plan_version_storage_pair
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from tests.owner_review_v6_fixture import ready
from tests.test_owner_review_v6_pure import compose
from tests.test_prepared_generation import db as db
from tests.test_prepared_generation import operands as operands


def prepared(operands: Any) -> Any:
    value = prepare_generation_checks(*operands)
    assert value is not None and value.candidate_replay is not None
    return value


def test_seven_validations_replaced_with_fresh_snapshot_and_detached_copy(
    operands: Any, db: Session
) -> None:
    document = operands[2]
    expected = plan_version_storage_pair(document)
    value = prepared(operands)
    counts = {"validation": 0, "snapshot": 0, "comparison": 0, "copy": 0}
    codes = {
        PlanVersion.coherent.__code__: "validation",
        replay._snapshot.__code__: "snapshot",
        replay.PreparedCandidate.matches.__code__: "comparison",
        deepcopy.__code__: "copy",
    }
    prior = sys.getprofile()

    def profile(frame: Any, event: str, arg: Any) -> None:
        if event == "call" and frame.f_code in codes:
            # Only the outer deepcopy, not its recursive internal calls.
            key = codes[frame.f_code]
            if key != "copy" or frame.f_back.f_code is replay.validate_retained_candidate.__code__:
                counts[key] += 1

    sys.setprofile(profile)
    try:
        for _ in range(7):
            replay.validate_retained_candidate(document, db)
        assert counts["validation"] == 7
        counts.update(dict.fromkeys(counts, 0))
        with value.use(db), replay.retained_candidate_scope(value, db):
            results = [replay.validate_retained_candidate(document, db) for _ in range(7)]
        assert counts == {"validation": 0, "snapshot": 0, "comparison": 14, "copy": 7}
    finally:
        sys.setprofile(prior)
    assert value.candidate_replay is None and replay._ACTIVE.get() is None
    assert all(result is not document for result in results)
    assert all(plan_version_storage_pair(result) == expected for result in results)
    object.__setattr__(results[0].inputs, "revision", 999)
    assert results[1].inputs.revision == document.inputs.revision


@pytest.mark.parametrize("damage", ["nested", "fieldset", "nested_fieldset"])
def test_changed_candidate_falls_back_without_overriding_existing_refusal(
    operands: Any, db: Session, damage: str
) -> None:
    value = prepared(operands)
    document = operands[2]
    with (
        value.use(db),
        pytest.raises(HTTPException) if damage == "nested" else nullcontext(),
        replay.retained_candidate_scope(value, db),
    ):
        if damage == "nested":
            object.__setattr__(document.inputs, "revision", 999)
        elif damage == "fieldset":
            document.__pydantic_fields_set__.discard("summary")
        else:
            document.inputs.__pydantic_fields_set__.discard("revision")
        assert replay._snapshot(document) != value.candidate_replay.snapshot
        if damage == "nested":
            with pytest.raises(ValueError) as actual:
                replay.validate_retained_candidate(document, db)
            with pytest.raises(ValueError) as original:
                PlanVersion.model_validate(document)
            assert str(actual.value) == str(original.value)
            with pytest.raises(HTTPException):
                value.generation(db, *operands)
        else:
            result = replay.validate_retained_candidate(document, db)
            expected = PlanVersion.model_validate(document)
            assert replay._snapshot(result) == replay._snapshot(expected)


def test_returned_graph_does_not_mutate_private_preparation(operands: Any, db: Session) -> None:
    value = prepared(operands)
    with value.use(db):
        with pytest.raises(HTTPException), replay.retained_candidate_scope(value, db):
            first = replay.validate_retained_candidate(operands[2], db)
            object.__setattr__(first.inputs, "revision", 999)
            second = replay.validate_retained_candidate(operands[2], db)
            assert second.inputs.revision == operands[2].inputs.revision
        assert value.invalid and replay._ACTIVE.get() is None


@pytest.mark.parametrize("change", ["method", "field", "helper", "schema"])
def test_changed_behavior_uses_original_validation(
    operands: Any, db: Session, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    from app.planning_documents import documents

    value = prepared(operands)
    document = operands[2]
    calls = []
    original = PlanVersion.model_validate

    def validate(cls: Any, /, item: Any, **kwargs: Any) -> Any:
        calls.append(item)
        return original(item, **kwargs)

    with value.use(db), replay.retained_candidate_scope(value, db):
        if change == "field":
            monkeypatch.setattr(
                PlanVersion, "summary", property(lambda self: "changed"), raising=False
            )
        elif change == "helper":
            monkeypatch.setattr(documents, "is_owner_review_policy", lambda *args: False)
        elif change == "schema":
            monkeypatch.setattr(PlanVersion, "__pydantic_serializer__", object())
        assert change == "method" or not replay._contracts_unchanged()
        monkeypatch.setattr(PlanVersion, "model_validate", classmethod(validate))
        assert not replay._contracts_unchanged()
        with suppress(ValueError, AttributeError):
            replay.validate_retained_candidate(document, db)
        assert len(calls) == 1 and calls[0] is document


def test_nested_scope_poison_and_exception_cleanup(operands: Any, db: Session) -> None:
    value = prepared(operands)
    with value.use(db):
        with (
            pytest.raises(HTTPException),
            replay.retained_candidate_scope(value, db),
            replay.retained_candidate_scope(value, db),
        ):
            pytest.fail("nested replay admitted")
        assert replay._ACTIVE.get() is None
        with pytest.raises(HTTPException):
            value.generation(db, *operands)
    assert value.candidate_replay is None


def test_foreign_thread_and_outside_scope_use_original_path(
    operands: Any, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    value = prepared(operands)
    calls = []
    original = PlanVersion.model_validate

    # Count via code profile in the worker, preserving admission guards.
    def run() -> Any:
        def observe(frame: Any, event: str, arg: Any) -> None:
            if event == "call" and frame.f_code is PlanVersion.coherent.__code__:
                calls.append(True)

        prior = sys.getprofile()
        sys.setprofile(observe)
        try:
            return replay.validate_retained_candidate(operands[2])
        finally:
            sys.setprofile(prior)

    with value.use(db), replay.retained_candidate_scope(value, db), ThreadPoolExecutor(1) as pool:
        result = pool.submit(copy_context().run, run).result()
        assert result == original(operands[2])
    assert len(calls) == 1
    run()
    assert len(calls) == 2


def test_replaced_transaction_refuses(operands: Any, db: Session) -> None:
    value = prepared(operands)
    with value.use(db), pytest.raises(HTTPException), replay.retained_candidate_scope(value, db):
        db.rollback()
        with pytest.raises(HTTPException):
            replay.validate_retained_candidate(operands[2], db)


def test_unsafe_fieldset_and_normalization_are_not_prepared(operands: Any) -> None:
    document = operands[2]
    other = deepcopy(document)
    other.__pydantic_fields_set__.discard("summary")
    assert replay.prepare_candidate(document, other) is None
    object.__setattr__(document, "__pydantic_fields_set__", ["summary"])
    assert replay.prepare_candidate(document, document) is None


@pytest.mark.parametrize(
    "name", ["__pydantic_fields_set__", "__pydantic_private__", "__pydantic_extra__"]
)
def test_warmed_storage_descriptor_change_disables_replay(
    operands: Any, db: Session, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    value = prepared(operands)
    with value.use(db), replay.retained_candidate_scope(value, db):
        replay.validate_retained_candidate(operands[2], db)
        with monkeypatch.context() as patch:
            patch.setattr(PlanVersion, name, property(lambda self: None))
            assert not replay._contracts_unchanged()
            calls = []

            def original_path(cls: Any, document: Any) -> Any:
                calls.append(document)
                return document

            patch.setattr(PlanVersion, "model_validate", classmethod(original_path))
            assert replay.validate_retained_candidate(operands[2], db) is operands[2]
            assert len(calls) == 1


def test_nested_unprepared_scope_cannot_inherit_replay(operands: Any, db: Session) -> None:
    value = prepared(operands)
    with value.use(db):
        with (
            pytest.raises(HTTPException),
            replay.retained_candidate_scope(value, db),
            replay.retained_candidate_scope(None, db),
        ):
            pytest.fail("nested unprepared scope admitted")
        assert replay._ACTIVE.get() is None and value.invalid


def test_foreign_session_does_not_touch_bound_session(
    operands: Any, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    value = prepared(operands)
    with value.use(db), replay.retained_candidate_scope(value, db), Session(db.get_bind()) as other:

        def forbidden(*args: Any) -> None:
            pytest.fail("foreign invocation touched bound Session")

        with monkeypatch.context() as patch:
            patch.setattr(value, "_current", forbidden)
            result = replay.validate_retained_candidate(operands[2], other)
            assert result == PlanVersion.model_validate(operands[2])


def test_issued_capacity_falls_back_and_exception_clears_tracking(
    operands: Any, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    value = prepared(operands)
    monkeypatch.setattr(replay, "_MAX_ISSUED", 1)
    failure = RuntimeError("original callback failure")
    issued = None
    with value.use(db):
        with pytest.raises(RuntimeError) as result, replay.retained_candidate_scope(value, db):
            active = replay._ACTIVE.get()
            assert active is not None
            issued = active[3]
            first = replay.validate_retained_candidate(operands[2], db)
            calls = []
            prior = sys.getprofile()

            def observe(frame: Any, event: str, arg: Any) -> None:
                if event == "call" and frame.f_code is PlanVersion.coherent.__code__:
                    calls.append(True)

            sys.setprofile(observe)
            try:
                second = replay.validate_retained_candidate(operands[2], db)
            finally:
                sys.setprofile(prior)
            assert calls == [True]  # Literal ordinary validation path.
            assert len(issued) == 1 and first is not operands[2]
            assert second == operands[2]
            object.__setattr__(first, "summary", "changed during failed callback")
            raise failure
        assert result.value is failure
        assert issued == [] and replay._ACTIVE.get() is None


def _constructor_before_preparation(
    operands: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = operands[2]
    checked = PlanVersion.model_validate(document)
    calls: list[bool] = []

    def changed_new(cls: Any, *args: Any, **kwargs: Any) -> Any:
        calls.append(True)
        raise AssertionError("replacement constructor must not execute during copy")

    monkeypatch.setattr(PlanVersion, "__new__", staticmethod(changed_new))
    assert not replay._contracts_unchanged()
    assert replay.prepare_candidate(checked, document) is None
    assert calls == []


def _constructor_warmed_hit(
    operands: Any, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    value = prepared(operands)
    document = operands[2]
    constructors: list[bool] = []
    validations: list[bool] = []
    copies: list[bool] = []
    failure = AssertionError("custom constructor refusal")
    original_validation = PlanVersion.model_validate.__code__

    def changed_new(cls: Any, *args: Any, **kwargs: Any) -> Any:
        constructors.append(True)
        raise failure

    def profile(frame: Any, event: str, arg: Any) -> None:
        if (
            event == "call"
            and frame.f_code is original_validation
            and frame.f_back.f_code is replay.validate_retained_candidate.__code__
            and frame.f_locals.get("cls") is PlanVersion
        ):
            validations.append(True)
        if event == "call" and frame.f_code is deepcopy.__code__:
            copies.append(True)

    with value.use(db), replay.retained_candidate_scope(value, db):
        assert replay.validate_retained_candidate(document, db) == document
        with monkeypatch.context() as patch:
            patch.setattr(PlanVersion, "__new__", staticmethod(changed_new))
            assert not replay._contracts_unchanged()
            # Ordinary Pydantic revalidation also calls __new__; preserve its refusal.
            with pytest.raises(AssertionError) as original:
                PlanVersion.model_validate(document)
            assert original.value is failure and constructors == [True]
            constructors.clear()
            prior = sys.getprofile()
            sys.setprofile(profile)
            try:
                with pytest.raises(AssertionError) as result:
                    replay.validate_retained_candidate(document, db)
            finally:
                sys.setprofile(prior)
            assert result.value is original.value
            assert validations == [True] and constructors == [True] and copies == []
    assert value.candidate_replay is None and replay._ACTIVE.get() is None


def _constructor_case(mode: str) -> None:
    # CPython constructor-slot mutation can survive deleting the Python attribute.
    # Keep the actual model mutation in its own process, away from later fixtures.
    values = ready()
    operands = values[0], values[1], compose(values)
    engine = create_engine("sqlite://")
    try:
        with Session(engine) as session, session.begin(), pytest.MonkeyPatch.context() as patch:
            if mode == "before":
                _constructor_before_preparation(operands, patch)
            else:
                assert mode == "warmed"
                _constructor_warmed_hit(operands, session, patch)
    finally:
        engine.dispose()


@pytest.mark.parametrize("mode", ["before", "warmed"])
def test_replaced_constructor_uses_safe_fallback(mode: str, tmp_path: Path) -> None:
    with (tmp_path / "constructor-child.log").open("x") as output:
        subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; from tests.test_prepared_candidate import _constructor_case; "
                "_constructor_case(sys.argv[1])",
                mode,
            ],
            check=True,
            timeout=60,
            stdout=output,
            stderr=subprocess.STDOUT,
        )
