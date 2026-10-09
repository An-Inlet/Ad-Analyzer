"""Current configured reads using genuinely retained approved drafts; no financial writer."""

import base64
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from app.api.customer_execution import router
from app.api.customer_social_execution import router as social_router
from app.api.customer_social_review import router as review_router
from app.campaign_review.models import CampaignRevision
from app.campaign_review.storage import LocalMediaStore
from app.production_runtime import assembly, provider_composition
from app.production_runtime.meta_configuration import MetaConfigurationBundleV1
from app.production_runtime.meta_contracts import (
    MetaEvidenceDescriptor,
    MetaExecutionEvidence,
    RegisteredMetaEvidenceSource,
)
from app.publication.scoped_media import ScopedProviderMediaReader
from app.settings import Settings, settings
from pydantic import SecretStr
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.configured_draft_retained_fixture import ConfiguredDraftIds
from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import login
from tests.test_meta_runtime_contracts import bundle_document, manifest
from tests.test_social_activation_journeys import Server


def configured_meta_customer(
    engine: Engine,
    config: Settings,
    path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    ids: ConfiguredDraftIds,
) -> Any:
    alice, _, _ = replicas
    monkeypatch.setattr(
        settings,
        "meta_token_encryption_key",
        SecretStr(base64.urlsafe_b64encode(b"m" * 32).decode()),
    )
    monkeypatch.setattr(settings, "media_storage_mode", "local_dev")
    monkeypatch.setattr(settings, "media_local_directory", str(path))
    wid = ids.workspace_id
    draft, rev = ids.draft_id, ids.draft_revision
    with Session(engine) as db:
        row = db.get(CampaignRevision, (draft, rev))
        assert row
        media_id = row.artifact["definition"]["content"]["media"]["media_id"]
        media_binding = ScopedProviderMediaReader(db, LocalMediaStore(path)).binding(wid, media_id)
    document = bundle_document()
    # Match the reviewed creative language set exactly.
    bundle = MetaConfigurationBundleV1.from_document(document)
    selected = manifest(bundle)
    mp, bp = path / "meta-manifest.json", path / "meta-bundle.json"
    mp.write_text(selected.model_dump_json())
    bp.write_text(json.dumps(document))
    monkeypatch.setattr(settings, "meta_execution_manifest_path", str(mp))
    monkeypatch.setattr(settings, "meta_execution_manifest_digest", selected.digest())
    monkeypatch.setattr(settings, "meta_execution_bundle_path", str(bp))
    monkeypatch.setattr(assembly, "execution_clock", lambda: NOW)
    descriptor = MetaEvidenceDescriptor(
        source_id=selected.evidence_source_id,
        profile_digest=selected.evidence_profile_digest,
        environment="contract_test",
        kind="contract_scenario",
    )
    control: dict[str, Any] = {"builds": 0, "opened": 0, "closed": 0}
    server = Server("meta_ads")
    server.media = {"image": media_binding}
    requests: list[httpx.Request] = []

    def wire(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        callback = control.pop("callback", None)
        if callback:
            callback()
        if request.method == "GET" and request.url.path == "/v26.0/act_1234567890":
            return httpx.Response(
                200,
                json={
                    "account_id": "1234567890",
                    "account_status": 1,
                    "currency": "USD",
                    "timezone_name": "UTC",
                },
            )
        if request.url.path.endswith("/promote_pages"):
            return httpx.Response(200, json={"data": [{"id": "41", "name": "Owned Page"}]})
        if request.url.path.endswith("/adspixels"):
            return httpx.Response(200, json={"data": [{"id": "42", "name": "Owned Pixel"}]})
        return server(request)

    class Tracked(httpx.MockTransport):
        def close(self) -> None:
            control["closed"] += 1
            super().close()

    def transport(manifest: Any) -> httpx.BaseTransport:
        assert manifest.environment == "contract_test"
        control["opened"] += 1
        return Tracked(wire)

    def build(sessions: Any, authorize: Any, actor_id: str, clock: Any) -> MetaExecutionEvidence:
        control["builds"] += 1

        def forbidden(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError("Read fixture must never qualify financial execution")

        return MetaExecutionEvidence(descriptor, forbidden, forbidden, forbidden)

    registered = RegisteredMetaEvidenceSource(descriptor, build)
    monkeypatch.setattr(
        provider_composition,
        "registered_meta_evidence",
        lambda name: registered if name == descriptor.source_id else None,
    )
    monkeypatch.setattr(provider_composition, "meta_execution_transport", transport)
    for item in (router, social_router, review_router):
        alice.app.include_router(item)
    assert login(alice, "configured-meta:current-read") == ids.actor_id
    return (
        alice,
        f"/api/customer/v1/workspaces/{wid}/execution",
        {},
        draft,
        rev,
        server,
        requests,
        control,
    )
