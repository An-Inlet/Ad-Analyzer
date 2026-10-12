"""Invocation-local pure replay after fresh SQL values; never a currentness cache."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from datetime import date
from inspect import getattr_static
from types import FunctionType
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ads.enums import AdvertisingPlatform
from app.ads.models import Campaign
from app.campaign_performance import capture_settings, presence_contracts, selected_contracts
from app.campaign_performance.selected_contracts import SelectedCaptureV1
from app.campaign_performance.selected_inert import _MODELS, _inert_capture
from app.campaign_performance.selected_models import SelectedCaptureRow, SelectedFactRow

_HEADER = (
    "id",
    "workspace_id",
    "account_id",
    "connection_id",
    "selection_id",
    "selection_digest",
    "completion_id",
    "request_digest",
    "fact_count",
    "canonical_json",
    "payload_digest",
    "payload_bytes",
)
_FACT = (
    "capture_id",
    "campaign_id",
    "metric_date",
    "workspace_id",
    "account_id",
    "native_campaign_id",
    "canonical_json",
    "payload_digest",
    "payload_bytes",
)
_CAMPAIGN = ("id", "account_id", "external_campaign_id", "platform")
# These are admission limits for an optional optimization, not product limits.
# Units conservatively estimate raw snapshot storage, not total Python heap bytes.
# Fact/entry/schema bounds also bound copied model graphs; capacity falls back.
_MAX_FACTS = 512
_MAX_ENTRIES = 20
_MAX_UNITS = 4 * 1024 * 1024
_COPY = BaseModel.__deepcopy__
_SCHEMAS = tuple((m, m.__pydantic_validator__, m.__pydantic_serializer__) for m in _MODELS)
_FUNCTIONS = tuple(
    (module, name, value)
    for module in (capture_settings, presence_contracts, selected_contracts)
    for name, value in vars(module).items()
    if type(value) is FunctionType
)
_MISSING = object()
_ORM_FIELDS = tuple(
    (model, name, getattr_static(model, name, _MISSING))
    for model, fields in (
        (SelectedCaptureRow, _HEADER),
        (SelectedFactRow, _FACT),
        (Campaign, _CAMPAIGN),
    )
    for name in fields
)
_METHODS = tuple(
    (model, name, getattr_static(model, name, _MISSING))
    for model in _MODELS
    for name in set(
        (
            "model_validate",
            "model_validate_json",
            "model_dump",
            "model_dump_json",
            "__deepcopy__",
            "__getattribute__",
        )
    )
    | set(model.model_fields)
    | {
        name
        for name, value in vars(model).items()
        if type(value) in (FunctionType, classmethod, staticmethod, property)
    }
)
_ACTIVE: ContextVar["_Replay | None"] = ContextVar("selected_reconstruction", default=None)
Decoder = Callable[
    [SelectedCaptureRow, list[SelectedFactRow], dict[int, Campaign], int, int], SelectedCaptureV1
]


def _contracts_unchanged() -> bool:
    return (
        getattr_static(BaseModel, "__deepcopy__", _MISSING) is _COPY
        and all(
            getattr_static(model, "__pydantic_validator__", _MISSING) is validator
            and getattr_static(model, "__pydantic_serializer__", _MISSING) is serializer
            and getattr_static(model, "__deepcopy__", _MISSING) is _COPY
            for model, validator, serializer in _SCHEMAS
        )
        and all(getattr(module, name, None) is value for module, name, value in _FUNCTIONS)
        and all(
            getattr_static(model, name, _MISSING) is value
            for model, name, value in (*_METHODS, *_ORM_FIELDS)
        )
    )


def _snapshot(
    header: SelectedCaptureRow,
    rows: list[SelectedFactRow],
    campaigns: dict[int, Campaign],
    wid: int,
    aid: int,
) -> tuple[tuple[Any, ...], int] | None:
    # No repr/serialization/copy callbacks or deferred ORM loads. Strings and dates
    # are immutable. Only values already loaded by the original reads are admitted.
    if type(wid) is not int or type(aid) is not int or len(rows) > _MAX_FACTS:
        return None
    units = 0

    def values(row: Any, expected: type[Any], names: tuple[str, ...]) -> tuple[Any, ...] | None:
        nonlocal units
        if type(row) is not expected:
            return None
        resident = object.__getattribute__(row, "__dict__")
        result = []
        for name in names:
            if name not in resident:
                return None
            value = resident[name]
            if type(value) is AdvertisingPlatform:
                value = value.value
            if type(value) is str:
                units += 4 * len(value) + 64
            elif type(value) is int or type(value) is date:
                units += 64
            else:
                return None
            if units > _MAX_UNITS:
                return None
            result.append(value)
        return tuple(result)

    h = values(header, SelectedCaptureRow, _HEADER)
    if h is None:
        return None
    facts = []
    for row in rows:
        item = values(row, SelectedFactRow, _FACT)
        if item is None:
            return None
        facts.append(item)
    members = []
    # Query order for DISTINCT campaign rows is unspecified; exact identity/value
    # membership, not incidental result order, is the dependency.
    if any(type(key) is not int for key in campaigns) or len(campaigns) > _MAX_FACTS:
        return None
    for key in sorted(campaigns):
        item = values(campaigns[key], Campaign, _CAMPAIGN)
        if item is None:
            return None
        members.append((key, item))
    return (wid, aid, h, tuple(facts), tuple(members)), units


class _Replay:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.root = db.get_transaction()
        self.connection: Any = None
        self.transaction: Any = None
        self.entries: dict[tuple[int, int, str], tuple[tuple[Any, ...], SelectedCaptureV1]] = {}
        self.units = 0
        self.closed = False

    def current(self, db: Session) -> bool:
        if (
            self.closed
            or db is not self.db
            or type(db) is not Session
            or self.root is None
            or not self.root.is_active
            or db.get_transaction() is not self.root
            or db.in_nested_transaction()
            or db.new
            or db.dirty
            or db.deleted
        ):
            self.close()
            return False
        # First use occurs only after the original three SQL reads have acquired
        # a connection. Entering the generation scope does not start DB work.
        if self.connection is None:
            self.connection = db.connection()
            self.transaction = self.connection.get_transaction()
        valid = (
            not self.connection.closed
            and db.connection() is self.connection
            and self.transaction is not None
            and self.transaction.is_active
            and self.connection.get_transaction() is self.transaction
            and not self.connection.in_nested_transaction()
        )
        if not valid:
            self.close()
        return bool(valid)

    def close(self) -> None:
        self.closed = True
        self.entries.clear()
        self.units = 0


@contextmanager
def generation_reconstruction(db: Session) -> Iterator[None]:
    """One generation's exact transaction; nested use never shares a cache."""
    replay = _Replay(db)
    token = _ACTIVE.set(replay)
    try:
        yield
    finally:
        replay.close()
        _ACTIVE.reset(token)


def reconstruct(
    db: Session,
    header: SelectedCaptureRow,
    rows: list[SelectedFactRow],
    campaigns: dict[int, Campaign],
    wid: int,
    aid: int,
    decoder: Decoder,
) -> tuple[SelectedCaptureV1, Callable[[], None]]:
    replay = _ACTIVE.get()
    if replay is None or not replay.current(db) or not _contracts_unchanged():
        return decoder(header, rows, campaigns, wid, aid), _noop
    # Storage helper overrides retain their original behavior, including callbacks.
    from app.campaign_performance import selected_storage as storage

    if any(getattr(storage, name) is not value for name, value in storage._PURE_RECONSTRUCTION):
        return decoder(header, rows, campaigns, wid, aid), _noop
    captured = _snapshot(header, rows, campaigns, wid, aid)
    if captured is None:
        return decoder(header, rows, campaigns, wid, aid), _noop
    snapshot, units = captured
    key = wid, aid, header.id
    prior = replay.entries.get(key)
    if prior is not None and snapshot == prior[0]:
        # Retained graph never escapes. Exact audited types make copying inert.
        return deepcopy(prior[1]), _noop
    result = decoder(header, rows, campaigns, wid, aid)
    if (
        not replay.current(db)
        or not _contracts_unchanged()
        or not _inert_capture(result)
        or key in replay.entries
        or len(replay.entries) >= _MAX_ENTRIES
        or replay.units + units > _MAX_UNITS
    ):
        return result, _noop
    owned = deepcopy(result)

    def promote() -> None:
        # Caller invokes only after both fresh historical dependencies validate.
        if (
            _ACTIVE.get() is replay
            and replay.current(db)
            and key not in replay.entries
            and len(replay.entries) < _MAX_ENTRIES
            and replay.units + units <= _MAX_UNITS
        ):
            replay.entries[key] = snapshot, owned
            replay.units += units

    return result, promote


def _noop() -> None:
    pass
