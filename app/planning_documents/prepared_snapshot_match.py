"""Exact comparison with an admitted private snapshot; no validation or SQL reuse."""

from datetime import date, datetime
from decimal import Decimal
from inspect import getattr_static
from types import GenericAlias, UnionType
from typing import Annotated, Any, Literal, Union, get_args, get_origin

from pydantic import BaseModel
from pydantic.fields import FieldInfo

from app.planning_documents import version_row_admission as original

_MISSING = object()
_VALUES = BaseModel.__dict__["__dict__"]
_PRIVATE = BaseModel.__dict__["__pydantic_private__"]
_EXTRA = BaseModel.__dict__["__pydantic_extra__"]
_FIELDSET = BaseModel.__dict__["__pydantic_fields_set__"]
_SCALARS = {
    "none": type(None),
    "str": str,
    "bytes": bytes,
    "bool": bool,
    "int": int,
    "date": date,
    "decimal": Decimal,
    "datetime": datetime,
}
_ALIAS_TYPES = (
    GenericAlias,
    UnionType,
    type(Literal[1]),
    type(Union[int, str]),  # noqa: UP007 - legacy typing alias is a distinct runtime class.
    type(Annotated[int, "x"]),
    type(tuple[Any, ...]),
)


def _annotation_parts(annotation: Any) -> tuple[Any, tuple[Any, ...]]:
    kind = type(annotation)
    if any(
        kind is allowed
        for allowed in (
            type,
            type(BaseModel),
            str,
            int,
            bool,
            type(None),
            type(Ellipsis),
            FieldInfo,
        )
    ):
        return None, ()
    if not any(kind is allowed for allowed in _ALIAS_TYPES):
        raise ValueError("unsupported annotation metadata")
    args = get_args(annotation)
    if type(args) is not tuple or len(args) > 10_000:
        raise ValueError("annotation argument capacity")
    return get_origin(annotation), args


_ORDINARY_MODEL = tuple(
    (name, getattr_static(BaseModel, name))
    for name in ("__eq__", "model_fields", "model_computed_fields")
)
_ORDINARY_META = tuple(
    (name, getattr_static(type(BaseModel), name))
    for name in ("__eq__", "__getattribute__", "__getattr__")
)
_ORIGINAL = tuple(
    (owner, name, getattr_static(owner, name, _MISSING))
    for owner, names in (
        (
            original,
            (
                "_Snapshot",
                "_MODEL_VALUES",
                "_MODEL_PRIVATE",
                "_MODEL_EXTRA",
                "_DATETIME_ZONE",
                "_MAX_NODES",
                "_MAX_DEPTH",
                "_MAX_BYTES",
                "_UNSUPPORTED",
                "get_origin",
                "get_args",
                "cast",
                "Annotated",
                "Union",
                "UnionType",
                "Literal",
                "BaseModel",
                "AwareDatetime",
                "date",
                "datetime",
                "timezone",
                "ZoneInfo",
                "TzInfo",
                "Decimal",
            ),
        ),
        (original._Snapshot, ("copy", "scalar", "matches", "charge")),
        (FieldInfo, ("__getattribute__", "annotation", "exclude", "exclude_if")),
        *((kind, ("__getattribute__", "__getattr__")) for kind in _ALIAS_TYPES),
    )
    for name in names
)


class PreparedSnapshotMatch:
    """Compile after admission; unsupported metadata selects the original copier."""

    def __init__(self, snapshot: object, *, candidate: bool = False) -> None:
        self.snapshot = snapshot
        self.candidate = candidate
        self.models: dict[type[BaseModel], tuple[Any, ...]] = {}
        self.annotations: dict[int, tuple[Any, Any, tuple[Any, ...]]] = {}
        pending = [snapshot]
        nodes = 0
        while pending:
            nodes += 1
            if nodes > 100_000:
                raise ValueError("snapshot comparison capacity")
            item = pending.pop()
            if type(item) is not tuple or not item:
                raise ValueError("admitted snapshot required")
            if candidate and type(item[0]) is tuple:
                item = item[0]
            if item[0] == "model":
                model = item[1]
                if model not in self.models:
                    if not all(
                        getattr_static(model, name, _MISSING) is method
                        for name, method in _ORDINARY_MODEL
                    ) or not all(
                        getattr_static(type(model), name, _MISSING) is method
                        for name, method in _ORDINARY_META
                    ):
                        raise ValueError("ordinary model descriptors required")
                    fields = getattr_static(model, "__pydantic_fields__", _MISSING)
                    computed = getattr_static(model, "__pydantic_computed_fields__", _MISSING)
                    if type(fields) is not dict or type(computed) is not dict or computed:
                        raise ValueError("ordinary snapshot metadata required")
                    specs = []
                    for name, field in fields.items():
                        if type(name) is not str or type(field) is not FieldInfo:
                            raise ValueError("ordinary field metadata required")
                        annotations = [field.annotation]
                        while annotations:
                            annotation = annotations.pop()
                            if id(annotation) in self.annotations:
                                continue
                            if len(self.annotations) >= 10_000:
                                raise ValueError("annotation capacity")
                            origin, args = _annotation_parts(annotation)
                            if len(annotations) + len(args) > 10_000:
                                raise ValueError("annotation pending capacity")
                            self.annotations[id(annotation)] = (
                                annotation,
                                origin,
                                args,
                            )
                            annotations.extend(args)
                        specs.append(
                            (name, field, field.annotation, field.exclude, field.exclude_if)
                        )
                    self.models[model] = (
                        type.__getattribute__(model, "__mro__"),
                        fields,
                        computed,
                        tuple(specs),
                        tuple(
                            (owner, name, getattr_static(owner, name, _MISSING))
                            for owner, names in (
                                (model, ("__eq__", "model_fields", "model_computed_fields")),
                                (type(model), ("__eq__", "__getattribute__", "__getattr__")),
                            )
                            for name in names
                        ),
                    )
                if tuple(name for name, _ in item[4]) != tuple(self.models[model][1]):
                    raise ValueError("snapshot field order changed")
                pending.extend(child for _, child in item[4])
            elif item[0] == "tuple":
                pending.extend(item[1])
            elif item[0] not in _SCALARS:
                raise ValueError("admitted snapshot scalar required")

    def current(self) -> bool:
        try:
            return self._current()
        except (AttributeError, TypeError, ValueError, RecursionError):
            return False

    def _current(self) -> bool:
        if not all(
            getattr_static(owner, name, _MISSING) is value for owner, name, value in _ORIGINAL
        ):
            return False
        for annotation, origin, args in self.annotations.values():
            actual_origin, actual = _annotation_parts(annotation)
            if (
                actual_origin is not origin
                or len(actual) != len(args)
                or any(left is not right for left, right in zip(actual, args, strict=True))
            ):
                return False
        for model, (mro, fields, computed, specs, methods) in self.models.items():
            if (
                type.__getattribute__(model, "__mro__") is not mro
                or getattr_static(model, "__pydantic_fields__", _MISSING) is not fields
                or getattr_static(model, "__pydantic_computed_fields__", _MISSING) is not computed
                or computed
                or any(type(name) is not str for name in fields)
                or tuple(fields) != tuple(item[0] for item in specs)
                or not all(getattr_static(o, n, _MISSING) is v for o, n, v in methods)
            ):
                return False
            for name, field, annotation, excluded, conditional in specs:
                if (
                    fields[name] is not field
                    or type(field) is not FieldInfo
                    or field.annotation is not annotation
                    or field.exclude is not excluded
                    or field.exclude_if is not conditional
                ):
                    return False
        return True

    def matches(self, value: object) -> bool | None:
        if not self.current():
            return None
        seen: set[int] = set()

        def compare(value: object, pattern: Any) -> bool:
            if self.candidate and type(pattern[0]) is tuple:
                raw, fieldset = pattern
                if type(value) is not raw[1]:
                    return False
                try:
                    actual = _FIELDSET.__get__(value, raw[1])
                except AttributeError:
                    return False
                if (
                    type(actual) is not set
                    or len(actual) != len(fieldset)
                    or any(type(key) is not str for key in actual)
                    or actual != set(fieldset)
                ):
                    return False
                pattern = raw
            kind = pattern[0]
            if kind == "model":
                model = pattern[1]
                if type(value) is not model or id(value) in seen:
                    return False
                seen.add(id(value))
                try:
                    values = _VALUES.__get__(value, model)
                    private = _PRIVATE.__get__(value, model)
                    extra = _EXTRA.__get__(value, model)
                except AttributeError:
                    return False
                for actual, expected in ((private, pattern[2]), (extra, pattern[3])):
                    if expected == "none":
                        if actual is not None:
                            return False
                    elif type(actual) is not dict or actual:
                        return False
                children = pattern[4]
                if (
                    type(values) is not dict
                    or len(values) != len(children)
                    or any(type(key) is not str for key in values)
                ):
                    return False
                return all(
                    name in values and compare(values[name], child) for name, child in children
                )
            if kind == "tuple":
                if (
                    type(value) is not tuple
                    or len(value) != len(pattern[1])
                    or value
                    and id(value) in seen
                ):
                    return False
                if value:
                    seen.add(id(value))
                return all(
                    compare(child, expected)
                    for child, expected in zip(value, pattern[1], strict=True)
                )
            if type(value) is not _SCALARS[kind]:
                return False
            if kind == "none":
                return value is None
            if kind in ("int", "str", "bytes", "bool"):
                return bool(value == pattern[1])
            if kind == "date":
                assert type(value) is date
                return bool((value.year, value.month, value.day) == pattern[1:])
            # Preserve exact Decimal representation, timezone/fold and unsupported-zone rules.
            return bool(original._Snapshot().scalar(value) == pattern)

        try:
            result = compare(value, self.snapshot)
        except (AttributeError, TypeError, ValueError, RecursionError):
            return None
        return result if self.current() else None


def prepare_snapshot_match(
    snapshot: object,
    value: object,
    expected: type[Any],
    *,
    candidate: bool = False,
    scanner: type[original._Snapshot] = original._Snapshot,
) -> PreparedSnapshotMatch | None:
    try:
        if not all(
            getattr_static(owner, name, _MISSING) is method for owner, name, method in _ORIGINAL
        ):
            return None
        result = PreparedSnapshotMatch(snapshot, candidate=candidate)
        if not result.current():
            return None
        admitted = scanner().copy(value, expected)
        if admitted is original._UNSUPPORTED or admitted != snapshot or not result.current():
            return None
        return result
    except (AttributeError, TypeError, ValueError, RecursionError):
        return None
