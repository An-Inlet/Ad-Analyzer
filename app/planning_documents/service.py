"""Customer planning orchestration; provider reads never span local transactions."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.customers.access import CustomerPrincipal
from app.customers.identity import IdentityProvider
from app.lifecycle.privacy import database_utc_now, workspace_export_revision
from app.planning_documents import authority, input_resolution, repository
from app.planning_documents.composer import (
    GENERATOR_VERSION,
    POLICY_VERSION,
    DescriptivePlanComposer,
    PlanCompositionUnavailable,
)
from app.planning_documents.events import CustomerDecision, ManualAssertion, ReadObservedStatus
from app.planning_documents.evidence_adapter import OwnedPlanningEvidenceReader
from app.planning_documents.evidence_local import recheck_local_sources, resolve_source_fences
from app.planning_documents.models import (
    PlanDependencyRow,
    PlanEventRow,
    PlanRequestRow,
    PlanRow,
    PlanVersionRow,
)
from app.planning_documents.ports import GenerationTicket, PlanningCompositionPolicy
from app.planning_documents.requests import (
    AssertionIntent,
    CreatePlan,
    DecisionIntent,
    EditPlan,
    GeneratePlan,
)
from app.planning_documents.responses import (
    EventPage,
    EventResult,
    InputResult,
    PlanPage,
    PlanReadResult,
    PlanSummary,
    VersionPage,
    VersionResult,
)
from app.planning_documents.retained_sources import RetainedSourcesChanged, recheck_retained_sources
from app.planning_documents.storage import document_for_row
from app.publication.clock import utc_now
from app.shopify.security import utc


class PlanningDocumentService:
    def __init__(
        self,
        engine: Engine,
        provider: IdentityProvider,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.engine = engine
        self.provider = provider
        self.clock = clock
        self.policy = PlanningCompositionPolicy(
            version=POLICY_VERSION, generator_version=GENERATOR_VERSION
        )
        self.composer = DescriptivePlanComposer()

    def create(self, principal: CustomerPrincipal, wid: int, request: CreatePlan) -> InputResult:
        request = CreatePlan.model_validate(request)
        return self._save_inputs(principal, wid, uuid4().hex, request)

    def revise(
        self, principal: CustomerPrincipal, wid: int, plan_id: str, request: EditPlan
    ) -> InputResult:
        request = EditPlan.model_validate(request)
        return self._save_inputs(principal, wid, plan_id, request)

    def _save_inputs(
        self, principal: CustomerPrincipal, wid: int, plan_id: str, request: CreatePlan | EditPlan
    ) -> InputResult:
        operation = "revise" if isinstance(request, EditPlan) else "create"
        expected_input = request.expected_input_revision if isinstance(request, EditPlan) else 0
        expected_version = request.expected_version if isinstance(request, EditPlan) else 0
        # The caller releases its authentication transaction with loaded detached rows.
        fact = authority.refresh(principal, self.provider)
        with Session(self.engine) as db, db.begin():
            current = authority.lock(db, principal, wid, fact)
            prior = repository.receipt(
                db, wid, current.user.id, operation, request.request_key, request.digest()
            )
            if prior is not None:
                if isinstance(request, EditPlan) and prior.plan_id != plan_id:
                    raise repository.changed("request key belongs to another plan")
                plan = repository.owned(db, wid, prior.plan_id)
                stored = repository.inputs(db, plan, prior.input_revision)
                authority.final(current, fact)
                return InputResult(plan_id=plan.id, input_revision=stored.revision, inputs=stored)
            if (
                request.inputs.exclusions
                or request.inputs.fixed_allocations
                or any(scenario.allocations for scenario in request.inputs.scenario_intents)
            ):
                raise repository.changed(
                    "Target-based planning needs a retained catalog receipt. "
                    "No plan changes were saved."
                )
            parent_digest = None
            if isinstance(request, EditPlan):
                plan = repository.owned(db, wid, plan_id)
                if (plan.input_head, plan.version_head) != (expected_input, expected_version):
                    raise repository.changed("plan input or version changed")
                if expected_version:
                    parent_digest = repository.version(db, plan)[1].digest()
            prepared = input_resolution.prepare(
                db,
                workspace_id=wid,
                plan_id=plan_id,
                revision=expected_input + 1,
                actor_id=current.user.id,
                intent=request.inputs,
                now=self.clock(),
            )
            sources = resolve_source_fences(
                db, principal=current, accounts=prepared.accounts, now=self.clock()
            )
            ticket = GenerationTicket(
                operation_id=uuid4().hex,
                actor_id=current.user.id,
                session_digest=current.session.digest,
                inputs=prepared,
                expected_version=expected_version,
                expected_parent_digest=parent_digest,
                privacy_revision=workspace_export_revision(db, wid),
                sources=sources,
                policy_version=self.policy.version,
                policy_digest=self.policy.digest(),
                prepared_at=self.clock(),
            )
            authority.final(current, fact)
        resolved = input_resolution.resolve(prepared, request.inputs, ())
        # Refresh only after all catalog/identity IO; no provider call follows under locks.
        fact = authority.refresh(principal, self.provider)
        with Session(self.engine) as db, db.begin():
            current = authority.lock(db, principal, wid, fact)
            actual = resolve_source_fences(
                db, principal=current, accounts=prepared.accounts, now=self.clock()
            )
            if (
                actual != ticket.sources
                or workspace_export_revision(db, wid) != ticket.privacy_revision
            ):
                raise repository.changed("planning input source changed")
            stored = repository.save_input(
                db,
                principal=current,
                fact=fact,
                document=resolved,
                expected_input_revision=expected_input,
                expected_version=expected_version,
                request_key=request.request_key,
                request_digest=request.digest(),
                now=self.clock(),
            )
            authority.final(current, fact)
            return InputResult(
                plan_id=stored.plan_id, input_revision=stored.revision, inputs=stored
            )

    def generate(
        self, principal: CustomerPrincipal, wid: int, plan_id: str, request: GeneratePlan
    ) -> VersionResult:
        request = GeneratePlan.model_validate(request)
        fact = authority.refresh(principal, self.provider)
        with Session(self.engine) as db, db.begin():
            current = authority.lock(db, principal, wid, fact)
            plan = repository.owned(db, wid, plan_id)
            prior = repository.receipt(
                db, wid, current.user.id, "generate", request.request_key, request.digest()
            )
            if prior is not None:
                if prior.plan_id != plan_id:
                    raise repository.changed("request key belongs to another plan")
                document = repository.version(db, plan, prior.version)[1]
                authority.final(current, fact)
                return VersionResult(plan_id=plan_id, version=document.version, document=document)
            if (plan.input_head, plan.version_head) != (
                request.expected_input_revision,
                request.expected_version,
            ):
                raise repository.changed("generation input or version changed")
            inputs = repository.inputs(db, plan)
            repository.check_goal(db, inputs, self.clock())
            sources = resolve_source_fences(
                db, principal=current, accounts=inputs.accounts, now=self.clock()
            )
            ticket = GenerationTicket(
                operation_id=uuid4().hex,
                actor_id=current.user.id,
                session_digest=current.session.digest,
                inputs=inputs,
                expected_version=plan.version_head,
                expected_parent_digest=repository.version(db, plan)[1].digest()
                if plan.version_head
                else None,
                privacy_revision=workspace_export_revision(db, wid),
                sources=sources,
                policy_version=self.policy.version,
                policy_digest=self.policy.digest(),
                prepared_at=self.clock(),
            )
            authority.final(current, fact)
        reader = OwnedPlanningEvidenceReader(
            lambda: Session(self.engine),
            principal=principal,
            provider=self.provider,
            policy=self.policy,
            clock=self.clock,
        )
        bundle = reader.collect(ticket)
        bundle.assert_ticket(ticket)
        try:
            candidate = self.composer.compose(
                inputs=inputs,
                evidence=bundle,
                policy=self.policy,
                version=ticket.expected_version + 1,
                parent_digest=ticket.expected_parent_digest,
                generated_by=ticket.actor_id,
                generated_at=self.clock(),
            )
        except PlanCompositionUnavailable as error:
            raise repository.changed(str(error)) from error
        if candidate.generator_version != self.policy.generator_version:
            raise repository.changed("configured planning generator changed")
        fact = authority.refresh(principal, self.provider)
        with Session(self.engine) as db, db.begin():
            document = repository.save_generation(
                db,
                principal=principal,
                fact=fact,
                ticket=ticket,
                bundle=bundle,
                candidate=candidate,
                request_key=request.request_key,
                request_digest=request.digest(),
                now=self.clock(),
                recheck=lambda db, current, ticket, bundle, now: recheck_local_sources(
                    db, principal=current, ticket=ticket, bundle=bundle, now=now
                ),
            )
            return VersionResult(plan_id=plan_id, version=document.version, document=document)

    @contextmanager
    def _read_session(
        self, principal: CustomerPrincipal, wid: int
    ) -> Iterator[tuple[Session, CustomerPrincipal]]:
        fact = authority.refresh(principal, self.provider)
        with Session(self.engine) as db, db.begin():
            current = authority.lock(db, principal, wid, fact, roles=authority.READ_ROLES)
            yield db, current
            authority.final(current, fact)

    @staticmethod
    def _page(limit: int, cursor: str | None, *, numeric: bool) -> str | int | None:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise HTTPException(422, "page limit must be between 1 and 100")
        if cursor is None:
            return None
        if numeric:
            if not cursor.isascii() or not cursor.isdecimal() or len(cursor) > 10:
                raise HTTPException(422, "invalid page cursor")
            value = int(cursor)
            if value < 1:
                raise HTTPException(422, "invalid page cursor")
            return value
        if len(cursor) != 32 or any(c not in "0123456789abcdef" for c in cursor):
            raise HTTPException(422, "invalid page cursor")
        return cursor

    def listing(
        self, principal: CustomerPrincipal, wid: int, *, cursor: str | None = None, limit: int = 20
    ) -> PlanPage:
        after = self._page(limit, cursor, numeric=False)
        with self._read_session(principal, wid) as (db, _):
            query = select(PlanRow).where(PlanRow.workspace_id == wid)
            if after is not None:
                query = query.where(PlanRow.id > after)
            rows = tuple(db.scalars(query.order_by(PlanRow.id).limit(limit + 1)))
            return PlanPage(
                items=tuple(
                    PlanSummary(
                        plan_id=row.id,
                        input_revision=row.input_head,
                        version=row.version_head,
                        event_sequence=row.event_sequence,
                        created_at=utc(row.created_at),
                    )
                    for row in rows[:limit]
                ),
                next_cursor=rows[limit - 1].id if len(rows) > limit else None,
            )

    def history(
        self,
        principal: CustomerPrincipal,
        wid: int,
        plan_id: str,
        *,
        cursor: str | None = None,
        limit: int = 20,
    ) -> VersionPage:
        after = self._page(limit, cursor, numeric=True)
        with self._read_session(principal, wid) as (db, _):
            plan = repository.owned(db, wid, plan_id)
            query = select(PlanVersionRow.version).where(
                PlanVersionRow.workspace_id == wid, PlanVersionRow.plan_id == plan_id
            )
            if after is not None:
                query = query.where(PlanVersionRow.version > after)
            versions = tuple(db.scalars(query.order_by(PlanVersionRow.version).limit(limit + 1)))
            return VersionPage(
                items=tuple(
                    VersionResult(
                        plan_id=plan_id, version=v, document=repository.version(db, plan, v)[1]
                    )
                    for v in versions[:limit]
                ),
                next_cursor=str(versions[limit - 1]) if len(versions) > limit else None,
            )

    def events(
        self,
        principal: CustomerPrincipal,
        wid: int,
        plan_id: str,
        *,
        cursor: str | None = None,
        limit: int = 20,
    ) -> EventPage:
        after = self._page(limit, cursor, numeric=True)
        with self._read_session(principal, wid) as (db, _):
            repository.owned(db, wid, plan_id)
            query = select(PlanEventRow).where(
                PlanEventRow.workspace_id == wid, PlanEventRow.plan_id == plan_id
            )
            if after is not None:
                query = query.where(PlanEventRow.sequence > after)
            rows = tuple(db.scalars(query.order_by(PlanEventRow.sequence).limit(limit + 1)))
            return EventPage(
                items=tuple(self._event_result(row) for row in rows[:limit]),
                next_cursor=str(rows[limit - 1].sequence) if len(rows) > limit else None,
            )

    @staticmethod
    def _event_result(row: PlanEventRow) -> EventResult:
        event = document_for_row(row.__tablename__, repository.values(row))
        assert isinstance(event, (CustomerDecision, ManualAssertion, ReadObservedStatus))
        return EventResult(event_sequence=row.sequence, event=event)

    def request_result(
        self, principal: CustomerPrincipal, wid: int, operation: str, request_key: str
    ) -> InputResult | VersionResult | EventResult:
        if operation not in {"create", "revise", "generate", "decide", "assert_applied"}:
            raise HTTPException(422, "unknown planning operation")
        if not 8 <= len(request_key) <= 128 or any(
            c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
            for c in request_key
        ):
            raise HTTPException(422, "invalid request key")
        with self._read_session(principal, wid) as (db, current):
            row = db.get(PlanRequestRow, (wid, current.user.id, operation, request_key))
            if row is None:
                raise HTTPException(404, "planning request not found")
            plan = repository.owned(db, wid, row.plan_id)
            if row.result_kind == "input":
                document = repository.inputs(db, plan, row.input_revision)
                return InputResult(
                    plan_id=plan.id, input_revision=document.revision, inputs=document
                )
            if row.result_kind == "version":
                version = repository.version(db, plan, row.version)[1]
                return VersionResult(plan_id=plan.id, version=version.version, document=version)
            event = db.get(PlanEventRow, (wid, plan.id, row.event_sequence))
            if event is None:
                raise HTTPException(404, "planning request result unavailable")
            return self._event_result(event)

    def decide(
        self, principal: CustomerPrincipal, wid: int, plan_id: str, request: DecisionIntent
    ) -> EventResult:
        request = DecisionIntent.model_validate(request)
        event = CustomerDecision(
            workspace_id=wid,
            plan_id=plan_id,
            version=request.expected_version,
            document_digest=request.document_digest,
            action_key=request.action_key,
            action_digest=request.action_digest,
            event_id=uuid4().hex,
            actor_id=principal.user.id,
            recorded_at=self.clock(),
            decision=request.decision,
            reason=request.reason,
            supersedes_event_id=request.supersedes_event_id,
        )
        return self._save_event(principal, event, request)

    def assert_applied(
        self, principal: CustomerPrincipal, wid: int, plan_id: str, request: AssertionIntent
    ) -> EventResult:
        request = AssertionIntent.model_validate(request)
        event = ManualAssertion(
            workspace_id=wid,
            plan_id=plan_id,
            version=request.expected_version,
            document_digest=request.document_digest,
            action_key=request.action_key,
            action_digest=request.action_digest,
            event_id=uuid4().hex,
            actor_id=principal.user.id,
            recorded_at=self.clock(),
            assertion=request.assertion,
            reported_applied_at=request.reported_applied_at,
            statement=request.statement,
            supersedes_event_id=request.supersedes_event_id,
        )
        return self._save_event(principal, event, request)

    def _save_event(
        self,
        principal: CustomerPrincipal,
        event: CustomerDecision | ManualAssertion,
        request: DecisionIntent | AssertionIntent,
    ) -> EventResult:
        fact = authority.refresh(principal, self.provider)
        with Session(self.engine) as db, db.begin():
            sequence, result = repository.save_event(
                db,
                principal=principal,
                fact=fact,
                event=event,
                expected_sequence=request.expected_event_sequence,
                request_key=request.request_key,
                request_digest=request.digest(),
                now=self.clock(),
            )
            return EventResult(event_sequence=sequence, event=result)

    def read(
        self, principal: CustomerPrincipal, wid: int, plan_id: str, version: int | None = None
    ) -> PlanReadResult:
        if version is not None and (type(version) is not int or version < 1):
            raise HTTPException(422, "positive version required")
        with self._read_session(principal, wid) as (db, current):
            plan = repository.owned(db, wid, plan_id)
            inputs = repository.inputs(db, plan)
            document = None
            freshness = "not_generated"
            reasons: tuple[str, ...] = ()
            selected = version if version is not None else plan.version_head
            if selected:
                _, document = repository.version(db, plan, selected)
                if document.inputs != inputs:
                    freshness, reasons = (
                        "input_changed",
                        ("Current plan inputs differ from this version.",),
                    )
                elif self.clock() >= document.valid_until:
                    freshness, reasons = (
                        "expired",
                        ("The retained source observation has expired.",),
                    )
                else:
                    try:
                        repository.check_goal(db, inputs, self.clock())
                    except HTTPException as error:
                        if error.status_code not in (404, 409):
                            raise
                        freshness, reasons = (
                            "goal_changed",
                            ("The confirmed goal or its source has changed.",),
                        )
                    else:
                        dependencies = tuple(
                            db.scalars(
                                select(PlanDependencyRow).where(
                                    PlanDependencyRow.workspace_id == wid,
                                    PlanDependencyRow.plan_id == plan_id,
                                    PlanDependencyRow.version == selected,
                                )
                            )
                        )
                        try:
                            recheck_retained_sources(
                                db,
                                principal=current,
                                document=document,
                                dependencies=dependencies,
                                now=self.clock(),
                            )
                        except RetainedSourcesChanged as error:
                            freshness, reasons = "source_changed", (error.reason,)
                        else:
                            freshness = "current"
            if (
                document is not None
                and freshness == "current"
                and max(self.clock(), database_utc_now(db)) >= document.valid_until
            ):
                freshness, reasons = "expired", ("The retained source observation has expired.",)
            return PlanReadResult.model_validate(
                dict(
                    plan_id=plan_id,
                    input_revision=inputs.revision,
                    version=selected,
                    event_sequence=plan.event_sequence,
                    created_at=utc(plan.created_at),
                    inputs=inputs,
                    document=document,
                    freshness=freshness,
                    reasons=reasons,
                )
            )

    def export(
        self, principal: CustomerPrincipal, wid: int, plan_id: str, version: int
    ) -> PlanReadResult:
        return self.read(principal, wid, plan_id, version)
