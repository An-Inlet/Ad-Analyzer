"""Server-derived, append-only provider review. No production dispatch is installed."""

from collections.abc import Callable
from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import advertising_capabilities
from app.ads.models import AdvertisingAccount
from app.billing.entitlements import paid_work
from app.campaign_review import service as source_reviews
from app.campaign_review.contracts import MediaStore
from app.campaign_review.models import CampaignDraft, CampaignRevision
from app.executors.google_publication import GooglePublicationHTTP
from app.google_connections.models import GoogleCustomerConnection
from app.mandates import service as mandates
from app.publication.contracts import PublicationScope
from app.publication.execution_authorization import ExecutionAuthorizer, owner_authorizer
from app.publication.google_compiler import compile_google
from app.publication.google_qualification import qualify_google
from app.publication.provider_contracts import (
    GooglePublicationFields,
    GoogleQualificationEvidence,
    ProviderContext,
    ProviderPublicationReview,
    ProviderPublishPlan,
)
from app.publication.provider_models import (
    ProviderQualificationRecord,
    ProviderReviewApproval,
    ProviderReviewRecord,
)
from app.publication.service import owner


def current_review(
    db: Session,
    wid: int,
    draft_id: str,
    fields: GooglePublicationFields,
    actor: str,
    store: MediaStore,
    now: datetime,
) -> ProviderPublicationReview:
    """Lock order: workspace → mandate → draft/native source; all from current DB."""
    mandates.workspace_lock(db, wid)
    owner(db, wid, actor)
    paid_work(db, wid, now)
    draft = db.scalar(
        select(CampaignDraft).where(CampaignDraft.id == draft_id, CampaignDraft.workspace_id == wid)
    )
    if draft is None:
        raise HTTPException(404, "campaign draft unavailable")
    revision = db.get(CampaignRevision, (draft.id, draft.revision))
    assert revision is not None
    mandates.owned(db, wid, str(revision.artifact["definition"]["mandate_id"]))
    row, artifact = source_reviews.preview(db, wid, draft.id, store, now)
    if row.approved_by is None or artifact.definition.account.platform != "google_ads":
        raise HTTPException(409, "approved Google source review required")
    account = db.get(AdvertisingAccount, artifact.definition.account.account_id)
    native = db.scalar(
        select(GoogleCustomerConnection)
        .where(
            GoogleCustomerConnection.workspace_id == wid,
            GoogleCustomerConnection.account_id == artifact.definition.account.account_id,
            GoogleCustomerConnection.integration_id == artifact.definition.account.connection_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if (
        account is None
        or native is None
        or native.status != "connected"
        or account.external_account_id != native.external_account_id
        or fields.login_customer_id != native.login_customer_id
        or account.currency_code != artifact.definition.currency
    ):
        raise HTTPException(409, "current provider account unavailable")
    scope = PublicationScope(
        workspace_id=wid,
        account=artifact.definition.account,
        external_advertiser_id=native.external_account_id,
        connection_version=f"google:{native.id}:{native.generation}",
        mandate_id=artifact.definition.mandate_id,
        mandate_revision=artifact.definition.mandate_revision,
    )
    return ProviderPublicationReview(
        source=artifact,
        source_digest=row.digest,
        scope=scope,
        configuration=fields,
        qualification_blockers=["configuration_qualification_required"],
    )


def prepare_google(
    db: Session,
    wid: int,
    draft_id: str,
    fields: GooglePublicationFields,
    actor: str,
    store: MediaStore,
    transport: GooglePublicationHTTP,
    context_factory: Callable[[PublicationScope], ProviderContext],
    clock: Callable[[], datetime],
    *,
    authorize: ExecutionAuthorizer = owner_authorizer,
) -> ProviderReviewRecord:
    """Transport/context are injected by server runtime; no route accepts caller evidence.

    Read qualification outside locks, then re-read current scope/source/owner before
    persisting. A reconnect, changed source or revoked entitlement during IO aborts.
    Each refresh creates new immutable evidence and review; existing approvals stay bound.
    """
    advertising_capabilities.require_advertising_write()
    authorize(db, wid, actor)
    now = clock()
    review = current_review(db, wid, draft_id, fields, actor, store, now)
    db.commit()  # release lifecycle locks before bounded provider reads
    context = context_factory(review.scope)
    evidence = qualify_google(review, context, transport, now)
    authorize(db, wid, actor)
    current = current_review(db, wid, draft_id, fields, actor, store, clock())
    now = clock()  # lifecycle locks may have waited beyond qualification expiry
    if (
        current.configuration_binding() != review.configuration_binding()
        or not evidence.observed_at <= now < evidence.expires_at
    ):
        raise HTTPException(409, "provider qualification became stale")
    qualified = ProviderPublicationReview.model_validate(
        {
            **current.model_dump(),
            "qualification": evidence.model_dump(),
            "qualification_blockers": [],
        }
    )
    plan = compile_google(qualified)
    existing = db.scalar(
        select(ProviderReviewRecord).where(
            ProviderReviewRecord.workspace_id == wid,
            ProviderReviewRecord.plan_digest == plan.digest(),
        )
    )
    paid_work(db, wid, clock())
    now = clock()  # final persistence check after database reads, including deduplication
    if not evidence.observed_at <= now < evidence.expires_at:
        raise HTTPException(409, "provider qualification became stale")
    if existing is not None:
        return existing
    qualification = ProviderQualificationRecord(
        id=uuid4().hex,
        workspace_id=wid,
        account_id=current.scope.account.account_id,
        integration_id=current.scope.account.connection_id,
        draft_id=draft_id,
        source_revision=current.source.revision,
        provider="google_ads",
        api_version="v25",
        binding_digest=current.configuration_binding(),
        evidence=evidence.model_dump(mode="json"),
        observed_at=evidence.observed_at,
        expires_at=evidence.expires_at,
        created_by=actor,
    )
    db.add(qualification)
    db.flush()
    result = ProviderReviewRecord(
        id=uuid4().hex,
        workspace_id=wid,
        qualification_id=qualification.id,
        draft_id=draft_id,
        source_revision=current.source.revision,
        review_digest=qualified.digest(),
        plan_digest=plan.digest(),
        review=qualified.model_dump(mode="json"),
        plan=plan.model_dump(mode="json"),
        created_by=actor,
        created_at=now,
    )
    db.add(result)
    db.commit()
    return result


def checked_review(
    db: Session,
    wid: int,
    review_id: str,
    actor: str,
    store: MediaStore,
    clock: Callable[[], datetime],
) -> tuple[ProviderReviewRecord, ProviderPublishPlan]:
    # Read identifiers first, then acquire fixed workspace/source lock order and reload.
    row = db.scalar(
        select(ProviderReviewRecord).where(
            ProviderReviewRecord.id == review_id, ProviderReviewRecord.workspace_id == wid
        )
    )
    if row is None:
        raise HTTPException(404, "provider review unavailable")
    review = ProviderPublicationReview.model_validate(row.review)
    current = current_review(db, wid, row.draft_id, review.configuration, actor, store, clock())
    row = db.scalar(
        select(ProviderReviewRecord)
        .where(
            ProviderReviewRecord.id == review_id,
            ProviderReviewRecord.workspace_id == wid,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    assert row is not None
    evidence_row = db.scalar(
        select(ProviderQualificationRecord)
        .where(
            ProviderQualificationRecord.id == row.qualification_id,
            ProviderQualificationRecord.workspace_id == wid,
        )
        .execution_options(populate_existing=True)
    )
    if evidence_row is None:
        raise HTTPException(409, "provider qualification unavailable")
    evidence = GoogleQualificationEvidence.model_validate(evidence_row.evidence)
    plan = ProviderPublishPlan.model_validate(row.plan)
    now = clock()  # sample after every potentially blocking lifecycle/review read
    if (
        review.digest() != row.review_digest
        or plan.digest() != row.plan_digest
        or plan.review != review
        or compile_google(review) != plan
        or review.scope.workspace_id != wid
        or review.source.draft_id != row.draft_id
        or review.source.revision != row.source_revision
        or current.configuration_binding() != review.configuration_binding()
        or review.qualification != evidence
        or review.qualification_blockers
        or evidence_row.binding_digest != current.configuration_binding()
        or evidence_row.account_id != current.scope.account.account_id
        or evidence_row.integration_id != current.scope.account.connection_id
        or evidence_row.draft_id != row.draft_id
        or evidence_row.source_revision != row.source_revision
        or evidence_row.provider != "google_ads"
        or evidence_row.api_version != "v25"
        or not evidence.observed_at <= now < evidence.expires_at
    ):
        raise HTTPException(409, "provider review or qualification changed")
    return row, plan


def approve(
    db: Session,
    wid: int,
    review_id: str,
    review_digest: str,
    plan_digest: str,
    actor: str,
    store: MediaStore,
    clock: Callable[[], datetime],
) -> ProviderReviewApproval:
    advertising_capabilities.require_advertising_write()
    row, plan = checked_review(db, wid, review_id, actor, store, clock)
    if row.review_digest != review_digest or row.plan_digest != plan_digest:
        raise HTTPException(409, "exact provider review and plan required")
    approval = db.get(ProviderReviewApproval, row.id)
    paid_work(db, wid, clock())
    now = clock()
    evidence = plan.review.qualification
    if evidence is None or not evidence.observed_at <= now < evidence.expires_at:
        raise HTTPException(409, "provider qualification became stale")
    if approval is None:
        approval = ProviderReviewApproval(
            review_id=row.id,
            workspace_id=wid,
            review_digest=review_digest,
            plan_digest=plan_digest,
            actor=actor,
            approved_at=now,
        )
        db.add(approval)
    db.commit()
    return approval


def publication_authority(
    db: Session,
    wid: int,
    review_id: str,
    actor: str,
    store: MediaStore,
    clock: Callable[[], datetime],
) -> None:
    row, _ = checked_review(db, wid, review_id, actor, store, clock)
    approval = db.get(ProviderReviewApproval, row.id)
    if (
        approval is None
        or approval.workspace_id != wid
        or approval.review_digest != row.review_digest
        or approval.plan_digest != row.plan_digest
    ):
        raise HTTPException(409, "provider review approval required")
    owner(db, wid, approval.actor)
    # Explicit missing implementation, not permission inferred from B07's simulation.
    # A subsequent production-mandate contract must derive current consent and reserve
    # exposure before any durable provider dispatch can be claimed.
    raise HTTPException(409, "production publication mandate implementation unavailable")


def view(row: ProviderReviewRecord) -> dict[str, Any]:
    """Exact renderable fields. No claim of live availability or permission."""
    return {
        "id": row.id,
        "review_digest": row.review_digest,
        "plan_digest": row.plan_digest,
        "review": row.review,
        "plan": row.plan,
        "publication_eligible": False,
        "remaining_implementation": [
            "production_publication_mandate",
            "provider_dispatch_claim",
            "separate_activation",
            "exposure_settlement",
        ],
    }
