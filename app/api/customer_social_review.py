"""Intent-only social configuration review, separate from spending/execution consent."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import Field, TypeAdapter

from app.api.customer_execution import Runtime as ExecutionRuntime
from app.campaign_review.contracts import MediaStore, ReviewArtifact
from app.campaign_review.models import CampaignRevision
from app.campaign_review.storage import get_media_store
from app.customers.access import Database, MutationPrincipal, Principal, Provider
from app.goals.schemas import StrictModel
from app.publication import social_review_service as reviews
from app.publication.customer_authority import bind_authority
from app.publication.provider_contracts import Digest
from app.publication.service import owner
from app.publication.social_catalog import MetaConfigurationProfile
from app.publication.social_review_contracts import (
    LegacySocialConfigurationDocumentV1,
    SocialConfigurationDocument,
)
from app.publication.social_review_models import (
    SocialConfigurationApproval,
    SocialConfigurationReview,
)
from app.publication.social_review_runtime import SocialReviewRuntime, get_social_review_runtime
from app.publication.social_selection import (
    CatalogIntent,
    ReviewIntent,
    discover,
    resolve,
    runtime_required,
)

router = APIRouter(
    prefix="/api/customer/v1/workspaces/{workspace_id}/execution/social", tags=["customer"]
)
LegacyRuntime = Annotated[SocialReviewRuntime | None, Depends(get_social_review_runtime)]


def configured_social_review(
    legacy: LegacyRuntime, execution: ExecutionRuntime
) -> SocialReviewRuntime | None:
    return legacy if legacy is not None else execution.social_review if execution else None


Runtime = Annotated[SocialReviewRuntime | None, Depends(configured_social_review)]
Store = Annotated[MediaStore, Depends(get_media_store)]
History: TypeAdapter[SocialConfigurationDocument | LegacySocialConfigurationDocumentV1] = (
    TypeAdapter(
        Annotated[
            SocialConfigurationDocument | LegacySocialConfigurationDocumentV1,
            Field(discriminator="schema_version"),
        ]
    )
)


class ConfirmationIntent(StrictModel):
    expected_digest: Digest
    acknowledged: bool = Field(strict=True)


def owned(db: Database, wid: int, actor: str, identifier: str) -> SocialConfigurationReview:
    owner(db, wid, actor)
    row = db.get(SocialConfigurationReview, identifier, populate_existing=True)
    if row is None or row.workspace_id != wid:
        raise HTTPException(404, "owned_configuration_unavailable")
    return row


def view(db: Database, row: SocialConfigurationReview) -> dict[str, Any]:
    try:
        document = History.validate_python(row.document)
    except ValueError:
        raise HTTPException(409, "configuration_record_unavailable") from None
    # Strict history without upgrading or relabeling a version1 confirmation.
    if document.digest() != row.digest:
        raise HTTPException(409, "configuration_record_changed")
    approval = db.get(SocialConfigurationApproval, row.id)
    if approval is not None and (
        approval.workspace_id != row.workspace_id
        or approval.review_digest != row.digest
        or approval.digest != reviews.approval_digest(approval)
    ):
        raise HTTPException(409, "configuration_confirmation_changed")
    revision = db.get(CampaignRevision, (row.draft_id, row.source_revision))
    if revision is None or revision.workspace_id != row.workspace_id:
        raise HTTPException(409, "configuration_source_unavailable")
    try:
        artifact = ReviewArtifact.model_validate(revision.artifact)
    except ValueError:
        raise HTTPException(409, "configuration_source_unavailable") from None
    if artifact.fingerprint() != document.request.source_digest:
        raise HTTPException(409, "configuration_source_changed")
    return {
        "campaign": {
            "name": artifact.definition.content.name,
            "starts_at": artifact.definition.starts_at.isoformat(),
            "ends_at": artifact.definition.ends_at.isoformat(),
            "landing_page": artifact.definition.content.landing_page,
        },
        "id": row.id,
        "digest": row.digest,
        "draft_id": document.request.draft_id,
        "draft_revision": document.request.draft_revision,
        "platform": document.request.account.account.platform,
        "environment": document.environment,
        "answer": document.answer.model_dump(),
        "primary": document.primary.model_dump(),
        "cover": document.cover.model_dump() if document.cover else None,
        "requirements_text": document.requirements.wording,
        "countries": document.request.countries,
        "languages": document.request.languages,
        "blockers": document.blockers(),
        "status": "requires_new_review"
        if isinstance(document, LegacySocialConfigurationDocumentV1)
        else "confirmed_historical"
        if approval
        else "awaiting_confirmation",
        "currently_executable": False,
        "configuration": document.configuration.model_dump(mode="json")
        if isinstance(document, SocialConfigurationDocument)
        else None,
        "publication": (
            "Separate spending consent, exact execution review and "
            "current provider qualification remain required."
        ),
    }


@router.post("/options")
def options(
    workspace_id: int,
    body: CatalogIntent,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    runtime: Runtime,
    store: Store,
    response: Response,
) -> dict[str, Any]:
    server = runtime_required(runtime)
    artifact, _, catalog = discover(
        db,
        workspace_id,
        principal.user.id,
        body,
        store,
        server,
        bind_authority(principal, provider),
    )
    response.headers["Cache-Control"] = "no-store"
    eligible_profiles = {
        p.digest()
        for p in server.profiles
        if not isinstance(p, MetaConfigurationProfile) or not p.dsa_required
    }
    return {
        "name": artifact.definition.content.name,
        "platform": artifact.definition.account.platform,
        "environment": server.environment,
        "options": [
            {
                "id": o.identifier(catalog.request),
                "name": o.label,
                "requirements_text": server.requirements[o.profile_digest].wording
                if o.profile_digest in server.requirements
                else None,
                "review_available": bool(
                    o.profile_digest in eligible_profiles
                    and o.profile_digest in server.requirements
                    and server.requirements[o.profile_digest].wording
                    and server.requirements[o.profile_digest].profile_digest == o.profile_digest
                ),
            }
            for o in catalog.options
        ],
        "blockers": catalog.qualification_blockers,
    }


@router.post("/reviews", status_code=201)
def prepare(
    workspace_id: int,
    body: ReviewIntent,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    runtime: Runtime,
    store: Store,
    response: Response,
) -> dict[str, Any]:
    server = runtime_required(runtime)
    authorize = bind_authority(principal, provider)
    document = resolve(db, workspace_id, principal.user.id, body, store, server, authorize)
    row = reviews.prepare(db, workspace_id, principal.user.id, document, server.clock, authorize)
    result = view(db, row)
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
    store: Store,
    response: Response,
) -> dict[str, Any]:
    server = runtime_required(runtime)
    authorize = bind_authority(principal, provider)
    authorize(db, workspace_id, principal.user.id)
    row = owned(db, workspace_id, principal.user.id, review_id)
    try:
        saved = SocialConfigurationDocument.model_validate(row.document)
    except ValueError:
        raise HTTPException(409, "new_exact_configuration_review_required") from None
    if not body.acknowledged:
        raise HTTPException(409, "explicit_configuration_acknowledgement_required")
    current = resolve(
        db,
        workspace_id,
        principal.user.id,
        ReviewIntent(
            draft_id=saved.request.draft_id,
            draft_revision=saved.request.draft_revision,
            option_id=saved.option_id,
            answer=saved.answer,
            cover_media_id=saved.cover.media_id if saved.cover else None,
        ),
        store,
        server,
        authorize,
    )
    reviews.confirm(
        db,
        workspace_id,
        review_id,
        body.expected_digest,
        principal.user.id,
        current,
        server.clock,
        authorize,
    )
    result = view(db, row)
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return result
