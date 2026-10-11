"""Actual input-only owner hypotheses; original proofs and all-or-nothing persistence."""

import copy
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from app.api import customer_planning_documents
from app.planning_documents import catalog_receipts
from app.planning_documents.catalog_receipt_models import InputCatalogReceiptRow
from app.planning_documents.catalog_receipts import CatalogReceiptUnavailable
from app.planning_documents.models import PlanInputRow
from app.planning_documents.service import PlanningDocumentService
from app.settings import Settings
from sqlalchemy import Engine, func, select

from tests.creative_q07_fixture import planning_snapshot
from tests.google_budget_input_fixture import ready_inputs
from tests.test_catalog_receipt_runtime_adverse import counts
from tests.test_creative_common_basis import financial_counts
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import login
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


def test_actual_owner_input_create_edit_replay_history_and_generation_refusal(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fixture, body, calls, catalog = ready_inputs(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    alice, _, _ = replicas
    root = f"/api/customer/v1/workspaces/{fixture.basis.workspace_id}/planning/plans"
    before_calls, before_effects = len(calls), financial_counts(customer_engine)
    result = alice.post(root, headers=headers(alice), json=body)
    assert result.status_code == 201, result.text
    saved = result.json()
    assert saved["inputs"]["google_daily_budget_intents"][0]["requested_amount_micros"] == 5_000_000
    url = root + "/" + saved["plan_id"]
    baseline = planning_snapshot(customer_engine)
    replay = alice.post(root, headers=headers(alice), json=body)
    assert replay.status_code == 201 and replay.json() == saved, replay.text
    blocked = alice.post(
        url + "/generate",
        headers=headers(alice),
        json=dict(
            expected_input_revision=1, expected_version=0, request_key="owner-generate-refused"
        ),
    )
    assert blocked.status_code == 409 and "owner hypotheses" in blocked.json()["detail"], (
        blocked.text
    )
    assert planning_snapshot(customer_engine) == baseline
    edit = copy.deepcopy(body)
    edit.update(expected_input_revision=1, expected_version=0, request_key="owner-input-edit")
    edit["inputs"]["google_daily_budget_intents"][0]["requested_amount_micros"] = 4_000_000
    changed = alice.post(url + "/inputs", headers=headers(alice), json=edit)
    assert changed.status_code == 200, changed.text
    assert changed.json()["input_revision"] == 2
    baseline = planning_snapshot(customer_engine)
    wrong = copy.deepcopy(edit)
    wrong["request_key"] = "owner-stale-cas"
    refused = alice.post(url + "/inputs", headers=headers(alice), json=wrong)
    assert refused.status_code == 409, refused.text
    assert planning_snapshot(customer_engine) == baseline

    # Controlled service-clock expiry, not a changed auth/DB wall clock.
    actual_service = customer_planning_documents.service
    after_expiry = datetime.fromisoformat(catalog["expires_at"]) + timedelta(seconds=1)
    clock_calls: list[bool] = []

    def historical_service(*args: Any, **kwargs: Any) -> Any:
        service = actual_service(*args, **kwargs)

        def expired_clock() -> datetime:
            clock_calls.append(True)
            return after_expiry

        service.clock = expired_clock
        return service

    monkeypatch.setattr(customer_planning_documents, "service", historical_service)

    # Simulated unavailable current receipt lookup must not affect exact completed replay/history.
    def unavailable(*args: Any, **kwargs: Any) -> Any:
        raise CatalogReceiptUnavailable("expired")

    monkeypatch.setattr(catalog_receipts, "_load", unavailable)
    again = alice.post(root, headers=headers(alice), json=body)
    assert again.status_code == 201 and again.json() == saved, again.text
    login(alice, "q16-owner:history")
    current = alice.get(url)
    assert current.status_code == 200, current.text
    request = alice.get(root + "/requests/create/" + body["request_key"])
    assert request.status_code == 200 and request.json() == saved, request.text
    assert len(calls) == before_calls and financial_counts(customer_engine) == before_effects
    # Completed replay/read use historical guards and never need the service clock.
    assert not clock_calls


@pytest.mark.parametrize(
    "case",
    [
        "opaque",
        "facts",
        "amount",
        "currency",
        "scenario",
        "exclusion",
        "child",
        "default",
        "final-link",
    ],
)
def test_owner_admission_rejects_without_partial_graph(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    case: str,
) -> None:
    fixture, body, calls, catalog = ready_inputs(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    alice, _, _ = replicas
    owner = body["inputs"]["google_daily_budget_intents"][0]
    late_rows: list[tuple[int, int]] = []
    if case == "opaque":
        owner["owner_selection_id"] = "0" * 64
    elif case == "facts":
        owner["expected_owner_facts_digest"] = "0" * 64
    elif case == "amount":
        owner["requested_amount_micros"] = 10_000_001
    elif case == "currency":
        owner["currency"] = "EUR"
    elif case == "scenario":
        owner["scenario_key"] = "missing"
    elif case == "exclusion":
        target = next(
            t
            for t in catalog["targets"]
            if t["entity"]["kind"] == "campaign"
            and t["canonical_entity_key"]
            != body["inputs"]["scenario_intents"][0]["allocations"][0]["target"][
                "canonical_entity_key"
            ]
        )
        body["inputs"]["exclusions"] = [
            dict(
                account_id=fixture.basis.account_id,
                canonical_entity_key=target["canonical_entity_key"],
                selection_key=target["selection_key"],
            )
        ]
    elif case == "child":
        child = next(
            t
            for t in catalog["targets"]
            if t["entity"]["kind"] == "adgroup"
            and t["entity"]["reference"]["parent_campaign_id"] == "1"
        )
        scenario = body["inputs"]["scenario_intents"][0]
        scenario["allocations"].append(
            dict(
                target=dict(
                    account_id=fixture.basis.account_id,
                    canonical_entity_key=child["canonical_entity_key"],
                    selection_key=child["selection_key"],
                ),
                amount_micros=0,
            )
        )
    elif case == "default":
        monkeypatch.setattr(
            customer_planning_documents, "PlanningDocumentService", PlanningDocumentService
        )
    else:
        original = catalog_receipts.bind_input_receipts

        def late(*args: Any, **kwargs: Any) -> Any:
            original(*args, **kwargs)
            db = args[0]
            db.flush()
            late_rows.append(
                (
                    db.scalar(select(func.count()).select_from(PlanInputRow)),
                    db.scalar(select(func.count()).select_from(InputCatalogReceiptRow)),
                )
            )
            assert late_rows[-1] == (1, 1)
            raise CatalogReceiptUnavailable("selection_mismatch")

        monkeypatch.setattr(catalog_receipts, "bind_input_receipts", late)
        from app.planning_documents import service

        monkeypatch.setattr(service, "bind_input_receipts", late)
    before = (
        planning_snapshot(customer_engine),
        counts(customer_engine),
        financial_counts(customer_engine),
        len(calls),
    )
    result = alice.post(
        f"/api/customer/v1/workspaces/{fixture.basis.workspace_id}/planning/plans",
        headers=headers(alice),
        json=body,
    )
    assert result.status_code == 409, result.text
    assert late_rows == ([(1, 1)] if case == "final-link" else [])
    assert (
        planning_snapshot(customer_engine),
        counts(customer_engine),
        financial_counts(customer_engine),
        len(calls),
    ) == before


@pytest.mark.parametrize("empty", [False, True])
def test_missing_proof_read_replay_or_explicit_empty_refusal(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    empty: bool,
) -> None:
    fixture, body, calls, _ = ready_inputs(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    alice, _, _ = replicas
    if empty:
        body["inputs"]["google_daily_budget_intents"] = []
        body["inputs"]["scenario_intents"] = []
    root = f"/api/customer/v1/workspaces/{fixture.basis.workspace_id}/planning/plans"
    saved = alice.post(root, headers=headers(alice), json=body)
    assert saved.status_code == 201, saved.text
    url = root + "/" + saved.json()["plan_id"]
    before = (
        planning_snapshot(customer_engine),
        counts(customer_engine),
        financial_counts(customer_engine),
        len(calls),
    )
    if empty:
        blocked = alice.post(
            url + "/generate",
            headers=headers(alice),
            json=dict(
                expected_input_revision=1, expected_version=0, request_key="empty-owner-generation"
            ),
        )
        assert blocked.status_code == 409 and "owner hypotheses" in blocked.json()["detail"]
        assert alice.get(url).status_code == 200
    else:
        monkeypatch.setattr(catalog_receipts, "_input_links", lambda *args: [])
        for response in (
            alice.get(url),
            alice.get(root + "/requests/create/" + body["request_key"]),
            alice.post(root, headers=headers(alice), json=body),
        ):
            assert response.status_code == 409, response.text
            assert (
                response.json()["detail"] == "The original budget owner input proof is unavailable."
            )
    assert (
        planning_snapshot(customer_engine),
        counts(customer_engine),
        financial_counts(customer_engine),
        len(calls),
    ) == before
