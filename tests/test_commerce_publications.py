"""Real terminal importer and scoped privacy publication acceptance, no live calls."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from typing import Any

import pytest
from app.api.customer_commerce import router
from app.commerce.evidence import (
    digest,
    read_publication,
    workspace_privacy_stamp,
)
from app.commerce.ledger import bind_store, retention_floor
from app.commerce.models import CommerceEvidenceState, CommerceMeasurementPublication
from app.commerce.privacy import purge_measurements
from app.commerce.sync import CommerceSyncService
from app.customers.models import CustomerMembership
from app.lifecycle.inventory import verify_registry
from app.lifecycle.privacy import workspace_export_revision
from app.settings import Settings
from app.shopify.privacy import process_event
from app.shopify.security import ShopifyError
from app.shopify.service import ConnectionService
from app.workspaces.models import Workspace
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW, FakeMeasurement, setup, source
from tests.test_customer_identity import (
    FakeProvider,
    login,
)
from tests.test_customer_identity import (
    customer_engine as customer_engine,
)
from tests.test_customer_identity import (
    replicas as replicas,
)
from tests.test_shopify_sales import SHOP
from tests.test_shopify_sales import configuration as configuration


def complete(db: Session, config: Settings, *, slug: str = "alpha") -> tuple[int, str, str]:
    row, store = setup(db, config, slug)
    store.last_sync_at = None
    db.commit()
    result = CommerceSyncService(db, config, FakeMeasurement(config, [([source()], None)])).page(
        row.workspace_id, now=NOW
    )
    assert result["status"] == "complete"
    pub = db.scalar(
        select(CommerceMeasurementPublication).where(
            CommerceMeasurementPublication.store_id == store.id
        )
    )
    assert pub is not None
    return row.workspace_id, store.id, pub.id


def test_terminal_publication_real_values_zero_and_correction(
    customer_engine: Engine, configuration: Settings
) -> None:
    with Session(customer_engine) as db:
        row, store = setup(db, configuration)
        store.last_sync_at = None
        db.commit()
        importer = CommerceSyncService(
            db, configuration, FakeMeasurement(configuration, [([source()], "next"), ([], None)])
        )
        assert importer.page(row.workspace_id, now=NOW)["status"] == "syncing"
        assert db.scalar(select(func.count()).select_from(CommerceMeasurementPublication)) == 0
        assert importer.page(row.workspace_id, now=NOW)["status"] == "complete"
        result = read_publication(db, row.workspace_id, store.id, now=NOW)
        manifest = result["manifest"]
        days = {p["day"]: p for p in manifest["partitions"]}
        assert days["2026-09-10"]["net_sales_micros"] == 90_000_000
        assert days["2026-09-11"] == {
            "day": "2026-09-11",
            "state": "complete_zero",
            "net_sales_micros": 0,
            "entry_count": 0,
        }
        assert manifest["maturity"] == "unavailable"
        assert result["comparison_available"] is False
        assert manifest["attribution"] == "not_applicable_store_total"
        before = result["manifest_digest"]
        db.commit()
        later = NOW + timedelta(minutes=60)
        revised = FakeMeasurement(configuration, [([source(updated=later)], None)])
        revised.facts[0]["sales"][0]["totalAmount"]["shopMoney"]["amount"] = "109"
        assert (
            CommerceSyncService(db, configuration, revised).page(row.workspace_id, now=later)[
                "status"
            ]
            == "complete"
        )
        updated = read_publication(db, row.workspace_id, store.id, now=NOW)
        assert updated["manifest_digest"] != before
        assert updated["manifest"]["predecessor_digest"] == before
        assert (
            read_publication(db, row.workspace_id, store.id, result["publication_id"], now=NOW)[
                "manifest_digest"
            ]
            == before
        )
        assert digest(manifest) == before
        verify_registry()


def test_erasure_closing_owner_disconnect_rebind_and_retention(
    customer_engine: Engine, configuration: Settings
) -> None:
    with Session(customer_engine) as db:
        wid, sid, pid = complete(db, configuration)
        stamp = workspace_privacy_stamp(db, wid)
        export_revision = workspace_export_revision(db, wid)
        owner = db.get(Workspace, wid)
        assert owner is not None
        owner.status = "closing"
        db.commit()
        with pytest.raises(ShopifyError):
            read_publication(db, wid, sid, now=NOW)
        process_event(db, configuration, "orders/delete", SHOP, {"id": 1}, NOW)
        assert db.get(CommerceMeasurementPublication, pid) is None
        assert workspace_privacy_stamp(db, wid) != stamp
        assert workspace_export_revision(db, wid) > export_revision
        assert db.get(Workspace, wid).status == "closing"  # type: ignore[union-attr]
        db.rollback()
    with Session(customer_engine) as db:
        wid2, sid2, pid2 = complete(db, configuration, slug="beta")
        before = db.get(CommerceEvidenceState, sid2)
        assert before is not None
        generation = before.generation
        export_revision = workspace_export_revision(db, wid2)
        row = ConnectionService(db, configuration).get(wid2)
        assert row is not None
        bind_store(db, row, "gid://shopify/Shop/123", configuration, NOW + timedelta(hours=1))
        db.commit()
        assert db.get(CommerceMeasurementPublication, pid2) is None
        assert db.get(CommerceEvidenceState, sid2).generation > generation  # type: ignore[union-attr]
        assert workspace_export_revision(db, wid2) > export_revision
        export_revision = workspace_export_revision(db, wid2)
        ConnectionService(db, configuration).disconnect(wid2, "owner")
        assert workspace_export_revision(db, wid2) > export_revision
        assert db.scalar(select(func.count()).select_from(CommerceMeasurementPublication)) == 0
    with Session(customer_engine) as db:
        wid3, sid3, pid3 = complete(db, configuration, slug="gamma")
        stamp3 = workspace_privacy_stamp(db, wid3)
        export_revision = workspace_export_revision(db, wid3)
        purge_measurements(db, NOW + timedelta(days=2))
        db.commit()
        assert db.get(CommerceMeasurementPublication, pid3) is None
        assert workspace_privacy_stamp(db, wid3) != stamp3
        assert workspace_export_revision(db, wid3) > export_revision


def test_owned_read_route_logout_and_scope(
    customer_engine: Engine,
    configuration: Settings,
    replicas: tuple[TestClient, TestClient, FakeProvider],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import datetime

    class Clock(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> "Clock":
            return cls.fromtimestamp(NOW.timestamp(), tz=tz)

    monkeypatch.setattr("app.commerce.evidence.datetime", Clock)
    alice, bob, _ = replicas
    alice.app.include_router(router)  # type: ignore[attr-defined]
    bob.app.include_router(router)  # type: ignore[attr-defined]
    aid, bid = login(alice, "publication-alice:1"), login(bob, "publication-bob:1")
    with Session(customer_engine) as db:
        wid, sid, pid = complete(db, configuration)
        db.add(CustomerMembership(user_id=aid, workspace_id=wid, role="owner", status="active"))
        db.commit()
    route = f"/api/customer/v1/workspaces/{wid}/commerce/stores/{sid}/publications/{pid}"
    response = alice.get(route)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert bob.get(route).status_code == 404
    alice.cookies.clear()
    assert alice.get(route).status_code == 401
    assert aid != bid


def test_privacy_commit_fences_other_replica(
    customer_engine: Engine, configuration: Settings
) -> None:
    if customer_engine.dialect.name != "postgresql":
        pytest.skip("row locking requires PostgreSQL")
    with Session(customer_engine) as db:
        wid, sid, pid = complete(db, configuration)
    started, done = Event(), Event()

    def erase() -> None:
        with Session(customer_engine) as writer:
            writer.execute(text("SET LOCAL lock_timeout = '5s'"))
            started.set()
            process_event(writer, configuration, "orders/delete", SHOP, {"id": 1}, NOW)
            done.set()

    with ThreadPoolExecutor(max_workers=1) as pool, Session(customer_engine) as reader:
        read_publication(reader, wid, sid, pid, now=NOW)
        old_stamp = workspace_privacy_stamp(reader, wid)
        future = pool.submit(erase)
        assert started.wait(2)
        assert not done.wait(0.15)
        reader.commit()
        future.result(timeout=8)
        assert workspace_privacy_stamp(reader, wid) != old_stamp
        with pytest.raises(ShopifyError):
            read_publication(reader, wid, sid, pid, now=NOW)


def test_missing_history_is_not_zero_and_tamper_fails(
    customer_engine: Engine, configuration: Settings
) -> None:
    from app.commerce.evidence import publish
    from app.commerce.models import CommerceStore

    with Session(customer_engine) as db:
        wid, sid, _ = complete(db, configuration)
        store = db.get(CommerceStore, sid)
        fence = db.get(CommerceEvidenceState, sid)
        assert store is not None and fence is not None
        fence.history_from = None
        item = publish(
            db,
            store,
            NOW - timedelta(days=1),
            NOW + timedelta(minutes=1),
            NOW + timedelta(minutes=1),
            "test",
        )
        assert all(
            p["state"] == "missing" and p["net_sales_micros"] is None
            for p in item.manifest["partitions"]
        )
        item.manifest = {**item.manifest, "currency": "EUR"}
        db.flush()
        with pytest.raises(ShopifyError, match="commerce_publication_invalid"):
            read_publication(db, wid, sid, item.id, now=NOW)
        assert retention_floor(NOW) < NOW


def test_terminal_failure_rolls_back_and_empty_complete_is_zero(
    customer_engine: Engine, configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.commerce.evidence as evidence

    with Session(customer_engine) as db:
        row, store = setup(db, configuration)
        store.last_sync_at = None
        db.commit()
        original = evidence.publish

        def fail(*args: Any, **kwargs: Any) -> Any:
            original(*args, **kwargs)
            raise ValueError("synthetic terminal rollback")

        monkeypatch.setattr(evidence, "publish", fail)
        importer = CommerceSyncService(
            db, configuration, FakeMeasurement(configuration, [([source()], None)])
        )
        assert importer.page(row.workspace_id, now=NOW)["status"] == "commerce_invalid_source"
        assert db.scalar(select(CommerceMeasurementPublication.id)) is None
        monkeypatch.setattr(evidence, "publish", original)
        next_time = NOW + timedelta(minutes=2)
        assert (
            CommerceSyncService(
                db, configuration, FakeMeasurement(configuration, [([], None)])
            ).page(row.workspace_id, now=next_time)["status"]
            == "complete"
        )
        result = read_publication(db, row.workspace_id, store.id, now=NOW)
        assert all(p["state"] == "complete_zero" for p in result["manifest"]["partitions"])
        with pytest.raises(ShopifyError, match="commerce_publication_outside_retention"):
            read_publication(db, row.workspace_id, store.id, now=NOW + timedelta(days=2))


def test_publication_local_day_dst_and_idempotent_completion(
    customer_engine: Engine,
    configuration: Settings,
) -> None:
    from datetime import UTC, datetime

    from app.commerce.evidence import publish
    from app.commerce.models import CommerceEntry, CommerceOrder

    with Session(customer_engine) as db:
        row, store = setup(db, configuration)
        store.time_zone = "America/New_York"
        end = datetime(2026, 11, 3, 12, tzinfo=UTC)
        db.add(
            CommerceOrder(
                store_id=store.id,
                workspace_id=row.workspace_id,
                order_key="f" * 64,
                privacy_key="e" * 64,
                created_at=end - timedelta(days=2),
                source_updated_at=end,
                fingerprint="d" * 64,
                quality="complete",
            )
        )
        db.flush()
        for i, hour in enumerate((5, 6)):
            db.add(
                CommerceEntry(
                    store_id=store.id,
                    order_key="f" * 64,
                    entry_key=str(i) * 64,
                    happened_at=datetime(2026, 11, 1, hour, 30, tzinfo=UTC),
                    currency="USD",
                    net_micros=10_000_000,
                    action="ORDER",
                )
            )
        db.flush()
        item = publish(db, store, retention_floor(end, store.time_zone), end, end, "test")
        days = {p["day"]: p for p in item.manifest["partitions"]}
        assert days["2026-11-01"]["net_sales_micros"] == 20_000_000
        assert (
            publish(db, store, retention_floor(end, store.time_zone), end, end, "test").id
            == item.id
        )
        assert db.scalar(select(func.count()).select_from(CommerceMeasurementPublication)) == 1
