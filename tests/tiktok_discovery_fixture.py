"""Real configured source/vault/session; only native HTTP is replaced with fixture wire."""

from pathlib import Path
from typing import Any

import httpx
import pytest
from app.api.customer_optimization import router as optimization_router
from app.api.customer_tiktok_discovery import router
from app.production_runtime import provider_composition
from app.settings import Settings
from sqlalchemy import Engine

from tests.test_tiktok_owned_discovery import response
from tests.tiktok_runtime_fixture import configured_tiktok_customer


def configured_discovery_customer(
    engine: Engine,
    configuration: Settings,
    path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    video: bytes,
) -> Any:
    alice, base, policy, _, _, server, _, control = configured_tiktok_customer(
        engine,
        configuration,
        path,
        monkeypatch,
        replicas,
        video,
    )
    alice.app.include_router(router)
    alice.app.include_router(optimization_router)
    requests: list[httpx.Request] = []
    control["total"] = 21

    def wire(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.method == "GET"
        assert request.url.path in {"/open_api/v1.3/identity/get/", "/open_api/v1.3/pixel/list/"}
        callback = control.pop("discovery_callback", None)
        if callback:
            callback()
        document = response(request, total=control["total"])
        if "identity_list" in document["data"]:
            for row in document["data"]["identity_list"]:
                row.update(
                    identity_id="PRIVATE-IDENTITY-" + row["identity_id"],
                    display_name="Example Identity",
                    available_status="AVAILABLE",
                    can_push_video=True,
                    can_pull_video=False,
                    is_gpppa=False,
                    username="PRIVATE-USERNAME",
                    profile_image="PRIVATE-PROFILE",
                )
        else:
            for row in document["data"]["pixels"]:
                row.update(
                    pixel_id="PRIVATE-PIXEL-" + row["pixel_id"],
                    pixel_name="Example Pixel",
                    pixel_script="PRIVATE-SCRIPT",
                    asset_ownership={
                        "asset_relation_status": None,
                        "ownership_status": True,
                        "owner_bc_id": None,
                    },
                    events=[
                        {
                            "name": "Purchase",
                            "event_id": "PRIVATE-EVENT",
                            "optimization_event": "SHOPPING",
                            "deprecated": False,
                        }
                    ]
                    * 21,
                )
            if control.get("missing_events"):
                document["data"]["pixels"][0]["events"] = None
        return httpx.Response(200, json=document)

    class Transport(httpx.MockTransport):
        def close(self) -> None:
            control["closed"] += 1
            super().close()

    def transport(manifest: Any) -> httpx.BaseTransport:
        assert manifest.environment == "contract_test"
        control["opened"] += 1
        callback = control.pop("between_reads_callback", None) if control["opened"] == 2 else None
        if callback:
            callback()
        return Transport(wire)

    monkeypatch.setattr(provider_composition, "tiktok_execution_transport", transport)
    return (
        alice,
        base,
        {"account_id": policy["account_ids"][0], "identity_type": "TT_USER"},
        (requests),
        control,
        server,
    )
