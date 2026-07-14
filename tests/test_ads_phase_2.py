from collections.abc import Generator
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from app.ads.enums import AdvertisingPlatform
from app.ads.models import AdvertisingAccount, Campaign
from app.ads.schemas import AdCreate, DailyMetricCreate, NormalizedMetricsBatch
from app.ads.services import NormalizedMetricsService
from app.database.session import Base
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture()
def session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    local_session = sessionmaker(bind=engine)
    db = local_session()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)


def test_account_campaign_relationship_and_unique_account_constraint(session: Session) -> None:
    account = AdvertisingAccount(
        platform=AdvertisingPlatform.GOOGLE_ADS,
        external_account_id="acct-1",
        name="Denticode Search",
        currency_code="USD",
    )
    account.campaigns.append(
        Campaign(
            platform=AdvertisingPlatform.GOOGLE_ADS,
            external_campaign_id="camp-1",
            name="Implants",
        )
    )
    session.add(account)
    session.commit()

    assert account.id is not None
    assert account.campaigns[0].account_id == account.id

    session.add(
        AdvertisingAccount(
            platform=AdvertisingPlatform.GOOGLE_ADS,
            external_account_id="acct-1",
            name="Duplicate",
            currency_code="USD",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()


def test_pydantic_validates_read_only_normalized_metrics() -> None:
    metric = DailyMetricCreate(
        platform="meta_ads",
        metric_date=date(2026, 7, 14),
        entity_type="campaign",
        entity_id=123,
        impressions=10,
        clicks=2,
        cost_micros=1500000,
        conversions=Decimal("1.5"),
    )

    assert metric.platform is AdvertisingPlatform.META_ADS

    with pytest.raises(ValidationError):
        DailyMetricCreate(
            platform="google_ads",
            metric_date=date(2026, 7, 14),
            entity_type="campaign",
            entity_id=123,
            cost_micros=-1,
        )


def test_ad_schema_requires_exactly_one_parent() -> None:
    with pytest.raises(ValidationError):
        AdCreate(platform="google_ads", external_ad_id="ad-1", name="No parent")

    with pytest.raises(ValidationError):
        AdCreate(
            platform="google_ads",
            external_ad_id="ad-1",
            name="Two parents",
            ad_group_id=1,
            ad_set_id=1,
        )

    ad = AdCreate(platform="meta_ads", external_ad_id="ad-1", name="Creative", ad_set_id=1)
    assert ad.ad_set_id == 1


def test_normalized_metrics_service_stores_metrics_and_enforces_uniqueness(
    session: Session,
) -> None:
    account = AdvertisingAccount(
        platform=AdvertisingPlatform.META_ADS,
        external_account_id="meta-acct-1",
        name="Denticode Social",
        currency_code="USD",
    )
    campaign = Campaign(
        account=account,
        platform=AdvertisingPlatform.META_ADS,
        external_campaign_id="meta-camp-1",
        name="Clear Aligners",
    )
    session.add(campaign)
    session.commit()

    batch = NormalizedMetricsBatch(
        metrics=[
            DailyMetricCreate(
                platform=AdvertisingPlatform.META_ADS,
                metric_date=date(2026, 7, 14),
                entity_type="campaign",
                entity_id=campaign.id,
                campaign_id=campaign.id,
                impressions=100,
                clicks=12,
                cost_micros=2500000,
                conversions=Decimal("2"),
                conversion_value_micros=10000000,
            )
        ]
    )

    stored = NormalizedMetricsService(session).store_batch(batch)
    session.commit()

    assert stored[0].id is not None
    assert stored[0].created_at <= datetime.now(UTC).replace(tzinfo=None)

    NormalizedMetricsService(session).store_batch(batch)
    with pytest.raises(IntegrityError):
        session.commit()
