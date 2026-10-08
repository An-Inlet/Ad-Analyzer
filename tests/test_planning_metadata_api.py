"""Actual HTTPS/CSRF, persisted vaults and all three fixed HTTP collectors."""

import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from app.api import customer_planning_target_catalog as api
from app.automation.models import PlatformAutomationControl
from app.collectors import account_diagnostics
from app.customers.models import CustomerMembership, CustomerSession, CustomerUser
from app.google_connections.models import GoogleCustomerConnection
from app.meta.models import MetaConnection
from app.publication import execution_mandates
from app.settings import Settings, settings
from app.sources.models import SourceConnection
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests import test_planning_target_catalog_api
from tests.test_customer_identity import ISSUER, FakeProvider, login
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_google_native_inventory import key, payloads
from tests.test_meta_native_inventory import PRIVATE
from tests.test_meta_native_inventory import Server as MetaServer
from tests.test_planning_target_catalog_api import seed
from tests.test_shopify_sales import configuration as configuration
from tests.test_tiktok_native_inventory import Server as TikTokServer


@pytest.mark.parametrize("provider", ["google_ads", "meta_ads", "tiktok_ads"])
@pytest.mark.parametrize(
    "change",
    [
        None,
        "disabled",
        "session",
        "generation",
        "metadata_session",
        "metadata_generation",
        "metadata_expiry",
        "metadata_foreign",
        "metadata_duplicate",
        "metadata_capacity",
        "metadata_parent",
        "metadata_names_missing",
        "metadata_names_over_bound",
        "observation_expiry",
        "role",
        "oauth_session",
        "control",
        "billing",
        "expired",
        "missing_credentials",
        "unrepresentable_period",
    ],
)
def test_real_planning_metadata_api(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: tuple[TestClient, TestClient, FakeProvider],
    provider: str,
    change: str | None,
) -> None:
    for attr in (
        "google_customer_encryption_key",
        "meta_token_encryption_key",
        "source_token_encryption_key",
    ):
        monkeypatch.setattr(settings, attr, SecretStr(Fernet.generate_key().decode()))
    monkeypatch.setattr(settings, "google_customer_client_id", "synthetic-client")
    monkeypatch.setattr(settings, "google_customer_client_secret", SecretStr("synthetic-secret"))
    monkeypatch.setattr(settings, "meta_client_secret", SecretStr("synthetic-app-secret"))
    monkeypatch.setattr(settings, "customer_native_diagnostics_enabled", change != "disabled")
    # Receipt expiry is bounded by the actual database clock, not a historical
    # fixture date. Keep synthetic credentials and reads in the same current window.
    observed_now = datetime.now(UTC)
    monkeypatch.setattr(test_planning_target_catalog_api, "NOW", observed_now)
    request = seed(customer_engine, configuration, tmp_path, provider)
    with Session(customer_engine) as db:
        user = db.get(CustomerUser, request.actor)
        assert user
        user.issuer, user.subject = ISSUER, "diagnostic-owner"
        db.commit()
    alice, bob, _ = replicas
    for client in (alice, bob):
        client.app.include_router(api.router)  # type: ignore[attr-defined]
    assert login(alice, "diagnostic-owner:1") == request.actor
    login(bob, "other:1")
    clock = [observed_now]
    monkeypatch.setattr(api, "utc_now", lambda: clock[0])

    # Account observations must not consult or create a spending consent.
    def forbidden(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("account diagnostics must not require a mandate")

    monkeypatch.setattr(execution_mandates, "checked", forbidden)
    calls: list[str] = []
    constructed: list[bool] = []
    closed: list[bool] = []
    server = MetaServer() if provider == "meta_ads" else TikTokServer()

    def revoke() -> None:
        with Session(customer_engine) as db:
            if change in {"observation_expiry", "metadata_expiry"}:
                clock[0] = observed_now + timedelta(minutes=6)
            elif change in {"session", "oauth_session", "metadata_session"}:
                for session in db.scalars(
                    select(CustomerSession).where(CustomerSession.user_id == request.actor)
                ):
                    session.revoked_at = int(time.time())
            elif change == "control":
                db.merge(
                    PlatformAutomationControl(
                        key="all_data_syncs", enabled=False, updated_by="test"
                    )
                )
            elif change == "billing":
                monkeypatch.setattr(settings, "billing_required", True)
            elif change == "expired":
                for session in db.scalars(
                    select(CustomerSession).where(CustomerSession.user_id == request.actor)
                ):
                    session.expires_at = int(time.time()) - 1
            elif change == "missing_credentials":
                if provider == "google_ads":
                    row = db.scalar(
                        select(GoogleCustomerConnection).where(
                            GoogleCustomerConnection.account_id == request.account_id
                        )
                    )
                    assert row
                    row.encrypted_grant = None
                elif provider == "meta_ads":
                    meta = db.scalar(
                        select(MetaConnection).where(
                            MetaConnection.account_id == request.account_id
                        )
                    )
                    assert meta
                    meta.encrypted_credentials = ""
                else:
                    source = db.scalar(
                        select(SourceConnection).where(
                            SourceConnection.account_id == request.account_id
                        )
                    )
                    assert source
                    source.encrypted_grant = None
            elif change == "role":
                member = db.get(CustomerMembership, (request.actor, request.workspace_id))
                assert member
                member.role = "viewer"
            elif change in {"generation", "metadata_generation"}:
                model: Any = {
                    "google_ads": GoogleCustomerConnection,
                    "meta_ads": MetaConnection,
                    "tiktok_ads": SourceConnection,
                }[provider]
                native = db.scalar(select(model).where(model.account_id == request.account_id))
                assert native
                native.generation += 1
            db.commit()

    def wire(req: httpx.Request) -> httpx.Response:
        rows: list[dict[str, Any]]
        calls.append(str(req.url.host))
        query = (
            json.loads(req.content).get("query", "")
            if req.url.host == "googleads.googleapis.com"
            else ""
        )
        fields = req.url.params.get("fields", "")
        is_metadata = (
            ".name" in query
            or "name" in fields.split(",")
            or "campaign_name" in fields
            or "adgroup_name" in fields
        )
        if is_metadata and change in {"metadata_session", "metadata_generation", "metadata_expiry"}:
            revoke()
        if req.url.host == "oauth2.googleapis.com":
            if change == "oauth_session":
                revoke()
            return httpx.Response(
                200, json=dict(access_token=PRIVATE, token_type="Bearer", expires_in=3600)
            )
        if change in {
            "session",
            "generation",
            "observation_expiry",
            "role",
            "oauth_session",
            "control",
            "billing",
            "expired",
            "missing_credentials",
        }:
            revoke()
        if provider == "google_ads":
            data = payloads()
            data["customer"][0]["customer"]["timeZone"] = "UTC"
            other_campaign = dict(data["campaign"][0]["campaign"])
            other_campaign["resourceName"] = other_campaign["resourceName"].rsplit("/", 1)[0] + "/2"
            data["campaign"].append({"campaign": other_campaign})
            data["campaign_budget"][0]["campaignBudget"].update(
                explicitlyShared=True, referenceCount="2"
            )
            if is_metadata:
                if "FROM ad_group" in query:
                    rows = [
                        {
                            "adGroup": dict(
                                resourceName="customers/1234567890/adGroups/7",
                                campaign="customers/1234567890/campaigns/1",
                                name="<b>Child</b>",
                                status="ENABLED",
                                type="SEARCH_STANDARD",
                            )
                        }
                    ]
                else:
                    rows = data["campaign"]
                    for row in rows:
                        row["campaign"]["name"] = "Owned Campaign"
                if change == "metadata_foreign":
                    rows[0]["adGroup" if "FROM ad_group" in query else "campaign"][
                        "resourceName"
                    ] = "customers/9999999999/campaigns/1"
                if change == "metadata_parent" and "FROM ad_group" in query:
                    rows[0]["adGroup"]["campaign"] = "customers/1234567890/campaigns/999"
                if change in {"metadata_names_missing", "metadata_names_over_bound"}:
                    for row in rows:
                        row["adGroup" if "FROM ad_group" in query else "campaign"]["name"] = (
                            None if change == "metadata_names_missing" else "x" * 161
                        )
                if change == "metadata_capacity":
                    rows = rows * 201
                if change == "metadata_duplicate":
                    rows.append(rows[0])
                return httpx.Response(200, json={"results": rows})
            return httpx.Response(200, json={"results": data[key(query)]})
        if is_metadata and isinstance(server, MetaServer):
            assert req.method == "GET" and req.url.host == "graph.facebook.com"
            assert "name" in fields.split(",") and "account_id" in fields.split(",")
            assert req.headers["Authorization"] == "Bearer " + PRIVATE
            response = httpx.Response(
                200,
                json={
                    "data": json.loads(
                        json.dumps(
                            server.adsets if req.url.path.endswith("adsets") else server.campaigns
                        )
                    )
                },
            )
        else:
            response = server(req)
        if is_metadata:
            data = response.json()
            rows = data["data"] if provider == "meta_ads" else data["data"]["list"]
            for row in rows:
                row[
                    "name"
                    if provider == "meta_ads"
                    else "adgroup_name"
                    if "adgroup/get" in req.url.path
                    else "campaign_name"
                ] = "<b>Owned Name</b>"
                if change == "metadata_foreign":
                    row["account_id" if provider == "meta_ads" else "advertiser_id"] = "999"
            if change == "metadata_parent" and (
                "adsets" in req.url.path or "adgroup/get" in req.url.path
            ):
                rows[0]["campaign_id"] = "999"
            if change in {"metadata_names_missing", "metadata_names_over_bound"}:
                for row in rows:
                    for field in ("name", "campaign_name", "adgroup_name"):
                        row[field] = None if change == "metadata_names_missing" else "x" * 161
            if change == "metadata_capacity":
                rows.extend([rows[0]] * 201)
            if change == "metadata_duplicate":
                rows.append(rows[0])
            return httpx.Response(200, json=data)
        return response

    class Transport(httpx.MockTransport):
        def close(self) -> None:
            closed.append(True)
            super().close()

    def transport() -> httpx.BaseTransport:
        constructed.append(True)
        return Transport(wire)

    monkeypatch.setattr(account_diagnostics, "diagnostic_transport", transport)
    path = f"/api/customer/v1/workspaces/{request.workspace_id}/planning/target-catalog-v2"
    payload = dict(
        account_id=request.account_id,
        starts_at=(observed_now - timedelta(days=1)).isoformat(),
        ends_at=observed_now.isoformat(),
    )
    assert alice.post(path, json=payload).status_code == 403
    assert bob.post(path, json=payload, headers=headers(bob)).status_code in {403, 404}
    assert not calls and not constructed
    if change == "unrepresentable_period":
        payload.update(starts_at="0001-01-01T00:00:00+14:00", ends_at="0001-01-02T00:00:00+14:00")
    response = alice.post(path, json=payload, headers=headers(alice))
    if change == "disabled":
        assert response.status_code == 503
        assert not calls and not constructed
    elif change == "unrepresentable_period":
        assert response.status_code == 422
        assert not calls and not constructed
    elif change and change not in {"metadata_names_missing", "metadata_names_over_bound"}:
        assert response.status_code in (
            {401, 402, 403, 409, 503} if change == "billing" else {401, 402, 403, 409}
        ), response.text
        if not change.startswith("metadata_"):
            assert len([c for c in calls if c != "oauth2.googleapis.com"]) <= 1
        assert len(closed) == 1
    else:
        assert response.status_code == 200, response.text
        composite = response.json()
        assert composite["schema_version"] == "inlet.planning-target-catalog.v2"
        if change in {"metadata_names_missing", "metadata_names_over_bound"}:
            assert all(t["entity"]["name"] is None for t in composite["targets"])
            assert all(
                t["entity"]["name_status"]
                == ("missing" if change == "metadata_names_missing" else "over_bound")
                for t in composite["targets"]
            )
        else:
            assert all(t["entity"]["name"] for t in composite["targets"])
        assert all(
            t["entity"]["reference"]["advertiser_id"]
            == ("1234567890" if provider == "google_ads" else "123")
            for t in composite["targets"]
        )
        if provider == "google_ads":
            child = next(t for t in composite["targets"] if t["entity"]["kind"] == "adgroup")
            if not change:
                assert child["entity"]["name"] == "<b>Child</b>"
            assert child["entity"]["status"] == "ENABLED"
            assert child["native_settings_key"] is None
        result = composite["native_observation"]
        assert result["advertising_writes_enabled"] is False
        assert result["spending_authority"] == "none"
        assert result["targets"]
        assert result["workspace_id"] == request.workspace_id
        assert result["account_id"] == request.account_id
        assert all(t["name"] is None for t in result["targets"])
        coverage = {c["kind"]: c for c in result["coverage"]}
        if provider == "google_ads":
            assert coverage["campaign"]["status"] == "complete"
            assert coverage["adgroup"]["status"] == "unavailable"
            campaign = result["targets"][0]
            assert campaign["settings"]["budget_explicitly_shared"] is True
            assert campaign["settings"]["budget_reference_count"] == 2
            assert campaign["settings"]["budget_amount_micros"] == 10000000
            assert campaign["budget_owner_key"] is not None
            assert campaign["budget_owner_key"] == result["targets"][1]["budget_owner_key"]
        else:
            assert all(c["status"] == "partial" for c in coverage.values())
            campaigns = {t["selection_key"] for t in result["targets"] if t["kind"] == "campaign"}
            assert all(
                t["parent_selection_key"] in campaigns
                for t in result["targets"]
                if t["kind"] != "campaign"
            )
        assert all(t["settings"]["platform"] == provider for t in result["targets"])
        assert response.headers["cache-control"] == "no-store"
        assert len(calls) >= 3 and len(closed) == 1
        for forbidden_text in (
            PRIVATE,
            "synthetic-refresh",
            "synthetic-secret",
            "mandate",
            "resource_name",
        ):
            assert forbidden_text not in response.text
        # No future/oversized periods or browser authority, and no subsequent HTTP.
        before = len(calls)
        for extra in (
            {"actor": request.actor},
            {"ends_at": (observed_now + timedelta(days=1)).isoformat()},
            {"starts_at": (observed_now - timedelta(days=367)).isoformat()},
        ):
            assert (
                alice.post(path, json={**payload, **extra}, headers=headers(alice)).status_code
                == 422
            )
        assert len(calls) == before
