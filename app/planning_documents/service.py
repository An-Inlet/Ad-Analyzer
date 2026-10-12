"""Customer planning orchestration; provider reads never span local transactions."""

from collections.abc import Callable, Iterator
from contextlib import closing, contextmanager, nullcontext
from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.campaign_performance.selected_reconstruction import generation_reconstruction
from app.campaign_review.contracts import MediaStore
from app.customers.access import CustomerPrincipal
from app.customers.identity import IdentityProvider
from app.lifecycle.privacy import database_utc_now, workspace_export_revision
from app.planning_documents import authority, input_resolution, repository
from app.planning_documents.catalog_receipts import (
    CatalogReceiptUnavailable,
    ResolvedInputs,
    bind_input_receipts,
    recheck_saved_input_receipts,
    resolve_input_catalogs,
)
from app.planning_documents.composer import (
    DescriptivePlanComposer,
    PlanCompositionUnavailable,
)
from app.planning_documents.creative_basis_reader import PlanningImageUnavailable
from app.planning_documents.creative_finalization import recheck_collected_creative
from app.planning_documents.creative_inputs import validate_creative_policy
from app.planning_documents.creative_paired_reader import OwnedCreativePairedReader
from app.planning_documents.creative_plan_bundle import CreativePairedEvidenceV1
from app.planning_documents.creative_plan_composer import CreativePlanComposer
from app.planning_documents.creative_retained_proof import creative_proof_from_collection
from app.planning_documents.events import CustomerDecision, ManualAssertion, ReadObservedStatus
from app.planning_documents.evidence_adapter import OwnedPlanningEvidenceReader
from app.planning_documents.evidence_local import recheck_local_sources, resolve_source_fences
from app.planning_documents.generation_ports import GenerationEvidence, GenerationEvidenceReader
from app.planning_documents.google_budget_events import (
    GoogleBudgetInvalidationV1,
    GoogleBudgetObservationV1,
)
from app.planning_documents.google_budget_generation_guard import (
    reject_google_budget_generation,
    validate_google_budget_input_policy,
)
from app.planning_documents.models import (
    PlanDependencyRow,
    PlanEventRow,
    PlanRequestRow,
    PlanRow,
    PlanVersionRow,
)
from app.planning_documents.owner_review_generation import recheck_owner_review_input_receipts
from app.planning_documents.owner_review_plan_composer import OwnerReviewPlanComposer
from app.planning_documents.owner_review_policy import is_owner_review_policy
from app.planning_documents.policy_capabilities import (
    reporting_capability,
    ticket_reporting_capability,
)
from app.planning_documents.ports import EvidenceBundle, GenerationTicket, PlanningCompositionPolicy
from app.planning_documents.prepared_generation import prepare_generation_checks, use_prepared
from app.planning_documents.progress_contracts import PlanSalesProgressV1, project_sales_progress
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
from app.planning_documents.selected_composer import SelectedPlanComposer
from app.planning_documents.selected_inputs import reject_legacy_selected
from app.planning_documents.selected_paired_evidence import SelectedPairedEvidenceV1
from app.planning_documents.selected_paired_local import recheck_selected_paired_sources
from app.planning_documents.selected_paired_reader import OwnedSelectedPairedReader
from app.planning_documents.storage import document_for_row
from app.planning_documents.window_adapter import OwnedWindowEvidenceReader
from app.planning_documents.window_composer import WindowPlanComposer
from app.planning_documents.window_evidence import WindowEvidenceBundleV1
from app.planning_documents.window_local import recheck_window_sources
from app.publication.clock import utc_now
from app.shopify.security import utc


@contextmanager
def receipt_errors() -> Iterator[None]:
    try:
        yield
    except CatalogReceiptUnavailable as error:
        raise HTTPException(
            409,
            "The exact catalog selection is unavailable. Read fresh targets and explicitly "
            "save a new input revision before generating a plan.",
        ) from error


def recheck_generation_sources(
    db: Session,
    principal: CustomerPrincipal,
    ticket: GenerationTicket,
    bundle: EvidenceBundle,
    now: datetime,
) -> None:
    recheck_local_sources(db, principal=principal, ticket=ticket, bundle=bundle, now=now)
    recheck_saved_input_receipts(
        db, principal=principal, ticket=ticket, catalogs=bundle.catalogs, now=now
    )


class PlanningDocumentService:
    def __init__(
        self,
        engine: Engine,
        provider: IdentityProvider,
        clock: Callable[[], datetime] = utc_now,
        *,
        policy: PlanningCompositionPolicy | None = None,
        media_store: MediaStore | None = None,
    ) -> None:
        self.engine = engine
        self.provider = provider
        self.clock = clock
        self.policy = (
            PlanningCompositionPolicy.model_validate(policy)
            if policy is not None
            else PlanningCompositionPolicy(
                version="inlet.descriptive-review.v3",
                generator_version="inlet.descriptive-planning.v3",
            )
        )
        if reporting_capability(
            self.policy.version, self.policy.generator_version
        ) != ticket_reporting_capability(self.policy.version, self.policy.digest()):
            raise ValueError("exact canonical planning policy required")
        self.media_store = media_store
        if (
            reporting_capability(self.policy.version, self.policy.generator_version).mode
            in (
                "creative_selected_requested_window",
                "owner_review_creative_selected_requested_window",
            )
            and media_store is None
        ):
            raise ValueError("explicit creative media store required")
        self.creative_composer = CreativePlanComposer()
        self.owner_review_composer = OwnerReviewPlanComposer()
        self.composer = DescriptivePlanComposer()
        self.window_composer = WindowPlanComposer()
        self.selected_composer = SelectedPlanComposer()

    def create(self, principal: CustomerPrincipal, wid: int, request: CreatePlan) -> InputResult:
        request = CreatePlan.model_validate(request)
        with receipt_errors():
            return self._save_inputs(principal, wid, uuid4().hex, request)

    def revise(
        self, principal: CustomerPrincipal, wid: int, plan_id: str, request: EditPlan
    ) -> InputResult:
        request = EditPlan.model_validate(request)
        with receipt_errors():
            return self._save_inputs(principal, wid, plan_id, request)

    def _save_inputs(
        self, principal: CustomerPrincipal, wid: int, plan_id: str, request: CreatePlan | EditPlan
    ) -> InputResult:
        try:
            validate_google_budget_input_policy(
                request.inputs.google_daily_budget_intents,
                self.policy.version,
                self.policy.generator_version,
            )
            if (
                request.inputs.google_daily_budget_intents is not None
                and ticket_reporting_capability(self.policy.version, self.policy.digest()).mode
                not in (
                    "creative_selected_requested_window",
                    "owner_review_creative_selected_requested_window",
                )
            ):
                raise ValueError(
                    "Google budget owner hypotheses require canonical private V5 or V6."
                )
            if (
                is_owner_review_policy(self.policy.version, self.policy.generator_version)
                and request.inputs.google_daily_budget_intents is None
            ):
                raise ValueError("explicit Google budget owner hypotheses required")
            validate_creative_policy(
                request.inputs.creative, self.policy.version, self.policy.generator_version
            )
            reject_legacy_selected(
                request.inputs.selected_reporting,
                self.policy.version,
                self.policy.generator_version,
            )
            if (
                reporting_capability(self.policy.version, self.policy.generator_version).mode
                in (
                    "selected_requested_window",
                    "creative_selected_requested_window",
                    "owner_review_creative_selected_requested_window",
                )
                and request.inputs.selected_reporting is None
            ):
                raise ValueError("explicit selected reporting selectors required")
        except ValueError as error:
            raise repository.changed(str(error)) from error
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
            if request.inputs.creative is not None:
                repository.check_creative_media_references(db, wid, request.inputs.creative)
            parent_digest = None
            if isinstance(request, EditPlan):
                plan = repository.owned(db, wid, plan_id)
                if (plan.input_head, plan.version_head) != (expected_input, expected_version):
                    raise repository.changed("plan input or version changed")
                if expected_version:
                    parent_digest = repository.version(db, plan)[1].digest()
            try:
                prepared = input_resolution.prepare(
                    db,
                    workspace_id=wid,
                    plan_id=plan_id,
                    revision=expected_input + 1,
                    actor_id=current.user.id,
                    intent=request.inputs,
                    now=self.clock(),
                )
            except ValidationError as error:
                raise HTTPException(
                    422,
                    "Planning inputs require past, non-overlapping reporting windows "
                    "and valid confirmed-goal limits.",
                ) from error
            sources = resolve_source_fences(
                db, principal=current, accounts=prepared.accounts, now=self.clock()
            )
            try:
                selected_catalogs = resolve_input_catalogs(
                    db,
                    principal=current,
                    prepared=prepared,
                    intent=request.inputs,
                    sources=sources,
                    now=self.clock(),
                )
            except ValidationError as error:
                raise HTTPException(
                    422,
                    "Planning selections and scenarios must match the "
                    "confirmed budget and constraints.",
                ) from error
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
        try:
            resolved = input_resolution.resolve(
                prepared,
                request.inputs,
                selected_catalogs.catalogs,
                owner_intents=selected_catalogs.owner_intents,
            )
        except ValidationError as error:
            raise HTTPException(
                422,
                "Each planning scenario must reconcile to the confirmed budget and constraints.",
            ) from error
        # Refresh only after all catalog/identity IO; no provider call follows under locks.
        fact = authority.refresh(principal, self.provider)
        with Session(self.engine) as db, db.begin():
            current = authority.lock(db, principal, wid, fact)
            # A concurrent identical request may have committed after preparation.
            # Replay its existing graph before trying to insert immutable input links.
            prior = repository.receipt(
                db, wid, current.user.id, operation, request.request_key, request.digest()
            )
            if prior is not None:
                if isinstance(request, EditPlan) and prior.plan_id != plan_id:
                    raise repository.changed("request key belongs to another plan")
                plan = repository.owned(db, wid, prior.plan_id)
                saved = repository.inputs(db, plan, prior.input_revision)
                authority.final(current, fact)
                return InputResult(plan_id=plan.id, input_revision=saved.revision, inputs=saved)
            if resolved.creative is not None:
                repository.check_creative_media_references(db, wid, resolved.creative)
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
            bind_input_receipts(
                db,
                principal=current,
                resolved=ResolvedInputs(inputs=stored, receipt_bindings=selected_catalogs.bindings),
                sources=actual,
                now=self.clock(),
            )
            authority.final(current, fact)
            return InputResult(
                plan_id=stored.plan_id, input_revision=stored.revision, inputs=stored
            )

    def generate(
        self, principal: CustomerPrincipal, wid: int, plan_id: str, request: GeneratePlan
    ) -> VersionResult:
        with receipt_errors():
            return self._generate(principal, wid, plan_id, request)

    def _generate(
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
            try:
                if is_owner_review_policy(self.policy.version, self.policy.generator_version):
                    if inputs.google_daily_budget_intents is None:
                        raise ValueError("explicit Google budget owner hypotheses required")
                else:
                    reject_google_budget_generation(inputs.google_daily_budget_intents)
                validate_creative_policy(
                    inputs.creative, self.policy.version, self.policy.generator_version
                )
                reject_legacy_selected(
                    inputs.selected_reporting, self.policy.version, self.policy.generator_version
                )
                if (
                    reporting_capability(self.policy.version, self.policy.generator_version).mode
                    in (
                        "selected_requested_window",
                        "creative_selected_requested_window",
                        "owner_review_creative_selected_requested_window",
                    )
                    and inputs.selected_reporting is None
                ):
                    raise ValueError("explicit selected reporting selectors required")
            except ValueError as error:
                raise repository.changed(str(error)) from error

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
        try:
            capability = ticket_reporting_capability(ticket.policy_version, ticket.policy_digest)
        except ValueError as error:
            raise repository.changed("unknown configured planning policy") from error
        if capability.mode in (
            "creative_selected_requested_window",
            "owner_review_creative_selected_requested_window",
        ):
            if self.media_store is None:
                raise repository.changed("explicit creative media store required")
            creative_reader = OwnedCreativePairedReader(
                lambda: Session(self.engine),
                principal=principal,
                provider=self.provider,
                policy=self.policy,
                store=self.media_store,
                clock=self.clock,
            )
            try:
                bundle: GenerationEvidence = creative_reader.collect(ticket)
            except (PlanningImageUnavailable, RetainedSourcesChanged) as error:
                raise repository.changed("creative planning evidence unavailable") from error
        else:
            reader_type = (
                OwnedSelectedPairedReader
                if capability.mode == "selected_requested_window"
                else OwnedWindowEvidenceReader
                if capability.mode == "presence_requested_window"
                else OwnedPlanningEvidenceReader
            )
            reader: GenerationEvidenceReader = reader_type(
                lambda: Session(self.engine),
                principal=principal,
                provider=self.provider,
                policy=self.policy,
                clock=self.clock,
            )
            try:
                bundle = reader.collect(ticket)
            except (ValueError, RetainedSourcesChanged) as error:
                if capability.mode != "selected_requested_window":
                    raise
                raise repository.changed("selected reporting integrity unavailable") from error
        expected_bundle = (
            CreativePairedEvidenceV1
            if capability.mode
            in (
                "creative_selected_requested_window",
                "owner_review_creative_selected_requested_window",
            )
            else SelectedPairedEvidenceV1
            if capability.mode == "selected_requested_window"
            else WindowEvidenceBundleV1
            if capability.mode == "presence_requested_window"
            else EvidenceBundle
        )
        if not isinstance(bundle, expected_bundle):
            raise repository.changed("planning evidence policy differs")
        try:
            bundle.assert_ticket(ticket)
        except ValueError as error:
            raise repository.changed("planning evidence does not match generation") from error
        try:
            if capability.mode in (
                "creative_selected_requested_window",
                "owner_review_creative_selected_requested_window",
            ):
                if not isinstance(bundle, CreativePairedEvidenceV1):
                    raise repository.changed("creative paired evidence required")
                composer = (
                    self.owner_review_composer
                    if capability.mode == "owner_review_creative_selected_requested_window"
                    else self.creative_composer
                )
                candidate = composer.compose(
                    ticket=ticket, evidence=bundle, policy=self.policy, generated_at=self.clock()
                )
            elif capability.mode == "selected_requested_window":
                if not isinstance(bundle, SelectedPairedEvidenceV1):
                    raise repository.changed("selected paired evidence required")
                candidate = self.selected_composer.compose(
                    ticket=ticket, evidence=bundle, policy=self.policy, generated_at=self.clock()
                )
            elif capability.mode == "presence_requested_window":
                if not isinstance(bundle, WindowEvidenceBundleV1):
                    raise repository.changed("requested-window evidence required")
                candidate = self.window_composer.compose(
                    ticket=ticket, evidence=bundle, policy=self.policy, generated_at=self.clock()
                )
            else:
                if not isinstance(bundle, EvidenceBundle):
                    raise repository.changed("legacy reporting evidence required")
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
        if (candidate.policy_version, candidate.generator_version) != (
            self.policy.version,
            self.policy.generator_version,
        ):
            raise repository.changed("configured planning generator changed")
        preparation = prepare_generation_checks(ticket, bundle, candidate)
        with closing(preparation) if preparation is not None else nullcontext():
            fact = authority.refresh(principal, self.provider)

            def final_sources(
                db: Session,
                current: CustomerPrincipal,
                actual_ticket: GenerationTicket,
                actual_bundle: GenerationEvidence,
                now: datetime,
            ) -> None:
                if isinstance(actual_bundle, CreativePairedEvidenceV1):

                    def creative_authorize(db: Session, workspace_id: int, actor: str) -> None:
                        if actor != current.user.id:
                            raise repository.changed("original generation actor changed")
                        authority.lock(db, current, workspace_id, fact)

                    try:
                        recheck_selected_paired_sources(
                            db,
                            principal=current,
                            ticket=actual_ticket,
                            bundle=actual_bundle.reporting,
                            authorize=creative_authorize,
                            clock=self.clock,
                            prepared=active_preparation,
                        )
                        proof = recheck_collected_creative(
                            db,
                            principal=current,
                            ticket=actual_ticket,
                            collection=actual_bundle.creative,
                            now=self.clock(),
                            authorize=creative_authorize,
                        )
                        if (
                            proof
                            != creative_proof_from_collection(actual_bundle.creative, actual_ticket)
                            or proof != candidate.creative_proof
                        ):
                            raise repository.changed(
                                "creative proof differs from collected evidence"
                            )
                        recheck_selected_paired_sources(
                            db,
                            principal=current,
                            ticket=actual_ticket,
                            bundle=actual_bundle.reporting,
                            authorize=creative_authorize,
                            clock=self.clock,
                            prepared=active_preparation,
                        )
                    except (PlanningImageUnavailable, RetainedSourcesChanged) as error:
                        raise repository.changed(
                            "creative planning evidence unavailable"
                        ) from error
                    if capability.mode == "owner_review_creative_selected_requested_window":
                        recheck_owner_review_input_receipts(
                            db,
                            principal=current,
                            ticket=actual_ticket,
                            candidate=candidate,
                            catalogs=actual_bundle.reporting.selected.catalogs,
                            now=self.clock(),
                        )
                    else:
                        recheck_saved_input_receipts(
                            db,
                            principal=current,
                            ticket=actual_ticket,
                            catalogs=actual_bundle.reporting.selected.catalogs,
                            now=self.clock(),
                        )
                elif isinstance(actual_bundle, (WindowEvidenceBundleV1, SelectedPairedEvidenceV1)):

                    def authorize(db: Session, workspace_id: int, actor: str) -> None:
                        if actor != current.user.id:
                            raise repository.changed("original generation actor changed")
                        authority.lock(db, current, workspace_id, fact)

                    if isinstance(actual_bundle, SelectedPairedEvidenceV1):
                        try:
                            recheck_selected_paired_sources(
                                db,
                                principal=current,
                                ticket=actual_ticket,
                                bundle=actual_bundle,
                                authorize=authorize,
                                clock=self.clock,
                            )
                        except (ValueError, RetainedSourcesChanged) as error:
                            raise repository.changed(
                                "selected reporting integrity unavailable"
                            ) from error
                        actual_catalogs = actual_bundle.selected.catalogs
                    else:
                        recheck_window_sources(
                            db,
                            principal=current,
                            ticket=actual_ticket,
                            bundle=actual_bundle,
                            authorize=authorize,
                            clock=self.clock,
                        )
                        actual_catalogs = actual_bundle.catalogs
                    recheck_saved_input_receipts(
                        db,
                        principal=current,
                        ticket=actual_ticket,
                        catalogs=actual_catalogs,
                        now=self.clock(),
                    )
                else:
                    recheck_generation_sources(db, current, actual_ticket, actual_bundle, now)

            with (
                Session(self.engine) as db,
                db.begin(),
                use_prepared(preparation, db) as active_preparation,
                generation_reconstruction(db),
            ):
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
                    recheck=final_sources,
                    prepared=active_preparation,
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

        def snapshot(db: Session) -> tuple[dict[str, Any], ...]:
            repository.owned(db, wid, plan_id)
            query = select(PlanEventRow).where(
                PlanEventRow.workspace_id == wid, PlanEventRow.plan_id == plan_id
            )
            if after is not None:
                query = query.where(PlanEventRow.sequence > after)
            rows = tuple(db.scalars(query.order_by(PlanEventRow.sequence).limit(limit + 1)))
            return tuple(repository.values(row) for row in rows)

        with self._prepared_event_read_session(principal, wid) as (db, _):
            rows = snapshot(db)
        result = EventPage(
            items=tuple(self._event_values_result(row) for row in rows[:limit]),
            next_cursor=str(rows[limit - 1]["sequence"]) if len(rows) > limit else None,
        )
        with self._prepared_event_read_session(principal, wid) as (db, _):
            if snapshot(db) != rows:
                raise repository.changed("event page changed during preparation")
            return result

    @contextmanager
    def _prepared_event_read_session(
        self, principal: CustomerPrincipal, wid: int
    ) -> Iterator[tuple[Session, CustomerPrincipal]]:
        fact = authority.refresh(principal, self.provider)
        with Session(self.engine) as db, db.begin():
            if self.engine.dialect.name == "sqlite":
                connection = db.connection()
                driver = connection.connection.driver_connection
                assert driver is not None
                if not driver.in_transaction:
                    connection.exec_driver_sql("BEGIN")
            current = authority.lock(db, principal, wid, fact, roles=authority.READ_ROLES)
            yield db, current
            authority.final(current, fact)

    @staticmethod
    def _event_result(row: PlanEventRow) -> EventResult:
        return PlanningDocumentService._event_values_result(repository.values(row))

    @staticmethod
    def _event_values_result(row: dict[str, Any]) -> EventResult:
        event = document_for_row(PlanEventRow.__tablename__, row)
        assert isinstance(
            event,
            (
                CustomerDecision,
                ManualAssertion,
                ReadObservedStatus,
                GoogleBudgetObservationV1,
                GoogleBudgetInvalidationV1,
            ),
        )
        return EventResult(event_sequence=row["sequence"], event=event)

    def _budget_request_result(
        self, principal: CustomerPrincipal, wid: int, operation: str, request_key: str
    ) -> EventResult:
        def snapshot(
            db: Session, current: CustomerPrincipal
        ) -> tuple[dict[str, Any], dict[str, Any]]:
            row = db.get(PlanRequestRow, (wid, current.user.id, operation, request_key))
            if row is None:
                raise HTTPException(404, "planning request not found")
            repository.owned(db, wid, row.plan_id)
            if row.result_kind != "event":
                raise repository.changed("budget request result type changed")
            event = db.get(PlanEventRow, (wid, row.plan_id, row.event_sequence))
            if event is None:
                raise HTTPException(404, "planning request result unavailable")
            return repository.values(row), repository.values(event)

        with self._prepared_event_read_session(principal, wid) as (db, current):
            receipt, event = snapshot(db, current)
        result = self._event_values_result(event)
        if (
            not isinstance(result.event, (GoogleBudgetObservationV1, GoogleBudgetInvalidationV1))
            or result.event.actor_id != principal.user.id
            or (operation == "budget_observe")
            != isinstance(result.event, GoogleBudgetObservationV1)
        ):
            raise repository.changed("budget request result binding changed")
        with self._prepared_event_read_session(principal, wid) as (db, current):
            if snapshot(db, current) != (receipt, event):
                raise repository.changed("budget request changed during preparation")
            return result

    def request_result(
        self, principal: CustomerPrincipal, wid: int, operation: str, request_key: str
    ) -> InputResult | VersionResult | EventResult:
        if operation not in {
            "create",
            "revise",
            "generate",
            "decide",
            "assert_applied",
            "budget_observe",
            "budget_invalidate",
        }:
            raise HTTPException(422, "unknown planning operation")
        if not 8 <= len(request_key) <= 128 or any(
            c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
            for c in request_key
        ):
            raise HTTPException(422, "invalid request key")
        if operation in {"budget_observe", "budget_invalidate"}:
            return self._budget_request_result(principal, wid, operation, request_key)
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
                elif utc(self.clock()) >= utc(document.valid_until):
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
                and max(utc(self.clock()), database_utc_now(db)) >= utc(document.valid_until)
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

    def sales_progress(
        self, principal: CustomerPrincipal, wid: int, plan_id: str, version: int
    ) -> PlanSalesProgressV1:
        """Read current closed-day sales for this exact retained goal, with no import IO."""
        from app.goals import service as goals
        from app.goals.models import GoalPreview, GoalRevision
        from app.goals.progress import _read_goal_progress_locked
        from app.goals.schemas import GoalDefinition

        if type(version) is not int or version < 1:
            raise HTTPException(422, "positive version required")
        with self._read_session(principal, wid) as (db, current):
            plan = repository.owned(db, wid, plan_id)
            try:
                _, document = repository.version(db, plan, version)
            except (ValueError, AssertionError) as error:
                raise HTTPException(409, "plan_progress_integrity_unavailable") from error
            ref = document.inputs.goal
            try:
                goal = goals.owned(db, wid, ref.goal_id)
            except HTTPException as error:
                if error.status_code != 404:
                    raise
                return project_sales_progress(
                    document,
                    sales=None,
                    reason="goal_unavailable",
                    as_of=max(self.clock(), database_utc_now(db)),
                )
            db.refresh(goal)
            revision = db.get(GoalRevision, (goal.id, goal.revision), populate_existing=True)
            if revision is None or revision.workspace_id != wid:
                raise HTTPException(409, "plan_progress_integrity_unavailable")
            preview = db.get(GoalPreview, ref.confirmation_reference, populate_existing=True)
            changed = (
                goal.revision != ref.revision
                or goal.confirmed_preview_id != ref.confirmation_reference
                or revision.confirmed_at is None
                or revision.definition is None
                or preview is None
                or (preview.goal_id, preview.revision) != (ref.goal_id, ref.revision)
            )
            if not changed:
                try:
                    definition = GoalDefinition.model_validate(revision.definition)
                except ValueError as error:
                    raise HTTPException(409, "plan_progress_integrity_unavailable") from error
                changed = definition != ref.definition
            if changed:
                return project_sales_progress(
                    document,
                    sales=None,
                    reason="goal_changed",
                    as_of=max(self.clock(), database_utc_now(db)),
                )
            try:
                sales = _read_goal_progress_locked(
                    db, current, wid, ref.goal_id, ref.revision, clock=self.clock
                )
                return project_sales_progress(document, sales=sales, reason=None, as_of=sales.as_of)
            except ValueError as error:
                raise HTTPException(409, "plan_progress_integrity_unavailable") from error

    def export(
        self, principal: CustomerPrincipal, wid: int, plan_id: str, version: int
    ) -> PlanReadResult:
        return self.read(principal, wid, plan_id, version)
