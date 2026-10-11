"""Actual v5 generation retains the real five-second final authority boundary."""

import time
from pathlib import Path
from typing import Any, cast

import pytest
from app.planning_documents import repository
from app.planning_documents.models import PlanDependencyRow, PlanRequestRow, PlanRow, PlanVersionRow
from app.planning_documents.retained_sources import capture_retained_sources
from app.settings import Settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.creative_runtime_fixture import configured
from tests.test_creative_runtime_api import generation
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_selected_runtime_api import create
from tests.test_shopify_sales import configuration as configuration


def test_real_delay_after_retained_capture_rejects_atomic_generation(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    f, root, body, _, _, store = configured(
        customer_engine, configuration, replicas, monkeypatch, tmp_path
    )
    byte_reads: list[int] = []
    original_read = store.read_exact

    def read(*args: Any) -> bytes:
        result = original_read(*args)
        byte_reads.append(1)
        return cast(bytes, result)

    monkeypatch.setattr(store, "read_exact", read)
    url = create(f, root, body)
    plan_id = url.rsplit("/", 1)[1]
    assert byte_reads == []
    completed: list[tuple[str, ...]] = []

    def capture(*args: Any, **kwargs: Any) -> Any:
        result = capture_retained_sources(*args, **kwargs)
        assert not completed  # Exactly one deliberately delayed final capture.
        completed.append(tuple(witness.kind for witness in result))
        assert "local_creative_basis_v1" in completed[0]
        assert "local_reporting_v3" in completed[0]
        time.sleep(6)  # Real clock/IdentityFact untouched; no retry or expiry extension.
        return result

    monkeypatch.setattr(repository, "capture_retained_sources", capture)
    with Session(customer_engine) as db:
        before = db.scalar(select(func.count()).select_from(PlanRequestRow))
    response = f.alice.post(url + "/generate", headers=headers(f.alice), json=generation())
    assert len(completed) == 1 and byte_reads == [1]
    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "planning_authority_expired"
    with Session(customer_engine) as db:
        plan = db.get(PlanRow, (f.wid, plan_id))
        assert plan is not None and (plan.input_head, plan.version_head) == (1, 0)
        for model in (PlanVersionRow, PlanDependencyRow):
            assert db.scalar(select(func.count()).select_from(model)) == 0
        assert db.scalar(select(func.count()).select_from(PlanRequestRow)) == before
        assert (
            db.scalar(
                select(func.count())
                .select_from(PlanRequestRow)
                .where(PlanRequestRow.operation == "generate")
            )
            == 0
        )
