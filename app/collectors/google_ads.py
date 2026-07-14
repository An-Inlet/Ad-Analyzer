from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum
from importlib import import_module
from typing import Any, NoReturn, Protocol, cast

from app.ads.enums import AdvertisingPlatform
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
from app.settings import Settings


class GoogleAdsIntegrationError(RuntimeError):
    """Base error for read-only Google Ads integration failures."""


class GoogleAdsMissingCredentialsError(GoogleAdsIntegrationError):
    """Raised when required Google Ads environment settings are missing."""


class GoogleAdsAuthenticationError(GoogleAdsIntegrationError):
    """Raised when Google Ads rejects configured credentials."""


class GoogleAdsAuthorizationError(GoogleAdsIntegrationError):
    """Raised when Google Ads denies access to a requested read-only resource."""


class GoogleAdsRateLimitError(GoogleAdsIntegrationError):
    """Raised when Google Ads rate limits a read-only request."""


class GoogleAdsReadOnlyClient(Protocol):
    def account_rows(self, *, customer_id: str) -> Iterable[Any]: ...

    def campaign_rows(self, *, customer_id: str) -> Iterable[Any]: ...

    def ad_group_rows(self, *, customer_id: str) -> Iterable[Any]: ...

    def ad_rows(self, *, customer_id: str) -> Iterable[Any]: ...

    def keyword_rows(self, *, customer_id: str) -> Iterable[Any]: ...

    def search_term_rows(
        self,
        *,
        customer_id: str,
        window: "ResolvedDateRange",
    ) -> Iterable[Any]: ...

    def metric_rows(
        self,
        *,
        customer_id: str,
        window: "ResolvedDateRange",
    ) -> Iterable[Any]: ...


_CustomerRowsCallable = Callable[[str], Iterable[Any]]
_WindowRowsCallable = Callable[[str, "ResolvedDateRange"], Iterable[Any]]


@dataclass(frozen=True, slots=True, init=False)
class GoogleAdsReadOnlyAdapter:
    """Narrow facade over GoogleAdsClient for approved read-only operations."""

    _account_rows: _CustomerRowsCallable
    _campaign_rows: _CustomerRowsCallable
    _ad_group_rows: _CustomerRowsCallable
    _ad_rows: _CustomerRowsCallable
    _keyword_rows: _CustomerRowsCallable
    _search_term_rows: _WindowRowsCallable
    _metric_rows: _WindowRowsCallable

    def account_rows(self, *, customer_id: str) -> Iterable[Any]:
        return self._account_rows(customer_id)

    def campaign_rows(self, *, customer_id: str) -> Iterable[Any]:
        return self._campaign_rows(customer_id)

    def ad_group_rows(self, *, customer_id: str) -> Iterable[Any]:
        return self._ad_group_rows(customer_id)

    def ad_rows(self, *, customer_id: str) -> Iterable[Any]:
        return self._ad_rows(customer_id)

    def keyword_rows(self, *, customer_id: str) -> Iterable[Any]:
        return self._keyword_rows(customer_id)

    def search_term_rows(
        self,
        *,
        customer_id: str,
        window: "ResolvedDateRange",
    ) -> Iterable[Any]:
        return self._search_term_rows(customer_id, window)

    def metric_rows(
        self,
        *,
        customer_id: str,
        window: "ResolvedDateRange",
    ) -> Iterable[Any]:
        return self._metric_rows(customer_id, window)


def _create_google_ads_read_only_adapter(google_ads_client: Any) -> GoogleAdsReadOnlyAdapter:
    service = google_ads_client.get_service("GoogleAdsService")
    search = service.search

    def run_google_ads_query(customer_id: str, fixed_gaql: str) -> Iterable[Any]:
        try:
            rows = search(customer_id=customer_id, query=fixed_gaql)
            yield from rows
        except Exception as exc:
            _raise_normalized_google_ads_error(exc)

    def account_rows(customer_id: str) -> Iterable[Any]:
        return run_google_ads_query(customer_id, account_query())

    def campaign_rows(customer_id: str) -> Iterable[Any]:
        return run_google_ads_query(customer_id, campaigns_query())

    def ad_group_rows(customer_id: str) -> Iterable[Any]:
        return run_google_ads_query(customer_id, ad_groups_query())

    def ad_rows(customer_id: str) -> Iterable[Any]:
        return run_google_ads_query(customer_id, ads_query())

    def keyword_rows(customer_id: str) -> Iterable[Any]:
        return run_google_ads_query(customer_id, keywords_query())

    def search_term_rows(customer_id: str, window: "ResolvedDateRange") -> Iterable[Any]:
        return run_google_ads_query(customer_id, search_terms_query(window))

    def metric_rows(customer_id: str, window: "ResolvedDateRange") -> Iterable[Any]:
        return run_google_ads_query(customer_id, daily_performance_metrics_query(window))

    adapter = GoogleAdsReadOnlyAdapter()
    object.__setattr__(adapter, "_account_rows", account_rows)
    object.__setattr__(adapter, "_campaign_rows", campaign_rows)
    object.__setattr__(adapter, "_ad_group_rows", ad_group_rows)
    object.__setattr__(adapter, "_ad_rows", ad_rows)
    object.__setattr__(adapter, "_keyword_rows", keyword_rows)
    object.__setattr__(adapter, "_search_term_rows", search_term_rows)
    object.__setattr__(adapter, "_metric_rows", metric_rows)
    return adapter


class GoogleAdsDateRange(StrEnum):
    YESTERDAY = "yesterday"
    LAST_7_DAYS = "last_7_days"
    PRIOR_7_DAYS = "prior_7_days"
    LAST_30_DAYS = "last_30_days"
    PRIOR_30_DAYS = "prior_30_days"


@dataclass(frozen=True)
class ResolvedDateRange:
    name: GoogleAdsDateRange
    start_date: date
    end_date: date


def resolve_date_range(name: GoogleAdsDateRange, today: date | None = None) -> ResolvedDateRange:
    current_date = today or date.today()
    yesterday = current_date - timedelta(days=1)
    match name:
        case GoogleAdsDateRange.YESTERDAY:
            start = end = yesterday
        case GoogleAdsDateRange.LAST_7_DAYS:
            start, end = current_date - timedelta(days=7), yesterday
        case GoogleAdsDateRange.PRIOR_7_DAYS:
            start, end = current_date - timedelta(days=14), current_date - timedelta(days=8)
        case GoogleAdsDateRange.LAST_30_DAYS:
            start, end = current_date - timedelta(days=30), yesterday
        case GoogleAdsDateRange.PRIOR_30_DAYS:
            start, end = current_date - timedelta(days=60), current_date - timedelta(days=31)
    return ResolvedDateRange(name=name, start_date=start, end_date=end)


def _between_clause(window: ResolvedDateRange) -> str:
    start = window.start_date.isoformat()
    end = window.end_date.isoformat()
    return f"segments.date BETWEEN '{start}' AND '{end}'"


def account_query() -> str:
    return """
        SELECT
          customer.id,
          customer.descriptive_name,
          customer.currency_code,
          customer.time_zone
        FROM customer
        LIMIT 1
    """


def campaigns_query() -> str:
    return """
        SELECT
          campaign.id,
          campaign.name,
          campaign.status,
          campaign.advertising_channel_type
        FROM campaign
        WHERE campaign.status != 'REMOVED'
    """


def ad_groups_query() -> str:
    return """
        SELECT
          campaign.id,
          ad_group.id,
          ad_group.name,
          ad_group.status
        FROM ad_group
        WHERE ad_group.status != 'REMOVED'
    """


def ads_query() -> str:
    return """
        SELECT
          ad_group.id,
          ad_group_ad.ad.id,
          ad_group_ad.ad.name,
          ad_group_ad.status
        FROM ad_group_ad
        WHERE ad_group_ad.status != 'REMOVED'
    """


def keywords_query() -> str:
    return """
        SELECT
          ad_group.id,
          ad_group_criterion.criterion_id,
          ad_group_criterion.keyword.text,
          ad_group_criterion.keyword.match_type,
          ad_group_criterion.status
        FROM keyword_view
        WHERE ad_group_criterion.status != 'REMOVED'
    """


def search_terms_query(window: ResolvedDateRange) -> str:
    return f"""
        SELECT
          ad_group.id,
          search_term_view.search_term,
          segments.keyword.info.match_type
        FROM search_term_view
        WHERE {_between_clause(window)}
    """


def daily_performance_metrics_query(window: ResolvedDateRange) -> str:
    return f"""
        SELECT
          segments.date,
          campaign.id,
          metrics.impressions,
          metrics.clicks,
          metrics.cost_micros,
          metrics.conversions,
          metrics.conversions_value
        FROM campaign
        WHERE {_between_clause(window)}
    """


def _require_google_ads_module() -> Any:
    try:
        module = import_module("google.ads.googleads.client")
    except ImportError as exc:
        raise GoogleAdsIntegrationError("google-ads dependency is not installed") from exc
    return module.__dict__["GoogleAdsClient"]


def _required_config(settings: Settings) -> dict[str, str]:
    values = {
        "developer_token": settings.google_ads_developer_token,
        "login_customer_id": settings.google_ads_login_customer_id,
        "customer_id": settings.google_ads_customer_id,
        "service_account_file": settings.google_ads_service_account_file,
    }
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise GoogleAdsMissingCredentialsError(
            "Missing required Google Ads configuration: " + ", ".join(sorted(missing))
        )
    return {key: cast(str, value) for key, value in values.items()}


def create_google_ads_client(settings: Settings) -> GoogleAdsReadOnlyClient:
    config = _required_config(settings)
    google_ads_client = _require_google_ads_module()
    return _create_google_ads_read_only_adapter(
        google_ads_client.load_from_dict(
            {
                "developer_token": config["developer_token"],
                "login_customer_id": config["login_customer_id"],
                "json_key_file_path": config["service_account_file"],
                "use_proto_plus": True,
            }
        )
    )


def _google_ads_error_text(exc: Exception) -> str:
    parts = [type(exc).__name__, str(exc)]
    code = getattr(exc, "code", None)
    if callable(code):
        try:
            code = code()
        except Exception:
            code = None
    if code is not None:
        parts.append(str(code))
    failure = getattr(exc, "failure", None)
    if failure is not None:
        parts.append(str(failure))
    return " ".join(parts).lower()


def _raise_normalized_google_ads_error(exc: Exception) -> NoReturn:
    message = _google_ads_error_text(exc)
    if any(
        marker in message
        for marker in (
            "resource_exhausted",
            "resource exhausted",
            "quota",
            "rate limit",
            "rate_limit",
            "too many requests",
            "429",
        )
    ):
        raise GoogleAdsRateLimitError("Google Ads API rate limit encountered") from exc
    if any(
        marker in message
        for marker in (
            "unauthenticated",
            "authentication",
            "credential",
            "invalid_grant",
            "oauth",
            "401",
            "token refresh",
            "token_refresh",
            "refresh token",
            "unauthorized_client",
        )
    ):
        raise GoogleAdsAuthenticationError("Google Ads API authentication failed") from exc
    if any(
        marker in message
        for marker in (
            "permission_denied",
            "permission denied",
            "authorization",
            "unauthorized",
            "not authorized",
            "access denied",
            "user_permission_denied",
            "403",
        )
    ):
        raise GoogleAdsAuthorizationError("Google Ads API authorization failed") from exc
    raise GoogleAdsIntegrationError("Google Ads read-only request failed") from exc


class GoogleAdsConnectionTestService:
    def __init__(self, client: GoogleAdsReadOnlyClient, customer_id: str) -> None:
        self.client = client
        self.customer_id = customer_id

    def test_connection(self) -> bool:
        next(iter(self.client.account_rows(customer_id=self.customer_id)), None)
        return True


class GoogleAdsReadOnlyCollector:
    def __init__(self, client: GoogleAdsReadOnlyClient, customer_id: str) -> None:
        self.client = client
        self.customer_id = customer_id

    def collect_account(self) -> AdvertisingAccountCreate:
        row = next(iter(self.client.account_rows(customer_id=self.customer_id)))
        return AdvertisingAccountCreate(
            platform=AdvertisingPlatform.GOOGLE_ADS,
            external_account_id=str(row.customer.id),
            name=row.customer.descriptive_name or str(row.customer.id),
            currency_code=row.customer.currency_code,
            time_zone=row.customer.time_zone,
        )

    def collect_campaigns(self, account_id: int) -> list[CampaignCreate]:
        return [
            CampaignCreate(
                account_id=account_id,
                platform=AdvertisingPlatform.GOOGLE_ADS,
                external_campaign_id=str(row.campaign.id),
                name=row.campaign.name,
                status=str(row.campaign.status.name),
                channel_type=str(row.campaign.advertising_channel_type.name),
            )
            for row in self.client.campaign_rows(customer_id=self.customer_id)
        ]

    def collect_ad_groups(self, campaign_ids_by_external_id: dict[str, int]) -> list[AdGroupCreate]:
        return [
            AdGroupCreate(
                campaign_id=campaign_ids_by_external_id[str(row.campaign.id)],
                platform=AdvertisingPlatform.GOOGLE_ADS,
                external_ad_group_id=str(row.ad_group.id),
                name=row.ad_group.name,
                status=str(row.ad_group.status.name),
            )
            for row in self.client.ad_group_rows(customer_id=self.customer_id)
            if str(row.campaign.id) in campaign_ids_by_external_id
        ]

    def collect_ads(self, ad_group_ids_by_external_id: dict[str, int]) -> list[AdCreate]:
        return [
            AdCreate(
                ad_group_id=ad_group_ids_by_external_id[str(row.ad_group.id)],
                platform=AdvertisingPlatform.GOOGLE_ADS,
                external_ad_id=str(row.ad_group_ad.ad.id),
                name=row.ad_group_ad.ad.name or str(row.ad_group_ad.ad.id),
                status=str(row.ad_group_ad.status.name),
            )
            for row in self.client.ad_rows(customer_id=self.customer_id)
            if str(row.ad_group.id) in ad_group_ids_by_external_id
        ]

    def collect_keywords(self, ad_group_ids_by_external_id: dict[str, int]) -> list[KeywordCreate]:
        return [
            KeywordCreate(
                ad_group_id=ad_group_ids_by_external_id[str(row.ad_group.id)],
                platform=AdvertisingPlatform.GOOGLE_ADS,
                external_keyword_id=str(row.ad_group_criterion.criterion_id),
                text=row.ad_group_criterion.keyword.text,
                match_type=str(row.ad_group_criterion.keyword.match_type.name),
                status=str(row.ad_group_criterion.status.name),
            )
            for row in self.client.keyword_rows(customer_id=self.customer_id)
            if str(row.ad_group.id) in ad_group_ids_by_external_id
        ]

    def collect_search_terms(
        self,
        ad_group_ids_by_external_id: dict[str, int],
        date_range: GoogleAdsDateRange,
        today: date | None = None,
    ) -> list[SearchTermCreate]:
        window = resolve_date_range(date_range, today)
        return [
            SearchTermCreate(
                ad_group_id=ad_group_ids_by_external_id[str(row.ad_group.id)],
                platform=AdvertisingPlatform.GOOGLE_ADS,
                term=row.search_term_view.search_term,
                match_type=str(row.segments.keyword.info.match_type.name),
            )
            for row in self.client.search_term_rows(customer_id=self.customer_id, window=window)
            if str(row.ad_group.id) in ad_group_ids_by_external_id
        ]

    def collect_daily_performance_metrics(
        self,
        campaign_ids_by_external_id: dict[str, int],
        date_range: GoogleAdsDateRange,
        today: date | None = None,
    ) -> NormalizedMetricsBatch:
        window = resolve_date_range(date_range, today)
        metrics = [
            DailyMetricCreate(
                platform=AdvertisingPlatform.GOOGLE_ADS,
                metric_date=date.fromisoformat(row.segments.date),
                entity_type="campaign",
                entity_id=campaign_ids_by_external_id[str(row.campaign.id)],
                campaign_id=campaign_ids_by_external_id[str(row.campaign.id)],
                impressions=row.metrics.impressions,
                clicks=row.metrics.clicks,
                cost_micros=row.metrics.cost_micros,
                conversions=Decimal(str(row.metrics.conversions)),
                conversion_value_micros=int(
                    Decimal(str(row.metrics.conversions_value)) * 1_000_000
                ),
            )
            for row in self.client.metric_rows(
                customer_id=self.customer_id,
                window=window,
            )
            if str(row.campaign.id) in campaign_ids_by_external_id
        ]
        return NormalizedMetricsBatch(metrics=metrics)
