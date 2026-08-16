from collections.abc import Generator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from sqlite3 import Connection as SQLiteConnection

import pytest
from app.ads.enums import AdvertisingPlatform, JobRunStatus, MetricEntityType
from app.ads.models import (
    AdGroup,
    AdvertisingAccount,
    Campaign,
    DailyMetric,
    JobRun,
    Keyword,
    SearchTerm,
)
from app.analysis.query_performance import (
    QueryPerformanceService,
    generate_query_findings,
)
from app.api.auth import require_api_token
from app.collectors import google_ads
from app.dashboard.auth import require_dashboard_session
from app.database.session import Base, get_db
from app.main import app
from app.optimizer.analytics import MetricWindow
from app.settings import settings
from app.workspaces.models import Workspace
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import ConnectionPoolEntry, StaticPool


def enable_foreign_keys(
    dbapi_connection: SQLiteConnection,
    _connection_record: ConnectionPoolEntry,
) -> None:
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


@pytest.fixture()
def database() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    event.listen(engine, "connect", enable_foreign_keys)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def add_metric_days(
    db: Session,
    *,
    campaign: Campaign,
    ad_group: AdGroup,
    entity_type: MetricEntityType,
    entity_id: int,
    current_cost_micros: int,
    comparison_cost_micros: int,
    current_impressions: int = 1_200,
    comparison_impressions: int = 600,
    current_clicks: int = 35,
    conversions: Decimal = Decimal("0"),
) -> None:
    for day_offset in range(3):
        scope: dict[str, int | None] = {
            "keyword_id": entity_id if entity_type is MetricEntityType.KEYWORD else None,
            "search_term_id": (
                entity_id if entity_type is MetricEntityType.SEARCH_TERM else None
            ),
        }
        db.add(
            DailyMetric(
                platform=campaign.platform,
                metric_date=date(2026, 8, 5) + timedelta(days=day_offset),
                entity_type=entity_type.value,
                entity_id=entity_id,
                campaign_id=campaign.id,
                ad_group_id=ad_group.id,
                impressions=current_impressions // 3,
                clicks=current_clicks // 3 + (1 if day_offset == 0 else 0),
                cost_micros=current_cost_micros // 3,
                conversions=conversions / Decimal("3"),
                conversion_value_micros=0,
                **scope,
            )
        )
        db.add(
            DailyMetric(
                platform=campaign.platform,
                metric_date=date(2026, 8, 2) + timedelta(days=day_offset),
                entity_type=entity_type.value,
                entity_id=entity_id,
                campaign_id=campaign.id,
                ad_group_id=ad_group.id,
                impressions=comparison_impressions // 3,
                clicks=10,
                cost_micros=comparison_cost_micros // 3,
                conversions=Decimal("1") / Decimal("3"),
                conversion_value_micros=1_000_000,
                **scope,
            )
        )


def seed(db: Session) -> dict[str, int | str]:
    workspace = Workspace(
        slug="denticode",
        name="Denticode Ad Analyzer",
        client_name="Denticode",
        status="active",
        is_default=True,
    )
    db.add(workspace)
    db.flush()
    account = AdvertisingAccount(
        workspace_id=workspace.id,
        platform=AdvertisingPlatform.GOOGLE_ADS,
        external_account_id="query-analysis-account",
        name="Denticode Search",
        currency_code="USD",
        time_zone="UTC",
    )
    campaign = Campaign(
        account=account,
        platform=AdvertisingPlatform.GOOGLE_ADS,
        external_campaign_id="query-analysis-campaign",
        name="Implants",
        status="ENABLED",
        channel_type="SEARCH",
    )
    ad_group = AdGroup(
        campaign=campaign,
        platform=AdvertisingPlatform.GOOGLE_ADS,
        external_ad_group_id="query-analysis-group",
        name="Implants Exact",
        status="ENABLED",
    )
    keyword = Keyword(
        ad_group=ad_group,
        platform=AdvertisingPlatform.GOOGLE_ADS,
        external_keyword_id="keyword-one",
        text="dental implants",
        match_type="EXACT",
        status="ENABLED",
    )
    expensive_keyword = Keyword(
        ad_group=ad_group,
        platform=AdvertisingPlatform.GOOGLE_ADS,
        external_keyword_id="keyword-two",
        text="implant dentist",
        match_type="PHRASE",
        status="ENABLED",
    )
    sensitive_text = "sensitive patient treatment query"
    search_term = SearchTerm(
        ad_group=ad_group,
        platform=AdvertisingPlatform.GOOGLE_ADS,
        term=sensitive_text,
        match_type="EXACT",
    )
    low_spend_term = SearchTerm(
        ad_group=ad_group,
        platform=AdvertisingPlatform.GOOGLE_ADS,
        term="another confidential query",
        match_type="BROAD",
    )
    db.add_all([keyword, expensive_keyword, search_term, low_spend_term])
    db.flush()
    add_metric_days(
        db,
        campaign=campaign,
        ad_group=ad_group,
        entity_type=MetricEntityType.KEYWORD,
        entity_id=keyword.id,
        current_cost_micros=6_000_000,
        comparison_cost_micros=3_000_000,
    )
    add_metric_days(
        db,
        campaign=campaign,
        ad_group=ad_group,
        entity_type=MetricEntityType.KEYWORD,
        entity_id=expensive_keyword.id,
        current_cost_micros=9_000_000,
        comparison_cost_micros=9_000_000,
        conversions=Decimal("3"),
    )
    add_metric_days(
        db,
        campaign=campaign,
        ad_group=ad_group,
        entity_type=MetricEntityType.SEARCH_TERM,
        entity_id=search_term.id,
        current_cost_micros=7_000_000,
        comparison_cost_micros=3_000_000,
    )
    add_metric_days(
        db,
        campaign=campaign,
        ad_group=ad_group,
        entity_type=MetricEntityType.SEARCH_TERM,
        entity_id=low_spend_term.id,
        current_cost_micros=900_000,
        comparison_cost_micros=900_000,
        current_impressions=90,
        comparison_impressions=90,
        current_clicks=3,
    )
    db.add(
        JobRun(
            workspace_id=workspace.id,
            platform=account.platform,
            account_id=account.id,
            job_name="google_ads_read_only_sync",
            status=JobRunStatus.SUCCEEDED,
            started_at=datetime(2026, 8, 8, 8, tzinfo=UTC),
            finished_at=datetime(2026, 8, 8, 8, tzinfo=UTC),
            records_processed=20,
        )
    )
    db.commit()
    return {
        "workspace_id": workspace.id,
        "campaign_id": campaign.id,
        "ad_group_id": ad_group.id,
        "keyword_id": keyword.id,
        "expensive_keyword_id": expensive_keyword.id,
        "search_term_id": search_term.id,
        "sensitive_text": sensitive_text,
    }


def make_client(db: Session) -> TestClient:
    def override_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[require_api_token] = lambda: None
    app.dependency_overrides[require_dashboard_session] = lambda: None
    return TestClient(app, base_url="https://testserver")


def test_query_findings_use_numeric_thresholds_and_platform_diagnostics() -> None:
    current = MetricWindow(
        date_from=date(2026, 8, 5),
        date_to=date(2026, 8, 7),
        window_days=3,
        days_with_metric_rows=3,
        impressions=1_200,
        clicks=35,
        cost_micros=6_000_000,
        conversions=Decimal("0"),
        conversion_value_micros=0,
    )
    comparison = MetricWindow(
        date_from=date(2026, 8, 2),
        date_to=date(2026, 8, 4),
        window_days=3,
        days_with_metric_rows=3,
        impressions=600,
        clicks=30,
        cost_micros=3_000_000,
        conversions=Decimal("1"),
        conversion_value_micros=1_000_000,
    )
    findings = generate_query_findings(
        MetricEntityType.SEARCH_TERM,
        current,
        comparison,
        last_success_at=datetime(2026, 8, 8, tzinfo=UTC),
        now=datetime(2026, 8, 8, 12, tzinfo=UTC),
    )

    assert [finding.code for finding in findings] == [
        "spend_without_platform_conversions",
        "unusual_spend_change",
        "unusual_traffic_change",
    ]
    assert [finding.severity for finding in findings] == ["high", "medium", "medium"]
    rendered = str(findings).lower()
    assert "negative keyword" not in rendered
    assert "authoritative" not in rendered


def test_api_is_spend_sorted_paginated_read_only_and_search_text_redacted(
    database: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ids = seed(database)
    sensitive_text = str(ids["sensitive_text"])
    collected = False

    def fail_collector(*_args: object, **_kwargs: object) -> object:
        nonlocal collected
        collected = True
        raise AssertionError("read-only analysis must not invoke collectors")

    monkeypatch.setattr(google_ads, "collect_account", fail_collector)
    statements: list[str] = []

    def capture_sql(
        _conn: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: object,
    ) -> None:
        statements.append(statement.strip().upper())

    event.listen(database.get_bind(), "before_cursor_execute", capture_sql)
    client = make_client(database)
    try:
        first_keyword = client.get(
            f"/api/v1/ad-groups/{ids['ad_group_id']}/keyword-performance"
            "?date_from=2026-08-05&date_to=2026-08-07&limit=1"
        )
        second_keyword = client.get(
            f"/api/v1/ad-groups/{ids['ad_group_id']}/keyword-performance"
            "?date_from=2026-08-05&date_to=2026-08-07&limit=1&offset=1"
        )
        search_terms = client.get(
            f"/api/v1/ad-groups/{ids['ad_group_id']}/search-term-performance"
            "?date_from=2026-08-05&date_to=2026-08-07"
        )
        maximum_limit = client.get(
            f"/api/v1/ad-groups/{ids['ad_group_id']}/search-term-performance?limit=100"
        )
        invalid_limit = client.get(
            f"/api/v1/ad-groups/{ids['ad_group_id']}/search-term-performance?limit=101"
        )
    finally:
        event.remove(database.get_bind(), "before_cursor_execute", capture_sql)
        app.dependency_overrides.clear()

    assert first_keyword.status_code == 200
    assert first_keyword.json()["total"] == 2
    assert first_keyword.json()["items"][0]["entity_id"] == ids["expensive_keyword_id"]
    assert second_keyword.json()["items"][0]["entity_id"] == ids["keyword_id"]
    assert maximum_limit.status_code == 200
    assert invalid_limit.status_code == 422
    search_payload = search_terms.json()
    assert search_payload["total"] == 2
    assert search_payload["items"][0]["entity_id"] == ids["search_term_id"]
    assert search_payload["items"][0]["display_label"].startswith("Search term #")
    assert search_payload["items"][0]["source_text_redacted"] is True
    assert "spend_without_platform_conversions" in {
        finding["code"] for finding in search_payload["items"][0]["findings"]
    }
    assert {
        "impressions",
        "clicks",
        "click_through_rate",
        "cost_micros",
        "average_cpc_micros",
        "platform_conversions",
        "platform_conversion_rate",
        "cost_per_platform_conversion_micros",
        "platform_conversion_value_micros",
        "platform_roas",
    }.issubset(search_payload["items"][0]["current"])
    assert sensitive_text not in search_terms.text
    assert "another confidential query" not in search_terms.text
    assert not collected
    assert not any(
        statement.startswith(("INSERT", "UPDATE", "DELETE")) for statement in statements
    )
    assert not any("SEARCH_TERMS.TERM" in statement for statement in statements)


def test_dashboard_masks_search_terms_and_counts_workspace_findings(
    database: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ids = seed(database)
    monkeypatch.setattr(settings, "app_env", "development")
    client = make_client(database)
    try:
        page = client.get(
            f"/dashboard/ad-groups/{ids['ad_group_id']}"
            "?date_from=2026-08-05&date_to=2026-08-07"
        )
    finally:
        app.dependency_overrides.clear()

    assert page.status_code == 200
    assert "Keyword performance" in page.text
    assert "Search-term performance" in page.text
    assert "Platform conversion value" in page.text
    assert "Platform ROAS" in page.text
    assert "Search term #" in page.text
    assert str(ids["sensitive_text"]) not in page.text
    assert "negative-keyword instructions" in page.text
    counts = QueryPerformanceService(database).count_workspace_findings(
        int(ids["workspace_id"]),
        date(2026, 8, 5),
        date(2026, 8, 7),
        now=datetime(2026, 8, 8, 12, tzinfo=UTC),
    )
    assert counts.keyword_findings_count >= 2
    assert counts.search_term_findings_count >= 3
    assert counts.high_severity_findings_count >= 2


def test_workspace_finding_counts_do_not_cross_workspace_boundaries(database: Session) -> None:
    ids = seed(database)
    service = QueryPerformanceService(database)
    before = service.count_workspace_findings(
        int(ids["workspace_id"]),
        date(2026, 8, 5),
        date(2026, 8, 7),
        now=datetime(2026, 8, 8, 12, tzinfo=UTC),
    )

    other_workspace = Workspace(
        slug="other-client",
        name="Other Client Analyzer",
        client_name="Other Client",
        status="active",
    )
    database.add(other_workspace)
    database.flush()
    other_account = AdvertisingAccount(
        workspace_id=other_workspace.id,
        platform=AdvertisingPlatform.GOOGLE_ADS,
        external_account_id="other-query-account",
        name="Other Search",
        currency_code="USD",
        time_zone="UTC",
    )
    other_campaign = Campaign(
        account=other_account,
        platform=AdvertisingPlatform.GOOGLE_ADS,
        external_campaign_id="other-query-campaign",
        name="Other Campaign",
    )
    other_group = AdGroup(
        campaign=other_campaign,
        platform=AdvertisingPlatform.GOOGLE_ADS,
        external_ad_group_id="other-query-group",
        name="Other Group",
    )
    other_term = SearchTerm(
        ad_group=other_group,
        platform=AdvertisingPlatform.GOOGLE_ADS,
        term="other workspace private query",
    )
    database.add(other_term)
    database.flush()
    add_metric_days(
        database,
        campaign=other_campaign,
        ad_group=other_group,
        entity_type=MetricEntityType.SEARCH_TERM,
        entity_id=other_term.id,
        current_cost_micros=8_000_000,
        comparison_cost_micros=3_000_000,
    )
    database.add(
        JobRun(
            workspace_id=other_workspace.id,
            platform=other_account.platform,
            account_id=other_account.id,
            job_name="google_ads_read_only_sync",
            status=JobRunStatus.SUCCEEDED,
            started_at=datetime(2026, 8, 8, 8, tzinfo=UTC),
            finished_at=datetime(2026, 8, 8, 8, tzinfo=UTC),
            records_processed=10,
        )
    )
    database.commit()

    after = service.count_workspace_findings(
        int(ids["workspace_id"]),
        date(2026, 8, 5),
        date(2026, 8, 7),
        now=datetime(2026, 8, 8, 12, tzinfo=UTC),
    )
    other = service.count_workspace_findings(
        other_workspace.id,
        date(2026, 8, 5),
        date(2026, 8, 7),
        now=datetime(2026, 8, 8, 12, tzinfo=UTC),
    )

    assert after == before
    assert other.search_term_findings_count > 0
    assert other.keyword_findings_count == 0


def test_query_analysis_source_never_selects_raw_search_term_text() -> None:
    from pathlib import Path

    source = Path("app/analysis/query_performance.py").read_text()
    schema = Path("app/analysis/schemas.py").read_text()

    assert "SearchTerm.term" not in source
    assert "term: str" not in schema
    assert "negative_keyword" not in source
