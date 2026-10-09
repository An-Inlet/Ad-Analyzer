from datetime import datetime, timedelta
from pathlib import Path

import pytest
from app.ads.models import AdvertisingAccount
from app.google_connections.models import GoogleCustomerConnection
from app.publication import coordinator, settlement
from app.publication import execution_mandates as mandates
from app.publication.execution_contracts import ExecutionAccount, ProviderMandatePolicy
from app.publication.execution_models import (
    ProviderExecutionMandate,
    ProviderExecutionRun,
    ProviderExposureReservation,
    ProviderPeriodLedger,
)
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.test_activation_review import activation_ready
from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_google_activation import Server
from tests.test_provider_execution_mandates import setup
from tests.test_provider_settlement import qualified
from tests.test_shopify_sales import configuration as configuration


def second_account(db: Session, policy: ProviderMandatePolicy) -> ExecutionAccount:
    old = db.scalar(
        select(GoogleCustomerConnection).where(
            GoogleCustomerConnection.workspace_id == policy.workspace_id
        )
    )
    assert old is not None
    source = db.get(AdvertisingAccount, old.account_id)
    assert source is not None
    account = AdvertisingAccount(
        workspace_id=policy.workspace_id,
        connection_id=old.integration_id,
        platform=source.platform,
        external_account_id="9876543210",
        name="Second Account",
        currency_code="USD",
    )
    db.add(account)
    db.flush()
    native = GoogleCustomerConnection(
        id="b" * 32,
        workspace_id=policy.workspace_id,
        integration_id=old.integration_id,
        account_id=account.id,
        external_account_id=account.external_account_id,
        status="connected",
        generation=1,
        backfill_through=old.backfill_through,
        history_floor=old.history_floor,
        window_start=old.window_start,
        window_end=old.window_end,
    )
    db.add(native)
    db.commit()
    return ExecutionAccount(
        workspace_id=policy.workspace_id,
        account=policy.accounts[0].account.model_copy(update={"account_id": account.id}),
        external_advertiser_id=account.external_account_id,
        connection_version=f"google:{native.id}:1",
    )


@pytest.mark.parametrize("mode", ["new", "revision"])
@pytest.mark.retained_execution
@pytest.mark.usefixtures("retained_execution_engine")
def test_settled_account_spend_cannot_be_omitted_from_period(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    mode: str,
) -> None:
    with Session(customer_engine) as db:
        wid, parent, actor, _, _, _ = activation_ready(db, configuration, tmp_path, Server())
        run = db.get(ProviderExecutionRun, parent)
        assert run is not None and run.reservation_id is not None
        reservation = db.get(ProviderExposureReservation, run.reservation_id)
        assert reservation is not None
        row = db.scalar(
            select(ProviderExecutionMandate).where(
                ProviderExecutionMandate.ledger_id == reservation.ledger_id
            )
        )
        assert row is not None
        policy = mandates.policy(db, row)
        second = second_account(db, policy)
        coordinator.cancel_creation(db, wid, parent, actor, lambda: NOW)
        replacement = policy.model_copy(update={"accounts": [second]})

        def read(
            snapshot: settlement.SettlementSnapshot, now: datetime
        ) -> settlement.SettlementObservation:
            # Settlement releases locks for source IO. Competing scope changes remain blocked.
            with Session(customer_engine) as competing:
                with pytest.raises(HTTPException, match="account set"):
                    mandates.revise(competing, wid, replacement, actor, lambda: NOW)
                competing.rollback()
            return qualified(snapshot, now).model_copy(
                update={"reported_portfolio_spend_micros": 60}
            )

        settlement.settle(
            db,
            wid,
            reservation.id,
            actor,
            settlement.SettlementRuntime("contract_test", read),
            lambda: NOW,
        )
        ledger = db.get(ProviderPeriodLedger, reservation.ledger_id)
        assert ledger is not None and ledger.spent_high_water_micros == 60
        assert reservation.state == "settled"
        # B's independent reported60 cannot replace A's settled60 in the same cap100 period.
        replacement = policy.model_copy(update={"accounts": [second]})
        with pytest.raises(HTTPException, match="account set"):
            mandates.revise(
                db,
                wid,
                replacement,
                actor,
                lambda: NOW,
                mandate_id=row.id if mode == "revision" else None,
                expected_revision=row.revision if mode == "revision" else None,
            )
        db.rollback()
        restored = mandates.revise(
            db, wid, policy, actor, lambda: NOW, mandate_id=row.id, expected_revision=row.revision
        )
        mandates.consent(
            db, wid, restored.id, restored.revision, policy.digest(), actor, lambda: NOW
        )
        db.refresh(ledger)
        assert ledger.spent_high_water_micros == 60


@pytest.mark.planning_boundary
def test_mixed_currency_prior_hold_is_not_added_as_numeric_micros(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
) -> None:
    from tests.financial_origin_retained_fixture import (
        current_policy,
        financial_source_engine,
        retained_financial_source,
    )

    with financial_source_engine(customer_engine, tmp_path) as customer_engine:
        ids = retained_financial_source(customer_engine, tmp_path / "retained", "source_only")
        with Session(customer_engine) as db:
            policy, actor = current_policy(db, ids), ids.actor_id
            old = ProviderPeriodLedger(
                id="a" * 32,
                workspace_id=policy.workspace_id,
                environment=policy.environment,
                currency="JPY",
                starts_at=policy.starts_at - timedelta(days=60),
                ends_at=policy.starts_at - timedelta(days=30),
            )
            db.add(old)
            db.flush()
            db.add(
                ProviderExposureReservation(
                    id="b" * 32,
                    workspace_id=policy.workspace_id,
                    ledger_id=old.id,
                    environment=policy.environment,
                    budget_owner_key="old-jpy",
                    amount_micros=60,
                    state="held",
                    evidence={},
                )
            )
            db.commit()
            with pytest.raises(HTTPException, match="currency"):
                mandates.revise(db, policy.workspace_id, policy, actor, lambda: NOW)


@pytest.mark.retained_execution
@pytest.mark.usefixtures("retained_execution_engine")
def test_drafts_are_editable_but_first_consent_pins_all_period_mandates(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
) -> None:
    with Session(customer_engine) as db:
        policy, actor = setup(db, configuration, tmp_path)
        second = second_account(db, policy)
        a = mandates.revise(db, policy.workspace_id, policy, actor, lambda: NOW)
        alternate = policy.model_copy(update={"accounts": [second]})
        b = mandates.revise(db, policy.workspace_id, alternate, actor, lambda: NOW)
        mandates.consent(
            db, policy.workspace_id, a.id, a.revision, policy.digest(), actor, lambda: NOW
        )
        with pytest.raises(HTTPException, match="account set"):
            mandates.consent(
                db, policy.workspace_id, b.id, b.revision, alternate.digest(), actor, lambda: NOW
            )
        db.rollback()
        with pytest.raises(HTTPException, match="account set"):
            mandates.revise(
                db,
                policy.workspace_id,
                policy.model_copy(update={"accounts": [*policy.accounts, second]}),
                actor,
                lambda: NOW,
                mandate_id=a.id,
                expected_revision=a.revision,
            )
        db.rollback()
        # Restoring the original set is permitted without changing ledger accounting.
        revised = mandates.revise(
            db,
            policy.workspace_id,
            policy,
            actor,
            lambda: NOW,
            mandate_id=b.id,
            expected_revision=b.revision,
        )
        assert revised.ledger_id == a.ledger_id
        mandates.consent(
            db, policy.workspace_id, b.id, b.revision, policy.digest(), actor, lambda: NOW
        )


@pytest.mark.retained_execution
@pytest.mark.usefixtures("retained_execution_engine")
def test_competing_account_set_consents_serialize(
    customer_engine: Engine, configuration: Settings, tmp_path: Path
) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from sqlalchemy import text

    if customer_engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL row-lock serialization")
    with Session(customer_engine) as db:
        policy, actor = setup(db, configuration, tmp_path)
        second = second_account(db, policy)
        other = policy.model_copy(update={"accounts": [second]})
        a = mandates.revise(db, policy.workspace_id, policy, actor, lambda: NOW)
        b = mandates.revise(db, policy.workspace_id, other, actor, lambda: NOW)
        args = [(a.id, a.revision, policy), (b.id, b.revision, other)]
    barrier = Barrier(2)

    def consent_one(item: tuple[str, int, ProviderMandatePolicy]) -> str:
        ident, revision, selected = item
        with Session(customer_engine) as db:
            db.execute(text("SET LOCAL lock_timeout = '5s'"))
            barrier.wait(timeout=5)
            try:
                mandates.consent(
                    db,
                    selected.workspace_id,
                    ident,
                    revision,
                    selected.digest(),
                    actor,
                    lambda: NOW,
                )
                return "accepted"
            except HTTPException as error:
                assert error.status_code == 409 and "account set" in error.detail
                db.rollback()
                return "blocked"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(consent_one, args)) == ["accepted", "blocked"]
