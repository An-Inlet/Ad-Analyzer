"""Actual owned empty declared Meta query and confirmed zero-budget V5 baseline."""

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from app.api import customer_planning_target_catalog
from app.collectors import account_diagnostics
from app.planning_documents.context import AccountTarget
from app.planning_documents.documents import PlanVersion
from app.settings import Settings
from sqlalchemy import Engine

from tests.creative_common_basis_fixture import prepare_creative_common_basis
from tests.test_creative_common_basis import financial_counts
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_meta_native_inventory import Server
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


def test_actual_v5_q08_empty_owned_query_zero_goal_baseline(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fixture = prepare_creative_common_basis(
        customer_engine,
        configuration,
        replicas,
        monkeypatch,
        tmp_path / "media",
        platform="meta_ads",
    )
    alice, _, _ = replicas
    wid, aid = fixture.basis.workspace_id, fixture.basis.account_id
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
    alice.app.include_router(customer_planning_target_catalog.router)
    window = body["inputs"]["reporting_window"]
    catalog = alice.post(
        root + "/planning/target-catalog-v2",
        headers=headers(alice),
        json=dict(
            account_id=aid, starts_at=window["starts_at"], ends_at=window["ends_at_exclusive"]
        ),
    )
    assert catalog.status_code == 200, catalog.text
    assert catalog.json()["targets"] == []
    baseline = financial_counts(customer_engine)
    assert baseline == (0,) * 6
    created = alice.post(root + "/planning/plans", headers=headers(alice), json=body)
    assert created.status_code == 201, created.text
    url = root + "/planning/plans/" + created.json()["plan_id"]
    intent = dict(expected_input_revision=1, expected_version=0, request_key="q08-generate-zero")
    result = alice.post(url + "/generate", headers=headers(alice), json=intent)
    assert result.status_code == 200, result.text
    document = result.json()["document"]
    doc = PlanVersion.model_validate(document)
    assert doc.policy_version == "inlet.descriptive-review.v5"
    assert doc.inputs.goal.revision == revision
    assert doc.inputs.total_ceiling_micros == 0
    assert doc.creative_proof is not None and len(doc.creative_proof.basis.images) == 1
    assert doc.creative_proof.basis.images[0].sha256 == fixture.basis.media_sha256
    assert doc.creative_composition is not None
    assert doc.creative_composition.proposals == () and doc.briefs == ()
    assert any("no included campaign" in text for text in doc.creative_composition.limitations)
    assert len(doc.actions) == 1
    action = doc.actions[0]
    assert isinstance(action.target, AccountTarget)
    assert (action.target.account.workspace_id, action.target.account.account_id) == (wid, aid)
    assert (
        action.kind == "investigate" and action.native_budget is None and not action.proposed_fields
    )
    assert "No included native campaign" in action.rationale
    assert "do not replace absent events with zero" in " ".join(action.manual_steps)
    assert all(ref.kind != "reported_metrics" for ref in doc.evidence)
    assert doc.selected_reporting_proof is not None
    assert all(p.capture_pin is None for p in doc.selected_reporting_proof.accounts)
    assert doc.scenarios
    for scenario in doc.scenarios:
        assert scenario.ceiling_micros == scenario.unallocated_micros == 0
        assert scenario.allocations == () and scenario.forecast is None
    assert doc.spending_authority == "none" and not doc.advertising_writes_enabled
    count = len(calls)
    assert count > 0
    replay = alice.post(url + "/generate", headers=headers(alice), json=intent)
    assert replay.status_code == 200 and replay.json() == result.json(), replay.text
    current = alice.get(url)
    assert current.status_code == 200 and current.json()["document"] == document, current.text
    assert current.json()["freshness"] == "current"
    exported = alice.get(url + "/export?version=1")
    assert exported.status_code == 200 and exported.json()["document"] == document, exported.text
    assert exported.json()["document_digest"] == doc.digest()
    assert len(calls) == count and financial_counts(customer_engine) == baseline
    prefix = f"q08-{customer_engine.dialect.name}"
    manifest = {}
    for label, payload in (
        ("catalog", catalog.json()),
        ("document", document),
        ("export", exported.json()),
    ):
        path = tmp_path / f"{prefix}-{label}.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        manifest[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (tmp_path / f"{prefix}-manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
