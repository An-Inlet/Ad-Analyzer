"""Linked Push customer intents; all provider facts are derived by the configured server."""

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Response

from app.api.customer_execution import Runtime, Store, bound
from app.api.customer_social_review import ConfirmationIntent
from app.campaign_review.contracts import ReviewArtifact
from app.campaign_review.models import CampaignRevision
from app.customers.access import Database, MutationPrincipal, Principal, Provider
from app.publication import customer_intents, tiktok_linked_intents
from app.publication import tiktok_linked_review_service as reviews
from app.publication.service import owner
from app.publication.social_execution_intents import SocialCreationIntent
from app.publication.social_review_models import (
    SocialConfigurationApproval,
    SocialConfigurationReview,
)
from app.publication.social_review_service import approval_digest
from app.publication.social_selection import CatalogIntent
from app.publication.tiktok_linked_customer_contracts import LinkedPushReviewIntent
from app.publication.tiktok_linked_review_contracts import LinkedPushConfigurationDocumentV1
from app.publication.tiktok_linked_selection import discover, required, resolve

router = APIRouter(
    prefix="/api/customer/v1/workspaces/{workspace_id}/execution/tiktok/linked", tags=["customer"]
)


def owned(db: Database, wid: int, actor: str, identifier: str) -> SocialConfigurationReview:
    owner(db, wid, actor)
    row = db.get(SocialConfigurationReview, identifier, populate_existing=True)
    if row is None or row.workspace_id != wid:
        raise HTTPException(404, "owned_linked_configuration_unavailable")
    return row


def view(db: Database, row: SocialConfigurationReview) -> dict[str, Any]:
    try:
        document = LinkedPushConfigurationDocumentV1.model_validate_json(
            json.dumps(row.document, allow_nan=False)
        )
        account = document.request.account
        if (
            document.digest() != row.digest
            or account.workspace_id != row.workspace_id
            or account.account.account_id != row.account_id
            or account.account.connection_id != row.integration_id
            or document.request.draft_id != row.draft_id
            or document.request.draft_revision != row.source_revision
        ):
            raise ValueError("owned commitment")
        revision = db.get(CampaignRevision, (row.draft_id, row.source_revision))
        if revision is None or revision.workspace_id != row.workspace_id:
            raise ValueError("source unavailable")
        artifact = ReviewArtifact.model_validate(revision.artifact)
        if artifact.fingerprint() != document.request.source_digest:
            raise ValueError("source changed")
    except ValueError:
        raise HTTPException(409, "linked_configuration_record_unavailable") from None
    approval = db.get(SocialConfigurationApproval, row.id, populate_existing=True)
    if approval and (
        approval.workspace_id != row.workspace_id
        or approval.review_digest != row.digest
        or approval.digest != approval_digest(approval)
    ):
        raise HTTPException(409, "linked_configuration_confirmation_changed")
    return dict(
        id=row.id,
        digest=row.digest,
        environment=document.environment,
        confirmed=approval is not None,
        option_id=document.option_id,
        campaign=dict(
            name=artifact.definition.content.name,
            starts_at=artifact.definition.starts_at.isoformat(),
            ends_at=artifact.definition.ends_at.isoformat(),
            currency=artifact.definition.currency,
            budget_micros=artifact.definition.budget_micros,
        ),
        media={
            "video": document.configuration.video.model_dump(mode="json"),
            "cover": document.configuration.cover.model_dump(mode="json"),
        },
        creative=artifact.definition.content.model_dump(mode="json"),
        configuration={
            key: value
            for key, value in document.configuration.model_dump(mode="json").items()
            if key
            not in {
                "identity",
                "pixel_id",
                "tracking_pixel_id",
                "location_ids_by_country",
                "rights_review_digest",
                "identity_observation_digest",
                "advertiser_observation_digest",
                "video",
                "cover",
            }
        },
        identity_label=document.identity_label,
        requirements_text=document.requirements.wording,
        identity_type="TT_USER",
        visibility="Ads Only",
        creation="Creates A New Linked Post",
        financial_qualification="not_assessed",
        spending_authority="none",
    )


@router.post("/options")
def options(
    workspace_id: int,
    body: CatalogIntent,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    runtime: Runtime,
    media: Store,
    response: Response,
) -> dict[str, Any]:
    server = bound(runtime, principal, provider)
    linked = required(server.linked_review)
    artifact, catalog = discover(
        db, workspace_id, principal.user.id, body, media, linked, server.creation.authorize
    )
    response.headers["Cache-Control"] = "no-store"
    return dict(
        name=artifact.definition.content.name,
        environment=linked.environment,
        options=[
            dict(
                id=option.identifier(catalog.request),
                name=option.label,
                requirements_text=linked.requirements[option.profile_digest].wording,
                review_available=True,
            )
            for option in catalog.options
            if option.profile_digest in linked.requirements
        ],
        blockers=list(catalog.qualification_blockers),
    )


@router.post("/reviews", status_code=201)
def prepare(
    workspace_id: int,
    body: LinkedPushReviewIntent,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    runtime: Runtime,
    media: Store,
    response: Response,
) -> dict[str, Any]:
    server = bound(runtime, principal, provider)
    document, _, _ = resolve(
        db,
        workspace_id,
        principal.user.id,
        body,
        media,
        required(server.linked_review),
        server.creation.authorize,
    )
    row = reviews.prepare(
        db, workspace_id, principal.user.id, document, server.clock, server.creation.authorize
    )
    result = view(db, row)
    server.creation.authorize(db, workspace_id, principal.user.id)
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get("/reviews/{review_id}")
def read(
    workspace_id: int, review_id: str, principal: Principal, db: Database, response: Response
) -> dict[str, Any]:
    result = view(db, owned(db, workspace_id, principal.user.id, review_id))
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("/reviews/{review_id}/confirmation")
def confirm(
    workspace_id: int,
    review_id: str,
    body: ConfirmationIntent,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    runtime: Runtime,
    media: Store,
    response: Response,
) -> dict[str, Any]:
    server = bound(runtime, principal, provider)
    if not body.acknowledged:
        raise HTTPException(409, "explicit_configuration_acknowledgement_required")
    saved, _, _ = tiktok_linked_intents.refresh_configuration(
        db, workspace_id, review_id, body.expected_digest, principal.user.id, media, server
    )
    reviews.confirm(
        db,
        workspace_id,
        review_id,
        body.expected_digest,
        principal.user.id,
        saved,
        server.clock,
        server.creation.authorize,
    )
    result = view(db, owned(db, workspace_id, principal.user.id, review_id))
    server.creation.authorize(db, workspace_id, principal.user.id)
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("/creation-reviews", status_code=201)
def creation_review(
    workspace_id: int,
    body: SocialCreationIntent,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    runtime: Runtime,
    media: Store,
    response: Response,
) -> dict[str, Any]:
    server = bound(runtime, principal, provider)
    row = tiktok_linked_intents.prepare_creation(
        db, workspace_id, body, principal.user.id, media, server
    )
    response.headers["Cache-Control"] = "no-store"
    return customer_intents.review_view(row)
