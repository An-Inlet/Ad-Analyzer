"""Private prepared candidate validation reuse; no source or authorization reuse."""

from asyncio import current_task
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from inspect import getattr_static
from sys import modules
from threading import get_ident
from types import FunctionType
from typing import TYPE_CHECKING, Any, get_args

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.planning_documents.documents import PlanVersion
from app.planning_documents.prepared_snapshot_match import prepare_snapshot_match
from app.planning_documents.version_row_admission import _UNSUPPORTED, _Snapshot

if TYPE_CHECKING:
    from app.planning_documents.prepared_generation import PreparedGenerationChecks

_MISSING = object()
_MAX_ISSUED = 16
_FIELDSET = BaseModel.__dict__["__pydantic_fields_set__"]
_COPY = BaseModel.__deepcopy__


def _models() -> tuple[type[BaseModel], ...]:
    found: set[type[BaseModel]] = set()

    def visit(annotation: Any) -> None:
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            if annotation in found:
                return
            found.add(annotation)
            for field in annotation.model_fields.values():
                visit(field.annotation)
        else:
            for child in get_args(annotation):
                visit(child)

    visit(PlanVersion)
    return tuple(sorted(found, key=lambda model: (model.__module__, model.__name__)))


_MODELS = _models()
_SCHEMAS = tuple((m, m.__pydantic_validator__, m.__pydantic_serializer__) for m in _MODELS)
_METHODS = tuple(
    (model, name, getattr_static(model, name, _MISSING))
    for model in _MODELS
    for name in set(model.model_fields)
    | {
        "model_validate",
        "model_dump",
        "model_dump_json",
        "__deepcopy__",
        "__new__",
        "__getattribute__",
        "__dict__",
        "__pydantic_fields_set__",
        "__pydantic_private__",
        "__pydantic_extra__",
    }
    | {
        name
        for cls in model.__mro__
        if cls is not BaseModel and cls is not object
        for name, value in vars(cls).items()
        if type(value) in (FunctionType, classmethod, staticmethod, property)
    }
)
# Include imported application helpers as well as each declared model's methods.
# Capture their application-global function dependencies transitively: changed
# validation/serialization helpers must select ordinary validation, not replay.


def _functions() -> tuple[tuple[dict[str, Any], str, object], ...]:
    result: dict[tuple[int, str], tuple[dict[str, Any], str, object]] = {}
    pending = [
        value
        for model in _MODELS
        for value in vars(modules[model.__module__]).values()
        if type(value) is FunctionType and value.__module__.startswith("app.")
    ]
    pending.extend(
        value.__func__ if type(value) in (classmethod, staticmethod) else value
        for _, _, value in _METHODS
        if type(value) in (FunctionType, classmethod, staticmethod)
    )
    seen: set[int] = set()
    while pending:
        function = pending.pop()
        if id(function) in seen:
            continue
        seen.add(id(function))
        namespace = function.__globals__
        for name in function.__code__.co_names:
            value = namespace.get(name)
            if type(value) is FunctionType and value.__module__.startswith("app."):
                result[(id(namespace), name)] = (namespace, name, value)
                pending.append(value)
    return tuple(result.values())


_FUNCTIONS = _functions()


def _contracts_unchanged() -> bool:
    return (
        all(
            getattr_static(model, "__pydantic_validator__", _MISSING) is validator
            and getattr_static(model, "__pydantic_serializer__", _MISSING) is serializer
            and getattr_static(model, "__deepcopy__", _MISSING) is _COPY
            for model, validator, serializer in _SCHEMAS
        )
        and all(getattr_static(model, name, _MISSING) is value for model, name, value in _METHODS)
        and all(namespace.get(name, _MISSING) is value for namespace, name, value in _FUNCTIONS)
    )


class _CandidateSnapshot(_Snapshot):
    def copy(self, value: object, expected: Any, depth: int = 0) -> object:
        result = super().copy(value, expected, depth)
        if result is _UNSUPPORTED:
            return result
        if isinstance(expected, type) and issubclass(expected, BaseModel):
            try:
                fields = _FIELDSET.__get__(value, expected)
            except AttributeError:
                return _UNSUPPORTED
            if (
                type(fields) is not set
                or len(fields) > len(expected.model_fields)
                or any(type(key) is not str or key not in expected.model_fields for key in fields)
            ):
                return _UNSUPPORTED
            return (result, tuple(sorted(fields)))
        return result


def _snapshot(document: PlanVersion) -> object | None:
    try:
        value = _CandidateSnapshot().copy(document, PlanVersion)
    except (AttributeError, TypeError, ValueError, RecursionError):
        return None
    return None if value is _UNSUPPORTED else value


_SNAPSHOT = _snapshot
_SNAPSHOT_CLASS = _CandidateSnapshot
_SNAPSHOT_COPY = _CandidateSnapshot.copy
_SNAPSHOT_FIELDSET = _FIELDSET


class PreparedCandidate:
    """Owned detached template, admitted only from the already validated candidate."""

    def __init__(self, snapshot: object, document: PlanVersion) -> None:
        self.snapshot = snapshot
        self.matcher = prepare_snapshot_match(
            snapshot, document, PlanVersion, candidate=True, scanner=_CandidateSnapshot
        )
        self.document: PlanVersion | None = document

    def matches(self, document: PlanVersion) -> bool:
        matcher = self.matcher
        matched = (
            matcher.matches(document)
            if matcher is not None
            and matcher.snapshot is self.snapshot
            and _snapshot is _SNAPSHOT
            and _CandidateSnapshot is _SNAPSHOT_CLASS
            and _CandidateSnapshot.copy is _SNAPSHOT_COPY
            and _FIELDSET is _SNAPSHOT_FIELDSET
            else None
        )
        return _snapshot(document) == self.snapshot if matched is None else matched

    def close(self) -> None:
        self.document = None
        self.snapshot = None
        self.matcher = None


def prepare_candidate(document: PlanVersion, original: PlanVersion) -> PreparedCandidate | None:
    if not _contracts_unchanged():
        return None
    snapshot = _snapshot(document)
    if snapshot is None or _snapshot(original) != snapshot:
        return None
    private = deepcopy(document)
    if _snapshot(private) != snapshot or not _contracts_unchanged():
        return None
    return PreparedCandidate(snapshot, private)


_ACTIVE: ContextVar[
    tuple["PreparedGenerationChecks", Session, tuple[int, object], list[PlanVersion]] | None
] = ContextVar("retained_prepared_candidate", default=None)


def _owner() -> tuple[int, object]:
    try:
        task: object = current_task()
    except RuntimeError:
        task = None
    return get_ident(), task


@contextmanager
def retained_candidate_scope(
    prepared: "PreparedGenerationChecks | None", db: Session
) -> Iterator[None]:
    from app.planning_documents.prepared_generation import require_prepared

    active = _ACTIVE.get()
    if active is not None and active[2] == _owner():
        outer, bound, _, _ = active
        outer.invalid = True
        require_prepared(outer, bound)
    if prepared is None:
        token = _ACTIVE.set(None)
        try:
            yield
        finally:
            _ACTIVE.reset(token)
        return
    require_prepared(prepared, db)
    issued: list[PlanVersion] = []
    token = _ACTIVE.set((prepared, db, _owner(), issued))
    try:
        yield
        # Original candidate checks cannot see mutations confined to detached
        # retained graphs. Seal every issued graph before witnesses escape.
        replay = prepared.candidate_replay
        if issued and (
            replay is None
            or not _contracts_unchanged()
            or any(not replay.matches(document) for document in issued)
        ):
            prepared.invalid = True
        require_prepared(prepared, db)
    finally:
        issued.clear()
        _ACTIVE.reset(token)


def validate_retained_candidate(document: PlanVersion, db: Session | None = None) -> PlanVersion:
    active = _ACTIVE.get()
    if active is not None and active[2] == _owner() and (db is None or db is active[1]):
        prepared, bound, _, issued = active
        prepared._current(bound)
        replay = prepared.candidate_replay
        if (
            replay is not None
            and replay.document is not None
            and len(issued) < _MAX_ISSUED
            and _contracts_unchanged()
            and replay.matches(document)
        ):
            result = deepcopy(replay.document)
            issued.append(result)
            prepared._current(bound)
            return result
    return PlanVersion.model_validate(document)
