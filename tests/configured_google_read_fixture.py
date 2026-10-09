"""Current configured reads using genuinely retained approved drafts; no financial writer."""

import base64
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from app.api.customer_execution import router
from app.production_runtime import assembly
from app.production_runtime.contracts import (
    GoogleEvidenceDescriptor,
    GoogleExecutionEvidence,
    GoogleExecutionManifestV1,
    RegisteredGoogleEvidenceSource,
)
from app.settings import Settings, settings
from pydantic import SecretStr
from sqlalchemy import Engine

from tests.configured_draft_retained_fixture import ConfiguredDraftIds
from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import login
from tests.test_google_activation import Server
from tests.test_google_runtime_contracts import manifest
from tests.test_provider_qualification import response_rows


def configured_customer(
    engine: Engine,
    config: Settings,
    path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    ids: ConfiguredDraftIds,
) -> Any:
    alice, _, provider = replicas
    monkeypatch.setattr(settings, "google_customer_client_id", "offline-client")
    monkeypatch.setattr(settings, "google_customer_client_secret", SecretStr("offline-secret"))
    monkeypatch.setattr(
        settings,
        "google_customer_encryption_key",
        SecretStr(base64.urlsafe_b64encode(b"g" * 32).decode()),
    )
    monkeypatch.setattr(settings, "media_storage_mode", "local_dev")
    monkeypatch.setattr(settings, "media_local_directory", str(path))
    draft_id, draft_revision = ids.draft_id, ids.draft_revision
    selected = manifest()
    file = path / "execution-manifest.json"
    file.write_text(selected.model_dump_json())
    monkeypatch.setattr(settings, "google_execution_manifest_path", str(file))
    monkeypatch.setattr(settings, "google_execution_manifest_digest", selected.digest())
    monkeypatch.setattr(assembly, "execution_clock", lambda: NOW)
    descriptor = GoogleEvidenceDescriptor(
        source_id=selected.evidence_source_id,
        profile_digest=selected.evidence_profile_digest,
        environment="contract_test",
        kind="contract_scenario",
    )

    def build(sessions: Any, authorize: Any, actor_id: str, clock: Any) -> GoogleExecutionEvidence:
        def forbidden(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError("Read fixture must never qualify financial execution")

        return GoogleExecutionEvidence(descriptor, forbidden, forbidden)

    registration = RegisteredGoogleEvidenceSource(descriptor, build)
    monkeypatch.setattr(
        assembly,
        "registered_google_evidence",
        lambda name: registration if name == descriptor.source_id else None,
    )
    rows = response_rows()
    rows["customer"].update(timeZone="Pacific/Pago_Pago", resourceName="customers/1234567890")
    rows["customConversionGoal"]["name"] = "Shop Purchases"
    rows["conversionAction"]["ownerCustomer"] = "customers/1234567890"
    server = Server()
    requests: list[httpx.Request] = []
    control: dict[str, Any] = {"transports_opened": 0, "transports_closed": 0}

    def wire(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        callback = control.pop("callback", None)
        if callback:
            callback()
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(
                200,
                json={"access_token": "offline-access", "expires_in": 3600, "token_type": "Bearer"},
            )
        if request.url.path.endswith("googleAds:search"):
            query = json.loads(request.content)["query"]
            table = query.split(" FROM ")[1].split()[0]
            key = table.split("_")[0] + "".join(p.title() for p in table.split("_")[1:])
            if key == "customer" and server.posts:
                qualification_callback = control.pop("qualification_callback", None)
                if qualification_callback:
                    qualification_callback()
            if key in rows:
                return httpx.Response(200, json={"results": [{key: rows[key]}]})
        return server(request)

    class TrackedTransport(httpx.MockTransport):
        def close(self) -> None:
            control["transports_closed"] += 1
            super().close()

    def transport(manifest: GoogleExecutionManifestV1) -> httpx.BaseTransport:
        control["transports_opened"] += 1
        return TrackedTransport(wire)

    monkeypatch.setattr(assembly, "google_execution_transport", transport)
    alice.app.include_router(router)
    assert login(alice, "configured-google:current-read") == ids.actor_id
    return (
        alice,
        f"/api/customer/v1/workspaces/{ids.workspace_id}/execution",
        {},
        draft_id,
        draft_revision,
        server,
        requests,
        control,
    )
