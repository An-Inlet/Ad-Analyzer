from pathlib import Path
from typing import Any

import pytest
from app.publication.execution_models import (
    ProviderExecutionAttempt,
    ProviderExecutionReceipt,
    ProviderExecutionReview,
    ProviderExposureReservation,
)
from app.settings import Settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.current_runtime_read_contexts import current_tiktok_source as current_tiktok_source
from tests.test_campaign_video import encoded as encoded
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration
from tests.tiktok_runtime_fixture import configured_tiktok_customer


def test_configured_custom_identity_cannot_create_future_review(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    encoded: Any,
) -> None:
    alice, base, policy_body, draft, revision, server, requests, control = (
        configured_tiktok_customer(
            customer_engine, configuration, tmp_path, monkeypatch, replicas, encoded()
        )
    )
    with Session(customer_engine) as db:
        for model in (
            ProviderExecutionReview,
            ProviderExecutionReceipt,
            ProviderExecutionAttempt,
            ProviderExposureReservation,
        ):
            assert db.scalar(select(func.count()).select_from(model)) == 0

    def post(path: str, body: Any = None, expected: int = 200) -> Any:
        response = alice.post(base + path, json=body, headers=headers(alice))
        assert response.status_code == expected, response.text
        assert control["opened"] == control["closed"]
        return response.json()

    policy = post("/mandates", policy_body, 201)
    post(
        f"/mandates/{policy['id']}/consent",
        {"expected_revision": policy["revision"], "policy_digest": policy["policy_digest"]},
    )
    catalog = post("/social/options", {"draft_id": draft, "draft_revision": revision})
    config = post(
        "/social/reviews",
        {
            "draft_id": draft,
            "draft_revision": revision,
            "option_id": catalog["options"][0]["id"],
            "answer": {"kind": "tiktok_cover", "reviewed_pair": True},
            "cover_media_id": control["cover_id"],
        },
        201,
    )
    post(
        f"/social/reviews/{config['id']}/confirmation",
        {"expected_digest": config["digest"], "acknowledged": True},
    )
    denied = post(
        "/social/creation-reviews",
        {
            "configuration_review_id": config["id"],
            "expected_configuration_digest": config["digest"],
            "mandate_id": policy["id"],
            "mandate_revision": policy["revision"],
        },
        409,
    )
    assert denied["detail"] == "tiktok_new_custom_identity_creation_unavailable"
    assert server.posts == 0 and server.activations == 0
    with Session(customer_engine) as db:
        for model in (
            ProviderExecutionReview,
            ProviderExecutionAttempt,
            ProviderExposureReservation,
        ):
            assert db.scalar(select(func.count()).select_from(model)) == 0
    # All five former forward scenarios live in test_tiktok_linked_runtime_api,
    # using actual linked consent and serializers rather than a legacy bypass.


@pytest.mark.parametrize(
    "scenario",
    [
        "revoke",
        "generation",
        "profile",
        "expired",
        "unknown_expiry",
        "naive_expiry",
        "real_transport",
        "missing",
        "partial",
        "billing",
    ],
)
@pytest.mark.planning_boundary
def test_tiktok_configuration_boundary(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    encoded: Any,
    scenario: str,
    current_tiktok_source: Any,
) -> None:
    from tests.tiktok_current_read_fixture import configured_tiktok_customer

    customer_engine, tmp_path, replicas, ids = current_tiktok_source

    import time
    from datetime import timedelta

    import httpx
    from app.customers.access import SESSION_COOKIE, digest
    from app.customers.models import CustomerSession
    from app.production_runtime import provider_composition
    from app.production_runtime.tiktok_transport import tiktok_execution_transport
    from app.settings import settings
    from app.sources.models import SourceConnection
    from app.sources.security import SourceVault

    from tests.test_commerce_measurement import NOW

    alice, base, _, draft, revision, server, requests, control = configured_tiktok_customer(
        customer_engine, configuration, tmp_path, monkeypatch, replicas, ids
    )

    def invalidate() -> None:
        if scenario == "profile":
            monkeypatch.setattr(settings, "tiktok_execution_manifest_digest", "f" * 64)
            return
        with Session(customer_engine) as db:
            if scenario == "revoke":
                session = db.get(CustomerSession, digest(alice.cookies[SESSION_COOKIE]))
                assert session
                session.revoked_at = int(time.time())
            else:
                source = db.scalar(select(SourceConnection))
                assert source
                source.generation += 1
            db.commit()

    if scenario in {"revoke", "generation", "profile"}:
        control["catalog_callback"] = invalidate
    elif scenario in {"expired", "unknown_expiry", "naive_expiry"}:
        with Session(customer_engine) as db:
            source = db.scalar(select(SourceConnection))
            assert source and source.encrypted_grant
            grant = SourceVault().open(
                wid := source.workspace_id, "tiktok_ads", source.id, source.encrypted_grant
            )
            grant["expires_at"] = (
                None
                if scenario == "unknown_expiry"
                else (NOW + timedelta(hours=1)).replace(tzinfo=None).isoformat()
                if scenario == "naive_expiry"
                else (NOW - timedelta(seconds=1)).isoformat()
            )
            source.encrypted_grant = SourceVault().seal(wid, "tiktok_ads", source.id, grant)
            db.commit()
    elif scenario == "billing":
        monkeypatch.setattr(settings, "billing_required", True)
        monkeypatch.setattr(settings, "billing_price_id", None)
    elif scenario == "partial":
        monkeypatch.setattr(settings, "tiktok_execution_bundle_path", None)
    elif scenario == "missing":
        monkeypatch.setattr(provider_composition, "registered_tiktok_evidence", lambda _: None)
    else:

        def forbidden(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError("contract scenario must not construct a real transport")

        monkeypatch.setattr(httpx, "HTTPTransport", forbidden)
        monkeypatch.setattr(
            provider_composition, "tiktok_execution_transport", tiktok_execution_transport
        )
    response = alice.post(
        base + "/social/options",
        headers=headers(alice),
        json={"draft_id": draft, "draft_revision": revision},
    )
    assert response.status_code == 503, response.text
    assert requests == [] and server.posts == 0
    assert control["opened"] == control["closed"]


def test_meta_tiktok_composition_is_lazy_and_environment_exact(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    encoded: Any,
) -> None:
    import json

    from app.production_runtime import provider_composition
    from app.production_runtime.meta_configuration import MetaConfigurationBundleV1
    from app.production_runtime.meta_contracts import (
        MetaEvidenceDescriptor,
        RegisteredMetaEvidenceSource,
    )
    from app.settings import settings

    from tests.test_meta_runtime_contracts import bundle_document, manifest

    alice, base, _, draft, revision, _, requests, control = configured_tiktok_customer(
        customer_engine, configuration, tmp_path, monkeypatch, replicas, encoded()
    )
    document = bundle_document()
    selected = manifest(MetaConfigurationBundleV1.from_document(document))
    descriptor = MetaEvidenceDescriptor(
        source_id=selected.evidence_source_id,
        profile_digest=selected.evidence_profile_digest,
        environment="contract_test",
        kind="contract_scenario",
    )

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("TikTok must not construct the unused Meta source")

    registered = RegisteredMetaEvidenceSource(descriptor, forbidden)
    monkeypatch.setattr(provider_composition, "registered_meta_evidence", lambda _: registered)
    mp, bp = tmp_path / "coexist-meta.json", tmp_path / "coexist-meta-bundle.json"
    mp.write_text(selected.model_dump_json())
    bp.write_text(json.dumps(document))
    monkeypatch.setattr(settings, "meta_execution_manifest_path", str(mp))
    monkeypatch.setattr(settings, "meta_execution_manifest_digest", selected.digest())
    monkeypatch.setattr(settings, "meta_execution_bundle_path", str(bp))
    capability = alice.get(base + "/capabilities")
    assert capability.status_code == 200, capability.text
    assert [p["available"] for p in capability.json()["providers"]] == [False, True, True]
    assert control["builds"] == 0 and requests == []
    result = alice.post(
        base + "/social/options",
        headers=headers(alice),
        json={"draft_id": draft, "draft_revision": revision},
    )
    assert result.status_code == 200, result.text
    assert "tiktok_native_catalog_parser_unverified" in result.json()["blockers"]
    assert control["builds"] == 1 and requests == []
    live = selected.model_copy(update={"environment": "live", "live_execution_enabled": True})
    mp.write_text(live.model_dump_json())
    monkeypatch.setattr(settings, "meta_execution_manifest_digest", live.digest())
    assert alice.get(base + "/capabilities").status_code == 409
    assert control["builds"] == 1 and control["opened"] == control["closed"]
