"""Actual configured planning capabilities require current workspace access."""

from functools import partial
from typing import Any

import pytest
from app.api import customer_planning_documents as api
from app.planning_documents.ports import PlanningCompositionPolicy
from app.planning_documents.service import PlanningDocumentService
from app.settings import Settings
from sqlalchemy import Engine

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import login
from tests.test_customer_identity import replicas as replicas
from tests.test_planning_evidence_adapter import setup_evidence
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize("selected", [False, True])
def test_actual_policy_capability_is_scoped_and_does_not_collect(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    selected: bool,
) -> None:
    _, ticket, _, calls = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, "google_ads"
    )
    if selected:
        monkeypatch.setattr(
            api,
            "PlanningDocumentService",
            partial(
                PlanningDocumentService,
                policy=PlanningCompositionPolicy(
                    version="inlet.descriptive-review.v4",
                    generator_version="inlet.descriptive-planning.v4",
                ),
            ),
        )
    alice, outsider, _ = replicas
    for client in (alice, outsider):
        client.app.include_router(api.router)
    path = f"/api/customer/v1/workspaces/{ticket.inputs.workspace_id}/planning/plans/capabilities"
    login(outsider, "capability-outsider:1")
    before = list(calls)
    response = alice.get(path)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["selected_reporting_available"] is selected
    assert data["policy_version"].endswith("v4" if selected else "v3")
    assert data["workspace_id"] == ticket.inputs.workspace_id
    assert data["spending_authority"] == "none"
    assert data["advertising_writes_enabled"] is False
    assert response.headers["cache-control"] == "no-store"
    assert outsider.get(path).status_code in {403, 404}
    assert calls == before
