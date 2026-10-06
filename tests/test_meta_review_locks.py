"""PostgreSQL barriers exercise complete review versus native Meta lifecycle paths."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from typing import Any

import pytest
from app.campaign_review import service as review
from app.campaign_review.contracts import RevisionInput
from app.mandates import service as mandates
from app.mandates.schemas import AccountScope
from app.meta.models import MetaConnection
from app.meta.service import ConnectionService
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, event, select
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_google_action_plans import setup
from tests.test_meta_connection import FakeMeta
from tests.test_meta_connection import configuration as meta_settings
from tests.test_shopify_sales import configuration as configuration

meta_configuration = meta_settings


def authorized(db: Session, config: Settings, wid: int, fake: FakeMeta) -> ConnectionService:
    from urllib.parse import parse_qs, urlsplit

    service = ConnectionService(db, config, fake)
    query = parse_qs(urlsplit(service.begin(wid, "owner-session", NOW)).query)
    state = service.pending({"state": query["state"][0]}, "owner-session", NOW)
    service.finish(state, "offline-code", "owner", NOW)
    return service


def review_fixture(
    db: Session, configuration: Settings, meta_configuration: Settings
) -> tuple[int, RevisionInput]:
    mandate, _, _ = setup(db, configuration)
    service = authorized(db, meta_configuration, mandate.workspace_id, FakeMeta(meta_configuration))
    connection = service.select_account(
        mandate.workspace_id, "owner-session", "101", "purchase", "owner", NOW
    )
    policy = mandates.policy(db, mandate)
    policy.accounts = [
        AccountScope(
            platform="meta_ads",
            connection_id=connection.workspace_integration_id or 0,
            account_id=connection.account_id,
        )
    ]
    mandates.edit(db, mandate, mandate.revision, policy, "owner", NOW)
    mandates.approve(db, mandate, mandate.revision, "owner", NOW)
    body = RevisionInput(
        account=policy.accounts[0],
        mandate_id=mandate.id,
        mandate_revision=mandate.revision,
        currency="USD",
        budget_micros=60,
        starts_at=NOW,
        ends_at=NOW + timedelta(hours=1),
        content={
            "kind": "meta_website_sales_image_v1",
            "objective": "website_sales",
            "name": "Fixture",
            "landing_page": "https://example.invalid/shop",
            "audience": {"countries": ["US"], "languages": ["en"]},
            "headline": "Shop",
            "text": "Supplied",
            "call_to_action": "SHOP_NOW",
            "media": {"media_id": "b" * 32, "sha256": "a" * 64},
        },
    )
    db.commit()
    # Grant creation precedes account selection, just as the dashboard flow does.
    authorized(db, meta_configuration, mandate.workspace_id, FakeMeta(meta_configuration))
    return mandate.workspace_id, body


@pytest.mark.parametrize("operation", ["disconnect", "reauthorize"])
def test_review_native_meta_lock_order(
    customer_engine: Engine,
    configuration: Settings,
    meta_configuration: Settings,
    operation: str,
) -> None:
    if customer_engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL row-lock ordering")
    with Session(customer_engine) as db:
        wid, body = review_fixture(db, configuration, meta_configuration)
    scope_locked, lifecycle_reached, release = Event(), Event(), Event()

    def before_sql(
        conn: Any, cursor: Any, statement: str, parameters: Any, context: Any, many: bool
    ) -> None:
        if (
            conn.info.get("lock_test_role") == "lifecycle"
            and "FROM workspaces" in statement
            and "FOR " in statement
        ):
            lifecycle_reached.set()  # Fixed path waits here before acquiring native/grant locks.

    def after_sql(
        conn: Any, cursor: Any, statement: str, parameters: Any, context: Any, many: bool
    ) -> None:
        role = conn.info.get("lock_test_role")
        if (
            role == "review"
            and "FROM advertising_accounts" in statement
            and "FOR UPDATE" in statement
            and not scope_locked.is_set()
        ):
            scope_locked.set()
            assert release.wait(10)
        if (
            role == "lifecycle"
            and "FROM meta_connections" in statement
            and "FOR UPDATE" in statement
        ):
            lifecycle_reached.set()  # Baseline has already acquired the conflicting native lock.

    def inspect_review() -> str:
        with Session(customer_engine) as db:
            db.connection().info["lock_test_role"] = "review"
            try:
                # Customer/dashboard authorization performs only reads before this service path.
                result = review.binding(db, wid, body, NOW)
                db.commit()
                return result
            finally:
                db.connection().info.pop("lock_test_role", None)

    def mutate() -> None:
        with Session(customer_engine) as db:
            db.connection().info["lock_test_role"] = "lifecycle"
            try:
                service = ConnectionService(db, meta_configuration, FakeMeta(meta_configuration))
                if operation == "disconnect":
                    service.disconnect(wid, "owner")
                else:
                    service.select_account(wid, "owner-session", "101", "purchase", "owner", NOW)
            finally:
                db.rollback()
                db.connection().info.pop("lock_test_role", None)

    event.listen(customer_engine, "before_cursor_execute", before_sql)
    event.listen(customer_engine, "after_cursor_execute", after_sql)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(inspect_review)
            assert scope_locked.wait(10)
            second = pool.submit(mutate)
            try:
                assert lifecycle_reached.wait(10)
            finally:
                release.set()
            assert first.result(timeout=15).endswith(":1")
            second.result(timeout=15)
    finally:
        release.set()
        event.remove(customer_engine, "before_cursor_execute", before_sql)
        event.remove(customer_engine, "after_cursor_execute", after_sql)
    with Session(customer_engine) as db:
        row = db.scalar(select(MetaConnection).where(MetaConnection.workspace_id == wid))
        if operation == "disconnect":
            assert row is None
            with pytest.raises(HTTPException):
                review.binding(db, wid, body, NOW)
        else:
            assert row is not None and row.generation == 2
            assert review.binding(db, wid, body, NOW).endswith(":2")
