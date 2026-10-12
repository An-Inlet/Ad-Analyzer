"""Differential equality with original admitted snapshots, including fallback."""

from copy import deepcopy
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from app.planning_documents.prepared_candidate import _CandidateSnapshot
from app.planning_documents.prepared_snapshot_match import prepare_snapshot_match
from app.planning_documents.version_row_admission import _UNSUPPORTED, _Snapshot
from pydantic import BaseModel, ConfigDict

from tests.test_prepared_generation import operands as operands


class Child(BaseModel):
    model_config = ConfigDict(frozen=True)
    number: int


class Graph(BaseModel):
    model_config = ConfigDict(frozen=True)
    children: tuple[Child, ...]
    text: str
    raw: bytes
    flag: bool
    optional: int | None
    decimal: Decimal
    day: date
    instant: datetime


def graph() -> Graph:
    return Graph(
        children=(Child(number=1), Child(number=2)),
        text="hello",
        raw=b"bytes",
        flag=True,
        optional=None,
        decimal=Decimal("1.00"),
        day=date(2026, 10, 12),
        instant=datetime(2026, 10, 12, tzinfo=UTC),
    )


@pytest.mark.parametrize("candidate", [False, True])
@pytest.mark.parametrize(
    "change",
    [
        "none",
        "equal_copy",
        "nested",
        "bool_as_int",
        "int_as_bool",
        "decimal_representation",
        "date",
        "instant",
        "fold",
        "extra_field",
        "private",
        "extra",
        "missing_field",
        "tuple_length",
        "alias",
        "cycle",
        "fieldset",
        "nested_fieldset",
        "subclass",
        "huge",
    ],
)
def test_exact_snapshot_differential(candidate: bool, change: str) -> None:
    value = graph()
    scan = _CandidateSnapshot if candidate else _Snapshot
    snapshot = scan().copy(value, Graph)
    assert snapshot is not _UNSUPPORTED
    matcher = prepare_snapshot_match(snapshot, value, Graph, candidate=candidate, scanner=scan)
    assert matcher is not None and matcher.matches(value) is True
    value = deepcopy(value)
    if change == "nested":
        object.__setattr__(value.children[0], "number", 99)
    elif change == "bool_as_int":
        object.__setattr__(value, "flag", 1)
    elif change == "int_as_bool":
        object.__setattr__(value.children[0], "number", True)
    elif change == "decimal_representation":
        object.__setattr__(value, "decimal", Decimal("1.0"))
    elif change == "date":
        object.__setattr__(value, "day", value.day + timedelta(days=1))
    elif change == "instant":
        object.__setattr__(value, "instant", value.instant + timedelta(microseconds=1))
    elif change == "fold":
        object.__setattr__(value, "instant", value.instant.replace(fold=1))
    elif change == "extra_field":
        value.__dict__["unexpected"] = 1
    elif change == "private":
        object.__setattr__(value, "__pydantic_private__", {"x": 1})
    elif change == "extra":
        object.__setattr__(value, "__pydantic_extra__", {"x": 1})
    elif change == "missing_field":
        del value.__dict__["text"]
    elif change == "tuple_length":
        object.__setattr__(value, "children", value.children[:1])
    elif change == "alias":
        object.__setattr__(value, "children", (value.children[0], value.children[0]))
    elif change == "cycle":
        object.__setattr__(value.children[0], "number", value)
    elif change == "fieldset":
        value.__pydantic_fields_set__.discard("text")
    elif change == "nested_fieldset":
        value.children[0].__pydantic_fields_set__.clear()
    elif change == "subclass":

        class Custom(Child):
            pass

        object.__setattr__(value, "children", (Custom(number=1), value.children[1]))
    elif change == "huge":
        object.__setattr__(value, "text", "x" * (8 * 1024 * 1024 + 1))
    expected = scan().copy(value, Graph)
    assert matcher.matches(value) is (expected is not _UNSUPPORTED and expected == snapshot)


@pytest.mark.parametrize(
    "damage",
    [
        "annotation",
        "exclude",
        "exclude_if",
        "order",
        "computed",
        "field_replace",
        "descriptor",
    ],
)
def test_in_place_metadata_changes_select_original_fallback(
    monkeypatch: pytest.MonkeyPatch, damage: str
) -> None:
    value = graph()
    matcher = prepare_snapshot_match(_Snapshot().copy(value, Graph), value, Graph)
    assert matcher is not None
    fields = Graph.model_fields
    if damage == "annotation":
        monkeypatch.setattr(fields["text"], "annotation", bytes)
    elif damage == "exclude":
        monkeypatch.setattr(fields["text"], "exclude", True)
    elif damage == "exclude_if":
        monkeypatch.setattr(fields["text"], "exclude_if", lambda value: True)
    elif damage == "order":
        monkeypatch.setattr(Graph, "__pydantic_fields__", dict(reversed(tuple(fields.items()))))
    elif damage == "computed":
        monkeypatch.setattr(Graph, "__pydantic_computed_fields__", {"extra": object()})
    elif damage == "field_replace":
        monkeypatch.setitem(fields, "text", deepcopy(fields["text"]))
    else:
        monkeypatch.setattr(Graph, "model_fields", property(lambda _: fields))
    assert matcher.matches(value) is None


def test_actual_prepared_roots_and_candidate_match(operands: Any) -> None:
    for value in operands:
        snapshot = _Snapshot().copy(value, type(value))
        matcher = prepare_snapshot_match(snapshot, value, type(value))
        assert matcher is not None and matcher.matches(value) is True
        assert matcher.matches(deepcopy(value)) is True
    document = operands[2]
    snapshot = _CandidateSnapshot().copy(document, type(document))
    matcher = prepare_snapshot_match(
        snapshot, document, type(document), candidate=True, scanner=_CandidateSnapshot
    )
    assert matcher is not None and matcher.matches(document) is True
    document.inputs.__pydantic_fields_set__.clear()
    assert matcher.matches(document) is False


@pytest.mark.parametrize("damage", ["annotation", "exclude", "equality", "descriptor"])
def test_metadata_changed_before_compilation_is_not_admitted(
    monkeypatch: pytest.MonkeyPatch, damage: str
) -> None:
    value = graph()
    snapshot = _Snapshot().copy(value, Graph)
    if damage == "annotation":
        monkeypatch.setattr(Graph.model_fields["text"], "annotation", bytes)
    elif damage == "exclude":
        monkeypatch.setattr(Graph.model_fields["text"], "exclude", True)
    elif damage == "equality":
        monkeypatch.setattr(Graph, "__eq__", lambda self, other: True)
    else:
        monkeypatch.setattr(Graph, "model_fields", property(lambda _: {}))
    assert prepare_snapshot_match(snapshot, value, Graph) is None


@pytest.mark.parametrize("before", [False, True])
@pytest.mark.parametrize("kind", ["literal", "annotated"])
def test_mutable_typing_alias_is_not_reused(
    monkeypatch: pytest.MonkeyPatch, before: bool, kind: str
) -> None:
    from typing import Annotated, Literal

    # Modify a local field annotation, not the model's cached validation schema.
    value = graph()
    alias = Literal["hello"] if kind == "literal" else Annotated[str, "local matcher test"]
    monkeypatch.setattr(Graph.model_fields["text"], "annotation", alias)
    snapshot = _Snapshot().copy(value, Graph)
    assert snapshot is not _UNSUPPORTED
    matcher = None if before else prepare_snapshot_match(snapshot, value, Graph)
    monkeypatch.setattr(
        alias,
        "__args__" if kind == "literal" else "__origin__",
        ("changed",) if kind == "literal" else bytes,
    )
    assert _Snapshot().copy(value, Graph) is _UNSUPPORTED
    if before:
        assert prepare_snapshot_match(snapshot, value, Graph) is None
    else:
        assert matcher is not None and matcher.matches(value) is None


def test_unknown_annotation_metadata_does_not_invoke_getters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    value = graph()
    snapshot = _Snapshot().copy(value, Graph)
    calls = []

    class Unknown:
        def __getattribute__(self, name: str) -> Any:
            calls.append(name)
            raise AssertionError("unsupported metadata getter")

    monkeypatch.setattr(Graph.model_fields["text"], "annotation", Unknown())
    assert prepare_snapshot_match(snapshot, value, Graph) is None
    assert calls == []


def test_oversized_alias_arguments_select_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    from typing import Literal

    value = graph()
    alias = Literal["hello"]
    monkeypatch.setattr(Graph.model_fields["text"], "annotation", alias)
    snapshot = _Snapshot().copy(value, Graph)
    matcher = prepare_snapshot_match(snapshot, value, Graph)
    assert matcher is not None
    monkeypatch.setattr(alias, "__args__", ("hello",) * 10_001)
    assert matcher.matches(value) is None
    assert prepare_snapshot_match(snapshot, value, Graph) is None


def test_opaque_annotated_field_metadata_preserves_original_semantics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from typing import Annotated

    from pydantic.fields import FieldInfo

    value = graph()
    metadata = FieldInfo(description="opaque snapshot metadata")
    alias = Annotated[str, metadata]
    monkeypatch.setattr(Graph.model_fields["text"], "annotation", alias)
    snapshot = _Snapshot().copy(value, Graph)
    matcher = prepare_snapshot_match(snapshot, value, Graph)
    assert matcher is not None and matcher.matches(value) is True
    metadata.description = "changed metadata ignored by original scanner"
    metadata.exclude = True
    assert _Snapshot().copy(value, Graph) == snapshot
    assert matcher.matches(value) is True
