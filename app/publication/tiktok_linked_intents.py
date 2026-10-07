"""Refresh server-owned linked facts outside locks, retain the original customer consent."""

import json
from dataclasses import replace
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.campaign_review.contracts import MediaStore, ReviewArtifact
from app.publication import coordinator, customer_intents
from app.publication import tiktok_linked_review_service as reviews
from app.publication.contracts import PublicationScope
from app.publication.customer_runtime import CustomerExecutionRuntime
from app.publication.execution_models import ProviderExecutionReview
from app.publication.social_contracts import SocialConfigurationApprovalRef
from app.publication.social_execution_intents import SocialCreationIntent
from app.publication.social_review_models import (
    SocialConfigurationApproval,
    SocialConfigurationReview,
)
from app.publication.social_review_service import approval_digest
from app.publication.tiktok_linked_catalog import LinkedPushCatalogV1
from app.publication.tiktok_linked_customer_contracts import LinkedPushReviewIntent
from app.publication.tiktok_linked_plan import (
    LinkedPushPlanV1,
    LinkedPushPublicationReviewV1,
    compile_linked_push,
)
from app.publication.tiktok_linked_review_contracts import LinkedPushConfigurationDocumentV1
from app.publication.tiktok_linked_selection import required, resolve


def refresh_configuration(
    db: Session,
    wid: int,
    identifier: str,
    expected_digest: str,
    actor: str,
    media: MediaStore,
    runtime: CustomerExecutionRuntime,
) -> tuple[LinkedPushConfigurationDocumentV1, ReviewArtifact, LinkedPushCatalogV1]:
    runtime.creation.authorize(db, wid, actor)
    row = db.get(SocialConfigurationReview, identifier, populate_existing=True)
    if row is None or row.workspace_id != wid:
        raise HTTPException(404, "owned_linked_configuration_unavailable")
    try:
        saved = LinkedPushConfigurationDocumentV1.model_validate_json(
            json.dumps(row.document, allow_nan=False)
        )
    except ValueError:
        raise HTTPException(409, "exact_linked_configuration_required") from None
    if saved.digest() != expected_digest or row.digest != expected_digest:
        raise HTTPException(409, "exact_linked_configuration_required")
    current, artifact, catalog = resolve(
        db,
        wid,
        actor,
        LinkedPushReviewIntent(
            draft_id=saved.request.draft_id,
            draft_revision=saved.request.draft_revision,
            option_id=saved.option_id,
            answer=saved.answer,
            cover_media_id=saved.configuration.cover.media_id,
        ),
        media,
        required(runtime.linked_review),
        runtime.creation.authorize,
    )
    excluded = {"identity_observation_digest", "advertiser_observation_digest"}
    if (
        saved.request != current.request
        or saved.answer != current.answer
        or saved.requirements != current.requirements
        or saved.environment != current.environment
        or saved.configuration.model_dump(exclude=excluded)
        != current.configuration.model_dump(exclude=excluded)
    ):
        raise HTTPException(409, "linked_configuration_changed")
    reviews.current_capabilities(
        saved, current.identity_observation, current.advertiser_observation, runtime.clock()
    )
    reviews.checked(db, wid, identifier, actor, saved, runtime.creation.authorize)
    return saved, artifact, catalog


def prepare_plan(
    db: Session,
    wid: int,
    identifier: str,
    expected_digest: str,
    actor: str,
    media: MediaStore,
    runtime: CustomerExecutionRuntime,
) -> tuple[LinkedPushPlanV1, CustomerExecutionRuntime]:
    saved, artifact, catalog = refresh_configuration(
        db, wid, identifier, expected_digest, actor, media, runtime
    )
    approval = db.get(SocialConfigurationApproval, identifier, populate_existing=True)
    if (
        approval is None
        or approval.workspace_id != wid
        or approval.review_digest != expected_digest
        or approval.digest != approval_digest(approval)
    ):
        raise HTTPException(409, "exact_linked_confirmation_required")
    from app.publication.service import owner

    owner(db, wid, approval.actor)
    source = artifact.definition
    scope = PublicationScope(
        **saved.request.account.model_dump(),
        mandate_id=source.mandate_id,
        mandate_revision=source.mandate_revision,
    )
    plan = compile_linked_push(
        LinkedPushPublicationReviewV1(
            source=artifact,
            source_digest=artifact.fingerprint(),
            scope=scope,
            configuration=saved.configuration,
            configuration_review=SocialConfigurationApprovalRef(
                review_id=identifier, review_digest=expected_digest, approval_digest=approval.digest
            ),
            qualification_blockers=list(catalog.qualification_blockers),
        )
    )
    previous = runtime.creation.linked_configuration_current
    fresh_identity = next(
        value
        for value in catalog.identities
        if value.request.identity == saved.configuration.identity
    )

    def validate(document: LinkedPushConfigurationDocumentV1, now: datetime) -> None:
        if document != saved or not catalog.observed_at <= now < catalog.expires_at:
            raise HTTPException(409, "linked_configuration_changed")
        reviews.current_capabilities(document, fresh_identity, catalog.advertiser, now)
        if previous is None:
            raise HTTPException(409, "linked_configuration_unavailable")
        previous(document, now)

    creation = replace(runtime.creation, linked_configuration_current=validate)
    activation = runtime.activation
    if activation is not None:
        activation = replace(activation, review=replace(activation.review, creation=creation))
    runtime.creation.authorize(db, wid, actor)
    return plan, replace(runtime, creation=creation, activation=activation)


def prepare_creation(
    db: Session,
    wid: int,
    body: SocialCreationIntent,
    actor: str,
    media: MediaStore,
    runtime: CustomerExecutionRuntime,
) -> ProviderExecutionReview:
    plan, refreshed = prepare_plan(
        db,
        wid,
        body.configuration_review_id,
        body.expected_configuration_digest,
        actor,
        media,
        runtime,
    )
    binding = customer_intents.binding(db, wid, body.mandate_id, body.mandate_revision)
    return coordinator.prepare_creation(
        db, wid, plan, binding, actor, media, refreshed.creation, refreshed.clock
    )
