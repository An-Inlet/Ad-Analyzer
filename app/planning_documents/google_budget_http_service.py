"""Owned mock HTTP observation admission under the original acquisition deadline."""

from collections.abc import Callable
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.billing.entitlements import paid_work
from app.customers.access import CustomerPrincipal
from app.customers.identity import IdentityProvider
from app.lifecycle.privacy import database_utc_now, workspace_export_revision
from app.planning_documents import authority, repository
from app.planning_documents.documents import PlanVersion
from app.planning_documents.google_budget_http_events import (
    BudgetHTTPIntent,
    GoogleBudgetHTTPObservationV1,
    http_budget_witness,
)
from app.planning_documents.google_budget_http_fixture import GoogleBudgetHTTPFixture
from app.planning_documents.google_budget_http_proof import (
    GoogleBudgetHTTPAccount,
    GoogleBudgetHTTPTicketV1,
)
from app.planning_documents.google_budget_hypothesis_comparison import (
    GoogleBudgetHypothesisComparisonV1,
)
from app.planning_documents.google_budget_observation_service import (
    GoogleBudgetObservationService,
    _ReplayNeeded,
    _transaction,
)
from app.planning_documents.models import PlanVersionRow
from app.planning_documents.responses import EventResult
from app.planning_documents.storage import canonical
from app.publication import customer_intents


class GoogleBudgetHTTPService:
    def __init__(
        self,
        engine: Engine,
        provider: IdentityProvider,
        bundle: GoogleBudgetHTTPFixture,
        clock: Callable[[], datetime],
        guard: Callable[[], None],
    ) -> None:
        self.engine, self.provider, self.bundle = engine, provider, bundle
        self.clock, self.guard = clock, guard

        # Share receipt preparation/append only; this port must never acquire v22 data.
        def unavailable(*args: object) -> str:
            raise ValueError("legacy acquisition unavailable")

        self.retained = GoogleBudgetObservationService(engine, provider, unavailable, clock, guard)

    def _current(
        self,
        db: Session,
        req: BudgetHTTPIntent,
        ticket: GoogleBudgetHTTPTicketV1,
        document: PlanVersion,
    ) -> None:
        plan = repository.owned(db, req.workspace_id, req.plan_id)
        version = db.get(PlanVersionRow, (req.workspace_id, req.plan_id, req.version))
        scope = customer_intents.account(db, req.workspace_id, ticket.account.account_id)
        current = GoogleBudgetHTTPAccount(
            workspace_id=scope.workspace_id,
            account_id=scope.account.account_id,
            connection_id=scope.account.connection_id,
            connection_version=scope.connection_version,
            native_customer_id=scope.external_advertiser_id,
            platform=scope.account.platform,
        )
        if (
            version is None
            or version.digest != req.document_digest
            or (plan.version_head, plan.input_head, plan.event_sequence)
            != (req.version, document.inputs.revision, req.expected_event_sequence)
            or current != ticket.account
            or workspace_export_revision(db, req.workspace_id) != ticket.privacy_revision
            or max(self.clock(), database_utc_now(db)) >= ticket.expires_at
        ):
            raise repository.changed("HTTP observation source, plan, privacy or deadline changed")
        repository.check_goal(db, document.inputs, self.clock())

    def observe(self, principal: CustomerPrincipal, request: BudgetHTTPIntent) -> EventResult:
        self.guard()
        req = BudgetHTTPIntent.model_validate(request)
        try:
            return self._observe(principal, req)
        except _ReplayNeeded:
            result = self.retained._recover(principal, req, "budget_http_observe")
            self.guard()
            return result

    def _observe(self, principal: CustomerPrincipal, req: BudgetHTTPIntent) -> EventResult:
        fact = authority.refresh(principal, self.provider)
        with _transaction(self.engine) as db:
            current = authority.lock(db, principal, req.workspace_id, fact)
            paid_work(db, req.workspace_id, self.clock())
            self.retained._replay(db, current, req, "budget_http_observe")
            plan = repository.owned(db, req.workspace_id, req.plan_id)
            _, document = repository.version(db, plan, req.version)
            req.binding().assert_document(document)
            reviews = document.google_budget_owner_review
            review = (
                next((r for r in reviews.reviews if r.action_key == req.action_key), None)
                if reviews
                else None
            )
            if review is None:
                raise repository.changed("budget hypothesis unavailable")
            scope = customer_intents.account(db, req.workspace_id, review.intent.account_id)
            now = self.clock()
            account = GoogleBudgetHTTPAccount(
                workspace_id=scope.workspace_id,
                account_id=scope.account.account_id,
                connection_id=scope.account.connection_id,
                connection_version=scope.connection_version,
                native_customer_id=scope.external_advertiser_id,
                platform=scope.account.platform,
            )
            ticket = GoogleBudgetHTTPTicketV1(
                nonce=uuid4().hex,
                binding=req.binding(),
                account=account,
                source_binding_digest=account.source_digest(),
                privacy_revision=workspace_export_revision(db, req.workspace_id),
                prepared_at=now,
                expires_at=now + timedelta(seconds=60),
            )
            if (
                ticket.source_binding_digest != review.intent.source_binding_digest
                or ticket.privacy_revision
                != review.witness.catalog_evidence.reference.privacy_revision
            ):
                raise repository.changed("budget source or privacy changed")
            self._current(db, req, ticket, document)
            authority.final(current, fact)

        def revalidate(original: GoogleBudgetHTTPTicketV1) -> None:
            self.guard()
            if original != ticket:
                raise repository.changed("HTTP ticket replaced")
            refreshed = authority.refresh(principal, self.provider)
            with _transaction(self.engine) as db:
                active = authority.lock(db, principal, req.workspace_id, refreshed)
                paid_work(db, req.workspace_id, self.clock())
                self._current(db, req, original, document)
                authority.final(active, refreshed)
            self.guard()

        acquired = self.bundle.acquire(ticket, revalidate, self.clock, self.guard)
        witness = http_budget_witness(
            acquired, document.inputs.reporting_window, review.witness.owner_key
        )
        compared = self.clock()
        comparison = GoogleBudgetHypothesisComparisonV1(
            document=document,
            binding=req.binding(),
            compared_at=compared,
            privacy_revision=ticket.privacy_revision,
            source_binding_digest=ticket.source_binding_digest,
            integrity="clear",
            fresh=witness,
        )
        status = comparison.status
        if status == "unavailable":
            raise repository.changed("HTTP budget observation unavailable")
        event = GoogleBudgetHTTPObservationV1(
            **req.binding().model_dump(),
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
            current = authority.lock(db, principal, req.workspace_id, fact)
            paid_work(db, req.workspace_id, self.clock())
            self.retained._replay(db, current, req, "budget_http_observe")
            self._current(db, req, ticket, document)
            self.guard()
            result = self.retained._append(
                db, current, req, event, raw, digest, None, "budget_http_observe"
            )
            if max(self.clock(), database_utc_now(db)) >= ticket.expires_at:
                raise repository.changed("HTTP observation expired before commit")
            authority.final(current, fact)
            self.guard()
            return result
