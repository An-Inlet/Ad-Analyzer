"""Pure preparation and single-save lifecycle; no live authorization claims."""

from datetime import datetime, timedelta, tzinfo
from typing import Any

import pytest
from app.planning_documents import prepared_generation as prepared
from app.planning_documents import repository
from app.planning_documents.storage import plan_version_storage_pair
from fastapi import HTTPException
from sqlalchemy import Integer, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from tests.owner_review_v6_fixture import ready
from tests.test_owner_review_v6_pure import compose


class Base(DeclarativeBase):
    pass


class Row(Base):
    __tablename__ = "preparation_scope_test"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)


@pytest.fixture
def operands() -> Any:
    values = ready()
    return values[0], values[1], compose(values)


@pytest.fixture
def db() -> Any:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session, session.begin():
            yield session
    finally:
        engine.dispose()


def make(operands: Any) -> prepared.PreparedGenerationChecks:
    value = prepared.prepare_generation_checks(*operands)
    assert value is not None, "real supported v6 graphs must qualify"
    return value


def test_original_pure_work_runs_once_and_storage_bytes_match(
    operands: Any, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    counts: dict[str, int] = {}
    for module, name in (
        (repository, "_generation_entry"),
        (repository, "_generation_actual_bindings"),
        (repository, "_generation_owner_binding"),
        (prepared, "_validate_paired_ticket_pair"),
        (prepared, "_validate_selected_ticket_pair"),
    ):
        original = getattr(module, name)

        def counted(*args: Any, _name: str = name, _original: Any = original) -> Any:
            counts[_name] = counts.get(_name, 0) + 1
            return _original(*args)

        monkeypatch.setattr(module, name, counted)
    ticket, bundle, candidate = operands
    before = plan_version_storage_pair(candidate)
    value = make(operands)
    assert counts == {key: 1 for key in counts} and len(counts) == 5
    with value.use(db):
        value.generation(db, *operands)
        for _ in range(2):  # The two source checks around creative revalidation.
            value.paired(db, ticket, bundle.reporting)
            value.selected(db, ticket, bundle.reporting.selected)
            value.selected(db, ticket, bundle.reporting.selected)
            value.paired(db, ticket, bundle.reporting)
        value.publication(db, *operands)
        value.generation(db, *operands)
    assert counts == {key: 1 for key in counts}
    assert plan_version_storage_pair(candidate) == before
    assert value.snapshots is None and value.db is None


@pytest.mark.parametrize("target", ["ticket", "candidate", "selected", "nested"])
def test_mutation_poisoned_even_if_refusal_is_caught(
    operands: Any, db: Session, target: str
) -> None:
    ticket, bundle, candidate = operands
    value = make(operands)
    with value.use(db):
        if target == "ticket":
            object.__setattr__(ticket, "expected_version", ticket.expected_version + 1)
        elif target == "candidate":
            object.__setattr__(candidate, "version", candidate.version + 1)
        elif target == "selected":
            selected = bundle.reporting.selected
            object.__setattr__(
                selected, "collected_at", selected.collected_at + timedelta(seconds=1)
            )
        else:
            object.__setattr__(candidate.inputs, "revision", candidate.inputs.revision + 1)
        with pytest.raises(HTTPException, match="prepared generation evidence changed"):
            value.generation(db, *operands)
        with pytest.raises(HTTPException):
            value.paired(db, ticket, bundle.reporting)


def test_custom_timezone_never_invoked_during_eligibility(operands: Any) -> None:
    calls: list[str] = []

    class CustomZone(tzinfo):
        def utcoffset(self, dt: datetime | None) -> timedelta:
            calls.append("offset")
            raise AssertionError("custom callback must select original path")

        def dst(self, dt: datetime | None) -> timedelta:
            raise AssertionError("custom callback must select original path")

        def tzname(self, dt: datetime | None) -> str:
            raise AssertionError("custom callback must select original path")

    object.__setattr__(operands[2], "generated_at", datetime(2026, 1, 1, tzinfo=CustomZone()))
    assert prepared.prepare_generation_checks(*operands) is None
    assert not calls


@pytest.mark.parametrize("refusal", ["expected", "normalized", "unexpected"])
def test_preparation_refusals_preserve_original_path(
    operands: Any, monkeypatch: pytest.MonkeyPatch, refusal: str
) -> None:
    original = repository._generation_entry
    failure = RuntimeError("test-only unexpected preparation failure")

    def altered(*args: Any) -> Any:
        if refusal == "expected":
            raise HTTPException(409, "test-only pure refusal")
        if refusal == "unexpected":
            raise failure
        ticket, candidate, capability = original(*args)
        return ticket.model_copy(update={"expected_version": 17}), candidate, capability

    monkeypatch.setattr(repository, "_generation_entry", altered)
    if refusal == "unexpected":
        with pytest.raises(RuntimeError) as result:
            prepared.prepare_generation_checks(*operands)
        assert result.value is failure
    else:
        assert prepared.prepare_generation_checks(*operands) is None


def test_preexisting_listener_uses_original_path(operands: Any, db: Session) -> None:
    value = make(operands)

    def listener(*args: Any) -> None:
        pass

    event.listen(db, "before_flush", listener)
    try:
        with value.use(db) as active:
            assert active is None
        assert event.contains(db, "before_flush", listener)
    finally:
        event.remove(db, "before_flush", listener)


@pytest.mark.parametrize("damage", ["reuse", "foreign", "nested", "flush"])
def test_scope_refusals_are_poisoned(operands: Any, db: Session, damage: str) -> None:
    value = make(operands)
    with value.use(db):
        with pytest.raises(HTTPException):
            if damage == "reuse":
                with value.use(db):
                    pytest.fail("reused preparation")
            elif damage == "foreign":
                with Session(db.get_bind()) as other, other.begin():
                    value.generation(other, *operands)
            elif damage == "nested":
                with db.begin_nested():
                    value.generation(db, *operands)
            else:
                db.add(Row(id=1))
                db.flush()
        with pytest.raises(HTTPException):
            value.generation(db, *operands)
        # A prohibited flush has not executed SQL; discard its pending object.
        for pending in list(db.new):
            db.expunge(pending)


def test_publication_flush_keeps_scope_and_checks(operands: Any, db: Session) -> None:
    value = make(operands)
    with value.use(db):
        value.publication(db, *operands)
        db.add(Row(id=1))
        db.flush()
        value.generation(db, *operands)
        assert not value.invalid
    assert not db.dispatch.before_flush


def test_fake_or_inactive_preparation_cannot_bypass_helpers(operands: Any, db: Session) -> None:
    with pytest.raises(HTTPException):
        prepared.require_prepared(object(), db)  # type: ignore[arg-type]
    value = make(operands)
    with pytest.raises(HTTPException):
        prepared.require_prepared(value, db)


def test_cleanup_attempts_all_removals_and_preserves_original_error(
    operands: Any, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    value = make(operands)
    original_remove = event.remove
    names: list[str] = []
    failure = RuntimeError("original")

    def remove(target: Any, name: str, fn: Any) -> None:
        names.append(name)
        original_remove(target, name, fn)
        if name == "after_transaction_end":
            raise RuntimeError("cleanup")

    monkeypatch.setattr(event, "remove", remove)
    with pytest.raises(RuntimeError) as result, value.use(db):
        raise failure
    assert result.value is failure
    assert names == list(reversed(prepared._EVENTS))
    assert value.snapshots is None and value.db is None


@pytest.mark.parametrize("registered", [False, True])
def test_partial_listener_installation_is_cleaned(
    operands: Any, db: Session, monkeypatch: pytest.MonkeyPatch, registered: bool
) -> None:
    value = make(operands)
    original = event.listen
    failure = RuntimeError("listener installation failure")
    calls = 0

    def listen(target: Any, name: str, callback: Any) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            if registered:
                original(target, name, callback)
            raise failure
        original(target, name, callback)

    monkeypatch.setattr(event, "listen", listen)
    with pytest.raises(RuntimeError) as result, value.use(db):
        pytest.fail("partial install must not admit a prepared scope")
    assert result.value is failure
    assert value.snapshots is None and value.db is None
    assert all(not getattr(db.dispatch, name) for name in prepared._EVENTS)


@pytest.mark.parametrize("consumer", ["save", "paired", "selected"])
def test_direct_consumers_refuse_forged_preparation(
    operands: Any, db: Session, consumer: str
) -> None:
    from app.planning_documents import selected_paired_local, selected_plan_local

    ticket, bundle, candidate = operands
    common: dict[str, Any] = dict(principal=None, ticket=ticket, prepared=object())
    with pytest.raises(HTTPException) as result:
        if consumer == "save":
            common["fact"] = None
            repository.save_generation(
                db,
                **common,
                bundle=bundle,
                candidate=candidate,
                request_key="unused",
                request_digest="unused",
                now=candidate.generated_at,
                recheck=lambda *args: None,
            )
        else:
            function = (
                selected_paired_local.recheck_selected_paired_sources
                if consumer == "paired"
                else selected_plan_local.recheck_selected_sources
            )
            function(
                db,
                **common,
                bundle=bundle.reporting if consumer == "paired" else bundle.reporting.selected,
                authorize=lambda *args: None,
                clock=lambda: candidate.generated_at,
            )
    assert result.value.status_code == 409
    assert result.value.detail == "prepared generation evidence changed"
