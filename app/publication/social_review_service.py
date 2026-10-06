"""Persist exact nonpersonal configuration reviews. No publication or live factory."""

from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.campaign_review import service as sources
from app.campaign_review.contracts import MediaStore, MetaImage, TikTokVideo
from app.publication import execution_mandates as mandates
from app.publication.contracts import fingerprint
from app.publication.execution_authorization import ExecutionAuthorizer
from app.publication.execution_contracts import ExecutionAccount
from app.publication.scoped_media import ScopedProviderMediaReader
from app.publication.service import owner
from app.publication.social_catalog import (
    MetaConfigurationProfile,
    SocialCatalog,
    TikTokConfigurationProfile,
)
from app.publication.social_customer_producer import SocialPlanProducer, catalog_request
from app.publication.social_review_contracts import (
    SocialAnswer,
    SocialConfigurationDocument,
    SocialRequirements,
)
from app.publication.social_review_models import (
    SocialConfigurationApproval,
    SocialConfigurationReview,
)

if TYPE_CHECKING:
    from app.publication.social_catalog import MetaDeclaration
    from app.publication.social_contracts import SocialPublishPlan

Clock = Callable[[], datetime]
Profile = MetaConfigurationProfile | TikTokConfigurationProfile


def selection(
    db: Session,
    wid: int,
    actor: str,
    account: ExecutionAccount,
    catalog: SocialCatalog,
    option_id: str,
    profile: Profile,
    requirements: SocialRequirements,
    answer: SocialAnswer,
    cover_media_id: str | None,
    environment: str,
    store: MediaStore,
    clock: Clock,
    authorize: ExecutionAuthorizer,
) -> SocialConfigurationDocument:
    # Catalog IO happens outside this function. Reauthorize its original customer
    # principal after IO, before downstream locks; fresh clocks follow media IO.
    authorize(db, wid, actor)
    mandates.current_account(db, account)
    row, artifact = sources.preview(db, wid, catalog.request.draft_id, store, clock())
    if row.approved_by is None or not artifact.offline_reviewable or artifact.blockers:
        raise HTTPException(409, "approved source required")
    owner(db, wid, row.approved_by)
    content = artifact.definition.content
    if not isinstance(content, (MetaImage, TikTokVideo)):
        raise HTTPException(409, "social source required")
    media = ScopedProviderMediaReader(db, store)
    primary = media.binding(wid, content.media.media_id)
    cover = media.binding(wid, cover_media_id) if cover_media_id else None
    authorize(db, wid, actor)
    now = clock()
    option = next((o for o in catalog.options if o.identifier(catalog.request) == option_id), None)
    if (
        account.workspace_id != wid
        or catalog.request != catalog_request(artifact, account)
        or not catalog.observed_at <= now < catalog.expires_at
        or option is None
        or option.kind != profile.kind
        or option.profile_digest != profile.digest()
        or requirements.profile_digest != profile.digest()
        or isinstance(profile, MetaConfigurationProfile)
        and profile.dsa_required
        or profile.currency != catalog.currency
        or catalog.currency != artifact.definition.currency
    ):
        raise HTTPException(409, "current verified non-DSA configuration required")
    fields = SocialPlanProducer([profile]).configuration_for_review(
        db,
        artifact,
        account,
        option_id,
        catalog,
        store,
        now,
        actor=actor,
        cover_media_id=cover_media_id,
    )
    authorize(db, wid, actor)
    if not catalog.observed_at <= clock() < catalog.expires_at:
        raise HTTPException(409, "current social catalog required")
    return SocialConfigurationDocument.model_validate(
        dict(
            request=catalog.request,
            environment=environment,
            option_id=option_id,
            configuration=fields,
            configuration_digest=fingerprint(
                "inlet.social-configuration-fields.v1", fields.model_dump(mode="json")
            ),
            requirements=requirements,
            primary=primary,
            cover=cover,
            answer=answer,
        )
    )


def prepare(
    db: Session,
    wid: int,
    actor: str,
    document: SocialConfigurationDocument,
    clock: Clock,
    authorize: ExecutionAuthorizer,
) -> SocialConfigurationReview:
    """Server-only entry: document must come from selection, never a customer body.

    Caller retains the selection transaction/locks; no IO between selection and save.
    Confirmation always rebuilds selection, so a saved stale preview cannot authorize.
    """
    authorize(db, wid, actor)
    document = SocialConfigurationDocument.model_validate(document.model_dump())
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
    db.add(row)
    db.flush()
    return row


def checked(
    db: Session,
    wid: int,
    review_id: str,
    actor: str,
    current: SocialConfigurationDocument,
    authorize: ExecutionAuthorizer,
) -> SocialConfigurationReview:
    authorize(db, wid, actor)
    row = db.get(SocialConfigurationReview, review_id, populate_existing=True)
    if row is None or row.workspace_id != wid:
        raise HTTPException(404, "owned configuration unavailable")
    saved = SocialConfigurationDocument.model_validate(row.document)
    account = saved.request.account
    if (
        saved != current
        or saved.digest() != row.digest
        or saved.request.account.workspace_id != wid
        or row.account_id != account.account.account_id
        or row.integration_id != account.account.connection_id
        or row.draft_id != saved.request.draft_id
        or row.source_revision != saved.request.draft_revision
        or saved.blockers()
    ):
        raise HTTPException(409, "current exact supported configuration required")
    return row


def confirm(
    db: Session,
    wid: int,
    review_id: str,
    expected_digest: str,
    actor: str,
    current: SocialConfigurationDocument,
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
    db.add(approval)
    db.flush()
    return approval


def approval_digest(row: SocialConfigurationApproval) -> str:
    from app.shopify.security import utc

    return fingerprint(
        "inlet.social-configuration-approval.v1",
        dict(
            review_id=row.review_id,
            workspace_id=row.workspace_id,
            review_digest=row.review_digest,
            actor=row.actor,
            confirmed_at=utc(row.confirmed_at).isoformat(),
        ),
    )


def read_confirmed(
    db: Session,
    wid: int,
    review_id: str,
    expected_digest: str,
    actor: str,
    current: SocialConfigurationDocument,
    authorize: ExecutionAuthorizer,
) -> SocialConfigurationApproval:
    """Owned persisted confirmation only; caller rebuilds selection after every IO."""
    row = checked(db, wid, review_id, actor, current, authorize)
    approval = db.get(SocialConfigurationApproval, review_id, populate_existing=True)
    if (
        row.digest != expected_digest
        or approval is None
        or approval.workspace_id != wid
        or approval.review_digest != row.digest
        or approval.digest != approval_digest(approval)
    ):
        raise HTTPException(409, "exact customer configuration confirmation required")
    owner(db, wid, approval.actor)
    return approval


def verify_plan(
    db: Session,
    wid: int,
    plan: "SocialPublishPlan",
    actor: str,
) -> SocialConfigurationDocument:
    """Verify exact DB authority, not mere presence of an approval identifier."""
    from app.publication.social_contracts import MetaImagePublicationFields

    reference = plan.review.configuration_review
    if reference is None:
        raise HTTPException(409, "customer configuration confirmation required")
    owner(db, wid, actor)
    row = db.get(SocialConfigurationReview, reference.review_id, populate_existing=True)
    if row is None or row.workspace_id != wid:
        raise HTTPException(404, "owned configuration unavailable")
    try:
        current = SocialConfigurationDocument.model_validate(row.document)
    except ValueError as exc:
        # Version1 has no complete configuration commitment and cannot be upgraded
        # silently into authority by interpreting the new fields as optional.
        raise HTTPException(409, "new exact configuration review required") from exc
    checked(db, wid, row.id, actor, current, lambda *_: owner(db, wid, actor))
    approval = db.get(SocialConfigurationApproval, row.id, populate_existing=True)
    fields = plan.review.configuration
    primary = fields.image if isinstance(fields, MetaImagePublicationFields) else fields.video
    cover = None if isinstance(fields, MetaImagePublicationFields) else fields.cover
    if (
        approval is None
        or approval.workspace_id != wid
        or approval.review_digest != row.digest
        or reference.review_digest != row.digest
        or reference.approval_digest != approval.digest
        or approval.digest != approval_digest(approval)
        or current.request
        != catalog_request(plan.review.source, ExecutionAccount.from_publication(plan.review.scope))
        or current.configuration_digest
        != fingerprint("inlet.social-configuration-fields.v1", fields.model_dump(mode="json"))
        or current.primary != primary
        or current.cover != cover
        or isinstance(fields, MetaImagePublicationFields)
        and (
            fields.dsa_beneficiary is not None
            or fields.dsa_payor is not None
            or fields.special_ad_category_declaration != "none_applicable"
        )
    ):
        raise HTTPException(409, "exact confirmed social configuration required")
    owner(db, wid, approval.actor)
    return current


def meta_declaration(
    db: Session,
    wid: int,
    review_id: str,
    expected_digest: str,
    actor: str,
    current: SocialConfigurationDocument,
    authorize: ExecutionAuthorizer,
) -> "MetaDeclaration":
    from app.publication.social_catalog import MetaDeclaration
    from app.publication.social_review_contracts import MetaNoDSAAnswer
    from app.shopify.security import utc

    approval = read_confirmed(db, wid, review_id, expected_digest, actor, current, authorize)
    if not isinstance(current.answer, MetaNoDSAAnswer):
        raise HTTPException(409, "confirmed Meta configuration required")
    return MetaDeclaration(
        request_digest=current.request.digest(),
        audit_record_id=review_id,
        confirmed_by=approval.actor,
        confirmed_at=utc(approval.confirmed_at),
        special_ad_category_declaration="none_applicable",
        dsa_beneficiary=None,
        dsa_payor=None,
    )
