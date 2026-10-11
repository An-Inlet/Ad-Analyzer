"""Current proofs over actual API-acquired selected reporting, not seeded captures."""

from datetime import UTC, datetime
from typing import Any

import pytest
from app.ads.models import Campaign
from app.campaign_performance.selected_models import CurrentEventSelectionRow
from app.customers.models import CustomerMembership, CustomerSession
from app.google_connections.models import GoogleCustomerConnection
from app.lifecycle.privacy import advance_workspace_export_revision
from app.planning_documents import selected_plan_retained as retained
from app.planning_documents.retained_sources import _reporting
from app.planning_documents.selected_inputs import SelectedCaptureSelectorV1
from fastapi import HTTPException
from sqlalchemy import delete, update
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_google_customer_connections import configured as configured
from tests.test_selected_customer_api import customer as customer
from tests.test_selected_plan_reader import ready


@pytest.mark.parametrize("selected", [False, True])
def test_current_proof_viewer_and_explicit_absence(customer: Any, selected: bool) -> None:
    _, kw, _, _ = ready(customer)
    with Session(customer.engine) as db:
        db.execute(
            update(CustomerMembership)
            .where(
                CustomerMembership.workspace_id == customer.wid,
                CustomerMembership.user_id == customer.actor,
            )
            .values(role="viewer")
        )
        db.commit()
    with Session(customer.engine) as db, db.begin():
        proof = retained.capture_selected_reporting_pin(
            db,
            kw["principal"],
            kw["account"],
            kw["expected_source"].privacy_revision,
            SelectedCaptureSelectorV1(account_id=customer.aid, capture_id=kw["capture_id"])
            if selected
            else None,
            datetime.now(UTC),
        )
        assert proof.selection_head is not None
        assert (proof.capture_pin is not None) is selected
        assert proof.source_fence == kw["expected_source"]
        assert not db.new and not db.dirty and not db.deleted


@pytest.mark.parametrize("mutation", ["privacy", "head", "grant", "session", "role", "campaign"])
def test_current_proof_rejects_mid_read_mutation(
    customer: Any, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    _, kw, _, _ = ready(customer)
    original = _reporting
    calls = 0

    def reporting(db: Session, *args: Any, **kwargs: Any) -> tuple[str, str]:
        nonlocal calls
        result = original(db, *args, **kwargs)
        calls += 1
        if calls == 1:
            if mutation == "privacy":
                advance_workspace_export_revision(db, customer.wid)
            elif mutation == "head":
                db.execute(
                    delete(CurrentEventSelectionRow).where(
                        CurrentEventSelectionRow.account_id == customer.aid
                    )
                )
            elif mutation == "grant":
                db.execute(
                    update(GoogleCustomerConnection)
                    .where(GoogleCustomerConnection.account_id == customer.aid)
                    .values(login_customer_id="9999999999")
                )
            elif mutation == "session":
                db.execute(
                    update(CustomerSession)
                    .where(CustomerSession.digest == customer.sid)
                    .values(revoked_at=1)
                )
            elif mutation == "campaign":
                db.execute(
                    update(Campaign)
                    .where(Campaign.account_id == customer.aid)
                    .values(name="Changed report name")
                )
            else:
                db.execute(
                    delete(CustomerMembership).where(
                        CustomerMembership.workspace_id == customer.wid,
                        CustomerMembership.user_id == customer.actor,
                    )
                )
        return result

    monkeypatch.setattr(retained, "_reporting", reporting)
    with Session(customer.engine) as db, db.begin():
        with pytest.raises((HTTPException, ValueError)):
            retained.capture_selected_reporting_pin(
                db,
                kw["principal"],
                kw["account"],
                kw["expected_source"].privacy_revision,
                SelectedCaptureSelectorV1(account_id=customer.aid, capture_id=kw["capture_id"]),
                datetime.now(UTC),
            )
        db.rollback()
