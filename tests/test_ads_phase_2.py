from collections.abc import Generator
from datetime import UTC, date, datetime
from decimal import Decimal
from sqlite3 import Connection as SQLiteConnection

import pytest
from app.ads.enums import AdvertisingPlatform
from app.ads.models import (
    Ad,
    AdGroup,
    AdSet,
    AdvertisingAccount,
    Campaign,
    DailyMetric,
    Keyword,
    SearchTerm,
)
from app.ads.schemas import AdCreate, DailyMetricCreate, NormalizedMetricsBatch
from app.ads.services import NormalizedMetricsService
from app.database.session import Base
from app.workspaces.models import Workspace
from pydantic import ValidationError
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import ConnectionPoolEntry


def enable_sqlite_foreign_keys(
    dbapi_connection: SQLiteConnection, _connection_record: ConnectionPoolEntry
) -> None:
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


def assert_integrity_error(session: Session) -> None:
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


@pytest.fixture()
def session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite:///:memory:")
    event.listen(engine, "connect", enable_sqlite_foreign_keys)
    Base.metadata.create_all(engine)
    local_session = sessionmaker(bind=engine)
    db = local_session()
    db.add(
        Workspace(
            id=1,
            slug="denticode",
            name="Denticode Ad Analyzer",
            client_name="Denticode",
            status="active",
            is_default=True,
        )
    )
    db.commit()
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


def test_database_requires_ads_to_have_exactly_one_parent(session: Session) -> None:
    google_account = AdvertisingAccount(
        platform=AdvertisingPlatform.GOOGLE_ADS,
        external_account_id="google-acct-ads-xor",
        name="Denticode Search",
        currency_code="USD",
    )
    google_campaign = Campaign(
        account=google_account,
        platform=AdvertisingPlatform.GOOGLE_ADS,
        external_campaign_id="google-camp-ads-xor",
        name="Implants",
    )
    google_ad_group = AdGroup(
        campaign=google_campaign,
        platform=AdvertisingPlatform.GOOGLE_ADS,
        external_ad_group_id="google-ad-group-ads-xor",
        name="Implants Exact",
    )
    meta_account = AdvertisingAccount(
        platform=AdvertisingPlatform.META_ADS,
        external_account_id="meta-acct-ads-xor",
        name="Denticode Social",
        currency_code="USD",
    )
    meta_campaign = Campaign(
        account=meta_account,
        platform=AdvertisingPlatform.META_ADS,
        external_campaign_id="meta-camp-ads-xor",
        name="Aligners",
    )
    meta_ad_set = AdSet(
        campaign=meta_campaign,
        platform=AdvertisingPlatform.META_ADS,
        external_ad_set_id="meta-ad-set-ads-xor",
        name="Retargeting",
    )
    session.add_all([google_ad_group, meta_ad_set])
    session.commit()

    session.add(
        Ad(
            platform=AdvertisingPlatform.GOOGLE_ADS,
            external_ad_id="ad-without-parent",
            name="No parent",
        )
    )
    assert_integrity_error(session)

    session.add(
        Ad(
            platform=AdvertisingPlatform.GOOGLE_ADS,
            external_ad_id="ad-with-two-parents",
            name="Two parents",
            ad_group_id=google_ad_group.id,
            ad_set_id=meta_ad_set.id,
        )
    )
    assert_integrity_error(session)

    session.add_all(
        [
            Ad(
                platform=AdvertisingPlatform.GOOGLE_ADS,
                external_ad_id="google-ad-with-parent",
                name="Search creative",
                ad_group_id=google_ad_group.id,
            ),
            Ad(
                platform=AdvertisingPlatform.META_ADS,
                external_ad_id="meta-ad-with-parent",
                name="Social creative",
                ad_set_id=meta_ad_set.id,
            ),
        ]
    )
    session.commit()


def test_database_enforces_platform_aware_parent_child_constraints(
    session: Session,
) -> None:
    google_account = AdvertisingAccount(
        platform=AdvertisingPlatform.GOOGLE_ADS,
        external_account_id="google-acct-platform",
        name="Denticode Search",
        currency_code="USD",
    )
    meta_account = AdvertisingAccount(
        platform=AdvertisingPlatform.META_ADS,
        external_account_id="meta-acct-platform",
        name="Denticode Social",
        currency_code="USD",
    )
    session.add_all([google_account, meta_account])
    session.commit()

    session.add(
        Campaign(
            account_id=google_account.id,
            platform=AdvertisingPlatform.META_ADS,
            external_campaign_id="bad-account-platform",
            name="Wrong account platform",
        )
    )
    assert_integrity_error(session)

    google_campaign = Campaign(
        account_id=google_account.id,
        platform=AdvertisingPlatform.GOOGLE_ADS,
        external_campaign_id="google-camp-platform",
        name="Implants",
    )
    meta_campaign = Campaign(
        account_id=meta_account.id,
        platform=AdvertisingPlatform.META_ADS,
        external_campaign_id="meta-camp-platform",
        name="Aligners",
    )
    session.add_all([google_campaign, meta_campaign])
    session.commit()

    session.add(
        AdGroup(
            campaign_id=google_campaign.id,
            platform=AdvertisingPlatform.META_ADS,
            external_ad_group_id="bad-ad-group-platform",
            name="Wrong campaign platform",
        )
    )
    assert_integrity_error(session)

    session.add(
        AdSet(
            campaign_id=meta_campaign.id,
            platform=AdvertisingPlatform.GOOGLE_ADS,
            external_ad_set_id="bad-ad-set-platform",
            name="Wrong campaign platform",
        )
    )
    assert_integrity_error(session)

    google_ad_group = AdGroup(
        campaign_id=google_campaign.id,
        platform=AdvertisingPlatform.GOOGLE_ADS,
        external_ad_group_id="google-ad-group-platform",
        name="Implants Exact",
    )
    meta_ad_set = AdSet(
        campaign_id=meta_campaign.id,
        platform=AdvertisingPlatform.META_ADS,
        external_ad_set_id="meta-ad-set-platform",
        name="Retargeting",
    )
    session.add_all([google_ad_group, meta_ad_set])
    session.commit()

    session.add(
        Ad(
            platform=AdvertisingPlatform.META_ADS,
            external_ad_id="bad-ad-ad-group-platform",
            name="Wrong ad group platform",
            ad_group_id=google_ad_group.id,
        )
    )
    assert_integrity_error(session)

    session.add(
        Ad(
            platform=AdvertisingPlatform.GOOGLE_ADS,
            external_ad_id="bad-ad-ad-set-platform",
            name="Wrong ad set platform",
            ad_set_id=meta_ad_set.id,
        )
    )
    assert_integrity_error(session)

    session.add(
        Keyword(
            ad_group_id=google_ad_group.id,
            platform=AdvertisingPlatform.META_ADS,
            external_keyword_id="bad-keyword-platform",
            text="dentist near me",
        )
    )
    assert_integrity_error(session)

    session.add(
        SearchTerm(
            ad_group_id=google_ad_group.id,
            platform=AdvertisingPlatform.META_ADS,
            term="implant dentist",
        )
    )
    assert_integrity_error(session)

    session.add(
        DailyMetric(
            platform=AdvertisingPlatform.META_ADS,
            metric_date=date(2026, 7, 14),
            entity_type="campaign",
            entity_id=google_campaign.id,
            campaign_id=google_campaign.id,
        )
    )
    assert_integrity_error(session)


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
