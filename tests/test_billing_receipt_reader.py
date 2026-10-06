"""Original financial evidence remains readable without a current sales offer."""

from datetime import UTC, datetime, timedelta
from typing import Self

import httpx
import pytest
from app.billing import offer_bindings, repository
from app.billing.contracts import UnavailableBilling, get_billing_transport
from app.billing.offers import digest
from app.billing.receipt_dispatcher import run
from app.billing.receipt_reader import (
    StripeReceiptReader,
    _GetOnlyStripe,
    get_billing_receipt_reader,
)
from app.billing.service import owned, require_entitlement
from app.billing.stripe import BillingProviderError
from app.jobs import customer_runtime
from app.settings import settings
from app.workspaces.models import Workspace
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.test_billing_offers import LIVE, POLICY, PROFILE, TEST, StripeOfferFixture, bound
from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_google_customer_connections import setup


def seeded(engine: Engine, fixture: StripeOfferFixture, *, checkout: bool = False) -> int:
    with Session(engine) as db:
        wid, _ = setup(db, "original")
        row = owned(db, wid, NOW, scope=LIVE)
        row.customer_id, row.checkout_key = "cus_fixture", bound().checkout_key
        saved = offer_bindings.install(db, row, PROFILE, NOW)
        fixture.binding_digest, fixture.checkout_key = digest(saved), saved.checkout_key
        row.checkout_id = "cs_fixture"
        if not checkout:
            row.subscription_id = "sub_fixture"
            row.subscription_offer_binding_id = saved.id
        db.commit()
    return wid


def reader(fixture: StripeOfferFixture) -> StripeReceiptReader:
    return StripeReceiptReader(
        LIVE,
        SecretStr("sk_live_offline_fixture"),
        http_transport=httpx.MockTransport(fixture.respond),
    )


@pytest.mark.parametrize("profile", [None, "{invalid"])
@pytest.mark.parametrize("checkout", [False, True])
def test_removed_offer_receipts_never_enable_forward_work(
    customer_engine: Engine, monkeypatch: pytest.MonkeyPatch, profile: str | None, checkout: bool
) -> None:
    fixture = StripeOfferFixture()
    wid = seeded(customer_engine, fixture, checkout=checkout)
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "billing_provider_mode", "disabled")
    monkeypatch.setattr(settings, "billing_live_enabled", False)
    monkeypatch.setattr(settings, "billing_offer_profile", profile)
    assert isinstance(get_billing_transport(), UnavailableBilling)
    result = run(lambda: Session(customer_engine), reader(fixture), clock=lambda: NOW)
    assert result == {"refreshes": 1, "failed": 0, "changed": 0}
    assert fixture.calls and {method for method, _ in fixture.calls} == {"GET"}
    with Session(customer_engine) as db:
        row = repository.billing(db, wid, LIVE)
        assert row is not None and row.qualification is not None
        assert row.subscription_id == "sub_fixture" and row.checkout_key == fixture.checkout_key
        with pytest.raises(HTTPException, match="qualified paid offer unavailable"):
            require_entitlement(db, wid, POLICY, NOW, scope=LIVE)
    fixture.status = "canceled"
    assert (
        run(
            lambda: Session(customer_engine),
            reader(fixture),
            clock=lambda: NOW + timedelta(minutes=3),
        )["refreshes"]
        == 1
    )
    with Session(customer_engine) as db:
        row = repository.billing(db, wid, LIVE)
        assert row is not None and row.status == "canceled" and row.qualification is None


def test_get_only_and_foreign_scope_rejected_before_http() -> None:
    fixture = StripeOfferFixture()
    wire = _GetOnlyStripe(
        SecretStr("sk_live_offline_fixture"),
        PROFILE.api_version,
        scope=LIVE,
        http_transport=httpx.MockTransport(fixture.respond),
    )
    for method, data, key in (("POST", None, None), ("GET", {}, None), ("GET", None, "key")):
        with pytest.raises(BillingProviderError, match="get_only"):
            wire.request(method, "/v1/customers", data=data, key=key)  # type: ignore[arg-type]
    other = StripeReceiptReader(TEST, SecretStr("sk_test_offline_fixture"))
    with pytest.raises(BillingProviderError, match="binding mismatch"):
        other.current_bound(bound(), "cus_fixture", "sub_fixture", NOW)
    assert fixture.calls == []


@pytest.mark.parametrize("change", ["closure", "identity", "newer_snapshot", "delay"])
def test_final_recheck_rejects_changed_original(customer_engine: Engine, change: str) -> None:
    fixture = StripeOfferFixture()
    wid = seeded(customer_engine, fixture)
    current = [NOW]
    original = fixture.respond
    mutated = False

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal mutated
        result = original(request)
        if not mutated:
            mutated = True
            if change == "delay":
                current[0] += timedelta(seconds=31)
            else:
                with Session(customer_engine) as db:
                    row = repository.billing(db, wid, LIVE)
                    assert row is not None
                    if change == "closure":
                        workspace = db.get(Workspace, wid)
                        assert workspace is not None
                        workspace.status = "closing"
                    elif change == "identity":
                        row.customer_id = "cus_replaced"
                    else:
                        row.verified_at = NOW + timedelta(seconds=1)
                    db.commit()
        return result

    receipt = StripeReceiptReader(
        LIVE, SecretStr("sk_live_offline_fixture"), http_transport=httpx.MockTransport(respond)
    )
    result = run(lambda: Session(customer_engine), receipt, clock=lambda: current[0])
    assert result["refreshes"] == 0
    assert result["failed" if change == "delay" else "changed"] == 1
    with Session(customer_engine) as db:
        row = repository.billing(db, wid, LIVE)
        assert row is not None and row.qualification is None


def test_unknown_checkout_is_not_replayed(customer_engine: Engine) -> None:
    fixture = StripeOfferFixture()
    wid = seeded(customer_engine, fixture, checkout=True)
    with Session(customer_engine) as db:
        row = repository.billing(db, wid, LIVE)
        assert row is not None
        row.checkout_id = None
        db.commit()
    result = run(lambda: Session(customer_engine), reader(fixture), clock=lambda: NOW)
    assert result["refreshes"] == 0
    assert fixture.calls == []
    with Session(customer_engine) as db:
        row = repository.billing(db, wid, LIVE)
        assert row is not None and row.checkout_key == fixture.checkout_key


def test_actual_scheduler_uses_original_reader_not_purchase_factory(
    customer_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.billing import receipt_dispatcher, receipt_reader

    fixture = StripeOfferFixture()
    wid = seeded(customer_engine, fixture)
    monkeypatch.setattr(settings, "customer_billing_scheduler_enabled", True)
    monkeypatch.setattr(settings, "billing_receipt_read_enabled", True)
    monkeypatch.setattr(settings, "billing_receipt_environment", "live")
    monkeypatch.setattr(settings, "billing_merchant_account_id", LIVE.merchant_account_id)
    monkeypatch.setattr(settings, "billing_api_key", SecretStr("sk_live_offline_fixture"))
    monkeypatch.setattr(settings, "billing_offer_profile", "invalid")
    monkeypatch.setattr(settings, "billing_api_version", "removed-current-version")
    monkeypatch.setattr(settings, "billing_provider_mode", "disabled")
    monkeypatch.setattr(settings, "billing_live_enabled", False)
    monkeypatch.setattr(settings, "app_env", "production")

    class Clock(datetime):
        @classmethod
        def now(cls, tz: object = None) -> Self:
            return cls.fromtimestamp(NOW.timestamp(), UTC)

    class FixtureReader(StripeReceiptReader):
        def __init__(self, scope: object, key: SecretStr) -> None:
            assert scope == LIVE

            def respond(request: httpx.Request) -> httpx.Response:
                assert request.headers["Stripe-Version"] == PROFILE.api_version
                return fixture.respond(request)

            super().__init__(LIVE, key, http_transport=httpx.MockTransport(respond))

    monkeypatch.setattr(receipt_reader, "StripeReceiptReader", FixtureReader)
    monkeypatch.setattr(receipt_dispatcher, "datetime", Clock)
    assert customer_runtime.run_customer_tick(customer_engine) == {"billing": "completed"}
    assert fixture.calls and {method for method, _ in fixture.calls} == {"GET"}
    with Session(customer_engine) as db:
        row = repository.billing(db, wid, LIVE)
        assert row is not None and row.qualification is not None
    monkeypatch.setattr(settings, "billing_receipt_read_enabled", False)
    with pytest.raises(ValueError):
        get_billing_receipt_reader()
    monkeypatch.setattr(settings, "billing_receipt_read_enabled", True)
    monkeypatch.setattr(settings, "billing_receipt_environment", "test")
    with pytest.raises(ValueError):
        get_billing_receipt_reader()


def test_failed_qualification_backoff_preserves_original(customer_engine: Engine) -> None:
    fixture = StripeOfferFixture()
    wid = seeded(customer_engine, fixture)

    def factory() -> Session:
        return Session(customer_engine)

    receipt = reader(fixture)
    assert run(factory, receipt, clock=lambda: NOW)["refreshes"] == 1
    with Session(customer_engine) as db:
        row = repository.billing(db, wid, LIVE)
        assert row is not None
        original_digest = row.qualification_digest
    fixture.mutations["/v1/invoices/in_fixture"] = {"amount_paid": 999}
    later = NOW + timedelta(minutes=3)
    assert run(factory, receipt, clock=lambda: later)["failed"] == 1
    before = len(fixture.calls)
    assert run(factory, receipt, clock=lambda: later)["refreshes"] == 0
    assert len(fixture.calls) == before
    with Session(customer_engine) as db:
        row = repository.billing(db, wid, LIVE)
        assert row is not None
        assert row.qualification_digest == original_digest
        assert row.error_code == "commercial_qualification_unavailable"
        assert row.checkout_key == fixture.checkout_key


def test_closing_scope_keeps_original_notice_lane(customer_engine: Engine) -> None:
    from app.billing.models import BillingEvent
    from app.lifecycle.quiescing import quiesce

    from tests.test_customer_identity import FakeProvider
    from tests.test_customer_lifecycle import seed
    from tests.test_customer_quiescing import confirmed

    fixture = StripeOfferFixture()
    with Session(customer_engine) as db:
        principal, wid = seed(db)
        row = owned(db, wid, NOW, scope=LIVE)
        row.customer_id, row.checkout_key = "cus_fixture", bound().checkout_key
        saved = offer_bindings.install(db, row, PROFILE, NOW)
        row.subscription_id, row.subscription_offer_binding_id = "sub_fixture", saved.id
        db.commit()
        request, evidence = confirmed(db, principal, wid)
        quiesce(db, principal, FakeProvider(), wid, request, 1, evidence, NOW)
        db.commit()
        db.add(
            BillingEvent(
                id="evt_late_original",
                **LIVE.columns(),
                customer_id="cus_fixture",
                subscription_id="sub_fixture",
                body_hash="a" * 64,
                state="pending",
                event_type="customer.subscription.updated",
                received_at=NOW,
            )
        )
        db.commit()
    assert run(lambda: Session(customer_engine), reader(fixture), clock=lambda: NOW) == {
        "refreshes": 0,
        "failed": 0,
        "changed": 0,
    }
    assert fixture.calls == []
    with Session(customer_engine) as db:
        event = repository.event(db, "evt_late_original", LIVE)
        assert event is not None and event.state == "closure_pending"
        retained = repository.billing(db, wid, LIVE)
        assert retained is not None and retained.subscription_offer_binding_id == saved.id


def test_notice_acknowledgement_is_original_scope_and_observation_bounded(
    customer_engine: Engine,
) -> None:
    from app.billing.models import BillingEvent

    fixture = StripeOfferFixture()
    seeded(customer_engine, fixture)
    with Session(customer_engine) as db:
        for eid, scope, sid, received in (
            ("evt_owned", LIVE, "sub_fixture", NOW),
            ("evt_after_observation", LIVE, "sub_fixture", NOW + timedelta(seconds=1)),
            ("evt_foreign_mode", TEST, "sub_fixture", NOW),
            ("evt_other_subscription", LIVE, "sub_other", NOW),
        ):
            db.add(
                BillingEvent(
                    id=eid,
                    **scope.columns(),
                    customer_id="cus_fixture",
                    subscription_id=sid,
                    body_hash="a" * 64,
                    state="pending",
                    received_at=received,
                    event_type="customer.subscription.updated",
                )
            )
        db.commit()
    assert (
        run(lambda: Session(customer_engine), reader(fixture), clock=lambda: NOW)["refreshes"] == 1
    )
    with Session(customer_engine) as db:
        for eid, scope, state in (
            ("evt_owned", LIVE, "processed"),
            ("evt_after_observation", LIVE, "pending"),
            ("evt_foreign_mode", TEST, "pending"),
            ("evt_other_subscription", LIVE, "pending"),
        ):
            event = repository.event(db, eid, scope)
            assert event is not None and event.state == state
