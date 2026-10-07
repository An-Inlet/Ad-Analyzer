"""Owned linked selection with original authorization before and after discovery IO."""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.campaign_review import service as sources
from app.campaign_review.contracts import MediaStore, ReviewArtifact, TikTokVideo
from app.publication import customer_intents
from app.publication.contracts import fingerprint
from app.publication.execution_authorization import ExecutionAuthorizer
from app.publication.scoped_media import ScopedProviderMediaReader
from app.publication.service import owner
from app.publication.social_customer_producer import catalog_request
from app.publication.social_selection import CatalogIntent
from app.publication.tiktok_linked_catalog import LinkedPushCatalogV1
from app.publication.tiktok_linked_customer_contracts import LinkedPushReviewIntent
from app.publication.tiktok_linked_plan import LinkedPushConfigurationV1
from app.publication.tiktok_linked_review_contracts import (
    LinkedPushConfigurationDocumentV1,
    linked_rights_digest,
)
from app.publication.tiktok_linked_runtime import LinkedPushReviewRuntime


def required(runtime: LinkedPushReviewRuntime | None) -> LinkedPushReviewRuntime:
    if runtime is None:
        raise HTTPException(503, "linked_configuration_unavailable")
    return runtime


def discover(
    db: Session,
    wid: int,
    actor: str,
    body: CatalogIntent,
    store: MediaStore,
    runtime: LinkedPushReviewRuntime,
    authorize: ExecutionAuthorizer,
) -> tuple[ReviewArtifact, LinkedPushCatalogV1]:
    authorize(db, wid, actor)
    row, artifact = sources.preview(db, wid, body.draft_id, store, runtime.clock())
    if row.approved_by is None or artifact.revision != body.draft_revision:
        raise HTTPException(409, "current_approved_source_required")
    owner(db, wid, row.approved_by)
    scope = customer_intents.account(db, wid, artifact.definition.account.account_id)
    request = catalog_request(artifact, scope)
    db.commit()
    try:
        catalog = LinkedPushCatalogV1.model_validate_json(
            runtime.catalog(request, runtime.clock()).model_dump_json()
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, "linked_configuration_unavailable") from None
    authorize(db, wid, actor)
    row, current = sources.preview(db, wid, body.draft_id, store, runtime.clock())
    current_scope = customer_intents.account(db, wid, current.definition.account.account_id)
    if (
        row.approved_by is None
        or catalog_request(current, current_scope) != request
        or catalog.request != request
        or not catalog.observed_at <= runtime.clock() < catalog.expires_at
    ):
        raise HTTPException(409, "linked_configuration_changed")
    owner(db, wid, row.approved_by)
    return current, catalog


def resolve(
    db: Session,
    wid: int,
    actor: str,
    body: LinkedPushReviewIntent,
    store: MediaStore,
    runtime: LinkedPushReviewRuntime,
    authorize: ExecutionAuthorizer,
) -> tuple[LinkedPushConfigurationDocumentV1, ReviewArtifact, LinkedPushCatalogV1]:
    artifact, catalog = discover(db, wid, actor, body, store, runtime, authorize)
    option = next(
        (value for value in catalog.options if value.identifier(catalog.request) == body.option_id),
        None,
    )
    profile = next(
        (value for value in runtime.profiles if option and value.digest() == option.profile_digest),
        None,
    )
    requirements = runtime.requirements.get(profile.digest()) if profile else None
    if (
        option is None
        or profile is None
        or requirements is None
        or profile.currency != catalog.currency
        or artifact.definition.currency != catalog.currency
    ):
        raise HTTPException(409, "linked_configuration_changed")
    identity = next(
        (value for value in catalog.identities if value.request.identity == option.identity), None
    )
    if identity is None:
        raise HTTPException(409, "linked_configuration_changed")
    source = artifact.definition
    if not isinstance(source.content, TikTokVideo):
        raise HTTPException(409, "linked_video_source_required")
    db.commit()  # private storage validation also occurs without the workspace fence
    media = ScopedProviderMediaReader(db, store)
    try:
        primary = media.binding(wid, source.content.media.media_id)
        cover = media.binding(wid, body.cover_media_id)
    except (OSError, ValueError):
        raise HTTPException(409, "linked_reviewed_media_unavailable") from None
    common = dict(
        account_timezone=catalog.account_timezone,
        currency=catalog.currency,
        reservation_micros=source.budget_micros,
        budget_semantics="lifetime_budget_not_independent_hard_cap",
        activation_policy="separate_exact_approval",
        automation_omission_policy="no_optional_assets_or_automation_requested",
    )
    config = LinkedPushConfigurationV1.model_validate(
        dict(
            **common,
            currency_decimal_places=profile.currency_exponent,
            lifetime_budget_micros=source.budget_micros,
            objective_type="WEB_CONVERSIONS",
            promotion_type="WEBSITE",
            campaign_type="REGULAR_CAMPAIGN",
            budget_optimize_on=False,
            campaign_budget_mode="BUDGET_MODE_TOTAL",
            adgroup_budget_mode="BUDGET_MODE_TOTAL",
            placement_type="PLACEMENT_TYPE_NORMAL",
            placements=["PLACEMENT_TIKTOK"],
            pixel_id=option.pixel_id,
            optimization_event="SHOPPING",
            optimization_goal="CONVERT",
            billing_event="OCPM",
            bid_type="BID_TYPE_NO_BID",
            pacing="PACING_MODE_SMOOTH",
            schedule_type="SCHEDULE_START_END",
            schedule_wire_timezone="UTC",
            click_attribution_window=profile.click_attribution_window,
            view_attribution_window=profile.view_attribution_window,
            engaged_view_attribution_window=profile.engaged_view_attribution_window,
            attribution_event_count="EVERY",
            location_ids_by_country=profile.location_ids_by_country,
            language_codes=profile.language_codes,
            age_groups=profile.age_groups,
            gender="GENDER_UNLIMITED",
            smart_audience_enabled=False,
            smart_interest_behavior_enabled=False,
            search_result_enabled=False,
            comment_disabled=profile.comment_disabled,
            share_disabled=profile.share_disabled,
            video_download_disabled=profile.video_download_disabled,
            identity=option.identity,
            identity_observation_digest=identity.digest(),
            advertiser_observation_digest=catalog.advertiser.digest(),
            rights_review_digest="0" * 64,
            commercial_music_rights_reviewed=True,
            linked_post_creation_reviewed=True,
            dark_post_status="ON",
            creative_authorized=False,
            creative_material_mode="CUSTOM",
            ad_format="SINGLE_VIDEO",
            video=primary,
            cover=cover,
            tracking_pixel_id=option.pixel_id,
            click_tracking_url=None,
            impression_tracking_url=None,
        )
    )
    config = LinkedPushConfigurationV1.model_validate(
        {
            **config.model_dump(),
            "rights_review_digest": linked_rights_digest(
                catalog.request, requirements, body.answer, config
            ),
        }
    )
    document = LinkedPushConfigurationDocumentV1(
        request=catalog.request,
        environment=runtime.environment,
        option_id=body.option_id,
        identity_label=option.label,
        requirements=requirements,
        answer=body.answer,
        identity_observation=identity,
        advertiser_observation=catalog.advertiser,
        configuration=config,
        configuration_digest=fingerprint(
            "inlet.tiktok-linked-push-configuration-fields.v1", config.model_dump(mode="json")
        ),
    )
    authorize(db, wid, actor)
    row, current = sources.preview(db, wid, body.draft_id, store, runtime.clock())
    current_scope = customer_intents.account(db, wid, current.definition.account.account_id)
    if (
        row.approved_by is None
        or current != artifact
        or catalog_request(current, current_scope) != catalog.request
        or not catalog.observed_at <= runtime.clock() < catalog.expires_at
    ):
        raise HTTPException(409, "linked_configuration_changed")
    owner(db, wid, row.approved_by)
    authorize(db, wid, actor)
    return document, current, catalog
