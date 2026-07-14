from collections.abc import Iterable, Iterator
from dataclasses import fields
from datetime import date
from types import SimpleNamespace
from typing import Any

import pytest
from app.ads.enums import AdvertisingPlatform
from app.collectors import google_ads as google_ads_module
from app.collectors.google_ads import (
    GoogleAdsAuthenticationError,
    GoogleAdsAuthorizationError,
    GoogleAdsDateRange,
    GoogleAdsIntegrationError,
    GoogleAdsMissingCredentialsError,
    GoogleAdsRateLimitError,
    GoogleAdsReadOnlyAdapter,
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


class LaterPageErrorIterable:
    def __init__(self, rows: list[Any], error: Exception) -> None:
        self.rows = rows
        self.error = error

    def __iter__(self) -> Iterator[Any]:
        yield from self.rows
        raise self.error


class FakeGoogleAdsService:
    def __init__(
        self,
        rows_by_query: dict[str, list[Any]] | None = None,
        error: Exception | None = None,
        later_page_error: Exception | None = None,
    ) -> None:
        self.rows_by_query = rows_by_query or {}
        self.error = error
        self.later_page_error = later_page_error
        self.queries: list[str] = []

    def search(self, *, customer_id: str, query: str) -> Iterable[Any]:
        assert customer_id == "1234567890"
        self.queries.append(query)
        if self.error:
            raise self.error
        rows = self.rows_by_query.get(query, [])
        if self.later_page_error:
            return LaterPageErrorIterable(rows, self.later_page_error)
        return rows

    def search_stream(self, *, customer_id: str, query: str) -> Iterable[Any]:
        assert customer_id == "1234567890"
        self.queries.append(query)
        if self.error:
            raise self.error
        rows = self.rows_by_query.get(query, [])
        if self.later_page_error:
            return LaterPageErrorIterable(rows, self.later_page_error)
        return rows


class FakeGoogleAdsClient:
    def __init__(self, service: FakeGoogleAdsService) -> None:
        self.service = service
        self.requested_services: list[str] = []

    def get_service(self, name: str) -> FakeGoogleAdsService:
        assert name == "GoogleAdsService"
        self.requested_services.append(name)
        return self.service


def read_only_adapter(service: FakeGoogleAdsService) -> GoogleAdsReadOnlyAdapter:
    return google_ads_module._create_google_ads_read_only_adapter(FakeGoogleAdsClient(service))


def enum_value(name: str) -> SimpleNamespace:
    return SimpleNamespace(name=name)


def campaign_row() -> SimpleNamespace:
    return SimpleNamespace(
        campaign=SimpleNamespace(
            id=11,
            name="Implants",
            status=enum_value("ENABLED"),
            advertising_channel_type=enum_value("SEARCH"),
        )
    )


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


def test_client_factory_returns_read_only_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_ADS_DEVELOPER_TOKEN", "test-token")
    monkeypatch.setenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "1112223333")
    monkeypatch.setenv("GOOGLE_ADS_CUSTOMER_ID", "1234567890")
    monkeypatch.setenv("GOOGLE_ADS_SERVICE_ACCOUNT_FILE", "/tmp/service-account.json")
    raw_client = FakeGoogleAdsClient(FakeGoogleAdsService({account_query(): []}))
    loaded_config: dict[str, Any] | None = None

    class FakeGoogleAdsClientModule:
        @staticmethod
        def load_from_dict(config: dict[str, Any]) -> FakeGoogleAdsClient:
            nonlocal loaded_config
            loaded_config = config
            return raw_client

    def fake_require_google_ads_module() -> type[FakeGoogleAdsClientModule]:
        return FakeGoogleAdsClientModule

    monkeypatch.setattr(
        google_ads_module, "_require_google_ads_module", fake_require_google_ads_module
    )

    client = create_google_ads_client(Settings(_env_file=None))

    assert isinstance(client, GoogleAdsReadOnlyAdapter)
    assert {field.name for field in fields(client)} == set()
    assert raw_client.requested_services == ["GoogleAdsService"]
    approved_methods = {
        "account_rows",
        "ad_group_rows",
        "ad_rows",
        "campaign_rows",
        "keyword_rows",
        "metric_rows",
        "search_term_rows",
    }
    public_methods = {
        name for name in dir(client) if not name.startswith("_") and callable(getattr(client, name))
    }
    assert public_methods == approved_methods
    for blocked_name in (
        "search",
        "search_stream",
        "get_service",
        "from_google_ads_client",
        "_google_ads_client",
        "_search",
        "_search_stream",
        "_run_search",
        "_run_search_stream",
        "_run_fixed_search",
        "mutate_campaigns",
    ):
        assert not hasattr(client, blocked_name)
        with pytest.raises(AttributeError):
            getattr(client, blocked_name)
    list(client.account_rows(customer_id="1234567890"))
    assert raw_client.requested_services == ["GoogleAdsService"]
    assert loaded_config == {
        "developer_token": "test-token",
        "login_customer_id": "1112223333",
        "json_key_file_path": "/tmp/service-account.json",
        "use_proto_plus": True,
    }


def test_read_only_adapter_rejects_arbitrary_gaql() -> None:
    service = FakeGoogleAdsService({campaigns_query(): [campaign_row()]})
    client = read_only_adapter(service)
    arbitrary_query = "SELECT campaign_budget.amount_micros FROM campaign_budget"

    for blocked_name in (
        "search",
        "search_stream",
        "_search",
        "_search_stream",
        "_run_search",
        "_run_search_stream",
        "_run_fixed_search",
    ):
        with pytest.raises(AttributeError):
            getattr(client, blocked_name)

    fixed_method_name = "campaign_rows"
    fixed_method = getattr(client, fixed_method_name)
    with pytest.raises(TypeError):
        fixed_method(customer_id="1234567890", query=arbitrary_query)

    assert list(client.campaign_rows(customer_id="1234567890")) == [campaign_row()]
    assert service.queries == [campaigns_query()]
    assert arbitrary_query not in service.queries


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
    collector = GoogleAdsReadOnlyCollector(read_only_adapter(service), "1234567890")

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
    collector = GoogleAdsReadOnlyCollector(read_only_adapter(service), "1234567890")

    assert collector.collect_ad_groups({"11": 1})[0].campaign_id == 1
    assert collector.collect_ads({"22": 2})[0].ad_group_id == 2
    assert collector.collect_keywords({"22": 2})[0].external_keyword_id == "44"
    assert collector.collect_search_terms(
        {"22": 2}, GoogleAdsDateRange.YESTERDAY, today=date(2026, 7, 14)
    )[0].term == "implant dentist"


def test_error_handling_maps_authentication_and_rate_limit_failures() -> None:
    auth_collector = GoogleAdsReadOnlyCollector(
        read_only_adapter(FakeGoogleAdsService(error=RuntimeError("authentication failed"))),
        "1234567890",
    )
    with pytest.raises(GoogleAdsAuthenticationError):
        auth_collector.collect_campaigns(account_id=1)

    rate_limited_collector = GoogleAdsReadOnlyCollector(
        read_only_adapter(FakeGoogleAdsService(error=RuntimeError("RESOURCE_EXHAUSTED quota"))),
        "1234567890",
    )
    with pytest.raises(GoogleAdsRateLimitError):
        rate_limited_collector.collect_campaigns(account_id=1)


def test_authentication_markers_take_precedence_over_authorization_markers() -> None:
    collector = GoogleAdsReadOnlyCollector(
        read_only_adapter(
            FakeGoogleAdsService(
                error=RuntimeError(
                    "PERMISSION_DENIED OAuth credential token refresh failed "
                    "for unauthorized_client 401"
                )
            )
        ),
        "1234567890",
    )

    with pytest.raises(GoogleAdsAuthenticationError):
        collector.collect_campaigns(account_id=1)


@pytest.mark.parametrize(
    ("raw_error", "normalized_error"),
    [
        (
            RuntimeError("UNAUTHENTICATED invalid credentials"),
            GoogleAdsAuthenticationError,
        ),
        (
            RuntimeError("PERMISSION_DENIED customer not authorized"),
            GoogleAdsAuthorizationError,
        ),
        (
            RuntimeError("RESOURCE_EXHAUSTED quota exceeded"),
            GoogleAdsRateLimitError,
        ),
    ],
)
def test_later_page_errors_are_normalized(
    raw_error: Exception,
    normalized_error: type[GoogleAdsIntegrationError],
) -> None:
    service = FakeGoogleAdsService(
        {campaigns_query(): [campaign_row()]},
        later_page_error=raw_error,
    )
    collector = GoogleAdsReadOnlyCollector(read_only_adapter(service), "1234567890")

    with pytest.raises(normalized_error) as exc_info:
        collector.collect_campaigns(account_id=1)

    assert exc_info.value.__cause__ is raw_error


def test_normalized_metrics_batch_rejects_empty_metric_collections() -> None:
    collector = GoogleAdsReadOnlyCollector(read_only_adapter(FakeGoogleAdsService()), "1234567890")

    with pytest.raises(ValidationError):
        collector.collect_daily_performance_metrics(
            {"11": 55}, GoogleAdsDateRange.YESTERDAY, today=date(2026, 7, 14)
        )
