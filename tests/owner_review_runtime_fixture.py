"""Genuine original-session input/catalog/upload path with an explicit private V6 factory."""

from functools import partial as partial_factory
from pathlib import Path
from typing import Any

import pytest
from app.api import customer_planning_documents as api
from app.planning_documents.ports import PlanningCompositionPolicy
from app.planning_documents.service import PlanningDocumentService
from app.settings import Settings
from sqlalchemy import Engine

from tests.google_budget_input_fixture import ready_inputs
from tests.google_budget_owner_discovery_fixture import OwnerCatalogResponseControl


def configured_owner_review(
    engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    partial: bool = False,
    response_control: OwnerCatalogResponseControl | None = None,
    native_names: dict[str, str] | None = None,
    configured_runtime: bool = False,
) -> tuple[Any, dict[str, Any], list[tuple[str, str]], dict[str, Any]]:
    # Existing helper obtains uploaded image, aggregate/selected capture and original
    # catalog/discovery receipts via real APIs. It does not save any input or plan.
    fixture, body, calls, catalog = ready_inputs(
        engine,
        configuration,
        replicas,
        monkeypatch,
        tmp_path,
        partial=partial,
        response_control=response_control,
        configured_runtime=configured_runtime,
        native_names=native_names,
    )
    if not configured_runtime:
        monkeypatch.setattr(
            api,
            "PlanningDocumentService",
            partial_factory(
                PlanningDocumentService,
                policy=PlanningCompositionPolicy(
                    version="inlet.descriptive-review.v6",
                    generator_version="inlet.descriptive-planning.v6",
                ),
                media_store=fixture.store,
            ),
        )
    from tests.test_customer_optimization_api import headers

    alice, _, _ = replicas
    root = f"/api/customer/v1/workspaces/{fixture.basis.workspace_id}/planning"
    before_calls = len(calls)
    discovery = alice.post(
        root + "/google-budget-owners",
        headers=headers(alice),
        json=dict(
            account_id=fixture.basis.account_id,
            catalog_composite_digest=catalog["composite_digest"],
            reporting_window=body["inputs"]["reporting_window"],
        ),
    )
    assert discovery.status_code == 200, discovery.text
    if partial:
        view = discovery.json()
        assert view["status"] == "unavailable" and view["owners"] == []
        assert view["reason"] == "google_budget_owner_unavailable"
        assert view["recovery"] == "Read fresh targets and review the full affected campaigns."
        assert body["inputs"]["google_daily_budget_intents"] == []
    else:
        assert discovery.json()["status"] == "available"
        assert any(
            option["owner_selection_id"]
            == body["inputs"]["google_daily_budget_intents"][0]["owner_selection_id"]
            for option in discovery.json()["owners"]
        )
    capability = alice.get(root + "/plans/capabilities")
    assert capability.status_code == 200, capability.text
    assert capability.json()["policy_version"] == "inlet.descriptive-review.v6"
    assert capability.json()["selected_reporting_available"] is True
    assert len(calls) == before_calls
    return fixture, body, calls, catalog


def confirm_zero_goal(alice: Any, fixture: Any, body: dict[str, Any]) -> None:
    """Change and explicitly confirm the real goal before saving the zero hypothesis."""
    from tests.test_customer_optimization_api import headers

    url = f"/api/customer/v1/workspaces/{fixture.basis.workspace_id}/goals/{fixture.basis.goal_id}"
    existing = alice.get(url)
    assert existing.status_code == 200, existing.text
    definition = existing.json()["definition"]
    definition["budget_micros"] = 0
    changed = alice.put(
        url,
        headers=headers(alice),
        json=dict(expected_revision=existing.json()["revision"], definition=definition),
    )
    assert changed.status_code == 200, changed.text
    revision = changed.json()["revision"]
    preview = alice.post(
        url + "/preview", headers=headers(alice), json=dict(expected_revision=revision)
    )
    assert preview.status_code == 200, preview.text
    confirmed = alice.post(
        url + "/confirm",
        headers=headers(alice),
        json=dict(
            expected_revision=revision,
            preview_id=preview.json()["preview_id"],
            idempotency_key="owner-v6-zero-goal",
        ),
    )
    assert confirmed.status_code == 200 and confirmed.json()["confirmation_recorded"], (
        confirmed.text
    )
    body["inputs"]["goal_revision"] = revision
    body["inputs"]["scenario_intents"][0]["allocations"][0]["amount_micros"] = 0
    body["inputs"]["scenario_intents"][0]["unallocated_micros"] = 0
    body["inputs"]["google_daily_budget_intents"][0]["requested_amount_micros"] = 0


def add_owned_meta(
    engine: Engine,
    alice: Any,
    fixture: Any,
    body: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    *,
    linked: bool,
) -> int:
    """Declared fixture connection bootstrap plus genuine owned native receipt, if linked."""
    import copy

    import httpx
    from app.collectors import account_diagnostics
    from app.settings import settings
    from cryptography.fernet import Fernet
    from pydantic import SecretStr

    from tests.creative_q05_fixture import _social_account
    from tests.test_customer_optimization_api import headers
    from tests.test_meta_native_inventory import Server

    monkeypatch.setattr(
        settings, "meta_token_encryption_key", SecretStr(Fernet.generate_key().decode())
    )
    monkeypatch.setattr(settings, "meta_client_secret", SecretStr("synthetic-app-secret"))
    aid = _social_account(engine, fixture.basis.workspace_id, "meta_ads")
    body["inputs"]["account_ids"].append(aid)
    google_factory = account_diagnostics.diagnostic_transport
    server = Server()
    server.account["timezone_name"] = "America/New_York"
    server.campaigns.append({**server.campaigns[0], "id": "7"})
    server.adsets.append({**server.adsets[0], "id": "8", "campaign_id": "7"})

    def wire(request: httpx.Request) -> httpx.Response:
        if request.url.host in {"googleads.googleapis.com", "oauth2.googleapis.com"}:
            assert request.method == "POST"
            assert (
                request.url.path == "/token"
                if request.url.host == "oauth2.googleapis.com"
                else request.url.path.endswith("/googleAds:search")
            )
            transport = google_factory()
            assert transport is not None
            with transport:
                return transport.handle_request(request)
        assert request.url.host == "graph.facebook.com" and request.method == "GET"
        fixture.calls.append("owner-meta-read")
        if "name" in request.url.params.get("fields", "").split(","):
            assert request.url.path.endswith(("/campaigns", "/adsets"))
            rows = copy.deepcopy(
                server.adsets if request.url.path.endswith("adsets") else server.campaigns
            )
            for row in rows:
                row["name"] = "Owned Mug " + row["id"]
            return httpx.Response(200, json={"data": rows})
        return server(request)

    monkeypatch.setattr(
        account_diagnostics, "diagnostic_transport", lambda: httpx.MockTransport(wire)
    )
    if linked:
        window = body["inputs"]["reporting_window"]
        response = alice.post(
            f"/api/customer/v1/workspaces/{fixture.basis.workspace_id}/planning/target-catalog-v2",
            headers=headers(alice),
            json=dict(
                account_id=aid, starts_at=window["starts_at"], ends_at=window["ends_at_exclusive"]
            ),
        )
        assert response.status_code == 200, response.text
        targets = [t for t in response.json()["targets"] if t["entity"]["kind"] == "campaign"]
        assert len(targets) == 2
        selectors = [
            dict(
                account_id=aid,
                canonical_entity_key=t["canonical_entity_key"],
                selection_key=t["selection_key"],
            )
            for t in targets
        ]
        body["inputs"]["scenario_intents"][0]["allocations"].append(
            dict(target=selectors[0], amount_micros=50_000_000)
        )
        body["inputs"]["scenario_intents"][0]["unallocated_micros"] -= 50_000_000
        body["inputs"]["exclusions"].append(selectors[1])
    return aid
