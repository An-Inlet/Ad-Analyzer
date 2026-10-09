import time
from pathlib import Path
from typing import Any

import pytest
from app.collectors import tiktok_customer_discovery as display
from app.customers.access import SESSION_COOKIE, digest
from app.customers.models import CustomerSession
from app.production_runtime import provider_composition
from app.publication.execution_models import (
    ProviderExecutionAttempt,
    ProviderExecutionReceipt,
    ProviderExecutionReview,
    ProviderExposureReservation,
)
from app.settings import Settings, settings
from app.sources.models import SourceConnection
from app.sources.security import SourceVault
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import login
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration
from tests.tiktok_discovery_fixture import configured_discovery_customer
from tests.tiktok_read_fixture import read_only_graph as read_only_graph

pytestmark = [pytest.mark.planning_boundary, pytest.mark.usefixtures("read_only_graph")]


@pytest.mark.parametrize("scenario", ["observed", "missing_events", "bc", "unconfigured", "source"])
def test_configured_discovery_has_no_execution_or_native_identifier_output(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    scenario: str,
) -> None:
    alice, base, body, requests, control, server = configured_discovery_customer(
        customer_engine,
        configuration,
        tmp_path,
        monkeypatch,
        replicas,
    )
    if scenario == "bc":
        body["identity_type"] = "BC_AUTH_TT"
    elif scenario == "unconfigured":
        for key in (
            "tiktok_execution_manifest_path",
            "tiktok_execution_manifest_digest",
            "tiktok_execution_bundle_path",
        ):
            monkeypatch.setattr(settings, key, None)
    elif scenario == "source":
        monkeypatch.setattr(provider_composition, "registered_tiktok_evidence", lambda _: None)
    elif scenario == "missing_events":
        control["missing_events"] = True
    response = alice.post(base + "/tiktok/discovery", json=body, headers=headers(alice))
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    value = response.json()
    assert value["publication_eligibility"] == "not_assessed"
    assert value["spending_authority"] == "none"
    if scenario in {"bc", "unconfigured", "source"}:
        assert value["status"] == "unavailable" and value["identity_count"] is None
        assert requests == []
    else:
        assert value["identity_count"] == value["pixel_count"] == 21
        assert len(value["identities"]) == len(value["pixels"]) == 20
        assert len(value["pixels"][0]["events"]) == (0 if scenario == "missing_events" else 20)
        assert value["display_truncated"] is True
        assert value["collection_completeness"] == "complete_requested_scope"
        assert value["event_count"] == (None if scenario == "missing_events" else 441)
        assert len(requests) == 3
        assert control["opened"] == control["closed"] == 2
        for secret in (
            "PRIVATE-",
            "access_token",
            "connection_version",
            '"scope":',
            "session_digest",
        ):
            assert secret not in response.text
    assert control["builds"] == 0  # No financial evidence builder is invoked.
    assert server.posts == server.activations == 0
    with Session(customer_engine) as db:
        for model in (
            ProviderExecutionAttempt,
            ProviderExecutionReceipt,
            ProviderExecutionReview,
            ProviderExposureReservation,
        ):
            assert db.scalar(select(func.count()).select_from(model)) == 0


@pytest.mark.parametrize(
    "scenario", ["csrf", "foreign", "revoke", "generation", "delivery", "token"]
)
def test_original_authority_changes_deny_discovery_without_partial_delivery(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    scenario: str,
) -> None:
    alice, base, body, requests, control, server = configured_discovery_customer(
        customer_engine,
        configuration,
        tmp_path,
        monkeypatch,
        replicas,
    )

    def revoke() -> None:
        with Session(customer_engine) as db:
            if scenario in {"generation", "token"}:
                source = db.scalar(
                    select(SourceConnection).where(SourceConnection.provider == "tiktok_ads")
                )
                assert source
                if scenario == "generation":
                    source.generation += 1
                else:
                    assert source.encrypted_grant
                    vault = SourceVault()
                    grant = vault.open(
                        source.workspace_id, source.provider, source.id, source.encrypted_grant
                    )
                    grant["access_token"] = "rotated-offline-token"
                    source.encrypted_grant = vault.seal(
                        source.workspace_id, source.provider, source.id, grant
                    )
            else:
                session = db.get(CustomerSession, digest(alice.cookies[SESSION_COOKIE]))
                assert session
                session.revoked_at = int(time.time())
            db.commit()

    client = alice
    if scenario in {"revoke", "generation"}:
        control["discovery_callback"] = revoke
    elif scenario == "token":
        control["between_reads_callback"] = revoke
    elif scenario == "delivery":
        original = display.project

        def project(*args: Any, **kwargs: Any) -> Any:
            result = original(*args, **kwargs)
            revoke()
            return result

        monkeypatch.setattr(display, "project", project)
    elif scenario == "foreign":
        login(client, "foreign-owner:1")
    response = client.post(
        base + "/tiktok/discovery", json=body, headers={} if scenario == "csrf" else headers(client)
    )
    assert response.status_code in {401, 403, 404, 409}, response.text
    assert "identities" not in response.text
    assert len(requests) == (
        0 if scenario in {"csrf", "foreign"} else 3 if scenario in {"delivery", "token"} else 1
    )
    assert control["opened"] == control["closed"]
    assert server.posts == server.activations == 0
