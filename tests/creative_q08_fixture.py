"""Actual owned empty Meta query and genuinely confirmed zero-budget input."""

import copy
from dataclasses import replace
from pathlib import Path
from typing import Any

import httpx
import pytest
from app.collectors import account_diagnostics
from app.customers.access import SESSION_COOKIE
from app.settings import Settings
from sqlalchemy import Engine

from tests.creative_common_basis_fixture import CreativeCommonBasis, prepare_creative_common_basis
from tests.test_customer_optimization_api import headers
from tests.test_meta_native_inventory import Server


def prepare_creative_q08_basis(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    artifacts: Path,
) -> CreativeCommonBasis:
    fixture = prepare_creative_common_basis(
        customer_engine,
        configuration,
        replicas,
        monkeypatch,
        artifacts,
        platform="meta_ads",
    )
    alice, _, _ = replicas
    original_session = alice.cookies[SESSION_COOKIE]
    wid = fixture.basis.workspace_id
    server = Server()
    server.account["timezone_name"] = "America/New_York"
    server.campaigns = []
    server.adsets = []
    calls: list[str] = []

    def wire(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET" and request.url.host == "graph.facebook.com"
        calls.append(request.url.path)
        if "name" in request.url.params.get("fields", "").split(","):
            assert request.url.path.endswith(("/campaigns", "/adsets"))
            return httpx.Response(200, json={"data": []})
        return server(request)

    monkeypatch.setattr(
        account_diagnostics, "diagnostic_transport", lambda: httpx.MockTransport(wire)
    )
    root = f"/api/customer/v1/workspaces/{wid}"
    goal_url = root + "/goals/" + fixture.basis.goal_id
    existing = alice.get(goal_url)
    assert existing.status_code == 200, existing.text
    definition = copy.deepcopy(existing.json()["definition"])
    definition["budget_micros"] = 0
    changed = alice.put(
        goal_url,
        headers=headers(alice),
        json=dict(expected_revision=existing.json()["revision"], definition=definition),
    )
    assert changed.status_code == 200, changed.text
    revision = changed.json()["revision"]
    preview = alice.post(
        goal_url + "/preview", headers=headers(alice), json=dict(expected_revision=revision)
    )
    assert preview.status_code == 200, preview.text
    confirmed = alice.post(
        goal_url + "/confirm",
        headers=headers(alice),
        json=dict(
            expected_revision=revision,
            preview_id=preview.json()["preview_id"],
            idempotency_key="q08-confirm-zero",
        ),
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["confirmation_recorded"]
    body = copy.deepcopy(fixture.body)
    body["request_key"] = "q08-empty-zero"
    body["inputs"]["goal_revision"] = revision
    assert (
        body["inputs"]["exclusions"]
        == body["inputs"]["fixed_allocations"]
        == body["inputs"]["scenario_intents"]
        == []
    )
    assert alice.cookies[SESSION_COOKIE] == original_session
    basis = replace(
        fixture.basis,
        goal_revision=revision,
        confirmation_id=preview.json()["preview_id"],
        body=body,
    )
    return CreativeCommonBasis(basis=basis, body=body, calls=calls, store=fixture.store)
