"""Actual owned inputs with explicit selectors; legacy generation remains unavailable."""

from typing import Any
from uuid import uuid4

import pytest
from app.api import customer_planning_documents as api
from app.planning_documents import authority, repository
from app.planning_documents.input_resolution import prepare, resolve
from app.planning_documents.models import PlanInputRow
from app.planning_documents.requests import CustomerInputs
from app.planning_documents.selected_inputs import SelectedCaptureSelectorV1
from app.settings import Settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_planning_documents_api import create_body
from tests.test_planning_evidence_adapter import setup_evidence
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize("empty", [True, False])
def test_actual_prepare_preserves_selector_and_legacy_api_rejects_before_io(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    empty: bool,
) -> None:
    _, ticket, principal, calls = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, "google_ads"
    )
    alice, _, _ = replicas
    alice.app.include_router(api.router)
    items = (
        ()
        if empty
        else (
            SelectedCaptureSelectorV1(
                account_id=ticket.inputs.accounts[0].account_id, capture_id="f" * 32
            ),
        )
    )
    body = create_body(ticket.inputs)
    body["inputs"]["selected_reporting"] = [x.model_dump(mode="json") for x in items]
    intent = CustomerInputs.model_validate(body["inputs"])
    with Session(customer_engine) as db:
        prepared = prepare(
            db,
            workspace_id=ticket.inputs.workspace_id,
            plan_id=uuid4().hex,
            revision=1,
            actor_id=ticket.actor_id,
            intent=intent,
            now=ticket.prepared_at,
        )
        assert prepared.selected_reporting == items
        assert resolve(prepared, intent, ()).selected_reporting == items
        before = db.scalar(select(func.count()).select_from(PlanInputRow))
    before_calls = list(calls)
    result = alice.post(
        f"/api/customer/v1/workspaces/{ticket.inputs.workspace_id}/planning/plans",
        headers=headers(alice),
        json=body,
    )
    assert result.status_code == 409, result.text
    assert "selected reporting" in result.json()["detail"]
    assert list(calls) == before_calls
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(PlanInputRow)) == before

    # Internal persistence is exercised without registering a generator or API
    # capability. The writer consumes the actual prepared input and owner fact.
    fact = authority.refresh(principal, replicas[2])
    with Session(customer_engine) as db:
        saved = repository.save_input(
            db,
            principal=principal,
            fact=fact,
            document=prepared,
            expected_input_revision=0,
            expected_version=0,
            request_key="selector-storage-first",
            request_digest=intent.digest(),
            now=ticket.prepared_at,
        )
        db.commit()
        plan = repository.owned(db, prepared.workspace_id, prepared.plan_id)
        retained = repository.inputs(db, plan)
        assert retained == saved
        assert retained.selected_reporting == items
        assert retained.digest() == prepared.digest()
        receipt = repository.receipt(
            db,
            prepared.workspace_id,
            principal.user.id,
            "create",
            "selector-storage-first",
            intent.digest(),
        )
        assert receipt is not None and receipt.input_revision == 1
