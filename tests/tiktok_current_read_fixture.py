"""Real configured TikTok APIs with explicit scenario evidence and actual MockHTTP."""

import base64
import json
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from app.api.customer_execution import router
from app.api.customer_social_execution import router as social_router
from app.api.customer_social_review import router as review_router
from app.campaign_review.storage import LocalMediaStore
from app.production_runtime import assembly, provider_composition
from app.production_runtime.tiktok_configuration import TikTokConfigurationBundleV1
from app.production_runtime.tiktok_contracts import (
    RegisteredTikTokEvidenceSource,
    TikTokEvidenceDescriptor,
    TikTokExecutionEvidence,
)
from app.publication.scoped_media import ScopedProviderMediaReader
from app.settings import Settings, settings
from pydantic import SecretStr
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import login
from tests.test_social_activation_journeys import Server
from tests.test_tiktok_runtime_contracts import bundle_document, manifest
from tests.tiktok_draft_retained_fixture import TikTokDraftIds


def configured_tiktok_customer(
    engine: Engine,
    config: Settings,
    path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    ids: TikTokDraftIds,
) -> Any:
    alice, _, _ = replicas
    monkeypatch.setattr(
        settings,
        "source_token_encryption_key",
        SecretStr(base64.urlsafe_b64encode(b"m" * 32).decode()),
    )
    monkeypatch.setattr(settings, "media_storage_mode", "local_dev")
    monkeypatch.setattr(settings, "media_local_directory", str(path))
    wid, draft, rev = ids.workspace_id, ids.draft_id, ids.draft_revision
    with Session(engine) as db:
        reader = ScopedProviderMediaReader(db, LocalMediaStore(path))
        media_binding = reader.binding(wid, ids.video_id)
        cover_binding = reader.binding(wid, ids.cover_id)
    document = bundle_document()
    # Match the reviewed creative language set exactly.
    bundle = TikTokConfigurationBundleV1.from_document(document)
    selected = manifest(bundle)
    mp, bp = path / "tiktok-manifest.json", path / "tiktok-bundle.json"
    mp.write_text(selected.model_dump_json())
    bp.write_text(json.dumps(document))
    monkeypatch.setattr(settings, "tiktok_execution_manifest_path", str(mp))
    monkeypatch.setattr(settings, "tiktok_execution_manifest_digest", selected.digest())
    monkeypatch.setattr(settings, "tiktok_execution_bundle_path", str(bp))
    monkeypatch.setattr(assembly, "execution_clock", lambda: NOW)
    descriptor = TikTokEvidenceDescriptor(
        source_id=selected.evidence_source_id,
        profile_digest=selected.evidence_profile_digest,
        environment="contract_test",
        kind="contract_scenario",
    )
    control: dict[str, Any] = {"builds": 0, "opened": 0, "closed": 0}
    server = Server("tiktok_ads")
    server.media = {"video": media_binding, "image": cover_binding}
    control["cover_id"] = cover_binding.media_id
    requests: list[httpx.Request] = []

    def wire(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        callback = control.pop("callback", None)
        if callback:
            callback()
        return server(request)

    class Tracked(httpx.MockTransport):
        def close(self) -> None:
            control["closed"] += 1
            super().close()

    def transport(manifest: Any) -> httpx.BaseTransport:
        assert manifest.environment == "contract_test"
        control["opened"] += 1
        return Tracked(wire)

    def build(sessions: Any, authorize: Any, actor_id: str, clock: Any) -> TikTokExecutionEvidence:
        control["builds"] += 1

        def forbidden(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError("Current reads must never qualify financial execution")

        def decoded(request: Any, now: Any) -> Any:
            from app.publication.social_catalog import SocialCatalog, TikTokCatalogOption

            callback = control.pop("catalog_callback", None)
            if callback:
                callback()
            return SocialCatalog(
                request=request,
                observed_at=now,
                expires_at=now + timedelta(seconds=60),
                currency="USD",
                account_timezone="UTC",
                options=[
                    TikTokCatalogOption(
                        label="Fixture identity / pixel",
                        profile_digest=bundle.profiles[0].digest(),
                        identity_id="identity",
                        pixel_id="42",
                    )
                ],
                unavailable_reasons=[],
                qualification_blockers=["tiktok_native_catalog_parser_unverified"],
                discovery_evidence="tiktok_decoded_contract_only",
            )

        return TikTokExecutionEvidence(descriptor, forbidden, forbidden, forbidden, decoded)

    registered = RegisteredTikTokEvidenceSource(descriptor, build)
    monkeypatch.setattr(
        provider_composition,
        "registered_tiktok_evidence",
        lambda name: registered if name == descriptor.source_id else None,
    )
    monkeypatch.setattr(provider_composition, "tiktok_execution_transport", transport)
    for item in (router, social_router, review_router):
        alice.app.include_router(item)
    assert login(alice, "configured-tiktok:current-read") == ids.actor_id
    body: dict[str, Any] = {}
    return (
        alice,
        f"/api/customer/v1/workspaces/{wid}/execution",
        body,
        draft,
        rev,
        server,
        requests,
        control,
    )
