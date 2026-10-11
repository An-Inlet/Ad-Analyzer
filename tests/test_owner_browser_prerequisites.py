"""Actual acquisition fixture options; no browser or generation qualification."""

from pathlib import Path
from typing import Any

import pytest
from app.planning_documents.models import PlanInputRow, PlanRow, PlanVersionRow
from app.settings import Settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.owner_review_runtime_fixture import configured_owner_review
from tests.test_creative_common_basis import financial_counts
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


@pytest.mark.parametrize("partial", [False, True], ids=["complete", "partial"])
def test_actual_owner_browser_fixture(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    partial: bool,
) -> None:
    fixture, body, calls, catalog = configured_owner_review(
        customer_engine, configuration, replicas, monkeypatch, tmp_path, partial=partial
    )
    assert calls and len(catalog["targets"]) == 6
    intents = body["inputs"]["google_daily_budget_intents"]
    if partial:
        assert intents == []
        assert body["inputs"]["scenario_intents"] == fixture.body["inputs"]["scenario_intents"]
    else:
        assert len(intents) == 1 and intents[0]["requested_amount_micros"] == 5_000_000
        assert body["inputs"]["scenario_intents"][0]["key"] == "owner-test"
    with Session(customer_engine) as db:
        for model in (PlanRow, PlanInputRow, PlanVersionRow):
            assert db.scalar(select(func.count()).select_from(model)) == 0
    assert financial_counts(customer_engine) == (0,) * 6
