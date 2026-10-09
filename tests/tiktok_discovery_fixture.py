"""Real configured source/vault/session; only native HTTP is replaced with fixture wire."""

from pathlib import Path
from typing import Any

import httpx
import pytest
from app.api.customer_optimization import router as optimization_router
from app.api.customer_tiktok_discovery import router
from app.production_runtime import provider_composition
from app.production_runtime.tiktok_configuration import load_tiktok_execution_configuration
from app.production_runtime.tiktok_contracts import (
    RegisteredTikTokEvidenceSource,
    TikTokEvidenceDescriptor,
)
from app.settings import Settings, settings
from sqlalchemy import Engine

from tests.test_social_activation_journeys import Server
from tests.test_tiktok_owned_discovery import response
from tests.tiktok_read_fixture import prepare_tiktok_read_source


def configured_discovery_customer(
    engine: Engine,
    configuration: Settings,
    path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    video: bytes | None = None,
) -> Any:
    ids = prepare_tiktok_read_source(engine, configuration, path, monkeypatch, replicas)
    alice = replicas[0]
    base = f"/api/customer/v1/workspaces/{ids.workspace_id}/execution"
    loaded = load_tiktok_execution_configuration(
        settings.tiktok_execution_manifest_path,
        settings.tiktok_execution_manifest_digest,
        settings.tiktok_execution_bundle_path,
    )
    assert loaded is not None
    selected = loaded[0]
    descriptor = TikTokEvidenceDescriptor(
        source_id=selected.evidence_source_id,
        profile_digest=selected.evidence_profile_digest,
        environment="contract_test",
        kind="contract_scenario",
    )
    control: dict[str, Any] = {"builds": 0, "opened": 0, "closed": 0}
    server = Server("tiktok_ads")

    def forbidden_build(*args: Any, **kwargs: Any) -> Any:
        control["builds"] += 1
        raise AssertionError("Read-only discovery must not build financial execution evidence")

    registered = RegisteredTikTokEvidenceSource(descriptor, forbidden_build)
    monkeypatch.setattr(
        provider_composition,
        "registered_tiktok_evidence",
        lambda name: registered if name == descriptor.source_id else None,
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
        {"account_id": ids.account_id, "identity_type": "TT_USER"},
        (requests),
        control,
        server,
    )
