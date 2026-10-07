"""Exact owned linked configuration storage; server-only, no HTTP or commit."""

import json
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.publication.contracts import fingerprint
from app.publication.execution_authorization import ExecutionAuthorizer
from app.publication.execution_contracts import ExecutionAccount
from app.publication.service import owner
from app.publication.social_customer_producer import catalog_request
from app.publication.social_review_models import (
    SocialConfigurationApproval,
    SocialConfigurationReview,
)
from app.publication.social_review_service import approval_digest
from app.publication.tiktok_linked_plan import LinkedPushPlanV1
from app.publication.tiktok_linked_review_contracts import LinkedPushConfigurationDocumentV1

if TYPE_CHECKING:
    from app.publication.tiktok_linked_contracts import (
        AdvertiserCapabilitiesObservationV1,
        IdentityInfoObservationV1,
    )

Clock = Callable[[], datetime]


def prepare(
    db: Session,
    wid: int,
    actor: str,
    document: LinkedPushConfigurationDocumentV1,
    clock: Clock,
    authorize: ExecutionAuthorizer,
) -> SocialConfigurationReview:
    """Server-only entry: document must come from selection, never a customer body.

    Caller retains the selection transaction/locks; no IO between selection and save.
    Confirmation always rebuilds selection, so a saved stale preview cannot authorize.
    """
    authorize(db, wid, actor)
    document = LinkedPushConfigurationDocumentV1.model_validate(document.model_dump())
    account = document.request.account
    if account.workspace_id != wid:
        raise HTTPException(404, "owned configuration unavailable")
    row = SocialConfigurationReview(
        id=uuid4().hex,
        workspace_id=wid,
        account_id=account.account.account_id,
        integration_id=account.account.connection_id,
        draft_id=document.request.draft_id,
        source_revision=document.request.draft_revision,
        digest=document.digest(),
        document=document.model_dump(mode="json"),
        created_by=actor,
        created_at=clock(),
    )
    authorize(db, wid, actor)
    db.add(row)
    db.flush()
    return row


def checked(
    db: Session,
    wid: int,
    review_id: str,
    actor: str,
    current: LinkedPushConfigurationDocumentV1,
    authorize: ExecutionAuthorizer,
) -> SocialConfigurationReview:
    authorize(db, wid, actor)
    row = db.get(SocialConfigurationReview, review_id, populate_existing=True)
    if row is None or row.workspace_id != wid:
        raise HTTPException(404, "owned configuration unavailable")
    saved = LinkedPushConfigurationDocumentV1.model_validate_json(
        json.dumps(row.document, allow_nan=False)
    )
    account = saved.request.account
    if (
        saved != current
        or saved.digest() != row.digest
        or saved.request.account.workspace_id != wid
        or row.account_id != account.account.account_id
        or row.integration_id != account.account.connection_id
        or row.draft_id != saved.request.draft_id
        or row.source_revision != saved.request.draft_revision
    ):
        raise HTTPException(409, "current exact supported configuration required")
    return row


def confirm(
    db: Session,
    wid: int,
    review_id: str,
    expected_digest: str,
    actor: str,
    current: LinkedPushConfigurationDocumentV1,
    clock: Clock,
    authorize: ExecutionAuthorizer,
) -> SocialConfigurationApproval:
    row = checked(db, wid, review_id, actor, current, authorize)
    if row.digest != expected_digest:
        raise HTTPException(409, "exact configuration digest required")
    previous = db.get(SocialConfigurationApproval, review_id, populate_existing=True)
    if previous is not None:
        owner(db, wid, previous.actor)
        if previous.review_digest != row.digest or previous.digest != approval_digest(previous):
            raise HTTPException(409, "configuration confirmation changed")
        return previous
    approval = SocialConfigurationApproval(
        review_id=row.id,
        workspace_id=wid,
        review_digest=row.digest,
        actor=actor,
        confirmed_at=clock(),
    )
    approval.digest = approval_digest(approval)
    authorize(db, wid, actor)
    db.add(approval)
    db.flush()
    return approval


def verify_plan(
    db: Session, wid: int, plan: LinkedPushPlanV1, actor: str
) -> LinkedPushConfigurationDocumentV1:
    reference = plan.review.configuration_review
    owner(db, wid, actor)
    row = db.get(SocialConfigurationReview, reference.review_id, populate_existing=True)
    if row is None or row.workspace_id != wid:
        raise HTTPException(404, "owned linked configuration unavailable")
    try:
        current = LinkedPushConfigurationDocumentV1.model_validate_json(
            json.dumps(row.document, allow_nan=False)
        )
    except ValueError:
        raise HTTPException(409, "exact linked configuration required") from None
    checked(db, wid, row.id, actor, current, lambda *_: owner(db, wid, actor))
    approval = db.get(SocialConfigurationApproval, row.id, populate_existing=True)
    fields = plan.review.configuration
    if (
        approval is None
        or approval.workspace_id != wid
        or approval.review_digest != row.digest
        or reference.review_digest != row.digest
        or reference.approval_digest != approval.digest
        or approval.digest != approval_digest(approval)
        or current.request
        != catalog_request(plan.review.source, ExecutionAccount.from_publication(plan.review.scope))
        or current.configuration != fields
        or current.configuration_digest
        != fingerprint(
            "inlet.tiktok-linked-push-configuration-fields.v1", fields.model_dump(mode="json")
        )
    ):
        raise HTTPException(409, "exact confirmed linked configuration required")
    owner(db, wid, approval.actor)
    return current


def current_capabilities(
    document: LinkedPushConfigurationDocumentV1,
    identity: "IdentityInfoObservationV1",
    advertiser: "AdvertiserCapabilitiesObservationV1",
    now: datetime,
) -> None:
    """Pure current TT_USER check; callers refresh owned facts outside DB locks.

    Timestamp changes do not force new consent. Original commitments remain in
    the immutable document; current observations must have the same owned request
    and satisfy present eligibility. BC permission is deliberately not inferred.
    """
    from app.publication.tiktok_linked_contracts import (
        AdvertiserCapabilitiesObservationV1,
        IdentityInfoObservationV1,
    )

    document = LinkedPushConfigurationDocumentV1.model_validate_json(document.model_dump_json())
    identity = IdentityInfoObservationV1.model_validate_json(identity.model_dump_json())
    advertiser = AdvertiserCapabilitiesObservationV1.model_validate_json(
        advertiser.model_dump_json()
    )
    if document.configuration.identity.identity_type == "BC_AUTH_TT":
        raise HTTPException(409, "linked_bc_publishing_permission_unavailable")
    if (
        now.tzinfo is None
        or identity.request != document.identity_observation.request
        or advertiser.request != document.advertiser_observation.request
        or not identity.observed_at <= now < identity.expires_at
        or not advertiser.observed_at <= now < advertiser.expires_at
        or identity.available_status != "AVAILABLE"
        or identity.is_gpppa.presence != "present"
        or identity.is_gpppa.value is not False
        or identity.can_push_video.presence != "present"
        or identity.can_push_video.value is not True
    ):
        raise HTTPException(409, "current_linked_capabilities_unavailable")
