"""Transaction-local owned plan operations. Callers refresh identity outside locks."""

from collections.abc import Callable
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.billing.entitlements import paid_work
from app.campaign_review.models import MediaObject
from app.commerce.ledger import lock_store
from app.customers.access import CustomerPrincipal
from app.goals import service as goals
from app.goals.models import GoalPreview
from app.goals.schemas import GoalDefinition
from app.lifecycle.privacy import database_utc_now, workspace_export_revision
from app.planning_documents import authority
from app.planning_documents.allocation_currency import check_allocations
from app.planning_documents.authority import IdentityFact
from app.planning_documents.common import fingerprint
from app.planning_documents.composer import targets
from app.planning_documents.context import AccountRef, PlanInputRevision, TargetRef
from app.planning_documents.creative_basis import CreativeInputV1
from app.planning_documents.creative_plan_bundle import CreativePairedEvidenceV1
from app.planning_documents.creative_plan_document import creative_basis_reference
from app.planning_documents.creative_retained_proof import creative_proof_from_collection
from app.planning_documents.documents import PlanVersion
from app.planning_documents.empty_catalog_validation import assert_empty_catalog_bindings
from app.planning_documents.events import CustomerDecision, ManualAssertion
from app.planning_documents.generation_ports import GenerationEvidence
from app.planning_documents.models import (
    PlanDependencyRow,
    PlanEventRow,
    PlanInputRow,
    PlanRequestRow,
    PlanRow,
    PlanVersionRow,
)
from app.planning_documents.owner_review_generation import assert_owner_review_generation_bundle
from app.planning_documents.policy_capabilities import (
    ReportingCapability,
    reporting_capability,
    ticket_reporting_capability,
)
from app.planning_documents.ports import EvidenceBundle, GenerationTicket
from app.planning_documents.prepared_generation import PreparedGenerationChecks, require_prepared
from app.planning_documents.retained_sources import (
    RetainedSourcesChanged,
    capture_retained_sources,
    recheck_retained_sources,
)
from app.planning_documents.selected_paired_evidence import SelectedPairedEvidenceV1
from app.planning_documents.storage import canonical, document_for_row, plan_version_storage_pair
from app.planning_documents.window_evidence import WindowEvidenceBundleV1
from app.publication import customer_intents
from app.shopify.security import ShopifyError, utc


def changed(reason: str) -> HTTPException:
    return HTTPException(409, reason)


def check_creative_media_references(
    db: Session, workspace_id: int, creative: CreativeInputV1
) -> None:
    """New input admission only; caller holds workspace authority, no byte evidence."""
    creative = CreativeInputV1.model_validate(creative)
    for selection in sorted(creative.media_selections, key=lambda item: item.media_id):
        row = db.scalar(
            select(MediaObject)
            .where(MediaObject.workspace_id == workspace_id, MediaObject.id == selection.media_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if row is None or row.sha256 != selection.expected_sha256:
            raise changed("selected creative media unavailable")


def values(row: PlanInputRow | PlanVersionRow | PlanEventRow) -> dict[str, Any]:
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


def owned(db: Session, workspace_id: int, plan_id: str) -> PlanRow:
    item = db.scalar(
        select(PlanRow)
        .where(PlanRow.workspace_id == workspace_id, PlanRow.id == plan_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if item is None:
        raise HTTPException(404, "plan not found")
    return item


def inputs(db: Session, plan: PlanRow, revision: int | None = None) -> PlanInputRevision:
    row = db.get(
        PlanInputRow,
        (plan.workspace_id, plan.id, revision or plan.input_head),
        populate_existing=True,
    )
    if row is None:
        raise HTTPException(404, "plan input not found")
    result = document_for_row(row.__tablename__, values(row))
    assert isinstance(result, PlanInputRevision)
    if result.google_daily_budget_intents is not None:
        from app.planning_documents.catalog_receipts import (
            CatalogReceiptUnavailable,
            validate_retained_input_receipts,
        )

        try:
            validate_retained_input_receipts(db, result)
        except CatalogReceiptUnavailable as error:
            raise changed("The original budget owner input proof is unavailable.") from error
    return result


def version(
    db: Session, plan: PlanRow, revision: int | None = None
) -> tuple[PlanVersionRow, PlanVersion]:
    row = db.get(
        PlanVersionRow,
        (plan.workspace_id, plan.id, revision or plan.version_head),
        populate_existing=True,
    )
    if row is None:
        raise HTTPException(404, "plan version not found")
    stored = values(row)
    result = document_for_row(row.__tablename__, stored)
    assert isinstance(result, PlanVersion)
    if result.selected_reporting_proof is not None:
        from app.planning_documents.selected_plan_history import (
            _validate_selected_plan_history_admitted,
            validate_selected_plan_history,
        )
        from app.planning_documents.version_row_admission import _make_version_row_admission

        admission = _make_version_row_admission(db=db, row=stored, document=result)
        try:
            if admission is None:
                validate_selected_plan_history(db, result)
            else:
                _validate_selected_plan_history_admitted(db, result, admission)
        except ValueError as error:
            raise changed("selected plan historical integrity unavailable") from error
        finally:
            if admission is not None:
                admission.close()
    return row, result


def check_goal(db: Session, document: PlanInputRevision, now: datetime) -> None:
    ref = document.goal
    goal = goals.owned(db, document.workspace_id, ref.goal_id)
    db.refresh(goal)
    goals.expect(goal, ref.revision)
    current = goals.current(db, goal)
    definition = GoalDefinition.model_validate(current.definition)
    preview = db.get(GoalPreview, ref.confirmation_reference, populate_existing=True)
    if (
        goal.confirmed_preview_id != ref.confirmation_reference
        or current.confirmed_at is None
        or preview is None
        or (preview.goal_id, preview.revision) != (ref.goal_id, ref.revision)
        or fingerprint("goal-definition", definition.model_dump(mode="json"))
        != ref.definition_digest
    ):
        raise changed("confirmed goal changed")
    try:
        lock_store(db, definition.store_id, document.workspace_id)
        if goals.assessment(db, goal, now) != "confirmed":
            raise changed("confirmed goal source unavailable")
    except ShopifyError as error:
        raise changed("confirmed goal commerce source unavailable") from error


def check_accounts(db: Session, document: PlanInputRevision) -> None:
    for expected in sorted(document.accounts, key=lambda value: value.account_id):
        scope = customer_intents.account(db, document.workspace_id, expected.account_id)
        actual = AccountRef(
            workspace_id=scope.workspace_id,
            account_id=scope.account.account_id,
            connection_id=scope.account.connection_id,
            platform=scope.account.platform,
            connection_version=scope.connection_version,
        )
        if actual != expected:
            raise changed("selected advertising source changed")


def receipt(
    db: Session, wid: int, actor: str, operation: str, key: str, digest: str
) -> PlanRequestRow | None:
    row = db.get(PlanRequestRow, (wid, actor, operation, key), populate_existing=True)
    if row is not None and row.request_digest != digest:
        raise changed("request key is bound to different input")
    return row


def save_input(
    db: Session,
    *,
    principal: CustomerPrincipal,
    fact: IdentityFact,
    document: PlanInputRevision,
    expected_input_revision: int,
    expected_version: int,
    request_key: str,
    request_digest: str,
    now: datetime,
) -> PlanInputRevision:
    """Internal commit only: document must come from server input resolution, never HTTP."""
    document = PlanInputRevision.model_validate(document)
    current = authority.lock(db, principal, document.workspace_id, fact)
    operation = "create" if expected_input_revision == 0 else "revise"
    prior = receipt(
        db, document.workspace_id, current.user.id, operation, request_key, request_digest
    )
    if prior is not None:
        if operation == "revise" and prior.plan_id != document.plan_id:
            raise changed("request key belongs to another plan")
        plan = owned(db, document.workspace_id, prior.plan_id)
        result = inputs(db, plan, prior.input_revision)
        authority.final(current, fact)
        return result
    if document.created_by != current.user.id or document.revision != expected_input_revision + 1:
        raise changed("input actor or revision mismatch")
    if expected_input_revision == 0:
        if expected_version != 0:
            raise changed("new plan cannot have a prior version")
        plan = PlanRow(
            workspace_id=document.workspace_id,
            id=document.plan_id,
            input_head=1,
            version_head=0,
            event_sequence=0,
            created_by=current.user.id,
            created_at=document.created_at,
        )
        db.add(plan)
        db.flush()
    else:
        plan = owned(db, document.workspace_id, document.plan_id)
        updated = db.scalar(
            update(PlanRow)
            .where(
                PlanRow.workspace_id == document.workspace_id,
                PlanRow.id == document.plan_id,
                PlanRow.input_head == expected_input_revision,
                PlanRow.version_head == expected_version,
            )
            .values(input_head=document.revision)
            .returning(PlanRow.id)
        )
        if updated is None:
            raise changed("plan input or version changed")
    check_goal(db, document, now)
    check_accounts(db, document)
    # Trusted orchestrator compares original source fences before entering this writer.
    authority.final(current, fact)
    db.add(
        PlanInputRow(
            workspace_id=document.workspace_id,
            plan_id=document.plan_id,
            revision=document.revision,
            goal_id=document.goal.goal_id,
            goal_revision=document.goal.revision,
            confirmed_preview_id=document.goal.confirmation_reference,
            definition_digest=document.goal.definition_digest,
            canonical_json=canonical(document),
            digest=document.digest(),
            actor_id=current.user.id,
            created_at=document.created_at,
        )
    )
    db.flush()
    db.add(
        PlanRequestRow(
            workspace_id=document.workspace_id,
            actor_id=current.user.id,
            operation=operation,
            request_key=request_key,
            request_digest=request_digest,
            plan_id=document.plan_id,
            result_kind="input",
            input_revision=document.revision,
            version=None,
            event_sequence=None,
        )
    )
    db.flush()
    check_goal(db, document, max(now, database_utc_now(db)))
    authority.final(current, fact)
    return document


def save_event(
    db: Session,
    *,
    principal: CustomerPrincipal,
    fact: IdentityFact,
    event: CustomerDecision | ManualAssertion,
    expected_sequence: int,
    request_key: str,
    request_digest: str,
    now: datetime,
) -> tuple[int, CustomerDecision | ManualAssertion]:
    event = type(event).model_validate(event)
    current = authority.lock(db, principal, event.workspace_id, fact)
    kind = "decision" if isinstance(event, CustomerDecision) else "assertion"
    operation = "decide" if kind == "decision" else "assert_applied"
    prior_receipt = receipt(
        db, event.workspace_id, current.user.id, operation, request_key, request_digest
    )
    plan = owned(db, event.workspace_id, event.plan_id)
    if prior_receipt is not None:
        if prior_receipt.plan_id != event.plan_id:
            raise changed("request key belongs to another plan")
        row = db.get(
            PlanEventRow, (event.workspace_id, event.plan_id, prior_receipt.event_sequence)
        )
        if row is None:
            raise changed("event receipt unavailable")
        stored = document_for_row(row.__tablename__, values(row))
        assert isinstance(stored, (CustomerDecision, ManualAssertion))
        authority.final(current, fact)
        return row.sequence, stored
    retracting = isinstance(event, ManualAssertion) and event.assertion == "retracted"
    if (
        not retracting and plan.version_head != event.version
    ) or plan.event_sequence != expected_sequence:
        raise changed("plan version or event sequence changed")
    version_row, document = version(db, plan, event.version)
    try:
        event.assert_document(document)
    except ValueError as error:
        raise changed("plan version or action binding changed") from error
    if event.actor_id != current.user.id or (
        not retracting and document.inputs.revision != plan.input_head
    ):
        raise changed("event actor or plan inputs changed")
    if not retracting:
        if version_row.privacy_revision != workspace_export_revision(db, event.workspace_id) or utc(
            now
        ) >= utc(document.valid_until):
            raise changed("plan evidence expired or changed")
        check_goal(db, document.inputs, now)
        check_accounts(db, document.inputs)
        try:
            recheck_retained_sources(
                db,
                principal=current,
                document=document,
                dependencies=tuple(
                    db.scalars(
                        select(PlanDependencyRow).where(
                            PlanDependencyRow.workspace_id == event.workspace_id,
                            PlanDependencyRow.plan_id == event.plan_id,
                            PlanDependencyRow.version == event.version,
                        )
                    )
                ),
                now=max(now, database_utc_now(db)),
            )
        except RetainedSourcesChanged as error:
            raise changed(error.reason) from error
    previous = db.scalar(
        select(PlanEventRow)
        .where(
            PlanEventRow.workspace_id == event.workspace_id,
            PlanEventRow.plan_id == event.plan_id,
            PlanEventRow.version == event.version,
            PlanEventRow.action_key == event.action_key,
            PlanEventRow.kind == kind,
        )
        .order_by(PlanEventRow.sequence.desc())
        .limit(1)
    )
    if event.supersedes_event_id != (previous.event_id if previous else None):
        raise changed("event chain head changed")
    if isinstance(event, ManualAssertion) and event.assertion == "retracted":
        if previous is None:
            raise changed("no manual report to retract")
        old = document_for_row(previous.__tablename__, values(previous))
        if not isinstance(old, ManualAssertion) or old.assertion != "customer_reports_applied":
            raise changed("manual report already retracted")
    authority.final(current, fact)
    if not retracting and max(utc(now), database_utc_now(db)) >= utc(document.valid_until):
        raise changed("plan evidence expired")
    sequence = expected_sequence + 1
    updated = db.scalar(
        update(PlanRow)
        .where(
            PlanRow.workspace_id == event.workspace_id,
            PlanRow.id == event.plan_id,
            PlanRow.event_sequence == expected_sequence,
            PlanRow.version_head == plan.version_head,
        )
        .values(event_sequence=sequence)
        .returning(PlanRow.id)
    )
    if updated is None:
        raise changed("event sequence changed")
    db.add(
        PlanEventRow(
            workspace_id=event.workspace_id,
            plan_id=event.plan_id,
            sequence=sequence,
            event_id=event.event_id,
            version=event.version,
            action_key=event.action_key,
            action_digest=event.action_digest,
            kind=kind,
            actor_id=current.user.id,
            recorded_at=event.recorded_at,
            prior_sequence=previous.sequence if previous else None,
            canonical_json=canonical(event),
            digest=event.digest(),
        )
    )
    db.flush()
    db.add(
        PlanRequestRow(
            workspace_id=event.workspace_id,
            actor_id=current.user.id,
            operation=operation,
            request_key=request_key,
            request_digest=request_digest,
            plan_id=event.plan_id,
            result_kind="event",
            input_revision=None,
            version=None,
            event_sequence=sequence,
        )
    )
    db.flush()
    authority.final(current, fact)
    return sequence, event


def _generation_entry(
    ticket: GenerationTicket, bundle: GenerationEvidence, candidate: PlanVersion
) -> tuple[GenerationTicket, PlanVersion, ReportingCapability]:
    ticket = GenerationTicket.model_validate(ticket)
    candidate = PlanVersion.model_validate(candidate)
    try:
        capability = ticket_reporting_capability(ticket.policy_version, ticket.policy_digest)
        candidate_capability = reporting_capability(
            candidate.policy_version, candidate.generator_version
        )
    except ValueError as error:
        raise changed("unknown planning policy or generator") from error
    expected_bundle = (
        CreativePairedEvidenceV1
        if capability.mode
        in ("creative_selected_requested_window", "owner_review_creative_selected_requested_window")
        else SelectedPairedEvidenceV1
        if capability.mode == "selected_requested_window"
        else WindowEvidenceBundleV1
        if capability.mode == "presence_requested_window"
        else EvidenceBundle
    )
    if capability != candidate_capability or not isinstance(bundle, expected_bundle):
        raise changed("planning evidence policy differs")
    try:
        bundle.assert_ticket(ticket)
    except ValueError as error:
        raise changed("planning evidence does not match generation") from error
    if isinstance(bundle, CreativePairedEvidenceV1) and utc(candidate.generated_at) < max(
        utc(ticket.prepared_at),
        utc(bundle.reporting.selected.collected_at),
        *(utc(image.observed_at) for image in bundle.creative.basis.images),
    ):
        raise changed("candidate generation predates original creative collection")
    return ticket, candidate, capability


def _generation_actual_bindings(
    ticket: GenerationTicket, bundle: GenerationEvidence, candidate: PlanVersion
) -> None:
    reporting = bundle.reporting if isinstance(bundle, CreativePairedEvidenceV1) else bundle
    actual = reporting.selected if isinstance(reporting, SelectedPairedEvidenceV1) else reporting
    if (
        isinstance(reporting, SelectedPairedEvidenceV1)
        and candidate.selected_reporting_proof != reporting.selected.reporting_proof
    ):
        raise changed("candidate selected proof differs from actual read bundle")
    refs = (
        [item.reference for item in actual.catalogs]
        + [item.reference for item in actual.performance]
        + [item.reference for item in actual.context]
    )
    if actual.commerce is not None:
        refs.append(actual.commerce.reference)
    if isinstance(reporting, SelectedPairedEvidenceV1):
        refs.extend(item.reference for item in reporting.traffic)
    if isinstance(bundle, CreativePairedEvidenceV1):
        proof = creative_proof_from_collection(bundle.creative, ticket)
        if candidate.creative_proof != proof:
            raise changed("candidate creative proof differs from actual read bundle")
        refs.append(creative_basis_reference(proof, ticket.inputs, candidate.valid_until))
    if (
        len(candidate.evidence) != len(refs)
        or len({ref.key for ref in refs}) != len(refs)
        or {ref.key: ref for ref in candidate.evidence} != {ref.key: ref for ref in refs}
        or any(ref.privacy_revision != ticket.privacy_revision for ref in candidate.evidence)
        or utc(candidate.valid_until) > min(utc(ref.expires_at) for ref in refs)
    ):
        raise changed("candidate evidence differs from actual read bundle")
    actual_targets = {
        target.canonical_entity_key: target
        for catalog in actual.catalogs
        for target in targets(catalog)
    }
    proposed_targets = [action.target for action in candidate.actions]
    proposed_targets.extend(brief.target for brief in candidate.briefs)
    proposed_targets.extend(
        a.target for scenario in candidate.scenarios for a in scenario.allocations
    )
    if any(
        isinstance(target, TargetRef) and actual_targets.get(target.canonical_entity_key) != target
        for target in proposed_targets
    ):
        raise changed("candidate target differs from actual owned catalog")
    check_allocations(ticket.inputs, actual.catalogs)
    if candidate.creative_composition is not None:
        try:
            assert_empty_catalog_bindings(candidate.creative_composition.proposals, actual.catalogs)
        except ValueError as error:
            raise changed("empty catalog witness differs from actual collected evidence") from error


def _generation_owner_binding(
    ticket: GenerationTicket,
    bundle: GenerationEvidence,
    candidate: PlanVersion,
    capability: ReportingCapability,
) -> None:
    if capability.mode == "owner_review_creative_selected_requested_window":
        if not isinstance(bundle, CreativePairedEvidenceV1):
            raise changed("creative paired evidence required")
        assert_owner_review_generation_bundle(ticket=ticket, candidate=candidate, bundle=bundle)


def save_generation(
    db: Session,
    *,
    principal: CustomerPrincipal,
    fact: IdentityFact,
    ticket: GenerationTicket,
    bundle: GenerationEvidence,
    candidate: PlanVersion,
    request_key: str,
    request_digest: str,
    now: datetime,
    recheck: Callable[
        [Session, CustomerPrincipal, GenerationTicket, GenerationEvidence, datetime], None
    ],
    prepared: PreparedGenerationChecks | None = None,
) -> PlanVersion:
    if prepared is None:
        ticket, candidate, capability = _generation_entry(ticket, bundle, candidate)
    else:
        require_prepared(prepared, db)
        prepared.generation(db, ticket, bundle, candidate)
        capability = ticket_reporting_capability(ticket.policy_version, ticket.policy_digest)
    wid, plan_id = ticket.inputs.workspace_id, ticket.inputs.plan_id
    current = authority.lock(db, principal, wid, fact)
    if ticket.actor_id != current.user.id or ticket.session_digest != current.session.digest:
        raise changed("original generation session changed")
    prior = receipt(db, wid, current.user.id, "generate", request_key, request_digest)
    plan = owned(db, wid, plan_id)
    if prior is not None:
        if prior.plan_id != plan_id:
            raise changed("request key belongs to another plan")
        _, result = version(db, plan, prior.version)
        authority.final(current, fact, diagnostic_phase="replay")
        return result
    if (
        plan.input_head != ticket.inputs.revision
        or plan.version_head != ticket.expected_version
        or inputs(db, plan).digest() != ticket.inputs.digest()
    ):
        raise changed("generation input or version changed")
    if (
        candidate.inputs.digest() != ticket.inputs.digest()
        or candidate.version != ticket.expected_version + 1
        or candidate.parent_digest != ticket.expected_parent_digest
        or candidate.generated_by != current.user.id
        or candidate.policy_version != ticket.policy_version
    ):
        raise changed("candidate does not match generation")
    if ticket.expected_version:
        _, prior_version = version(db, plan)
        if prior_version.digest() != ticket.expected_parent_digest:
            raise changed("generation parent changed")
    if prepared is None:
        _generation_actual_bindings(ticket, bundle, candidate)
        _generation_owner_binding(ticket, bundle, candidate, capability)
    else:
        prepared.generation(db, ticket, bundle, candidate)
    paid_work(db, wid, now)
    check_goal(db, ticket.inputs, now)
    check_accounts(db, ticket.inputs)
    if workspace_export_revision(db, wid) != ticket.privacy_revision:
        raise changed("generation privacy changed")
    recheck(db, current, ticket, bundle, now)
    if prepared is not None:
        prepared.generation(db, ticket, bundle, candidate)
    try:
        witnesses = capture_retained_sources(
            db, principal=current, document=candidate, now=max(now, database_utc_now(db))
        )
    except RetainedSourcesChanged as error:
        raise changed(error.reason) from error
    if prepared is not None:
        prepared.publication(db, ticket, bundle, candidate)
    authority.final(current, fact, diagnostic_phase="pre_cas")
    if max(utc(now), database_utc_now(db)) >= utc(candidate.valid_until):
        raise changed("generation evidence expired")
    updated = db.scalar(
        update(PlanRow)
        .where(
            PlanRow.workspace_id == wid,
            PlanRow.id == plan_id,
            PlanRow.input_head == ticket.inputs.revision,
            PlanRow.version_head == ticket.expected_version,
        )
        .values(version_head=candidate.version)
        .returning(PlanRow.id)
    )
    if updated is None:
        raise changed("generation head changed")
    candidate_json, candidate_digest = plan_version_storage_pair(candidate)
    db.add(
        PlanVersionRow(
            workspace_id=wid,
            plan_id=plan_id,
            version=candidate.version,
            input_revision=ticket.inputs.revision,
            parent_digest=candidate.parent_digest,
            digest=candidate_digest,
            canonical_json=candidate_json,
            generator_version=candidate.generator_version,
            policy_version=candidate.policy_version,
            actor_id=current.user.id,
            generated_at=candidate.generated_at,
            valid_until=candidate.valid_until,
            privacy_revision=ticket.privacy_revision,
        )
    )
    db.flush()
    for witness in witnesses:
        db.add(PlanDependencyRow(**witness.model_dump(mode="python")))
    for ref in candidate.evidence:
        db.add(
            PlanDependencyRow(
                workspace_id=wid,
                plan_id=plan_id,
                version=candidate.version,
                evidence_key=ref.key,
                account_id=ref.account.account_id if ref.account else None,
                connection_id=ref.account.connection_id if ref.account else None,
                store_id=ticket.inputs.goal.definition.store_id
                if ref.kind == "shopify_measurement"
                else None,
                kind=ref.kind,
                source_binding_digest=ref.source_binding_digest,
                document_digest=ref.document_digest,
                source_revision=ref.source_revision,
                observed_at=ref.observed_at,
                expires_at=ref.expires_at,
                privacy_revision=ref.privacy_revision,
            )
        )
    db.add(
        PlanRequestRow(
            workspace_id=wid,
            actor_id=current.user.id,
            operation="generate",
            request_key=request_key,
            request_digest=request_digest,
            plan_id=plan_id,
            result_kind="version",
            input_revision=None,
            version=candidate.version,
            event_sequence=None,
        )
    )
    db.flush()
    if max(utc(now), database_utc_now(db)) >= utc(candidate.valid_until):
        raise changed("generation evidence expired")
    if prepared is not None:
        prepared.generation(db, ticket, bundle, candidate)
    authority.final(current, fact, diagnostic_phase="post_flush")
    return candidate
