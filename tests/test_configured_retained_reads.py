"""Current actual configuration reads from genuine approved historical sources."""

from pathlib import Path
from typing import Any, cast

import pytest
from app.settings import Settings
from sqlalchemy import Engine

from tests.configured_draft_retained_fixture import retained_configured_draft_fixture
from tests.configured_google_read_fixture import configured_customer
from tests.configured_meta_read_fixture import configured_meta_customer
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.planning_boundary
@pytest.mark.parametrize("provider", ["google_ads", "meta_ads"])
def test_current_configured_owned_read(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    provider: Any,
) -> None:
    with retained_configured_draft_fixture(customer_engine, tmp_path / "retained", provider) as (
        engine,
        ids,
        media,
    ):
        clients = cast(Any, replicas).__wrapped__(engine, monkeypatch)
        build = configured_customer if provider == "google_ads" else configured_meta_customer
        alice, base, _, draft, revision, server, requests, control = build(
            engine, configuration, media, monkeypatch, clients, ids
        )
        endpoint = "/configuration-options" if provider == "google_ads" else "/social/options"
        body = {"draft_id": draft}
        if provider == "meta_ads":
            body["draft_revision"] = revision
        response = alice.post(base + endpoint, json=body, headers=headers(alice))
        assert response.status_code == 200, response.text
        assert response.json()["options"] and requests
        assert response.headers["cache-control"] == "no-store"
        assert server.posts == server.activations == 0
        keys = (
            ("transports_opened", "transports_closed")
            if provider == "google_ads"
            else ("opened", "closed")
        )
        assert control[keys[0]] == control[keys[1]] > 0
        capabilities = alice.get(base + "/capabilities")
        assert capabilities.status_code == 200
        value = capabilities.json()
        assert [p["available"] for p in value["providers"]] == [False, False, False]
        assert not value["activation_available"] and not value["advertising_writes_enabled"]
        assert value["scope"] == "planning_only"
        before = len(requests)
        denied = alice.post(base + "/mandates", json={}, headers=headers(alice))
        assert denied.status_code == 409 and denied.json()["detail"] == (
            "advertising_writes_disabled_in_planning_mvp"
        )
        assert len(requests) == before
        clients[0].close()
        clients[1].close()


@pytest.mark.planning_boundary
@pytest.mark.parametrize("provider", ["google_ads", "meta_ads"])
@pytest.mark.parametrize(
    "scenario",
    [
        "revoked",
        "foreign",
        "nonowner",
        "nonmember",
        "during_revoke",
        "generation",
        "real_transport",
        "missing",
    ],
)
def test_current_configured_adverse_read(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    provider: Any,
    scenario: str,
) -> None:
    import time

    import httpx
    from app.customers.access import SESSION_COOKIE, digest
    from app.customers.models import CustomerMembership, CustomerSession
    from app.google_connections.models import GoogleCustomerConnection
    from app.meta.models import MetaConnection
    from app.production_runtime import assembly, provider_composition
    from app.production_runtime.meta_transport import meta_execution_transport
    from app.production_runtime.owned_google_contexts import google_execution_transport
    from sqlalchemy.orm import Session

    from tests.test_customer_identity import login

    with retained_configured_draft_fixture(customer_engine, tmp_path / "retained", provider) as (
        engine,
        ids,
        media,
    ):
        clients = cast(Any, replicas).__wrapped__(engine, monkeypatch)
        build = configured_customer if provider == "google_ads" else configured_meta_customer
        alice, base, _, draft, revision, server, requests, control = build(
            engine, configuration, media, monkeypatch, clients, ids
        )
        endpoint = "/configuration-options" if provider == "google_ads" else "/social/options"
        body = {"draft_id": draft}
        if provider == "meta_ads":
            body["draft_revision"] = revision
        callbacks: list[str] = []
        real_constructions: list[bool] = []

        def invalidate() -> None:
            callbacks.append(scenario)
            with Session(engine) as db:
                if scenario in {"revoked", "during_revoke"}:
                    row = db.get(CustomerSession, digest(alice.cookies[SESSION_COOKIE]))
                    assert row
                    row.revoked_at = int(time.time())
                else:
                    native: GoogleCustomerConnection | MetaConnection | None
                    if provider == "google_ads":
                        native = db.get(GoogleCustomerConnection, ids.native_connection_id)
                    else:
                        native = db.get(MetaConnection, ids.native_connection_id)
                    assert native
                    native.generation += 1
                db.commit()

        if scenario == "revoked":
            invalidate()
        elif scenario == "foreign":
            body["draft_id"] = "f" * 32
        elif scenario in {"nonowner", "nonmember"}:
            other = login(alice, "unrelated-current-owner:1")
            if scenario == "nonowner":
                with Session(engine) as db:
                    db.add(
                        CustomerMembership(
                            user_id=other, workspace_id=ids.workspace_id, role="viewer"
                        )
                    )
                    db.commit()
        elif scenario in {"during_revoke", "generation"}:
            control["callback"] = invalidate
        elif scenario == "real_transport":

            def forbidden(*args: Any, **kwargs: Any) -> Any:
                real_constructions.append(True)
                raise AssertionError("real transport must not be constructed")

            monkeypatch.setattr(httpx, "HTTPTransport", forbidden)
            monkeypatch.setattr(
                assembly if provider == "google_ads" else provider_composition,
                "google_execution_transport"
                if provider == "google_ads"
                else "meta_execution_transport",
                google_execution_transport
                if provider == "google_ads"
                else meta_execution_transport,
            )
        else:
            monkeypatch.setattr(
                assembly if provider == "google_ads" else provider_composition,
                "registered_google_evidence"
                if provider == "google_ads"
                else "registered_meta_evidence",
                lambda name: None,
            )
        response = alice.post(base + endpoint, json=body, headers=headers(alice))
        expected = {"revoked": 401, "foreign": 404, "nonowner": 403, "nonmember": 404}.get(
            scenario, 409 if provider == "google_ads" else 503
        )
        if scenario == "during_revoke" and provider == "google_ads":
            expected = 401
        assert response.status_code == expected, response.text
        assert real_constructions == []
        if provider == "meta_ads" and scenario == "missing":
            assert control["builds"] == 0
        assert "advertising_writes_disabled" not in response.text
        assert server.posts == server.activations == 0
        if scenario in {"during_revoke", "generation"}:
            assert callbacks == [scenario] and requests
        else:
            assert requests == []
        keys = (
            ("transports_opened", "transports_closed")
            if provider == "google_ads"
            else ("opened", "closed")
        )
        assert control[keys[0]] == control[keys[1]]
        clients[0].close()
        clients[1].close()
