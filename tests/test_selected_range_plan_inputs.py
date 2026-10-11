"""Actual requested-range and selected capture flow into the owned collector."""

from decimal import Decimal
from typing import Any, Literal

import pytest
from app.campaign_performance.range_receipts import read_range_receipt
from app.settings import Settings
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.selected_range_plan_fixture import prepared_range_plan
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize("family", ["conversions", "all_conversions"])
def test_genuine_61_day_capture_projects_distinct_months(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    family: Literal["conversions", "all_conversions"],
) -> None:
    reader, ticket, f, request_id, calls = prepared_range_plan(
        customer_engine, configuration, replicas, monkeypatch, family=family
    )
    bundle = reader.collect(ticket)
    bundle.assert_ticket(ticket)
    assert calls and len(bundle.selected_captures) == 1
    assert len(bundle.performance) == 2
    months = {p.document.summary.starts_on.month: p.document.summary for p in bundle.performance}
    assert months[9].conversions.value == Decimal("10")
    assert months[9].conversions.coverage == "observed_requested_days"
    assert not months[9].zero_for_requested_window
    assert months[8].conversions.value == Decimal("0")
    assert months[8].zero_for_requested_window
    with Session(customer_engine) as db:
        receipt = read_range_receipt(db, f.wid, f.aid, request_id)
        assert receipt.row_count == 61
        assert (
            bundle.selected_captures[0].capture.request.aggregate.completion_id
            == receipt.completion_id
        )
