"""One generation's pure checks; never an identity or source-currentness cache."""

from collections.abc import Iterator
from contextlib import contextmanager
from sys import exception
from typing import Any

from fastapi import HTTPException
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.planning_documents.creative_plan_bundle import CreativePairedEvidenceV1
from app.planning_documents.documents import PlanVersion
from app.planning_documents.generation_ports import GenerationEvidence
from app.planning_documents.owner_review_policy import is_owner_review_policy
from app.planning_documents.ports import GenerationTicket
from app.planning_documents.selected_paired_evidence import (
    SelectedPairedEvidenceV1,
    _validate_paired_ticket_pair,
)
from app.planning_documents.selected_plan_bundle import (
    SelectedPlanEvidenceBundleV1,
    _validate_selected_ticket_pair,
)
from app.planning_documents.version_row_admission import _UNSUPPORTED, _Snapshot

_EVENTS = ("before_flush", "after_transaction_create", "after_transaction_end")
_KEY = object()


def _snapshot(value: object, expected: type[Any]) -> object | None:
    try:
        result = _Snapshot().copy(value, expected)
    except (AttributeError, TypeError, ValueError, RecursionError):
        return None
    return None if result is _UNSUPPORTED else result


def _changed() -> HTTPException:
    return HTTPException(409, "prepared generation evidence changed")


class PreparedGenerationChecks:
    """Private explicit single-use scope; snapshots contain no mutable models."""

    def __init__(self, key: object, snapshots: tuple[object, ...]) -> None:
        if key is not _KEY:
            raise _changed()
        self.snapshots: tuple[object, ...] | None = snapshots
        self.used = self.invalid = self.publishing = False
        self.db: Session | None = None
        self.root: Any = None
        self.connection: Any = None
        self.transaction: Any = None
        self.hooks: list[tuple[str, Any]] = []

    def _flush(self, *_args: object) -> None:
        if not self.publishing:
            self.invalid = True
            raise _changed()

    def _transaction(self, db: Session, transaction: Any) -> None:
        # Ordinary publication flushes may create an internal non-nested child.
        if not self.publishing or transaction is self.root or transaction.nested:
            self.invalid = True

    def _current(self, db: Session) -> None:
        connection = self.connection
        if (
            self.invalid
            or self.snapshots is None
            or self.db is not db
            or self.root is None
            or not self.root.is_active
            or db.get_transaction() is not self.root
            or db.in_nested_transaction()
            or db.new
            or db.dirty
            or db.deleted
            or connection is None
            or connection.closed
            or db.connection() is not connection
            or self.transaction is None
            or not self.transaction.is_active
            or connection.get_transaction() is not self.transaction
            or connection.in_nested_transaction()
        ):
            self.invalid = True
            raise _changed()

    def _match(self, db: Session, *operands: tuple[int, object, type[Any]]) -> None:
        self._current(db)
        assert self.snapshots is not None
        for index, value, expected in operands:
            snapshot = _snapshot(value, expected)
            if snapshot is None or snapshot != self.snapshots[index]:
                self.invalid = True
                raise _changed()
        self._current(db)

    def generation(
        self,
        db: Session,
        ticket: GenerationTicket,
        bundle: GenerationEvidence,
        candidate: PlanVersion,
    ) -> None:
        self._match(
            db,
            (0, ticket, GenerationTicket),
            (1, bundle, CreativePairedEvidenceV1),
            (2, candidate, PlanVersion),
        )

    def paired(
        self, db: Session, ticket: GenerationTicket, bundle: SelectedPairedEvidenceV1
    ) -> None:
        self._match(db, (0, ticket, GenerationTicket), (3, bundle, SelectedPairedEvidenceV1))

    def selected(
        self, db: Session, ticket: GenerationTicket, bundle: SelectedPlanEvidenceBundleV1
    ) -> None:
        self._match(db, (0, ticket, GenerationTicket), (4, bundle, SelectedPlanEvidenceBundleV1))

    def publication(
        self,
        db: Session,
        ticket: GenerationTicket,
        bundle: GenerationEvidence,
        candidate: PlanVersion,
    ) -> None:
        self.generation(db, ticket, bundle, candidate)
        self.publishing = True

    @contextmanager
    def use(self, db: Session) -> Iterator["PreparedGenerationChecks | None"]:
        if self.used:
            self.invalid = True
            raise _changed()
        self.used = True
        try:
            # Never modify a listener collection that might be dispatching.
            if any(getattr(db.dispatch, name) for name in _EVENTS):
                yield None
                return
            self.db, self.root = db, db.get_transaction()
            self.connection = db.connection()
            self.transaction = self.connection.get_transaction()
            self._current(db)
            for name in _EVENTS:
                callback = self._flush if name == "before_flush" else self._transaction
                self.hooks.append((name, callback))
                event.listen(db, name, callback)
            yield self
        finally:
            self.close()

    def close(self) -> None:
        original = exception()
        cleanup: BaseException | None = None
        try:
            if self.db is not None:
                for name, callback in reversed(self.hooks):
                    try:
                        if event.contains(self.db, name, callback):
                            event.remove(self.db, name, callback)
                    except BaseException as error:
                        if cleanup is None:
                            cleanup = error
        finally:
            self.hooks.clear()
            self.invalid = self.used = True
            self.snapshots = None
            self.db = self.root = self.connection = self.transaction = None
        if cleanup is not None and original is None:
            raise cleanup


@contextmanager
def use_prepared(
    preparation: PreparedGenerationChecks | None, db: Session
) -> Iterator[PreparedGenerationChecks | None]:
    if preparation is None:
        yield None
    elif type(preparation) is PreparedGenerationChecks:
        with preparation.use(db) as active:
            yield active
    else:
        raise _changed()


def require_prepared(value: PreparedGenerationChecks, db: Session) -> None:
    if type(value) is not PreparedGenerationChecks:
        raise _changed()
    value._current(db)


def prepare_generation_checks(
    ticket: GenerationTicket, bundle: GenerationEvidence, candidate: PlanVersion
) -> PreparedGenerationChecks | None:
    # Exact shape eligibility precedes all preparatory callbacks/validators.
    if type(bundle) is not CreativePairedEvidenceV1 or type(candidate) is not PlanVersion:
        return None
    roots = (
        (ticket, GenerationTicket),
        (bundle, CreativePairedEvidenceV1),
        (candidate, PlanVersion),
    )
    first = tuple(_snapshot(value, expected) for value, expected in roots)
    if any(value is None for value in first):
        return None
    if not is_owner_review_policy(candidate.policy_version, candidate.generator_version):
        return None
    paired, selected = bundle.reporting, bundle.reporting.selected
    extra = (
        _snapshot(paired, SelectedPairedEvidenceV1),
        _snapshot(selected, SelectedPlanEvidenceBundleV1),
    )
    if any(value is None for value in extra):
        return None
    from app.planning_documents import repository

    try:
        checked_ticket, checked_candidate, capability = repository._generation_entry(
            ticket, bundle, candidate
        )
        if (
            _snapshot(checked_ticket, GenerationTicket) != first[0]
            or _snapshot(checked_candidate, PlanVersion) != first[2]
        ):
            return None
        repository._generation_actual_bindings(checked_ticket, bundle, checked_candidate)
        repository._generation_owner_binding(checked_ticket, bundle, checked_candidate, capability)
        checked_paired, paired_ticket = _validate_paired_ticket_pair(paired, ticket)
        checked_selected, selected_ticket = _validate_selected_ticket_pair(selected, ticket)
        if (
            _snapshot(checked_paired, SelectedPairedEvidenceV1) != extra[0]
            or _snapshot(checked_selected, SelectedPlanEvidenceBundleV1) != extra[1]
            or _snapshot(paired_ticket, GenerationTicket) != first[0]
            or _snapshot(selected_ticket, GenerationTicket) != first[0]
        ):
            return None
        selected.assert_ticket(ticket)
        paired.assert_ticket(ticket)
    except (ValueError, HTTPException):
        # Retain original authorization/error precedence and direct-call behavior.
        return None
    if tuple(_snapshot(value, expected) for value, expected in roots) != first:
        return None
    if (
        _snapshot(bundle.reporting, SelectedPairedEvidenceV1),
        _snapshot(bundle.reporting.selected, SelectedPlanEvidenceBundleV1),
    ) != extra:
        return None
    return PreparedGenerationChecks(_KEY, first + extra)
