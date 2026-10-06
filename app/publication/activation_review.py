"""Server-compiled activation review of every original paused graph resource.

Creation approval cannot authorize activation. All original resources, including
non-activatable creative, media, tracking and budget steps, must be read back again.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol
from uuid import uuid4

from fastapi import HTTPException
from pydantic import Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.automation.catalog import AutomationControlKey
from app.automation.models import PlatformAutomationControl
from app.campaign_review.contracts import MediaStore
from app.goals.schemas import StrictModel
from app.publication import coordinator as creation
from app.publication import execution_mandates as mandates
from app.publication.activation_contracts import (
    ACTIVATABLE,
    ActivationPlan,
    ActivationTarget,
)
from app.publication.contracts import fingerprint
from app.publication.coordinator_contracts import (
    ConfigurationQualification,
    CreationExecutionReview,
    CreationPlan,
    CreationRuntime,
)
from app.publication.execution_contracts import (
    ExecutionAccount,
    ExposureEvidence,
    ProviderMandateBinding,
)
from app.publication.execution_models import (
    ProviderExecutionApproval,
    ProviderExecutionAttempt,
    ProviderExecutionReceipt,
    ProviderExecutionReview,
    ProviderExecutionRun,
    ProviderExecutionStep,
    ProviderExposureReservation,
)
from app.publication.provider_contracts import Digest, Id
from app.publication.service import owner


class GraphReceipt(StrictModel):
    step_id: str = Field(min_length=1, max_length=32)
    attempt_id: Id
    receipt_id: Id
    receipt_digest: Digest
    request_digest: Digest
    readback_digest: Digest


class ActivationExecutionReview(StrictModel):
    schema_version: Literal["inlet.execution-activation-review.v1"] = (
        "inlet.execution-activation-review.v1"
    )
    purpose: Literal["activate"] = "activate"
    mandate: ProviderMandateBinding
    reservation_id: Id
    creation_plan: CreationPlan
    plan: ActivationPlan
    graph: list[GraphReceipt] = Field(min_length=2, max_length=96)
    qualification: ConfigurationQualification
    exposure: ExposureEvidence

    @model_validator(mode="after")
    def exact(self) -> "ActivationExecutionReview":
        original = self.creation_plan
        expected = [s.step_id for s in original.steps]
        if (
            self.plan.account != ExecutionAccount.from_publication(original.review.scope)
            or self.plan.parent_plan_digest != original.digest()
            or [r.step_id for r in self.graph] != expected
            or len({r.attempt_id for r in self.graph}) != len(expected)
            or self.qualification.account != self.plan.account
            or self.qualification.plan_digest != original.digest()
            or self.qualification.api_version != original.api_version
            or self.qualification.environment != self.mandate.environment
            or self.qualification.unresolved
            or self.exposure.account != self.plan.account
            or self.exposure.mandate != self.mandate
        ):
            raise ValueError("complete original graph and current qualification required")
        wanted = list(
            reversed([s.step_id for s in original.steps if s.operation.kind in ACTIVATABLE])
        )
        if [t.step_id for t in self.plan.targets] != wanted:
            raise ValueError("server activation graph must reverse all activatable steps")
        by_step = {r.step_id: r for r in self.graph}
        for target in self.plan.targets:
            ref = by_step[target.step_id]
            if (
                target.source_attempt_id != ref.attempt_id
                or target.source_receipt_id != ref.receipt_id
                or target.source_receipt_digest != ref.receipt_digest
                or target.before_readback_digest != ref.readback_digest
                or target.original_request.digest() != ref.request_digest
            ):
                raise ValueError("activation target must bind original complete graph evidence")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class ActivationExposureReader(Protocol):
    def __call__(
        self,
        db: Session,
        binding: ProviderMandateBinding,
        plan: CreationPlan,
        reservation_id: str,
        now: datetime,
        /,
    ) -> ExposureEvidence:
        """Server proof; existing reservations excludes this retained parent reservation."""
        ...


@dataclass(frozen=True)
class ActivationReviewRuntime:
    creation: CreationRuntime
    exposure_reader: ActivationExposureReader


def parent_graph(
    db: Session, wid: int, parent_id: str
) -> tuple[ProviderExecutionRun, CreationExecutionReview, list[GraphReceipt], ActivationPlan]:
    """Called under the workspace/ledger/source locks; never accepts client receipts."""
    parent = db.scalar(
        select(ProviderExecutionRun)
        .where(ProviderExecutionRun.id == parent_id, ProviderExecutionRun.workspace_id == wid)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if parent is None:
        raise HTTPException(404, "paused parent run unavailable")
    row = db.get(ProviderExecutionReview, parent.review_id)
    if row is None or row.workspace_id != wid or row.document.get("purpose") != "create_paused":
        raise HTTPException(409, "creation parent required")
    document = CreationExecutionReview.model_validate(row.document)
    if row.digest != document.digest() or parent.reservation_id is None:
        raise HTTPException(409, "original reviewed graph changed")
    if parent.canceled_at is not None:
        raise HTTPException(409, "creation parent canceled")
    refs, targets = [], []
    for spec in document.plan.steps:
        attempt = db.scalar(
            select(ProviderExecutionAttempt).where(
                ProviderExecutionAttempt.workspace_id == wid,
                ProviderExecutionAttempt.run_id == parent.id,
                ProviderExecutionAttempt.step_id == spec.step_id,
            )
        )
        if attempt is None:
            raise HTTPException(409, "complete original graph required")
        _, _, _, request = creation.evidence_lock(db, wid, attempt.id)
        latest = db.scalar(
            select(ProviderExecutionReceipt)
            .where(
                ProviderExecutionReceipt.workspace_id == wid,
                ProviderExecutionReceipt.attempt_id == attempt.id,
            )
            .order_by(ProviderExecutionReceipt.sequence.desc())
            .limit(1)
        )
        if latest is None:
            raise HTTPException(409, "complete original readback required")
        receipt = creation.receipt_for(document, latest.receipt)
        digest = fingerprint("inlet.provider-receipt.v1", receipt.model_dump(mode="json"))
        if (
            latest.digest != digest
            or receipt.outcome != "verified_effect"
            or receipt.request_digest != request.digest()
            or receipt.scope != request.scope
            or receipt.plan_id != request.plan_id
            or receipt.plan_digest != request.plan_digest
            or receipt.step_id != spec.step_id
            or receipt.fence != request.fence
            or receipt.resource_name is None
            or receipt.readback_digest is None
        ):
            raise HTTPException(409, "current complete original graph readback required")
        refs.append(
            GraphReceipt(
                step_id=spec.step_id,
                attempt_id=attempt.id,
                receipt_id=latest.id,
                receipt_digest=latest.digest,
                request_digest=request.digest(),
                readback_digest=receipt.readback_digest,
            )
        )
        if spec.operation.kind in ACTIVATABLE:
            platform = request.scope.account.platform
            targets.append(
                ActivationTarget(
                    source_attempt_id=attempt.id,
                    source_receipt_id=latest.id,
                    source_receipt_digest=latest.digest,
                    original_request=request,
                    resource_name=receipt.resource_name,
                    before_readback_digest=receipt.readback_digest,
                    before_status="DISABLE" if platform == "tiktok_ads" else "PAUSED",
                    target_status={
                        "google_ads": "ENABLED",
                        "meta_ads": "ACTIVE",
                        "tiktok_ads": "ENABLE",
                    }[platform],
                )
            )
    plan = ActivationPlan(
        account=ExecutionAccount.from_publication(document.plan.review.scope),
        parent_run_id=parent.id,
        parent_plan_digest=document.plan.digest(),
        targets=list(reversed(targets)),
    )
    return parent, document, refs, plan


def current(
    db: Session,
    wid: int,
    binding: ProviderMandateBinding,
    original: CreationPlan,
    actor: str,
    store: MediaStore,
    runtime: ActivationReviewRuntime,
    clock: creation.Clock,
) -> None:
    creation.gate(runtime.creation, binding.environment, original)
    runtime.creation.authorize(db, wid, actor)
    _, policy = mandates.checked(db, wid, binding, actor, clock)
    creation.source_current(db, wid, original, actor, store, clock)
    creation.social_configuration_current(db, wid, original, actor, runtime.creation, clock)
    master = db.get(
        PlatformAutomationControl, AutomationControlKey.ALL_DATA_SYNCS.value, populate_existing=True
    )
    if "activate" not in policy.allowed_purposes or (master is not None and not master.enabled):
        raise HTTPException(409, "activation outside current approved policy")


def validate_fresh(
    db: Session,
    wid: int,
    document: ActivationExecutionReview,
    actor: str,
    clock: creation.Clock,
) -> None:
    ledger, policy = mandates.checked(db, wid, document.mandate, actor, clock)
    reservation = db.scalar(
        select(ProviderExposureReservation)
        .where(
            ProviderExposureReservation.id == document.reservation_id,
            ProviderExposureReservation.workspace_id == wid,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    e = document.exposure
    others = (
        db.scalar(
            select(func.coalesce(func.sum(ProviderExposureReservation.amount_micros), 0)).where(
                ProviderExposureReservation.workspace_id == wid,
                ProviderExposureReservation.environment == document.mandate.environment,
                ProviderExposureReservation.state == "held",
                ProviderExposureReservation.id != document.reservation_id,
            )
        )
        or 0
    )
    now = clock()
    if (
        reservation is None
        or reservation.state != "held"
        or reservation.ledger_id != ledger.id
        or reservation.environment != document.mandate.environment
        or reservation.budget_owner_key != e.budget_owner_key
        or e.proposed_owner_upper_micros is None
        or e.proposed_owner_upper_micros != reservation.amount_micros
        or e.existing_reservations_micros != others
        or e.reported_spend_micros < ledger.spent_high_water_micros
        or not document.qualification.observed_at <= now < document.qualification.expires_at
        or not e.eligible(policy, now)
    ):
        raise HTTPException(409, "fresh activation proof within retained exposure required")


def prepare_activation(
    db: Session,
    wid: int,
    parent_id: str,
    binding: ProviderMandateBinding,
    actor: str,
    store: MediaStore,
    runtime: ActivationReviewRuntime,
    clock: creation.Clock,
) -> ProviderExecutionReview:
    # Discover only within workspace; current locks are acquired before graph records.
    parent = db.scalar(
        select(ProviderExecutionRun).where(
            ProviderExecutionRun.id == parent_id, ProviderExecutionRun.workspace_id == wid
        )
    )
    if parent is None:
        raise HTTPException(404, "paused parent run unavailable")
    old = db.get(ProviderExecutionReview, parent.review_id)
    if old is None or old.document.get("purpose") != "create_paused":
        raise HTTPException(409, "creation parent required")
    original = CreationExecutionReview.model_validate(old.document).plan
    current(db, wid, binding, original, actor, store, runtime, clock)
    _, _, refs, _ = parent_graph(db, wid, parent_id)
    db.commit()
    # Re-read every step, not just resources with a mutable status. No provider mutation.
    for ref in refs:
        result = creation.reconcile_attempt(db, wid, ref.attempt_id, runtime.creation, clock)
        if result.outcome != "verified_effect":
            raise HTTPException(409, "original graph no longer exactly verified")
    qualification = runtime.creation.qualification_reader(original, clock())
    parent = db.get(ProviderExecutionRun, parent_id)
    assert parent is not None and parent.reservation_id is not None
    exposure = runtime.exposure_reader(db, binding, original, parent.reservation_id, clock())
    db.commit()
    current(db, wid, binding, original, actor, store, runtime, clock)
    parent, old_document, refs, plan = parent_graph(db, wid, parent_id)
    assert parent.reservation_id is not None
    document = ActivationExecutionReview(
        mandate=binding,
        reservation_id=parent.reservation_id,
        creation_plan=old_document.plan,
        plan=plan,
        graph=refs,
        qualification=qualification,
        exposure=exposure,
    )
    validate_fresh(db, wid, document, actor, clock)
    row = ProviderExecutionReview(
        id=uuid4().hex,
        workspace_id=wid,
        consent_id=binding.consent_id,
        account_id=plan.account.account.account_id,
        integration_id=plan.account.account.connection_id,
        source_draft_id=original.review.source.draft_id,
        source_revision=original.review.source.revision,
        document=document.model_dump(mode="json"),
        digest=document.digest(),
        plan_digest=plan.digest(),
        actor=actor,
        created_at=clock(),
    )
    db.add(row)
    db.commit()
    return row


def checked_review(
    db: Session,
    wid: int,
    review_id: str,
    actor: str,
    store: MediaStore,
    runtime: ActivationReviewRuntime,
    clock: creation.Clock,
) -> tuple[ProviderExecutionReview, ActivationExecutionReview]:
    row = db.scalar(
        select(ProviderExecutionReview).where(
            ProviderExecutionReview.id == review_id, ProviderExecutionReview.workspace_id == wid
        )
    )
    if row is None or row.document.get("purpose") != "activate":
        raise HTTPException(404, "activation review unavailable")
    document = ActivationExecutionReview.model_validate(row.document)
    current(db, wid, document.mandate, document.creation_plan, actor, store, runtime, clock)
    _, _, refs, plan = parent_graph(db, wid, document.plan.parent_run_id)
    db.refresh(row, with_for_update=True)
    if (
        row.digest != document.digest()
        or row.plan_digest != document.plan.digest()
        or row.document != document.model_dump(mode="json")
        or row.consent_id != document.mandate.consent_id
        or refs != document.graph
        or plan != document.plan
    ):
        raise HTTPException(409, "exact activation review or graph evidence changed")
    validate_fresh(db, wid, document, actor, clock)
    return row, document


def approve_activation(
    db: Session,
    wid: int,
    review_id: str,
    digest: str,
    plan_digest: str,
    actor: str,
    store: MediaStore,
    runtime: ActivationReviewRuntime,
    clock: creation.Clock,
) -> ProviderExecutionApproval:
    row, document = checked_review(db, wid, review_id, actor, store, runtime, clock)
    if (digest, plan_digest) != (row.digest, row.plan_digest):
        raise HTTPException(409, "separate exact activation approval required")
    approval = db.get(ProviderExecutionApproval, row.id)
    validate_fresh(db, wid, document, actor, clock)
    if approval is None:
        approval = ProviderExecutionApproval(
            review_id=row.id,
            workspace_id=wid,
            review_digest=digest,
            plan_digest=plan_digest,
            actor=actor,
            approved_at=clock(),
        )
        db.add(approval)
    db.commit()
    return approval


def create_run(
    db: Session,
    wid: int,
    review_id: str,
    actor: str,
    store: MediaStore,
    runtime: ActivationReviewRuntime,
    clock: creation.Clock,
) -> ProviderExecutionRun:
    row, document = checked_review(db, wid, review_id, actor, store, runtime, clock)
    approval = db.get(ProviderExecutionApproval, row.id)
    if approval is None or (approval.review_digest, approval.plan_digest) != (
        row.digest,
        row.plan_digest,
    ):
        raise HTTPException(409, "separate exact activation approval required")
    owner(db, wid, approval.actor)
    existing = db.scalar(
        select(ProviderExecutionRun).where(
            ProviderExecutionRun.workspace_id == wid,
            ProviderExecutionRun.parent_run_id == document.plan.parent_run_id,
        )
    )
    if existing is not None:
        if existing.review_id != row.id:
            raise HTTPException(409, "original activation run already exists")
        return existing
    validate_fresh(db, wid, document, actor, clock)
    run = ProviderExecutionRun(
        id=uuid4().hex,
        workspace_id=wid,
        review_id=row.id,
        state="ready",
        created_at=clock(),
        parent_run_id=document.plan.parent_run_id,
        reservation_id=document.reservation_id,
    )
    db.add(run)
    db.flush()
    for index, target in enumerate(document.plan.targets):
        db.add(
            ProviderExecutionStep(
                run_id=run.id,
                step_id=target.step_id,
                workspace_id=wid,
                ordinal=index,
                state="pending",
            )
        )
    db.commit()
    return run
