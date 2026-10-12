"""Injected fixture service; no network default or advertising execution authority."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import Engine, select, update
from sqlalchemy.orm import Session

from app.billing.entitlements import paid_work
from app.customers.access import CustomerPrincipal
from app.customers.identity import IdentityProvider
from app.lifecycle.privacy import database_utc_now, workspace_export_revision
from app.planning_documents import authority, repository
from app.planning_documents.google_budget_events import (
    BudgetEvent,
    BudgetIntent,
    BudgetInvalidationIntent,
    BudgetReadIntent,
    GoogleBudgetHTTPObservationV1,
    GoogleBudgetInvalidationV1,
    GoogleBudgetObservationV1,
    budget_operation,
)
from app.planning_documents.google_budget_hypothesis_comparison import (
    GoogleBudgetHypothesisComparisonV1,
)
from app.planning_documents.google_budget_read import (
    GoogleBudgetReadTicketV1,
    InjectedGoogleSearch,
    read_google_budget,
)
from app.planning_documents.google_budget_read_projection import budget_read_witness
from app.planning_documents.models import PlanEventRow, PlanRequestRow, PlanRow, PlanVersionRow
from app.planning_documents.responses import EventResult
from app.planning_documents.storage import canonical, document_for_row
from app.publication import customer_intents
from app.publication.clock import utc_now
from app.publication.contracts import fingerprint


@contextmanager
def _transaction(engine: Engine) -> Iterator[Session]:
    with Session(engine) as db, db.begin():
        if engine.dialect.name == "sqlite":
            connection = db.connection()
            driver = connection.connection.driver_connection
            assert driver is not None
            if not driver.in_transaction:
                connection.exec_driver_sql("BEGIN")
        yield db


def _prior_row(db: Session, request: BudgetInvalidationIntent) -> PlanEventRow:
    row = db.get(
        PlanEventRow, (request.workspace_id, request.plan_id, request.observation_sequence)
    )
    if (
        row is None
        or row.event_id != request.observation_event_id
        or row.digest != request.observation_digest
    ):
        raise repository.changed("exact budget observation unavailable")
    # Every invalidation names a previous observation using the existing immutable FK.
    invalidated = db.scalar(
        select(PlanEventRow.sequence)
        .where(
            PlanEventRow.workspace_id == request.workspace_id,
            PlanEventRow.plan_id == request.plan_id,
            PlanEventRow.prior_sequence == row.sequence,
            PlanEventRow.kind == "observation",
        )
        .limit(1)
    )
    if invalidated is not None:
        raise repository.changed("budget observation already invalidated")
    return row


class _ReplayNeeded(Exception):
    """Exit every SQL scope before preparing an existing immutable result."""


class GoogleBudgetObservationService:
    def __init__(
        self,
        engine: Engine,
        provider: IdentityProvider,
        search: InjectedGoogleSearch,
        clock: Callable[[], datetime] = utc_now,
        runtime_guard: Callable[[], None] | None = None,
    ) -> None:
        self.engine, self.provider, self.search, self.clock = engine, provider, search, clock
        self.runtime_guard = runtime_guard

    def _guard(self) -> None:
        if self.runtime_guard is not None:
            self.runtime_guard()

    def _replay(
        self, db: Session, principal: CustomerPrincipal, request: BudgetIntent, operation: str
    ) -> EventResult | None:
        receipt = repository.receipt(
            db,
            request.workspace_id,
            principal.user.id,
            operation,
            request.request_key,
            request.digest(),
        )
        if receipt is None:
            return None
        raise _ReplayNeeded

    def _recover(
        self, principal: CustomerPrincipal, request: BudgetIntent, operation: str
    ) -> EventResult:
        def snapshot(
            db: Session, current: CustomerPrincipal
        ) -> tuple[dict[str, Any], dict[str, Any]]:
            receipt = repository.receipt(
                db,
                request.workspace_id,
                current.user.id,
                operation,
                request.request_key,
                request.digest(),
            )
            if receipt is None:
                raise HTTPException(404, "budget observation receipt unavailable")
            if receipt.plan_id != request.plan_id:
                raise repository.changed("request belongs to another plan")
            repository.owned(db, request.workspace_id, request.plan_id)
            row = db.get(
                PlanEventRow, (request.workspace_id, request.plan_id, receipt.event_sequence)
            )
            if row is None:
                raise HTTPException(404, "budget observation receipt unavailable")
            return repository.values(receipt), repository.values(row)

        fact = authority.refresh(principal, self.provider)
        with _transaction(self.engine) as db:
            current = authority.lock(db, principal, request.workspace_id, fact)
            paid_work(db, request.workspace_id, self.clock())
            receipt_values, row_values = snapshot(db, current)
            authority.final(current, fact)
        # Invocation-private preparation; retain every original strict parser/check.
        # No SQL or final identity fact is held during potentially expensive proof work.
        event = document_for_row(PlanEventRow.__tablename__, row_values)
        if not isinstance(
            event,
            (GoogleBudgetObservationV1, GoogleBudgetInvalidationV1, GoogleBudgetHTTPObservationV1),
        ):
            raise repository.changed("budget receipt type mismatch")
        if (
            event.actor_id != principal.user.id
            or event.binding() != request.binding()
            or operation != budget_operation(event)
        ):
            raise repository.changed("budget receipt binding mismatch")
        result = EventResult(event_sequence=row_values["sequence"], event=event)
        fact = authority.refresh(principal, self.provider)
        with _transaction(self.engine) as db:
            current = authority.lock(db, principal, request.workspace_id, fact)
            paid_work(db, request.workspace_id, self.clock())
            if snapshot(db, current) != (receipt_values, row_values):
                raise repository.changed("budget receipt changed during preparation")
            authority.final(current, fact)
            return result

    def observe(self, principal: CustomerPrincipal, request: BudgetReadIntent) -> EventResult:
        self._guard()
        request = BudgetReadIntent.model_validate(request)
        try:
            return self._observe(principal, request)
        except _ReplayNeeded:
            result = self._recover(principal, request, "budget_observe")
            self._guard()
            return result

    def _observe(self, principal: CustomerPrincipal, request: BudgetReadIntent) -> EventResult:
        request = BudgetReadIntent.model_validate(request)
        fact = authority.refresh(principal, self.provider)
        with _transaction(self.engine) as db:
            current = authority.lock(db, principal, request.workspace_id, fact)
            paid_work(db, request.workspace_id, self.clock())
            replay = self._replay(db, current, request, "budget_observe")
            if replay is not None:
                authority.final(current, fact)
                return replay
            plan = repository.owned(db, request.workspace_id, request.plan_id)
            _, document = repository.version(db, plan, request.version)
            request.binding().assert_document(document)
            if (plan.version_head, plan.input_head, plan.event_sequence) != (
                request.version,
                document.inputs.revision,
                request.expected_event_sequence,
            ):
                raise repository.changed("plan version, inputs or event sequence changed")
            proof = document.google_budget_owner_review
            review = (
                next((r for r in proof.reviews if r.action_key == request.action_key), None)
                if proof
                else None
            )
            if review is None:
                raise repository.changed("budget hypothesis unavailable")
            scope = customer_intents.account(db, request.workspace_id, review.intent.account_id)
            now = self.clock()
            ticket = GoogleBudgetReadTicketV1(
                nonce=uuid4().hex,
                binding=request.binding(),
                account=scope,
                privacy_revision=workspace_export_revision(db, request.workspace_id),
                reporting_window=document.inputs.reporting_window,
                prepared_at=now,
                expires_at=now + timedelta(minutes=5),
            )
            if (
                ticket.source_digest() != review.intent.source_binding_digest
                or ticket.privacy_revision
                != review.witness.catalog_evidence.reference.privacy_revision
            ):
                raise repository.changed("budget source or privacy changed")
            repository.check_goal(db, document.inputs, now)
            authority.final(current, fact)
        # No SQL connection/transaction is held across the injected search port.
        self._guard()
        acquired = read_google_budget(ticket, self.search, self.clock)
        witness = budget_read_witness(acquired, review.witness.owner_key)
        compared = self.clock()
        comparison = GoogleBudgetHypothesisComparisonV1(
            document=document,
            binding=request.binding(),
            compared_at=compared,
            privacy_revision=ticket.privacy_revision,
            source_binding_digest=ticket.source_digest(),
            integrity="clear",
            fresh=witness,
        )
        status = comparison.status
        if status == "unavailable":
            raise repository.changed("budget observation unavailable")
        event = GoogleBudgetObservationV1(
            **request.binding().model_dump(),
            event_id=uuid4().hex,
            actor_id=principal.user.id,
            recorded_at=compared,
            comparison=comparison,
            proof=acquired,
            finding=status,
        )
        raw, digest = canonical(event), event.digest()
        fact = authority.refresh(principal, self.provider)
        with _transaction(self.engine) as db:
            current = authority.lock(db, principal, request.workspace_id, fact)
            paid_work(db, request.workspace_id, self.clock())
            replay = self._replay(db, current, request, "budget_observe")
            if replay is not None:
                authority.final(current, fact)
                return replay
            plan = repository.owned(db, request.workspace_id, request.plan_id)
            version = db.get(
                PlanVersionRow, (request.workspace_id, request.plan_id, request.version)
            )
            current_scope = customer_intents.account(
                db, request.workspace_id, review.intent.account_id
            )
            if (
                version is None
                or version.digest != request.document_digest
                or (plan.version_head, plan.input_head)
                != (request.version, document.inputs.revision)
                or current_scope != ticket.account
                or workspace_export_revision(db, request.workspace_id) != ticket.privacy_revision
                or max(self.clock(), database_utc_now(db)) >= ticket.expires_at
            ):
                raise repository.changed("budget observation source, plan or deadline changed")
            repository.check_goal(db, document.inputs, self.clock())
            self._guard()
            result = self._append(db, current, request, event, raw, digest, None, "budget_observe")
            if max(self.clock(), database_utc_now(db)) >= ticket.expires_at:
                raise repository.changed("budget observation expired before commit")
            authority.final(current, fact)
            self._guard()
            return result

    def invalidate_source_change(
        self, principal: CustomerPrincipal, request: BudgetInvalidationIntent
    ) -> EventResult:
        request = BudgetInvalidationIntent.model_validate(request)
        try:
            return self._invalidate_source_change(principal, request)
        except _ReplayNeeded:
            return self._recover(principal, request, "budget_invalidate")

    def _invalidate_source_change(
        self, principal: CustomerPrincipal, request: BudgetInvalidationIntent
    ) -> EventResult:
        """Server-only operation: derive the reason from actual changed local source state."""
        request = BudgetInvalidationIntent.model_validate(request)
        fact = authority.refresh(principal, self.provider)
        with _transaction(self.engine) as db:
            current = authority.lock(db, principal, request.workspace_id, fact)
            paid_work(db, request.workspace_id, self.clock())
            self._replay(db, current, request, "budget_invalidate")
            repository.owned(db, request.workspace_id, request.plan_id)
            original_values = repository.values(_prior_row(db, request))
            authority.final(current, fact)
        original = document_for_row(PlanEventRow.__tablename__, original_values)
        if (
            not isinstance(original, GoogleBudgetObservationV1)
            or original.binding() != request.binding()
        ):
            raise repository.changed("exact budget observation unavailable")
        fact = authority.refresh(principal, self.provider)
        with _transaction(self.engine) as db:
            current = authority.lock(db, principal, request.workspace_id, fact)
            paid_work(db, request.workspace_id, self.clock())
            replay = self._replay(db, current, request, "budget_invalidate")
            if replay is not None:
                authority.final(current, fact)
                return replay
            repository.owned(db, request.workspace_id, request.plan_id)
            if repository.values(_prior_row(db, request)) != original_values:
                raise repository.changed("budget observation changed during preparation")
            scope = customer_intents.account(
                db, request.workspace_id, original.proof.ticket.account.account.account_id
            )
            privacy = workspace_export_revision(db, request.workspace_id)
            source = fingerprint("inlet.planning-source.v1", scope.model_dump(mode="json"))
            if source == original.proof.ticket.source_digest():
                raise repository.changed("budget source has not changed")
            authority.final(current, fact)
        event = GoogleBudgetInvalidationV1(
            **request.binding().model_dump(),
            event_id=uuid4().hex,
            actor_id=principal.user.id,
            recorded_at=self.clock(),
            observation_event_id=request.observation_event_id,
            observation_digest=request.observation_digest,
            observation_sequence=request.observation_sequence,
            observation_recorded_at=original.recorded_at,
            original_source_digest=original.proof.ticket.source_digest(),
            current_account=scope,
            current_source_digest=source,
            privacy_revision=privacy,
        )
        raw, digest = canonical(event), event.digest()
        fact = authority.refresh(principal, self.provider)
        with _transaction(self.engine) as db:
            current = authority.lock(db, principal, request.workspace_id, fact)
            paid_work(db, request.workspace_id, self.clock())
            replay = self._replay(db, current, request, "budget_invalidate")
            if replay is not None:
                authority.final(current, fact)
                return replay
            if repository.values(_prior_row(db, request)) != original_values:
                raise repository.changed("budget observation changed during preparation")
            if (
                customer_intents.account(db, request.workspace_id, scope.account.account_id)
                != scope
                or workspace_export_revision(db, request.workspace_id) != privacy
            ):
                raise repository.changed("invalidation source or privacy changed")
            result = self._append(
                db,
                current,
                request,
                event,
                raw,
                digest,
                request.observation_sequence,
                "budget_invalidate",
            )
            authority.final(current, fact)
            return result

    @staticmethod
    def _append(
        db: Session,
        principal: CustomerPrincipal,
        request: BudgetIntent,
        event: BudgetEvent,
        raw: str,
        digest: str,
        prior: int | None,
        operation: str,
    ) -> EventResult:
        sequence = request.expected_event_sequence + 1
        statement = update(PlanRow).where(
            PlanRow.workspace_id == request.workspace_id,
            PlanRow.id == request.plan_id,
            PlanRow.event_sequence == request.expected_event_sequence,
        )
        if isinstance(event, (GoogleBudgetObservationV1, GoogleBudgetHTTPObservationV1)):
            statement = statement.where(
                PlanRow.version_head == event.version,
                PlanRow.input_head == event.comparison.document.inputs.revision,
            )
        changed = db.scalar(statement.values(event_sequence=sequence).returning(PlanRow.id))
        if changed is None:
            raise repository.changed("budget event sequence changed")
        db.add(
            PlanEventRow(
                workspace_id=request.workspace_id,
                plan_id=request.plan_id,
                sequence=sequence,
                event_id=event.event_id,
                version=request.version,
                action_key=request.action_key,
                action_digest=request.action_digest,
                kind="observation",
                actor_id=principal.user.id,
                recorded_at=event.recorded_at,
                prior_sequence=prior,
                canonical_json=raw,
                digest=digest,
            )
        )
        db.flush()
        db.add(
            PlanRequestRow(
                workspace_id=request.workspace_id,
                actor_id=principal.user.id,
                operation=operation,
                request_key=request.request_key,
                request_digest=request.digest(),
                plan_id=request.plan_id,
                result_kind="event",
                input_revision=None,
                version=None,
                event_sequence=sequence,
            )
        )
        db.flush()
        return EventResult(event_sequence=sequence, event=event)
