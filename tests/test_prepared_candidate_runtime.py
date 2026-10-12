"""A retained callback cannot mutate a detached graph around publication seals."""

from datetime import timedelta
from typing import Any

import pytest
from app.planning_documents import google_budget_owner_retained as retained
from app.planning_documents.documents import PlanVersion
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.creative_q07_fixture import planning_snapshot
from tests.test_creative_common_basis import financial_counts
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_owner_review_runtime_api import generation
from tests.test_owner_runtime_composition import actual_owner as actual_owner
from tests.test_prepared_generation_runtime import create, trace_preparation
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize("field", ["summary", "generated_at"])
def test_valid_local_document_mutation_refuses_publication(
    actual_owner: Any,
    customer_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
) -> None:
    alice, url = create(actual_owner)
    before, effects = planning_snapshot(customer_engine), financial_counts(customer_engine)
    captured = trace_preparation(monkeypatch)
    original = retained._owner_evidence
    changed: list[bool] = []

    def mutate(db: Session, document: PlanVersion) -> Any:
        if not changed:
            assert len(captured) == 1
            seal, operands = captured[0]
            assert seal.candidate_replay is not None
            assert document is not operands[2]
            if field == "summary":
                object.__setattr__(document, field, "Valid but changed retained summary")
            else:
                # This changes the creative local witness's observed_at field.
                object.__setattr__(
                    document, field, document.generated_at + timedelta(microseconds=1)
                )
            assert PlanVersion.model_validate(document) == document
            assert getattr(document, field) != getattr(operands[2], field)
            changed.append(True)
        return original(db, document)

    monkeypatch.setattr(retained, "_owner_evidence", mutate)
    response = alice.post(url + "/generate", headers=headers(alice), json=generation())
    assert changed == [True]
    assert response.status_code == 409
    assert response.json()["detail"] == "prepared generation evidence changed"
    assert planning_snapshot(customer_engine) == before
    assert financial_counts(customer_engine) == effects
    seal, _ = captured[0]
    assert seal.candidate_replay is None and seal.snapshots is None and seal.db is None
