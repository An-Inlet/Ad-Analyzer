from datetime import date
from types import SimpleNamespace
from typing import Any

import pytest
from app.ads.enums import AdvertisingPlatform
from app.collectors.google_ads import (
    GoogleAdsAuthenticationError,
    GoogleAdsDateRange,
    GoogleAdsMissingCredentialsError,
    GoogleAdsRateLimitError,
    GoogleAdsReadOnlyCollector,
    account_query,
    ads_query,
    campaigns_query,
    create_google_ads_client,
    daily_performance_metrics_query,
    keywords_query,
    resolve_date_range,
    search_terms_query,
)
from app.settings import Settings
from pydantic import ValidationError


class FakeGoogleAdsService:
    def __init__(
        self,
        rows_by_query: dict[str, list[Any]] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.rows_by_query = rows_by_query or {}
        self.error = error
        self.queries: list[str] = []

    def search(self, *, customer_id: str, query: str) -> list[Any]:
        assert customer_id == "1234567890"
        self.queries.append(query)
        if self.error:
            raise self.error
        return self.rows_by_query.get(query, [])


class FakeGoogleAdsClient:
    def __init__(self, service: FakeGoogleAdsService) -> None:
        self.service = service

    def get_service(self, name: str) -> FakeGoogleAdsService:
        assert name == "GoogleAdsService"
        return self.service


def enum_value(name: str) -> SimpleNamespace:
    return SimpleNamespace(name=name)


def test_google_ads_settings_are_loaded_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_ADS_DEVELOPER_TOKEN", "test-token")
    monkeypatch.setenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "1112223333")
    monkeypatch.setenv("GOOGLE_ADS_CUSTOMER_ID", "1234567890")
    monkeypatch.setenv("GOOGLE_ADS_SERVICE_ACCOUNT_FILE", "/tmp/service-account.json")

    settings = Settings(_env_file=None)

    assert settings.google_ads_developer_token == "test-token"
    assert settings.google_ads_login_customer_id == "1112223333"
    assert settings.google_ads_customer_id == "1234567890"
    assert settings.google_ads_service_account_file == "/tmp/service-account.json"


def test_client_factory_requires_all_google_ads_credentials() -> None:
    settings = Settings(_env_file=None)

    with pytest.raises(GoogleAdsMissingCredentialsError) as exc_info:
        create_google_ads_client(settings)

    assert "developer_token" in str(exc_info.value)
    assert "service_account_file" in str(exc_info.value)


def test_supported_google_ads_date_ranges_are_deterministic() -> None:
    today = date(2026, 7, 14)

    assert resolve_date_range(GoogleAdsDateRange.YESTERDAY, today).start_date == date(2026, 7, 13)
    assert resolve_date_range(GoogleAdsDateRange.LAST_7_DAYS, today).start_date == date(2026, 7, 7)
    assert resolve_date_range(GoogleAdsDateRange.LAST_7_DAYS, today).end_date == date(2026, 7, 13)
    prior_7_days = resolve_date_range(GoogleAdsDateRange.PRIOR_7_DAYS, today)
    last_30_days = resolve_date_range(GoogleAdsDateRange.LAST_30_DAYS, today)
    prior_30_days = resolve_date_range(GoogleAdsDateRange.PRIOR_30_DAYS, today)
    assert prior_7_days.start_date == date(2026, 6, 30)
    assert prior_7_days.end_date == date(2026, 7, 6)
    assert last_30_days.start_date == date(2026, 6, 14)
    assert prior_30_days.start_date == date(2026, 5, 15)
    assert prior_30_days.end_date == date(2026, 6, 13)


def test_fixed_gaql_queries_do_not_expose_arbitrary_execution() -> None:
    window = resolve_date_range(GoogleAdsDateRange.YESTERDAY, date(2026, 7, 14))

    assert "FROM customer" in account_query()
    assert "FROM campaign" in campaigns_query()
    assert "FROM ad_group_ad" in ads_query()
    assert "FROM keyword_view" in keywords_query()
    assert "2026-07-13" in search_terms_query(window)
    assert "metrics.cost_micros" in daily_performance_metrics_query(window)


def test_collector_normalizes_google_ads_rows_to_phase_2_schemas() -> None:
    window = resolve_date_range(GoogleAdsDateRange.YESTERDAY, date(2026, 7, 14))
    service = FakeGoogleAdsService(
        {
            account_query(): [
                SimpleNamespace(
                    customer=SimpleNamespace(
                        id=1234567890,
                        descriptive_name="Denticode Search",
                        currency_code="USD",
                        time_zone="America/New_York",
                    )
                )
            ],
            campaigns_query(): [
                SimpleNamespace(
                    campaign=SimpleNamespace(
                        id=11,
                        name="Implants",
                        status=enum_value("ENABLED"),
                        advertising_channel_type=enum_value("SEARCH"),
                    )
                )
            ],
            daily_performance_metrics_query(window): [
                SimpleNamespace(
                    segments=SimpleNamespace(date="2026-07-13"),
                    campaign=SimpleNamespace(id=11),
                    metrics=SimpleNamespace(
                        impressions=100,
                        clicks=10,
                        cost_micros=1230000,
                        conversions=2.5,
                        conversions_value=42,
                    ),
                )
            ],
        }
    )
    collector = GoogleAdsReadOnlyCollector(FakeGoogleAdsClient(service), "1234567890")

    account = collector.collect_account()
    campaigns = collector.collect_campaigns(account_id=1)
    metrics = collector.collect_daily_performance_metrics(
        {"11": 55}, GoogleAdsDateRange.YESTERDAY, today=date(2026, 7, 14)
    )

    assert account.platform is AdvertisingPlatform.GOOGLE_ADS
    assert account.external_account_id == "1234567890"
    assert campaigns[0].external_campaign_id == "11"
    assert campaigns[0].channel_type == "SEARCH"
    assert metrics.metrics[0].entity_id == 55
    assert metrics.metrics[0].conversion_value_micros == 42_000_000


def test_collector_normalizes_child_entities() -> None:
    service = FakeGoogleAdsService(
        {
            """
        SELECT
          campaign.id,
          ad_group.id,
          ad_group.name,
          ad_group.status
        FROM ad_group
        WHERE ad_group.status != 'REMOVED'
    """: [
                SimpleNamespace(
                    campaign=SimpleNamespace(id=11),
                    ad_group=SimpleNamespace(id=22, name="Exact", status=enum_value("ENABLED")),
                )
            ],
            ads_query(): [
                SimpleNamespace(
                    ad_group=SimpleNamespace(id=22),
                    ad_group_ad=SimpleNamespace(
                        ad=SimpleNamespace(id=33, name="Responsive search"),
                        status=enum_value("PAUSED"),
                    ),
                )
            ],
            keywords_query(): [
                SimpleNamespace(
                    ad_group=SimpleNamespace(id=22),
                    ad_group_criterion=SimpleNamespace(
                        criterion_id=44,
                        keyword=SimpleNamespace(
                            text="dentist near me", match_type=enum_value("EXACT")
                        ),
                        status=enum_value("ENABLED"),
                    ),
                )
            ],
            search_terms_query(
                resolve_date_range(GoogleAdsDateRange.YESTERDAY, date(2026, 7, 14))
            ): [
                SimpleNamespace(
                    ad_group=SimpleNamespace(id=22),
                    search_term_view=SimpleNamespace(search_term="implant dentist"),
                    segments=SimpleNamespace(
                        keyword=SimpleNamespace(info=SimpleNamespace(match_type=enum_value("PHRASE")))
                    ),
                )
            ],
        }
    )
    collector = GoogleAdsReadOnlyCollector(FakeGoogleAdsClient(service), "1234567890")

    assert collector.collect_ad_groups({"11": 1})[0].campaign_id == 1
    assert collector.collect_ads({"22": 2})[0].ad_group_id == 2
    assert collector.collect_keywords({"22": 2})[0].external_keyword_id == "44"
    assert collector.collect_search_terms(
        {"22": 2}, GoogleAdsDateRange.YESTERDAY, today=date(2026, 7, 14)
    )[0].term == "implant dentist"


def test_error_handling_maps_authentication_and_rate_limit_failures() -> None:
    auth_collector = GoogleAdsReadOnlyCollector(
        FakeGoogleAdsClient(FakeGoogleAdsService(error=RuntimeError("authentication failed"))),
        "1234567890",
    )
    with pytest.raises(GoogleAdsAuthenticationError):
        auth_collector.collect_campaigns(account_id=1)

    rate_limited_collector = GoogleAdsReadOnlyCollector(
        FakeGoogleAdsClient(FakeGoogleAdsService(error=RuntimeError("RESOURCE_EXHAUSTED quota"))),
        "1234567890",
    )
    with pytest.raises(GoogleAdsRateLimitError):
        rate_limited_collector.collect_campaigns(account_id=1)


def test_normalized_metrics_batch_rejects_empty_metric_collections() -> None:
    collector = GoogleAdsReadOnlyCollector(
        FakeGoogleAdsClient(FakeGoogleAdsService()), "1234567890"
    )

    with pytest.raises(ValidationError):
        collector.collect_daily_performance_metrics(
            {"11": 55}, GoogleAdsDateRange.YESTERDAY, today=date(2026, 7, 14)
        )
