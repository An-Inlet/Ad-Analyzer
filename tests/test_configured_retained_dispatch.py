"""Current lazy dispatch/credential guards, separately from historical publication."""

from datetime import timedelta
from pathlib import Path
from typing import Any, cast

import pytest
from app.settings import Settings, settings
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.configured_draft_retained_fixture import retained_configured_draft_fixture
from tests.configured_meta_read_fixture import configured_meta_customer
from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.planning_boundary
@pytest.mark.parametrize("scenario", ["expired", "coexistence", "unsupported"])
def test_current_meta_configured_dispatch(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
) -> None:
    from app.meta.models import MetaConnection
    from app.meta.security import Vault
    from app.production_runtime import assembly
    from app.production_runtime.contracts import (
        GoogleEvidenceDescriptor,
        RegisteredGoogleEvidenceSource,
    )

    from tests.test_google_runtime_contracts import manifest

    with retained_configured_draft_fixture(customer_engine, tmp_path / "retained", "meta_ads") as (
        engine,
        ids,
        media,
    ):
        clients = cast(Any, replicas).__wrapped__(engine, monkeypatch)
        alice, base, _, draft, revision, server, requests, control = configured_meta_customer(
            engine, configuration, media, monkeypatch, clients, ids
        )
        if scenario == "expired":
            with Session(engine) as db:
                native = db.get(MetaConnection, ids.native_connection_id)
                assert native
                native.encrypted_credentials = Vault(settings).seal(
                    ids.workspace_id,
                    native.external_account_id,
                    {
                        "access_token": "offline-meta-access",
                        "expires_at": (NOW - timedelta(seconds=1)).isoformat(),
                    },
                )
                db.commit()
            response = alice.post(
                base + "/social/options",
                headers=headers(alice),
                json={"draft_id": draft, "draft_revision": revision},
            )
            assert response.status_code == 503
            assert response.json()["detail"] == "social_configuration_discovery_unavailable"
            assert not requests
        elif scenario == "coexistence":
            selected = manifest()
            descriptor = GoogleEvidenceDescriptor(
                source_id=selected.evidence_source_id,
                profile_digest=selected.evidence_profile_digest,
                environment="contract_test",
                kind="contract_scenario",
            )

            def forbidden(*args: Any, **kwargs: Any) -> Any:
                raise AssertionError("Meta read must not build Google evidence")

            registration = RegisteredGoogleEvidenceSource(descriptor, forbidden)
            monkeypatch.setattr(assembly, "registered_google_evidence", lambda name: registration)
            path = tmp_path / "google-manifest.json"
            path.write_text(selected.model_dump_json())
            monkeypatch.setattr(settings, "google_execution_manifest_path", str(path))
            monkeypatch.setattr(settings, "google_execution_manifest_digest", selected.digest())
            response = alice.get(base + "/capabilities")
            assert response.status_code == 200
            assert [p["available"] for p in response.json()["providers"]] == [False] * 3
            assert not requests and control["builds"] == 0
            response = alice.post(
                base + "/social/options",
                headers=headers(alice),
                json={"draft_id": draft, "draft_revision": revision},
            )
            assert response.status_code == 200 and response.json()["options"]
            assert requests and control["builds"] == 1
            mismatched = selected.model_copy(
                update={"environment": "live", "live_execution_enabled": True}
            )
            path.write_text(mismatched.model_dump_json())
            monkeypatch.setattr(settings, "google_execution_manifest_digest", mismatched.digest())
            before = len(requests)
            response = alice.get(base + "/capabilities")
            assert response.status_code == 409
            assert response.json()["detail"] == "provider_execution_environment_mismatch"
            assert len(requests) == before and control["builds"] == 1
        else:
            from app.campaign_review.storage import get_media_store
            from app.customers.access import SESSION_COOKIE, CustomerPrincipal, digest
            from app.customers.models import CustomerSession, CustomerUser
            from app.production_runtime.provider_composition import configured_execution
            from app.publication.social_compiler import compile_social
            from fastapi import HTTPException

            from tests.test_social_customer_catalog import request as catalog_request
            from tests.test_social_publication_http import tiktok_reviewed

            with Session(engine) as db:
                session = db.get(CustomerSession, digest(alice.cookies[SESSION_COOKIE]))
                user = db.get(CustomerUser, ids.actor_id)
                assert session and user
                with configured_execution(
                    db, CustomerPrincipal(user, session), clients[2], settings, get_media_store
                ) as runtime:
                    assert runtime and runtime.social_review
                    with pytest.raises(HTTPException):
                        runtime.creation.qualification_reader(
                            compile_social(tiktok_reviewed()), NOW
                        )
                    with pytest.raises(HTTPException):
                        runtime.social_review.catalog(catalog_request(True), NOW)
            assert control["builds"] == control["opened"] == 0 and not requests
            response = alice.post(
                base + "/social/creation-reviews",
                headers=headers(alice),
                json={
                    "configuration_review_id": "a" * 32,
                    "expected_configuration_digest": "b" * 64,
                    "mandate_id": "c" * 32,
                    "mandate_revision": 1,
                },
            )
            assert response.status_code == 409
            assert response.json()["detail"] == "advertising_writes_disabled_in_planning_mvp"
        assert server.posts == server.activations == 0
        assert control["opened"] == control["closed"]
        clients[0].close()
        clients[1].close()
