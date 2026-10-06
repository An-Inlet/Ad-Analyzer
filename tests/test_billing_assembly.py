"""Production assembly cannot select test billing or the rollout bypass."""
from collections.abc import Generator
from pathlib import Path

import pytest
from app.billing.entitlements import paid_work
from app.billing.service import owned
from app.campaign_review.models import MediaObject
from app.campaign_review.storage import LocalMediaStore, get_media_store
from app.customers.access import CSRF_COOKIE
from app.customers.identity import get_identity_provider
from app.customers.models import CustomerMembership
from app.database.session import get_db
from app.main import app
from app.settings import settings
from app.workspaces.models import Workspace
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_campaign_review import png
from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import ORIGIN, FakeProvider, login
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_google_customer_connections import setup


@pytest.mark.parametrize("required", [False, True])
@pytest.mark.parametrize("mode", ["disabled", "stripe_test", "stripe_live"])
def test_production_gate_cannot_use_disabled_rollout(
    customer_engine: Engine, monkeypatch: pytest.MonkeyPatch, mode: str, required: bool
) -> None:
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "billing_provider_mode", mode)
    monkeypatch.setattr(settings, "billing_required", required)
    monkeypatch.setattr(settings, "billing_live_enabled", False)
    with Session(customer_engine) as db:
        wid, _ = setup(db, "production-gate")
        with pytest.raises(HTTPException, match="live billing qualification unavailable"):
            paid_work(db, wid, NOW)


@pytest.mark.parametrize("mode", ["disabled", "stripe_test"])
def test_actual_app_production_upload_and_billing_status(
    customer_engine: Engine, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mode: str
) -> None:
    monkeypatch.setattr(settings, "customer_app_origin", ORIGIN)
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "billing_provider_mode", mode)
    monkeypatch.setattr(settings, "billing_required", False)
    monkeypatch.setattr(settings, "billing_api_key", None)

    def database() -> Generator[Session, None, None]:
        with Session(customer_engine) as db:
            yield db

    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_identity_provider] = FakeProvider
    app.dependency_overrides[get_media_store] = lambda: LocalMediaStore(tmp_path)
    try:
        client = TestClient(app, base_url=ORIGIN)
        actor = login(client, "production-owner")
        with Session(customer_engine) as db:
            workspace = Workspace(slug="production", name="Production", client_name="P")
            db.add(workspace)
            db.flush()
            wid = workspace.id
            db.add(CustomerMembership(workspace_id=wid, user_id=actor, role="owner"))
            row = owned(db, wid, NOW)
            row.status = "active"
            row.customer_id = "cus_legacy"
            db.commit()
        url = f"/api/customer/v1/workspaces/{wid}"
        headers = {"Origin": ORIGIN, "X-CSRF-Token": client.cookies[CSRF_COOKIE]}
        response = client.post(url + "/media", content=png(), headers=headers)
        assert response.status_code == 503, response.text
        with Session(customer_engine) as db:
            assert db.scalar(select(func.count()).select_from(MediaObject)) == 0
        status = client.get(url + "/billing")
        assert status.status_code == 200, status.text
        body = status.json()
        assert body["enforcement_enabled"] is True
        assert body["status"] == "unconfigured"
        assert body["scope"] is None
        assert not body["can_checkout"] and not body["can_manage"]
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


def test_production_factory_rejects_complete_test_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.billing.contracts import UnavailableBilling, get_billing_transport
    from pydantic import SecretStr

    from tests.test_billing_offers import PROFILE, TEST

    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "billing_provider_mode", "stripe_test")
    monkeypatch.setattr(settings, "billing_api_key", SecretStr("sk_test_offline_fixture"))
    monkeypatch.setattr(settings, "billing_merchant_account_id", TEST.merchant_account_id)
    monkeypatch.setattr(settings, "billing_api_version", PROFILE.api_version)
    monkeypatch.setattr(
        settings,
        "billing_offer_profile",
        PROFILE.model_copy(update={"scope": TEST}).model_dump_json(),
    )
    assert isinstance(get_billing_transport(), UnavailableBilling)
    monkeypatch.setattr(settings, "app_env", "development")
    assert not isinstance(get_billing_transport(), UnavailableBilling)
