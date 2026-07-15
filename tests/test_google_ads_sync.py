from collections.abc import Generator
from datetime import date
from decimal import Decimal
from sqlite3 import Connection as SQLiteConnection

import pytest
from app.ads.enums import AdvertisingPlatform, JobRunStatus
from app.ads.models import (
    Ad,
    AdGroup,
    AdvertisingAccount,
    Campaign,
    DailyMetric,
    JobRun,
    Keyword,
    SearchTerm,
)
from app.ads.schemas import (
    AdCreate,
    AdGroupCreate,
    AdvertisingAccountCreate,
    CampaignCreate,
    DailyMetricCreate,
    KeywordCreate,
    NormalizedMetricsBatch,
    SearchTermCreate,
)
from app.ads.services import GoogleAdsSyncService
from app.collectors import google_ads
from app.database.session import Base
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import ConnectionPoolEntry


def enable_sqlite_foreign_keys(
    dbapi_connection: SQLiteConnection, _connection_record: ConnectionPoolEntry
) -> None:
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


@pytest.fixture()
def session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite:///:memory:")
    event.listen(engine, "connect", enable_sqlite_foreign_keys)
    Base.metadata.create_all(engine)
    local_session = sessionmaker(bind=engine)
    db = local_session()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)


class GoogleAdsCollectorStub:
    def __init__(
        self,
        *,
        campaign_name: str = "Implants",
        fail_at: str | None = None,
        zero: bool = False,
    ) -> None:
        self.campaign_name = campaign_name
        self.fail_at = fail_at
        self.zero = zero

    def _fail_if_needed(self, name: str) -> None:
        if self.fail_at == name:
            raise RuntimeError("refresh token leaked-secret should be sanitized")

    def collect_account(self) -> AdvertisingAccountCreate:
        self._fail_if_needed("account")
        return AdvertisingAccountCreate(
            platform=AdvertisingPlatform.GOOGLE_ADS,
            external_account_id="acct-1",
            name="Denticode Search",
            currency_code="USD",
            time_zone="America/New_York",
        )

    def collect_campaigns(self, account_id: int) -> list[CampaignCreate]:
        self._fail_if_needed("campaigns")
        if self.zero:
            return []
        return [
            CampaignCreate(
                account_id=account_id,
                platform=AdvertisingPlatform.GOOGLE_ADS,
                external_campaign_id="camp-1",
                name=self.campaign_name,
                status="ENABLED",
                channel_type="SEARCH",
            )
        ]

    def collect_ad_groups(self, campaign_ids_by_external_id: dict[str, int]) -> list[AdGroupCreate]:
        self._fail_if_needed("ad_groups")
        return [
            AdGroupCreate(
                campaign_id=campaign_ids_by_external_id["camp-1"],
                platform=AdvertisingPlatform.GOOGLE_ADS,
                external_ad_group_id="ag-1",
                name="Implants Exact",
                status="ENABLED",
            )
        ] if campaign_ids_by_external_id else []

    def collect_ads(self, ad_group_ids_by_external_id: dict[str, int]) -> list[AdCreate]:
        self._fail_if_needed("ads")
        return [
            AdCreate(
                ad_group_id=ad_group_ids_by_external_id["ag-1"],
                platform=AdvertisingPlatform.GOOGLE_ADS,
                external_ad_id="ad-1",
                name="Implant Ad",
                status="ENABLED",
            )
        ] if ad_group_ids_by_external_id else []

    def collect_keywords(self, ad_group_ids_by_external_id: dict[str, int]) -> list[KeywordCreate]:
        self._fail_if_needed("keywords")
        return [
            KeywordCreate(
                ad_group_id=ad_group_ids_by_external_id["ag-1"],
                platform=AdvertisingPlatform.GOOGLE_ADS,
                external_keyword_id="kw-1",
                text="dental implants",
                match_type="EXACT",
                status="ENABLED",
            )
        ] if ad_group_ids_by_external_id else []

    def collect_search_terms(
        self,
        ad_group_ids_by_external_id: dict[str, int],
        date_range: google_ads.GoogleAdsDateRange,
    ) -> list[SearchTermCreate]:
        self._fail_if_needed("search_terms")
        return [
            SearchTermCreate(
                ad_group_id=ad_group_ids_by_external_id["ag-1"],
                platform=AdvertisingPlatform.GOOGLE_ADS,
                term="best dental implants",
                match_type="EXACT",
            )
        ] if ad_group_ids_by_external_id else []

    def collect_metrics(
        self,
        campaign_ids_by_external_id: dict[str, int],
        date_range: google_ads.GoogleAdsDateRange,
    ) -> NormalizedMetricsBatch:
        self._fail_if_needed("metrics")
        return NormalizedMetricsBatch(metrics=[
            DailyMetricCreate(
                platform=AdvertisingPlatform.GOOGLE_ADS,
                metric_date=date(2026, 7, 14),
                entity_type="campaign",
                entity_id=campaign_ids_by_external_id["camp-1"],
                campaign_id=campaign_ids_by_external_id["camp-1"],
                impressions=100,
                clicks=10,
                cost_micros=1230000,
                conversions=Decimal("2.5"),
                conversion_value_micros=2500000,
            )
        ])


@pytest.fixture()
def stub_collectors(monkeypatch: pytest.MonkeyPatch) -> GoogleAdsCollectorStub:
    stub = GoogleAdsCollectorStub()
    for name in (
        "collect_account", "collect_campaigns", "collect_ad_groups", "collect_ads",
        "collect_keywords", "collect_search_terms", "collect_metrics",
    ):
        monkeypatch.setattr(google_ads, name, getattr(stub, name))
    return stub


def test_first_sync_persists_google_ads_data(
    session: Session, stub_collectors: GoogleAdsCollectorStub
) -> None:
    result = GoogleAdsSyncService(session).sync()

    assert result.status is JobRunStatus.SUCCEEDED
    assert result.records_processed == 7
    account = session.scalar(
        select(AdvertisingAccount).where(AdvertisingAccount.external_account_id == "acct-1")
    )
    assert account is not None
    campaign = session.scalar(select(Campaign).where(Campaign.external_campaign_id == "camp-1"))
    assert campaign is not None
    assert session.scalar(select(AdGroup).where(AdGroup.external_ad_group_id == "ag-1")) is not None
    assert session.scalar(select(Ad).where(Ad.external_ad_id == "ad-1")) is not None
    assert session.scalar(select(Keyword).where(Keyword.external_keyword_id == "kw-1")) is not None
    search_term = session.scalar(
        select(SearchTerm).where(SearchTerm.term == "best dental implants")
    )
    assert search_term is not None
    assert session.scalar(select(DailyMetric).where(DailyMetric.impressions == 100)) is not None


def test_repeated_sync_is_idempotent(
    session: Session, stub_collectors: GoogleAdsCollectorStub
) -> None:
    GoogleAdsSyncService(session).sync()
    GoogleAdsSyncService(session).sync()

    assert len(session.scalars(select(Campaign)).all()) == 1
    assert len(session.scalars(select(AdGroup)).all()) == 1
    assert len(session.scalars(select(DailyMetric)).all()) == 1
    succeeded_runs = session.scalars(
        select(JobRun).where(JobRun.status == JobRunStatus.SUCCEEDED)
    ).all()
    assert len(succeeded_runs) == 2


def test_updated_campaign_data_is_upserted(
    session: Session, stub_collectors: GoogleAdsCollectorStub
) -> None:
    GoogleAdsSyncService(session).sync()
    stub_collectors.campaign_name = "Implants Updated"
    GoogleAdsSyncService(session).sync()

    campaign = session.scalar(select(Campaign).where(Campaign.external_campaign_id == "camp-1"))
    assert campaign is not None
    assert campaign.name == "Implants Updated"


def test_zero_campaign_account_is_successful(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    stub = GoogleAdsCollectorStub(zero=True)
    for name in (
        "collect_account",
        "collect_campaigns",
        "collect_ad_groups",
        "collect_ads",
        "collect_keywords",
        "collect_search_terms",
        "collect_metrics",
    ):
        monkeypatch.setattr(google_ads, name, getattr(stub, name))

    result = GoogleAdsSyncService(session).sync()

    assert result.status is JobRunStatus.SUCCEEDED
    assert result.records_processed == 1
    assert len(session.scalars(select(Campaign)).all()) == 0


def test_rollback_after_failure(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    stub = GoogleAdsCollectorStub(fail_at="metrics")
    for name in (
        "collect_account",
        "collect_campaigns",
        "collect_ad_groups",
        "collect_ads",
        "collect_keywords",
        "collect_search_terms",
        "collect_metrics",
    ):
        monkeypatch.setattr(google_ads, name, getattr(stub, name))

    with pytest.raises(RuntimeError):
        GoogleAdsSyncService(session).sync()

    assert len(session.scalars(select(Campaign)).all()) == 0
    assert len(session.scalars(select(AdGroup)).all()) == 0
    failed = session.scalar(select(JobRun).where(JobRun.status == JobRunStatus.FAILED))
    assert failed is not None
    assert failed.records_processed == 6
    assert failed.error_message is not None
    assert "secret" not in failed.error_message
    assert "token" not in failed.error_message


def test_successful_and_failed_job_run_records(
    session: Session, stub_collectors: GoogleAdsCollectorStub
) -> None:
    GoogleAdsSyncService(session).sync()
    stub_collectors.fail_at = "campaigns"
    with pytest.raises(RuntimeError):
        GoogleAdsSyncService(session).sync()

    job_runs = session.scalars(select(JobRun).order_by(JobRun.id)).all()
    assert [job.status for job in job_runs] == [JobRunStatus.SUCCEEDED, JobRunStatus.FAILED]
    assert job_runs[0].started_at is not None and job_runs[0].finished_at is not None
    assert job_runs[1].started_at is not None and job_runs[1].finished_at is not None
