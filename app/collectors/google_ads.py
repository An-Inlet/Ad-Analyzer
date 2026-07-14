import json as _json
from dataclasses import dataclass as _dataclass
from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum
from importlib import import_module as _import_module
from pathlib import Path as _Path
from typing import Any, NoReturn
from typing import cast as _cast

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
from app.settings import settings as app_settings

__all__ = (
    "collect_account",
    "collect_ad_groups",
    "collect_ads",
    "collect_campaigns",
    "collect_keywords",
    "collect_metrics",
    "collect_search_terms",
)


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


class GoogleAdsDateRange(StrEnum):
    YESTERDAY = "yesterday"
    LAST_7_DAYS = "last_7_days"
    PRIOR_7_DAYS = "prior_7_days"
    LAST_30_DAYS = "last_30_days"
    PRIOR_30_DAYS = "prior_30_days"


@_dataclass(frozen=True)
class _ResolvedDateRange:
    name: GoogleAdsDateRange
    start_date: date
    end_date: date


def _settings_or_default(settings: Settings | None) -> Settings:
    return settings or app_settings


def _resolve_date_range(
    name: GoogleAdsDateRange,
    today: date | None = None,
) -> _ResolvedDateRange:
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
    return _ResolvedDateRange(name=name, start_date=start, end_date=end)


def _between_clause(window: _ResolvedDateRange) -> str:
    start = window.start_date.isoformat()
    end = window.end_date.isoformat()
    return f"segments.date BETWEEN '{start}' AND '{end}'"


def _account_query() -> str:
    return """
        SELECT
          customer.id,
          customer.descriptive_name,
          customer.currency_code,
          customer.time_zone
        FROM customer
        LIMIT 1
    """


def _campaigns_query() -> str:
    return """
        SELECT
          campaign.id,
          campaign.name,
          campaign.status,
          campaign.advertising_channel_type
        FROM campaign
        WHERE campaign.status != 'REMOVED'
    """


def _ad_groups_query() -> str:
    return """
        SELECT
          campaign.id,
          ad_group.id,
          ad_group.name,
          ad_group.status
        FROM ad_group
        WHERE ad_group.status != 'REMOVED'
    """


def _ads_query() -> str:
    return """
        SELECT
          ad_group.id,
          ad_group_ad.ad.id,
          ad_group_ad.ad.name,
          ad_group_ad.status
        FROM ad_group_ad
        WHERE ad_group_ad.status != 'REMOVED'
    """


def _keywords_query() -> str:
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


def _search_terms_query(window: _ResolvedDateRange) -> str:
    return f"""
        SELECT
          ad_group.id,
          search_term_view.search_term,
          segments.keyword.info.match_type
        FROM search_term_view
        WHERE {_between_clause(window)}
    """


def _metrics_query(window: _ResolvedDateRange) -> str:
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
        module = _import_module("google.ads.googleads.client")
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
    return {key: _cast(str, value) for key, value in values.items()}


def _client_config(config: dict[str, str]) -> dict[str, object]:
    return {
        "developer_token": config["developer_token"],
        "login_customer_id": config["login_customer_id"],
        "json_key_file_path": config["service_account_file"],
        "use_proto_plus": True,
    }


def _validate_service_account_file(file_path: str) -> None:
    try:
        raw_credentials = _Path(file_path).read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise GoogleAdsMissingCredentialsError(
            "Google Ads service-account credentials file is missing"
        ) from exc
    except UnicodeDecodeError as exc:
        raise GoogleAdsAuthenticationError(
            "Google Ads service-account credentials file is malformed"
        ) from exc
    except OSError as exc:
        raise GoogleAdsMissingCredentialsError(
            "Google Ads service-account credentials file is unreadable"
        ) from exc

    try:
        credentials = _json.loads(raw_credentials)
    except _json.JSONDecodeError as exc:
        raise GoogleAdsAuthenticationError(
            "Google Ads service-account credentials file is malformed"
        ) from exc

    if not isinstance(credentials, dict):
        raise GoogleAdsAuthenticationError(
            "Google Ads service-account credentials file is invalid"
        )

    required_fields = ("type", "client_email", "private_key", "token_uri")
    missing_fields = [name for name in required_fields if not credentials.get(name)]
    if credentials.get("type") != "service_account" or missing_fields:
        raise GoogleAdsAuthenticationError(
            "Google Ads service-account credentials file is invalid"
        )


def _google_ads_service(settings: Settings | None) -> tuple[Any, str]:
    config = _required_config(_settings_or_default(settings))
    _validate_service_account_file(config["service_account_file"])
    google_ads_client = _require_google_ads_module()
    try:
        client = google_ads_client.load_from_dict(_client_config(config))
        service = client.get_service("GoogleAdsService")
    except Exception as exc:
        _raise_normalized_google_ads_error(exc, credential_context=True)
    return service, config["customer_id"]


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


def _raise_normalized_google_ads_error(
    exc: Exception,
    *,
    credential_context: bool = False,
) -> NoReturn:
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
    if "credential" in message:
        raise GoogleAdsAuthenticationError("Google Ads API authentication failed") from exc
    if credential_context and any(
        marker in message
        for marker in (
            "service account",
            "service-account",
            "private key",
            "json key",
            "client email",
            "token_uri",
        )
    ):
        raise GoogleAdsAuthenticationError("Google Ads API authentication failed") from exc
    raise GoogleAdsIntegrationError("Google Ads read-only request failed") from exc


def collect_account(*, settings: Settings | None = None) -> AdvertisingAccountCreate:
    service, customer_id = _google_ads_service(settings)

    try:
        rows = service.search(customer_id=customer_id, query=_account_query())
        row = next(iter(rows))
    except Exception as exc:
        _raise_normalized_google_ads_error(exc)
    return AdvertisingAccountCreate(
        platform=AdvertisingPlatform.GOOGLE_ADS,
        external_account_id=str(row.customer.id),
        name=row.customer.descriptive_name or str(row.customer.id),
        currency_code=row.customer.currency_code,
        time_zone=row.customer.time_zone,
    )


def collect_campaigns(
    account_id: int,
    *,
    settings: Settings | None = None,
) -> list[CampaignCreate]:
    service, customer_id = _google_ads_service(settings)

    try:
        rows = service.search(customer_id=customer_id, query=_campaigns_query())
        return [
            CampaignCreate(
                account_id=account_id,
                platform=AdvertisingPlatform.GOOGLE_ADS,
                external_campaign_id=str(row.campaign.id),
                name=row.campaign.name,
                status=str(row.campaign.status.name),
                channel_type=str(row.campaign.advertising_channel_type.name),
            )
            for row in rows
        ]
    except Exception as exc:
        _raise_normalized_google_ads_error(exc)


def collect_ad_groups(
    campaign_ids_by_external_id: dict[str, int],
    *,
    settings: Settings | None = None,
) -> list[AdGroupCreate]:
    service, customer_id = _google_ads_service(settings)

    try:
        rows = service.search(customer_id=customer_id, query=_ad_groups_query())
        return [
            AdGroupCreate(
                campaign_id=campaign_ids_by_external_id[str(row.campaign.id)],
                platform=AdvertisingPlatform.GOOGLE_ADS,
                external_ad_group_id=str(row.ad_group.id),
                name=row.ad_group.name,
                status=str(row.ad_group.status.name),
            )
            for row in rows
            if str(row.campaign.id) in campaign_ids_by_external_id
        ]
    except Exception as exc:
        _raise_normalized_google_ads_error(exc)


def collect_ads(
    ad_group_ids_by_external_id: dict[str, int],
    *,
    settings: Settings | None = None,
) -> list[AdCreate]:
    service, customer_id = _google_ads_service(settings)

    try:
        rows = service.search(customer_id=customer_id, query=_ads_query())
        return [
            AdCreate(
                ad_group_id=ad_group_ids_by_external_id[str(row.ad_group.id)],
                platform=AdvertisingPlatform.GOOGLE_ADS,
                external_ad_id=str(row.ad_group_ad.ad.id),
                name=row.ad_group_ad.ad.name or str(row.ad_group_ad.ad.id),
                status=str(row.ad_group_ad.status.name),
            )
            for row in rows
            if str(row.ad_group.id) in ad_group_ids_by_external_id
        ]
    except Exception as exc:
        _raise_normalized_google_ads_error(exc)


def collect_keywords(
    ad_group_ids_by_external_id: dict[str, int],
    *,
    settings: Settings | None = None,
) -> list[KeywordCreate]:
    service, customer_id = _google_ads_service(settings)

    try:
        rows = service.search(customer_id=customer_id, query=_keywords_query())
        return [
            KeywordCreate(
                ad_group_id=ad_group_ids_by_external_id[str(row.ad_group.id)],
                platform=AdvertisingPlatform.GOOGLE_ADS,
                external_keyword_id=str(row.ad_group_criterion.criterion_id),
                text=row.ad_group_criterion.keyword.text,
                match_type=str(row.ad_group_criterion.keyword.match_type.name),
                status=str(row.ad_group_criterion.status.name),
            )
            for row in rows
            if str(row.ad_group.id) in ad_group_ids_by_external_id
        ]
    except Exception as exc:
        _raise_normalized_google_ads_error(exc)


def collect_search_terms(
    ad_group_ids_by_external_id: dict[str, int],
    date_range: GoogleAdsDateRange,
    *,
    today: date | None = None,
    settings: Settings | None = None,
) -> list[SearchTermCreate]:
    service, customer_id = _google_ads_service(settings)
    window = _resolve_date_range(date_range, today)

    try:
        rows = service.search(customer_id=customer_id, query=_search_terms_query(window))
        return [
            SearchTermCreate(
                ad_group_id=ad_group_ids_by_external_id[str(row.ad_group.id)],
                platform=AdvertisingPlatform.GOOGLE_ADS,
                term=row.search_term_view.search_term,
                match_type=str(row.segments.keyword.info.match_type.name),
            )
            for row in rows
            if str(row.ad_group.id) in ad_group_ids_by_external_id
        ]
    except Exception as exc:
        _raise_normalized_google_ads_error(exc)


def collect_metrics(
    campaign_ids_by_external_id: dict[str, int],
    date_range: GoogleAdsDateRange,
    *,
    today: date | None = None,
    settings: Settings | None = None,
) -> NormalizedMetricsBatch:
    service, customer_id = _google_ads_service(settings)
    window = _resolve_date_range(date_range, today)

    try:
        rows = service.search(customer_id=customer_id, query=_metrics_query(window))
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
            for row in rows
            if str(row.campaign.id) in campaign_ids_by_external_id
        ]
    except Exception as exc:
        _raise_normalized_google_ads_error(exc)
    return NormalizedMetricsBatch(metrics=metrics)
