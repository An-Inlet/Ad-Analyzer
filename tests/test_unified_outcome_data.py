from collections.abc import Generator
from datetime import UTC, date, datetime
from decimal import Decimal
from importlib import import_module
from sqlite3 import Connection as SQLiteConnection

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import ConnectionPoolEntry, StaticPool

from app.ads.enums import AdvertisingPlatform
from app.ads.models import AdGroup, AdvertisingAccount, Campaign, DailyMetric
from app.crm.models import CrmConnection
from app.crm.schemas import CrmEvent
from app.crm.worker import CrmEventProcessor
from app.database.session import Base, get_db
from app.main import app
from app.measurement.ingestion import Ga4EventCreate, WebAnalyticsRepository
from app.measurement.models import (
    MeasurementContract,
    MeasurementEventMapping,
    MeasurementStageDefinition,
    WebAnalyticsEvent,
)
from app.measurement.unified import UnifiedOutcomeService
from app.settings import settings
from app.workspaces.models import Workspace


def enable_sqlite_foreign_keys(
    dbapi_connection: SQLiteConnection, _connection_record: ConnectionPoolEntry
) -> None:
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    event.listen(engine, "connect", enable_sqlite_foreign_keys)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def seed_workspace(
    db: Session,
    slug: str,
    *,
    contract_status: str = "active",
    maturity_days: int = 30,
    click_lookback_days: int = 90,
    value_horizon_days: int = 365,
) -> tuple[Workspace, AdvertisingAccount, Campaign]:
    workspace = Workspace(
        slug=slug,
        name=f"{slug.title()} Ad Analyzer",
        client_name=slug.title(),
        status="active",
        is_default=slug == "denticode",
    )
    db.add(workspace)
    db.flush()
    contract = MeasurementContract(
        workspace_id=workspace.id,
        version=1,
        status=contract_status,
        effective_at=(
            datetime(2026, 1, 1, tzinfo=UTC) if contract_status == "active" else None
        ),
        currency_code="USD",
        source_of_truth="crm",
        platform_conversion_role="diagnostic_only",
        attribution_model="last_eligible_paid_touch",
        click_lookback_days=click_lookback_days,
        engaged_view_lookback_days=0,
        outcome_maturity_days=maturity_days,
        customer_value_mode="observed_revenue_only",
        customer_value_horizon_days=value_horizon_days,
        optimization_goal_stage_key="qualified_lead",
        business_value_stage_key="sale",
    )
    db.add(contract)
    db.flush()
    stages = [
        ("lead", "Lead", 10, "leading_indicator", False),
        ("qualified_lead", "Qualified lead", 20, "optimization_outcome", False),
        ("sale", "Sale", 30, "business_outcome", True),
        ("revenue_adjustment", "Revenue adjustment", 40, "value_adjustment", True),
        ("cancelled", "Cancelled", 90, "negative_outcome", False),
    ]
    db.add_all(
        [
            MeasurementStageDefinition(
                workspace_id=workspace.id,
                stage_key=stage_key,
                display_name=display_name,
                position=position,
                category=category,
                counts_toward_funnel=category not in {"value_adjustment", "negative_outcome"},
                accepts_monetary_value=accepts_value,
                description=f"Definition for {display_name}.",
            )
            for stage_key, display_name, position, category, accepts_value in stages
        ]
    )
    db.flush()
    mappings = [
        ("lead_created", "lead", "ignore"),
        ("lead_qualified", "qualified_lead", "ignore"),
        ("sale_won", "sale", "set"),
        ("revenue_adjusted", "revenue_adjustment", "adjust"),
        ("sale_cancelled", "cancelled", "adjust"),
    ]
    db.add_all(
        [
            MeasurementEventMapping(
                workspace_id=workspace.id,
                event_source="crm",
                source_event_type=event_type,
                stage_key=stage_key,
                authority="authoritative",
                value_behavior=value_behavior,
            )
            for event_type, stage_key, value_behavior in mappings
        ]
    )
    account = AdvertisingAccount(
        workspace_id=workspace.id,
        platform=AdvertisingPlatform.GOOGLE_ADS,
        external_account_id=f"{slug}-account",
        name=f"{slug.title()} Google Ads",
        currency_code="USD",
    )
    db.add(account)
    db.flush()
    campaign = Campaign(
        account_id=account.id,
        platform=AdvertisingPlatform.GOOGLE_ADS,
        external_campaign_id=f"{slug}-campaign",
        name=f"{slug.title()} Search",
        status="ENABLED",
        channel_type="SEARCH",
    )
    db.add(campaign)
    db.flush()
    db.add(
        CrmConnection(
            workspace_id=workspace.id,
            name="primary",
            status="active",
            secret_manager_reference=f"projects/example/secrets/{slug}-crm",
        )
    )
    db.commit()
    return workspace, account, campaign


def ga4_event(
    workspace: Workspace,
    account: AdvertisingAccount,
    campaign: Campaign,
    *,
    event_id: str = "ga4-event-1",
    occurred_at: datetime = datetime(2026, 6, 10, 12, tzinfo=UTC),
    subject_id: str = "practice-pseudo-001",
    session_id: str = "session-001",
    gclid: str = "paid-click-001",
    event_name: str = "session_start",
    ad_group: AdGroup | None = None,
) -> Ga4EventCreate:
    return Ga4EventCreate(
        workspace_id=workspace.id,
        external_event_id=event_id,
        event_name=event_name,
        occurred_at=occurred_at,
        user_pseudo_id="ga4-user-001",
        session_id=session_id,
        analytics_pseudonymous_id=subject_id,
        gclid=gclid,
        account_id=account.id,
        campaign_id=campaign.id,
        ad_group_id=ad_group.id if ad_group is not None else None,
        source="Google",
        medium="CPC",
        device_category="desktop",
        country_code="US",
        region_code="US-WA",
        landing_page_path="/book-demo",
        is_paid_touchpoint=True,
    )


def add_metric(
    db: Session,
    campaign: Campaign,
    *,
    metric_date: date = date(2026, 6, 10),
    impressions: int = 1_000,
    clicks: int = 100,
    cost_micros: int = 10_000_000,
    conversions: Decimal = Decimal("0"),
    conversion_value_micros: int = 0,
    ad_group: AdGroup | None = None,
) -> None:
    db.add(
        DailyMetric(
            platform=AdvertisingPlatform.GOOGLE_ADS,
            metric_date=metric_date,
            entity_type="ad_group" if ad_group is not None else "campaign",
            entity_id=ad_group.id if ad_group is not None else campaign.id,
            campaign_id=campaign.id,
            ad_group_id=ad_group.id if ad_group is not None else None,
            impressions=impressions,
            clicks=clicks,
            cost_micros=cost_micros,
            conversions=conversions,
            conversion_value_micros=conversion_value_micros,
        )
    )
    db.commit()


def process_crm_event(
    db: Session,
    workspace: Workspace,
    *,
    event_id: str,
    event_type: str,
    occurred_at: datetime,
    lead_id: str = "lead-001",
    subject_id: str = "practice-pseudo-001",
    gclid: str | None = "paid-click-001",
    value: str | None = None,
    currency: str | None = None,
) -> None:
    payload: dict[str, object] = {
        "workspace_id": workspace.id,
        "payload_version": 1,
        "event_id": event_id,
        "event_type": event_type,
        "occurred_at": occurred_at.isoformat(),
        "crm_lead_id": lead_id,
        "analytics_pseudonymous_id": subject_id,
    }
    if gclid is not None:
        payload["gclid"] = gclid
    if value is not None:
        payload["value"] = value
    if currency is not None:
        payload["currency"] = currency
    assert CrmEventProcessor(db).process(payload) is True


def add_complete_journey(
    db: Session,
    workspace: Workspace,
    *,
    lead_id: str = "lead-001",
    subject_id: str = "practice-pseudo-001",
    gclid: str = "paid-click-001",
) -> None:
    process_crm_event(
        db,
        workspace,
        event_id=f"{lead_id}-lead",
        event_type="lead_created",
        occurred_at=datetime(2026, 6, 11, 12, tzinfo=UTC),
        lead_id=lead_id,
        subject_id=subject_id,
        gclid=gclid,
    )
    process_crm_event(
        db,
        workspace,
        event_id=f"{lead_id}-qualified",
        event_type="lead_qualified",
        occurred_at=datetime(2026, 6, 20, 12, tzinfo=UTC),
        lead_id=lead_id,
        subject_id=subject_id,
        gclid=None,
    )
    process_crm_event(
        db,
        workspace,
        event_id=f"{lead_id}-sale",
        event_type="sale_won",
        occurred_at=datetime(2026, 7, 5, 12, tzinfo=UTC),
        lead_id=lead_id,
        subject_id=subject_id,
        gclid=None,
        value="500.00",
        currency="USD",
    )


def test_ga4_ingestion_hashes_identifiers_and_is_idempotent(db: Session) -> None:
    workspace, account, campaign = seed_workspace(db, "denticode")
    raw = ga4_event(workspace, account, campaign)
    repository = WebAnalyticsRepository(db)

    record, created = repository.record_ga4_event(raw)
    db.commit()
    duplicate, duplicate_created = repository.record_ga4_event(raw)

    assert created is True and duplicate_created is False
    assert duplicate.id == record.id
    assert record.user_pseudo_id_digest != raw.user_pseudo_id
    assert record.subject_id_digest != raw.analytics_pseudonymous_id
    assert record.session_id_digest != raw.session_id
    assert record.click_id_digest != raw.gclid
    stored_text = " ".join(str(value) for value in vars(record).values())
    for secret_value in (
        raw.user_pseudo_id,
        raw.analytics_pseudonymous_id,
        raw.session_id,
        raw.gclid,
    ):
        assert secret_value is not None and secret_value not in stored_text

    conflicting = raw.model_copy(update={"event_name": "page_view"})
    with pytest.raises(ValueError, match="conflicting web analytics event"):
        repository.record_ga4_event(conflicting)


def test_ga4_ingestion_rejects_query_strings_phi_like_ids_and_cross_workspace_scope(
    db: Session,
) -> None:
    workspace, account, campaign = seed_workspace(db, "denticode")
    other, _other_account, _other_campaign = seed_workspace(db, "second")
    base = ga4_event(workspace, account, campaign).model_dump()
    with pytest.raises(ValidationError):
        Ga4EventCreate.model_validate({**base, "landing_page_path": "/demo?email=a@b.test"})
    with pytest.raises(ValidationError):
        Ga4EventCreate.model_validate(
            {**base, "analytics_pseudonymous_id": "person@example.test"}
        )
    with pytest.raises(ValidationError):
        Ga4EventCreate.model_validate({**base, "source": "person@example.test"})
    with pytest.raises(ValidationError):
        Ga4EventCreate.model_validate({**base, "gclid": "person@example.test"})
    cross_workspace = ga4_event(other, account, campaign, event_id="cross-workspace")
    with pytest.raises(ValueError, match="outside the workspace"):
        WebAnalyticsRepository(db).record_ga4_event(cross_workspace)

    other_campaign = Campaign(
        account_id=account.id,
        platform=AdvertisingPlatform.GOOGLE_ADS,
        external_campaign_id="other-campaign",
        name="Other campaign",
    )
    db.add(other_campaign)
    db.flush()
    other_group = AdGroup(
        campaign_id=other_campaign.id,
        platform=AdvertisingPlatform.GOOGLE_ADS,
        external_ad_group_id="other-group",
        name="Other group",
    )
    db.add(other_group)
    db.flush()
    cross_group = Ga4EventCreate.model_validate(
        {
            **base,
            "external_event_id": "cross-group",
            "ad_group_id": other_group.id,
        }
    )
    with pytest.raises(ValueError, match="outside the campaign"):
        WebAnalyticsRepository(db).record_ga4_event(cross_group)


def test_crm_schema_accepts_only_safe_pseudonymous_correlation_id() -> None:
    valid = CrmEvent.model_validate(
        {
            "event_id": "crm-event-1",
            "event_type": "lead_created",
            "occurred_at": "2026-06-11T12:00:00Z",
            "crm_lead_id": "lead-001",
            "analytics_pseudonymous_id": "practice-pseudo-001",
        }
    )
    assert valid.analytics_pseudonymous_id == "practice-pseudo-001"
    with pytest.raises(ValidationError):
        CrmEvent.model_validate(
            {
                **valid.model_dump(mode="json"),
                "analytics_pseudonymous_id": "person@example.test",
            }
        )


def test_draft_contract_blocks_all_downstream_outcome_metrics(db: Session) -> None:
    workspace, account, campaign = seed_workspace(
        db, "denticode", contract_status="draft"
    )
    WebAnalyticsRepository(db).record_ga4_event(ga4_event(workspace, account, campaign))
    add_metric(db, campaign)
    add_complete_journey(db, workspace)

    report = UnifiedOutcomeService(db).report(
        workspace.id,
        date(2026, 6, 1),
        date(2026, 6, 30),
        as_of=datetime(2026, 8, 8, tzinfo=UTC),
    )

    assert report.analysis_ready is False
    assert report.blocking_reasons == ("measurement_contract_not_active",)
    assert report.totals is None
    assert report.campaigns == ()


def test_active_contract_correlates_google_ads_ga4_and_crm_value(db: Session) -> None:
    workspace, account, campaign = seed_workspace(db, "denticode")
    WebAnalyticsRepository(db).record_ga4_event(ga4_event(workspace, account, campaign))
    db.commit()
    add_metric(db, campaign)
    add_complete_journey(db, workspace)

    report = UnifiedOutcomeService(db).report(
        workspace.id,
        date(2026, 6, 1),
        date(2026, 6, 30),
        as_of=datetime(2026, 8, 8, tzinfo=UTC),
    )

    assert report.analysis_ready is True
    assert report.blocking_reasons == ()
    assert report.ad_group_analysis_ready is False
    assert "ad_group_metrics_missing" in report.ad_group_blocking_reasons
    assert "ad_group_paid_touchpoints_missing" in report.ad_group_blocking_reasons
    assert report.mature_through == date(2026, 6, 30)
    assert report.source_coverage.advertising_metric_days == 1
    assert report.source_coverage.attributed_journey_count == 1
    assert report.source_coverage.attribution_rate == Decimal("1.000000")
    assert report.totals is not None
    assert report.totals.impressions == 1_000
    assert report.totals.clicks == 100
    assert report.totals.lead_count == 1
    assert report.totals.optimization_outcome_count == 1
    assert report.totals.business_outcome_count == 1
    assert report.totals.observed_revenue_micros == 500_000_000
    assert report.totals.revenue_per_click_micros == 5_000_000
    assert report.totals.cost_per_optimization_outcome_micros == 10_000_000
    assert report.totals.business_outcome_rate == Decimal("1.000000")
    assert report.totals.funnel_drop_off_rate == Decimal("0.000000")
    assert report.totals.median_outcome_lag_days == Decimal("25.00")
    assert len(report.campaigns) == 1
    assert report.campaigns[0].campaign_id == campaign.id


def test_ad_group_outcomes_add_scope_without_double_counting_campaign_totals(
    db: Session,
) -> None:
    workspace, account, campaign = seed_workspace(db, "denticode")
    ad_group = AdGroup(
        campaign_id=campaign.id,
        platform=campaign.platform,
        external_ad_group_id="implants-exact",
        name="Implants exact",
        status="ENABLED",
    )
    db.add(ad_group)
    db.commit()
    WebAnalyticsRepository(db).record_ga4_event(
        ga4_event(workspace, account, campaign, ad_group=ad_group)
    )
    db.commit()
    add_metric(
        db,
        campaign,
        conversions=Decimal("3"),
        conversion_value_micros=600_000_000,
    )
    add_metric(
        db,
        campaign,
        impressions=600,
        clicks=60,
        cost_micros=6_000_000,
        conversions=Decimal("2"),
        conversion_value_micros=400_000_000,
        ad_group=ad_group,
    )
    add_complete_journey(db, workspace)

    report = UnifiedOutcomeService(db).report(
        workspace.id,
        date(2026, 6, 1),
        date(2026, 6, 30),
        as_of=datetime(2026, 8, 8, tzinfo=UTC),
    )

    assert report.analysis_ready is True
    assert report.ad_group_analysis_ready is True
    assert report.ad_group_blocking_reasons == ()
    assert report.source_coverage.ad_group_metric_days == 1
    assert report.source_coverage.ad_group_attributed_journey_count == 1
    assert report.source_coverage.ad_group_unattributed_journey_count == 0
    assert report.source_coverage.ad_group_attribution_rate == Decimal("1.000000")
    assert report.totals is not None
    assert report.totals.platform_conversion_count == Decimal("3.000000")
    assert report.totals.platform_conversion_value_micros == 600_000_000
    assert report.totals.click_through_rate == Decimal("0.100000")
    assert report.totals.platform_conversion_rate == Decimal("0.030000")
    assert report.totals.click_to_paid_session_rate == Decimal("0.010000")
    assert report.totals.paid_session_to_lead_rate == Decimal("1.000000")
    assert report.totals.cost_per_lead_micros == 10_000_000
    assert report.totals.observed_roas == Decimal("50.000000")
    assert len(report.campaigns[0].ad_groups) == 1
    scoped = report.campaigns[0].ad_groups[0]
    assert scoped.ad_group_id == ad_group.id
    assert scoped.metrics.clicks == 60
    assert scoped.metrics.platform_conversion_count == Decimal("2.000000")
    assert scoped.metrics.lead_count == 1
    assert scoped.metrics.observed_revenue_micros == 500_000_000
    assert scoped.metrics.cost_per_business_outcome_micros == 6_000_000


def test_last_eligible_paid_touch_selects_latest_campaign(db: Session) -> None:
    workspace, account, first_campaign = seed_workspace(db, "denticode")
    second_campaign = Campaign(
        account_id=account.id,
        platform=AdvertisingPlatform.GOOGLE_ADS,
        external_campaign_id="denticode-campaign-2",
        name="Denticode Retargeting",
        status="ENABLED",
        channel_type="DISPLAY",
    )
    db.add(second_campaign)
    db.commit()
    repository = WebAnalyticsRepository(db)
    repository.record_ga4_event(
        ga4_event(
            workspace,
            account,
            first_campaign,
            event_id="first-touch",
            occurred_at=datetime(2026, 6, 1, 12, tzinfo=UTC),
            session_id="session-first",
            gclid="click-first",
        )
    )
    repository.record_ga4_event(
        ga4_event(
            workspace,
            account,
            second_campaign,
            event_id="second-touch",
            occurred_at=datetime(2026, 6, 9, 12, tzinfo=UTC),
            session_id="session-second",
            gclid="click-second",
        )
    )
    db.commit()
    add_metric(db, first_campaign, metric_date=date(2026, 6, 1), clicks=20)
    add_metric(db, second_campaign, metric_date=date(2026, 6, 9), clicks=30)
    process_crm_event(
        db,
        workspace,
        event_id="latest-touch-lead",
        event_type="lead_created",
        occurred_at=datetime(2026, 6, 10, 12, tzinfo=UTC),
        gclid=None,
    )

    report = UnifiedOutcomeService(db).report(
        workspace.id,
        date(2026, 6, 1),
        date(2026, 6, 30),
        as_of=datetime(2026, 8, 8, tzinfo=UTC),
    )
    rows = {row.campaign_id: row.metrics for row in report.campaigns}

    assert rows[first_campaign.id].lead_count == 0
    assert rows[second_campaign.id].lead_count == 1


def test_outside_lookback_and_immature_cohorts_fail_closed(db: Session) -> None:
    workspace, account, campaign = seed_workspace(
        db,
        "denticode",
        click_lookback_days=5,
    )
    WebAnalyticsRepository(db).record_ga4_event(
        ga4_event(
            workspace,
            account,
            campaign,
            occurred_at=datetime(2026, 6, 1, 12, tzinfo=UTC),
        )
    )
    db.commit()
    add_metric(db, campaign, metric_date=date(2026, 6, 1))
    process_crm_event(
        db,
        workspace,
        event_id="outside-lookback",
        event_type="lead_created",
        occurred_at=datetime(2026, 6, 20, 12, tzinfo=UTC),
    )
    outside = UnifiedOutcomeService(db).report(
        workspace.id,
        date(2026, 6, 1),
        date(2026, 6, 30),
        as_of=datetime(2026, 8, 8, tzinfo=UTC),
    )
    immature = UnifiedOutcomeService(db).report(
        workspace.id,
        date(2026, 7, 20),
        date(2026, 7, 31),
        as_of=datetime(2026, 8, 8, tzinfo=UTC),
    )

    assert outside.analysis_ready is False
    assert "crm_attribution_missing" in outside.blocking_reasons
    assert outside.source_coverage.unattributed_journey_count == 1
    assert immature.analysis_ready is False
    assert immature.blocking_reasons == ("no_mature_cohort",)
    assert immature.totals is None


def test_revenue_adjustments_replace_value_and_cancellation_removes_sale(db: Session) -> None:
    workspace, account, campaign = seed_workspace(db, "denticode")
    WebAnalyticsRepository(db).record_ga4_event(ga4_event(workspace, account, campaign))
    db.commit()
    add_metric(db, campaign)
    add_complete_journey(db, workspace)
    process_crm_event(
        db,
        workspace,
        event_id="lead-001-adjusted",
        event_type="revenue_adjusted",
        occurred_at=datetime(2026, 7, 10, 12, tzinfo=UTC),
        gclid=None,
        value="650.00",
        currency="USD",
    )
    adjusted = UnifiedOutcomeService(db).report(
        workspace.id,
        date(2026, 6, 1),
        date(2026, 6, 30),
        as_of=datetime(2026, 8, 8, tzinfo=UTC),
    )
    assert adjusted.totals is not None
    assert adjusted.totals.observed_revenue_micros == 650_000_000

    process_crm_event(
        db,
        workspace,
        event_id="lead-001-cancelled",
        event_type="sale_cancelled",
        occurred_at=datetime(2026, 7, 15, 12, tzinfo=UTC),
        gclid=None,
    )
    cancelled = UnifiedOutcomeService(db).report(
        workspace.id,
        date(2026, 6, 1),
        date(2026, 6, 30),
        as_of=datetime(2026, 8, 8, tzinfo=UTC),
    )
    assert cancelled.totals is not None
    assert cancelled.totals.business_outcome_count == 0
    assert cancelled.totals.cancelled_outcome_count == 1
    assert cancelled.totals.observed_revenue_micros == 0


def test_currency_mismatch_and_value_horizon_fail_closed(db: Session) -> None:
    workspace, account, campaign = seed_workspace(
        db,
        "denticode",
        value_horizon_days=30,
    )
    WebAnalyticsRepository(db).record_ga4_event(ga4_event(workspace, account, campaign))
    db.commit()
    add_metric(db, campaign)
    process_crm_event(
        db,
        workspace,
        event_id="lead-in-window",
        event_type="lead_created",
        occurred_at=datetime(2026, 6, 11, 12, tzinfo=UTC),
    )
    process_crm_event(
        db,
        workspace,
        event_id="sale-outside-horizon",
        event_type="sale_won",
        occurred_at=datetime(2026, 7, 20, 12, tzinfo=UTC),
        gclid=None,
        value="500.00",
        currency="USD",
    )

    outside_horizon = UnifiedOutcomeService(db).report(
        workspace.id,
        date(2026, 6, 1),
        date(2026, 6, 30),
        as_of=datetime(2026, 8, 8, tzinfo=UTC),
    )
    assert outside_horizon.totals is not None
    assert outside_horizon.totals.business_outcome_count == 0
    assert outside_horizon.totals.observed_revenue_micros == 0

    process_crm_event(
        db,
        workspace,
        event_id="sale-currency-mismatch",
        event_type="sale_won",
        occurred_at=datetime(2026, 6, 25, 12, tzinfo=UTC),
        gclid=None,
        value="400.00",
        currency="CAD",
    )
    mismatch = UnifiedOutcomeService(db).report(
        workspace.id,
        date(2026, 6, 1),
        date(2026, 6, 30),
        as_of=datetime(2026, 8, 8, tzinfo=UTC),
    )
    assert mismatch.analysis_ready is False
    assert "crm_currency_mismatch" in mismatch.blocking_reasons
    assert mismatch.source_coverage.currency_mismatch_count == 1
    assert mismatch.totals is not None
    assert mismatch.totals.observed_revenue_micros == 0


def test_read_only_api_and_dashboard_expose_aggregates_not_identifiers(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, account, campaign = seed_workspace(db, "denticode")
    raw_event = ga4_event(workspace, account, campaign)
    WebAnalyticsRepository(db).record_ga4_event(raw_event)
    db.commit()
    add_metric(db, campaign)
    add_complete_journey(db, workspace)
    token = "u" * 48
    monkeypatch.setattr(settings, "denticode_api_token", SecretStr(token))
    monkeypatch.setattr(settings, "app_env", "development")

    def override_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app, base_url="https://testserver")
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get(
            "/api/v1/workspaces/denticode/outcome-analysis"
            "?date_from=2026-06-01&date_to=2026-06-30",
            headers=headers,
        )
        client.get("/dashboard", headers=headers)
        dashboard = client.get(
            "/dashboard/workspaces/denticode/outcomes"
            "?date_from=2026-06-01&date_to=2026-06-30"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["analysis_ready"] is True
    assert response.json()["totals"]["observed_revenue_micros"] == 500_000_000
    assert dashboard.status_code == 200
    assert "Unified outcome analysis" in dashboard.text
    for private_value in (
        raw_event.user_pseudo_id,
        raw_event.analytics_pseudonymous_id,
        raw_event.session_id,
        raw_event.gclid,
        "lead-001",
    ):
        assert private_value is not None
        assert private_value not in response.text
        assert private_value not in dashboard.text


def test_unified_data_migration_upgrades_and_reverses_on_disposable_schema() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    migration = import_module(
        "migrations.versions.20260808_0010_unified_outcome_data"
    )
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE workspaces (id INTEGER PRIMARY KEY)"))
        connection.execute(
            text(
                "CREATE TABLE advertising_accounts ("
                "id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL, "
                "UNIQUE(id, workspace_id))"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE campaigns ("
                "id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL, "
                "UNIQUE(id, account_id))"
            )
        )
        migration.__dict__["op"] = Operations(MigrationContext.configure(connection))

        migration.upgrade()
        tables = {
            row[0]
            for row in connection.execute(
                text("SELECT name FROM sqlite_master WHERE type = 'table'")
            )
        }
        assert "web_analytics_events" in tables

        migration.downgrade()
        tables = {
            row[0]
            for row in connection.execute(
                text("SELECT name FROM sqlite_master WHERE type = 'table'")
            )
        }
        assert "web_analytics_events" not in tables
    engine.dispose()


def test_unified_table_contains_only_digests_not_raw_identifier_columns() -> None:
    column_names = {column.name for column in WebAnalyticsEvent.__table__.columns}
    assert {
        "user_pseudo_id_digest",
        "subject_id_digest",
        "session_id_digest",
        "click_id_digest",
    }.issubset(column_names)
    assert {
        "user_pseudo_id",
        "analytics_pseudonymous_id",
        "session_id",
        "gclid",
        "gbraid",
        "wbraid",
        "raw_payload",
    }.isdisjoint(column_names)
    assert list(select(WebAnalyticsEvent).column_descriptions)[0]["entity"] is WebAnalyticsEvent
