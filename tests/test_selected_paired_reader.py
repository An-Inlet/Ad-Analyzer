"""Actual range/capture APIs into original-session paired reader and pure composer."""

from typing import Any, Literal

import pytest
from app.planning_documents.selected_composer import SelectedPlanComposer, observation_text
from app.planning_documents.selected_paired_reader import OwnedSelectedPairedReader
from app.settings import Settings
from sqlalchemy import Engine

from tests.selected_range_plan_fixture import prepared_range_plan
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize("family", ["conversions", "all_conversions"])
@pytest.mark.parametrize("value", ["10", "0", None])
def test_actual_range_selected_and_traffic_compose(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    family: Literal["conversions", "all_conversions"],
    value: str | None,
) -> None:
    old, ticket, _, _, _ = prepared_range_plan(
        customer_engine, configuration, replicas, monkeypatch, value=value, family=family
    )
    reader = OwnedSelectedPairedReader(
        old.sessions,
        principal=old.principal,
        provider=old.provider,
        policy=old.policy,
        clock=old.clock,
    )
    paired = reader.collect(ticket)
    paired.assert_ticket(ticket)
    assert len(paired.traffic_graphs) == 1
    assert len(paired.traffic) == 2
    selected = next(
        p for p in paired.selected.performance if p.document.summary.starts_on.month == 9
    )
    traffic = next(p for p in paired.traffic if p.document.starts_on.month == 9)
    assert traffic.document.clicks.value == 100
    assert traffic.document.spend_micros.value == 100_000_000
    choice = paired.selected.selected_captures[0].capture.request.selection
    text = observation_text("Primary", selected, traffic, choice)
    if value == "0":
        assert "Observed zero selected conversions" in text
        assert "Positive reported spend" in text
    else:
        assert "Observed zero selected conversions" not in text
        assert "Positive reported spend" not in text
    plan = SelectedPlanComposer().compose(
        ticket=ticket, evidence=paired, policy=old.policy, generated_at=old.clock()
    )
    assert plan.selected_reporting_proof == paired.selected.reporting_proof
    assert plan.selected_reporting_proof is not None
    assert plan.selected_reporting_proof.accounts[0].traffic_pin is not None


@pytest.mark.parametrize("change", ["receipt", "session"])
def test_paired_reader_rechecks_after_selected_collection(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    from app.campaign_performance.range_receipt_models import RangeReceiptRow
    from app.customers.models import CustomerSession
    from app.planning_documents.retained_sources import RetainedSourcesChanged
    from app.planning_documents.selected_plan_adapter import OwnedSelectedEvidenceReader
    from fastapi import HTTPException
    from sqlalchemy import delete, update
    from sqlalchemy.orm import Session

    old, ticket, f, _, _ = prepared_range_plan(
        customer_engine, configuration, replicas, monkeypatch
    )
    collect = OwnedSelectedEvidenceReader.collect

    def changed_collect(self: OwnedSelectedEvidenceReader, actual: Any) -> Any:
        result = collect(self, actual)
        with Session(customer_engine) as db, db.begin():
            if change == "receipt":
                db.execute(delete(RangeReceiptRow).where(RangeReceiptRow.account_id == f.aid))
            else:
                db.execute(
                    update(CustomerSession)
                    .where(CustomerSession.digest == f.sid)
                    .values(revoked_at=1)
                )
        return result

    monkeypatch.setattr(OwnedSelectedEvidenceReader, "collect", changed_collect)
    reader = OwnedSelectedPairedReader(
        old.sessions,
        principal=old.principal,
        provider=old.provider,
        policy=old.policy,
        clock=old.clock,
    )
    with pytest.raises((HTTPException, ValueError, RetainedSourcesChanged)):
        reader.collect(ticket)
