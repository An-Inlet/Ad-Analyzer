"""Owned original-session linked capability reads with actual vault and MockHTTP."""

import json
import time
from pathlib import Path
from typing import Any

import httpx
import pytest
from app.collectors.tiktok_linked_capabilities import TikTokLinkedCapabilities
from app.collectors.tiktok_owned_discovery import TikTokDiscoveryUnavailable
from app.customers.access import SESSION_COOKIE, digest
from app.customers.models import CustomerSession
from app.publication.tiktok_linked_contracts import TikTokBusinessIdentityV1
from app.settings import Settings
from app.sources.models import SourceConnection
from fastapi import HTTPException
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.test_campaign_video import encoded as encoded
from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_shopify_sales import configuration as configuration
from tests.test_tiktok_owned_discovery import prepare
from tests.tiktok_read_fixture import read_only_graph as read_only_graph

IDENTITY = TikTokBusinessIdentityV1(
    identity_type="BC_AUTH_TT", identity_id="linked-123", identity_authorized_bc_id="bc-456"
)


def body(scope: Any, kind: str) -> dict[str, Any]:
    return {
        "code": 0,
        "data": {
            "identity_info": {
                **IDENTITY.model_dump(),
                "available_status": "AVAILABLE",
                "is_gpppa": False,
                "can_push_video": True,
                "can_pull_video": None,
            }
        }
        if kind == "identity"
        else {
            "list": [
                {
                    "advertiser_id": scope.external_advertiser_id,
                    "ads_only_mode": True,
                    "can_use_custom_identity": None,
                }
            ]
        },
    }


@pytest.mark.planning_boundary
@pytest.mark.usefixtures("read_only_graph")
@pytest.mark.parametrize("kind", ["identity", "advertiser"])
@pytest.mark.parametrize(
    "change", ["none", "revoke", "generation", "close", "wrong", "boolean", "duplicate"]
)
def test_owned_linked_read(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    encoded: Any,
    kind: str,
    change: str,
) -> None:
    scope, contexts, alice = prepare(
        customer_engine, configuration, tmp_path, monkeypatch, replicas, encoded()
    )
    calls: list[httpx.Request] = []

    def invalidate() -> None:
        with Session(customer_engine) as db:
            if change in {"revoke", "close"}:
                session = db.get(CustomerSession, digest(alice.cookies[SESSION_COOKIE]))
                assert session
                session.revoked_at = int(time.time())
            else:
                source = db.scalar(
                    select(SourceConnection).where(SourceConnection.provider == "tiktok_ads")
                )
                assert source
                source.generation += 1
            db.commit()

    def wire(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.method == "GET"
        assert request.headers["Access-Token"] == "offline-tiktok-access"
        if kind == "identity":
            assert request.url.path.endswith("/identity/info/")
            assert dict(request.url.params) == {
                "advertiser_id": scope.external_advertiser_id,
                **IDENTITY.model_dump(),
            }
        else:
            assert request.url.path.endswith("/advertiser/info/")
            assert json.loads(request.url.params["advertiser_ids"]) == [
                scope.external_advertiser_id
            ]
            assert json.loads(request.url.params["fields"]) == [
                "ads_only_mode",
                "can_use_custom_identity",
            ]
            assert set(request.url.params) == {"advertiser_ids", "fields"}
        payload = body(scope, kind)
        row = payload["data"]["identity_info"] if kind == "identity" else payload["data"]["list"][0]
        if change == "wrong":
            row["identity_authorized_bc_id" if kind == "identity" else "advertiser_id"] = "foreign"
        if change == "boolean":
            row["can_push_video" if kind == "identity" else "ads_only_mode"] = 1
        if change in {"revoke", "generation"}:
            invalidate()
        if change == "duplicate":
            return httpx.Response(200, content=b'{"code":0,"code":0,"data":{}}')
        return httpx.Response(200, json=payload)

    class Transport(httpx.MockTransport):
        def close(self) -> None:
            if change == "close":
                invalidate()
            super().close()

    reader = TikTokLinkedCapabilities(scope, contexts, Transport(wire), lambda: NOW)
    read = (lambda: reader.identity(IDENTITY)) if kind == "identity" else reader.advertiser
    try:
        if change != "none":
            with pytest.raises((TikTokDiscoveryUnavailable, HTTPException)):
                read()
        else:
            result = read()
            assert result.request.owner.workspace_id == scope.workspace_id
            assert result.observed_at == NOW < result.expires_at
            assert "offline-tiktok-access" not in result.model_dump_json()
            if kind == "identity":
                assert result.can_push_video.value is True  # type: ignore[union-attr]
                assert result.can_pull_video.presence == "null"  # type: ignore[union-attr]
                assert result.ads_only_mode.presence == "absent"
            else:
                assert result.ads_only_mode.value is True
                assert result.can_use_custom_identity.presence == "null"  # type: ignore[union-attr]
        assert len(calls) == 1
    finally:
        contexts.close()


@pytest.mark.parametrize("failure", ["oversized", "redirect", "nan", "array", "late_close"])
def test_transport_boundary(failure: str) -> None:
    from datetime import timedelta
    from types import SimpleNamespace
    from typing import cast

    from app.collectors import tiktok_linked_capabilities as linked
    from app.production_runtime.owned_tiktok_contexts import OwnedTikTokContexts
    from app.publication.execution_contracts import ExecutionAccount
    from pydantic import SecretStr

    now = [NOW]

    class Context:
        manifest = SimpleNamespace(environment="contract_test")

        def credentials(self, scope: ExecutionAccount) -> tuple[SecretStr, Any]:
            return SecretStr("offline-boundary-token"), NOW + timedelta(seconds=5)

    scope = ExecutionAccount.model_validate(
        {
            "workspace_id": 1,
            "account": {"platform": "tiktok_ads", "account_id": 2, "connection_id": 3},
            "external_advertiser_id": "123",
            "connection_version": "v1",
        }
    )

    def wire(request: httpx.Request) -> httpx.Response:
        if failure == "oversized":
            return httpx.Response(200, content=b" " * (linked.MAX_BYTES + 1))
        if failure == "redirect":
            return httpx.Response(302, headers={"Location": "https://example.invalid"})
        if failure == "nan":
            return httpx.Response(200, content=b'{"code":0,"data":{"list":NaN}}')
        if failure == "array":
            return httpx.Response(200, json=[])
        return httpx.Response(200, json=body(scope, "advertiser"))

    class Transport(httpx.MockTransport):
        def close(self) -> None:
            if failure == "late_close":
                now[0] += timedelta(seconds=6)
            super().close()

    reader = linked.TikTokLinkedCapabilities(
        scope, cast(OwnedTikTokContexts, Context()), Transport(wire), lambda: now[0]
    )
    with pytest.raises(TikTokDiscoveryUnavailable):
        reader.advertiser()
