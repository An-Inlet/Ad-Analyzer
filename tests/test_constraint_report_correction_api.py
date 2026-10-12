"""Configured V7 customer-report correction CAS, never independent provider observation."""

import hmac
import io
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier, Lock
from typing import Any

import pytest
from app.api import customer_planning_documents as api
from app.campaign_review.storage import get_media_store
from app.customers.access import SESSION_COOKIE
from app.lifecycle.privacy import bump_workspace_export_revision
from app.main import app
from app.planning_documents.documents import PlanVersion
from app.planning_documents.events import ManualAssertion
from app.planning_documents.models import (
    PlanDependencyRow,
    PlanEventRow,
    PlanInputRow,
    PlanRequestRow,
    PlanRow,
    PlanVersionRow,
)
from app.planning_documents.service import PlanningDocumentService
from app.settings import Settings, settings
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.creative_common_basis_fixture import prepare_creative_common_basis
from tests.test_creative_common_basis import financial_counts
from tests.test_creative_runtime_composition import media_config
from tests.test_customer_exports import unpack
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import login
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_owner_review_customer_cas import graph
from tests.test_planning_runtime_composition import configure
from tests.test_shopify_sales import configuration as configuration


def test_configured_v7_customer_report_correction_lifecycle(
    customer_engine: Engine,
    request: pytest.FixtureRequest,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    media_config(monkeypatch, tmp_path / "media")
    configure(monkeypatch, "v7")
    fixture = prepare_creative_common_basis(
        customer_engine, configuration, replicas, monkeypatch, tmp_path / "media",
        platform="meta_ads", configured_runtime=True,
    )
    primitive = deepcopy(fixture.body)
    primitive["inputs"]["constraints"] = ["No discount claims."]
    primitive["inputs"]["creative"]["product"]["restrictions"] = ["No discount claims."]
    monkeypatch.setattr(app, "dependency_overrides", dict(replicas[0].app.dependency_overrides))
    assert vars(api)["PlanningDocumentService"] is PlanningDocumentService
    assert get_media_store not in app.dependency_overrides
    alice = TestClient(app, base_url=str(replicas[0].base_url))
    request.addfinalizer(alice.close)
    alice.cookies.update(replicas[0].cookies)
    original_cookie = alice.cookies[SESSION_COOKIE]
    wid = fixture.basis.workspace_id
    root = f"/api/customer/v1/workspaces/{wid}/planning/plans"
    created = alice.post(root, headers=headers(alice), json=primitive)
    assert created.status_code == 201, created.text
    plan_id = created.json()["plan_id"]
    url = root + "/" + plan_id
    generated = alice.post(url + "/generate", headers=headers(alice), json=dict(
        expected_input_revision=1, expected_version=0, request_key="q13-v7-generate",
    ))
    assert generated.status_code == 200, generated.text
    document = PlanVersion.model_validate(generated.json()["document"])
    assert document.creative_composition is not None
    action = document.creative_composition.proposals[0].action
    assert action.kind == "creative_review" and not action.proposed_fields
    assert action.native_budget is None
    provider_reads = list(fixture.calls)
    effects = financial_counts(customer_engine)
    assert effects == (0,) * 6
    report: dict[str, Any] = dict(
        expected_version=1, expected_event_sequence=0,
        document_digest=document.digest(), action_key=action.key, action_digest=action.digest(),
        assertion="customer_reports_applied", reported_applied_at=datetime.now(UTC).isoformat(),
        statement="Customer reports completing creative review; no published ad claimed.",
        supersedes_event_id=None, request_key="q13-v7-original-report",
    )
    baseline = graph(customer_engine, wid, plan_id)
    spoofed = alice.post(url + "/assertions", headers=headers(alice), json={
        **report, "verification": "provider_verified",
    })
    assert spoofed.status_code == 422, spoofed.text
    assert graph(customer_engine, wid, plan_id) == baseline
    first = alice.post(url + "/assertions", headers=headers(alice), json=report)
    assert first.status_code == 200, first.text
    original = first.json()
    original_event = ManualAssertion.model_validate(original["event"])
    original_event.assert_document(document)
    assert original_event.verification == "customer_report_only"
    before_race = graph(customer_engine, wid, plan_id)
    corrections: list[dict[str, Any]] = [{
        **report, "expected_event_sequence": 1,
        "supersedes_event_id": original_event.event_id,
        "statement": f"Correction {index}: reviewed copy only; image rights still unresolved.",
        "request_key": f"q13-v7-correction-{index}",
    } for index in range(2)]
    barrier, lock = Barrier(2), Lock()
    arrivals: list[str] = []
    outcomes: list[dict[str, Any]] = []
    original_assert = PlanningDocumentService.assert_applied

    def gated(service: Any, principal: Any, workspace: int, plan: str, request: Any) -> Any:
        assert workspace == wid and plan == plan_id
        assert request.request_key in {c["request_key"] for c in corrections}
        with lock:
            arrivals.append(request.request_key)
        if customer_engine.dialect.name == "postgresql":
            barrier.wait(timeout=30)  # Before fresh identity IO or transaction/locks.
        return original_assert(service, principal, workspace, plan, request)

    try:
        with (
            TestClient(app, base_url=str(alice.base_url)) as left,
            TestClient(app, base_url=str(alice.base_url)) as right,
            monkeypatch.context() as patch,
        ):
            for client in (left, right):
                client.cookies.update(alice.cookies)
                same_session = hmac.compare_digest(client.cookies[SESSION_COOKIE], original_cookie)
                assert same_session, "original correction session differs"
            patch.setattr(PlanningDocumentService, "assert_applied", gated)

            def send(index: int) -> Any:
                client = (left, right)[index]
                try:
                    response = client.post(
                        url + "/assertions", headers=headers(client), json=corrections[index]
                    )
                    outcome = dict(index=index, status=response.status_code, body=response.json())
                except BaseException as error:
                    outcome = dict(index=index, exception=type(error).__name__)
                    with lock:
                        outcomes.append(outcome)
                    raise
                with lock:
                    outcomes.append(outcome)
                return response

            if customer_engine.dialect.name == "postgresql":
                with ThreadPoolExecutor(max_workers=2) as pool:
                    responses = list(pool.map(send, (0, 1)))
            else:
                responses = [send(0), send(1)]  # Sequential CAS parity, not concurrent SQLite.
    finally:
        original_failure = sys.exception() is not None
        try:
            (tmp_path / "q13-correction-outcomes.json").write_text(json.dumps(dict(
                arrivals=arrivals, outcomes=outcomes,
                concurrent=customer_engine.dialect.name == "postgresql",
            ), indent=2))
        except OSError:
            request.node.user_properties.append(("correction_outcome_persistence", "failed"))
            if not original_failure:
                raise
    assert sorted(arrivals) == sorted(c["request_key"] for c in corrections)
    assert sorted(r.status_code for r in responses) == [200, 409]
    winner = next(i for i, response in enumerate(responses) if response.status_code == 200)
    assert responses[1 - winner].json() == {"detail": "plan version or event sequence changed"}
    corrected = responses[winner].json()
    correction_event = ManualAssertion.model_validate(corrected["event"])
    correction_event.assert_document(document)
    assert corrected["event_sequence"] == 2
    assert correction_event.supersedes_event_id == original_event.event_id
    assert correction_event.actor_id == original_event.actor_id
    assert correction_event.verification == "customer_report_only"
    assert correction_event.statement == corrections[winner]["statement"]
    assert correction_event.reported_applied_at == original_event.reported_applied_at
    after_race = graph(customer_engine, wid, plan_id)
    for name in before_race:
        if name not in {
            PlanRow.__tablename__, PlanEventRow.__tablename__, PlanRequestRow.__tablename__
        }:
            assert after_race[name] == before_race[name]
    assert len(after_race[PlanEventRow.__tablename__]) == 2
    assert len(after_race[PlanRequestRow.__tablename__]) == 4
    with Session(customer_engine) as db:
        head = db.get(PlanRow, (wid, plan_id))
        assert head and (head.input_head, head.version_head, head.event_sequence) == (1, 1, 2)
        keys = set(db.scalars(select(PlanRequestRow.request_key).where(
            PlanRequestRow.workspace_id == wid, PlanRequestRow.plan_id == plan_id,
        )))
        assert corrections[winner]["request_key"] in keys
        assert corrections[1 - winner]["request_key"] not in keys

    def replay(body: dict[str, Any], expected: dict[str, Any]) -> None:
        before = graph(customer_engine, wid, plan_id)
        response = alice.post(url + "/assertions", headers=headers(alice), json=body)
        assert response.status_code == 200 and response.json() == expected, response.text
        receipt = alice.get(root + "/requests/assert_applied/" + body["request_key"])
        assert receipt.status_code == 200 and receipt.json() == expected
        assert graph(customer_engine, wid, plan_id) == before

    replay(report, original)
    replay(corrections[winner], corrected)
    changed = alice.post(url + "/assertions", headers=headers(alice), json={
        **corrections[winner], "statement": "Different content under an existing key",
    })
    assert changed.status_code == 409
    assert changed.json() == {"detail": "request key is bound to different input"}
    assert graph(customer_engine, wid, plan_id) == after_race
    revised = deepcopy(primitive)
    revised.update(expected_input_revision=1, expected_version=1, request_key="q13-v7-revise")
    revised["inputs"]["milestone"] = "Review a corrected customer goal statement"
    saved = alice.post(url + "/inputs", headers=headers(alice), json=revised)
    assert saved.status_code == 200, saved.text
    stale = {**corrections[winner], "expected_event_sequence": 2,
             "supersedes_event_id": correction_event.event_id, "request_key": "q13-v7-stale"}
    before_stale = graph(customer_engine, wid, plan_id)
    refused = alice.post(url + "/assertions", headers=headers(alice), json=stale)
    assert refused.status_code == 409
    assert refused.json() == {"detail": "event actor or plan inputs changed"}
    assert graph(customer_engine, wid, plan_id) == before_stale
    withdrawal: dict[str, Any] = {**stale, "assertion": "retracted", "reported_applied_at": None,
                  "statement": "Withdraw the customer report; independent verification was absent.",
                  "request_key": "q13-v7-withdraw"}
    response = alice.post(url + "/assertions", headers=headers(alice), json=withdrawal)
    assert response.status_code == 200, response.text
    withdrawn = response.json()
    assert withdrawn["event_sequence"] == 3
    withdrawn_event = ManualAssertion.model_validate(withdrawn["event"])
    assert withdrawn_event.assertion == "retracted"
    assert withdrawn_event.supersedes_event_id == correction_event.event_id
    assert withdrawn_event.reported_applied_at is None
    replay(withdrawal, withdrawn)
    replay(report, original)
    replay(corrections[winner], corrected)
    history = alice.get(url + "/events")
    assert history.status_code == 200
    assert history.json()["items"] == [original, corrected, withdrawn]
    for item in history.json()["items"]:
        event = ManualAssertion.model_validate(item["event"])
        event.assert_document(document)
        assert event.verification == "customer_report_only"
    exported = alice.get(url + "/export?version=1")
    assert exported.status_code == 200
    assert exported.json()["document"] == document.model_dump(mode="json")
    assert exported.json()["document_digest"] == document.digest()

    monkeypatch.setattr(settings, "customer_export_enabled", True)
    exports = f"/api/customer/v1/workspaces/{wid}/exports"
    requested = alice.post(
        exports, headers={**headers(alice), "Idempotency-Key": "q13-v7-report-archive"}, json={}
    )
    assert requested.status_code == 200, requested.text
    download = alice.get(exports + "/" + requested.json()["request_id"] + "/download")
    assert download.status_code == 200, download.text[:500]
    _, entries = unpack(io.BytesIO(download.content))
    archive_events = [json.loads(line) for line in
                      entries["data/planning_document_events.jsonl"].splitlines()]
    assert [row["document"] for row in archive_events] == [
        item["event"] for item in history.json()["items"]
    ]
    assert all(row["kind"] == "assertion" for row in archive_events)
    foreign = TestClient(app, base_url=str(alice.base_url))
    request.addfinalizer(foreign.close)
    login(foreign, "q13-foreign-owner:1")
    before_foreign = graph(customer_engine, wid, plan_id)
    assert foreign.get(url + "/events").status_code in {403, 404}
    assert foreign.get(url + "/export?version=1").status_code in {403, 404}
    denied = foreign.post(url + "/assertions", headers=headers(foreign), json=withdrawal)
    assert denied.status_code in {403, 404}
    assert graph(customer_engine, wid, plan_id) == before_foreign
    before_revocation = graph(customer_engine, wid, plan_id)
    provider = replicas[2]
    provider.revoked.add("q16-owner")
    assert alice.get(url + "/events").status_code == 401
    revoked = alice.post(url + "/assertions", headers=headers(alice), json=withdrawal)
    assert revoked.status_code == 401
    assert graph(customer_engine, wid, plan_id) == before_revocation
    provider.revoked.clear()
    with Session(customer_engine) as db, db.begin():
        bump_workspace_export_revision(db, wid)
    for model in (
        PlanRow, PlanInputRow, PlanVersionRow, PlanDependencyRow, PlanEventRow, PlanRequestRow
    ):
        with Session(customer_engine) as db:
            assert db.scalar(select(func.count()).select_from(model).where(
                model.workspace_id == wid
            )) == 0
    login(alice, "q16-owner:after-erasure")
    assert alice.get(url + "/events").status_code == 404
    missing = alice.get(root + "/requests/assert_applied/" + withdrawal["request_key"])
    assert missing.status_code == 404
    erased = alice.post(url + "/assertions", headers=headers(alice), json=withdrawal)
    assert erased.status_code == 404
    assert fixture.calls == provider_reads
    assert financial_counts(customer_engine) == effects
    (tmp_path / "q13-report-history.json").write_text(json.dumps(dict(
        document=exported.json(), history=history.json(), archive_events=archive_events,
        observation_rows=0, privacy_erased=True,
    ), indent=2))
