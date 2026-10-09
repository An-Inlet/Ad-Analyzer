"""Ordinary configured linked customer runtime: actual owned APIs, only MockHTTP evidence."""

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from app.api.customer_tiktok_linked import router
from app.production_runtime import assembly, provider_composition
from app.production_runtime.tiktok_contracts import TikTokExecutionManifestV1
from app.settings import Settings, settings
from sqlalchemy import Engine

from tests.test_commerce_measurement import NOW
from tests.test_tiktok_linked_configuration import linked_bundle
from tests.test_tiktok_owned_discovery import response
from tests.tiktok_current_read_fixture import configured_tiktok_customer
from tests.tiktok_draft_retained_fixture import TikTokDraftIds


def configured_linked_customer(
    engine: Engine,
    configuration: Settings,
    path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    ids: TikTokDraftIds,
) -> Any:
    values = configured_tiktok_customer(engine, configuration, path, monkeypatch, replicas, ids)
    alice, _, _, _, _, _, requests, control = values
    bundle = linked_bundle()
    assert settings.tiktok_execution_manifest_path and settings.tiktok_execution_bundle_path
    mp = Path(settings.tiktok_execution_manifest_path)
    manifest = TikTokExecutionManifestV1.model_validate_json(mp.read_text()).model_copy(
        update={"configuration_bundle_digest": bundle.digest()}
    )
    mp.write_text(manifest.model_dump_json())
    Path(settings.tiktok_execution_bundle_path).write_bytes(bundle._canonical)
    monkeypatch.setattr(settings, "tiktok_execution_manifest_digest", manifest.digest())
    control.update(now=NOW, can_push=True)
    monkeypatch.setattr(assembly, "execution_clock", lambda: control["now"])
    original_transport = provider_composition.tiktok_execution_transport

    def factory(selected: Any) -> httpx.BaseTransport:
        original = original_transport(selected)

        class LinkedTransport(httpx.MockTransport):
            def close(self) -> None:
                original.close()
                super().close()

        def wire(request: httpx.Request) -> httpx.Response:
            if request.method == "GET" and any(
                request.url.path.endswith(suffix)
                for suffix in ("/identity/get/", "/identity/info/", "/advertiser/info/")
            ):
                requests.append(request)
                callback = control.pop("discovery_callback", None)
                if callback:
                    callback()
                if request.url.path.endswith("/identity/get/"):
                    value = response(request, total=1)
                    value["data"]["identity_list"][0]["display_name"] = "Sample Linked Brand"
                elif request.url.path.endswith("/identity/info/"):
                    value = {
                        "code": 0,
                        "data": {
                            "identity_info": {
                                "identity_id": request.url.params["identity_id"],
                                "identity_type": "TT_USER",
                                "available_status": "AVAILABLE",
                                "is_gpppa": False,
                                "can_push_video": control["can_push"],
                            }
                        },
                    }
                else:
                    value = {
                        "code": 0,
                        "data": {
                            "list": [
                                {
                                    "advertiser_id": json.loads(
                                        request.url.params["advertiser_ids"]
                                    )[0],
                                    "ads_only_mode": True,
                                    "can_use_custom_identity": False,
                                }
                            ]
                        },
                    }
                return httpx.Response(200, json=value)
            return original.handle_request(request)

        return LinkedTransport(wire)

    monkeypatch.setattr(provider_composition, "tiktok_execution_transport", factory)
    alice.app.include_router(router)
    return values
