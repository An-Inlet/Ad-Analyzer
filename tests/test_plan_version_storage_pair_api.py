"""Actual post-CAS storage failure rollback; no deadline or authority substitution."""

from pathlib import Path
from typing import Any

import pytest
from app.planning_documents import repository
from app.planning_documents.documents import PlanVersion
from app.planning_documents.models import PlanRow, PlanVersionRow
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.dml import Update

from tests.creative_q07_fixture import planning_snapshot
from tests.owner_review_runtime_fixture import configured_owner_review
from tests.test_creative_common_basis import financial_counts
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_owner_review_runtime_api import generation
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


def test_actual_pair_failure_after_cas_rolls_back(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fixture, body, _, _ = configured_owner_review(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    alice, _, _ = replicas
    root = f"/api/customer/v1/workspaces/{fixture.basis.workspace_id}/planning/plans"
    saved = alice.post(root, headers=headers(alice), json=body)
    assert saved.status_code == 201, saved.text
    url = root + "/" + saved.json()["plan_id"]
    before = planning_snapshot(customer_engine), financial_counts(customer_engine)
    sessions: list[Session] = []
    observed: list[tuple[int, int]] = []
    original_scalar = Session.scalar

    def scalar(db: Session, statement: Any, *args: Any, **kwargs: Any) -> Any:
        result = original_scalar(db, statement, *args, **kwargs)
        if (
            isinstance(statement, Update)
            and getattr(statement.table, "name", None) == PlanRow.__tablename__
        ):
            sessions.append(db)
        return result

    def fail_pair(document: PlanVersion) -> tuple[str, str]:
        assert len(sessions) == 1
        db = sessions[0]
        head = db.scalar(
            select(PlanRow.version_head).where(
                PlanRow.workspace_id == document.inputs.workspace_id,
                PlanRow.id == document.inputs.plan_id,
            )
        )
        count = db.scalar(select(func.count()).select_from(PlanVersionRow))
        assert head == 1 and count == 0
        observed.append((head, count))
        raise HTTPException(409, "controlled storage pair failure")

    monkeypatch.setattr(Session, "scalar", scalar)
    monkeypatch.setattr(repository, "plan_version_storage_pair", fail_pair)
    response = alice.post(url + "/generate", headers=headers(alice), json=generation())
    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "controlled storage pair failure"
    assert observed == [(1, 0)]
    assert (planning_snapshot(customer_engine), financial_counts(customer_engine)) == before
