"""Exact configured v6 actual application, with private constructor seams unused."""

import json
from pathlib import Path
from typing import Any

import pytest
from app.api import customer_planning_documents as api
from app.campaign_review.storage import get_media_store
from app.main import app
from app.planning_documents.documents import PlanVersion
from app.planning_documents.models import PlanVersionRow
from app.planning_documents.service import PlanningDocumentService
from app.settings import Settings, settings
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests import test_owner_review_planning_browser as browser
from tests.creative_q07_fixture import planning_snapshot
from tests.owner_review_runtime_fixture import configured_owner_review, confirm_zero_goal
from tests.test_creative_common_basis import financial_counts
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_owner_review_runtime_api import generation
from tests.test_planning_runtime_composition import configure
from tests.test_shopify_sales import configuration as configuration


def owner_config(patch: pytest.MonkeyPatch, root: Path) -> None:
    patch.setenv("AD_ANALYZER_MEDIA_STORAGE_MODE", "local_dev")
    patch.setenv("AD_ANALYZER_MEDIA_LOCAL_DIRECTORY", str(root))
    parsed = configure(patch, "v6")
    patch.setattr(settings, "media_storage_mode", parsed.media_storage_mode)
    patch.setattr(settings, "media_local_directory", parsed.media_local_directory)


@pytest.mark.parametrize(
    "journey", ["positive", "partial", "complete_to_partial", "literal_text", "duplicate_names"]
)
def test_configured_owner_browser(
    customer_engine: Engine,
    request: pytest.FixtureRequest,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    journey: str,
) -> None:
    owner_config(monkeypatch, tmp_path / "media")
    browser.test_actual_owner_review_planning_browser(
        customer_engine,
        request,
        configuration,
        replicas,
        monkeypatch,
        tmp_path,
        journey,
        configured_runtime=True,
    )
    assert vars(api)["PlanningDocumentService"] is PlanningDocumentService
    assert get_media_store not in app.dependency_overrides
    document = PlanVersion.model_validate_json((tmp_path / "document.json").read_text())
    exported = json.loads((tmp_path / "export.json").read_text())
    assert PlanVersion.model_validate(exported["document"]).digest() == document.digest()
    with Session(customer_engine) as db:
        rows = list(db.scalars(select(PlanVersionRow)))
        assert len(rows) == 1
        assert PlanVersion.model_validate_json(rows[0].canonical_json) == document
        assert rows[0].digest == document.digest()
    (tmp_path / "configured-owner-result.json").write_text(
        json.dumps(
            {
                "document": document.model_dump(mode="json"),
                "export": exported,
                "document_digest": document.digest(),
                "real_constructor": True,
                "configured_media": True,
                "journey": journey,
            },
            indent=2,
        )
    )


@pytest.fixture
def actual_owner(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Any:
    owner_config(monkeypatch, tmp_path / "media")
    fixture, body, calls, catalog = configured_owner_review(
        customer_engine,
        configuration,
        replicas,
        monkeypatch,
        tmp_path,
        configured_runtime=True,
    )
    original = replicas[0]
    monkeypatch.setattr(app, "dependency_overrides", dict(original.app.dependency_overrides))
    assert vars(api)["PlanningDocumentService"] is PlanningDocumentService
    assert get_media_store not in app.dependency_overrides
    alice = TestClient(app, base_url=str(original.base_url))
    alice.cookies.update(original.cookies)
    root = f"/api/customer/v1/workspaces/{fixture.basis.workspace_id}/planning/plans"
    return fixture, body, calls, catalog, alice, root


@pytest.mark.parametrize("damage", ["omitted", "wrong_owner", "changed_ceiling"])
def test_configured_owner_input_refusals(
    actual_owner: Any, customer_engine: Engine, damage: str
) -> None:
    f, body, calls, _, alice, root = actual_owner
    if damage == "omitted":
        del body["inputs"]["google_daily_budget_intents"]
    elif damage == "wrong_owner":
        intent = body["inputs"]["google_daily_budget_intents"][0]
        original = intent["owner_selection_id"]
        intent["owner_selection_id"] = original[:-1] + ("a" if original[-1] != "a" else "b")
    else:
        # The actual ceiling is server-derived from the confirmed goal; clients
        # cannot supply an override at all.
        body["inputs"]["total_ceiling_micros"] = 1
    before = planning_snapshot(customer_engine)
    counts, native = financial_counts(customer_engine), (list(calls), list(f.calls))
    response = alice.post(root, headers=headers(alice), json=body)
    assert response.status_code in (409, 422), response.text
    if damage == "changed_ceiling":
        assert response.status_code == 422
        assert response.json() == {"detail": "invalid request parameters"}
    assert planning_snapshot(customer_engine) == before
    assert financial_counts(customer_engine) == counts
    assert (calls, f.calls) == native


@pytest.mark.parametrize("variant", ["owner", "zero"])
def test_configured_owner_history_without_media(
    actual_owner: Any,
    customer_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    variant: str,
) -> None:
    f, body, calls, _, alice, root = actual_owner
    if variant == "zero":
        confirm_zero_goal(alice, f, body)
    saved = alice.post(root, headers=headers(alice), json=body)
    assert saved.status_code == 201, saved.text
    url = root + "/" + saved.json()["plan_id"]
    made = alice.post(url + "/generate", headers=headers(alice), json=generation())
    assert made.status_code == 200, made.text
    document = PlanVersion.model_validate(made.json()["document"])
    assert document.google_budget_owner_review
    review = document.google_budget_owner_review.reviews[0]
    assert (review.disposition, review.application, review.period_spending_compatibility) == (
        "investigate_only",
        "unavailable",
        "not_assessed",
    )
    assert document.inputs.total_ceiling_micros == (0 if variant == "zero" else 1_000_000_000)
    assert review.intent.requested_amount_micros == (0 if variant == "zero" else 5_000_000)
    counts, native = financial_counts(customer_engine), (list(calls), list(f.calls))
    monkeypatch.setattr(settings, "media_storage_mode", "disabled")
    retained = []
    for suffix in ("/versions/1", "/export?version=1"):
        response = alice.get(url + suffix)
        assert response.status_code == 200, response.text
        assert PlanVersion.model_validate(response.json()["document"]) == document
        retained.append(response.json())
    replay = alice.post(url + "/generate", headers=headers(alice), json=generation())
    assert replay.status_code == 200, replay.text
    assert PlanVersion.model_validate(replay.json()["document"]) == document
    assert financial_counts(customer_engine) == counts and (calls, f.calls) == native
    (tmp_path / "configured-owner-history.json").write_text(
        json.dumps(
            {
                "document": document.model_dump(mode="json"),
                "retained": retained,
                "replay": replay.json(),
                "budget_variant": variant,
            },
            indent=2,
        )
    )
