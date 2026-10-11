"""Actual admission rejects reserved creative inputs before reads or persistence."""

from functools import partial
from typing import Any
from uuid import uuid4

import pytest
from app.api import customer_planning_documents as api
from app.planning_documents import authority, repository
from app.planning_documents.input_resolution import prepare, resolve
from app.planning_documents.models import PlanInputRow, PlanVersionRow
from app.planning_documents.ports import PlanningCompositionPolicy
from app.planning_documents.requests import CustomerInputs
from app.planning_documents.service import PlanningDocumentService
from app.settings import Settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_planning_documents_api import create_body
from tests.test_planning_evidence_adapter import setup_evidence
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize("version", [3, 4])
@pytest.mark.parametrize("empty", [False, True])
def test_reserved_creative_admission_and_changed_replay_cannot_write(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    version: int,
    empty: bool,
) -> None:
    _, ticket, principal, calls = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, "google_ads"
    )
    policy = PlanningCompositionPolicy(
        version=f"inlet.descriptive-review.v{version}",
        generator_version=f"inlet.descriptive-planning.v{version}",
    )
    monkeypatch.setattr(
        api, "PlanningDocumentService", partial(PlanningDocumentService, policy=policy)
    )
    alice, _, _ = replicas
    alice.app.include_router(api.router)
    body = create_body(ticket.inputs)
    if version == 4:
        body["inputs"]["selected_reporting"] = []
    root = f"/api/customer/v1/workspaces/{ticket.inputs.workspace_id}/planning/plans"
    original = alice.post(root, headers=headers(alice), json=body)
    assert original.status_code == 201, original.text
    creative: dict[str, Any] = {} if empty else {"product": {"name": "Reusable travel mug"}}
    altered = {**body, "inputs": {**body["inputs"], "creative": creative}}
    intent = CustomerInputs.model_validate(altered["inputs"])
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
        assert prepared.creative == intent.creative and prepared.creative is not None
        assert resolve(prepared, intent, ()).creative == intent.creative
        before = db.scalar(select(func.count()).select_from(PlanInputRow))
    before_calls = list(calls)
    for request in (altered, {**altered, "request_key": "reserved-creative-new"}):
        rejected = alice.post(root, headers=headers(alice), json=request)
        assert rejected.status_code == 409 and "typed creative" in rejected.json()["detail"]
    edit = alice.post(
        root + "/" + original.json()["plan_id"] + "/inputs",
        headers=headers(alice),
        json={
            **altered,
            "request_key": "reserved-creative-edit",
            "expected_input_revision": 1,
            "expected_version": 0,
        },
    )
    assert edit.status_code == 409, edit.text
    assert list(calls) == before_calls
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(PlanInputRow)) == before
    replay = alice.post(root, headers=headers(alice), json=body)
    assert replay.status_code == 201 and replay.json() == original.json()
    if version == 4 and empty:
        # A server-reserved draft is not permission for an older generator to
        # silently discard typed inputs. No consumer policy is registered here.
        fact = authority.refresh(principal, replicas[2])
        with Session(customer_engine) as db:
            repository.save_input(
                db,
                principal=principal,
                fact=fact,
                document=prepared,
                expected_input_revision=0,
                expected_version=0,
                request_key="reserved-internal-input",
                request_digest=intent.digest(),
                now=ticket.prepared_at,
            )
            db.commit()
        generated = alice.post(
            root + "/" + prepared.plan_id + "/generate",
            headers=headers(alice),
            json=dict(
                expected_input_revision=1,
                expected_version=0,
                request_key="reserved-denied-generation",
            ),
        )
        assert generated.status_code == 409 and "typed creative" in generated.json()["detail"]
        assert list(calls) == before_calls
        with Session(customer_engine) as db:
            assert db.scalar(select(func.count()).select_from(PlanVersionRow)) == 0
            assert repository.owned(db, prepared.workspace_id, prepared.plan_id).version_head == 0
