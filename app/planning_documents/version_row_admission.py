"""One version read's immutable admission; never a source/authority cache.

All unsupported values select the original decoder. Public row and historical
validators remain responsible for errors; this module confers no authorization.
"""

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal
from sys import exception
from types import UnionType
from typing import Annotated, Any, Literal, Union, cast, get_args, get_origin
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, BaseModel
from pydantic_core import TzInfo
from sqlalchemy import event
from sqlalchemy.engine import Connection
from sqlalchemy.orm import ORMExecuteState, Session

from app.planning_documents.documents import PlanVersion
from app.planning_documents.owner_review_policy import is_owner_review_policy

_MAX_NODES = 100_000
_MAX_DEPTH = 128
_MAX_BYTES = 8 * 1024 * 1024
_MODEL_VALUES = BaseModel.__dict__["__dict__"]
_MODEL_PRIVATE = BaseModel.__dict__["__pydantic_private__"]
_MODEL_EXTRA = BaseModel.__dict__["__pydantic_extra__"]
_DATETIME_ZONE = datetime.__dict__["tzinfo"]
_UNSUPPORTED = object()
_ROW_FIELDS = (
    "workspace_id",
    "plan_id",
    "version",
    "input_revision",
    "parent_digest",
    "generator_version",
    "policy_version",
    "actor_id",
    "generated_at",
    "valid_until",
    "privacy_revision",
    "canonical_json",
    "digest",
)
_ROW_INTS = frozenset({"workspace_id", "version", "input_revision", "privacy_revision"})
_ROW_DATES = frozenset({"generated_at", "valid_until"})


class _Snapshot:
    """Bounded local copier. Snapshots contain no model/mutable-container values."""

    def __init__(self) -> None:
        self.nodes = 0
        self.bytes = 0
        self.seen: set[int] = set()

    def charge(self, size: int = 32) -> bool:
        self.nodes += 1
        self.bytes += size
        return self.nodes <= _MAX_NODES and self.bytes <= _MAX_BYTES

    def scalar(self, value: object) -> object:
        kind = type(value)
        if kind is str:
            text_value = cast(str, value)
            if len(text_value) > _MAX_BYTES or not self.charge(
                len(text_value.encode("utf-8", errors="surrogatepass")) + 32
            ):
                return _UNSUPPORTED
            return ("str", text_value)
        if kind is bytes:
            bytes_value = cast(bytes, value)
            if not self.charge(len(bytes_value) + 32):
                return _UNSUPPORTED
            return ("bytes", bytes_value)
        if not self.charge():
            return _UNSUPPORTED
        if value is None:
            return ("none",)
        if kind is bool:
            return ("bool", value)
        if kind is int:
            integer_value = cast(int, value)
            if integer_value.bit_length() > _MAX_BYTES * 8:
                return _UNSUPPORTED
            self.bytes += (integer_value.bit_length() + 7) // 8
            return ("int", integer_value) if self.bytes <= _MAX_BYTES else _UNSUPPORTED
        if kind is date:
            date_value = cast(date, value)
            return ("date", date_value.year, date_value.month, date_value.day)
        if kind is Decimal:
            decimal_value = cast(Decimal, value)
            if not decimal_value.is_finite() or Decimal.__sizeof__(decimal_value) > 4096:
                return _UNSUPPORTED
            parts = decimal_value.as_tuple()
            self.bytes += len(parts.digits) * 8
            return (
                ("decimal", parts.sign, parts.digits, parts.exponent)
                if self.bytes <= _MAX_BYTES
                else _UNSUPPORTED
            )
        if kind is datetime:
            datetime_value = cast(datetime, value)
            zone = _DATETIME_ZONE.__get__(datetime_value, datetime)
            if zone is None:
                key: object = ("naive",)
            elif type(zone) is timezone:
                offset = datetime_value.utcoffset()
                name = self.scalar(datetime_value.tzname())
                if name is _UNSUPPORTED:
                    return _UNSUPPORTED
                key = ("timezone", offset, name)
            elif type(zone) is TzInfo:
                key = ("pydantic_timezone", datetime_value.utcoffset())
            elif type(zone) is ZoneInfo:
                first = datetime_value.replace(fold=0).utcoffset()
                second = datetime_value.replace(fold=1).utcoffset()
                if first != second:
                    return _UNSUPPORTED
                name = self.scalar(zone.key)
                if name is _UNSUPPORTED:
                    return _UNSUPPORTED
                key = ("zoneinfo", name, first)
            else:
                return _UNSUPPORTED
            if not self.charge(192):
                return _UNSUPPORTED
            return (
                "datetime",
                datetime_value.year,
                datetime_value.month,
                datetime_value.day,
                datetime_value.hour,
                datetime_value.minute,
                datetime_value.second,
                datetime_value.microsecond,
                datetime_value.fold,
                key,
            )
        return _UNSUPPORTED

    def copy(self, value: object, expected: Any, depth: int = 0) -> object:
        if depth > _MAX_DEPTH or not self.charge():
            return _UNSUPPORTED
        origin = get_origin(expected)
        args = get_args(expected)
        if origin is Annotated:
            return self.copy(value, args[0], depth + 1)
        if origin in (Union, UnionType):
            # Choose by exact outer shape only; no speculative copying/callbacks.
            options = [a for a in args if self.matches(value, a)]
            if len(options) != 1:
                return _UNSUPPORTED
            return self.copy(value, options[0], depth + 1)
        if origin is Literal:
            if not any(
                type(a) in (str, int, bool, type(None)) and type(value) is type(a) and value == a
                for a in args
            ):
                return _UNSUPPORTED
            return self.scalar(value)
        if origin is tuple:
            if type(value) is not tuple or len(value) > _MAX_NODES - self.nodes:
                return _UNSUPPORTED
            if value and id(value) in self.seen:
                return _UNSUPPORTED
            if value:
                self.seen.add(id(value))
            if len(args) == 2 and args[1] is Ellipsis:
                types = (args[0],) * len(value)
            elif len(args) == len(value):
                types = args
            else:
                return _UNSUPPORTED
            copied = []
            for child, annotation in zip(value, types, strict=True):
                item = self.copy(child, annotation, depth + 1)
                if item is _UNSUPPORTED:
                    return _UNSUPPORTED
                copied.append(item)
            return ("tuple", tuple(copied))
        if isinstance(expected, type) and issubclass(expected, BaseModel):
            if type(value) is not expected or expected.__eq__ is not BaseModel.__eq__:
                return _UNSUPPORTED
            if type(expected).__eq__ is not type.__eq__ or id(value) in self.seen:
                return _UNSUPPORTED
            self.seen.add(id(value))
            values = _MODEL_VALUES.__get__(value, expected)
            private = _MODEL_PRIVATE.__get__(value, expected)
            extra = _MODEL_EXTRA.__get__(value, expected)
            if (
                type(values) is not dict
                or private is not None
                and (type(private) is not dict or private)
                or extra is not None
                and (type(extra) is not dict or extra)
            ):
                return _UNSUPPORTED
            fields = expected.model_fields
            if (
                expected.model_computed_fields
                or len(values) != len(fields)
                or len(fields) > _MAX_NODES - self.nodes
                or any(type(k) is not str or k not in fields for k in values)
            ):
                return _UNSUPPORTED
            copied = []
            for name, field in fields.items():
                if field.exclude or field.exclude_if is not None:
                    return _UNSUPPORTED
                if not self.charge(len(name.encode("utf-8", errors="surrogatepass")) + 32):
                    return _UNSUPPORTED
                item = self.copy(values[name], field.annotation, depth + 1)
                if item is _UNSUPPORTED:
                    return _UNSUPPORTED
                copied.append((name, item))
            # Retain exact declared CLASS identity, never a model instance. Its
            # metaclass equality was checked above to be builtin type equality.
            return (
                "model",
                expected,
                "none" if private is None else "empty_dict",
                "none" if extra is None else "empty_dict",
                tuple(copied),
            )
        if self.matches(value, expected):
            return self.scalar(value)
        return _UNSUPPORTED

    @staticmethod
    def matches(value: object, expected: Any) -> bool:
        origin = get_origin(expected)
        if origin is Annotated:
            return _Snapshot.matches(value, get_args(expected)[0])
        if origin is Literal:
            return any(
                type(a) in (str, int, bool, type(None)) and type(value) is type(a) and value == a
                for a in get_args(expected)
            )
        if origin is tuple:
            return type(value) is tuple
        if expected is AwareDatetime:
            return type(value) is datetime
        return type(value) is expected


def _snapshot_version(document: PlanVersion, scan: _Snapshot | None = None) -> object | None:
    snapshot = (scan if scan is not None else _Snapshot()).copy(document, PlanVersion)
    return None if snapshot is _UNSUPPORTED else snapshot


def _snapshot_row(row: Mapping[str, Any], scan: _Snapshot | None = None) -> object | None:
    # Callers copy the actual SQL mapping to a plain dictionary at the original
    # decoder position. No user mapping methods are used on the optimized path.
    if type(row) is not dict or any(type(key) is not str for key in row):
        return None
    scan = scan if scan is not None else _Snapshot()
    values = []
    for key in _ROW_FIELDS:
        if key not in row:
            return None
        value = row[key]
        expected = int if key in _ROW_INTS else datetime if key in _ROW_DATES else str
        if (value is None and key == "parent_digest") or type(value) is expected:
            item = scan.scalar(value)
        else:
            return None
        if item is _UNSUPPORTED:
            return None
        values.append((key, item))
    return tuple(values)


class _VersionRowAdmission:
    """Private, one-shot immutable values and scope; no retained document graph."""

    __slots__ = (
        "db",
        "root",
        "connection",
        "transaction",
        "row",
        "document",
        "consumed",
        "invalid",
        "listening",
        "orm_listening",
        "permitted_statement",
        "permit_active",
        "permit_used",
    )

    def __init__(self, db: Session, connection: Connection, row: object, document: object) -> None:
        self.db: Session | None = db
        self.root = db.get_transaction()
        self.connection: Connection | None = connection
        self.transaction = connection.get_transaction()
        self.row: object | None = row
        self.document: object | None = document
        self.consumed = False
        self.invalid = False
        self.listening = False
        self.orm_listening = False
        self.permitted_statement: object | None = None
        self.permit_active = False
        self.permit_used = False
        try:
            self.listening = True
            event.listen(db, "before_flush", self.invalidate)
            self.orm_listening = True
            event.listen(db, "do_orm_execute", self.orm_read)
        except BaseException:
            self.close()
            raise

    def invalidate(self, *_args: object) -> None:
        self.invalid = True

    @contextmanager
    def reading_statement(self, statement: object) -> Iterator[None]:
        """Permit only the original fresh-row execute, never a query shape."""
        if self.permit_active or self.permit_used:
            self.invalid = True
        self.permit_active = True
        self.permit_used = False
        self.permitted_statement = statement
        try:
            yield
        finally:
            self.permitted_statement = None
            self.permit_active = False
            self.permit_used = True

    def orm_read(self, state: ORMExecuteState) -> None:
        if state.is_orm_statement:
            if (
                self.permit_active
                and not self.permit_used
                and state.statement is self.permitted_statement
            ):
                # Burn before returning into execution/listener callbacks.
                self.permit_used = True
                self.permitted_statement = None
                return
            self.invalid = True

    def current(self, db: Session) -> bool:
        connection = self.connection
        return bool(
            not self.invalid
            and self.db is db
            and self.root is not None
            and db.get_transaction() is self.root
            and self.root.is_active
            and not db.in_nested_transaction()
            and not db.new
            and not db.dirty
            and not db.deleted
            and connection is not None
            and not connection.closed
            and db.connection() is connection
            and self.transaction is not None
            and connection.get_transaction() is self.transaction
            and self.transaction.is_active
            and not connection.in_nested_transaction()
        )

    def close(self) -> None:
        original_error = exception()
        cleanup_error: BaseException | None = None
        db = self.db
        try:
            if db is not None:
                for installed, name, callback in (
                    (self.orm_listening, "do_orm_execute", self.orm_read),
                    (self.listening, "before_flush", self.invalidate),
                ):
                    if installed:
                        try:
                            if event.contains(db, name, callback):
                                event.remove(db, name, callback)
                        except BaseException as error:
                            # Attempt both removals and preserve a pending original
                            # failure. A cleanup-only failure remains observable.
                            if cleanup_error is None:
                                cleanup_error = error
        finally:
            self.listening = self.orm_listening = False
            self.consumed = True
            self.permitted_statement = None
            self.permit_active = False
            self.permit_used = True
            self.row = self.document = None
            self.db = self.root = self.connection = self.transaction = None
        if cleanup_error is not None and original_error is None:
            raise cleanup_error


def _make_version_row_admission(
    *, db: Session, row: Mapping[str, Any], document: PlanVersion
) -> _VersionRowAdmission | None:
    if type(document) is not PlanVersion:
        return None
    # Never modify an event collection that may already be dispatching. This
    # also prevents nested admissions while this proof's listeners are present.
    if db.dispatch.do_orm_execute or db.dispatch.before_flush:
        return None
    scan = _Snapshot()
    row_snapshot = _snapshot_row(row, scan)
    document_snapshot = _snapshot_version(document, scan)
    if row_snapshot is None or document_snapshot is None:
        return None
    raw = _MODEL_VALUES.__get__(document, PlanVersion)
    if not is_owner_review_policy(raw["policy_version"], raw["generator_version"]):
        return None
    root = db.get_transaction()
    if (
        root is None
        or not root.is_active
        or db.in_nested_transaction()
        or db.new
        or db.dirty
        or db.deleted
    ):
        return None
    connection = db.connection()
    transaction = connection.get_transaction()
    if (
        connection.closed
        or transaction is None
        or not transaction.is_active
        or connection.in_nested_transaction()
    ):
        return None
    return _VersionRowAdmission(db, connection, row_snapshot, document_snapshot)


def _matches_admitted_version_row(
    *, db: Session, row: Mapping[str, Any], document: PlanVersion, admission: _VersionRowAdmission
) -> bool | None:
    was_consumed = admission.consumed
    admission.consumed = True
    try:
        if was_consumed or not admission.current(db):
            return None
        scan = _Snapshot()
        actual_row = _snapshot_row(row, scan)
        if actual_row is None or actual_row != admission.row:
            return None
        actual_document = _snapshot_version(document, scan)
        if actual_document is None or actual_document != admission.document:
            return None
        return True
    finally:
        admission.close()
