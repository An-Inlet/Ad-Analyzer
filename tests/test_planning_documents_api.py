"""Actual authenticated planning routes/service/storage and MockHTTP native reads."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from app.api import customer_planning_documents as api
from app.customers.access import CustomerPrincipal
from app.customers.models import CustomerMembership, CustomerSession, CustomerUser
from app.planning_documents.requests import CreatePlan, CustomerInputs
from app.publication.execution_models import ProviderExecutionAttempt, ProviderExecutionRun
from app.settings import Settings
from sqlalchemy import Engine, func, inspect, select
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import login
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_planning_evidence_adapter import setup_evidence
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


def create_body(inputs: Any) -> dict[str, Any]:
    return CreatePlan(
        request_key="api-create-first",
        inputs=CustomerInputs(
            goal_id=inputs.goal.goal_id,
            goal_revision=inputs.goal.revision,
            account_ids=tuple(a.account_id for a in inputs.accounts),
            reporting_window=inputs.reporting_window,
            comparison_window=None,
            milestone=inputs.milestone,
            product_offer="Reusable bottle",
            constraints=(),
            assumptions=(),
            exclusions=(),
            fixed_allocations=(),
            scenario_intents=(),
            maximum_creative_assets=1,
        ),
    ).model_dump(mode="json")


@pytest.mark.parametrize("platform", ["google_ads", "meta_ads", "tiktok_ads"])
def test_owned_http_create_generate_read_decide_report_export_and_replay(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    platform: str,
) -> None:
    _, ticket, _, calls = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, platform
    )
    alice, outsider, _ = replicas
    alice.app.include_router(api.router)
    outsider.app.include_router(api.router)
    root = f"/api/customer/v1/workspaces/{ticket.inputs.workspace_id}/planning/plans"
    body = create_body(ticket.inputs)
    rejected = alice.post(root, json=body)
    assert rejected.status_code == 403
    forged = alice.post(
        root, headers=headers(alice), json={**body, "advertising_writes_enabled": True}
    )
    assert forged.status_code == 422
    created = alice.post(root, headers=headers(alice), json=body)
    assert created.status_code == 201, created.text
    assert created.headers["cache-control"] == "no-store"
    stable_input = created.json()
    plan_id = stable_input["plan_id"]
    url = root + "/" + plan_id
    empty = alice.get(url)
    assert empty.status_code == 200, empty.text
    assert empty.json()["freshness"] == "not_generated"
    assert empty.json()["document_digest"] is None
    assert empty.json()["action_digests"] == {}
    request = dict(expected_input_revision=1, expected_version=0, request_key="api-generate-first")
    generated = alice.post(url + "/generate", headers=headers(alice), json=request)
    assert generated.status_code == 200, generated.text
    stable_version = generated.json()
    assert stable_version["version"] == 1 and "freshness" not in stable_version
    assert calls
    count = len(calls)
    replay = alice.post(url + "/generate", headers=headers(alice), json=request)
    assert replay.status_code == 200 and replay.json() == stable_version
    assert len(calls) == count
    current = alice.get(url)
    assert current.status_code == 200, current.text
    value = current.json()
    assert value["freshness"] == "current"
    assert value["document_digest"] == stable_version["document_digest"]
    action = value["document"]["actions"][0]
    decision = dict(
        expected_version=1,
        expected_event_sequence=0,
        document_digest=value["document_digest"],
        action_key=action["key"],
        action_digest=value["action_digests"][action["key"]],
        decision="accepted_for_manual_application",
        reason="Reviewed by customer",
        supersedes_event_id=None,
        request_key="api-decision-first",
    )
    accepted = alice.post(url + "/decisions", headers=headers(alice), json=decision)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["event_sequence"] == 1
    assertion = {key: val for key, val in decision.items() if key not in {"decision", "reason"}}
    assertion.update(
        expected_event_sequence=1,
        assertion="customer_reports_applied",
        reported_applied_at=value["document"]["generated_at"],
        statement="Customer report, not independently verified",
        request_key="api-report-first",
    )
    reported = alice.post(url + "/assertions", headers=headers(alice), json=assertion)
    assert reported.status_code == 200, reported.text
    assert reported.json()["event_sequence"] == 2
    events = alice.get(url + "/events")
    assert events.status_code == 200 and len(events.json()["items"]) == 2
    exported = alice.get(url + "/export?version=1")
    assert exported.status_code == 200, exported.text
    assert "artifact.json" in exported.headers["content-disposition"]
    assert exported.headers["cache-control"] == "no-store"
    assert exported.json()["document_digest"] == value["document_digest"]
    assert alice.get(url + "/versions/1").json()["document"] == value["document"]
    assert alice.get(root).json()["items"][0]["plan_id"] == plan_id
    lookup = alice.get(root + "/requests/generate/api-generate-first")
    assert lookup.status_code == 200 and lookup.json() == stable_version
    assert alice.get(root + "/requests/forged/api-generate-first").status_code == 422
    assert alice.get(url + "/versions?limit=101").status_code == 422
    assert alice.get(url + "/comparisons/1/3").status_code == 422
    edited_body = {
        **body,
        "request_key": "api-edit-successor",
        "expected_input_revision": 1,
        "expected_version": 1,
        "inputs": {**body["inputs"], "milestone": "Review the revised customer milestone"},
    }
    edited = alice.post(url + "/inputs", headers=headers(alice), json=edited_body)
    assert edited.status_code == 200, edited.text
    assert edited.json()["input_revision"] == 2
    replay_input = alice.post(root, headers=headers(alice), json=body)
    assert replay_input.status_code == 201 and replay_input.json() == stable_input
    assert alice.get(url).json()["freshness"] == "input_changed"
    successor = alice.post(
        url + "/generate",
        headers=headers(alice),
        json=dict(
            expected_input_revision=2, expected_version=1, request_key="api-generate-successor"
        ),
    )
    assert successor.status_code == 200, successor.text
    assert successor.json()["version"] == 2
    assert successor.json()["document"]["parent_digest"] == value["document_digest"]
    compared = alice.get(url + "/comparisons/1/2")
    assert compared.status_code == 200, compared.text
    assert compared.json()["current_digest"] == successor.json()["document_digest"]
    assert compared.json()["decisions_carried_over"] is False
    assert any(change["path"] == ["inputs", "milestone"] for change in compared.json()["changes"])
    stale = alice.post(
        url + "/decisions",
        headers=headers(alice),
        json={**decision, "request_key": "api-obsolete-decision"},
    )
    assert stale.status_code == 409
    assert alice.get(url + "/versions/1").json()["document"] == value["document"]
    assert len(calls) > count
    login(outsider, "outsider:1")
    assert outsider.get(url).status_code in {403, 404}
    assert outsider.get(url + "/export?version=1").status_code in {403, 404}
    assert outsider.get(root + "/requests/generate/api-generate-first").status_code in {403, 404}
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 0
        assert db.scalar(select(func.count()).select_from(ProviderExecutionRun)) == 0


def test_service_factory_releases_auth_transaction_without_expiring_principal(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, ticket, principal, _ = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, "google_ads"
    )
    provider = replicas[2]
    checked = []
    original = provider.check_active
    with Session(customer_engine) as db:
        user = db.get(CustomerUser, principal.user.id)
        session = db.get(CustomerSession, principal.session.digest)
        assert user is not None and session is not None and db.in_transaction()
        authenticated = CustomerPrincipal(user, session)
        runtime = api.service(db, provider, authenticated)
        assert not db.in_transaction()
        assert inspect(user).detached and inspect(session).detached
        assert not inspect(user).expired_attributes and not inspect(session).expired_attributes

        def check_active(subject: str, authenticated_at: int) -> None:
            assert not db.in_transaction()
            checked.append(subject)
            original(subject, authenticated_at)

        monkeypatch.setattr(provider, "check_active", check_active)
        result = runtime.create(
            authenticated,
            ticket.inputs.workspace_id,
            CreatePlan.model_validate(create_body(ticket.inputs)),
        )
        assert result.input_revision == 1 and checked


def test_http_semantic_rejections_and_viewer_access(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, ticket, principal, calls = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, "google_ads"
    )
    alice, _, _ = replicas
    alice.app.include_router(api.router)
    root = f"/api/customer/v1/workspaces/{ticket.inputs.workspace_id}/planning/plans"
    body = create_body(ticket.inputs)
    future = datetime.now(UTC) + timedelta(days=1)
    invalid = {
        **body,
        "inputs": {
            **body["inputs"],
            "reporting_window": {
                "starts_at": future.isoformat(),
                "ends_at_exclusive": (future + timedelta(days=1)).isoformat(),
            },
        },
    }
    rejected = alice.post(root, headers=headers(alice), json=invalid)
    assert rejected.status_code == 422, rejected.text
    assert alice.get(root).json()["items"] == []
    created = alice.post(root, headers=headers(alice), json=body)
    assert created.status_code == 201, created.text
    url = root + "/" + created.json()["plan_id"]
    generated = alice.post(
        url + "/generate",
        headers=headers(alice),
        json=dict(expected_input_revision=1, expected_version=0, request_key="api-viewer-version"),
    )
    assert generated.status_code == 200, generated.text
    with Session(customer_engine) as db:
        member = db.scalar(
            select(CustomerMembership).where(
                CustomerMembership.user_id == principal.user.id,
                CustomerMembership.workspace_id == ticket.inputs.workspace_id,
            )
        )
        assert member is not None
        member.role = "viewer"
        db.commit()
    count = len(calls)
    for suffix in ("", "/versions", "/versions/1", "/events", "/export?version=1"):
        response = alice.get(url + suffix)
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
    assert alice.get(root).status_code == 200 and len(calls) == count
    denied = alice.post(
        root, headers=headers(alice), json={**body, "request_key": "viewer-create-denied"}
    )
    assert denied.status_code == 403, denied.text
