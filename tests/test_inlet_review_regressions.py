"""Independent review counterexamples: real API transactions and persisted drafts."""

import io
import logging
from collections.abc import Generator
from datetime import date, datetime
from types import SimpleNamespace as NS
from typing import Literal
from unittest.mock import Mock

import pytest
from app.billing.contracts import CheckoutResult, CheckoutState, SubscriptionState
from app.customers.models import CustomerMembership
from app.executors import google_actions as g
from app.mandates import service as m
from app.mandates.models import Mandate, MandateAction
from app.mandates.schemas import ActionDraft, ClaimInput
from app.settings import Settings, settings
from fastapi import HTTPException
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_google_action_plans import setup as google_setup
from tests.test_mandates import draft, evidence, seed
from tests.test_shopify_sales import configuration as configuration
from tests.test_tiktok_sources import configured as configured


@pytest.mark.parametrize("observed", [50, 110])
def test_rejected_api_claim_preserves_highwater_without_reservation(
    customer_engine: Engine,
    configuration: Settings,
    monkeypatch: pytest.MonkeyPatch,
    observed: int,
) -> None:
    from app.api import customer_mandates as api
    from app.api.customer import router as auth_router
    from app.customers.access import CSRF_COOKIE
    from app.customers.identity import get_identity_provider
    from app.database.session import get_db
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from tests.test_customer_identity import ORIGIN, FakeProvider, login

    clock = Mock()
    clock.now.return_value = NOW
    monkeypatch.setattr(api, "datetime", clock)
    monkeypatch.setattr(settings, "customer_app_origin", ORIGIN)
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(api.router)

    def database() -> Generator[Session, None, None]:
        with Session(customer_engine) as db:
            yield db  # Rejected requests close without any artificial commit.

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_identity_provider] = lambda: FakeProvider()
    client = TestClient(app, base_url=ORIGIN)
    uid = login(client, "owner:1")
    with Session(customer_engine) as db:
        mandate = seed(db, configuration)
        action = draft(db, mandate)
        wid, mid, aid = mandate.workspace_id, mandate.id, action.id
        db.add(CustomerMembership(user_id=uid, workspace_id=wid, role="owner", status="active"))
        db.commit()
        high = ClaimInput(request_key="high-observation", evidence=evidence(db, mandate, observed))
        lower = ClaimInput(request_key="lower-observation", evidence=evidence(db, mandate, 10))
    path = f"/api/customer/v1/workspaces/{wid}/mandates/{mid}/actions/{aid}/simulate/claim"
    headers = {"Origin": ORIGIN, "X-CSRF-Token": client.cookies[CSRF_COOKIE]}
    assert client.post(path, headers=headers, json=high.model_dump(mode="json")).status_code == 409
    with Session(customer_engine) as db:
        saved, saved_action = db.get(Mandate, mid), db.get(MandateAction, aid)
        assert saved is not None and saved_action is not None
        assert saved.observed_micros == observed
        assert saved.reserved_micros == saved.actions_used == saved.changes_used == 0
        assert (
            saved_action.state == "eligible"
            and saved_action.fence is None
            and saved_action.request_key is None
        )
    assert client.post(path, headers=headers, json=lower.model_dump(mode="json")).status_code == 409


@pytest.mark.parametrize(
    "field,value",
    [
        ("kind", "pause"),
        ("exposure_micros", 0),
        ("positive_change_micros", 0),
        ("resource_key", "google-campaign:999"),
    ],
)
@pytest.mark.retained_execution
@pytest.mark.usefixtures("retained_execution_engine")
def test_generic_persisted_draft_cannot_mislabel_google_operation(
    customer_engine: Engine,
    configuration: Settings,
    field: str,
    value: str | int,
) -> None:
    with Session(customer_engine) as db:
        mandate, scope, state = google_setup(db, configuration)
        original = g.prepare(
            db,
            mandate,
            scope,
            state,
            g.GoogleChange(kind="budget_change", new_budget_micros=20, modeled_exposure_micros=60),
            "owner",
            NOW,
        )
        body = ActionDraft.model_validate(original.draft).model_copy(update={field: value})
        # Same generic draft entry point used by the customer API, with a valid payload hash.
        forged = m.draft(db, mandate, body, "owner", NOW)
        db.commit()
        adapter = g.FixtureGoogleActions({"1": state})
        with pytest.raises(HTTPException):
            g.run_fixture(
                db, mandate, forged, adapter, evidence(db, mandate), "forged-request", "owner", NOW
            )
        assert adapter.calls == 0 and mandate.reserved_micros == 0


@pytest.mark.retained_execution
@pytest.mark.usefixtures("retained_execution_engine")
def test_stale_executor_session_cannot_overwrite_existing_reservation(
    customer_engine: Engine,
    configuration: Settings,
) -> None:
    with Session(customer_engine) as db:
        mandate, scope, state = google_setup(db, configuration)
        change = g.GoogleChange(
            kind="budget_change", new_budget_micros=20, modeled_exposure_micros=60
        )
        first = g.prepare(db, mandate, scope, state, change, "owner", NOW)
        other_state = state.model_copy(update={"campaign_id": "3", "budget_id": "4"})
        second = g.prepare(db, mandate, scope, other_state, change, "owner", NOW)
        mid, aid, bid = mandate.id, first.id, second.id
    adapter = g.FixtureGoogleActions({"1": state, "3": other_state})
    with Session(customer_engine) as stale:
        cached, pending = stale.get(Mandate, mid), stale.get(MandateAction, bid)
        assert cached is not None and pending is not None and cached.reserved_micros == 0
        sample = evidence(stale, cached)
        with Session(customer_engine) as fresh:
            current, action = fresh.get(Mandate, mid), fresh.get(MandateAction, aid)
            assert current is not None and action is not None
            g.run_fixture(fresh, current, action, adapter, sample, "first-attempt", "owner", NOW)
        with pytest.raises(HTTPException):
            g.run_fixture(stale, cached, pending, adapter, sample, "second-attempt", "owner", NOW)
        stale.rollback()
    with Session(customer_engine) as db:
        saved = db.get(Mandate, mid)
        assert saved is not None and saved.reserved_micros == 60 and saved.actions_used == 1
    assert adapter.calls == 1


@pytest.mark.parametrize("size", [1001, 10000])
def test_google_sdk_documented_page_size_keeps_cursor_and_rows(size: int) -> None:
    from app.google_connections.wire import GoogleReadWireAdapter

    class SDK:
        login_customer_id: str | None = None

        def get_service(self, name: str) -> "SDK":
            return self

        def search(self, *, request: dict[str, str]) -> NS:
            start, count = (1, size) if not request["page_token"] else (size + 1, 3)
            rows = [
                NS(
                    campaign=NS(id=n),
                    segments=NS(date="2026-10-01"),
                    metrics=NS(
                        impressions=100,
                        clicks=10,
                        cost_micros=100,
                        conversions=1,
                        conversions_value=3,
                    ),
                )
                for n in range(start, start + count)
            ]
            return NS(pages=[NS(results=rows, next_page_token="next" if start == 1 else "")])

    adapter = GoogleReadWireAdapter(lambda code, redirect: {}, lambda token: SDK())
    one = adapter.page("synthetic", "1234567890", date(2026, 10, 1), date(2026, 10, 1), "metrics:")
    assert len(one.metrics) == size and one.next_cursor
    retry = adapter.page(
        "synthetic", "1234567890", date(2026, 10, 1), date(2026, 10, 1), "metrics:"
    )
    assert retry == one
    two = adapter.page(
        "synthetic", "1234567890", date(2026, 10, 1), date(2026, 10, 1), one.next_cursor
    )
    assert len({r.campaign_external_id for r in one.metrics + two.metrics}) == size + 3
    assert two.next_cursor is None


def test_actual_uvicorn_access_capture_excludes_oauth_queries_preserves_normal_events() -> None:
    from app.shopify.logging import install_access_filter

    logger = logging.getLogger("uvicorn.access")
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    level, disabled = logger.level, logger.disabled
    # Earlier migration tests configure logging with disable_existing_loggers.
    logger.disabled = False
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    install_access_filter()
    try:
        for path in [
            "/dashboard/shopify/callback",
            "/dashboard/meta/callback",
            "/api/customer/v1/google/callback",
            "/api/customer/v1/sources/tiktok_ads/callback",
            "/api/customer/v1/sources/klaviyo/callback",
        ]:
            logger.info(
                '%s - "%s %s HTTP/%s" %d',
                "127.0.0.1:123",
                "GET",
                path + "?code=private-code&state=private-state&auth_code=private-auth-code",
                "1.1",
                200,
            )
        logger.info('%s - "%s %s HTTP/%s" %d', "127.0.0.1:123", "GET", "/health", "1.1", 200)
        assert "private-" not in stream.getvalue() and "GET /health HTTP/1.1" in stream.getvalue()
    finally:
        logger.removeHandler(handler)
        logger.setLevel(level)
        logger.disabled = disabled


@pytest.mark.parametrize(
    "batch,fault", [(1, "account"), (20, "account"), (1, "cursor"), (1, "publication")]
)
def test_tiktok_rejected_page_backs_off_without_starving_next_connection(
    customer_engine: Engine,
    configured: None,
    batch: int,
    fault: str,
) -> None:
    from datetime import timedelta
    from typing import Any

    from app.sources.dispatcher import run_tiktok
    from app.sources.models import SourceConnection
    from app.sources.security import SourceVault

    from tests.test_google_customer_connections import setup
    from tests.test_tiktok_sources import TikTokFixture, connect

    class RejectSome(TikTokFixture):
        def read(
            self, account: str, token: str, start: date, end: date, cursor: str | None
        ) -> dict[str, Any]:
            if token == "bad-fixture":
                if fault == "cursor":
                    return {"account_id": account, "currency": "USD", "next_cursor": "repeat"}
                if fault == "publication":
                    return {
                        "account_id": account,
                        "currency": "USD",
                        "ads": [{"id": "9", "group_id": "8", "name": "Orphan", "status": "PAUSED"}],
                    }
                return {"account_id": "999", "currency": "USD"}
            return super().read(account, token, start, end, cursor)

    fixture = RejectSome()
    with Session(customer_engine) as db:
        rows = []
        for i in range(batch + 1):
            wid, sid = setup(db, f"scope-{i}")
            rows.append(connect(db, wid, sid, fixture)[0])
        rows.sort(key=lambda row: row.id)
        for i, row in enumerate(rows):
            row.encrypted_grant = SourceVault().seal(
                row.workspace_id,
                "tiktok_ads",
                row.id,
                {"access_token": "bad-fixture" if i < batch else "good-fixture"},
            )
        if fault == "cursor":
            for row in rows[:-1]:
                row.cursor = "repeat"
        ids, good = [row.id for row in rows[:-1]], rows[-1].id
        db.commit()
    assert run_tiktok(customer_engine, fixture, NOW, batch)["failed"] == batch
    with Session(customer_engine) as db:
        for cid in ids:
            saved_row = db.get(SourceConnection, cid)
            assert saved_row is not None and saved_row.error_code == "import_rejected"
            assert saved_row.last_sync_at is None and saved_row.covered_from is None
            from app.shopify.security import utc

            assert saved_row.next_attempt_at is not None and utc(
                saved_row.next_attempt_at
            ) == NOW + timedelta(minutes=5)
    assert run_tiktok(customer_engine, fixture, NOW, batch)["selected"] == 1
    assert run_tiktok(customer_engine, fixture, NOW, batch)["completed_windows"] == 1
    with Session(customer_engine) as db:
        saved_row = db.get(SourceConnection, good)
        assert saved_row is not None and saved_row.last_sync_at is not None


def test_klaviyo_list_suppression_is_not_global_unsubscribe() -> None:
    from app.customer_context.wire import ProfileReader

    from tests.test_customer_context import IO

    reader = ProfileReader(
        "klaviyo",
        IO(
            {
                "data": [
                    {
                        "id": "fixture-profile",
                        "attributes": {
                            "subscriptions": {
                                "email": {
                                    "marketing": {
                                        "consent": "SUBSCRIBED",
                                        "suppression": [],
                                        "list_suppressions": [{"list_id": "fixture-list"}],
                                    }
                                }
                            }
                        },
                    }
                ]
            }
        ),
    )
    profile = reader.page("fixture", "synthetic", None, NOW).profiles[0]
    assert profile.email_status == "subscribed" and profile.email_suppression_scope == "list"
    assert "fixture-list" not in profile.model_dump_json()


class TrackedCheckout:
    """Provider state survives timeout and URL expiry independently of local billing."""

    mode: Literal["fixture"] = "fixture"

    def __init__(self) -> None:
        from datetime import timedelta

        from app.billing.contracts import SubscriptionState

        from tests.test_customer_billing import POLICY

        self.now = NOW
        self.uncertain = False
        self.unavailable = False
        self.results: dict[str, CheckoutResult] = {}
        self.states: dict[str, CheckoutState] = {}
        self.requested_keys: list[str] = []
        self.subscriptions = {
            "sub_fixture": SubscriptionState(
                customer_id="cus_fixture",
                subscription_id="sub_fixture",
                price_id=POLICY.price_id,
                status="active",
                period_end=NOW + timedelta(days=30),
                cancel_at_period_end=False,
                observed_at=NOW,
            )
        }

    def customer(self, workspace_id: int, idempotency_key: str) -> str:
        return "cus_fixture"

    def checkout(
        self, customer_id: str, price_id: str, idempotency_key: str, return_url: str
    ) -> CheckoutResult:
        from datetime import timedelta

        self.requested_keys.append(idempotency_key)
        if idempotency_key not in self.results:
            cid = "cs_session" + str(len(self.results) + 1)
            self.results[idempotency_key] = CheckoutResult(
                id=cid,
                url="https://checkout.stripe.com/c/" + cid,
                expires_at=self.now + timedelta(hours=1),
            )
            self.states[cid] = CheckoutState(
                id=cid, customer_id=customer_id, status="open", observed_at=self.now
            )
        if self.uncertain:
            raise TimeoutError("synthetic timeout after provider created session")
        return self.results[idempotency_key]

    def checkout_state(self, customer_id: str, checkout_id: str, now: datetime) -> CheckoutState:
        if self.unavailable:
            raise TimeoutError("synthetic unavailable lookup")
        return self.states[checkout_id].model_copy(update={"observed_at": now})

    def current(self, customer_id: str, subscription_id: str, now: datetime) -> SubscriptionState:
        return self.subscriptions[subscription_id].model_copy(update={"observed_at": now})


@pytest.mark.parametrize("missing_url", [False, True])
def test_uncertain_expired_checkout_is_recovered_before_attempt_retirement(
    customer_engine: Engine,
    missing_url: bool,
) -> None:
    from datetime import timedelta

    from app.billing import service as billing

    from tests.test_customer_billing import POLICY
    from tests.test_google_customer_connections import setup

    fixture = TrackedCheckout()
    with Session(customer_engine) as db:
        wid, _ = setup(db, "expired")
        fixture.uncertain = True
        with pytest.raises(HTTPException, match="pending"):
            billing.checkout(db, wid, POLICY, fixture, "https://inlet.example/settings", NOW)
        fixture.uncertain, fixture.now = False, NOW + timedelta(hours=2)
        fixture.states["cs_session1"] = fixture.states["cs_session1"].model_copy(
            update={"status": "expired"}
        )
        if missing_url:
            fixture.results = {
                key: value.model_copy(update={"url": None})
                for key, value in fixture.results.items()
            }
        fixture.unavailable = True
        with pytest.raises(HTTPException, match="reconciliation unavailable"):
            billing.checkout(
                db, wid, POLICY, fixture, "https://inlet.example/settings", fixture.now
            )
        db.rollback()
        assert len(fixture.results) == 1
        fixture.unavailable = False
        result = billing.checkout(
            db, wid, POLICY, fixture, "https://inlet.example/settings", fixture.now
        )
        assert result["id"] == "cs_session2" and len(fixture.results) == 2
        assert fixture.requested_keys[0] == fixture.requested_keys[1]
        assert fixture.requested_keys[-1] != fixture.requested_keys[0]


def test_completed_checkout_without_webhook_cannot_issue_second_purchase(
    customer_engine: Engine,
) -> None:
    from datetime import timedelta

    from app.billing import service as billing
    from app.billing.models import WorkspaceBilling
    from app.billing.scope import LEGACY_TEST_SCOPE

    from tests.test_customer_billing import POLICY
    from tests.test_google_customer_connections import setup

    fixture = TrackedCheckout()
    with Session(customer_engine) as db:
        wid, _ = setup(db, "completed")
        billing.checkout(db, wid, POLICY, fixture, "https://inlet.example/settings", NOW)
        fixture.states["cs_session1"] = fixture.states["cs_session1"].model_copy(
            update={"status": "complete", "subscription_id": "sub_fixture"}
        )
        with pytest.raises(HTTPException, match="completed"):
            billing.checkout(
                db, wid, POLICY, fixture, "https://inlet.example/settings", NOW + timedelta(hours=2)
            )
        assert len(fixture.results) == 1
        row = db.get(WorkspaceBilling, LEGACY_TEST_SCOPE.key(wid))
        assert row is not None and row.subscription_id == "sub_fixture" and row.status == "active"


def test_repurchase_requires_terminal_old_subscription_and_owned_completed_session(
    customer_engine: Engine,
) -> None:
    import json
    from datetime import timedelta

    from app.billing import service as billing
    from app.billing.models import WorkspaceBilling
    from app.billing.scope import LEGACY_TEST_SCOPE
    from app.billing.webhooks import receive

    from tests.test_customer_billing import POLICY, SECRET, payload, signature
    from tests.test_google_customer_connections import setup

    fixture = TrackedCheckout()
    with Session(customer_engine) as db:
        wid, _ = setup(db, "repurchase")
        billing.checkout(db, wid, POLICY, fixture, "https://inlet.example/settings", NOW)
        fixture.states["cs_session1"] = fixture.states["cs_session1"].model_copy(
            update={"status": "complete", "subscription_id": "sub_fixture"}
        )
        event = payload("evt_original")
        receive(db, event, signature(event), SECRET, NOW)
        billing.reconcile(db, wid, "evt_original", POLICY, fixture, NOW)
        fixture.subscriptions["sub_fixture"] = fixture.subscriptions["sub_fixture"].model_copy(
            update={"status": "canceled"}
        )
        event = payload("evt_cancel")
        receive(db, event, signature(event), SECRET, NOW)
        billing.reconcile(db, wid, "evt_cancel", POLICY, fixture, NOW)
        fixture.now = NOW + timedelta(hours=2)
        new = billing.checkout(
            db, wid, POLICY, fixture, "https://inlet.example/settings", fixture.now
        )
        assert new["id"] == "cs_session2"
        fixture.subscriptions["sub_new"] = fixture.subscriptions["sub_fixture"].model_copy(
            update={"subscription_id": "sub_new", "status": "active"}
        )
        fixture.states["cs_session2"] = fixture.states["cs_session2"].model_copy(
            update={"status": "complete", "subscription_id": "sub_new"}
        )
        raw = json.loads(payload("evt_new_subscription"))
        raw["data"]["object"]["id"] = "sub_new"
        event = json.dumps(raw).encode()
        receive(db, event, signature(event, fixture.now), SECRET, fixture.now)
        billing.reconcile(db, wid, "evt_new_subscription", POLICY, fixture, fixture.now)
        row = db.get(WorkspaceBilling, LEGACY_TEST_SCOPE.key(wid))
        assert row is not None and row.subscription_id == "sub_new"
        billing.require_entitlement(db, wid, POLICY, fixture.now)


def test_scheduler_recovers_completed_checkout_without_subscription_webhook(
    customer_engine: Engine,
) -> None:
    from datetime import timedelta

    from app.billing import service as billing
    from app.billing.dispatcher import run
    from app.billing.models import WorkspaceBilling
    from app.billing.scope import LEGACY_TEST_SCOPE
    from sqlalchemy.orm import sessionmaker

    from tests.test_customer_billing import POLICY
    from tests.test_google_customer_connections import setup

    fixture = TrackedCheckout()
    with Session(customer_engine) as db:
        wid, _ = setup(db, "missing-webhook")
        billing.checkout(db, wid, POLICY, fixture, "https://inlet.example/settings", NOW)
    fixture.states["cs_session1"] = fixture.states["cs_session1"].model_copy(
        update={"status": "complete", "subscription_id": "sub_fixture"}
    )
    assert (
        run(sessionmaker(customer_engine), POLICY, fixture, NOW + timedelta(minutes=3))["refreshes"]
        == 1
    )
    with Session(customer_engine) as db:
        row = db.get(WorkspaceBilling, LEGACY_TEST_SCOPE.key(wid))
        assert row is not None and row.subscription_id == "sub_fixture" and row.status == "active"
    assert len(fixture.results) == 1


def test_replacement_lookup_failure_backs_off_before_dispatch_limit(
    customer_engine: Engine,
) -> None:
    from datetime import timedelta

    from app.billing.dispatcher import run
    from app.billing.models import BillingEvent, WorkspaceBilling
    from app.billing.scope import LEGACY_TEST_SCOPE
    from sqlalchemy.orm import sessionmaker

    from tests.test_customer_billing import POLICY
    from tests.test_google_customer_connections import setup

    class LookupOutage(TrackedCheckout):
        def checkout_state(
            self, customer_id: str, checkout_id: str, now: datetime
        ) -> CheckoutState:
            raise TimeoutError("synthetic lookup outage")

    fixture = LookupOutage()
    with Session(customer_engine) as db:
        bad, _ = setup(db, "replacement-outage")
        good, _ = setup(db, "healthy-behind")
        db.add_all(
            [
                WorkspaceBilling(
                    workspace_id=bad,
                    customer_request_key="bad",
                    customer_id="cus_bad",
                    subscription_id="sub_old",
                    status="canceled",
                    checkout_id="cs_new",
                ),
                WorkspaceBilling(
                    workspace_id=good,
                    customer_request_key="good",
                    customer_id="cus_fixture",
                    subscription_id="sub_fixture",
                ),
                BillingEvent(
                    id="evt_bad",
                    body_hash="a" * 64,
                    customer_id="cus_bad",
                    subscription_id="sub_new",
                    event_type="customer.subscription.created",
                    received_at=NOW - timedelta(seconds=1),
                ),
                BillingEvent(
                    id="evt_good",
                    body_hash="b" * 64,
                    customer_id="cus_fixture",
                    subscription_id="sub_fixture",
                    event_type="customer.subscription.updated",
                    received_at=NOW,
                ),
            ]
        )
        db.commit()
    factory = sessionmaker(customer_engine)
    assert run(factory, POLICY, fixture, NOW, limit=1)["failed"] == 1
    assert run(factory, POLICY, fixture, NOW, limit=1)["events"] == 1
    with Session(customer_engine) as db:
        event = db.get(BillingEvent, LEGACY_TEST_SCOPE.key("evt_bad"))
        assert event is not None and event.state == "pending" and event.next_attempt_at is not None
        assert db.get(BillingEvent, LEGACY_TEST_SCOPE.key("evt_good")).state == "processed"  # type: ignore[union-attr]


def test_tiktok_prior_read_failure_does_not_preserve_rejected_staging(
    customer_engine: Engine, configured: None
) -> None:
    from datetime import timedelta
    from typing import Any

    from app.sources.dispatcher import run_tiktok
    from app.sources.models import SourceConnection

    from tests.test_google_customer_connections import setup
    from tests.test_tiktok_sources import TikTokFixture, connect

    class RecoverThenConflict(TikTokFixture):
        read_calls = 0

        def read(
            self, account: str, token: str, start: date, end: date, cursor: str | None
        ) -> dict[str, Any]:
            self.read_calls += 1
            if self.read_calls == 1:
                raise TimeoutError("synthetic transient")
            return {"account_id": account, "currency": "USD", "next_cursor": "repeat"}

    fixture = RecoverThenConflict()
    with Session(customer_engine) as db:
        wid, sid = setup(db, "retry-conflict")
        connected, _ = connect(db, wid, sid, fixture)
        cid = connected.id
        db.commit()
    assert run_tiktok(customer_engine, fixture, NOW, 1)["failed"] == 1
    future = NOW + timedelta(minutes=5)
    assert run_tiktok(customer_engine, fixture, future, 1)["failed"] == 0
    with Session(customer_engine) as db:
        row = db.get(SourceConnection, cid)
        assert row is not None and row.cursor == "repeat" and row.staged
        assert row.error_code is None
        # Also exercise cleanup with a legacy persisted transient marker.
        row.error_code = "read_unavailable"
        db.commit()
    assert run_tiktok(customer_engine, fixture, future, 1)["failed"] == 1
    with Session(customer_engine) as db:
        row = db.get(SourceConnection, cid)
        assert row is not None and row.error_code == "import_rejected"
        assert row.cursor is None and row.staged == {}
        assert row.last_sync_at is None and row.covered_from is None
