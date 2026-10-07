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

from tests.google_runtime_fixture import configured_customer
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize("scenario", ["complete", "revoked_activation", "unknown_creation"])
def test_configured_google_creation_then_separate_activation(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    scenario: str,
) -> None:
    alice, base, policy_body, draft, revision, server, requests, control = configured_customer(
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
        assert control["transports_opened"] == control["transports_closed"]
        return response.json()

    policy = post("/mandates", policy_body, 201)
    catalog = post("/configuration-options", {"draft_id": draft})
    post(
        f"/mandates/{policy['id']}/consent",
        {"expected_revision": policy["revision"], "policy_digest": policy["policy_digest"]},
    )
    reviewed = post(
        "/creation-reviews",
        {
            "draft_id": draft,
            "draft_revision": revision,
            "mandate_id": policy["id"],
            "mandate_revision": policy["revision"],
            "google": {
                "catalog_option_id": catalog["options"][0]["id"],
                "daily_budget_micros": 20,
                "max_cpc_micros": 1,
                "search_partners": False,
            },
        },
        201,
    )
    run: dict[str, Any] = {}
    for activation in (False, True):
        if activation and scenario == "revoked_activation":
            import time

            from app.customers.access import SESSION_COOKIE, digest
            from app.customers.models import CustomerSession

            session_id = digest(alice.cookies[SESSION_COOKIE])

            def revoke_after_release(session_key: str = session_id) -> None:
                with Session(customer_engine) as concurrent:
                    session = concurrent.get(CustomerSession, session_key)
                    assert session is not None
                    session.revoked_at = int(time.time())
                    concurrent.commit()

            control["qualification_callback"] = revoke_after_release
            with Session(customer_engine) as db:
                before_receipts = db.scalar(
                    select(func.count()).select_from(ProviderExecutionReceipt)
                )
            writes = server.posts
            response = alice.post(
                base + "/activation-reviews",
                headers=headers(alice),
                json={
                    "parent_run_id": run["id"],
                    "mandate_id": policy["id"],
                    "mandate_revision": policy["revision"],
                },
            )
            assert response.status_code == 401, response.text
            assert control["transports_opened"] == control["transports_closed"]
            with Session(customer_engine) as db:
                assert (
                    db.scalar(select(func.count()).select_from(ProviderExecutionReceipt))
                    == before_receipts
                )
                assert db.scalar(select(func.count()).select_from(ProviderExposureReservation)) == 1
            assert server.posts == writes and server.activations == 0
            return
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
    "scenario", ["missing_manifest", "live_scenario", "social_body", "real_transport"]
)
def test_configured_admission_denies_before_source_or_http(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    scenario: str,
) -> None:
    from app.api.customer_social_execution import router as social_router
    from app.production_runtime import assembly
    from app.settings import settings

    from tests.test_google_runtime_contracts import manifest

    alice, base, policy_body, draft, revision, server, requests, control = configured_customer(
        customer_engine, configuration, tmp_path, monkeypatch, replicas
    )
    if scenario == "missing_manifest":
        monkeypatch.setattr(settings, "google_execution_manifest_path", None)
        monkeypatch.setattr(settings, "google_execution_manifest_digest", None)
    elif scenario == "live_scenario":
        configured = manifest().model_copy(
            update={"environment": "live", "live_execution_enabled": True}
        )
        path = tmp_path / "live-manifest.json"
        path.write_text(configured.model_dump_json())
        monkeypatch.setattr(settings, "google_execution_manifest_path", str(path))
        monkeypatch.setattr(settings, "google_execution_manifest_digest", configured.digest())
    elif scenario == "real_transport":
        import httpx
        from app.production_runtime.owned_google_contexts import google_execution_transport

        def forbidden_transport(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError("contract scenario must not construct a real transport")

        monkeypatch.setattr(httpx, "HTTPTransport", forbidden_transport)
        monkeypatch.setattr(assembly, "google_execution_transport", google_execution_transport)
    else:

        def forbidden_source(*args: Any) -> Any:
            raise AssertionError("social request must not resolve evidence source")

        monkeypatch.setattr(assembly, "registered_google_evidence", forbidden_source)
        alice.app.include_router(social_router)
        result = alice.post(
            base + "/social/creation-reviews",
            headers=headers(alice),
            json={
                "configuration_review_id": "a" * 32,
                "expected_configuration_digest": "b" * 64,
                "mandate_id": "c" * 32,
                "mandate_revision": 1,
            },
        )
        assert result.status_code == 409, result.text
        assert requests == []
        return
    # Lazy composition permits local consent preparation without constructing an
    # unused provider transport. Discovery is the first typed provider IO boundary.
    result = alice.post(
        base + ("/configuration-options" if scenario == "real_transport" else "/mandates"),
        headers=headers(alice),
        json={"draft_id": draft} if scenario == "real_transport" else policy_body,
    )
    assert result.status_code == 409, result.text
    assert requests == [] and server.posts == 0
    assert control["transports_opened"] == control["transports_closed"] == 0
