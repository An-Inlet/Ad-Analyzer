"""Q12 actual V6 HTTP CAS; SQLite parity, PostgreSQL overlapping requests."""

import copy
import hashlib
import hmac
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Lock
from typing import Any

import pytest
from app.customers.access import SESSION_COOKIE
from app.planning_documents.catalog_receipt_models import (
    CatalogReceiptRow,
    CatalogReceiptSelectionRow,
    InputCatalogReceiptRow,
)
from app.planning_documents.documents import PlanVersion
from app.planning_documents.models import (
    PlanDependencyRow,
    PlanEventRow,
    PlanInputRow,
    PlanRequestRow,
    PlanRow,
    PlanVersionRow,
)
from app.planning_documents.service import PlanningDocumentService
from app.settings import Settings
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.owner_review_runtime_fixture import configured_owner_review
from tests.test_creative_common_basis import financial_counts
from tests.test_customer_identity import ORIGIN
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


def graph(engine: Engine, wid: int, plan_id: str) -> dict[str, list[str]]:
    """Scoped immutable row commitments; artifacts never contain session digests."""
    models = (
        PlanRow,
        PlanInputRow,
        PlanVersionRow,
        PlanDependencyRow,
        PlanEventRow,
        PlanRequestRow,
        InputCatalogReceiptRow,
        CatalogReceiptRow,
        CatalogReceiptSelectionRow,
    )
    with Session(engine) as db:
        receipts = select(InputCatalogReceiptRow.receipt_id).where(
            InputCatalogReceiptRow.workspace_id == wid,
            InputCatalogReceiptRow.plan_id == plan_id,
        )
        result = {}
        for model in models:
            table = model.__table__
            query = select(table).where(table.c.workspace_id == wid)
            if model is PlanRow:
                query = query.where(table.c.id == plan_id)
            elif model is CatalogReceiptRow:
                query = query.where(table.c.id.in_(receipts))
            elif model is CatalogReceiptSelectionRow:
                query = query.where(table.c.receipt_id.in_(receipts))
            else:
                query = query.where(table.c.plan_id == plan_id)
            result[model.__tablename__] = sorted(
                hashlib.sha256(
                    json.dumps(dict(row), sort_keys=True, default=str).encode()
                ).hexdigest()
                for row in db.execute(query).mappings()
            )
        return result


def test_actual_v6_customer_edit_cas_replay_and_obsolete_decisions(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fixture, primitive, calls, _ = configured_owner_review(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    alice, _, _ = replicas
    original_cookie = alice.cookies[SESSION_COOKIE]
    provider_counts = len(calls), len(fixture.calls)
    wid = fixture.basis.workspace_id
    root = f"/api/customer/v1/workspaces/{wid}/planning/plans"
    before_effects = financial_counts(customer_engine)
    assert not any(before_effects)
    assert primitive["inputs"]["google_daily_budget_intents"]
    created = alice.post(root, headers=headers(alice), json=primitive)
    assert created.status_code == 201, created.text
    plan_id = created.json()["plan_id"]
    url = root + "/" + plan_id
    first = alice.post(
        url + "/generate",
        headers=headers(alice),
        json=dict(expected_input_revision=1, expected_version=0, request_key="q12-v6-first"),
    )
    assert first.status_code == 200, first.text
    original = first.json()
    doc1 = PlanVersion.model_validate(original["document"])
    assert doc1.policy_version == "inlet.descriptive-review.v6"
    assert doc1.google_budget_owner_review is not None
    assert len(doc1.google_budget_owner_review.reviews) == 1
    response = alice.get(url)
    assert response.status_code == 200, response.text
    view = response.json()
    action = view["document"]["actions"][0]
    decision = dict(
        expected_version=1,
        expected_event_sequence=0,
        document_digest=view["document_digest"],
        action_key=action["key"],
        action_digest=view["action_digests"][action["key"]],
        decision="accepted_for_manual_application",
        reason="Reviewed original owner plan",
        supersedes_event_id=None,
        request_key="q12-v1-accept",
    )
    accepted = alice.post(url + "/decisions", headers=headers(alice), json=decision)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["event_sequence"] == 1
    response = alice.get(url + "/events")
    assert response.status_code == 200, response.text
    events1 = response.json()
    assert events1["items"] == [accepted.json()]
    response = alice.get(url + "/export?version=1")
    assert response.status_code == 200, response.text
    export1 = response.json()
    immutable1 = graph(customer_engine, wid, plan_id)
    immutable1.pop(PlanRow.__tablename__)  # Heads are checked independently below.
    edits = []
    for index in range(2):
        body = copy.deepcopy(primitive)  # Primitive customer fields, never resolved DTOs.
        body.update(request_key=f"q12-edit-{index}", expected_input_revision=1, expected_version=1)
        body["inputs"]["milestone"] = f"Review customer alternative {index}"
        edits.append(body)
    barrier = Barrier(2)
    arrivals: list[str] = []
    lock = Lock()
    original_revise = PlanningDocumentService.revise

    def gated(service: Any, principal: Any, workspace: int, plan: str, request: Any) -> Any:
        assert workspace == wid and plan == plan_id
        assert request.request_key in {"q12-edit-0", "q12-edit-1"}
        with lock:
            arrivals.append(request.request_key)
        if customer_engine.dialect.name == "postgresql":
            barrier.wait(timeout=30)
        return original_revise(service, principal, workspace, plan, request)

    # Independent clients carry the same original session; no concurrent cookie jar.
    with (
        TestClient(alice.app, base_url=ORIGIN) as left,
        TestClient(alice.app, base_url=ORIGIN) as right,
    ):
        for client in (left, right):
            client.cookies.update(alice.cookies)
            same_session = hmac.compare_digest(client.cookies[SESSION_COOKIE], original_cookie)
            assert same_session, "original authenticated session changed"
        with monkeypatch.context() as patch:
            patch.setattr(PlanningDocumentService, "revise", gated)

            def send(index: int) -> Any:
                client = (left, right)[index]
                return client.post(url + "/inputs", headers=headers(client), json=edits[index])

            if customer_engine.dialect.name == "postgresql":
                with ThreadPoolExecutor(max_workers=2) as pool:
                    outcomes = list(pool.map(send, (0, 1)))
            else:
                outcomes = [send(0), send(1)]  # Sequential parity, not a SQLite race.
    assert sorted(arrivals) == ["q12-edit-0", "q12-edit-1"]
    assert sorted(r.status_code for r in outcomes) == [200, 409]
    winner = next(i for i, r in enumerate(outcomes) if r.status_code == 200)
    loser = outcomes[1 - winner]
    assert loser.json() == {"detail": "plan input or version changed"}
    assert outcomes[winner].json()["input_revision"] == 2
    after_edit = graph(customer_engine, wid, plan_id)
    assert len(after_edit[PlanInputRow.__tablename__]) == 2
    assert len(after_edit[PlanVersionRow.__tablename__]) == 1
    assert len(after_edit[PlanEventRow.__tablename__]) == 1
    assert len(after_edit[PlanRequestRow.__tablename__]) == 4  # create, generate, decide, revise
    assert len(after_edit[InputCatalogReceiptRow.__tablename__]) == 2
    with Session(customer_engine) as db:
        head = db.get(PlanRow, (wid, plan_id))
        assert head is not None
        assert (head.input_head, head.version_head, head.event_sequence) == (2, 1, 1)
    replay = alice.post(url + "/inputs", headers=headers(alice), json=edits[winner])
    assert replay.status_code == 200 and replay.json() == outcomes[winner].json(), replay.text
    assert graph(customer_engine, wid, plan_id) == after_edit
    altered = copy.deepcopy(edits[winner])
    altered["inputs"]["milestone"] = "Different content under the same key"
    conflict = alice.post(url + "/inputs", headers=headers(alice), json=altered)
    assert conflict.status_code == 409
    assert conflict.json() == {"detail": "request key is bound to different input"}
    assert graph(customer_engine, wid, plan_id) == after_edit
    lookup = alice.get(root + "/requests/revise/" + edits[winner]["request_key"])
    assert lookup.status_code == 200 and lookup.json() == replay.json()
    successor = alice.post(
        url + "/generate",
        headers=headers(alice),
        json=dict(expected_input_revision=2, expected_version=1, request_key="q12-v6-second"),
    )
    assert successor.status_code == 200, successor.text
    doc2 = PlanVersion.model_validate(successor.json()["document"])
    assert doc2.policy_version == doc1.policy_version
    assert doc2.parent_digest == doc1.digest()
    assert doc2.inputs.milestone == edits[winner]["inputs"]["milestone"]
    assert doc2.inputs.google_daily_budget_intents == doc1.inputs.google_daily_budget_intents
    assert doc2.inputs.creative == doc1.inputs.creative
    assert doc2.google_budget_owner_review is not None
    assert doc2.google_budget_owner_review.reviews == doc1.google_budget_owner_review.reviews
    response = alice.get(url)
    assert response.status_code == 200, response.text
    current = response.json()
    assert current["freshness"] == "current"
    assert current["document_digest"] == doc2.digest()
    before_denials = graph(customer_engine, wid, plan_id)
    obsolete = alice.post(
        url + "/decisions",
        headers=headers(alice),
        json={
            **decision,
            "expected_event_sequence": 1,
            "request_key": "q12-obsolete",
        },
    )
    assert obsolete.status_code == 409
    assert obsolete.json() == {"detail": "plan version or event sequence changed"}
    assert graph(customer_engine, wid, plan_id) == before_denials
    next_action = current["document"]["actions"][0]
    wrong_digest = (
        "0" * 64 if current["action_digests"][next_action["key"]] != "0" * 64 else "1" * 64
    )
    changed_action = alice.post(
        url + "/decisions",
        headers=headers(alice),
        json={
            **decision,
            "expected_version": 2,
            "expected_event_sequence": 1,
            "document_digest": doc2.digest(),
            "action_key": next_action["key"],
            "action_digest": wrong_digest,
            "request_key": "q12-changed-action",
        },
    )
    assert changed_action.status_code == 409
    assert changed_action.json() == {"detail": "plan version or action binding changed"}
    assert graph(customer_engine, wid, plan_id) == before_denials
    response = alice.get(url + "/comparisons/1/2")
    assert response.status_code == 200, response.text
    comparison = response.json()
    assert comparison["decisions_carried_over"] is False
    assert any(
        x["path"] == ["inputs", "milestone"]
        and x["before"] == doc1.inputs.milestone
        and x["after"] == doc2.inputs.milestone
        for x in comparison["changes"]
    )
    for name, original_rows in immutable1.items():
        assert set(original_rows) <= set(before_denials[name]), name
    response = alice.get(url + "/events")
    assert response.status_code == 200, response.text
    assert response.json() == events1
    response = alice.get(url + "/versions/1")
    assert response.status_code == 200, response.text
    assert response.json()["document"] == original["document"]
    response = alice.get(url + "/export?version=1")
    assert response.status_code == 200, response.text
    assert response.json()["document"] == export1["document"]
    with Session(customer_engine) as db:
        head = db.get(PlanRow, (wid, plan_id))
        assert head is not None
        assert (head.input_head, head.version_head, head.event_sequence) == (2, 2, 1)
    assert financial_counts(customer_engine) == before_effects
    same_session = hmac.compare_digest(alice.cookies[SESSION_COOKIE], original_cookie)
    assert same_session, "original authenticated session changed"
    assert (len(calls), len(fixture.calls)) == provider_counts
    (tmp_path / "q12-customer-evidence.json").write_text(
        json.dumps(
            {
                "original": original,
                "current": current,
                "comparison": comparison,
                "events": events1,
                "export": export1,
                "immutable_v1_graph": immutable1,
                "after_edit_graph": after_edit,
                "after_successor_graph": before_denials,
                "financial_before": before_effects,
                "financial_after": financial_counts(customer_engine),
                "concurrent": customer_engine.dialect.name == "postgresql",
                "winner": winner,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
