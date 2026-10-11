"""Actual V6 historical customer correction, never provider verification."""

import copy
import hmac
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from app.customers.access import SESSION_COOKIE
from app.customers.models import CustomerMembership
from app.planning_documents.documents import PlanVersion
from app.planning_documents.events import ManualAssertion
from app.planning_documents.models import PlanRow
from app.settings import Settings
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.creative_q07_fixture import planning_snapshot
from tests.owner_review_runtime_fixture import configured_owner_review
from tests.test_creative_common_basis import financial_counts
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_google_owner_repeated_hypotheses_api import receipt_snapshot
from tests.test_owner_review_runtime_api import generation
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


def test_v6_report_and_historical_retraction(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fixture, body, calls, _ = configured_owner_review(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    alice, _, _ = replicas
    original_cookie = alice.cookies[SESSION_COOKIE]
    wid = fixture.basis.workspace_id
    with Session(customer_engine) as db:
        actor = db.scalar(
            select(CustomerMembership.user_id).where(
                CustomerMembership.workspace_id == wid, CustomerMembership.role == "owner"
            )
        )
    assert actor is not None
    root = f"/api/customer/v1/workspaces/{wid}/planning/plans"
    effects = financial_counts(customer_engine)
    response = alice.post(root, headers=headers(alice), json=body)
    assert response.status_code == 201, response.text
    url = root + "/" + response.json()["plan_id"]
    response = alice.post(url + "/generate", headers=headers(alice), json=generation())
    assert response.status_code == 200, response.text
    first = response.json()["document"]
    doc1 = PlanVersion.model_validate(first)
    assert doc1.policy_version == "inlet.descriptive-review.v6"
    assert doc1.google_budget_owner_review is not None
    review = doc1.google_budget_owner_review.reviews[0]
    action = next(a for a in doc1.actions if a.key == review.action_key)
    assert action.kind == "investigate" and action.proposed_fields == ()
    assert action.native_budget is None and review.application == "unavailable"
    native = (copy.deepcopy(calls), copy.deepcopy(fixture.calls))
    retained_receipts = receipt_snapshot(customer_engine)

    def no_effects() -> None:
        assert (calls, fixture.calls) == native
        assert receipt_snapshot(customer_engine) == retained_receipts
        assert financial_counts(customer_engine) == effects
        same_session = hmac.compare_digest(alice.cookies[SESSION_COOKIE], original_cookie)
        assert same_session, "original authenticated session changed"

    def refused(request: dict[str, Any], detail: str) -> None:
        before = planning_snapshot(customer_engine)
        rejected = alice.post(url + "/assertions", headers=headers(alice), json=request)
        assert rejected.status_code == 409, rejected.text
        assert rejected.json() == {"detail": detail}
        assert planning_snapshot(customer_engine) == before
        no_effects()

    report = dict(
        expected_version=1,
        expected_event_sequence=0,
        document_digest=doc1.digest(),
        action_key=action.key,
        action_digest=action.digest(),
        assertion="customer_reports_applied",
        reported_applied_at=datetime.now(UTC).isoformat(),
        statement="Customer reports completing manual investigation; no native change claimed.",
        supersedes_event_id=None,
        request_key="q13-report-original",
    )
    before_report = planning_snapshot(customer_engine)
    response = alice.post(url + "/assertions", headers=headers(alice), json=report)
    assert response.status_code == 200, response.text
    original = response.json()
    reported = ManualAssertion.model_validate(original["event"])
    assert original["event_sequence"] == 1
    assert reported.actor_id == actor and reported.verification == "customer_report_only"
    reported.assert_document(doc1)
    assert reported.assertion == report["assertion"]
    assert reported.statement == report["statement"]
    assert reported.reported_applied_at == datetime.fromisoformat(
        cast(str, report["reported_applied_at"])
    )
    after_report = planning_snapshot(customer_engine)
    assert after_report[1:4] == before_report[1:4]
    assert set(before_report[4]) < set(after_report[4])
    assert len(after_report[4]) == len(before_report[4]) + 1
    assert set(before_report[5]) < set(after_report[5])
    assert len(after_report[5]) == len(before_report[5]) + 1
    with Session(customer_engine) as db:
        plan = db.get(PlanRow, (wid, doc1.inputs.plan_id))
        assert plan is not None
        assert (plan.input_head, plan.version_head, plan.event_sequence) == (1, 1, 1)

    def replay(request: dict[str, Any], expected: dict[str, Any]) -> None:
        before = planning_snapshot(customer_engine)
        repeated = alice.post(url + "/assertions", headers=headers(alice), json=request)
        assert repeated.status_code == 200, repeated.text
        assert repeated.json() == expected
        lookup = alice.get(root + "/requests/assert_applied/" + request["request_key"])
        assert lookup.status_code == 200, lookup.text
        assert lookup.json() == expected
        assert planning_snapshot(customer_engine) == before
        no_effects()

    replay(report, original)
    refused({**report, "statement": "Different claim"}, "request key is bound to different input")
    no_effects()
    edit = copy.deepcopy(body)
    edit.update(expected_input_revision=1, expected_version=1, request_key="q13-edit-milestone")
    edit["inputs"]["milestone"] = "Follow up after customer investigation"
    response = alice.post(url + "/inputs", headers=headers(alice), json=edit)
    assert response.status_code == 200, response.text
    response = alice.post(
        url + "/generate",
        headers=headers(alice),
        json=dict(
            expected_input_revision=2, expected_version=1, request_key="q13-generate-successor"
        ),
    )
    assert response.status_code == 200, response.text
    second = response.json()["document"]
    doc2 = PlanVersion.model_validate(second)
    assert doc2.version == 2 and doc2.parent_digest == doc1.digest()
    assert doc2.inputs.revision == 2
    assert financial_counts(customer_engine) == effects
    native = (copy.deepcopy(calls), copy.deepcopy(fixture.calls))
    retained_receipts = receipt_snapshot(customer_engine)
    stable = planning_snapshot(customer_engine)
    refused(
        {**report, "expected_event_sequence": 1, "request_key": "q13-obsolete-report"},
        "plan version or event sequence changed",
    )
    retract = dict(
        **report,
    )
    retract.update(
        expected_event_sequence=1,
        assertion="retracted",
        reported_applied_at=None,
        supersedes_event_id=reported.event_id,
        statement="Customer withdraws the investigation claim.",
        request_key="q13-retract-original",
    )
    wrong = "0" * 32 if reported.event_id != "0" * 32 else "1" * 32
    refused(
        {**retract, "supersedes_event_id": wrong, "request_key": "q13-wrong-chain"},
        "event chain head changed",
    )
    response = alice.post(url + "/assertions", headers=headers(alice), json=retract)
    assert response.status_code == 200, response.text
    withdrawn = response.json()
    correction = ManualAssertion.model_validate(withdrawn["event"])
    assert withdrawn["event_sequence"] == 2
    assert correction.actor_id == reported.actor_id == actor
    assert correction.recorded_at >= reported.recorded_at
    assert correction.reported_applied_at is None and correction.assertion == "retracted"
    assert correction.supersedes_event_id == reported.event_id
    assert correction.verification == "customer_report_only"
    correction.assert_document(doc1)
    assert correction.statement == retract["statement"]
    after = planning_snapshot(customer_engine)
    assert after[1:4] == stable[1:4]  # Immutable inputs, versions and full dependency graph.
    assert set(stable[4]) < set(after[4]) and len(after[4]) == len(stable[4]) + 1
    assert set(stable[5]) < set(after[5]) and len(after[5]) == len(stable[5]) + 1
    with Session(customer_engine) as db:
        plan = db.get(PlanRow, (wid, doc1.inputs.plan_id))
        assert plan is not None
        assert (plan.input_head, plan.version_head, plan.event_sequence) == (2, 2, 2)
    replay(retract, withdrawn)
    replay(report, original)
    refused(
        {
            **retract,
            "expected_event_sequence": 2,
            "supersedes_event_id": correction.event_id,
            "request_key": "q13-retract-again",
        },
        "manual report already retracted",
    )
    response = alice.get(url + "/events")
    assert response.status_code == 200, response.text
    events = response.json()
    assert events["items"] == [original, withdrawn] and events["next_cursor"] is None
    assert all(item["event"]["version"] == 1 for item in events["items"])
    response = alice.get(url)
    assert response.status_code == 200, response.text
    assert response.json()["document"] == second
    assert response.json()["document_digest"] == doc2.digest()
    exports = []
    for version, expected in ((1, first), (2, second)):
        response = alice.get(url + f"/versions/{version}")
        assert response.status_code == 200, response.text
        assert response.json()["document"] == expected
        assert response.json()["document_digest"] == PlanVersion.model_validate(expected).digest()
        response = alice.get(url + f"/export?version={version}")
        assert response.status_code == 200, response.text
        assert response.json()["document"] == expected
        assert response.json()["document_digest"] == PlanVersion.model_validate(expected).digest()
        exports.append(response.json())
    assert planning_snapshot(customer_engine) == after
    no_effects()
    (tmp_path / "q13-report-retraction.json").write_text(
        json.dumps(
            dict(events=events, original=first, successor=second, exports=exports),
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
