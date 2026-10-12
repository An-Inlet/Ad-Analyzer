"""Namespaced offline acquisition; never changes retained evidence or production routing."""

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal

import httpx
import pytest
from app.billing.contracts import CheckoutResult, SubscriptionState
from app.billing.entitlements import paid_work
from app.billing.service import checkout, reconcile
from app.billing.webhooks import receive
from app.settings import settings
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests import test_customer_billing as billing


@dataclass(frozen=True)
class FixtureIdentity:
    namespace: Literal["matrix-a", "matrix-b"]
    customer: Literal["2234567890", "3234567890"]
    size: Literal["small", "large"]

    @property
    def reporting_campaigns(self) -> int:
        return 1 if self.size == "small" else 4

    @property
    def native_campaigns(self) -> int:
        return 3 if self.size == "small" else 4

    @property
    def owners(self) -> int:
        return 1 if self.size == "small" else 2

    @property
    def shop(self) -> str:
        return self.namespace + ".myshopify.com"


def install_shared_configuration(patch: pytest.MonkeyPatch) -> None:
    patch.setattr(
        settings, "google_customer_encryption_key", SecretStr(Fernet.generate_key().decode())
    )
    patch.setattr(settings, "google_customer_client_id", "synthetic-client")
    patch.setattr(settings, "google_customer_client_secret", SecretStr("synthetic-secret"))
    patch.setattr(settings, "customer_native_diagnostics_enabled", True)
    patch.setattr(settings, "billing_required", True)
    patch.setattr(settings, "billing_price_id", billing.POLICY.price_id)
    patch.setattr(settings, "billing_max_accounts", billing.POLICY.max_accounts)


def native_wire(
    operation: Callable[[httpx.Request], httpx.Response], identity: FixtureIdentity | None
) -> Callable[[httpx.Request], httpx.Response]:
    if identity is None:
        return operation

    def replace(value: Any) -> Any:
        if type(value) is str:
            return value.replace("1234567890", identity.customer)
        if type(value) is list:
            return [replace(item) for item in value]
        if type(value) is dict:
            return {key: replace(item) for key, item in value.items()}
        return value

    def wire(request: httpx.Request) -> httpx.Response:
        original = operation(request)
        assert original.status_code == 200
        return httpx.Response(200, json=replace(original.json()))

    return wire


def paid_workspace(engine: Engine, wid: int, identity: FixtureIdentity, now: datetime) -> None:
    billing_namespace = identity.namespace.replace("-", "_")

    class NamespacedBilling(billing.FixtureBilling):
        def __init__(self) -> None:
            super().__init__()
            self.state = SubscriptionState(
                customer_id="cus_" + billing_namespace,
                subscription_id="sub_" + billing_namespace,
                price_id=billing.POLICY.price_id,
                status="active",
                period_end=now + timedelta(days=30),
                cancel_at_period_end=False,
                observed_at=now,
            )

        def customer(self, workspace_id: int, idempotency_key: str) -> str:
            assert workspace_id == wid
            self.keys.append(idempotency_key)
            return self.state.customer_id

        def checkout(
            self, customer_id: str, price_id: str, idempotency_key: str, return_url: str
        ) -> CheckoutResult:
            assert customer_id == self.state.customer_id and price_id == billing.POLICY.price_id
            self.keys.append(idempotency_key)
            return CheckoutResult(
                id="cs_" + billing_namespace,
                url="https://checkout.stripe.com/c/fixture",
                expires_at=now + timedelta(hours=1),
            )

        def current(
            self, customer_id: str, subscription_id: str, at: datetime
        ) -> SubscriptionState:
            assert (customer_id, subscription_id) == (
                self.state.customer_id,
                self.state.subscription_id,
            )
            return self.state.model_copy(update={"observed_at": at})

    fixture = NamespacedBilling()
    identifier = "evt_" + billing_namespace
    body = json.loads(billing.payload(identifier))
    body["data"]["object"].update(
        id=fixture.state.subscription_id, customer=fixture.state.customer_id
    )
    raw = json.dumps(body).encode()
    with Session(engine) as db:
        checkout(db, wid, billing.POLICY, fixture, "https://inlet.example/settings", now)
        assert receive(db, raw, billing.signature(raw, now), billing.SECRET, now)
        assert reconcile(db, wid, identifier, billing.POLICY, fixture, now)
        paid_work(db, wid, now)
