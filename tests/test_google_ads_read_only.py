import inspect
import traceback
from collections.abc import Iterable, Iterator
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
    collect_account,
    collect_ad_groups,
    collect_ads,
    collect_campaigns,
    collect_keywords,
    collect_metrics,
    collect_search_terms,
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
    def __init__(
        self,
        service: FakeGoogleAdsService,
        get_service_error: Exception | None = None,
    ) -> None:
        self.service = service
        self.get_service_error = get_service_error
        self.requested_services: list[str] = []

    def get_service(self, name: str) -> FakeGoogleAdsService:
        assert name == "GoogleAdsService"
        self.requested_services.append(name)
        if self.get_service_error:
            raise self.get_service_error
        return self.service


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


def valid_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("GOOGLE_ADS_DEVELOPER_TOKEN", "test-token")
    monkeypatch.setenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "1112223333")
    monkeypatch.setenv("GOOGLE_ADS_CUSTOMER_ID", "1234567890")
    monkeypatch.setenv("GOOGLE_ADS_CLIENT_ID", "client-id.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_ADS_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("GOOGLE_ADS_REFRESH_TOKEN", "refresh-token")
    return Settings(_env_file=None)


def install_fake_google_ads_module(
    monkeypatch: pytest.MonkeyPatch,
    service: FakeGoogleAdsService,
    load_error: Exception | None = None,
    get_service_error: Exception | None = None,
) -> tuple[FakeGoogleAdsClient, list[dict[str, Any]]]:
    raw_client = FakeGoogleAdsClient(service, get_service_error=get_service_error)
    loaded_configs: list[dict[str, Any]] = []

    class FakeGoogleAdsClientModule:
        @staticmethod
        def load_from_dict(config: dict[str, Any]) -> FakeGoogleAdsClient:
            loaded_configs.append(config)
            if load_error:
                raise load_error
            return raw_client

    def fake_require_google_ads_module() -> type[FakeGoogleAdsClientModule]:
        return FakeGoogleAdsClientModule

    monkeypatch.setattr(
        google_ads_module, "_require_google_ads_module", fake_require_google_ads_module
    )
    return raw_client, loaded_configs


def callable_parameters(value: Any) -> set[str]:
    try:
        return set(inspect.signature(value).parameters)
    except (TypeError, ValueError):
        return set()


def test_google_ads_settings_are_loaded_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = valid_settings(monkeypatch)

    assert settings.google_ads_developer_token == "test-token"
    assert settings.google_ads_login_customer_id == "1112223333"
    assert settings.google_ads_customer_id == "1234567890"
    assert settings.google_ads_client_id == "client-id.apps.googleusercontent.com"
    assert settings.google_ads_client_secret == "client-secret"
    assert settings.google_ads_refresh_token == "refresh-token"


def test_collectors_require_all_google_ads_credentials() -> None:
    settings = Settings(_env_file=None)

    with pytest.raises(GoogleAdsMissingCredentialsError) as exc_info:
        collect_account(settings=settings)

    assert "developer_token" in str(exc_info.value)
    assert "client_id" in str(exc_info.value)
    assert "client_secret" in str(exc_info.value)
    assert "refresh_token" in str(exc_info.value)


def test_public_api_exposes_only_fixed_collector_functions() -> None:
    expected_functions = {
        "collect_account",
        "collect_ad_groups",
        "collect_ads",
        "collect_campaigns",
        "collect_keywords",
        "collect_metrics",
        "collect_search_terms",
    }
    public_functions = {
        name
        for name, value in vars(google_ads_module).items()
        if inspect.isfunction(value) and not name.startswith("_")
    }

    assert public_functions == expected_functions
    assert set(google_ads_module.__all__) == expected_functions
    assert "GoogleAdsReadOnlyAdapter" not in vars(google_ads_module)
    assert "GoogleAdsReadOnlyCollector" not in vars(google_ads_module)
    assert "GoogleAdsConnectionTestService" not in vars(google_ads_module)
    assert "create_google_ads_client" not in vars(google_ads_module)


def test_no_module_callable_accepts_arbitrary_gaql() -> None:
    offenders: list[str] = []
    module_name = google_ads_module.__name__

    for name, value in vars(google_ads_module).items():
        if (
            inspect.isfunction(value)
            and value.__module__ == module_name
            and "query" in callable_parameters(value)
        ):
            offenders.append(name)
        if inspect.isclass(value) and value.__module__ == module_name:
            for method_name, method in inspect.getmembers(value, inspect.isfunction):
                if method.__module__ == module_name and "query" in callable_parameters(method):
                    offenders.append(f"{name}.{method_name}")

    assert offenders == []


@pytest.mark.parametrize(
    ("collector", "args"),
    [
        (collect_account, ()),
        (collect_campaigns, (1,)),
        (collect_ad_groups, ({"11": 1},)),
        (collect_ads, ({"22": 2},)),
        (collect_keywords, ({"22": 2},)),
        (collect_search_terms, ({"22": 2}, GoogleAdsDateRange.YESTERDAY)),
        (collect_metrics, ({"11": 55}, GoogleAdsDateRange.YESTERDAY)),
    ],
)
def test_fixed_collectors_reject_arbitrary_gaql_keyword(
    collector: Any,
    args: tuple[Any, ...],
) -> None:
    arbitrary_query = "SELECT campaign_budget.amount_micros FROM campaign_budget"

    with pytest.raises(TypeError):
        collector(*args, query=arbitrary_query)


def test_supported_google_ads_date_ranges_are_deterministic() -> None:
    today = date(2026, 7, 14)

    assert google_ads_module._resolve_date_range(
        GoogleAdsDateRange.YESTERDAY, today
    ).start_date == date(2026, 7, 13)
    assert google_ads_module._resolve_date_range(
        GoogleAdsDateRange.LAST_7_DAYS, today
    ).start_date == date(2026, 7, 7)
    assert google_ads_module._resolve_date_range(
        GoogleAdsDateRange.LAST_7_DAYS, today
    ).end_date == date(2026, 7, 13)
    prior_7_days = google_ads_module._resolve_date_range(
        GoogleAdsDateRange.PRIOR_7_DAYS, today
    )
    last_30_days = google_ads_module._resolve_date_range(
        GoogleAdsDateRange.LAST_30_DAYS, today
    )
    prior_30_days = google_ads_module._resolve_date_range(
        GoogleAdsDateRange.PRIOR_30_DAYS, today
    )
    assert prior_7_days.start_date == date(2026, 6, 30)
    assert prior_7_days.end_date == date(2026, 7, 6)
    assert last_30_days.start_date == date(2026, 6, 14)
    assert prior_30_days.start_date == date(2026, 5, 15)
    assert prior_30_days.end_date == date(2026, 6, 13)


def test_fixed_gaql_queries_are_internal_and_approved() -> None:
    window = google_ads_module._resolve_date_range(
        GoogleAdsDateRange.YESTERDAY, date(2026, 7, 14)
    )

    assert "FROM customer" in google_ads_module._account_query()
    assert "FROM campaign" in google_ads_module._campaigns_query()
    assert "FROM ad_group_ad" in google_ads_module._ads_query()
    assert "FROM keyword_view" in google_ads_module._keywords_query()
    assert "2026-07-13" in google_ads_module._search_terms_query(window)
    assert "metrics.cost_micros" in google_ads_module._metrics_query(window)


def test_collectors_normalize_google_ads_rows_to_phase_2_schemas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = valid_settings(monkeypatch)
    window = google_ads_module._resolve_date_range(
        GoogleAdsDateRange.YESTERDAY, date(2026, 7, 14)
    )
    service = FakeGoogleAdsService(
        {
            google_ads_module._account_query(): [
                SimpleNamespace(
                    customer=SimpleNamespace(
                        id=1234567890,
                        descriptive_name="Denticode Search",
                        currency_code="USD",
                        time_zone="America/New_York",
                    )
                )
            ],
            google_ads_module._campaigns_query(): [campaign_row()],
            google_ads_module._metrics_query(window): [
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
    raw_client, loaded_configs = install_fake_google_ads_module(monkeypatch, service)

    account = collect_account(settings=settings)
    campaigns = collect_campaigns(account_id=1, settings=settings)
    metrics = collect_metrics(
        {"11": 55},
        GoogleAdsDateRange.YESTERDAY,
        today=date(2026, 7, 14),
        settings=settings,
    )

    assert account.platform is AdvertisingPlatform.GOOGLE_ADS
    assert account.external_account_id == "1234567890"
    assert campaigns[0].external_campaign_id == "11"
    assert campaigns[0].channel_type == "SEARCH"
    assert metrics.metrics[0].entity_id == 55
    assert metrics.metrics[0].conversion_value_micros == 42_000_000
    assert raw_client.requested_services == [
        "GoogleAdsService",
        "GoogleAdsService",
        "GoogleAdsService",
    ]
    assert loaded_configs[0] == {
        "developer_token": "test-token",
        "login_customer_id": "1112223333",
        "client_id": "client-id.apps.googleusercontent.com",
        "client_secret": "client-secret",
        "refresh_token": "refresh-token",
        "use_proto_plus": True,
    }


def test_collectors_normalize_child_entities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = valid_settings(monkeypatch)
    service = FakeGoogleAdsService(
        {
            google_ads_module._ad_groups_query(): [
                SimpleNamespace(
                    campaign=SimpleNamespace(id=11),
                    ad_group=SimpleNamespace(id=22, name="Exact", status=enum_value("ENABLED")),
                )
            ],
            google_ads_module._ads_query(): [
                SimpleNamespace(
                    ad_group=SimpleNamespace(id=22),
                    ad_group_ad=SimpleNamespace(
                        ad=SimpleNamespace(id=33, name="Responsive search"),
                        status=enum_value("PAUSED"),
                    ),
                )
            ],
            google_ads_module._keywords_query(): [
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
            google_ads_module._search_terms_query(
                google_ads_module._resolve_date_range(
                    GoogleAdsDateRange.YESTERDAY, date(2026, 7, 14)
                )
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
    install_fake_google_ads_module(monkeypatch, service)

    assert collect_ad_groups({"11": 1}, settings=settings)[0].campaign_id == 1
    assert collect_ads({"22": 2}, settings=settings)[0].ad_group_id == 2
    assert collect_keywords({"22": 2}, settings=settings)[0].external_keyword_id == "44"
    assert collect_search_terms(
        {"22": 2},
        GoogleAdsDateRange.YESTERDAY,
        today=date(2026, 7, 14),
        settings=settings,
    )[0].term == "implant dentist"


def test_error_handling_maps_authentication_and_rate_limit_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = valid_settings(monkeypatch)
    install_fake_google_ads_module(
        monkeypatch,
        FakeGoogleAdsService(error=RuntimeError("authentication failed")),
    )
    with pytest.raises(GoogleAdsAuthenticationError):
        collect_campaigns(account_id=1, settings=settings)

    install_fake_google_ads_module(
        monkeypatch,
        FakeGoogleAdsService(error=RuntimeError("RESOURCE_EXHAUSTED quota")),
    )
    with pytest.raises(GoogleAdsRateLimitError):
        collect_campaigns(account_id=1, settings=settings)


def test_client_construction_errors_are_normalized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = valid_settings(monkeypatch)
    install_fake_google_ads_module(
        monkeypatch,
        FakeGoogleAdsService(),
        load_error=RuntimeError("invalid OAuth client secret"),
    )

    with pytest.raises(GoogleAdsAuthenticationError):
        collect_campaigns(account_id=1, settings=settings)


def test_authentication_errors_suppress_secret_bearing_exception_chain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = valid_settings(monkeypatch)
    secret_refresh_token = "secret-refresh-token-value"
    secret_client_secret = "secret-client-secret-value"
    raw_error = RuntimeError(
        "UNAUTHENTICATED token refresh failed "
        f"refresh_token={secret_refresh_token} client_secret={secret_client_secret}"
    )
    install_fake_google_ads_module(
        monkeypatch,
        FakeGoogleAdsService(error=raw_error),
    )

    with pytest.raises(GoogleAdsAuthenticationError) as exc_info:
        collect_campaigns(account_id=1, settings=settings)

    assert exc_info.value.__cause__ is None
    assert exc_info.value.__suppress_context__ is True
    rendered_traceback = "".join(
        traceback.format_exception(exc_info.type, exc_info.value, exc_info.tb)
    )
    assert secret_refresh_token not in rendered_traceback
    assert secret_client_secret not in rendered_traceback
    assert "Google Ads API authentication failed" in rendered_traceback


@pytest.mark.parametrize(
    ("raw_message", "secret_fragment"),
    [
        (
            "invalid_client client_secret=secret-invalid-client-value",
            "secret-invalid-client-value",
        ),
        (
            "unauthorized_client client-secret=secret-unauthorized-client-value",
            "secret-unauthorized-client-value",
        ),
        (
            "OAuth credential failure refresh-token=secret-oauth-refresh-token-value",
            "secret-oauth-refresh-token-value",
        ),
        (
            "token-refresh failed refresh_token=secret-token-refresh-value",
            "secret-token-refresh-value",
        ),
    ],
)
def test_oauth_authentication_markers_are_sanitized_without_chaining(
    monkeypatch: pytest.MonkeyPatch,
    raw_message: str,
    secret_fragment: str,
) -> None:
    settings = valid_settings(monkeypatch)
    install_fake_google_ads_module(
        monkeypatch,
        FakeGoogleAdsService(error=RuntimeError(raw_message)),
    )

    with pytest.raises(GoogleAdsAuthenticationError) as exc_info:
        collect_campaigns(account_id=1, settings=settings)

    assert exc_info.value.__cause__ is None
    assert exc_info.value.__suppress_context__ is True
    rendered_traceback = "".join(
        traceback.format_exception(exc_info.type, exc_info.value, exc_info.tb)
    )
    assert raw_message not in rendered_traceback
    assert secret_fragment not in rendered_traceback
    assert "Google Ads API authentication failed" in rendered_traceback


def test_get_service_errors_are_normalized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = valid_settings(monkeypatch)
    install_fake_google_ads_module(
        monkeypatch,
        FakeGoogleAdsService(),
        get_service_error=RuntimeError("authentication failed"),
    )

    with pytest.raises(GoogleAdsAuthenticationError):
        collect_campaigns(account_id=1, settings=settings)


@pytest.mark.parametrize(
    ("raw_message", "secret_fragment"),
    [
        (
            "PERMISSION_DENIED invalid_client client_secret=secret-mixed-client-value",
            "secret-mixed-client-value",
        ),
        (
            "USER_PERMISSION_DENIED token refresh failed refresh_token=secret-mixed-refresh-value",
            "secret-mixed-refresh-value",
        ),
        (
            "PERMISSION_DENIED unauthorized_client client-secret=secret-mixed-unauthorized-value",
            "secret-mixed-unauthorized-value",
        ),
    ],
)
def test_credential_markers_take_precedence_over_permission_denied(
    monkeypatch: pytest.MonkeyPatch,
    raw_message: str,
    secret_fragment: str,
) -> None:
    settings = valid_settings(monkeypatch)
    raw_error = RuntimeError(raw_message)
    install_fake_google_ads_module(
        monkeypatch,
        FakeGoogleAdsService(error=raw_error),
    )

    with pytest.raises(GoogleAdsAuthenticationError) as exc_info:
        collect_campaigns(account_id=1, settings=settings)

    assert exc_info.value.__cause__ is None
    assert exc_info.value.__suppress_context__ is True
    rendered_traceback = "".join(
        traceback.format_exception(exc_info.type, exc_info.value, exc_info.tb)
    )
    assert raw_message not in rendered_traceback
    assert secret_fragment not in rendered_traceback
    assert "Google Ads API authentication failed" in rendered_traceback


@pytest.mark.parametrize(
    ("raw_message", "secret_fragment"),
    [
        (
            "RESOURCE_EXHAUSTED quota exceeded refresh_token=secret-rate-refresh-value",
            "secret-rate-refresh-value",
        ),
        (
            "quota exceeded invalid_client client_secret=secret-rate-client-value",
            "secret-rate-client-value",
        ),
        (
            "rate limit token refresh failed refresh-token=secret-rate-token-value",
            "secret-rate-token-value",
        ),
    ],
)
def test_credential_markers_take_precedence_over_rate_limits(
    monkeypatch: pytest.MonkeyPatch,
    raw_message: str,
    secret_fragment: str,
) -> None:
    settings = valid_settings(monkeypatch)
    raw_error = RuntimeError(raw_message)
    install_fake_google_ads_module(
        monkeypatch,
        FakeGoogleAdsService(error=raw_error),
    )

    with pytest.raises(GoogleAdsAuthenticationError) as exc_info:
        collect_campaigns(account_id=1, settings=settings)

    assert exc_info.value.__cause__ is None
    assert exc_info.value.__suppress_context__ is True
    rendered_traceback = "".join(
        traceback.format_exception(exc_info.type, exc_info.value, exc_info.tb)
    )
    assert raw_message not in rendered_traceback
    assert secret_fragment not in rendered_traceback
    assert "Google Ads API authentication failed" in rendered_traceback


@pytest.mark.parametrize(
    "raw_message",
    [
        "RESOURCE_EXHAUSTED quota exceeded UNAUTHENTICATED invalid credentials",
        "quota exceeded while authentication failed",
        "too many requests 429 credential validation failed",
        "rate limit auth failure",
    ],
)
def test_generic_auth_markers_take_precedence_over_rate_limits(
    monkeypatch: pytest.MonkeyPatch,
    raw_message: str,
) -> None:
    settings = valid_settings(monkeypatch)
    raw_error = RuntimeError(raw_message)
    install_fake_google_ads_module(
        monkeypatch,
        FakeGoogleAdsService(error=raw_error),
    )

    with pytest.raises(GoogleAdsAuthenticationError) as exc_info:
        collect_campaigns(account_id=1, settings=settings)

    assert exc_info.value.__cause__ is None
    assert exc_info.value.__suppress_context__ is True
    rendered_traceback = "".join(
        traceback.format_exception(exc_info.type, exc_info.value, exc_info.tb)
    )
    assert raw_message not in rendered_traceback
    assert "Google Ads API authentication failed" in rendered_traceback


@pytest.mark.parametrize(
    "raw_error",
    [
        RuntimeError("PERMISSION_DENIED user lacks access to customer"),
        RuntimeError("USER_PERMISSION_DENIED user cannot access customer"),
        RuntimeError("PERMISSION_DENIED OAuth user lacks access to customer"),
        RuntimeError("USER_PERMISSION_DENIED OAuth user cannot access customer"),
    ],
)
def test_permission_denied_access_errors_are_authorization_failures(
    monkeypatch: pytest.MonkeyPatch,
    raw_error: Exception,
) -> None:
    settings = valid_settings(monkeypatch)
    install_fake_google_ads_module(
        monkeypatch,
        FakeGoogleAdsService(error=raw_error),
    )

    with pytest.raises(GoogleAdsAuthorizationError) as exc_info:
        collect_campaigns(account_id=1, settings=settings)

    assert exc_info.value.__cause__ is raw_error


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
    monkeypatch: pytest.MonkeyPatch,
    raw_error: Exception,
    normalized_error: type[GoogleAdsIntegrationError],
) -> None:
    settings = valid_settings(monkeypatch)
    install_fake_google_ads_module(
        monkeypatch,
        FakeGoogleAdsService(
            {google_ads_module._campaigns_query(): [campaign_row()]},
            later_page_error=raw_error,
        ),
    )

    with pytest.raises(normalized_error) as exc_info:
        collect_campaigns(account_id=1, settings=settings)

    if normalized_error is GoogleAdsAuthenticationError:
        assert exc_info.value.__cause__ is None
        assert exc_info.value.__suppress_context__ is True
    else:
        assert exc_info.value.__cause__ is raw_error


def test_normalized_metrics_batch_rejects_empty_metric_collections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = valid_settings(monkeypatch)
    install_fake_google_ads_module(monkeypatch, FakeGoogleAdsService())

    with pytest.raises(ValidationError):
        collect_metrics(
            {"11": 55},
            GoogleAdsDateRange.YESTERDAY,
            today=date(2026, 7, 14),
            settings=settings,
        )
