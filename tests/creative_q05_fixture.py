"""One actual private-v5 Common Basis with three owned native catalogues."""

import copy
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

import httpx
import pytest
from app.ads.enums import AdvertisingPlatform
from app.ads.models import AdvertisingAccount
from app.api import customer_planning_target_catalog
from app.collectors import account_diagnostics
from app.customers.access import SESSION_COOKIE
from app.meta.models import MetaConnection
from app.meta.security import Vault as MetaVault
from app.settings import Settings, settings
from app.sources.models import SourceConnection
from app.sources.security import SourceVault
from app.workspaces.models import WorkspaceIntegration
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.creative_common_basis_fixture import CreativeCommonBasis, prepare_creative_common_basis
from tests.test_customer_optimization_api import headers
from tests.test_meta_native_inventory import PRIVATE
from tests.test_meta_native_inventory import Server as MetaServer
from tests.test_tiktok_native_inventory import Server as TikTokServer


@dataclass(frozen=True)
class CreativeQ05Basis:
    creative: CreativeCommonBasis
    account_ids: tuple[int, int, int]
    selectors: tuple[dict[str, Any], ...]
    body: dict[str, Any]
    native_calls: list[tuple[str, str]]


def _social_account(
    engine: Engine,
    wid: int,
    platform: str,
    *,
    currency: Literal["USD", "EUR"] = "USD",
    external_id: str = "123",
) -> int:
    # Fixture-owned connection bootstrap only, using keys initialized once below.
    now = datetime.now(UTC)
    bundle = dict(access_token=PRIVATE, expires_at=(now + timedelta(hours=1)).isoformat())
    with Session(engine) as db:
        integration = WorkspaceIntegration(
            workspace_id=wid,
            integration_key="common-" + platform,
            provider=platform,
            display_name="Mug " + platform,
            status="active",
            configuration={},
        )
        db.add(integration)
        db.flush()
        account = AdvertisingAccount(
            workspace_id=wid,
            connection_id=integration.id,
            platform=AdvertisingPlatform(platform),
            external_account_id=external_id,
            name="Mug " + platform,
            currency_code=currency,
            time_zone="America/New_York",
        )
        db.add(account)
        db.flush()
        if platform == "meta_ads":
            db.add(
                MetaConnection(
                    workspace_id=wid,
                    workspace_integration_id=integration.id,
                    account_id=account.id,
                    external_account_id=external_id,
                    encrypted_credentials=MetaVault(settings).seal(wid, external_id, bundle),
                    conversion_action_type="purchase",
                )
            )
        else:
            sid = uuid4().hex
            db.add(
                SourceConnection(
                    id=sid,
                    workspace_id=wid,
                    integration_id=integration.id,
                    account_id=account.id,
                    provider=platform,
                    external_id=external_id,
                    status="connected",
                    generation=1,
                    window_start=date(2026, 8, 1),
                    window_end=date(2026, 9, 30),
                    encrypted_grant=SourceVault().seal(wid, platform, sid, bundle),
                )
            )
        db.commit()
        aid = account.id
    return aid


def prepare_creative_q05_basis(
    engine: Engine,
    config: Settings,
    replicas: Any,
    patch: pytest.MonkeyPatch,
    artifacts: Path,
    *,
    meta_currency: Literal["USD", "EUR"] = "USD",
) -> CreativeQ05Basis:
    creative = prepare_creative_common_basis(
        engine, config, replicas, patch, artifacts, platform="google_ads", selected_value="10"
    )
    basis = creative.basis
    alice, _, _ = replicas
    alice.app.include_router(customer_planning_target_catalog.router)
    original_cookie = alice.cookies[SESSION_COOKIE]
    google_factory = account_diagnostics.diagnostic_transport
    patch.setattr(settings, "meta_token_encryption_key", SecretStr(Fernet.generate_key().decode()))
    patch.setattr(
        settings, "source_token_encryption_key", SecretStr(Fernet.generate_key().decode())
    )
    patch.setattr(settings, "meta_client_secret", SecretStr("synthetic-app-secret"))
    accounts = (
        basis.account_id,
        _social_account(engine, basis.workspace_id, "meta_ads", currency=meta_currency),
        _social_account(engine, basis.workspace_id, "tiktok_ads"),
    )
    meta, tiktok = MetaServer(), TikTokServer()
    meta.account["timezone_name"] = "America/New_York"
    meta.account["currency"] = meta_currency
    meta.campaigns.append({**meta.campaigns[0], "id": "7"})
    meta.adsets.append({**meta.adsets[0], "id": "8", "campaign_id": "7"})
    calls: list[tuple[str, str]] = []

    def wire(request: httpx.Request) -> httpx.Response:
        host = request.url.host
        calls.append((host, request.method))
        if host in {"googleads.googleapis.com", "oauth2.googleapis.com"}:
            assert request.method == "POST"
            if host == "oauth2.googleapis.com":
                assert request.url.path == "/token"
            else:
                assert request.url.path.endswith(("/googleAds:search", "/googleAds:searchStream"))
            transport = google_factory()
            assert transport is not None
            with transport:
                return transport.handle_request(request)
        assert request.method == "GET"
        if host == "graph.facebook.com":
            if "name" in request.url.params.get("fields", "").split(","):
                assert request.url.path.endswith(("/campaigns", "/adsets"))
                rows = copy.deepcopy(
                    meta.adsets if request.url.path.endswith("adsets") else meta.campaigns
                )
                for row in rows:
                    row["name"] = (
                        "Mug " + ("Ad Set " if "campaign_id" in row else "Campaign ") + row["id"]
                    )
                return httpx.Response(200, json={"data": rows})
            return meta(request)
        assert host == "business-api.tiktok.com"
        response = tiktok(request)
        payload = response.json()
        for row in payload["data"]["list"]:
            if "currency" in row:
                row["timezone"] = "America/New_York"
            elif "adgroup_id" in row:
                row["adgroup_name"] = "Mug Ad Group"
            else:
                row["campaign_name"] = "Mug Campaign"
        return httpx.Response(response.status_code, json=payload)

    patch.setattr(account_diagnostics, "diagnostic_transport", lambda: httpx.MockTransport(wire))
    root = f"/api/customer/v1/workspaces/{basis.workspace_id}"
    selectors: list[dict[str, Any]] = []
    for aid, native_id in zip(accounts, ("1", "5", "5"), strict=True):
        window = creative.body["inputs"]["reporting_window"]
        response = alice.post(
            root + "/planning/target-catalog-v2",
            headers=headers(alice),
            json=dict(
                account_id=aid, starts_at=window["starts_at"], ends_at=window["ends_at_exclusive"]
            ),
        )
        assert response.status_code == 200, response.text
        targets = [
            t
            for t in response.json()["targets"]
            if t["entity"]["kind"] == "campaign"
            and t["entity"]["reference"]["entity_id"] == native_id
        ]
        assert len(targets) == 1
        target = targets[0]
        assert response.json()["native_observation"]["account_id"] == aid
        assert response.json()["native_observation"]["workspace_id"] == basis.workspace_id
        if aid == accounts[1]:
            assert response.json()["native_observation"]["currency"] == meta_currency
            with Session(engine) as db:
                owned = db.get(AdvertisingAccount, aid)
                assert owned is not None
                assert (owned.workspace_id, owned.currency_code, owned.external_account_id) == (
                    basis.workspace_id,
                    meta_currency,
                    "123",
                )
        selectors.append(
            dict(
                account_id=aid,
                canonical_entity_key=target["canonical_entity_key"],
                selection_key=target["selection_key"],
            )
        )
    body = copy.deepcopy(creative.body)
    body["inputs"]["account_ids"] = list(accounts)
    body["inputs"]["scenario_intents"] = [
        dict(
            key=key,
            title=key,
            unallocated_micros=100_000_000,
            allocations=[
                dict(target=selector, amount_micros=amount * 1_000_000)
                for selector, amount in zip(selectors, amounts, strict=True)
            ],
        )
        for key, amounts in (("option_a", (400, 300, 200)), ("option_b", (300, 400, 200)))
    ]
    assert alice.cookies[SESSION_COOKIE] == original_cookie
    return CreativeQ05Basis(creative, accounts, tuple(selectors), body, calls)
