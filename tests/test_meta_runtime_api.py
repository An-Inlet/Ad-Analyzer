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

from tests.meta_runtime_fixture import configured_meta_customer
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize("scenario", ["complete", "unknown_creation", "unknown_activation"])
def test_configured_meta_creation_then_separate_activation(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    scenario: str,
) -> None:
    alice, base, policy_body, draft, revision, server, requests, control = configured_meta_customer(
        customer_engine, configuration, tmp_path, monkeypatch, replicas
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
            "answer": {"kind": "meta_no_dsa", "special_category_answer": "none_applicable"},
            "cover_media_id": None,
        },
        201,
    )
    post(
        f"/social/reviews/{config['id']}/confirmation",
        {"expected_digest": config["digest"], "acknowledged": True},
    )
    reviewed = post(
        "/social/creation-reviews",
        {
            "configuration_review_id": config["id"],
            "expected_configuration_digest": config["digest"],
            "mandate_id": policy["id"],
            "mandate_revision": policy["revision"],
        },
        201,
    )
    run: dict[str, Any] = {}
    for activation in (False, True):
        if activation:
            reviewed = post(
                "/activation-reviews",
                {
                    "parent_run_id": run["id"],
                    "mandate_id": policy["id"],
                    "mandate_revision": policy["revision"],
                },
                201,
            )
        post(
            f"/reviews/{reviewed['id']}/approval",
            {"review_digest": reviewed["review_digest"], "plan_digest": reviewed["plan_digest"]},
        )
        run = post(f"/reviews/{reviewed['id']}/runs", expected=201)
        if scenario == "unknown_creation":
            server.timeout = True
            result = post(f"/runs/{run['id']}/advance")
            assert result["state"] == "unknown", result
            writes = server.posts
            server.timeout = False
            repeated = post(f"/runs/{run['id']}/advance")
            assert repeated["state"] == "unknown", repeated
            assert server.posts == writes == 1
            with Session(customer_engine) as db:
                assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 1
                assert db.scalar(select(func.count()).select_from(ProviderExposureReservation)) == 1
                reservation = db.scalar(select(ProviderExposureReservation))
                assert reservation and reservation.state == "held"
            return
        if activation and scenario == "unknown_activation":
            server.activation_timeout = True
            server.delay = True
            first = post(f"/runs/{run['id']}/advance")
            assert first["state"] == "unknown", first
            server.activation_timeout = False
            repeated = post(f"/runs/{run['id']}/advance")
            assert repeated["state"] == "unknown", repeated
            assert server.activations == 1
            with Session(customer_engine) as db:
                assert db.scalar(select(func.count()).select_from(ProviderExposureReservation)) == 1
            return
        expected_state = "activation_observed" if activation else "created_paused"
        for _ in range(30):
            run = post(f"/runs/{run['id']}/advance")
            if run["state"] == expected_state:
                break
        assert run["state"] == expected_state
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(ProviderExposureReservation)) == 1
        row = db.scalar(select(ProviderExposureReservation))
        assert row and row.state == "held"
    assert server.posts > 0 and server.activations > 0 and requests


@pytest.mark.parametrize(
    "scenario", ["revoke", "generation", "expired", "real_transport", "missing"]
)
def test_meta_configuration_boundary_fails_closed(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    scenario: str,
) -> None:
    import time
    from datetime import timedelta

    import httpx
    from app.customers.access import SESSION_COOKIE, digest
    from app.customers.models import CustomerSession
    from app.meta.models import MetaConnection
    from app.meta.security import Vault
    from app.production_runtime import provider_composition
    from app.production_runtime.meta_transport import meta_execution_transport
    from app.settings import settings

    from tests.test_commerce_measurement import NOW

    alice, base, _, draft, revision, server, requests, control = configured_meta_customer(
        customer_engine,
        configuration,
        tmp_path,
        monkeypatch,
        replicas,
    )

    def invalidate() -> None:
        with Session(customer_engine) as db:
            if scenario == "revoke":
                row = db.get(CustomerSession, digest(alice.cookies[SESSION_COOKIE]))
                assert row
                row.revoked_at = int(time.time())
            else:
                native = db.scalar(select(MetaConnection))
                assert native
                native.generation += 1
            db.commit()

    if scenario in {"revoke", "generation"}:
        control["callback"] = invalidate
    elif scenario == "expired":
        with Session(customer_engine) as db:
            native = db.scalar(select(MetaConnection))
            assert native
            native.encrypted_credentials = Vault(settings).seal(
                native.workspace_id,
                native.external_account_id,
                {
                    "access_token": "offline-meta-access",
                    "expires_at": (NOW - timedelta(seconds=1)).isoformat(),
                },
            )
            db.commit()
    elif scenario == "real_transport":

        def forbidden(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError("contract_test cannot construct real transport")

        monkeypatch.setattr(httpx, "HTTPTransport", forbidden)
        monkeypatch.setattr(
            provider_composition, "meta_execution_transport", meta_execution_transport
        )
    else:
        monkeypatch.setattr(provider_composition, "registered_meta_evidence", lambda name: None)
    response = alice.post(
        base + "/social/options",
        headers=headers(alice),
        json={"draft_id": draft, "draft_revision": revision},
    )
    assert response.status_code == 503, response.text
    assert server.posts == 0 and control["opened"] == control["closed"]
    if scenario in {"expired", "real_transport", "missing"}:
        assert requests == []
    if scenario == "missing":
        assert control["builds"] == 0


def test_tiktok_typed_and_direct_intents_cannot_build_meta_source(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
) -> None:
    from app.campaign_review.storage import get_media_store
    from app.customers.access import SESSION_COOKIE, CustomerPrincipal, digest
    from app.customers.models import CustomerSession, CustomerUser
    from app.production_runtime.provider_composition import configured_execution
    from app.publication.social_compiler import compile_social
    from app.settings import settings
    from fastapi import HTTPException

    from tests.test_commerce_measurement import NOW
    from tests.test_social_customer_catalog import request as catalog_request
    from tests.test_social_publication_http import tiktok_reviewed

    alice, base, _, _, _, _, requests, control = configured_meta_customer(
        customer_engine,
        configuration,
        tmp_path,
        monkeypatch,
        replicas,
    )
    with Session(customer_engine) as db:
        session = db.get(CustomerSession, digest(alice.cookies[SESSION_COOKIE]))
        assert session
        user = db.get(CustomerUser, session.user_id)
        assert user
        with configured_execution(
            db, CustomerPrincipal(user, session), replicas[2], settings, get_media_store
        ) as runtime:
            assert runtime is not None and runtime.social_review is not None
            plan = compile_social(tiktok_reviewed())
            with pytest.raises(HTTPException):
                runtime.creation.qualification_reader(plan, NOW)
            with pytest.raises(HTTPException):
                runtime.social_review.catalog(catalog_request(True), NOW)
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
    assert response.status_code == 404
    assert control["builds"] == 0 and control["opened"] == 0 and requests == []


def test_same_environment_coexistence_is_lazy_and_mismatch_denied(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
) -> None:
    from app.production_runtime import assembly
    from app.production_runtime.contracts import (
        GoogleEvidenceDescriptor,
        RegisteredGoogleEvidenceSource,
    )
    from app.settings import settings

    from tests.test_google_runtime_contracts import manifest

    alice, base, _, draft, revision, _, requests, control = configured_meta_customer(
        customer_engine,
        configuration,
        tmp_path,
        monkeypatch,
        replicas,
    )
    selected = manifest()
    descriptor = GoogleEvidenceDescriptor(
        source_id=selected.evidence_source_id,
        profile_digest=selected.evidence_profile_digest,
        environment="contract_test",
        kind="contract_scenario",
    )

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("Meta operation must not build Google evidence")

    registered = RegisteredGoogleEvidenceSource(descriptor, forbidden)
    monkeypatch.setattr(assembly, "registered_google_evidence", lambda name: registered)
    path = tmp_path / "coexisting-google.json"
    path.write_text(selected.model_dump_json())
    monkeypatch.setattr(settings, "google_execution_manifest_path", str(path))
    monkeypatch.setattr(settings, "google_execution_manifest_digest", selected.digest())
    response = alice.get(base + "/capabilities")
    assert response.status_code == 200
    assert [p["available"] for p in response.json()["providers"]] == [True, True, False]
    assert control["builds"] == 0 and requests == []
    result = alice.post(
        base + "/social/options",
        headers=headers(alice),
        json={"draft_id": draft, "draft_revision": revision},
    )
    assert result.status_code == 200, result.text
    assert control["builds"] == 1
    mismatched = selected.model_copy(update={"environment": "live", "live_execution_enabled": True})
    path.write_text(mismatched.model_dump_json())
    monkeypatch.setattr(settings, "google_execution_manifest_digest", mismatched.digest())
    before = len(requests)
    response = alice.get(base + "/capabilities")
    assert response.status_code == 409
    assert len(requests) == before and control["builds"] == 1
