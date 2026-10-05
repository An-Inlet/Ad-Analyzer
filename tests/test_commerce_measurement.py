"""Offline B05 acceptance, run against SQLite and isolated PostgreSQL schemas."""

from collections.abc import Generator
from copy import deepcopy
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from app.commerce.ledger import (
    MEASUREMENT_SCOPES,
    apply_order,
    bind_store,
    identity_key,
    link_verified_order,
    retention_floor,
)
from app.commerce.models import (
    CommerceDailyRevision,
    CommerceEntry,
    CommerceOrder,
    CommerceSnapshot,
    CommerceStore,
)
from app.commerce.privacy import purge_measurements
from app.commerce.reporting import MeasurementWindow, measurement
from app.commerce.source import MeasurementClient
from app.commerce.sync import CommerceSyncService
from app.imports.native import bind_shopify
from app.settings import Settings
from app.shopify.models import ShopifyConnection, ShopifyPrivacyRequest
from app.shopify.privacy import process_event
from app.shopify.security import ShopifyError, Vault
from app.shopify.service import ConnectionService
from app.workspaces.models import WorkspaceIntegration
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_shopify_sales import FakeShopify, connected
from tests.test_shopify_sales import configuration as configuration

NOW = datetime(2026, 10, 5, 12, tzinfo=UTC)
CREATED = datetime(2026, 9, 10, 12, tzinfo=UTC)


def amount(value: str) -> dict[str, Any]:
    return {"shopMoney": {"amount": value, "currencyCode": "USD"}}


def agreement(
    number: int = 1,
    gross: str = "99",
    tax: str = "9",
    action: str = "ORDER",
    when: datetime = CREATED,
    line: str = "PRODUCT",
) -> dict[str, Any]:
    return {
        "id": f"gid://shopify/OrderAgreement/{number}",
        "__typename": {
            "ORDER": "OrderAgreement",
            "RETURN": "RefundAgreement",
            "UPDATE": "OrderEditAgreement",
        }.get(action, "OrderAgreement"),
        "reason": {"ORDER": "ORDER", "RETURN": "REFUND", "UPDATE": "ORDER_EDIT"}.get(
            action, "ORDER"
        ),
        "refund": {"processedAt": when.isoformat()} if action == "RETURN" else None,
        "happenedAt": when.isoformat(),
        "sales": [
            {
                "id": f"gid://shopify/ProductSale/{number}",
                "actionType": action,
                "lineType": line,
                "totalAmount": amount(gross),
                "totalTaxAmount": amount(tax),
            }
        ],
    }


def source(
    number: int = 1, customer: int | None = 100, updated: datetime = CREATED
) -> dict[str, Any]:
    return {
        "id": f"gid://shopify/Order/{number}",
        "createdAt": CREATED.isoformat(),
        "updatedAt": updated.isoformat(),
        "test": False,
        "customer": {"id": f"gid://shopify/Customer/{customer}"} if customer else None,
    }


def setup(
    db: Session, config: Settings, slug: str = "alpha"
) -> tuple[ShopifyConnection, CommerceStore]:
    config.shopify_measurement_enabled = True
    row = connected(db, config, slug)
    bind_shopify(db, row)
    store = bind_store(db, row, "gid://shopify/Shop/123", config, NOW)
    store.covered_from, store.last_sync_at = retention_floor(NOW), NOW
    bundle = Vault(config).open(row.workspace_id, row.shop_domain, row.encrypted_credentials)
    bundle["scopes"], bundle["expires_at"] = (
        sorted(MEASUREMENT_SCOPES),
        (NOW + timedelta(hours=1)).isoformat(),
    )
    row.encrypted_credentials = Vault(config).seal(row.workspace_id, row.shop_domain, bundle)
    db.commit()
    return row, store


def window(
    start: date = date(2026, 9, 1), end: date = date(2026, 10, 1), basis: str = "calendar_month"
) -> MeasurementWindow:
    return MeasurementWindow(
        start=start, end=end, time_basis=basis, currency="USD", time_zone="UTC"
    )


def test_canonical_sources_refunds_customers_and_history(
    customer_engine: Engine, configuration: Settings
) -> None:
    with Session(customer_engine) as db:
        row, store = setup(db, configuration)
        initial = [agreement(), agreement(2, "11", "1", line="SHIPPING")]
        assert apply_order(db, store, row, source(), initial, configuration, NOW)
        baseline = measurement(db, row.workspace_id, store.id, window(), now=NOW, snapshot=True)
        assert baseline["net_sales_micros"] == 90_000_000
        db.commit()
        for provider in ("klaviyo", "hubspot", "omnisend"):
            connection = WorkspaceIntegration(
                workspace_id=row.workspace_id,
                integration_key=provider,
                provider=provider,
                display_name=provider,
                status="active",
            )
            db.add(connection)
            db.flush()
            link_verified_order(
                db,
                row.workspace_id,
                connection.id,
                "external-1",
                store.id,
                source()["id"],
                configuration,
            )
        assert not apply_order(db, store, row, source(), initial, configuration, NOW)
        assert store.revision == 1
        refunded = initial + [
            agreement(3, "-22", "-2", "RETURN", datetime(2026, 10, 2, tzinfo=UTC))
        ]
        assert apply_order(db, store, row, source(updated=NOW), refunded, configuration, NOW)
        assert (
            measurement(db, row.workspace_id, store.id, window(), now=NOW)["net_sales_micros"]
            == 90_000_000
        )
        cumulative = measurement(
            db,
            row.workspace_id,
            store.id,
            window(date(2026, 9, 1), date(2026, 10, 5), "cumulative"),
            now=NOW,
        )
        assert cumulative["net_sales_micros"] == 70_000_000
        saved = db.get(CommerceSnapshot, baseline["snapshot_id"])
        assert saved is not None and saved.result["net_sales_micros"] == 90_000_000
        apply_order(db, store, row, source(2), [agreement(4)], configuration, NOW)
        totals = measurement(db, row.workspace_id, store.id, window(), now=NOW)
        assert totals["orders"] == 2 and totals["distinct_customers"] == 1
        apply_order(db, store, row, source(3, customer=None), [agreement(5)], configuration, NOW)
        totals = measurement(db, row.workspace_id, store.id, window(), now=NOW)
        assert totals["distinct_customers"] is None and totals["known_distinct_customers"] == 1
        assert totals["orders_without_customer_identity"] == 1
        assert db.scalar(select(func.count()).select_from(CommerceOrder)) == 3


def test_zero_missing_revisions_and_retention(
    customer_engine: Engine, configuration: Settings
) -> None:
    with Session(customer_engine) as db:
        row, store = setup(db, configuration)
        assert (
            measurement(db, row.workspace_id, store.id, window(), now=NOW)["net_sales_micros"] == 0
        )
        store.covered_from = None
        assert (
            measurement(db, row.workspace_id, store.id, window(), now=NOW)["net_sales_micros"]
            is None
        )
        store.covered_from = retention_floor(NOW)
        apply_order(db, store, row, source(), [agreement()], configuration, NOW)
        assert not apply_order(
            db, store, row, source(), [agreement()], configuration, NOW + timedelta(days=1)
        )
        with pytest.raises(ShopifyError, match="commerce_conflicting_revision"):
            apply_order(db, store, row, source(), [agreement(gross="110")], configuration, NOW)
        apply_order(
            db,
            store,
            row,
            source(updated=NOW),
            [agreement(gross="110", tax="10")],
            configuration,
            NOW,
        )
        assert not apply_order(db, store, row, source(), [agreement()], configuration, NOW)
        assert list(
            db.scalars(
                select(CommerceDailyRevision.net_micros).order_by(CommerceDailyRevision.revision)
            )
        ) == [90_000_000, 100_000_000]
        db.commit()
        purge_measurements(db, NOW + timedelta(days=90))
        assert db.scalar(select(func.count()).select_from(CommerceOrder)) == 1
        purge_measurements(db, NOW + timedelta(days=410))
        assert db.scalar(select(func.count()).select_from(CommerceEntry)) == 0
        assert db.scalar(select(func.count()).select_from(CommerceOrder)) == 0


def test_privacy_export_erasure_and_reconnect_suppression(
    customer_engine: Engine, configuration: Settings
) -> None:
    with Session(customer_engine) as db:
        row, store = setup(db, configuration)
        apply_order(db, store, row, source(), [agreement()], configuration, NOW)
        snap = measurement(db, row.workspace_id, store.id, window(), now=NOW, snapshot=True)
        db.commit()
        payload = {"customer": {"id": 100}, "orders_requested": [], "data_request": {"id": 99}}
        process_event(db, configuration, "customers/data_request", row.shop_domain, payload, NOW)
        request = db.scalar(select(ShopifyPrivacyRequest))
        assert request is not None
        assert request.commerce_keys == [identity_key(Vault(configuration), store, "order", 1)]
        process_event(
            db,
            configuration,
            "customers/redact",
            row.shop_domain,
            {"customer": {"id": 100}, "orders_to_redact": []},
            NOW,
        )
        assert db.scalar(select(func.count()).select_from(CommerceEntry)) == 0
        assert db.get(CommerceSnapshot, snap["snapshot_id"]) is None
        erased = measurement(db, row.workspace_id, store.id, window(), now=NOW)
        assert erased["net_sales_micros"] is None
        assert "privacy_suppressed_source" in erased["reasons"]
        assert db.scalar(select(func.count()).select_from(CommerceDailyRevision)) == 0
        assert not apply_order(db, store, row, source(9), [agreement(9)], configuration, NOW)
        store_id, workspace_id = store.id, row.workspace_id
        ConnectionService(db, configuration).disconnect(workspace_id, "owner")
        # Recreate a native authorization without changing the stable verified shop identity.
        replacement = ShopifyConnection(
            workspace_id=workspace_id,
            shop_domain="renamed.myshopify.com",
            shop_name="Renamed",
            currency_code="USD",
            time_zone="UTC",
            encrypted_credentials="unused",
        )
        db.add(replacement)
        bind_shopify(db, replacement, reconnect=True)
        rebound = bind_store(db, replacement, "gid://shopify/Shop/123", configuration, NOW)
        assert rebound.id == store_id
        assert not apply_order(
            db, rebound, replacement, source(), [agreement()], configuration, NOW
        )


def test_tenant_and_connection_boundaries(customer_engine: Engine, configuration: Settings) -> None:
    with Session(customer_engine) as db:
        row, store = setup(db, configuration)
        other_row, other_store = setup(db, configuration, "beta")
        for native, canonical in ((row, store), (other_row, other_store)):
            apply_order(db, canonical, native, source(), [agreement()], configuration, NOW)
        assert identity_key(Vault(configuration), store, "order", 1) != identity_key(
            Vault(configuration), other_store, "order", 1
        )
        with pytest.raises(ShopifyError):
            measurement(db, row.workspace_id, other_store.id, window(), now=NOW)
        with pytest.raises(ShopifyError):
            apply_order(db, store, other_row, source(), [agreement()], configuration, NOW)
        registry = db.get(WorkspaceIntegration, row.workspace_integration_id)
        assert registry is not None
        registry.status = "revoked"
        db.flush()
        with pytest.raises(ShopifyError):
            apply_order(db, store, row, source(), [agreement()], configuration, NOW)


@pytest.mark.parametrize(
    "line,action,gross,tax",
    [
        ("ADJUSTMENT", "ORDER", "90", "0"),
        ("PRODUCT", "UNKNOWN", "90", "0"),
        ("PRODUCT", "ORDER", "-90", "0"),
        ("PRODUCT", "ORDER", "10", "11"),
        ("PRODUCT", "ORDER", "90", "-1"),
    ],
)
def test_unreconciled_is_never_complete(
    customer_engine: Engine, configuration: Settings, line: str, action: str, gross: str, tax: str
) -> None:
    with Session(customer_engine) as db:
        row, store = setup(db, configuration)
        apply_order(
            db,
            store,
            row,
            source(),
            [agreement(line=line, action=action, gross=gross, tax=tax)],
            configuration,
            NOW,
        )
        result = measurement(db, row.workspace_id, store.id, window(), now=NOW)
        assert result["net_sales_micros"] is None
        assert "unreconciled_source" in result["reasons"]


def test_window_validation_and_calendar_retention() -> None:
    with pytest.raises(ValueError):
        window(date(2026, 7, 1), date(2026, 10, 1))
    assert window(date(2026, 7, 1), date(2026, 10, 1), "cumulative").time_basis == "cumulative"
    with pytest.raises(ValueError):
        MeasurementWindow(
            start=date(2026, 9, 1),
            end=date(2026, 10, 1),
            time_basis="calendar_month",
            currency="USD",
            time_zone="Invalid/Zone",
        )
    assert retention_floor(datetime(2025, 3, 31, tzinfo=UTC)).date() == date(2024, 2, 29)


class FakeMeasurement(FakeShopify, MeasurementClient):
    def __init__(self, config: Settings, pages: list[Any]) -> None:
        super().__init__(config, pages)
        self.scope = ",".join(sorted(MEASUREMENT_SCOPES))
        self.facts = [agreement()]

    def measurement_orders(self, shop: str, token: str, cursor: str | None, query: str) -> Any:
        self.requests.append((shop, cursor, query))
        response = self.pages.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def agreements(self, shop: str, token: str, order_id: str) -> Any:
        return deepcopy(self.facts)


def test_import_pagination_failure_retry_and_history_scope(
    customer_engine: Engine, configuration: Settings
) -> None:
    with Session(customer_engine) as db:
        row, store = setup(db, configuration)
        store.covered_from, store.last_sync_at = None, None
        db.commit()
        client = FakeMeasurement(
            configuration,
            [
                ([source()], "page-2"),
                ShopifyError("commerce_incomplete_source"),
                ([source()], None),
            ],
        )
        service = CommerceSyncService(db, configuration, client)
        assert service.page(row.workspace_id, now=NOW)["status"] == "syncing"
        assert store.last_sync_at is None
        assert service.page(row.workspace_id, now=NOW)["status"] == "commerce_incomplete_source"
        assert store.cursor == "page-2" and store.last_sync_at is None
        assert service.page(row.workspace_id, now=NOW)["status"] == "retry_later"
        assert (
            service.page(row.workspace_id, now=NOW + timedelta(minutes=1))["status"] == "complete"
        )
        assert store.revision == 1
        assert "created_at" not in client.requests[0][2]
        assert (
            measurement(db, row.workspace_id, store.id, window(), now=NOW)["net_sales_micros"]
            == 90_000_000
        )
        bundle = Vault(configuration).open(
            row.workspace_id, row.shop_domain, row.encrypted_credentials
        )
        bundle["scopes"] = ["read_orders", "read_products"]
        bundle["expires_at"] = (NOW + timedelta(hours=3)).isoformat()
        row.encrypted_credentials = Vault(configuration).seal(
            row.workspace_id, row.shop_domain, bundle
        )
        db.commit()
        assert (
            service.page(row.workspace_id, now=NOW + timedelta(minutes=61))["status"]
            == "commerce_history_access_required"
        )


def test_postgres_concurrent_import_is_one_revision(
    customer_engine: Engine, configuration: Settings
) -> None:
    if customer_engine.dialect.name != "postgresql":
        return  # The SQLite arm is covered above; row-lock assertion requires PostgreSQL.
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    with Session(customer_engine) as db:
        row, store = setup(db, configuration)
        row_id, store_id = row.id, store.id
    barrier = Barrier(2)

    def import_order() -> bool:
        with Session(customer_engine) as db:
            native, canonical = db.get(ShopifyConnection, row_id), db.get(CommerceStore, store_id)
            assert native is not None and canonical is not None
            barrier.wait(timeout=10)
            changed = apply_order(
                db, canonical, native, source(), [agreement()], configuration, NOW
            )
            db.commit()
            return changed

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(import_order) for _ in range(2)]
        assert sorted(f.result(timeout=20) for f in futures) == [False, True]
    with Session(customer_engine) as db:
        canonical = db.get(CommerceStore, store_id)
        assert canonical is not None and canonical.revision == 1
        assert db.scalar(select(func.count()).select_from(CommerceEntry)) == 1


def test_calendar_dst_boundary_and_negative_edit(
    customer_engine: Engine, configuration: Settings
) -> None:
    with Session(customer_engine) as db:
        row, store = setup(db, configuration)
        store.time_zone = row.time_zone = "America/New_York"
        data = source(updated=NOW)
        data["createdAt"] = "2026-03-01T04:30:00Z"  # Still February in the verified store zone.
        facts = [
            agreement(when=datetime(2026, 3, 1, 4, 30, tzinfo=UTC)),
            agreement(2, "-11", "-1", "UPDATE", datetime(2026, 3, 9, 4, tzinfo=UTC)),
        ]
        apply_order(db, store, row, data, facts, configuration, NOW)
        march = MeasurementWindow(
            start=date(2026, 3, 1),
            end=date(2026, 4, 1),
            time_basis="calendar_month",
            currency="USD",
            time_zone=store.time_zone,
        )
        result = measurement(db, row.workspace_id, store.id, march, now=NOW)
        assert result["net_sales_micros"] == -10_000_000 and result["orders"] == 0
        with pytest.raises(ValueError):
            measurement(db, row.workspace_id, store.id, window(), now=NOW)


def test_old_order_current_refund_survives_raw_retention_and_late_erasure(
    customer_engine: Engine, configuration: Settings
) -> None:
    from app.shopify.privacy import purge_expired_facts

    with Session(customer_engine) as db:
        row, store = setup(db, configuration)
        old = source(updated=NOW)
        old["createdAt"] = "2024-01-01T00:00:00Z"
        facts = [
            agreement(when=datetime(2024, 1, 1, tzinfo=UTC)),
            agreement(2, "22", "2", "RETURN", CREATED),
        ]
        apply_order(db, store, row, old, facts, configuration, NOW)
        db.commit()
        wid, sid, shop = row.workspace_id, store.id, row.shop_domain
    purge_expired_facts(customer_engine, now=NOW)
    with Session(customer_engine) as db:
        assert measurement(db, wid, sid, window(), now=NOW)["net_sales_micros"] == -20_000_000
        ConnectionService(db, configuration).disconnect(wid, "owner")
        # Late authenticated erasure persists even without a native connection.
        process_event(db, configuration, "orders/delete", shop, {"id": 1}, NOW)
        from app.commerce.models import CommerceSuppression

        assert db.scalar(select(func.count()).select_from(CommerceSuppression)) == 1


def test_customer_commerce_api_isolation_and_csrf(
    customer_engine: Engine, configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.api.customer import router as auth_router
    from app.api.customer_commerce import router
    from app.customers.access import CSRF_COOKIE
    from app.customers.identity import get_identity_provider
    from app.customers.models import CustomerMembership
    from app.database.session import get_db
    from app.settings import settings
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from tests.test_customer_identity import ORIGIN, FakeProvider, login

    monkeypatch.setattr(settings, "customer_app_origin", ORIGIN)
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(router)

    def database() -> Generator[Session, None, None]:
        with Session(customer_engine) as db:
            yield db

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_identity_provider] = lambda: FakeProvider()
    client = TestClient(app, base_url=ORIGIN)
    user = login(client, "alice:1")
    with Session(customer_engine) as db:
        row, store = setup(db, configuration)
        other, _ = setup(db, configuration, "beta")
        db.add(
            CustomerMembership(
                user_id=user, workspace_id=row.workspace_id, role="owner", status="active"
            )
        )
        db.commit()
        prefix = f"/api/customer/v1/workspaces/{row.workspace_id}/commerce"
        path = prefix + f"/stores/{store.id}"
        other_prefix = f"/api/customer/v1/workspaces/{other.workspace_id}/commerce"
    headers = {"Origin": ORIGIN, "X-CSRF-Token": client.cookies[CSRF_COOKIE]}
    assert client.get(prefix + "/stores").status_code == 200
    assert client.get(other_prefix + "/stores").status_code == 404
    assert (
        client.post(path + "/snapshots", json=window().model_dump(mode="json")).status_code == 403
    )
    response = client.post(
        path + "/snapshots", json=window().model_dump(mode="json"), headers=headers
    )
    assert response.status_code == 201, response.text
    identifier = response.json()["snapshot_id"]
    assert client.get(prefix + "/snapshots/" + identifier).status_code == 200
    assert client.get(other_prefix + "/snapshots/" + identifier).status_code == 404
    with Session(customer_engine) as db:
        membership = db.scalar(select(CustomerMembership).where(CustomerMembership.user_id == user))
        assert membership is not None
        membership.role = "viewer"
        db.commit()
    assert (
        client.post(
            path + "/snapshots", json=window().model_dump(mode="json"), headers=headers
        ).status_code
        == 403
    )
    assert (
        client.post(
            path + "/preview", json=window().model_dump(mode="json"), headers=headers
        ).status_code
        == 200
    )


def test_source_paginates_sales_in_exact_agreement_and_bounds_cycles(
    configuration: Settings,
) -> None:
    from app.commerce.source import MeasurementClient

    class Client(MeasurementClient):
        def __init__(self, responses: list[dict[str, Any]]) -> None:
            super().__init__(configuration)
            self.responses = responses
            self.variables: list[dict[str, Any]] = []

        def _query(
            self, shop: str, token: str, query: str, variables: dict[str, Any]
        ) -> dict[str, Any]:
            self.variables.append(variables)
            return self.responses.pop(0)

    def page(
        nodes: list[dict[str, Any]], more: bool = False, cursor: str | None = None
    ) -> dict[str, Any]:
        return {"nodes": nodes, "pageInfo": {"hasNextPage": more, "endCursor": cursor}}

    first, second = agreement(action="RETURN"), agreement(2, action="RETURN")
    first["refund"] = {"processedAt": "2026-10-02T00:00:00Z"}
    initial = {**first, "sales": page(first["sales"], True, "sales-2")}
    extra = {"id": first["id"], "sales": page(second["sales"])}
    client = Client(
        [{"order": {"agreements": page([initial])}}, {"order": {"agreements": {"nodes": [extra]}}}]
    )
    imported = client.agreements("unused", "unused", source()["id"])[0]
    assert len(imported["sales"]) == 2
    assert imported["__typename"] == "RefundAgreement"
    assert imported["reason"] == "REFUND"
    assert imported["refund"] == first["refund"]
    assert client.variables[1]["agreementBefore"] is None
    mismatch = Client(
        [
            {"order": {"agreements": page([initial])}},
            {"order": {"agreements": {"nodes": [{**extra, "id": second["id"]}]}}},
        ]
    )
    with pytest.raises(ShopifyError, match="commerce_incomplete_source"):
        mismatch.agreements("unused", "unused", source()["id"])
    repeated = {
        "order": {"agreements": page([{**first, "sales": page(first["sales"])}], True, "same")}
    }
    cycle = Client([repeated, repeated])
    with pytest.raises(ShopifyError, match="commerce_source_page_limit"):
        cycle.agreements("unused", "unused", source()["id"])


def test_oauth_requires_verified_history_and_customer_scopes(
    customer_engine: Engine, configuration: Settings
) -> None:
    from urllib.parse import parse_qs, urlsplit

    from tests.test_unified_outcome_data import seed_workspace

    class VerifiedShop(FakeMeasurement):
        def shop(self, shop: str, token: str) -> dict[str, Any]:
            result = super().shop(shop, token)
            result["shop"]["id"] = "gid://shopify/Shop/123"
            return result

    with Session(customer_engine) as db:
        configuration.shopify_measurement_enabled = True
        workspace, _, _ = seed_workspace(db, "oauth")
        db.commit()
        client = VerifiedShop(configuration, [])
        service = ConnectionService(db, configuration, client)
        url = service.begin(workspace.id, "oauth.myshopify.com", "owner", NOW)
        params = parse_qs(urlsplit(url).query)
        assert set(params["scope"][0].split(",")) == MEASUREMENT_SCOPES
        state = service.pending(
            {"state": params["state"][0], "shop": "oauth.myshopify.com"}, "owner", NOW
        )
        row = service.finish(state, "offline", "owner", NOW)
        assert row.commerce_store_id is not None
        assert db.get(CommerceStore, row.commerce_store_id) is not None
        client.scope = "read_orders,read_products"
        url = service.begin(workspace.id, "oauth.myshopify.com", "owner", NOW)
        state = service.pending(
            {"state": parse_qs(urlsplit(url).query)["state"][0], "shop": "oauth.myshopify.com"},
            "owner",
            NOW,
        )
        with pytest.raises(ShopifyError, match="shopify_store_verification_failed"):
            service.finish(state, "offline", "owner", NOW)


def test_failed_page_does_not_publish_partial_revision(
    customer_engine: Engine, configuration: Settings
) -> None:
    with Session(customer_engine) as db:
        row, store = setup(db, configuration)
        store.covered_from, store.last_sync_at = None, None
        db.commit()
        # Reused sale identity on a different order must roll back the entire page.
        client = FakeMeasurement(configuration, [([source(), source(2)], None)])
        result = CommerceSyncService(db, configuration, client).page(row.workspace_id, now=NOW)
        assert result["status"] == "commerce_sale_identity_conflict"
        assert db.scalar(select(func.count()).select_from(CommerceEntry)) == 0
        assert db.scalar(select(func.count()).select_from(CommerceOrder)) == 0
        assert store.revision == 0 and store.last_sync_at is None


def test_late_old_domain_erasure_reaches_reconnected_store(
    customer_engine: Engine, configuration: Settings
) -> None:
    from app.shopify.models import ShopifyTombstone
    from app.shopify.normalize import order_key

    with Session(customer_engine) as db:
        row, store = setup(db, configuration)
        old_domain, workspace_id = row.shop_domain, row.workspace_id
        apply_order(db, store, row, source(), [agreement()], configuration, NOW)
        db.commit()
        ConnectionService(db, configuration).disconnect(workspace_id, "owner")
        replacement = ShopifyConnection(
            workspace_id=workspace_id,
            shop_domain="renamed.myshopify.com",
            shop_name="Renamed",
            currency_code="USD",
            time_zone="UTC",
            encrypted_credentials="unused",
            connected_at=NOW,
        )
        db.add(replacement)
        bind_shopify(db, replacement, reconnect=True)
        rebound = bind_store(db, replacement, "gid://shopify/Shop/123", configuration, NOW)
        apply_order(db, rebound, replacement, source(), [agreement()], configuration, NOW)
        db.commit()
        process_event(db, configuration, "orders/delete", old_domain, {"id": 1}, NOW)
        assert db.scalar(select(func.count()).select_from(CommerceEntry)) == 0
        assert (
            db.get(
                ShopifyTombstone, (replacement.id, order_key(Vault(configuration), replacement, 1))
            )
            is not None
        )
        assert not apply_order(
            db, rebound, replacement, source(), [agreement()], configuration, NOW
        )
        process_event(
            db, configuration, "app/uninstalled", old_domain, {}, NOW - timedelta(seconds=1)
        )
        assert db.get(ShopifyConnection, replacement.id) is not None


def test_customer_erasure_covers_legacy_facts_and_reconnect_replay(
    customer_engine: Engine, configuration: Settings
) -> None:
    from app.shopify.models import ShopifyOrder
    from app.shopify.sync import ShopifySyncService

    from tests.test_shopify_sales import order as legacy_order
    from tests.test_shopify_sales import page

    with Session(customer_engine) as db:
        row, store = setup(db, configuration)
        apply_order(db, store, row, source(), [agreement()], configuration, NOW)
        db.commit()
        client = FakeShopify(
            configuration,
            [page(legacy_order(1, createdAt=CREATED.isoformat(), updatedAt=NOW.isoformat()))],
        )
        assert (
            ShopifySyncService(db, configuration, client).page(row.workspace_id, now=NOW)["status"]
            == "complete"
        )
        assert db.scalar(select(func.count()).select_from(ShopifyOrder)) == 1
        process_event(
            db,
            configuration,
            "customers/data_request",
            row.shop_domain,
            {"customer": {"id": 100}, "orders_requested": [], "data_request": {"id": 98}},
            NOW,
        )
        request = db.scalar(select(ShopifyPrivacyRequest))
        assert request is not None and len(request.order_keys) == 1
        process_event(
            db,
            configuration,
            "customers/redact",
            row.shop_domain,
            {"customer": {"id": 100}, "orders_to_redact": []},
            NOW,
        )
        assert db.scalar(select(func.count()).select_from(ShopifyOrder)) == 0
        workspace_id, domain, authorization = (
            row.workspace_id,
            row.shop_domain,
            row.encrypted_credentials,
        )
        ConnectionService(db, configuration).disconnect(workspace_id, "owner")
        replacement = ShopifyConnection(
            workspace_id=workspace_id,
            shop_domain=domain,
            shop_name="Reauthorized",
            currency_code="USD",
            time_zone="UTC",
            encrypted_credentials=authorization,
            connected_at=NOW,
        )
        db.add(replacement)
        bind_shopify(db, replacement, reconnect=True)
        bind_store(db, replacement, "gid://shopify/Shop/123", configuration, NOW)
        db.commit()
        replay = FakeShopify(configuration, [page(legacy_order(1))])
        assert (
            ShopifySyncService(db, configuration, replay).page(workspace_id, now=NOW)["status"]
            == "shopify_privacy_reconciliation_required"
        )
        assert replay.requests == []
        assert db.scalar(select(func.count()).select_from(ShopifyOrder)) == 0


def test_disabling_measurement_does_not_bypass_erasure_on_oauth_reconnect(
    customer_engine: Engine, configuration: Settings
) -> None:
    from urllib.parse import parse_qs, urlsplit

    from app.shopify.sync import ShopifySyncService

    class LegacyOAuth(FakeShopify):
        def shop(self, shop: str, token: str) -> dict[str, Any]:
            value = super().shop(shop, token)
            value["shop"]["id"] = "gid://shopify/Shop/123"
            return value

    with Session(customer_engine) as db:
        row, store = setup(db, configuration)
        apply_order(db, store, row, source(), [agreement()], configuration, NOW)
        db.commit()
        workspace_id, store_id = row.workspace_id, store.id
        process_event(
            db,
            configuration,
            "customers/redact",
            row.shop_domain,
            {"customer": {"id": 100}, "orders_to_redact": [1]},
            NOW,
        )
        ConnectionService(db, configuration).disconnect(workspace_id, "owner")
        configuration.shopify_measurement_enabled = False
        client = LegacyOAuth(configuration)
        service = ConnectionService(db, configuration, client)
        url = service.begin(workspace_id, "renamed.myshopify.com", "owner", NOW)
        query = parse_qs(urlsplit(url).query)
        assert set(query["scope"][0].split(",")) == {"read_orders", "read_products"}
        state = service.pending(
            {"state": query["state"][0], "shop": "renamed.myshopify.com"}, "owner", NOW
        )
        restored = service.finish(state, "offline-code", "owner", NOW)
        assert restored.commerce_store_id == store_id
        result = ShopifySyncService(db, configuration, client).page(workspace_id, now=NOW)
        assert result["status"] == "shopify_privacy_reconciliation_required"
        assert client.requests == []


def test_privacy_migration_backfills_existing_measurement_identity(
    customer_engine: Engine, configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alembic import command
    from alembic.config import Config
    from app.commerce.models import CommerceShopAlias
    from app.settings import settings
    from app.shopify.models import ShopifyOrder
    from app.shopify.normalize import normalized_order
    from sqlalchemy import text

    from tests.test_shopify_sales import order as legacy_order

    with Session(customer_engine) as db:
        row, store = setup(db, configuration)
        apply_order(db, store, row, source(), [agreement()], configuration, NOW)
        values = normalized_order(db, row, legacy_order(1), Vault(configuration))
        legacy = ShopifyOrder(connection_id=row.id, workspace_id=row.workspace_id, **values)
        db.add(legacy)
        db.commit()
        sid, domain, legacy_id = store.id, row.shop_domain, legacy.id
        expected_key = identity_key(Vault(configuration), store, "order", 1)
        assert db.get(CommerceShopAlias, (domain, sid)) is not None
    if customer_engine.dialect.name != "postgresql":
        return  # Schema migration target is PostgreSQL; both dialects verify binding above.
    with customer_engine.connect() as connection:
        schema = connection.scalar(text("SELECT current_schema()"))
    scoped = customer_engine.url.update_query_dict({"options": f"-csearch_path={schema}"})
    monkeypatch.setattr(settings, "database_url", scoped.render_as_string(hide_password=False))
    config = Config("alembic.ini")
    command.stamp(config, "head")
    command.downgrade(config, "20261005_0023")
    command.upgrade(config, "head")
    with Session(customer_engine) as db:
        restored_legacy = db.get(ShopifyOrder, legacy_id)
        assert restored_legacy is not None and restored_legacy.commerce_order_key == expected_key
        assert db.get(CommerceShopAlias, (domain, sid)) is not None


def test_retention_preserves_recent_unreconciled_old_order(
    customer_engine: Engine, configuration: Settings
) -> None:
    with Session(customer_engine) as db:
        row, store = setup(db, configuration)
        old = source(updated=NOW)
        old["createdAt"] = "2024-01-01T00:00:00Z"
        apply_order(db, store, row, old, [agreement(line="ADJUSTMENT")], configuration, NOW)
        db.commit()
        purge_measurements(db, NOW)
        result = measurement(db, row.workspace_id, store.id, window(), now=NOW)
        assert result["net_sales_micros"] is None
        assert "unreconciled_source" in result["reasons"]
        purge_measurements(db, NOW + timedelta(days=410))
        assert db.scalar(select(func.count()).select_from(CommerceOrder)) == 0
