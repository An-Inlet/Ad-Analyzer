"""Q11: actual corrected acquisition joined to retained private V5 creative evidence."""

import json
import re
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pytest
from app.campaign_performance.selected_storage import historical_capture
from app.publication.execution_models import (
    ProviderExecutionAttempt,
    ProviderExecutionRun,
    ProviderExposureReservation,
)
from app.settings import Settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.creative_runtime_fixture import configured
from tests.test_creative_runtime_api import generation
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_selected_runtime_api import create
from tests.test_shopify_sales import configuration as configuration


def exact_rationale(text: str, primary: int) -> None:
    parts = text.split("Comparison", 1)
    assert len(parts) == 2
    for part, counts in zip(parts, ((primary, 100, 100), (0, 0, 0)), strict=True):
        for pattern, expected in zip(
            (
                r"(?<![\d.])selected count ([0-9]+(?:\.[0-9]+)?) ",
                r"(?<![\d.])([0-9]+(?:\.[0-9]+)?) observed clicks",
                r"(?<![\d.])([0-9]+(?:\.[0-9]+)?) USD observed spend",
            ),
            counts,
            strict=True,
        ):
            matches = re.findall(pattern, part)
            assert len(matches) == 1 and Decimal(matches[0]) == Decimal(expected)


def exact_capture(engine: Engine, wid: int, aid: int, capture_id: str, total: int) -> None:
    with Session(engine) as db:
        capture = historical_capture(db, wid, aid, capture_id)
        assert capture.capability == "supported" and capture.pagination_complete
        assert len(capture.facts) == 61
        for fact in capture.facts:
            assert fact.selected_conversions.presence == "present"
            expected = total if fact.metric_date.isoformat() == "2026-09-15" else 0
            assert fact.selected_conversions.value == Decimal(expected)


def test_actual_selected_correction_preserves_creative_basis_and_decision_history(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    f, root, body, _, _, _ = configured(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    url = create(f, root, body)
    first = f.alice.post(url + "/generate", headers=headers(f.alice), json=generation())
    assert first.status_code == 200, first.text
    original = first.json()
    assert original["document"]["policy_version"] == "inlet.descriptive-review.v5"
    basis_before = original["document"]["creative_proof"]["basis"]
    assert basis_before["requested"] == body["inputs"]["creative"]
    image_identity = [(x["media_id"], x["sha256"]) for x in basis_before["images"]]
    assert image_identity == [
        (x["media_id"], x["expected_sha256"])
        for x in body["inputs"]["creative"]["media_selections"]
    ]
    assert len(image_identity) == 1
    exact_rationale(original["document"]["actions"][0]["rationale"], 10)
    original_pin = original["document"]["selected_reporting_proof"]["accounts"][0]["capture_pin"]
    exact_capture(customer_engine, f.wid, f.aid, original_pin["capture_id"], 10)
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
    assert accepted.json()["event_sequence"] == 1
    accepted_event = accepted.json()["event"]
    for field in ("document_digest", "action_key", "action_digest", "decision"):
        assert accepted_event[field] == decision[field]
    assert accepted_event["version"] == 1 and accepted_event["workspace_id"] == f.wid
    assert accepted_event["plan_id"] == original["document"]["inputs"]["plan_id"]
    events_before = f.alice.get(url + "/events").json()
    assert events_before["items"] == [accepted.json()]
    assert events_before["next_cursor"] is None
    export_before = f.alice.get(url + "/export?version=1")
    assert export_before.status_code == 200, export_before.text
    assert export_before.json()["document"] == original["document"]
    old_transport = f.runtime.transport()
    assert isinstance(old_transport, httpx.MockTransport)
    corrected_reads: list[str] = []

    def corrected(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST" and request.url.path.endswith("googleAds:search")
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
    assert stale.json()["reasons"] == ["source_integrity_unavailable"]
    assert stale.json()["document"] == original["document"]
    blocked = f.alice.post(
        url + "/decisions",
        headers=headers(f.alice),
        json={**decision, "expected_event_sequence": 1, "request_key": "stale-correction"},
    )
    assert blocked.status_code == 409, blocked.text
    assert blocked.json() == {"detail": "source_integrity_unavailable"}
    assert f.alice.get(url + "/events").json() == events_before
    assert f.alice.get(url + "/export?version=1").json()["document"] == original["document"]
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
    exact_capture(customer_engine, f.wid, f.aid, capture_id, 4)
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
    assert document["policy_version"] == "inlet.descriptive-review.v5"
    basis_after = document["creative_proof"]["basis"]
    assert basis_after["requested"] == basis_before["requested"] == body["inputs"]["creative"]
    assert [(x["media_id"], x["sha256"]) for x in basis_after["images"]] == image_identity
    # Current byte checks may have new observation timestamps; history must not be rewritten.
    assert document["parent_digest"] == original["document_digest"]
    exact_rationale(document["actions"][0]["rationale"], 4)
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
    assert changes["previous_digest"] == original["document_digest"]
    assert changes["current_digest"] == successor.json()["document_digest"]
    assert any(
        x["path"][-1] == "rationale"
        and "selected count 10 " in x["before"]
        and "selected count 4 " in x["after"]
        for x in changes["changes"]
    )
    assert not any(
        x["path"][:3] == ["creative_proof", "basis", "requested"] for x in changes["changes"]
    )
    assert document["inputs"]["creative"] == original["document"]["inputs"]["creative"]
    for change in changes["changes"]:
        path = change["path"]
        assert path[:2] != ["inputs", "creative"]
        if path[:3] == ["creative_proof", "basis", "images"]:
            assert [
                {k: v for k, v in image.items() if k != "observed_at"} for image in change["before"]
            ] == [
                {k: v for k, v in image.items() if k != "observed_at"} for image in change["after"]
            ]
    assert f.alice.get(url + "/events").json() == events_before
    assert f.alice.get(url + "/versions/1").json()["document"] == original["document"]
    assert f.alice.get(url + "/export?version=1").json()["document"] == original["document"]
    assert f.alice.get(url).json()["freshness"] == "current"
    assert any("segments.conversion_action" in query for query in corrected_reads)
    assert any("segments.conversion_action" not in query for query in corrected_reads)
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(ProviderExecutionRun)) == 0
        assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 0
        assert db.scalar(select(func.count()).select_from(ProviderExposureReservation)) == 0

    # Synthetic customer-facing evidence only; no provider bodies or credentials.
    evidence = tmp_path / "q11-customer-evidence.json"
    evidence.write_text(
        json.dumps(
            {
                "original": original,
                "current": f.alice.get(url).json(),
                "comparison": changes,
                "events": f.alice.get(url + "/events").json(),
                "export": f.alice.get(url + "/export?version=1").json(),
            },
            sort_keys=True,
            indent=2,
        )
        + "\n"
    )
