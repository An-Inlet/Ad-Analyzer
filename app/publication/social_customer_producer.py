"""Canonical social plans from opaque server catalog choices; no execution authority."""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy.orm import Session

from app.campaign_review.contracts import MediaStore, MetaImage, ReviewArtifact, TikTokVideo
from app.publication import coordinator
from app.publication.contracts import PublicationScope
from app.publication.execution_contracts import ExecutionAccount
from app.publication.scoped_media import ScopedProviderMediaReader
from app.publication.social_catalog import (
    MetaCatalogOption,
    MetaConfigurationProfile,
    MetaDeclarationReader,
    SocialCatalog,
    SocialCatalogRequest,
    TikTokCatalogOption,
    TikTokConfigurationProfile,
)
from app.publication.social_compiler import compile_social
from app.publication.social_contracts import (
    MetaImagePublicationFields,
    SocialConfigurationApprovalRef,
    SocialPublicationReview,
    SocialPublishPlan,
    TikTokVideoPublicationFields,
)


def catalog_request(artifact: ReviewArtifact, account: ExecutionAccount) -> SocialCatalogRequest:
    if (
        account.workspace_id != artifact.workspace_id
        or account.account != artifact.definition.account
        or account.connection_version != artifact.connection_version
    ):
        raise ValueError("current owned source required")
    return SocialCatalogRequest.model_validate(
        dict(
            account=account,
            draft_id=artifact.draft_id,
            draft_revision=artifact.revision,
            source_digest=artifact.fingerprint(),
            countries=artifact.definition.content.audience.countries,
            languages=artifact.definition.content.audience.languages,
            content_kind=artifact.definition.content.kind,
        )
    )


class SocialPlanProducer:
    def __init__(
        self,
        profiles: Sequence[MetaConfigurationProfile | TikTokConfigurationProfile],
        *,
        declarations: MetaDeclarationReader | None = None,
    ) -> None:
        self.profiles = {p.digest(): type(p).model_validate(p.model_dump()) for p in profiles}
        self.declarations = declarations

    def _configuration(
        self,
        db: Session,
        artifact: ReviewArtifact,
        account: ExecutionAccount,
        option_id: str,
        catalog: SocialCatalog,
        media_store: MediaStore,
        now: datetime,
        *,
        actor: str,
        cover_media_id: str | None = None,
        preview: bool = False,
    ) -> MetaImagePublicationFields | TikTokVideoPublicationFields:
        artifact = ReviewArtifact.model_validate(artifact.model_dump())
        catalog = SocialCatalog.model_validate(catalog.model_dump())
        request = catalog_request(artifact, account)
        if (
            catalog.request != request
            or not catalog.observed_at <= now < catalog.expires_at
            or catalog.currency != artifact.definition.currency
        ):
            raise ValueError("fresh exact social catalog required")
        option = next((o for o in catalog.options if o.identifier(request) == option_id), None)
        if option is None:
            raise ValueError("current opaque option required")
        profile = self.profiles.get(option.profile_digest)
        if profile is None or profile.currency != catalog.currency:
            raise ValueError("current server configuration profile required")
        source = artifact.definition
        content = source.content
        if not isinstance(content, (MetaImage, TikTokVideo)):
            raise ValueError("social source required")
        media = ScopedProviderMediaReader(db, media_store)
        primary = media.binding(artifact.workspace_id, content.media.media_id)
        common = dict(
            account_timezone=catalog.account_timezone,
            currency=catalog.currency,
            reservation_micros=source.budget_micros,
            budget_semantics="lifetime_budget_not_independent_hard_cap",
            activation_policy="separate_exact_approval",
            automation_omission_policy="no_optional_assets_or_automation_requested",
        )
        fields: MetaImagePublicationFields | TikTokVideoPublicationFields
        if isinstance(option, MetaCatalogOption) and isinstance(profile, MetaConfigurationProfile):
            declaration = None
            if preview:
                if profile.dsa_required:
                    raise ValueError("personal_declaration_capture_unavailable")
            else:
                if self.declarations is None:
                    raise ValueError("audited customer declaration required")
                declaration = self.declarations(request, now)
                if (
                    declaration.request_digest != request.digest()
                    or declaration.confirmed_at > now
                    or (
                        profile.dsa_required
                        and (
                            not declaration.dsa_beneficiary
                            or not declaration.dsa_beneficiary.strip()
                            or not declaration.dsa_payor
                            or not declaration.dsa_payor.strip()
                        )
                    )
                ):
                    raise ValueError("current audited customer declaration required")
            fields = MetaImagePublicationFields.model_validate(
                dict(
                    **common,
                    currency_minor_unit_exponent=profile.currency_exponent,
                    adset_lifetime_budget_micros=source.budget_micros,
                    page_id=option.page_id,
                    pixel_id=option.pixel_id,
                    conversion_event="PURCHASE",
                    objective="OUTCOME_SALES",
                    buying_type="AUCTION",
                    bid_strategy="LOWEST_COST_WITHOUT_CAP",
                    optimization_goal="OFFSITE_CONVERSIONS",
                    billing_event="IMPRESSIONS",
                    destination_type="WEBSITE",
                    attribution=profile.attribution,
                    attribution_count_type="ALL_CONVERSIONS",
                    countries=request.countries,
                    language_locale_ids=profile.language_locale_ids,
                    age_min=profile.age_min,
                    age_max=profile.age_max,
                    publisher_platforms=["facebook"],
                    facebook_positions=["feed"],
                    advantage_audience=0,
                    dynamic_creative=False,
                    is_adset_budget_sharing_enabled=False,
                    special_ad_categories=[],
                    special_ad_category_declaration=(
                        declaration.special_ad_category_declaration
                        if declaration is not None
                        else "none_applicable"
                    ),
                    dsa_beneficiary=declaration.dsa_beneficiary
                    if declaration is not None
                    else None,
                    dsa_payor=declaration.dsa_payor if declaration is not None else None,
                    url_tags=profile.url_tags,
                    image=primary,
                )
            )
        elif isinstance(option, TikTokCatalogOption) and isinstance(
            profile, TikTokConfigurationProfile
        ):
            if cover_media_id is None:
                raise ValueError("reviewed_cover_required")
            cover = media.binding(artifact.workspace_id, cover_media_id)
            fields = TikTokVideoPublicationFields.model_validate(
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
                    identity_type=option.identity_type,
                    identity_id=option.identity_id,
                    creative_material_mode="CUSTOM",
                    ad_format="SINGLE_VIDEO",
                    video=primary,
                    cover=cover,
                    tracking_pixel_id=option.pixel_id,
                    click_tracking_url=None,
                    impression_tracking_url=None,
                )
            )
        else:
            raise ValueError("configuration provider mismatch")
        return fields

    def configuration_for_review(
        self,
        db: Session,
        artifact: ReviewArtifact,
        account: ExecutionAccount,
        option_id: str,
        catalog: SocialCatalog,
        media_store: MediaStore,
        now: datetime,
        *,
        actor: str,
        cover_media_id: str | None = None,
    ) -> MetaImagePublicationFields | TikTokVideoPublicationFields:
        """Non-authorizing preview; never invent an audit ID or personal declaration.

        The customer service separately records an explicit answer and blocks
        applicable/unsure. This method returns fields, never an executable plan.
        """
        return self._configuration(
            db,
            artifact,
            account,
            option_id,
            catalog,
            media_store,
            now,
            actor=actor,
            cover_media_id=cover_media_id,
            preview=True,
        )

    def produce(
        self,
        db: Session,
        artifact: ReviewArtifact,
        account: ExecutionAccount,
        option_id: str,
        catalog: SocialCatalog,
        media_store: MediaStore,
        now: datetime,
        *,
        actor: str,
        cover_media_id: str | None = None,
        configuration_review: SocialConfigurationApprovalRef | None = None,
    ) -> SocialPublishPlan:
        fields = self._configuration(
            db,
            artifact,
            account,
            option_id,
            catalog,
            media_store,
            now,
            actor=actor,
            cover_media_id=cover_media_id,
        )
        source = artifact.definition
        scope = PublicationScope(
            **account.model_dump(),
            mandate_id=source.mandate_id,
            mandate_revision=source.mandate_revision,
        )
        plan = compile_social(
            SocialPublicationReview(
                source=artifact,
                source_digest=artifact.fingerprint(),
                scope=scope,
                configuration=fields,
                configuration_review=configuration_review,
                qualification_blockers=catalog.qualification_blockers,
            )
        )
        # The facade reauthorizes its original session after HTTP; this also enforces
        # actual current DB source approval, owner membership and native generation.
        coordinator.source_current(db, account.workspace_id, plan, actor, media_store, lambda: now)
        return plan
