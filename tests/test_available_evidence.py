from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from app.ads.enums import AdvertisingPlatform
from app.ads.models import AdGroup, AdvertisingAccount, Campaign, DailyMetric
from app.database.session import Base
from app.intelligence.availability import build_available_evidence
from app.meta.models import MetaConnection
from app.shopify.models import ShopifyConnection, ShopifyOrder
from app.workspaces.models import Workspace
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

NOW = datetime(2026, 9, 6, 12, tzinfo=UTC)


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def workspace(db: Session, name: str = "client") -> Workspace:
    row = Workspace(slug=name, name=name, client_name=name, status="active")
    db.add(row)
    db.flush()
    return row


def campaign(
    db: Session,
    owner: Workspace,
    platform: AdvertisingPlatform = AdvertisingPlatform.META_ADS,
    *,
    currency: str = "USD",
    time_zone: str | None = "UTC",
) -> Campaign:
    account = AdvertisingAccount(
        workspace_id=owner.id,
        platform=platform,
        external_account_id=f"local-{owner.id}-{currency}-{platform}",
        name=f"{platform.value} account",
        currency_code=currency,
        time_zone=time_zone,
    )
    db.add(account)
    db.flush()
    row = Campaign(
        account_id=account.id,
        platform=platform,
        external_campaign_id="local-campaign",
        name="Acquisition",
        status="ACTIVE",
    )
    db.add(row)
    db.flush()
    return row


def metrics(
    db: Session,
    owner: Campaign,
    *,
    first_day_ago: int = 56,
    last_day_ago: int = 1,
    **overrides: Any,
) -> None:
    for ago in range(last_day_ago, first_day_ago + 1):
        db.add(
            DailyMetric(
                platform=owner.platform,
                metric_date=NOW.date() - timedelta(days=ago),
                entity_type="campaign",
                entity_id=owner.id,
                campaign_id=owner.id,
                impressions=overrides.get("impressions", 1_000 if ago > 28 else 2_000),
                clicks=overrides.get("clicks", 20),
                cost_micros=overrides.get("cost_micros", 10_000_000 if ago > 28 else 20_000_000),
                conversions=Decimal("0"),
                conversion_value_micros=0,
            )
        )
    db.flush()


def completed_meta(db: Session, owner: Workspace, active: Campaign) -> MetaConnection:
    connection = MetaConnection(
        workspace_id=owner.id,
        account_id=active.account_id,
        external_account_id="12345678",
        encrypted_credentials="opaque-test-ciphertext",
        conversion_action_type="purchase",
        status="connected",
        last_sync_at=NOW - timedelta(hours=1),
        covered_from=NOW.date() - timedelta(days=56),
        covered_through=NOW.date() - timedelta(days=1),
    )
    db.add(connection)
    db.flush()
    return connection


@pytest.mark.parametrize("platform", list(AdvertisingPlatform))
def test_one_platform_is_useful_without_crm_analytics_or_contract(
    db: Session, platform: AdvertisingPlatform
) -> None:
    owner = workspace(db)
    active = campaign(db, owner, platform)
    metrics(db, active)
    report = build_available_evidence(db, owner.id, NOW)
    assert report["analysis_ready"]
    assert report["capabilities"]["platform_performance"]["ready"]
    assert not report["capabilities"]["attributed_outcomes"]["ready"]
    assert not report["capabilities"]["commerce"]["ready"]
    row = report["accounts"][0]
    assert row["current"]["cost_micros"] == 560_000_000
    assert row["current"]["revenue_micros"] is None
    assert row["comparison"]["ctr_change_ratio"] == -0.5
    assert row["comparison"]["cpc_change_ratio"] == 1
    assert len(report["recommendations"]) == 2
    assert all(r["confidence"] == "directional" for r in report["recommendations"])
    assert all(r["cost_change_micros"] == 0 for r in report["recommendations"])


def test_no_connections_leaves_planning_usable_without_inventing_metrics(db: Session) -> None:
    owner = workspace(db)
    report = build_available_evidence(db, owner.id, NOW)
    assert report["capabilities"]["planning"]["ready"]
    assert not report["analysis_ready"]
    assert report["accounts"] == []
    assert report["recommendations"] == []
    assert not report["commerce"]["connected"]


def test_missing_metrics_differ_from_observed_zero_and_today_is_excluded(db: Session) -> None:
    owner = workspace(db)
    active = campaign(db, owner)
    metrics(db, active, first_day_ago=0, last_day_ago=0)
    report = build_available_evidence(db, owner.id, NOW)
    assert report["accounts"][0]["current"] is None
    metrics(db, active, first_day_ago=28, impressions=0, clicks=0, cost_micros=0)
    report = build_available_evidence(db, owner.id, NOW)
    current = report["accounts"][0]["current"]
    assert current["impressions"] == current["clicks"] == current["cost_micros"] == 0
    assert current["ctr"] is None and current["cpc_micros"] is None
    assert current["complete"]
    assert report["accounts"][0]["previous"] is None
    assert report["recommendations"] == []


def test_only_campaign_grain_is_counted(db: Session) -> None:
    owner = workspace(db)
    active = campaign(db, owner, AdvertisingPlatform.GOOGLE_ADS)
    metrics(db, active, first_day_ago=1)
    group = AdGroup(
        campaign_id=active.id,
        platform=active.platform,
        external_ad_group_id="local-group",
        name="Local group",
    )
    db.add(group)
    db.flush()
    db.add(
        DailyMetric(
            platform=active.platform,
            campaign_id=active.id,
            ad_group_id=group.id,
            entity_id=group.id,
            entity_type="ad_group",
            metric_date=NOW.date() - timedelta(days=1),
            impressions=999_999,
            clicks=999,
            cost_micros=999_000_000,
        )
    )
    db.flush()
    current = build_available_evidence(db, owner.id, NOW)["accounts"][0]["current"]
    assert current["impressions"] == 2_000
    assert current["cost_micros"] == 20_000_000


def test_currencies_providers_and_workspaces_stay_separate(db: Session) -> None:
    owner, unrelated = workspace(db), workspace(db, "unrelated")
    usd = campaign(db, owner, AdvertisingPlatform.GOOGLE_ADS)
    eur = campaign(db, owner, AdvertisingPlatform.META_ADS, currency="EUR")
    other = campaign(db, unrelated)
    metrics(db, usd, first_day_ago=1, cost_micros=1_000_000)
    metrics(db, eur, first_day_ago=1, cost_micros=2_000_000)
    metrics(db, other, first_day_ago=56, cost_micros=9_000_000)
    report = build_available_evidence(db, owner.id, NOW)
    assert len(report["accounts"]) == 2
    assert {(r["platform"], r["currency_code"]) for r in report["accounts"]} == {
        ("google_ads", "USD"),
        ("meta_ads", "EUR"),
    }
    assert {r["current"]["cost_micros"] for r in report["accounts"]} == {1_000_000, 2_000_000}
    assert report["recommendations"] == []
    assert all(other.id != c["id"] for r in report["accounts"] for c in r["campaigns"])


def test_stale_or_sparse_history_never_produces_directional_advice(db: Session) -> None:
    owner = workspace(db)
    active = campaign(db, owner)
    metrics(db, active, last_day_ago=5)
    report = build_available_evidence(db, owner.id, NOW)
    assert report["accounts"][0]["status"] == "stale"
    assert not report["analysis_ready"]
    assert report["recommendations"] == []
    metrics(db, active, first_day_ago=1)
    report = build_available_evidence(db, owner.id, NOW)
    assert report["analysis_ready"]
    assert not report["accounts"][0]["comparison"]["ready"]
    assert report["recommendations"] == []


def test_missing_campaign_does_not_disable_other_campaigns(db: Session) -> None:
    owner = workspace(db)
    active = campaign(db, owner)
    metrics(db, active)
    db.add(
        Campaign(
            account_id=active.account_id,
            platform=active.platform,
            external_campaign_id="pending-import",
            name="Pending import",
        )
    )
    db.flush()
    report = build_available_evidence(db, owner.id, NOW)
    assert report["analysis_ready"]
    assert not report["accounts"][0]["comparison"]["ready"]
    assert report["accounts"][0]["campaigns"][1]["current"] is None
    assert len(report["recommendations"]) == 2


def test_zero_clicks_advice_requires_fresh_observations_and_never_claims_waste(db: Session) -> None:
    owner = workspace(db)
    active = campaign(db, owner)
    metrics(db, active, first_day_ago=7, clicks=0)
    report = build_available_evidence(db, owner.id, NOW)
    assert len(report["recommendations"]) == 1
    suggestion = report["recommendations"][0]
    assert suggestion["key"].endswith("no_clicks")
    assert "objective" in suggestion["action"]
    assert "waste" not in suggestion["title"]
    assert "CPA" not in str(report["recommendations"])


def test_unknown_timezone_withholds_directional_comparison(db: Session) -> None:
    owner = workspace(db)
    active = campaign(db, owner, time_zone=None)
    metrics(db, active)
    report = build_available_evidence(db, owner.id, NOW)
    assert report["accounts"][0]["current"]
    assert not report["accounts"][0]["comparison"]["ready"]
    assert report["recommendations"] == []


@pytest.mark.parametrize(
    ("selected", "covered_days", "synced", "current_available", "previous_available"),
    [
        (False, 56, True, False, False),
        (True, 56, False, False, False),
        (True, 7, True, False, False),
        (True, 28, True, True, False),
        (True, 56, True, True, True),
    ],
)
def test_meta_conversion_zero_is_only_observed_for_a_selected_imported_event(
    db: Session,
    selected: bool,
    covered_days: int,
    synced: bool,
    current_available: bool,
    previous_available: bool,
) -> None:
    owner = workspace(db)
    active = campaign(db, owner)
    metrics(db, active)
    db.add(
        MetaConnection(
            workspace_id=owner.id,
            account_id=active.account_id,
            external_account_id="12345678",
            encrypted_credentials="opaque-test-ciphertext",
            conversion_action_type="purchase" if selected else None,
            last_sync_at=NOW - timedelta(hours=1) if synced else None,
            covered_from=NOW.date() - timedelta(days=covered_days),
            covered_through=NOW.date() - timedelta(days=1),
        )
    )
    db.flush()
    account = build_available_evidence(db, owner.id, NOW)["accounts"][0]
    for key, available in (("current", current_available), ("previous", previous_available)):
        assert account[key]["platform_conversions_available"] is available
        assert account[key]["platform_conversions"] == (0.0 if available else None)
        assert account[key]["revenue_micros"] is None


def test_completed_window_uses_the_accounts_calendar_day(db: Session) -> None:
    owner = workspace(db)
    active = campaign(db, owner, time_zone="America/Los_Angeles")
    metrics(db, active, first_day_ago=2)
    report = build_available_evidence(db, owner.id, NOW.replace(hour=0))
    account = report["accounts"][0]
    assert account["window"]["end"] == "2026-09-04"
    assert account["current"]["observed_days"] == 1
    assert account["current"]["cost_micros"] == 20_000_000


def test_complete_sparse_meta_windows_certify_omitted_zero_delivery(db: Session) -> None:
    owner = workspace(db)
    active = campaign(db, owner)
    completed_meta(db, owner, active)
    metrics(db, active, first_day_ago=40, last_day_ago=40, clicks=100)
    metrics(db, active, first_day_ago=2, last_day_ago=2, clicks=100)
    report = build_available_evidence(db, owner.id, NOW)
    account = report["accounts"][0]
    assert account["comparison"]["ready"]
    assert account["campaigns"][0]["comparison"]["ready"]
    assert account["current"]["observed_days"] == 1
    assert account["current"]["covered_days"] == 28
    assert account["current"]["coverage_basis"] == "completed_meta_import"
    assert account["current"]["cost_micros"] == 20_000_000
    # Sparse delivery does not meet the seven observed delivery-day advice threshold.
    assert report["recommendations"] == []


def test_paused_meta_campaign_has_known_zero_in_completed_current_period(db: Session) -> None:
    owner = workspace(db)
    active = campaign(db, owner)
    active.status = "PAUSED"
    completed_meta(db, owner, active)
    metrics(db, active, first_day_ago=40, last_day_ago=40)
    report = build_available_evidence(db, owner.id, NOW)
    account = report["accounts"][0]
    current = account["campaigns"][0]["current"]
    assert report["analysis_ready"]
    assert current["complete"]
    assert current["observed_days"] == 0
    assert current["covered_days"] == 28
    assert current["last_metric_date"] is None
    assert current["cost_micros"] == current["clicks"] == current["impressions"] == 0
    assert current["ctr"] is None and current["cpc_micros"] is None
    assert account["campaigns"][0]["comparison"]["spend_change_ratio"] == -1
    assert report["recommendations"] == []


def test_new_meta_campaign_does_not_gain_an_invented_previous_lifetime(db: Session) -> None:
    owner = workspace(db)
    active = campaign(db, owner)
    completed_meta(db, owner, active)
    metrics(db, active, first_day_ago=2)
    account = build_available_evidence(db, owner.id, NOW)["accounts"][0]
    assert account["previous"]["cost_micros"] == 0
    assert account["previous"]["complete"]
    assert account["campaigns"][0]["previous"] is None
    assert not account["campaigns"][0]["comparison"]["ready"]
    assert "campaign age" in account["campaigns"][0]["comparison"]["reason"]


def test_meta_import_with_no_delivery_is_a_known_zero_account(db: Session) -> None:
    owner = workspace(db)
    active = campaign(db, owner)
    completed_meta(db, owner, active)
    report = build_available_evidence(db, owner.id, NOW)
    account = report["accounts"][0]
    assert report["analysis_ready"]
    assert account["current"]["cost_micros"] == 0
    assert account["current"]["complete"]
    assert account["current"]["observed_days"] == 0
    assert account["campaigns"][0]["current"] is None
    assert report["recommendations"] == []


@pytest.mark.parametrize("reset", [True, False])
def test_reconnect_and_stale_meta_imports_withhold_directional_advice(
    db: Session, reset: bool
) -> None:
    owner = workspace(db)
    active = campaign(db, owner)
    connection = completed_meta(db, owner, active)
    metrics(db, active)
    connection.last_sync_at = None if reset else NOW - timedelta(days=4)
    connection.status = "reconnect_required" if reset else "connected"
    db.flush()
    report = build_available_evidence(db, owner.id, NOW)
    assert report["accounts"][0]["status"] == "stale"
    assert not report["analysis_ready"]
    assert report["recommendations"] == []


def test_meta_refresh_keeps_completed_snapshot_coverage(db: Session) -> None:
    owner = workspace(db)
    active = campaign(db, owner)
    connection = completed_meta(db, owner, active)
    metrics(db, active, first_day_ago=40, last_day_ago=40)
    connection.window_start = NOW.date() - timedelta(days=55)
    connection.window_end = NOW.date()
    db.flush()
    account = build_available_evidence(db, owner.id, NOW)["accounts"][0]
    assert account["current"]["complete"]
    assert account["current"]["cost_micros"] == 0
    assert any("previous completed import" in reason for reason in account["limitations"])


def test_meta_lead_event_does_not_invent_reported_monetary_value(db: Session) -> None:
    owner = workspace(db)
    active = campaign(db, owner)
    connection = completed_meta(db, owner, active)
    connection.conversion_action_type = "lead"
    metrics(db, active)
    snapshot = build_available_evidence(db, owner.id, NOW)["accounts"][0]["current"]
    assert snapshot["platform_conversions_available"]
    assert snapshot["platform_conversions"] == 0
    assert not snapshot["platform_conversion_value_available"]
    assert snapshot["platform_conversion_value_micros"] is None


def test_shopify_only_is_ready_without_advertising_or_crm(db: Session) -> None:
    owner = workspace(db)
    connection = ShopifyConnection(
        workspace_id=owner.id,
        shop_domain="fixture.myshopify.com",
        shop_name="Fixture",
        currency_code="USD",
        time_zone="UTC",
        encrypted_credentials="opaque-test-ciphertext",
        status="connected",
        last_sync_at=NOW - timedelta(hours=1),
        covered_from=NOW - timedelta(days=60),
    )
    db.add(connection)
    db.flush()
    db.add(
        ShopifyOrder(
            connection_id=connection.id,
            workspace_id=owner.id,
            order_key="minimized-order",
            created_at=NOW - timedelta(days=2),
            source_updated_at=NOW - timedelta(days=1),
            currency_code="USD",
            net_collected_micros=100_000_000,
            refunded_micros=0,
            cancelled=False,
            customer_order_index=1,
            channel="direct",
            products_complete=True,
            products=[],
        )
    )
    db.flush()
    report = build_available_evidence(db, owner.id, NOW)
    assert report["analysis_ready"]
    assert report["capabilities"]["commerce"]["ready"]
    assert not report["capabilities"]["platform_performance"]["ready"]
    assert report["commerce"]["current"]["net_collected_micros"] == 100_000_000
    assert report["commerce"]["blended_sales_to_spend"] is None
    assert report["accounts"] == []
