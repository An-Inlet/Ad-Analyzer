from datetime import timedelta
from uuid import uuid4

from app.database.models import register_models
from app.lifecycle.contracts import LifecycleScopeV1
from app.lifecycle.inventory import export_section, inventory, verify_registry
from app.lifecycle.quiescing import quiesce
from app.lifecycle.registry import TABLES
from app.publication.execution_models import (
    ProviderExecutionMandate,
    ProviderExposureReservation,
    ProviderPeriodLedger,
)
from sqlalchemy import JSON, Engine
from sqlalchemy.orm import Session

from tests.test_customer_identity import FakeProvider
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_lifecycle import NOW, seed
from tests.test_customer_quiescing import confirmed


def test_all_twelve_execution_tables_are_scoped_protected_and_scalar_only() -> None:
    metadata = register_models()
    verify_registry()
    names = [
        n
        for n in metadata.tables
        if n.startswith("provider_execution_")
        or n in {"provider_period_ledgers", "provider_exposure_reservations"}
    ]
    assert len(names) == 12
    for name in names:
        policy = TABLES[name]
        assert policy.scope == "workspace" and policy.protected
        assert "workspace_id" in policy.fields
        assert all(
            not isinstance(metadata.tables[name].c[field].type, JSON) for field in policy.fields
        )


def test_closure_revokes_provider_consent_but_retains_exposure(customer_engine: Engine) -> None:
    with Session(customer_engine) as db:
        principal, wid = seed(db)
        _, foreign = seed(db, "foreign-execution")
        ledger = ProviderPeriodLedger(
            id=uuid4().hex,
            workspace_id=wid,
            environment="contract_test",
            currency="USD",
            starts_at=NOW,
            ends_at=NOW + timedelta(days=1),
            spent_high_water_micros=20,
            action_count=1,
        )
        db.add(ledger)
        db.flush()
        mandate = ProviderExecutionMandate(
            id=uuid4().hex, workspace_id=wid, ledger_id=ledger.id, revision=1, state="active"
        )
        reservation = ProviderExposureReservation(
            id=uuid4().hex,
            workspace_id=wid,
            ledger_id=ledger.id,
            environment="contract_test",
            budget_owner_key="google/123/campaign/1",
            amount_micros=50,
            state="held",
            evidence={"internal": "never-export"},
        )
        db.add_all([mandate, reservation])
        db.commit()
        scope = LifecycleScopeV1(workspace_id=wid)
        assert any(
            b["subsystem"] == "provider_exposure_reservations"
            for b in inventory(db, scope)["blockers"]
        )
        exported = export_section(db, scope, "provider_exposure_reservations")
        assert "never-export" not in str(exported)
        assert reservation.id not in str(
            export_section(
                db, LifecycleScopeV1(workspace_id=foreign), "provider_exposure_reservations"
            )
        )
        request, digest = confirmed(db, principal, wid)
        quiesce(db, principal, FakeProvider(), wid, request, 1, digest, NOW)
        db.commit()
        db.refresh(mandate)
        db.refresh(reservation)
        db.refresh(ledger)
        assert mandate.state == "revoked"
        assert reservation.state == "held" and reservation.amount_micros == 50
        assert ledger.spent_high_water_micros == 20
        assert any(
            b["subsystem"] == "provider_exposure_reservations"
            for b in inventory(db, scope)["blockers"]
        )
