"""Server-only persistence, fresh owned fences, CAS slots and read-time scoring."""

from collections.abc import Callable
from decimal import Decimal
from typing import Literal
from uuid import uuid4

from fastapi import HTTPException
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.commerce.evidence import digest, lock_workspace
from app.outcome_feedback.models import (
    ContributionSlot,
    FeedbackRecord,
    V3Assessment,
    V3EvidenceDependency,
)
from app.outcomes.contracts import Digest, Frozen, Positive
from app.outcomes.descriptive import validate_manifest
from app.outcomes.feedback import (
    FeedbackContribution,
    FeedbackDecisionPolicy,
    decision_policy_for,
    prepare_feedback,
    recompute_active_score,
)
from app.outcomes.maturity import PolicyLookup, policy_for
from app.outcomes.owned import Clock, publication
from app.outcomes.owned_v3 import OwnedV3Assessment, OwnedV3Request, SessionAuthorize, _snapshot
from app.shopify.security import utc


class EvidenceReference(Frozen):
    publication_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    manifest_digest: Digest
    completion_digest: Digest


class SlotVersion(Frozen):
    slot_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    revision: Positive
    active_feedback_digest: Digest


DecisionLookup = Callable[[str], FeedbackDecisionPolicy | None]


def _check(
    db: Session,
    wid: int,
    actor: str,
    value: OwnedV3Assessment,
    references: tuple[EvidenceReference, ...],
    authorize: SessionAuthorize,
    clock: Clock,
    policies: PolicyLookup,
) -> None:
    if value.context.scope.workspace_id != wid or not 1 <= len(references) <= 33:
        raise HTTPException(409, "owned assessment dependencies unavailable")
    request = OwnedV3Request(
        attempt_id=value.receipt.attempt_id,
        publication_id=value.publication_id,
        before_start=value.before_window.start,
        before_end=value.before_window.end,
        after_start=value.after_window.start,
        after_end=value.after_window.end,
    )
    current = _snapshot(db, wid, actor, request, authorize, clock)
    if (
        current.context.scope != value.context.scope
        or current.receipt != value.receipt
        or current.publication_digest != value.publication_digest
        or current.context.source_current != value.context.source_current
        or current.context.evaluated_at < value.context.evaluated_at
    ):
        raise HTTPException(409, "assessment evidence changed")
    registered = policies(current.context.scope)
    expected_policies = {
        part.policy_digest
        for part in (value.before_maturity, value.after_maturity)
        if part is not None
    }
    if expected_policies and expected_policies != {
        registered.policy_digest if registered else None
    }:
        raise HTTPException(409, "maturity policy changed")
    if value.status == "operational_association_as_of" and registered is None:
        raise HTTPException(409, "maturity policy unavailable")
    seen: set[str] = set()
    completions: set[str] = set()
    for reference in references:
        reference = EvidenceReference.model_validate(reference.model_dump())
        if reference.publication_id in seen:
            raise HTTPException(409, "duplicate evidence dependency")
        seen.add(reference.publication_id)
        row, _ = publication(db, wid, reference.publication_id, clock)
        validate_manifest(row)
        if utc(row.published_at) > value.context.evaluated_at:
            raise HTTPException(409, "future evidence dependency")
        if (
            row.store_id != value.context.scope.store_id
            or row.generation != value.context.scope.generation
            or row.privacy_epoch != value.context.scope.privacy_epoch
            or row.manifest_digest != reference.manifest_digest
            or row.completion_digest != reference.completion_digest
        ):
            raise HTTPException(409, "source dependency changed")
        completions.add(reference.completion_digest)
    required = {
        completion
        for part in (value.before_maturity, value.after_maturity)
        if part is not None
        for completion in part.supporting_completions
    }
    if value.publication_id not in seen or not required <= completions:
        raise HTTPException(409, "complete evidence dependency set required")
    authorize(db)


def persist_assessment(
    db: Session,
    wid: int,
    actor: str,
    value: OwnedV3Assessment,
    references: tuple[EvidenceReference, ...],
    authorize: SessionAuthorize,
    clock: Clock,
    *,
    policies: PolicyLookup = policy_for,
) -> V3Assessment:
    value = OwnedV3Assessment.model_validate(value.model_dump())
    _check(db, wid, actor, value, references, authorize, clock, policies)
    payload = value.model_dump(mode="json")
    if len(value.model_dump_json().encode()) > 256 * 1024:
        raise HTTPException(413, "assessment exceeds bounded size")
    existing = db.scalar(
        select(V3Assessment).where(
            V3Assessment.workspace_id == wid, V3Assessment.input_digest == value.input_digest
        )
    )
    if existing is not None:
        if existing.document_digest != digest(payload):
            raise HTTPException(409, "assessment input conflict")
        return existing
    row = V3Assessment(
        id=uuid4().hex,
        workspace_id=wid,
        store_id=value.context.scope.store_id,
        environment=value.context.environment,
        attempt_id=value.receipt.attempt_id,
        receipt_id=value.receipt.receipt_id,
        receipt_sequence=value.receipt.sequence,
        generation=value.context.scope.generation,
        privacy_epoch=value.context.scope.privacy_epoch,
        input_digest=value.input_digest,
        document_digest=digest(payload),
        document=payload,
        created_at=value.context.evaluated_at,
    )
    db.add(row)
    db.flush()
    for index, reference in enumerate(references):
        db.add(
            V3EvidenceDependency(
                assessment_id=row.id, ordinal=index, workspace_id=wid, **reference.model_dump()
            )
        )
    db.flush()
    return row


def read_current(
    db: Session,
    wid: int,
    actor: str,
    identifier: str,
    authorize: SessionAuthorize,
    clock: Clock,
    policies: PolicyLookup = policy_for,
) -> tuple[V3Assessment, OwnedV3Assessment]:
    lock_workspace(db, wid, active=True)
    authorize(db)
    row = db.scalar(
        select(V3Assessment)
        .where(V3Assessment.id == identifier, V3Assessment.workspace_id == wid)
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise HTTPException(404, "assessment unavailable")
    value = OwnedV3Assessment.model_validate(row.document)
    if digest(value.model_dump(mode="json")) != row.document_digest or (
        row.environment,
        row.attempt_id,
        row.receipt_id,
        row.receipt_sequence,
        row.generation,
        row.privacy_epoch,
        row.store_id,
        row.input_digest,
    ) != (
        value.context.environment,
        value.receipt.attempt_id,
        value.receipt.receipt_id,
        value.receipt.sequence,
        value.context.scope.generation,
        value.context.scope.privacy_epoch,
        value.context.scope.store_id,
        value.input_digest,
    ):
        raise HTTPException(409, "assessment document invalid")
    dependencies = list(
        db.scalars(
            select(V3EvidenceDependency)
            .where(
                V3EvidenceDependency.assessment_id == row.id,
                V3EvidenceDependency.workspace_id == wid,
            )
            .order_by(V3EvidenceDependency.ordinal)
            .limit(34)
        )
    )
    references = tuple(
        EvidenceReference(
            publication_id=item.publication_id,
            manifest_digest=item.manifest_digest,
            completion_digest=item.completion_digest,
        )
        for item in dependencies
    )
    _check(db, wid, actor, value, references, authorize, clock, policies)
    return row, value


def apply_feedback(
    db: Session,
    wid: int,
    actor: str,
    assessment_id: str,
    family: str,
    scope_digest: str,
    expected: SlotVersion | None,
    authorize: SessionAuthorize,
    clock: Clock,
    *,
    decisions: DecisionLookup = decision_policy_for,
    policies: PolicyLookup = policy_for,
) -> ContributionSlot | None:
    row, value = read_current(db, wid, actor, assessment_id, authorize, clock, policies)
    decision = decisions(family)
    if decision is None:
        return None
    if decision.family != family:
        raise HTTPException(409, "decision policy family mismatch")
    # Scope is a server-defined recommendation group, not a customer direction/proof.
    if len(scope_digest) != 64 or any(char not in "0123456789abcdef" for char in scope_digest):
        raise HTTPException(409, "recommendation scope unavailable")
    contribution = prepare_feedback(
        value,
        decision,
        environment=value.context.environment,
        expected_assessment_digest=row.document_digest,
    )
    if contribution.status != "eligible":
        return None
    key = (
        ContributionSlot.workspace_id == wid,
        ContributionSlot.environment == value.context.environment,
        ContributionSlot.attempt_id == value.receipt.attempt_id,
        ContributionSlot.policy_family == family,
        ContributionSlot.scope_digest == scope_digest,
    )
    slot = db.scalar(
        select(ContributionSlot)
        .where(*key)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    existing = db.scalar(
        select(FeedbackRecord).where(
            FeedbackRecord.workspace_id == wid,
            FeedbackRecord.environment == value.context.environment,
            FeedbackRecord.assessment_digest == row.document_digest,
            FeedbackRecord.policy_digest == decision.policy_digest,
            FeedbackRecord.scope_digest == scope_digest,
        )
    )
    if slot is not None and existing is not None and slot.feedback_id == existing.id:
        return slot
    active = db.get(FeedbackRecord, slot.feedback_id) if slot else None
    if (slot is None) != (expected is None) or (
        slot is not None
        and (
            expected is None
            or expected.slot_id != slot.id
            or expected.revision != slot.revision
            or active is None
            or expected.active_feedback_digest != active.document_digest
        )
    ):
        raise HTTPException(409, "contribution slot changed")
    if existing is None:
        payload = contribution.model_dump(mode="json")
        existing = FeedbackRecord(
            id=uuid4().hex,
            workspace_id=wid,
            environment=value.context.environment,
            attempt_id=value.receipt.attempt_id,
            assessment_id=row.id,
            assessment_digest=row.document_digest,
            policy_family=family,
            policy_digest=decision.policy_digest,
            scope_digest=scope_digest,
            document_digest=digest(payload),
            document=payload,
            state="eligible",
            created_at=clock(),
        )
        db.add(existing)
        db.flush()
    if active is not None:
        active.state = "superseded"
    if slot is None:
        slot = ContributionSlot(
            id=uuid4().hex,
            workspace_id=wid,
            environment=value.context.environment,
            attempt_id=value.receipt.attempt_id,
            policy_family=family,
            scope_digest=scope_digest,
            feedback_id=existing.id,
            revision=1,
        )
        db.add(slot)
    else:
        slot.feedback_id = existing.id
        slot.revision += 1
    existing.state = "eligible"
    authorize(db)
    db.flush()
    return slot


def active_score(
    db: Session,
    wid: int,
    actor: str,
    environment: Literal["contract_test", "live"],
    family: str,
    scope_digest: str,
    authorize: SessionAuthorize,
    clock: Clock,
    *,
    decisions: DecisionLookup = decision_policy_for,
    policies: PolicyLookup = policy_for,
) -> Decimal | None:
    """Fresh owned read projection; no persisted aggregate can outlive retraction."""
    lock_workspace(db, wid, active=True)
    authorize(db)
    decision = decisions(family)
    if decision is None:
        return None
    if decision.family != family:
        raise HTTPException(409, "decision policy family mismatch")
    rows = list(
        db.scalars(
            select(FeedbackRecord)
            .join(
                ContributionSlot,
                (ContributionSlot.feedback_id == FeedbackRecord.id)
                & (ContributionSlot.workspace_id == FeedbackRecord.workspace_id),
            )
            .where(
                ContributionSlot.workspace_id == wid,
                ContributionSlot.environment == environment,
                ContributionSlot.policy_family == family,
                ContributionSlot.scope_digest == scope_digest,
            )
            .limit(65)
        )
    )
    if len(rows) > 64:
        raise HTTPException(409, "active contribution read bound exceeded")
    values = []
    for row in rows:
        assessment, evidence = read_current(
            db, wid, actor, row.assessment_id, authorize, clock, policies
        )
        value = FeedbackContribution.model_validate(row.document)
        expected = prepare_feedback(
            evidence,
            decision,
            environment=environment,
            expected_assessment_digest=assessment.document_digest,
        )
        if (
            digest(value.model_dump(mode="json")) != row.document_digest
            or row.state != "eligible"
            or value != expected
            or row.policy_digest != decision.policy_digest
        ):
            raise HTTPException(409, "active contribution invalid")
        values.append(value)
    authorize(db)
    return recompute_active_score(
        decision, tuple(values), workspace_id=wid, environment=environment
    )
