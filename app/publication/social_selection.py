"""Server-owned social selection; catalog IO precedes fresh customer authorization."""

from fastapi import HTTPException
from pydantic import Field
from sqlalchemy.orm import Session

from app.campaign_review import service as sources
from app.campaign_review.contracts import MediaStore, ReviewArtifact
from app.goals.schemas import StrictModel
from app.publication import customer_intents
from app.publication import social_review_service as reviews
from app.publication.execution_authorization import ExecutionAuthorizer
from app.publication.execution_contracts import ExecutionAccount
from app.publication.provider_contracts import Digest, Id
from app.publication.service import owner
from app.publication.social_catalog import SocialCatalog
from app.publication.social_customer_producer import catalog_request
from app.publication.social_review_contracts import SocialAnswer, SocialConfigurationDocument
from app.publication.social_review_runtime import SocialReviewRuntime


class CatalogIntent(StrictModel):
    draft_id: Id
    draft_revision: int = Field(strict=True, ge=1)


class ReviewIntent(CatalogIntent):
    option_id: Digest
    answer: SocialAnswer
    cover_media_id: Id | None = None


def runtime_required(runtime: SocialReviewRuntime | None) -> SocialReviewRuntime:
    if runtime is None:
        raise HTTPException(503, "social_configuration_discovery_unavailable")
    return runtime


def discover(
    db: Session,
    wid: int,
    actor: str,
    body: CatalogIntent,
    store: MediaStore,
    runtime: SocialReviewRuntime,
    authorize: ExecutionAuthorizer,
) -> tuple[ReviewArtifact, ExecutionAccount, SocialCatalog]:
    authorize(db, wid, actor)
    row, artifact = sources.preview(db, wid, body.draft_id, store, runtime.clock())
    if row.approved_by is None or artifact.revision != body.draft_revision:
        raise HTTPException(409, "current_approved_source_required")
    owner(db, wid, row.approved_by)
    scope = customer_intents.account(db, wid, artifact.definition.account.account_id)
    request = catalog_request(artifact, scope)
    db.commit()
    try:
        result = runtime.catalog(request, runtime.clock())
        catalog = SocialCatalog.model_validate(result.model_dump())
    except Exception:
        raise HTTPException(503, "social_configuration_discovery_unavailable") from None
    authorize(db, wid, actor)
    row, current = sources.preview(db, wid, body.draft_id, store, runtime.clock())
    current_scope = customer_intents.account(db, wid, current.definition.account.account_id)
    if (
        row.approved_by is None
        or catalog_request(current, current_scope) != request
        or catalog.request != request
        or not catalog.observed_at <= runtime.clock() < catalog.expires_at
    ):
        raise HTTPException(409, "social_configuration_changed")
    owner(db, wid, row.approved_by)
    return current, current_scope, catalog


def resolve_selection(
    db: Session,
    wid: int,
    actor: str,
    body: ReviewIntent,
    store: MediaStore,
    runtime: SocialReviewRuntime,
    authorize: ExecutionAuthorizer,
) -> tuple[SocialConfigurationDocument, ReviewArtifact, SocialCatalog]:
    artifact, scope, catalog = discover(db, wid, actor, body, store, runtime, authorize)
    option = next(
        (o for o in catalog.options if o.identifier(catalog.request) == body.option_id), None
    )
    profile = next(
        (p for p in runtime.profiles if option and p.digest() == option.profile_digest), None
    )
    requirements = runtime.requirements.get(profile.digest()) if profile else None
    if profile is None or requirements is None:
        raise HTTPException(409, "verified_configuration_requirements_unavailable")
    try:
        document = reviews.selection(
            db,
            wid,
            actor,
            scope,
            catalog,
            body.option_id,
            profile,
            requirements,
            body.answer,
            body.cover_media_id,
            runtime.environment,
            store,
            runtime.clock,
            authorize,
        )
    except (ValueError, OSError):
        # Missing/unreadable exact private media is unavailable, never a new binding.
        raise HTTPException(409, "supported_exact_configuration_required") from None

    return document, artifact, catalog


def resolve(
    db: Session,
    wid: int,
    actor: str,
    body: ReviewIntent,
    store: MediaStore,
    runtime: SocialReviewRuntime,
    authorize: ExecutionAuthorizer,
) -> SocialConfigurationDocument:
    return resolve_selection(db, wid, actor, body, store, runtime, authorize)[0]
