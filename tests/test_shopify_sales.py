"""Offline Shopify contract, isolation, accounting and authorization checks."""

import base64
import hashlib
import hmac
import json
import logging
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest
from app.automation.models import PlatformAutomationControl, WorkspaceAutomationControl
from app.intelligence.service import IntelligenceService
from app.settings import Settings, settings
from app.shopify.client import ShopifyClient
from app.shopify.logging import OAuthAccessFilter
from app.shopify.models import (
    ShopifyConnection,
    ShopifyOAuthState,
    ShopifyOrder,
    ShopifyPrivacyRequest,
)
from app.shopify.normalize import normalized_order
from app.shopify.privacy import process_event, purge_expired_facts
from app.shopify.reporting import sales_report
from app.shopify.security import (
    ShopifyError,
    Vault,
    configuration_ready,
    shop_domain,
    verify_callback,
)
from app.shopify.service import ConnectionService, credentials
from app.shopify.sync import ShopifySyncService
from app.workspaces.models import WorkspaceMembership
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from tests.test_business_intelligence import client as client
from tests.test_business_intelligence import csrf
from tests.test_business_intelligence import db as db
from tests.test_unified_outcome_data import seed_workspace

NOW = datetime(2026, 9, 6, 12, tzinfo=UTC)
SHOP = "example-test.myshopify.com"


@pytest.fixture()
def configuration() -> Settings:
    # Deterministic fake runtime values. Never contact a real store.
    return Settings(
        _env_file=None,
        AD_ANALYZER_SHOPIFY_ENABLED=True,
        shopify_client_id="offline-client-id",
        shopify_client_secret=SecretStr("offline-secret-" * 3),
        shopify_token_encryption_key=SecretStr(base64.urlsafe_b64encode(b"x" * 32).decode()),
        shopify_identifier_hash_key=SecretStr("offline-hash-" * 4),
        shopify_redirect_uri="https://example.test/dashboard/shopify/callback",
        shopify_webhook_subscription="projects/offline/subscriptions/shopify",
    )


class FakeShopify(ShopifyClient):
    def __init__(self, configuration: Settings, pages: list[Any] | None = None) -> None:
        super().__init__(configuration)
        self.pages = list(pages or [])
        self.requests: list[tuple[str, str | None, str]] = []
        self.token_calls = 0
        self.scope = "read_orders,read_products"

    def token(
        self, shop: str, *, code: str | None = None, refresh: str | None = None
    ) -> dict[str, Any]:
        self.token_calls += 1
        return {
            "access_token": "offline-access-rotated",
            "refresh_token": "offline-refresh-rotated",
            "expires_in": 3600,
            "scope": self.scope,
        }

    def shop(self, shop: str, token: str) -> dict[str, Any]:
        return {
            "shop": {
                "name": "Example Store",
                "myshopifyDomain": shop,
                "currencyCode": "USD",
                "ianaTimezone": "UTC",
            },
            "currentAppInstallation": {
                "accessScopes": [{"handle": scope} for scope in self.scope.split(",")]
            },
        }

    def orders(self, shop: str, token: str, cursor: str | None, query: str) -> dict[str, Any]:
        self.requests.append((shop, cursor, query))
        response = self.pages.pop(0)
        if isinstance(response, Exception):
            raise response
        return dict(response)


def connected(db: Session, configuration: Settings, slug: str = "alpha") -> ShopifyConnection:
    workspace, _account, _campaign = seed_workspace(db, slug)
    shop = SHOP if slug == "alpha" else f"{slug}.myshopify.com"
    bundle = credentials(
        {
            "access_token": "offline-access-token",
            "refresh_token": "offline-refresh-token",
            "expires_in": 3600,
            "scope": "read_orders,read_products",
        },
        NOW,
    )
    row = ShopifyConnection(
        workspace_id=workspace.id,
        shop_domain=shop,
        shop_name="Example Store",
        currency_code="USD",
        time_zone="UTC",
        encrypted_credentials=Vault(configuration).seal(workspace.id, shop, bundle),
        connected_at=NOW,
    )
    db.add(row)
    db.commit()
    return row


def order(number: int = 101, **changes: Any) -> dict[str, Any]:
    def amount(value: str) -> dict[str, Any]:
        return {"shopMoney": {"amount": value, "currencyCode": "USD"}}

    data = {
        "id": f"gid://shopify/Order/{number}",
        "createdAt": (NOW - timedelta(days=2)).isoformat(),
        "updatedAt": (NOW - timedelta(hours=1)).isoformat(),
        "test": False,
        "cancelledAt": None,
        "netPaymentSet": amount("80"),
        "totalRefundedSet": amount("20"),
        "customerJourneySummary": {
            "ready": True,
            "customerOrderIndex": 1,
            "lastVisit": {
                "utmParameters": {"source": "google", "campaign": "123", "medium": "cpc"}
            },
        },
        "lineItems": {
            "pageInfo": {"hasNextPage": False},
            "nodes": [
                {
                    "quantity": 2,
                    "currentQuantity": 1,
                    "originalUnitPriceSet": amount("50"),
                    "variant": {
                        "id": "gid://shopify/ProductVariant/7",
                        "product": {"id": "gid://shopify/Product/5", "title": "Example product"},
                    },
                }
            ],
        },
    }
    return {**data, **changes}


def page(*nodes: dict[str, Any], more: bool = False, cursor: str | None = None) -> dict[str, Any]:
    return {"nodes": list(nodes), "pageInfo": {"hasNextPage": more, "endCursor": cursor}}


def callback_values(secret: str, **changes: str) -> dict[str, str]:
    values = {
        "shop": SHOP,
        "state": "s" * 43,
        "code": "offline-code",
        "timestamp": str(int(NOW.timestamp())),
        **changes,
    }
    message = "&".join(f"{k}={values[k]}" for k in sorted(values))
    return {
        **values,
        "hmac": hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest(),
    }


@pytest.mark.parametrize(
    "value",
    [
        "https://shop.myshopify.com",
        "shop.myshopify.com.attacker.test",
        "shop.myshopify.com:443",
        "127.0.0.1",
        "shop.myshopify.com/path",
        "shop@evil.test",
    ],
)
def test_shop_destinations_are_restricted(value: str) -> None:
    with pytest.raises(ShopifyError):
        shop_domain(value)


def test_configuration_is_opt_in_and_complete(configuration: Settings) -> None:
    assert configuration_ready(configuration)
    assert not configuration_ready(configuration.model_copy(update={"shopify_enabled": False}))
    assert not configuration_ready(
        configuration.model_copy(update={"shopify_webhook_subscription": ""})
    )
    assert not configuration_ready(
        configuration.model_copy(
            update={"shopify_redirect_uri": "http://example.test/dashboard/shopify/callback"}
        )
    )


def test_oauth_signature_expiry_and_duplicate_parameters(configuration: Settings) -> None:
    assert configuration.shopify_client_secret
    secret = configuration.shopify_client_secret.get_secret_value()
    values = callback_values(secret)
    assert verify_callback(list(values.items()), secret, NOW)["shop"] == SHOP
    for pairs in [list({**values, "code": "tampered"}.items()), [*values.items(), ("shop", SHOP)]]:
        with pytest.raises(ShopifyError):
            verify_callback(pairs, secret, NOW)
    with pytest.raises(ShopifyError):
        verify_callback(list(values.items()), secret, NOW + timedelta(minutes=11))


def test_oauth_state_actor_shop_workspace_and_replay(db: Session, configuration: Settings) -> None:
    workspace, _a, _c = seed_workspace(db, "alpha")
    fake = FakeShopify(configuration)
    service = ConnectionService(db, configuration, fake)
    url = service.begin(workspace.id, SHOP, "owner", NOW)
    args = {k: values[0] for k, values in parse_qs(urlsplit(url).query).items()}
    assert set(args["scope"].split(",")) == {"read_orders", "read_products"}
    values = {"shop": SHOP, "state": args["state"]}
    for bad, actor in [
        (values, "other-owner"),
        ({**values, "shop": "elsewhere.myshopify.com"}, "owner"),
    ]:
        with pytest.raises(ShopifyError, match="invalid_oauth_state"):
            service.pending(bad, actor, NOW)
    state = service.pending(values, "owner", NOW)
    row = service.finish(state, "offline-code", "owner", NOW)
    assert row.workspace_id == workspace.id and row.status == "connected"
    assert "offline-access" not in row.encrypted_credentials
    with pytest.raises(ShopifyError, match="invalid_oauth_state"):
        service.pending(values, "owner", NOW)
    beta, _a, _c = seed_workspace(db, "beta")
    with pytest.raises(ShopifyError, match="store_already_connected"):
        service.begin(beta.id, SHOP, "owner", NOW)


def test_credentials_are_context_bound_and_write_scopes_rejected(configuration: Settings) -> None:
    vault = Vault(configuration)
    encrypted = vault.seal(1, SHOP, {"access_token": "offline-only"})
    assert vault.open(1, SHOP, encrypted)["access_token"] == "offline-only"
    for workspace, shop in [(2, SHOP), (1, "elsewhere.myshopify.com")]:
        with pytest.raises(ShopifyError):
            vault.open(workspace, shop, encrypted)
    for scope in ["write_orders,read_orders,read_products", "read_products"]:
        with pytest.raises(ShopifyError, match="read_only_scopes"):
            credentials({"access_token": "offline-only", "scope": scope}, NOW)


def test_cursor_query_is_frozen_and_reimports_update_without_duplicates(
    db: Session, configuration: Settings
) -> None:
    row = connected(db, configuration)
    first = order()
    changed = order()
    changed["netPaymentSet"]["shopMoney"]["amount"] = "60"
    changed["totalRefundedSet"]["shopMoney"]["amount"] = "40"
    fake = FakeShopify(
        configuration, [page(first, more=True, cursor="next-page"), page(order(102)), page(changed)]
    )
    service = ShopifySyncService(db, configuration, fake)
    assert service.page(row.workspace_id, now=NOW)["status"] == "syncing"
    assert service.page(row.workspace_id, now=NOW + timedelta(minutes=1))["status"] == "complete"
    assert fake.requests[0][2] == fake.requests[1][2]
    assert fake.requests[1][1] == "next-page"
    assert (
        service.page(row.workspace_id, now=NOW + timedelta(minutes=2), manual=True)["status"]
        == "complete"
    )
    rows = list(db.scalars(select(ShopifyOrder)))
    assert len(rows) == 2 and sum(o.refunded_micros for o in rows) == 60_000_000
    assert not row.cursor and row.last_sync_at


def test_failed_page_is_atomic_and_preserves_rotated_token(
    db: Session, configuration: Settings
) -> None:
    row = connected(db, configuration)
    broken = order(102)
    broken["netPaymentSet"]["shopMoney"]["currencyCode"] = "EUR"
    fake = FakeShopify(configuration, [page(order(), broken)])
    result = ShopifySyncService(db, configuration, fake).page(
        row.workspace_id, now=NOW + timedelta(hours=1)
    )
    assert result["status"] == "shopify_currency_mismatch"
    assert list(db.scalars(select(ShopifyOrder))) == []
    assert fake.token_calls == 1
    bundle = Vault(configuration).open(row.workspace_id, SHOP, row.encrypted_credentials)
    assert bundle["refresh_token"] == "offline-refresh-rotated"
    assert row.last_sync_at is None and row.next_attempt_at


def test_throttle_and_automation_controls_stop_network_reads(
    db: Session, configuration: Settings
) -> None:
    row = connected(db, configuration)
    fake = FakeShopify(configuration, [ShopifyError("shopify_throttled", retry_after=300)])
    service = ShopifySyncService(db, configuration, fake)
    assert service.page(row.workspace_id, now=NOW)["status"] == "shopify_throttled"
    assert (
        service.page(row.workspace_id, now=NOW + timedelta(minutes=1), manual=True)["status"]
        == "retry_later"
    )
    db.add(PlatformAutomationControl(key="all_data_syncs", enabled=False, updated_by="test"))
    db.commit()
    assert (
        service.page(row.workspace_id, now=NOW + timedelta(hours=1), manual=True)["status"]
        == "disabled"
    )
    assert len(fake.requests) == 1


def test_workspace_control_blocks_import(db: Session, configuration: Settings) -> None:
    row = connected(db, configuration)
    db.add(
        WorkspaceAutomationControl(
            workspace_id=row.workspace_id,
            key="shopify_sales_sync",
            enabled=False,
            updated_by="test",
        )
    )
    db.commit()
    fake = FakeShopify(configuration)
    assert (
        ShopifySyncService(db, configuration, fake).page(row.workspace_id, now=NOW, manual=True)[
            "status"
        ]
        == "disabled"
    )
    assert not fake.requests


def test_redaction_is_scoped_idempotent_and_prevents_reimport(
    db: Session, configuration: Settings
) -> None:
    alpha = connected(db, configuration)
    beta = connected(db, configuration, "beta")
    for connection in (alpha, beta):
        ShopifySyncService(db, configuration, FakeShopify(configuration, [page(order())])).page(
            connection.workspace_id, now=NOW
        )
    for _ in range(2):
        process_event(
            db,
            configuration,
            "customers/redact",
            SHOP,
            {"orders_to_redact": [101], "customer": {"email": "discard@example.test"}},
            NOW,
        )
    assert len(list(db.scalars(select(ShopifyOrder)))) == 1
    ShopifySyncService(db, configuration, FakeShopify(configuration, [page(order())])).page(
        alpha.workspace_id, now=NOW, manual=True
    )
    assert len(list(db.scalars(select(ShopifyOrder)))) == 1
    assert sales_report(db, beta.workspace_id, now=NOW)["current"]["paid_orders"] == 1


def test_test_orders_and_large_line_items_do_not_distort_totals(
    db: Session, configuration: Settings
) -> None:
    row = connected(db, configuration)
    huge = order(102)
    huge["lineItems"]["pageInfo"]["hasNextPage"] = True
    ShopifySyncService(
        db, configuration, FakeShopify(configuration, [page(order(test=True), huge)])
    ).page(row.workspace_id, now=NOW)
    report = sales_report(db, row.workspace_id, now=NOW)
    assert report["current"]["net_collected_micros"] == 80_000_000
    assert not report["products"]
    assert any("10 line items" in note for note in report["warnings"])


def test_sales_totals_repeat_unknown_and_foreign_campaigns(
    db: Session, configuration: Settings
) -> None:
    row = connected(db, configuration)
    beta = connected(db, configuration, "beta")
    second = order(102)
    second["customerJourneySummary"]["customerOrderIndex"] = 2
    third = order(103, customerJourneySummary={"ready": False, "customerOrderIndex": 2})
    ShopifySyncService(
        db, configuration, FakeShopify(configuration, [page(order(), second, third)])
    ).page(row.workspace_id, now=NOW)
    report = sales_report(db, row.workspace_id, now=NOW)
    assert report["current"]["net_collected_micros"] == 240_000_000
    assert report["current"]["refunded_micros"] == 60_000_000
    assert report["current"]["returning_order_share"] == 0.5
    assert report["current"]["unknown_orders"] == 1
    assert report["products"][0]["ordered_units"] == 6
    assert report["blended_sales_to_spend"] is None
    assert sales_report(db, beta.workspace_id, now=NOW)["current"]["orders"] == 0
    assert report["ready"] and report["previous_complete"]
    assert "discard@example.test" not in json.dumps(report)


def test_retention_runs_while_disabled_and_disconnect_purges(
    db: Session, configuration: Settings
) -> None:
    row = connected(db, configuration)
    old = normalized_order(
        db, row, order(createdAt=(NOW - timedelta(days=60)).isoformat()), Vault(configuration)
    )
    db.add(ShopifyOrder(connection_id=row.id, workspace_id=row.workspace_id, **old))
    db.commit()
    purge_expired_facts(db.get_bind(), now=NOW)  # type: ignore[arg-type]
    db.expire_all()
    assert list(db.scalars(select(ShopifyOrder))) == []
    ConnectionService(db, configuration).begin(row.workspace_id, SHOP, "owner", NOW)
    ConnectionService(db, configuration).disconnect(row.workspace_id, "owner")
    assert list(db.scalars(select(ShopifyConnection))) == []
    assert list(db.scalars(select(ShopifyOAuthState))) == []


def test_uninstall_ignores_previous_installation_and_removes_current(
    db: Session, configuration: Settings
) -> None:
    row = connected(db, configuration)
    process_event(db, configuration, "app/uninstalled", SHOP, {}, NOW - timedelta(days=1))
    assert db.get(ShopifyConnection, row.id) is not None
    process_event(db, configuration, "app/uninstalled", SHOP, {}, NOW)
    assert list(db.scalars(select(ShopifyConnection))) == []


def test_dashboard_api_export_privacy_and_permissions(
    client: TestClient, db: Session, configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Route reports must use the same fixed clock as the imported order fixture.
    monkeypatch.setattr("app.api.shopify.sales_report", partial(sales_report, now=NOW))
    monkeypatch.setattr("app.dashboard.shopify.sales_report", partial(sales_report, now=NOW))
    row = connected(db, configuration)
    beta = connected(db, configuration, "beta")
    for key in type(configuration).model_fields:
        if key.startswith("shopify_"):
            monkeypatch.setattr(settings, key, getattr(configuration, key))
    ShopifySyncService(db, configuration, FakeShopify(configuration, [page(order())])).page(
        row.workspace_id, now=NOW
    )
    root = "/dashboard/workspaces/alpha/shopify"
    response = client.get(root)
    assert response.status_code == 200 and "Product demand" in response.text
    assert "offline-access" not in response.text
    token = csrf(response.text)
    assert client.get(root + "/sales.csv").status_code == 200
    assert client.get("/api/v1/workspaces/alpha/shopify").json()["current"]["paid_orders"] == 1
    assert client.post(root + "/connect", data={"shop": SHOP}).status_code == 403
    values = {
        "orders_requested": [101],
        "data_request": {"id": 44},
        "customer": {"email": "discard@example.test"},
    }
    for _ in range(2):
        process_event(db, configuration, "customers/data_request", SHOP, values, NOW)
    pending = list(db.scalars(select(ShopifyPrivacyRequest)))
    assert len(pending) == 1
    path = f"/privacy/{pending[0].id}"
    exported = client.get(root + path + ".json")
    assert exported.status_code == 200 and len(exported.json()["records"]) == 1
    assert "discard@example.test" not in exported.text
    assert client.get(f"/dashboard/workspaces/beta/shopify{path}.json").status_code == 404
    assert (
        client.post(
            root + path + "/delivered", data={"csrf_token": token}, follow_redirects=False
        ).status_code
        == 303
    )
    assert client.post(root + "/disconnect", data={"csrf_token": token}).status_code == 422
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "iap_audience", "test-audience")
    monkeypatch.setattr(
        "app.dashboard.auth.verify_iap_jwt",
        lambda assertion, audience: {"email": "viewer@example.test"},
    )
    client.headers["x-goog-iap-jwt-assertion"] = "offline-assertion"
    db.add(
        WorkspaceMembership(
            workspace_id=row.workspace_id,
            principal="viewer@example.test",
            role="viewer",
            status="active",
        )
    )
    db.commit()
    assert client.get(root).status_code == 200
    assert client.get("/dashboard/workspaces/beta/shopify").status_code == 404
    assert client.get(root + path + ".json").status_code == 403
    assert (
        client.post(root + "/connect", data={"shop": SHOP, "csrf_token": token}).status_code == 403
    )
    assert beta.workspace_id != row.workspace_id


def test_dashboard_callback_is_authenticated_and_bound(
    client: TestClient, db: Session, configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, _a, _c = seed_workspace(db, "alpha")
    for key in type(configuration).model_fields:
        if key.startswith("shopify_"):
            monkeypatch.setattr(settings, key, getattr(configuration, key))
    fake = FakeShopify(configuration)
    monkeypatch.setattr("app.shopify.service.ShopifyClient", lambda configuration: fake)
    html = client.get("/dashboard/workspaces/alpha/shopify")
    response = client.post(
        "/dashboard/workspaces/alpha/shopify/connect",
        data={"shop": SHOP, "csrf_token": csrf(html.text)},
        follow_redirects=False,
    )
    import re
    from html import unescape

    assert response.status_code == 200
    assert "form-action 'self'" in response.headers["content-security-policy"]
    assert "no-store" in response.headers["cache-control"]
    match = re.search(r'id="shopify-authorization"[^>]*href="([^"]+)"', response.text)
    assert match
    location = unescape(match.group(1))
    assert urlsplit(location).hostname == SHOP
    state = parse_qs(urlsplit(location).query)["state"][0]
    assert configuration.shopify_client_secret
    values = callback_values(
        configuration.shopify_client_secret.get_secret_value(),
        state=state,
        timestamp=str(int(datetime.now(UTC).timestamp())),
    )
    path = "/dashboard/shopify/callback?" + urlencode(values)
    assert client.get(path, follow_redirects=False).status_code == 303
    assert client.get(path, follow_redirects=False).status_code == 422
    assert fake.token_calls == 1
    assert db.scalar(select(ShopifyConnection.workspace_id)) == workspace.id


def test_sales_question_uses_commerce_evidence(db: Session, configuration: Settings) -> None:
    row = connected(db, configuration)
    service = IntelligenceService(db)
    report = service.report(row.workspace_id, as_of=NOW)
    answer = service.answer(report, "How are Shopify sales and refunds doing?")
    assert answer["topic"] == "sales" and answer["evidence"] == report["commerce"]
    assert "causation" in str(answer["limitations"])


def test_oauth_access_logs_are_suppressed() -> None:
    callback = logging.LogRecord(
        "uvicorn.access",
        20,
        "",
        1,
        '%s - "%s %s HTTP/%s" %s',
        ("client", "GET", "/dashboard/shopify/callback?code=offline-sensitive", "1.1", 303),
        None,
    )
    assert not OAuthAccessFilter().filter(callback)
    normal = logging.LogRecord("uvicorn.access", 20, "", 1, "GET /health", (), None)
    assert OAuthAccessFilter().filter(normal)


def test_campaign_sales_spend_uses_canonical_rows_and_complete_coverage(
    db: Session, configuration: Settings
) -> None:
    from app.ads.models import AdvertisingAccount, Campaign, DailyMetric

    row = connected(db, configuration)
    campaign = db.scalar(select(Campaign))
    assert campaign
    campaign.external_campaign_id = "123"
    account = db.get(AdvertisingAccount, campaign.account_id)
    assert account
    account.time_zone = "UTC"
    for days in range(1, 29):
        db.add(
            DailyMetric(
                platform=campaign.platform,
                campaign_id=campaign.id,
                entity_type="campaign",
                entity_id=campaign.id,
                metric_date=NOW.date() - timedelta(days=days),
                cost_micros=1_000_000,
            )
        )
    db.commit()
    ShopifySyncService(db, configuration, FakeShopify(configuration, [page(order())])).page(
        row.workspace_id, now=NOW
    )
    report = sales_report(db, row.workspace_id, now=NOW)
    assert report["matched_orders"] == 1
    assert report["ad_spend_micros"] == 28_000_000
    assert report["blended_sales_to_spend"] == pytest.approx(80 / 28)
    assert report["campaigns"][0]["tagged_sales_to_spend"] == pytest.approx(80 / 28)
    account.currency_code = "EUR"
    db.commit()
    assert sales_report(db, row.workspace_id, now=NOW)["blended_sales_to_spend"] is None
    account.currency_code = "USD"
    metric = db.scalar(select(DailyMetric))
    assert metric
    db.delete(metric)
    db.commit()
    assert sales_report(db, row.workspace_id, now=NOW)["blended_sales_to_spend"] is None


def test_foreign_campaign_tag_never_matches_or_leaks(db: Session, configuration: Settings) -> None:
    from app.ads.models import AdvertisingAccount, Campaign

    row = connected(db, configuration)
    other = connected(db, configuration, "beta")
    foreign = db.scalar(
        select(Campaign)
        .join(AdvertisingAccount)
        .where(AdvertisingAccount.workspace_id == other.workspace_id)
    )
    assert foreign
    foreign.external_campaign_id = "123"
    db.commit()
    ShopifySyncService(db, configuration, FakeShopify(configuration, [page(order())])).page(
        row.workspace_id, now=NOW
    )
    imported = db.scalar(select(ShopifyOrder).where(ShopifyOrder.workspace_id == row.workspace_id))
    assert imported and imported.campaign_id is None
    # Defend the read boundary even against a corrupt local cross-workspace reference.
    imported.campaign_id = foreign.id
    db.commit()
    report = sales_report(db, row.workspace_id, now=NOW)
    assert not report["campaigns"] and report["matched_orders"] == 0
    assert foreign.name not in json.dumps(report)


def test_stale_updates_do_not_restore_old_refunds(db: Session, configuration: Settings) -> None:
    row = connected(db, configuration)
    stale = order(updatedAt=(NOW - timedelta(days=1)).isoformat())
    stale["totalRefundedSet"]["shopMoney"]["amount"] = "0"
    fake = FakeShopify(configuration, [page(order()), page(stale)])
    service = ShopifySyncService(db, configuration, fake)
    service.page(row.workspace_id, now=NOW)
    service.page(row.workspace_id, now=NOW, manual=True)
    saved = db.scalar(select(ShopifyOrder))
    assert saved and saved.refunded_micros == 20_000_000


def test_transport_sanitizes_errors_and_prohibits_redirects(
    configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    from email.message import Message
    from urllib.error import HTTPError

    from app.shopify.client import NoRedirect

    class Failure:
        def open(self, request: Any, timeout: int) -> Any:
            assert request.full_url == f"https://{SHOP}/admin/api/2026-07/graphql.json"
            assert timeout == 15
            headers = Message()
            headers["Retry-After"] = "180"
            raise HTTPError(request.full_url, 429, "sensitive upstream response", headers, None)

    monkeypatch.setattr("app.shopify.client.build_opener", lambda handler: Failure())
    with pytest.raises(ShopifyError) as error:
        ShopifyClient(configuration).orders(SHOP, "offline-token", None, "")
    assert error.value.code == "shopify_throttled" and error.value.retry_after == 180
    assert "sensitive" not in str(error.value)
    NoRedirect().redirect_request(None, None, 302, "", {}, "https://elsewhere.test")


def test_pubsub_commits_before_ack_and_does_not_log_payloads(
    db: Session,
    configuration: Settings,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from types import SimpleNamespace

    from app.shopify.privacy import run_privacy_tick

    row = connected(db, configuration)
    ShopifySyncService(db, configuration, FakeShopify(configuration, [page(order())])).page(
        row.workspace_id, now=NOW
    )
    for key in type(configuration).model_fields:
        if key.startswith("shopify_"):
            monkeypatch.setattr(settings, key, getattr(configuration, key))
    monkeypatch.setattr(settings, "shopify_enabled", False)
    acked = []
    event = {
        "metadata": {"X-Shopify-Topic": "customers/redact", "X-Shopify-Shop-Domain": SHOP},
        "payload": {"orders_to_redact": [101], "customer": {"email": "private@example.test"}},
    }
    valid = SimpleNamespace(
        ack_id="valid",
        message=SimpleNamespace(data=json.dumps(event).encode(), publish_time=NOW, attributes={}),
    )
    invalid = SimpleNamespace(
        ack_id="invalid",
        message=SimpleNamespace(data=b"private@example.test", publish_time=NOW, attributes={}),
    )

    class Subscriber:
        def __enter__(self) -> Any:
            return self

        def __exit__(self, *args: Any) -> None:
            pass

        def pull(self, **kwargs: Any) -> Any:
            return SimpleNamespace(received_messages=[valid, invalid])

        def acknowledge(self, **kwargs: Any) -> None:
            with Session(db.get_bind()) as check:
                assert check.scalar(select(ShopifyOrder.id)) is None
            acked.extend(kwargs["request"]["ack_ids"])

    monkeypatch.setattr("google.cloud.pubsub_v1.SubscriberClient", Subscriber)
    run_privacy_tick(db.get_bind())  # type: ignore[arg-type]
    assert acked == ["valid"]
    assert "private@example.test" not in caplog.text


def test_shopify_migration_matches_models_and_composite_isolation(db: Session) -> None:
    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine, inspect

    path = Path("migrations/versions/20260906_0018_shopify_sales.py")
    spec = importlib.util.spec_from_file_location("shopify_migration", path)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        names = inspect(connection).get_table_names()
        assert {"shopify_connections", "shopify_orders", "shopify_privacy_requests"} <= set(names)
        foreign_keys = inspect(connection).get_foreign_keys("shopify_orders")
        assert any(
            key["constrained_columns"] == ["connection_id", "workspace_id"] for key in foreign_keys
        )
    engine.dispose()


def test_slow_manual_sync_does_not_block_other_dashboard_requests(
    client: TestClient, db: Session, configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    connected(db, configuration)
    root = "/dashboard/workspaces/alpha/shopify"
    token = csrf(client.get(root).text)
    entered, release = Event(), Event()

    def slow_page(self: Any, workspace_id: int, **kwargs: Any) -> dict[str, Any]:
        entered.set()
        assert release.wait(10)
        return {"status": "complete", "imported": 0}

    monkeypatch.setattr(ShopifySyncService, "page", slow_page)
    with ThreadPoolExecutor(max_workers=2) as pool:
        refresh = pool.submit(
            client.post, root + "/sync", data={"csrf_token": token}, follow_redirects=False
        )
        try:
            assert entered.wait(5)
            health = pool.submit(client.get, "/health")
            assert health.result(timeout=5).status_code == 200
        finally:
            release.set()
        assert refresh.result(timeout=5).status_code == 303
