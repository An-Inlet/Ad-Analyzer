"""Actual re-acquisition and selected successor lineage; a bounded Q11 subset."""

import json
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx
import pytest
from app.publication.execution_models import ProviderExecutionAttempt, ProviderExecutionRun
from app.settings import Settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_selected_runtime_api import configured, create, generation
from tests.test_shopify_sales import configuration as configuration


def test_actual_corrected_acquisition_preserves_history_and_requires_new_decision(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    f, root, body, _, _ = configured(customer_engine, configuration, replicas, monkeypatch)
    url = create(f, root, body)
    first = f.alice.post(url + "/generate", headers=headers(f.alice), json=generation())
    assert first.status_code == 200, first.text
    original = first.json()
    view = f.alice.get(url).json()
    action = view["document"]["actions"][0]
    decision = dict(
        expected_version=1,
        expected_event_sequence=0,
        document_digest=view["document_digest"],
        action_key=action["key"],
        action_digest=view["action_digests"][action["key"]],
        decision="accepted_for_manual_application",
        reason="Reviewed original selected event evidence",
        supersedes_event_id=None,
        request_key="before-correction-decision",
    )
    accepted = f.alice.post(url + "/decisions", headers=headers(f.alice), json=decision)
    assert accepted.status_code == 200, accepted.text
    events_before = f.alice.get(url + "/events").json()
    old_transport = f.runtime.transport()
    assert isinstance(old_transport, httpx.MockTransport)
    corrected_reads: list[str] = []

    def corrected(request: httpx.Request) -> httpx.Response:
        response = old_transport.handle_request(request)
        query = json.loads(request.content)["query"]
        assert request.url.path.endswith("googleAds:search")
        payload = response.json()
        if "metrics." in query:
            corrected_reads.append(query)
            for row in payload.get("results", []):
                if row.get("segments", {}).get("date") == "2026-09-15":
                    row["metrics"]["conversions"] = "4"
        return httpx.Response(response.status_code, json=payload)

    f.runtime = replace(f.runtime, transport=lambda: httpx.MockTransport(corrected))
    f.now = datetime.now(UTC)
    refreshed = f.post(
        "/aggregate-range",
        dict(
            account_id=f.aid,
            request_id=uuid4().hex,
            requested_starts_on="2026-08-01",
            requested_ends_on="2026-09-30",
        ),
    )
    assert refreshed.status_code == 200, refreshed.text
    stale = f.alice.get(url)
    assert stale.status_code == 200 and stale.json()["freshness"] == "source_changed"
    assert stale.json()["document"] == original["document"]
    blocked = f.alice.post(
        url + "/decisions",
        headers=headers(f.alice),
        json={**decision, "expected_event_sequence": 1, "request_key": "stale-correction"},
    )
    assert blocked.status_code == 409, blocked.text
    options = f.post("/event-options", {"account_id": f.aid})
    assert options.status_code == 200, options.text
    choice = next(x for x in options.json()["options"] if x["metric_family"] == "conversions")
    current_selection = f.alice.get(f.base + "/event-selection", params={"account_id": f.aid})
    assert current_selection.status_code == 200, current_selection.text
    selected = f.confirm(choice, current_selection.json())
    assert selected.status_code == 200, selected.text
    capture_id = uuid4().hex
    captured = f.post(
        "/captures",
        dict(
            account_id=f.aid,
            request_id=capture_id,
            expected_selection_id=selected.json()["selection_id"],
            expected_selection_digest=selected.json()["selection_digest"],
            starts_on="2026-08-01",
            ends_on="2026-09-30",
        ),
    )
    assert captured.status_code == 200, captured.text
    edited = f.alice.post(
        url + "/inputs",
        headers=headers(f.alice),
        json={
            **body,
            "request_key": "corrected-capture-input",
            "expected_input_revision": 1,
            "expected_version": 1,
            "inputs": {
                **body["inputs"],
                "selected_reporting": [{"account_id": f.aid, "capture_id": capture_id}],
            },
        },
    )
    assert edited.status_code == 200, edited.text
    successor = f.alice.post(
        url + "/generate",
        headers=headers(f.alice),
        json=dict(expected_input_revision=2, expected_version=1, request_key="corrected-plan"),
    )
    assert successor.status_code == 200, successor.text
    document = successor.json()["document"]
    assert document["parent_digest"] == original["document_digest"]
    assert "selected count 4 " in document["actions"][0]["rationale"]
    assert "100 observed clicks" in document["actions"][0]["rationale"]
    assert "100 USD observed spend" in document["actions"][0]["rationale"]
    assert "selected count 10 " in original["document"]["actions"][0]["rationale"]
    target = document["actions"][0]["target"]
    prior_target = original["document"]["actions"][0]["target"]
    for field in ("account", "provider_reference", "canonical_entity_key", "kind", "display_name"):
        assert target[field] == prior_target[field]
    assert target["selection_key"] != prior_target["selection_key"]
    old_pin = original["document"]["selected_reporting_proof"]["accounts"][0]["capture_pin"]
    new_pin = document["selected_reporting_proof"]["accounts"][0]["capture_pin"]
    assert new_pin["capture_id"] == capture_id != old_pin["capture_id"]
    assert new_pin["aggregate"] != old_pin["aggregate"]
    comparison = f.alice.get(url + "/comparisons/1/2")
    assert comparison.status_code == 200, comparison.text
    changes = comparison.json()
    assert changes["decisions_carried_over"] is False
    assert changes["omitted_changes"] == 0
    assert any(x["path"][-1] == "rationale" for x in changes["changes"])
    assert f.alice.get(url + "/events").json() == events_before
    assert f.alice.get(url + "/versions/1").json()["document"] == original["document"]
    assert f.alice.get(url + "/export?version=1").json()["document"] == original["document"]
    assert f.alice.get(url).json()["freshness"] == "current"
    assert any("segments.conversion_action" in query for query in corrected_reads)
    assert any("segments.conversion_action" not in query for query in corrected_reads)
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(ProviderExecutionRun)) == 0
        assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 0
