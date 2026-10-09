from datetime import timedelta
from typing import Any

import pytest
from app.google_connections.models import GoogleCustomerConnection
from app.mandates import service as simulation
from app.mandates.models import Mandate
from app.publication import execution_mandates as s
from app.publication.execution_contracts import ExecutionAccount, ProviderMandatePolicy
from app.publication.execution_models import ProviderPeriodLedger
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_provider_qualification import seeded
from tests.test_shopify_sales import configuration as configuration


def setup(
    db: Session,
    config: Settings,
    path: Any,
    *,
    total_budget: bool = False,
    goal_budget_micros: int = 50_000_000,
) -> tuple[ProviderMandatePolicy, str]:
    wid, _, actor, _ = seeded(
        db, config, path, total_budget=total_budget, goal_budget_micros=goal_budget_micros
    )
    old = db.scalar(select(Mandate).where(Mandate.workspace_id == wid))
    assert old is not None
    source = simulation.policy(db, old)
    native = db.scalar(
        select(GoogleCustomerConnection).where(GoogleCustomerConnection.workspace_id == wid)
    )
    assert native is not None
    return ProviderMandatePolicy(
        environment="contract_test",
        workspace_id=wid,
        goal_id=source.goal_id,
        goal_revision=source.goal_revision,
        currency=source.currency,
        time_zone=source.time_zone,
        starts_at=source.starts_at,
        ends_at=source.ends_at,
        accounts=[
            ExecutionAccount(
                workspace_id=wid,
                account=source.accounts[0],
                external_advertiser_id=native.external_account_id,
                connection_version=f"google:{native.id}:{native.generation}",
            )
        ],
        total_cap_micros=100,
        per_plan_cap_micros=80,
        positive_change_cap_micros=20,
        action_limit=10,
        cooldown_seconds=0,
        freshness_seconds=300,
        aggressiveness_percent=5,
        allowed_purposes=["create_paused", "activate"],
        campaign_and_creative_policy="new_exact_review_required",
        activation_policy="separate_exact_approval",
    ), actor


@pytest.mark.retained_execution
@pytest.mark.usefixtures("retained_execution_engine")
def test_exact_separate_consent_and_current_generation(
    customer_engine: Engine, configuration: Settings, tmp_path: Any
) -> None:
    with Session(customer_engine) as db:
        p, actor = setup(db, configuration, tmp_path)
        row = s.revise(db, p.workspace_id, p, actor, lambda: NOW)
        with pytest.raises(HTTPException, match="exact"):
            s.consent(db, p.workspace_id, row.id, row.revision, "f" * 64, actor, lambda: NOW)
        db.rollback()
        binding = s.consent(
            db, p.workspace_id, row.id, row.revision, p.digest(), actor, lambda: NOW
        )
        _, current = s.checked(db, p.workspace_id, binding, actor, lambda: NOW)
        assert current == p
        native = db.scalar(
            select(GoogleCustomerConnection).where(
                GoogleCustomerConnection.workspace_id == p.workspace_id
            )
        )
        assert native is not None
        native.generation += 1
        db.commit()
        with pytest.raises(HTTPException, match="generation"):
            s.checked(db, p.workspace_id, binding, actor, lambda: NOW)


@pytest.mark.retained_execution
@pytest.mark.usefixtures("retained_execution_engine")
def test_revision_and_new_consent_do_not_reset_shared_ledger(
    customer_engine: Engine, configuration: Settings, tmp_path: Any
) -> None:
    with Session(customer_engine) as db:
        p, actor = setup(db, configuration, tmp_path)
        row = s.revise(db, p.workspace_id, p, actor, lambda: NOW)
        binding = s.consent(
            db, p.workspace_id, row.id, row.revision, p.digest(), actor, lambda: NOW
        )
        ledger, _ = s.checked(db, p.workspace_id, binding, actor, lambda: NOW)
        ledger.spent_high_water_micros, ledger.action_count = 30, 2
        db.commit()
        revised = p.model_copy(update={"aggressiveness_percent": 20})
        s.revise(
            db, p.workspace_id, revised, actor, lambda: NOW, mandate_id=row.id, expected_revision=1
        )
        with pytest.raises(HTTPException, match="consent"):
            s.checked(db, p.workspace_id, binding, actor, lambda: NOW)
        db.rollback()
        next_binding = s.consent(
            db, p.workspace_id, row.id, 2, revised.digest(), actor, lambda: NOW
        )
        next_ledger, _ = s.checked(db, p.workspace_id, next_binding, actor, lambda: NOW)
        assert (next_ledger.id, next_ledger.spent_high_water_micros, next_ledger.action_count) == (
            ledger.id,
            30,
            2,
        )
        second = s.revise(db, p.workspace_id, p, actor, lambda: NOW)
        assert second.ledger_id == ledger.id
        assert db.scalar(select(func.count()).select_from(ProviderPeriodLedger)) == 1


@pytest.mark.parametrize("change", ["environment", "period", "overlap", "foreign", "owner"])
@pytest.mark.retained_execution
@pytest.mark.usefixtures("retained_execution_engine")
def test_cannot_reinterpret_period_or_environment(
    customer_engine: Engine, configuration: Settings, tmp_path: Any, change: str
) -> None:
    with Session(customer_engine) as db:
        p, actor = setup(db, configuration, tmp_path)
        row = s.revise(db, p.workspace_id, p, actor, lambda: NOW)
        changed = p.model_copy(update={"environment": "live"}) if change == "environment" else p
        if change in {"period", "overlap"}:
            changed = p.model_copy(update={"ends_at": p.ends_at + timedelta(hours=1)})
        with pytest.raises(HTTPException):
            s.revise(
                db,
                p.workspace_id + (1 if change == "foreign" else 0),
                changed,
                "unknown" if change == "owner" else actor,
                lambda: NOW,
                mandate_id=None if change == "overlap" else row.id,
                expected_revision=1,
            )


@pytest.mark.retained_execution
@pytest.mark.usefixtures("retained_execution_engine")
def test_pause_and_revoke_keep_accounting(
    customer_engine: Engine, configuration: Settings, tmp_path: Any
) -> None:
    with Session(customer_engine) as db:
        p, actor = setup(db, configuration, tmp_path)
        row = s.revise(db, p.workspace_id, p, actor, lambda: NOW)
        binding = s.consent(db, p.workspace_id, row.id, 1, p.digest(), actor, lambda: NOW)
        s.suspend(db, p.workspace_id, row.id, actor)
        with pytest.raises(HTTPException):
            s.checked(db, p.workspace_id, binding, actor, lambda: NOW)
        db.rollback()
        s.suspend(db, p.workspace_id, row.id, actor, revoke=True)
        with pytest.raises(HTTPException):
            s.consent(db, p.workspace_id, row.id, 1, p.digest(), actor, lambda: NOW)
        assert db.get(ProviderPeriodLedger, binding.ledger_id) is not None


def test_populated_execution_migration_roundtrip(
    monkeypatch: pytest.MonkeyPatch, configuration: Settings, tmp_path: Any
) -> None:
    import os
    from uuid import uuid4

    from alembic import command
    from alembic.config import Config
    from app.customers.models import CustomerUser
    from app.settings import settings
    from scripts.reset_disposable_postgres import validate_disposable_url
    from sqlalchemy import create_engine, make_url, text

    if (
        not os.environ.get("AD_ANALYZER_TEST_POSTGRES_URL")
        or os.environ.get("AD_ANALYZER_CI_DISPOSABLE_POSTGRES") != "true"
    ):
        pytest.skip("explicit disposable PostgreSQL required")
    url = validate_disposable_url()
    schema = "provider_execution_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as db:
        db.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped = make_url(url).update_query_dict({"options": f"-csearch_path={schema}"})
    engine = create_engine(scoped)
    monkeypatch.setattr(settings, "database_url", scoped.render_as_string(hide_password=False))
    config = Config("alembic.ini")
    try:
        # Seed with today's ORM only at today's schema. Then exercise the real
        # predecessor upgrade with populated retained customer data.
        command.upgrade(config, "head")
        with Session(engine) as db:
            p, actor = setup(db, configuration, tmp_path)
        command.downgrade(config, "20261006_0043")
        command.upgrade(config, "head")
        with Session(engine) as db:
            row = s.revise(db, p.workspace_id, p, actor, lambda: NOW)
            binding = s.consent(db, p.workspace_id, row.id, 1, p.digest(), actor, lambda: NOW)
            ledger, _ = s.checked(db, p.workspace_id, binding, actor, lambda: NOW)
            ledger.spent_high_water_micros = 30
            db.commit()
        command.downgrade(config, "20261006_0043")
        command.upgrade(config, "head")
        with Session(engine) as db:
            assert db.get(CustomerUser, actor) is not None
            assert db.scalar(select(func.count()).select_from(ProviderPeriodLedger)) == 0
            row = s.revise(db, p.workspace_id, p, actor, lambda: NOW)
            s.consent(db, p.workspace_id, row.id, 1, p.digest(), actor, lambda: NOW)
    finally:
        engine.dispose()
        with admin.begin() as db:
            db.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def test_unresolved_budget_owner_cannot_get_second_period_reservation(
    customer_engine: Engine, configuration: Settings, tmp_path: Any
) -> None:
    from uuid import uuid4

    from app.publication.execution_models import ProviderExposureReservation
    from sqlalchemy.exc import IntegrityError

    with Session(customer_engine) as db:
        p, actor = setup(db, configuration, tmp_path)
        first = s.revise(db, p.workspace_id, p, actor, lambda: NOW)
        later = p.model_copy(
            update={"starts_at": p.ends_at, "ends_at": p.ends_at + timedelta(days=1)}
        )
        second = s.revise(db, p.workspace_id, later, actor, lambda: NOW)
        db.add(
            ProviderExposureReservation(
                id=uuid4().hex,
                workspace_id=p.workspace_id,
                ledger_id=first.ledger_id,
                environment=p.environment,
                budget_owner_key="google/123/campaign/1",
                amount_micros=50,
                state="held",
                evidence={},
            )
        )
        db.commit()
        with pytest.raises(IntegrityError), db.begin_nested():
            db.add(
                ProviderExposureReservation(
                    id=uuid4().hex,
                    workspace_id=p.workspace_id,
                    ledger_id=second.ledger_id,
                    environment=p.environment,
                    budget_owner_key="google/123/campaign/1",
                    amount_micros=50,
                    state="held",
                    evidence={},
                )
            )
            db.flush()
