from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from app.campaign_review.models import CampaignRevision, MediaObject
from app.publication.coordinator_contracts import CreationExecutionReview
from app.publication.execution_contracts import ExecutionAccount
from app.publication.execution_models import ProviderExecutionReview, ProviderExecutionRun
from app.publication.social_catalog import (
    MetaCatalogOption,
    MetaConfigurationProfile,
    MetaDeclaration,
    SocialCatalog,
    TikTokCatalogOption,
    TikTokConfigurationProfile,
)
from app.publication.social_compiler import compile_social
from app.publication.social_contracts import MetaImagePublicationFields, SocialPublishPlan
from app.publication.social_customer_producer import SocialPlanProducer, catalog_request
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.test_campaign_video import encoded as encoded
from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_shopify_sales import configuration as configuration
from tests.test_social_coordinator_journeys import SocialServer, ready


def fixture(
    db: Session, configuration: Settings, path: Path, provider: str, video: bytes | None
) -> tuple[Any, ...]:
    wid, runid, actor, store, _, native = ready(
        db, configuration, path, provider, video, SocialServer(provider)
    )
    run = db.get(ProviderExecutionRun, runid)
    assert run is not None
    row = db.get(ProviderExecutionReview, run.review_id)
    assert row is not None
    document = CreationExecutionReview.model_validate(row.document)
    assert isinstance(document.plan, SocialPublishPlan)
    original = document.plan
    fields = original.review.configuration
    account = ExecutionAccount.from_publication(original.review.scope)
    req = catalog_request(original.review.source, account)
    profile: MetaConfigurationProfile | TikTokConfigurationProfile
    option: MetaCatalogOption | TikTokCatalogOption
    cover = None
    if isinstance(fields, MetaImagePublicationFields):
        profile = MetaConfigurationProfile(
            profile_id="explicit_contract_case",
            label="Website purchases",
            currency=fields.currency,
            currency_exponent=fields.currency_minor_unit_exponent,
            language_locale_ids=fields.language_locale_ids,
            attribution=fields.attribution,
            age_min=fields.age_min,
            age_max=fields.age_max,
            dsa_required=True,
            url_tags=fields.url_tags,
        )
        option = MetaCatalogOption(
            label="Page / Pixel",
            profile_digest=profile.digest(),
            page_id=fields.page_id,
            pixel_id=fields.pixel_id,
        )
    else:
        profile = TikTokConfigurationProfile(
            profile_id="explicit_decoded_contract_case",
            label="Website purchases",
            currency=fields.currency,
            currency_exponent=fields.currency_decimal_places,
            location_ids_by_country=fields.location_ids_by_country,
            language_codes=fields.language_codes,
            age_groups=fields.age_groups,
            click_attribution_window=fields.click_attribution_window,
            view_attribution_window=fields.view_attribution_window,
            engaged_view_attribution_window=fields.engaged_view_attribution_window,
            comment_disabled=fields.comment_disabled,
            share_disabled=fields.share_disabled,
            video_download_disabled=fields.video_download_disabled,
        )
        option = TikTokCatalogOption(
            label="Identity / Pixel",
            profile_digest=profile.digest(),
            identity_id=fields.identity_id,
            pixel_id=fields.pixel_id,
        )
        cover = fields.cover.media_id
    catalog = SocialCatalog(
        request=req,
        observed_at=NOW,
        expires_at=NOW + timedelta(seconds=60),
        currency="USD",
        account_timezone=fields.account_timezone,
        options=[option],
        unavailable_reasons=[],
        qualification_blockers=[
            "tiktok_native_catalog_parser_unverified"
            if provider == "tiktok_ads"
            else "native_configuration_unqualified"
        ],
        discovery_evidence="tiktok_decoded_contract_only"
        if provider == "tiktok_ads"
        else "meta_account_edges",
    )

    def declaration(request: Any, now: Any) -> MetaDeclaration:
        # Explicit server-reader fixture. No claim of a production audit repository.
        assert request == req
        return MetaDeclaration(
            request_digest=req.digest(),
            audit_record_id="d" * 32,
            confirmed_by=actor,
            confirmed_at=NOW,
            special_ad_category_declaration="none_applicable",
            dsa_beneficiary="Confirmed store",
            dsa_payor="Confirmed store",
        )

    return (
        original,
        account,
        catalog,
        SocialPlanProducer([profile], declarations=declaration),
        actor,
        store,
        cover,
        native,
    )


@pytest.mark.parametrize("provider", ["meta_ads", "tiktok_ads"])
def test_produce_canonical_owned_plan_with_exact_cover_review(
    customer_engine: Engine, configuration: Settings, tmp_path: Path, encoded: Any, provider: str
) -> None:
    with Session(customer_engine) as db:
        original, account, catalog, producer, actor, store, cover, _ = fixture(
            db, configuration, tmp_path, provider, encoded() if provider == "tiktok_ads" else None
        )
        plan = producer.produce(
            db,
            original.review.source,
            account,
            catalog.options[0].identifier(catalog.request),
            catalog,
            store,
            NOW,
            actor=actor,
            cover_media_id=cover,
        )
        assert compile_social(plan.review) == plan
        assert len(plan.steps) == 5
        assert (
            plan.review.configuration.reservation_micros
            == original.review.source.definition.budget_micros
        )
        if provider == "tiktok_ads":
            assert plan.review.configuration.cover.media_id == cover
            assert "tiktok_native_catalog_parser_unverified" in plan.review.qualification_blockers
        else:
            assert plan.review.configuration.special_ad_category_declaration == "none_applicable"


@pytest.mark.parametrize(
    "change", ["generation", "unapproved", "foreign_media", "expired", "option", "declaration"]
)
def test_producer_rejects_stale_or_unowned_inputs(
    customer_engine: Engine, configuration: Settings, tmp_path: Path, change: str
) -> None:
    with Session(customer_engine) as db:
        original, account, catalog, producer, actor, store, cover, native = fixture(
            db, configuration, tmp_path, "meta_ads", None
        )
        option = catalog.options[0].identifier(catalog.request)
        now = NOW
        if change == "generation":
            native.generation += 1
            db.commit()
        elif change == "unapproved":
            row = db.get(
                CampaignRevision, (original.review.source.draft_id, original.review.source.revision)
            )
            assert row is not None
            row.approved_by = None
            db.commit()
        elif change == "foreign_media":
            media_row = db.scalar(
                select(MediaObject).where(
                    MediaObject.id == original.review.configuration.image.media_id
                )
            )
            assert media_row is not None
            db.delete(media_row)
            db.commit()
        elif change == "expired":
            now += timedelta(seconds=61)
        elif change == "option":
            option = "f" * 64
        else:
            producer.declarations = None
        with pytest.raises((ValueError, HTTPException)):
            producer.produce(
                db,
                original.review.source,
                account,
                option,
                catalog,
                store,
                now,
                actor=actor,
                cover_media_id=cover,
            )


def test_tiktok_missing_or_foreign_cover_never_auto_selected(
    customer_engine: Engine, configuration: Settings, tmp_path: Path, encoded: Any
) -> None:
    with Session(customer_engine) as db:
        original, account, catalog, producer, actor, store, _, _ = fixture(
            db, configuration, tmp_path, "tiktok_ads", encoded()
        )
        for cover in (None, "f" * 32):
            with pytest.raises(ValueError):
                producer.produce(
                    db,
                    original.review.source,
                    account,
                    catalog.options[0].identifier(catalog.request),
                    catalog,
                    store,
                    NOW,
                    actor=actor,
                    cover_media_id=cover,
                )
