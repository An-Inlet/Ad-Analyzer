"""Owned social creation intents and request-local forward authorization.

Discovery is refreshed before economic locks. Historical reconciliation deliberately
uses the original request without this forward-only current-configuration gate.
"""

from dataclasses import replace
from datetime import datetime

from fastapi import HTTPException
from pydantic import Field
from sqlalchemy.orm import Session

from app.campaign_review.contracts import MediaStore
from app.goals.schemas import StrictModel
from app.publication import coordinator, customer_intents, social_review_service
from app.publication.activation_review import ActivationExecutionReview
from app.publication.coordinator_contracts import CreationExecutionReview
from app.publication.customer_runtime import CustomerExecutionRuntime
from app.publication.execution_models import ProviderExecutionReview
from app.publication.provider_contracts import Digest, Id
from app.publication.social_catalog import MetaDeclaration, SocialCatalogRequest
from app.publication.social_contracts import SocialConfigurationApprovalRef, SocialPublishPlan
from app.publication.social_customer_producer import SocialPlanProducer
from app.publication.social_review_contracts import SocialConfigurationDocument
from app.publication.social_review_models import SocialConfigurationReview
from app.publication.social_selection import ReviewIntent, resolve_selection, runtime_required


class SocialCreationIntent(StrictModel):
    configuration_review_id: Id
    expected_configuration_digest: Digest
    mandate_id: Id
    mandate_revision: int = Field(strict=True, ge=1)


def prepare_plan(
    db: Session,
    wid: int,
    identifier: str,
    expected_digest: str,
    actor: str,
    media: MediaStore,
    runtime: CustomerExecutionRuntime,
) -> tuple[SocialPublishPlan, CustomerExecutionRuntime]:
    runtime.creation.authorize(db, wid, actor)
    discovery = runtime_required(runtime.social_review)
    if discovery.environment != runtime.creation.environment:
        raise HTTPException(409, "social_configuration_environment_changed")
    row = db.get(SocialConfigurationReview, identifier, populate_existing=True)
    if row is None or row.workspace_id != wid:
        raise HTTPException(404, "owned_configuration_unavailable")
    try:
        saved = SocialConfigurationDocument.model_validate(row.document)
    except ValueError:
        raise HTTPException(409, "new_exact_configuration_review_required") from None
    current, artifact, catalog = resolve_selection(
        db,
        wid,
        actor,
        ReviewIntent(
            draft_id=saved.request.draft_id,
            draft_revision=saved.request.draft_revision,
            option_id=saved.option_id,
            answer=saved.answer,
            cover_media_id=saved.cover.media_id if saved.cover else None,
        ),
        media,
        discovery,
        runtime.creation.authorize,
    )
    if runtime.creation.environment == "live" and catalog.qualification_blockers:
        raise HTTPException(409, "social_native_configuration_unqualified")
    approval = social_review_service.read_confirmed(
        db,
        wid,
        identifier,
        expected_digest,
        actor,
        current,
        runtime.creation.authorize,
    )

    # Only this exact owned confirmation can satisfy the producer's Meta declaration
    # reader. No callback, audited actor, native proof or plan comes from the client.
    def declaration(request: SocialCatalogRequest, now: datetime) -> MetaDeclaration:
        if request != current.request:
            raise HTTPException(409, "social_configuration_changed")
        return social_review_service.meta_declaration(
            db,
            wid,
            identifier,
            expected_digest,
            actor,
            current,
            runtime.creation.authorize,
        )

    producer = SocialPlanProducer(list(discovery.profiles), declarations=declaration)
    plan = producer.produce(
        db,
        artifact,
        current.request.account,
        current.option_id,
        catalog,
        media,
        runtime.clock(),
        actor=actor,
        cover_media_id=current.cover.media_id if current.cover else None,
        configuration_review=SocialConfigurationApprovalRef(
            review_id=identifier,
            review_digest=expected_digest,
            approval_digest=approval.digest,
        ),
    )
    runtime.creation.authorize(db, wid, actor)

    previous_validator = runtime.creation.social_configuration_current

    def validate(document: SocialConfigurationDocument, now: datetime) -> None:
        # Immutable request-local snapshot; canonical authority is still independently
        # reloaded by coordinator.verify_plan at every locked forward boundary.
        profiles = {p.digest(): p for p in discovery.profiles}
        if (
            document != current
            or discovery.environment != runtime.creation.environment
            or not catalog.observed_at <= now < catalog.expires_at
            or document.requirements.profile_digest not in profiles
            or discovery.requirements.get(document.requirements.profile_digest)
            != document.requirements
        ):
            raise HTTPException(409, "social_configuration_changed")
        if previous_validator is not None:
            previous_validator(document, now)

    creation = replace(runtime.creation, social_configuration_current=validate)
    activation = runtime.activation
    if activation is not None:
        activation = replace(activation, review=replace(activation.review, creation=creation))
    return plan, replace(runtime, creation=creation, activation=activation)


def refresh_social_execution(
    db: Session,
    workspace_id: int,
    review: ProviderExecutionReview,
    actor: str,
    media: MediaStore,
    runtime: CustomerExecutionRuntime,
) -> CustomerExecutionRuntime:
    runtime.creation.authorize(db, workspace_id, actor)
    if review.workspace_id != workspace_id:
        raise HTTPException(404, "owned_execution_review_unavailable")
    document = (
        ActivationExecutionReview.model_validate(review.document)
        if review.document.get("purpose") == "activate"
        else CreationExecutionReview.model_validate(review.document)
    )
    plan = (
        document.creation_plan if isinstance(document, ActivationExecutionReview) else document.plan
    )
    if review.digest != document.digest() or review.plan_digest != document.plan.digest():
        raise HTTPException(409, "execution_review_integrity_unavailable")
    if not isinstance(plan, SocialPublishPlan):
        return runtime
    reference = plan.review.configuration_review
    if reference is None:
        raise HTTPException(409, "customer_configuration_confirmation_required")
    current_plan, refreshed = prepare_plan(
        db,
        workspace_id,
        reference.review_id,
        reference.review_digest,
        actor,
        media,
        runtime,
    )
    if current_plan != plan:
        raise HTTPException(409, "social_configuration_changed")
    return refreshed


def prepare_creation(
    db: Session,
    wid: int,
    body: SocialCreationIntent,
    actor: str,
    media: MediaStore,
    runtime: CustomerExecutionRuntime,
) -> ProviderExecutionReview:
    plan, server = prepare_plan(
        db,
        wid,
        body.configuration_review_id,
        body.expected_configuration_digest,
        actor,
        media,
        runtime,
    )
    server.creation.authorize(db, wid, actor)
    binding = customer_intents.binding(db, wid, body.mandate_id, body.mandate_revision)
    return coordinator.prepare_creation(
        db, wid, plan, binding, actor, media, server.creation, server.clock
    )
