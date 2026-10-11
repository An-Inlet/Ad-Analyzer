"""Existing whole-request owner uniqueness, with production's sanitized refusal."""

import copy
import hmac
from pathlib import Path
from typing import Any

import pytest
from app.customers.access import SESSION_COOKIE
from app.main import validation_error_handler
from app.planning_documents.catalog_receipt_models import (
    CatalogReceiptRow,
    CatalogReceiptSelectionRow,
    InputCatalogReceiptRow,
)
from app.planning_documents.requests import CreatePlan
from app.settings import Settings
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.creative_q07_fixture import planning_snapshot
from tests.owner_review_runtime_fixture import configured_owner_review
from tests.test_creative_common_basis import financial_counts
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


def receipt_snapshot(engine: Engine) -> tuple[tuple[str, ...], ...]:
    with Session(engine) as db:
        return tuple(
            tuple(sorted(repr(dict(row)) for row in db.execute(select(model.__table__)).mappings()))
            for model in (CatalogReceiptRow, CatalogReceiptSelectionRow, InputCatalogReceiptRow)
        )


@pytest.mark.parametrize("variant", ["same", "conflicting"])
def test_repeated_owner_hypotheses_refuse_without_effects(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    variant: str,
) -> None:
    alice, _, _ = replicas
    assert alice.app.middleware_stack is None
    observed: list[tuple[tuple[str | int, ...], str, str]] = []
    handler_calls = 0

    def record_validation(request: Request, exc: Exception) -> JSONResponse:
        nonlocal handler_calls
        assert isinstance(exc, RequestValidationError)
        handler_calls += 1
        # Never retain error input/context or request bodies in diagnostic output.
        observed.extend((tuple(e["loc"]), e["type"], e["msg"]) for e in exc.errors())
        return validation_error_handler(request, exc)

    alice.app.add_exception_handler(RequestValidationError, record_validation)
    fixture, body, calls, _ = configured_owner_review(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    assert handler_calls == 0 and observed == []
    original_cookie = alice.cookies[SESSION_COOKIE]
    goal = alice.get(
        f"/api/customer/v1/workspaces/{fixture.basis.workspace_id}/goals/{fixture.basis.goal_id}"
    )
    assert goal.status_code == 200
    assert goal.json()["revision"] == body["inputs"]["goal_revision"]
    ceiling = goal.json()["definition"]["budget_micros"]
    assert ceiling == 1_000_000_000

    original_scenario = body["inputs"]["scenario_intents"][0]
    original_intent = body["inputs"]["google_daily_budget_intents"][0]
    scenarios = []
    intents = []
    amounts = (5_000_000, 5_000_000) if variant == "same" else (4_000_000, 5_000_000)
    for index, key in enumerate(("owner-first", "owner-second")):
        scenario = copy.deepcopy(original_scenario)
        scenario.update(key=key, title=f"Independent alternative {index + 1}")
        scenario["allocations"][0]["amount_micros"] = (index + 1) * 100_000_000
        scenario["unallocated_micros"] = ceiling - (index + 1) * 100_000_000
        assert sum(a["amount_micros"] for a in scenario["allocations"]) + scenario[
            "unallocated_micros"
        ] == ceiling
        scenarios.append(scenario)
        intents.append(
            {**original_intent, "scenario_key": key, "requested_amount_micros": amounts[index]}
        )
    body["inputs"]["scenario_intents"] = scenarios
    body["inputs"]["google_daily_budget_intents"] = intents
    assert scenarios[0]["allocations"] != scenarios[1]["allocations"]
    assert intents[0]["account_id"] == intents[1]["account_id"]
    assert intents[0]["owner_selection_id"] == intents[1]["owner_selection_id"]
    # These are request-shape checks, not admitted inputs or fabricated proofs.
    for intent in intents:
        single = copy.deepcopy(body)
        single["inputs"]["google_daily_budget_intents"] = [intent]
        CreatePlan.model_validate(single)

    plans_before = planning_snapshot(customer_engine)
    assert all(not rows for rows in plans_before)
    receipts_before = receipt_snapshot(customer_engine)
    assert receipts_before[0] and receipts_before[1] and not receipts_before[2]
    financial_before = financial_counts(customer_engine)
    assert not any(financial_before)
    calls_before = tuple(calls)
    acquisition_calls_before = tuple(fixture.calls)
    response = alice.post(
        f"/api/customer/v1/workspaces/{fixture.basis.workspace_id}/planning/plans",
        headers=headers(alice),
        json=body,
    )
    assert response.status_code == 422
    assert response.json() == {"detail": "invalid request parameters"}
    assert handler_calls == 1
    assert observed == [
        (("body", "inputs"), "value_error", "Value error, duplicate budget owner intent")
    ]
    same_session = hmac.compare_digest(alice.cookies[SESSION_COOKIE], original_cookie)
    assert same_session, "original authenticated session changed"
    assert planning_snapshot(customer_engine) == plans_before
    assert receipt_snapshot(customer_engine) == receipts_before
    assert financial_counts(customer_engine) == financial_before
    assert tuple(calls) == calls_before
    assert tuple(fixture.calls) == acquisition_calls_before
