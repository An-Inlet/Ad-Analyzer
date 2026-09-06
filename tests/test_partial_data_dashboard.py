from datetime import datetime, timedelta
from typing import Any

import pytest
from app.ads.enums import AdvertisingPlatform
from app.intelligence.service import IntelligenceService
from app.meta.models import MetaConnection
from app.shopify.models import ShopifyConnection
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.test_available_evidence import NOW, campaign, metrics, workspace
from tests.test_business_intelligence import client as client
from tests.test_business_intelligence import db as db


@pytest.fixture(autouse=True)
def fixed_report_date(monkeypatch: pytest.MonkeyPatch) -> None:
    original = IntelligenceService.report

    def report(
        self: IntelligenceService, workspace_id: int, *, as_of: datetime | None = None
    ) -> dict[str, Any]:
        return original(self, workspace_id, as_of=as_of or NOW)

    monkeypatch.setattr(IntelligenceService, "report", report)


def test_meta_only_dashboard_shows_delivery_without_business_setup(
    client: TestClient, db: Session
) -> None:
    owner = workspace(db, "meta-client")
    active = campaign(db, owner)
    metrics(db, active)
    db.commit()

    page = client.get("/dashboard/workspaces/meta-client/intelligence")
    assert page.status_code == 200
    assert "Platform insights available" in page.text
    assert "56,000" in page.text
    assert "Review declining click engagement" in page.text
    assert "Unavailable measurements are not treated as zero" in page.text
    assert 'aria-label="Business performance overview"' not in page.text
    assert "Some decisions need better evidence" not in page.text
    assert "/dashboard/workspaces/meta-client/meta" in page.text
    assert 'href="/dashboard/workspaces/meta-client/meta" aria-current' not in page.text
    assert "No briefs have been saved" in page.text
    assert "company strategy is present" not in page.text

    portfolio = client.get("/dashboard/portfolio")
    assert portfolio.status_code == 200
    assert "Platform insights available" in portfolio.text
    assert "Measurement needs attention" not in portfolio.text


def test_empty_workspace_keeps_planning_available(client: TestClient, db: Session) -> None:
    workspace(db, "new-client")
    db.commit()
    page = client.get("/dashboard/workspaces/new-client/intelligence")
    assert page.status_code == 200
    assert "Planning ready" in page.text
    assert "Start with one advertising account" in page.text
    assert "Plan an event" in page.text
    assert "Plan an experiment" in page.text
    assert 'aria-label="Business performance overview"' not in page.text
    overview = client.get("/dashboard/workspaces/new-client")
    assert overview.status_code == 200
    assert "Start with the connections you have" in overview.text
    assert "Business-outcome analysis must remain disabled" not in overview.text
    assert 'href="/dashboard/workspaces/new-client/meta"' in overview.text


def test_platform_accounts_keep_currency_and_workspace_boundaries(
    client: TestClient, db: Session
) -> None:
    owner = workspace(db, "mixed-client")
    usd = campaign(db, owner, AdvertisingPlatform.GOOGLE_ADS)
    eur = campaign(db, owner, currency="EUR", time_zone="Europe/Paris")
    metrics(db, usd, first_day_ago=1, cost_micros=11_000_000)
    metrics(db, eur, first_day_ago=1, cost_micros=22_000_000)
    foreign = workspace(db, "other-client")
    other = campaign(db, foreign)
    other.account.name = "Private other client account"
    metrics(db, other)
    db.commit()

    page = client.get("/dashboard/workspaces/mixed-client/intelligence")
    assert page.status_code == 200
    assert "Google Ads · USD · UTC" in page.text
    assert "Meta Ads · EUR · Europe/Paris" in page.text
    assert "11.00" in page.text and "22.00" in page.text
    assert "The window is incomplete" in page.text
    assert "Private other client account" not in page.text
    assert "Review declining click engagement" not in page.text


def test_shopify_only_dashboard_exposes_independent_sales(
    client: TestClient, db: Session
) -> None:
    owner = workspace(db, "store-client")
    db.add(
        ShopifyConnection(
            workspace_id=owner.id,
            shop_domain="fixture.myshopify.com",
            shop_name="Fixture Store",
            currency_code="USD",
            time_zone="UTC",
            encrypted_credentials="opaque-test-ciphertext",
            status="connected",
            last_sync_at=NOW - timedelta(hours=1),
            covered_from=NOW - timedelta(days=60),
        )
    )
    db.commit()
    page = client.get("/dashboard/workspaces/store-client/intelligence")
    assert page.status_code == 200
    assert "Sales insights available" in page.text
    assert "Fixture Store" in page.text
    assert "0 paid orders" in page.text
    assert "Store totals include all channels" in page.text
    assert 'aria-label="Business performance overview"' not in page.text
    portfolio = client.get("/dashboard/portfolio")
    assert "Sales insights available" in portfolio.text


def test_meta_detail_pages_mask_unconfigured_conversions(
    client: TestClient, db: Session
) -> None:
    owner = workspace(db, "delivery-client")
    active = campaign(db, owner)
    metrics(db, active, first_day_ago=1)
    db.commit()
    window = "?date_from=2026-09-05&date_to=2026-09-05"
    account = client.get(f"/dashboard/accounts/{active.account_id}{window}")
    assert account.status_code == 200
    assert "<dt>Platform conversions</dt><dd>Unavailable</dd>" in account.text
    assert "<dt>Platform conversion value</dt><dd>Unavailable</dd>" in account.text
    detail = client.get(f"/dashboard/campaigns/{active.id}{window}")
    assert detail.status_code == 200
    assert "<dt>Platform conversions</dt><dd>Unavailable</dd>" in detail.text
    assert "<dt>Platform ROAS</dt><dd>Unavailable</dd>" in detail.text


@pytest.mark.parametrize("action_type", ["purchase", "lead"])
def test_selected_meta_conversion_zero_is_visible_as_an_observation(
    client: TestClient, db: Session, action_type: str
) -> None:
    owner = workspace(db, "measured-client")
    active = campaign(db, owner)
    metrics(db, active)
    db.add(
        MetaConnection(
            workspace_id=owner.id,
            account_id=active.account_id,
            external_account_id="12345678",
            encrypted_credentials="opaque-test-ciphertext",
            conversion_action_type=action_type,
            last_sync_at=NOW - timedelta(hours=1),
            covered_from=NOW.date() - timedelta(days=56),
            covered_through=NOW.date() - timedelta(days=1),
        )
    )
    db.commit()
    page = client.get("/dashboard/workspaces/measured-client/intelligence")
    assert page.status_code == 200
    assert f"Selected Meta conversion event: {action_type}" in page.text
    table = page.text.split("platform campaign performance", 1)[1].split("</table>", 1)[0]
    assert "<td>0.0</td>" in table
    assert "<td>Unavailable</td>" not in table
    assert 'aria-label="Business performance overview"' not in page.text
    if action_type == "lead":
        window = "?date_from=2026-09-05&date_to=2026-09-05"
        account = client.get(f"/dashboard/accounts/{active.account_id}{window}")
        assert account.status_code == 200
        count = account.text.split("<dt>Platform conversions</dt><dd>", 1)[1].split("</dd>", 1)[0]
        assert float(count) == 0
        assert "<dt>Platform conversion value</dt><dd>Unavailable</dd>" in account.text
        detail = client.get(f"/dashboard/campaigns/{active.id}{window}")
        assert detail.status_code == 200
        assert "<dt>Platform ROAS</dt><dd>Unavailable</dd>" in detail.text
