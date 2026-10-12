"""Actual default-off app route, immutable fixtures, scope and late configuration fences."""

from pathlib import Path
from typing import Any

import pytest
from app.customers.models import CustomerMembership
from app.main import app
from app.planning_documents.google_budget_fixture_runtime import GoogleBudgetFixture
from app.planning_documents.google_budget_observation_service import GoogleBudgetObservationService
from app.settings import Settings, settings
from pydantic import ValidationError
from sqlalchemy import Engine, update
from sqlalchemy.orm import Session

from tests.creative_q07_fixture import planning_snapshot
from tests.google_budget_runtime_fixture import install_fixture
from tests.test_creative_common_basis import financial_counts
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_google_budget_observation_service import customer_engine as customer_engine
from tests.test_google_budget_observation_service import principal
from tests.test_owner_review_runtime_api import generation
from tests.test_owner_runtime_composition import actual_owner as actual_owner
from tests.test_shopify_sales import configuration as configuration


def test_fixture_mode_defaults_and_rejects_live(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INLET_CUSTOMER_GOOGLE_BUDGET_OBSERVATION_MODE", raising=False)
    assert Settings(_env_file=None).customer_google_budget_observation_mode == "disabled"
    monkeypatch.setenv("INLET_CUSTOMER_GOOGLE_BUDGET_OBSERVATION_MODE", "live")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_assembled_budget_request_recovery_and_configuration_fences(
    actual_owner: Any, customer_engine: Engine, replicas: Any,
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    f, create_body, calls, catalog, alice, root = actual_owner
    created = alice.post(root, headers=headers(alice), json=create_body)
    assert created.status_code == 201, created.text
    url = root + "/" + created.json()["plan_id"]
    generated = alice.post(url + "/generate", headers=headers(alice), json=generation())
    assert generated.status_code == 200, generated.text
    result = generated.json()
    review = result["document"]["google_budget_owner_review"]["reviews"][0]
    action = review["action_key"]
    body = dict(
        expected_version=1, expected_event_sequence=0,
        document_digest=result["document_digest"], action_key=action,
        action_digest=result["action_digests"][action], request_key="assembled-budget-read",
    )
    endpoint = url + "/budget-observations"
    owner = principal(customer_engine, alice)
    before = planning_snapshot(customer_engine)
    effects, reads = financial_counts(customer_engine), list(calls)
    assert effects == (0,) * 6
    assert alice.get(root + "/capabilities").json()["google_budget_observation"] == "unavailable"
    assert alice.post(endpoint, headers=headers(alice), json=body).status_code == 503
    monkeypatch.setattr(settings, "customer_google_budget_observation_mode", "injected_fixture")
    assert alice.post(endpoint, headers=headers(alice), json=body).status_code == 503
    bundle = install_fixture(
        customer_engine, monkeypatch, f.basis.workspace_id, f.basis.account_id,
        catalog["native_observation"]["time_zone"],
    )
    capability = alice.get(root + "/capabilities").json()
    assert capability["google_budget_observation"] == "injected_fixture"
    assert alice.post(endpoint, json=body).status_code == 403  # CSRF still required.
    for injected in ("workspace_id", "account_id", "response_json", "profile_digest", "query"):
        bad = alice.post(endpoint, headers=headers(alice), json={**body, injected: "forbidden"})
        assert bad.status_code == 422, bad.text
    with monkeypatch.context() as patch:
        patch.setattr(settings, "customer_planning_policy", "v7")
        assert alice.post(endpoint, headers=headers(alice), json=body).status_code == 503
    foreign = alice.post(endpoint.replace("/workspaces/", "/workspaces/999"),
                         headers=headers(alice), json=body)
    assert foreign.status_code == 404, foreign.text
    with monkeypatch.context() as patch:
        wrong = GoogleBudgetFixture.model_validate({
            **bundle.model_dump(), "privacy_revision": bundle.privacy_revision + 1,
        })
        patch.setattr(app.state, "google_budget_observation_fixture", wrong)
        assert alice.post(endpoint, headers=headers(alice), json=body).status_code == 409
    with monkeypatch.context() as patch:
        wrong = GoogleBudgetFixture.model_validate({
            **bundle.model_dump(), "source_binding_digest": "0" * 64,
        })
        patch.setattr(app.state, "google_budget_observation_fixture", wrong)
        assert alice.post(endpoint, headers=headers(alice), json=body).status_code == 409
    with Session(customer_engine) as db, db.begin():
        db.execute(update(CustomerMembership).where(
            CustomerMembership.user_id == owner.user.id,
            CustomerMembership.workspace_id == f.basis.workspace_id,
        ).values(role="viewer"))
    assert alice.post(endpoint, headers=headers(alice), json=body).status_code == 403
    with Session(customer_engine) as db, db.begin():
        db.execute(update(CustomerMembership).where(
            CustomerMembership.user_id == owner.user.id,
            CustomerMembership.workspace_id == f.basis.workspace_id,
        ).values(role="owner"))
    assert planning_snapshot(customer_engine) == before

    original_search = GoogleBudgetFixture.search
    for damage in ("disable", "replace", "policy", "revoke"):
        with monkeypatch.context() as patch:
            def changed(
                self: Any, ticket: Any, query: str, cursor: str | None, damage: str = damage,
            ) -> str:
                page = original_search(self, ticket, query, cursor)
                if damage == "disable":
                    patch.setattr(settings, "customer_google_budget_observation_mode", "disabled")
                elif damage == "replace":
                    patch.setattr(app.state, "google_budget_observation_fixture",
                                  GoogleBudgetFixture.model_validate(bundle.model_dump()))
                elif damage == "policy":
                    patch.setattr(settings, "customer_planning_policy", "v3")
                else:
                    replicas[2].revoked.add(owner.user.subject)
                return page
            patch.setattr(GoogleBudgetFixture, "search", changed)
            response = alice.post(endpoint, headers=headers(alice), json=body)
            assert response.status_code == (401 if damage == "revoke" else 503), response.text
        replicas[2].revoked.clear()
        assert planning_snapshot(customer_engine) == before

    original_append = GoogleBudgetObservationService._append
    with monkeypatch.context() as patch:
        def disable_after_insert(*args: Any, **kwargs: Any) -> Any:
            value = original_append(*args, **kwargs)
            patch.setattr(settings, "customer_google_budget_observation_mode", "disabled")
            return value
        patch.setattr(GoogleBudgetObservationService, "_append", staticmethod(disable_after_insert))
        refused = alice.post(endpoint, headers=headers(alice), json=body)
        assert refused.status_code == 503, refused.text
    assert planning_snapshot(customer_engine) == before
    response = alice.post(endpoint, headers=headers(alice), json=body)
    assert response.status_code == 200, response.text
    observed = response.json()
    assert observed["event"]["schema_version"] == "inlet.google-budget-observation.v1"
    assert observed["event"]["provenance"] == "injected_fixture"
    assert observed["event"]["implementation"] == "not_assessed"
    saved = planning_snapshot(customer_engine)
    assert alice.post(endpoint, headers=headers(alice), json=body).json() == observed
    changed_intent = alice.post(endpoint, headers=headers(alice), json={
        **body, "expected_event_sequence": 1,
    })
    assert changed_intent.status_code == 409
    monkeypatch.setattr(settings, "customer_google_budget_observation_mode", "disabled")
    assert alice.post(endpoint, headers=headers(alice), json=body).status_code == 503
    recovered = alice.get(root + "/requests/budget_observe/" + body["request_key"])
    assert recovered.status_code == 200, recovered.text
    assert recovered.json() == observed
    assert recovered.headers["cache-control"] == "no-store"
    history = alice.get(url + "/events")
    assert history.status_code == 200, history.text
    assert history.json()["items"] == [observed]
    assert planning_snapshot(customer_engine) == saved
    assert calls == reads and financial_counts(customer_engine) == effects
    (tmp_path / "assembled-budget-result.json").write_text(response.text)


def test_assembled_budget_observation_browser(
    customer_engine: Engine, request: pytest.FixtureRequest, configuration: Settings,
    replicas: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    from tests import test_owner_review_planning_browser as browser
    from tests.test_owner_runtime_composition import owner_config

    owner_config(monkeypatch, tmp_path / "media")
    browser.test_actual_owner_review_planning_browser(
        customer_engine, request, configuration, replicas, monkeypatch, tmp_path,
        "budget_observation", configured_runtime=True,
    )
