"""Durable offline coordinator. No HTTP adapters or live publication authority exist here."""

import hashlib
import json
from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ads.models import AdvertisingAccount
from app.billing.entitlements import paid_work
from app.campaign_review import service as reviews
from app.campaign_review.contracts import MediaStore
from app.campaign_review.models import CampaignDraft
from app.customers.models import CustomerMembership, CustomerUser
from app.google_connections.models import GoogleCustomerConnection
from app.mandates import service as mandates
from app.mandates.models import Mandate, MandateAction
from app.mandates.schemas import ActionDraft, ClaimInput, SyntheticEvidence
from app.meta.models import MetaConnection
from app.publication.contracts import (
    BoundRequest,
    FixtureReviewFields,
    PublicationReviewV2,
    PublishPlan,
    PublishReceipt,
    fingerprint,
)
from app.publication.fixture import compile_registered, require_fixture
from app.publication.models import (
    PublicationPlanRecord,
    PublicationReceiptRecord,
    PublicationStepRecord,
)
from app.sources.models import SourceConnection


def owner(db: Session, wid: int, actor: str) -> None:
    if (
        db.scalar(
            select(CustomerMembership.user_id)
            .join(CustomerUser)
            .where(
                CustomerMembership.workspace_id == wid,
                CustomerMembership.user_id == actor,
                CustomerMembership.status == "active",
                CustomerMembership.role == "owner",
                CustomerUser.status == "active",
            )
        )
        is None
    ):
        raise HTTPException(403, "current customer owner required")


def lock_source(
    db: Session, plan: PublishPlan
) -> GoogleCustomerConnection | MetaConnection | SourceConnection | None:
    scope = plan.scope
    db.scalar(
        select(CampaignDraft)
        .where(
            CampaignDraft.id == plan.review.source.draft_id,
            CampaignDraft.workspace_id == scope.workspace_id,
        )
        .with_for_update()
    )
    if scope.account.platform == "google_ads":
        return db.scalar(
            select(GoogleCustomerConnection)
            .where(
                GoogleCustomerConnection.workspace_id == scope.workspace_id,
                GoogleCustomerConnection.integration_id == scope.account.connection_id,
                GoogleCustomerConnection.account_id == scope.account.account_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    if scope.account.platform == "meta_ads":
        return db.scalar(
            select(MetaConnection)
            .where(
                MetaConnection.workspace_id == scope.workspace_id,
                MetaConnection.workspace_integration_id == scope.account.connection_id,
                MetaConnection.account_id == scope.account.account_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    return db.scalar(
        select(SourceConnection)
        .where(
            SourceConnection.workspace_id == scope.workspace_id,
            SourceConnection.provider == "tiktok_ads",
            SourceConnection.integration_id == scope.account.connection_id,
            SourceConnection.account_id == scope.account.account_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )


class DatabaseFixtureAuthority:
    """Current DB authority only. Simulation approvals never authorize external mutation."""

    def __init__(self, store: MediaStore) -> None:
        self.store = store

    def validate(self, db: Session, plan: PublishPlan, actor: str, now: datetime) -> Mandate:
        scope = plan.scope
        mandate = mandates.owned(db, scope.workspace_id, scope.mandate_id)
        native = lock_source(db, plan)
        external = (
            native.external_id
            if isinstance(native, SourceConnection)
            else getattr(native, "external_account_id", None)
        )
        if external != scope.external_advertiser_id:
            raise HTTPException(409, "native advertiser identity changed")
        owner(db, scope.workspace_id, actor)
        paid_work(db, scope.workspace_id, now)
        account = db.get(AdvertisingAccount, scope.account.account_id)
        if account is None or account.external_account_id != scope.external_advertiser_id:
            raise HTTPException(409, "advertiser identity changed")
        policy = mandates.policy(db, mandate)
        if policy.mode != "simulation":
            raise HTTPException(409, "offline simulation authority required")
        row, artifact = reviews.preview(
            db, scope.workspace_id, plan.review.source.draft_id, self.store, now
        )
        if row.approved_by is None or artifact.fingerprint() != plan.review.source_digest:
            raise HTTPException(409, "approved source review changed")
        if artifact.connection_version != scope.connection_version:
            raise HTTPException(409, "connection generation changed")
        return mandate

    def evidence(
        self, db: Session, mandate: Mandate, plan: PublishPlan, now: datetime
    ) -> SyntheticEvidence:
        # Fixture observation is explicitly synthetic; it is not provider spend verification.
        return SyntheticEvidence(
            state_digest=plan.review_digest,
            observed_at=now,
            bound_micros=plan.exposure_micros,
            entitlement_active=True,
            period_consumed_micros=mandate.observed_micros,
            covered_account_ids=[a.account_id for a in mandates.policy(db, mandate).accounts],
        )


def prepare(
    db: Session,
    wid: int,
    draft_id: str,
    compiler_id: str,
    configuration: FixtureReviewFields,
    actor: str,
    authority: DatabaseFixtureAuthority,
    now: datetime,
) -> PublicationPlanRecord:
    mandates.workspace_lock(db, wid)
    owner(db, wid, actor)
    # Peek the immutable definition to acquire mandate before the draft/native connection locks.
    from app.campaign_review.models import CampaignRevision

    draft = db.scalar(
        select(CampaignDraft).where(CampaignDraft.id == draft_id, CampaignDraft.workspace_id == wid)
    )
    if draft is None:
        raise HTTPException(404, "campaign draft unavailable")
    revision = db.get(CampaignRevision, (draft.id, draft.revision))
    assert revision is not None
    mandates.owned(db, wid, str(revision.artifact["definition"]["mandate_id"]))
    row, artifact = reviews.preview(db, wid, draft_id, authority.store, now)
    if row.approved_by is None:
        raise HTTPException(409, "offline source review required")
    account = db.get(AdvertisingAccount, artifact.definition.account.account_id)
    assert account is not None
    review = PublicationReviewV2(
        source=artifact,
        source_digest=row.digest,
        external_advertiser_id=account.external_account_id,
        configuration=configuration,
    )
    plan = compile_registered(compiler_id, review)
    mandate = authority.validate(db, plan, actor, now)
    prior = db.scalar(
        select(PublicationPlanRecord).where(
            PublicationPlanRecord.workspace_id == wid, PublicationPlanRecord.digest == plan.digest()
        )
    )
    if prior is not None:
        return prior
    payload = {
        "schema": "offline_publication_v1",
        "plan_digest": plan.digest(),
        "review_digest": plan.review_digest,
    }
    action = mandates.draft(
        db,
        mandate,
        ActionDraft(
            account=plan.scope.account,
            kind="new_campaign",
            resource_key="publication:" + draft_id,
            payload=payload,
            payload_digest=hashlib.sha256(
                json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
            expected_state_digest=plan.review_digest,
            exposure_micros=plan.exposure_micros,
            positive_change_micros=plan.exposure_micros,
            mandate_revision=mandate.revision,
        ),
        actor,
        now,
    )
    record = PublicationPlanRecord(
        id=uuid4().hex,
        workspace_id=wid,
        action_id=action.id,
        digest=plan.digest(),
        document=plan.model_dump(mode="json"),
    )
    db.add(record)
    db.flush()
    for step in plan.steps:
        db.add(PublicationStepRecord(plan_id=record.id, step_id=step.step_id, workspace_id=wid))
    db.commit()
    return record


def locked(
    db: Session, wid: int, plan_id: str
) -> tuple[PublicationPlanRecord, PublishPlan, Mandate, MandateAction]:
    mandates.workspace_lock(db, wid)
    peek = db.scalar(
        select(PublicationPlanRecord)
        .where(PublicationPlanRecord.id == plan_id, PublicationPlanRecord.workspace_id == wid)
        .execution_options(populate_existing=True)
    )
    if peek is None:
        raise HTTPException(404, "publication plan unavailable")
    plan = PublishPlan.model_validate(peek.document)
    if plan.digest() != peek.digest or plan.scope.workspace_id != wid:
        raise HTTPException(409, "publication plan integrity mismatch")
    # Server compiler remains the authority for allowed operations and exact reviewed fields.
    if compile_registered(plan.compiler_id, plan.review).digest() != peek.digest:
        raise HTTPException(409, "publication compiler mismatch")
    mandate = mandates.owned(db, wid, plan.scope.mandate_id)
    lock_source(db, plan)
    record = db.scalar(
        select(PublicationPlanRecord)
        .where(PublicationPlanRecord.id == plan_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    assert record is not None
    action = mandates.action(db, mandate, record.action_id)
    expected = ActionDraft.model_validate(action.draft)
    if (
        expected.payload.get("plan_digest") != record.digest
        or expected.exposure_micros != plan.exposure_micros
        or expected.kind != "new_campaign"
        or expected.account != plan.scope.account
        or expected.mandate_revision != plan.scope.mandate_revision
        or expected.expected_state_digest != plan.review_digest
        or expected.payload.get("review_digest") != plan.review_digest
        or expected.positive_change_micros != plan.exposure_micros
        or expected.resource_key != "publication:" + plan.review.source.draft_id
        or expected.payload
        != {
            "schema": "offline_publication_v1",
            "plan_digest": record.digest,
            "review_digest": plan.review_digest,
        }
        or action.digest
        != hashlib.sha256(
            json.dumps(
                expected.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest()
    ):
        raise HTTPException(409, "publication reservation mismatch")
    return record, plan, mandate, action


def approve(
    db: Session,
    wid: int,
    plan_id: str,
    review_digest: str,
    plan_digest: str,
    actor: str,
    authority: DatabaseFixtureAuthority,
    now: datetime,
) -> None:
    record, plan, mandate, action = locked(db, wid, plan_id)
    authority.validate(db, plan, actor, now)
    if review_digest != plan.review_digest or plan_digest != record.digest:
        raise HTTPException(409, "exact publication review changed")
    if record.approved_by is not None:
        return
    mandates.review(db, mandate, action, action.digest, actor, now)
    record.approved_by, record.approved_at, record.state = actor, now, "approved"
    db.commit()


def claim_next(
    db: Session,
    wid: int,
    plan_id: str,
    request_key: str,
    actor: str,
    authority: DatabaseFixtureAuthority,
    now: datetime,
) -> BoundRequest | None:
    record, plan, mandate, action = locked(db, wid, plan_id)
    authority.validate(db, plan, actor, now)
    if not record.approved_by or record.state in {"cancelled", "cancel_requested"}:
        raise HTTPException(409, "publication not approved or cancelled")
    owner(db, wid, record.approved_by)
    if record.request_key is not None and record.request_key != request_key:
        raise HTTPException(409, "publication request conflict")
    if record.state == "paused_verified":
        return None
    # B07 performs the single durable reservation; its existing simulation boundary stays intact.
    mandates.claim(
        db,
        mandate,
        action,
        ClaimInput(request_key=request_key, evidence=authority.evidence(db, mandate, plan, now)),
        actor,
        now,
    )
    record, plan, mandate, action = locked(db, wid, plan_id)
    authority.validate(db, plan, actor, now)
    mandates.preconditions(db, mandate, action, authority.evidence(db, mandate, plan, now), now)
    record.request_key = request_key
    if action.cancel_requested or action.state not in {"claimed", "dispatching", "outcome_unknown"}:
        raise HTTPException(409, "publication cancelled")
    if action.state == "claimed":
        mandates.dispatch(
            db,
            mandate,
            action,
            action.fence or "",
            authority.evidence(db, mandate, plan, now),
            actor,
            now,
        )
        record, plan, mandate, action = locked(db, wid, plan_id)
        authority.validate(db, plan, actor, now)
        # dispatch commits the mandate marker. A stop may win before we reacquire
        # the workspace fence, so no earlier authorization survives this boundary.
        if (
            not record.approved_by
            or record.state in {"cancelled", "cancel_requested"}
            or action.cancel_requested
            or action.state != "dispatching"
            or record.request_key not in {None, request_key}
        ):
            raise HTTPException(409, "publication cancelled or dispatch changed")
        owner(db, wid, record.approved_by)
        mandates.preconditions(
            db, mandate, action, authority.evidence(db, mandate, plan, now), now
        )
    rows = {
        r.step_id: r
        for r in db.scalars(
            select(PublicationStepRecord)
            .where(PublicationStepRecord.plan_id == plan_id)
            .with_for_update()
        )
    }
    if any(r.state in {"dispatching", "unknown", "conflict"} for r in rows.values()):
        db.commit()
        return None
    next_step = next((step for step in plan.steps if rows[step.step_id].state != "verified"), None)
    if next_step is None:
        record.state = "paused_verified"
        db.commit()
        return None
    parent = None
    for dependency in next_step.dependencies:
        previous = rows[dependency]
        if previous.state != "verified" or previous.receipt is None:
            raise HTTPException(409, "publication dependency unavailable")
        receipt = PublishReceipt.model_validate(previous.receipt)
        if (
            receipt.scope != plan.scope
            or receipt.plan_id != plan_id
            or receipt.outcome != "verified_effect"
        ):
            raise HTTPException(409, "publication dependency ownership mismatch")
        if next_step.operation.parent and dependency == next_step.operation.parent.step_id:
            parent = receipt.resource_id
    row = db.get(PublicationStepRecord, (plan_id, next_step.step_id))
    assert row is not None
    request = BoundRequest(
        plan_id=plan_id,
        plan_digest=record.digest,
        scope=plan.scope,
        step=next_step,
        parent_resource_id=parent,
        fence=uuid4().hex,
        dispatched_at=now,
    )
    row.attempt += 1
    row.fence, row.request, row.state = (
        request.fence,
        request.model_dump(mode="json"),
        "dispatching",
    )
    row.receipt = None
    record.state = "creating_paused"
    db.commit()  # Durable before emission; expired lease never implies safe resubmission.
    return request


def record_receipt(
    db: Session, wid: int, plan_id: str, receipt: PublishReceipt, now: datetime
) -> None:
    receipt = PublishReceipt.model_validate(receipt.model_dump(mode="json"))
    record, plan, _, _ = locked(db, wid, plan_id)
    row = db.get(PublicationStepRecord, (plan_id, receipt.step_id))
    if row is None or row.request is None:
        raise HTTPException(409, "no publication attempt")
    request = BoundRequest.model_validate(row.request)
    if not request.dispatched_at <= receipt.observed_at <= now:
        raise HTTPException(409, "publication receipt freshness mismatch")
    if (
        receipt.scope != plan.scope
        or receipt.plan_id != plan_id
        or receipt.fence != row.fence
        or receipt.request_digest != request.digest()
    ):
        raise HTTPException(409, "publication receipt scope/fence mismatch")
    if row.state == "verified":
        if (
            row.receipt is None
            or PublishReceipt.model_validate(row.receipt).resource_id != receipt.resource_id
        ):
            raise HTTPException(409, "conflicting verified receipt")
        return
    digest = fingerprint("inlet.publication-receipt.v1", receipt.model_dump(mode="json"))
    if (
        db.scalar(
            select(PublicationReceiptRecord.id).where(
                PublicationReceiptRecord.plan_id == plan_id,
                PublicationReceiptRecord.step_id == receipt.step_id,
                PublicationReceiptRecord.digest == digest,
            )
        )
        is None
    ):
        db.add(
            PublicationReceiptRecord(
                id=uuid4().hex,
                plan_id=plan_id,
                step_id=receipt.step_id,
                workspace_id=wid,
                digest=digest,
                request=request.model_dump(mode="json"),
                receipt=receipt.model_dump(mode="json"),
                recorded_at=now,
            )
        )
    row.state = {
        "verified_effect": "verified",
        "verified_no_effect": "pending",
        "unknown": "unknown",
        "conflict": "conflict",
    }[receipt.outcome]
    row.receipt = receipt.model_dump(mode="json")
    if record.state not in {"cancelled", "cancel_requested"}:
        record.state = (
            "outcome_unknown" if row.state in {"unknown", "conflict"} else "creating_paused"
        )
        db.flush()
        if all(
            s.state == "verified"
            for s in db.scalars(
                select(PublicationStepRecord).where(PublicationStepRecord.plan_id == plan_id)
            )
        ):
            record.state = "paused_verified"
    db.commit()  # Do not release the one horizon reservation on paused creation success.


def dispatch_next(
    db: Session,
    wid: int,
    plan_id: str,
    request_key: str,
    actor: str,
    authority: DatabaseFixtureAuthority,
    adapter: object,
    now: datetime,
) -> BoundRequest | None:
    transport = require_fixture(adapter)
    request = claim_next(db, wid, plan_id, request_key, actor, authority, now)
    if request is None:
        return None
    try:
        receipt = transport.apply_once(request, now)
    except Exception:
        receipt = PublishReceipt(
            scope=request.scope,
            plan_id=plan_id,
            step_id=request.step.step_id,
            fence=request.fence,
            request_digest=request.digest(),
            outcome="unknown",
            observed_at=now,
        )
    record_receipt(db, wid, plan_id, receipt, now)
    return request


def reconcile_step(
    db: Session, wid: int, plan_id: str, step_id: str, adapter: object, now: datetime
) -> None:
    transport = require_fixture(adapter)
    _, _, _, _ = locked(db, wid, plan_id)
    row = db.get(PublicationStepRecord, (plan_id, step_id))
    if (
        row is None
        or row.request is None
        or row.state not in {"dispatching", "unknown", "conflict"}
    ):
        raise HTTPException(409, "no uncertain publication step")
    request = BoundRequest.model_validate(row.request)
    db.rollback()  # No external network here; preserve future port's short transaction boundary.
    record_receipt(db, wid, plan_id, transport.reconcile(request, now), now)


def cancel(db: Session, wid: int, plan_id: str, actor: str, now: datetime) -> None:
    record, _, mandate, action = locked(db, wid, plan_id)
    owner(db, wid, actor)
    mandates.cancel(db, mandate, action, actor, now)
    record.state = "cancelled" if action.state == "cancelled" else "cancel_requested"
    db.commit()


def activation_preview(db: Session, wid: int, plan_id: str) -> str:
    record, _, _, _ = locked(db, wid, plan_id)
    if record.state != "paused_verified":
        raise HTTPException(409, "verified paused graph required")
    receipts = [
        row.receipt
        for row in db.scalars(
            select(PublicationStepRecord)
            .where(PublicationStepRecord.plan_id == plan_id)
            .order_by(PublicationStepRecord.step_id)
        )
    ]
    return fingerprint(
        "inlet.publication-activation.v1",
        {"plan_digest": record.digest, "receipts": receipts, "target": "ENABLED"},
    )


def approve_activation(
    db: Session,
    wid: int,
    plan_id: str,
    digest: str,
    actor: str,
    authority: DatabaseFixtureAuthority,
    now: datetime,
) -> None:
    record, plan, _, _ = locked(db, wid, plan_id)
    authority.validate(db, plan, actor, now)
    if activation_preview(db, wid, plan_id) != digest:
        raise HTTPException(409, "activation review changed")
    record.activation_digest, record.activation_approved_by = digest, actor
    db.commit()
    # This is a distinct offline approval receipt, not an activation implementation.
