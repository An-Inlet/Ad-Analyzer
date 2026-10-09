from datetime import timedelta
from typing import Any

import pytest
from app.publication import coordinator
from app.publication.coordinator_contracts import CreationExecutionReview
from app.publication.execution_models import (
    ProviderExecutionReview,
    ProviderExecutionRun,
    ProviderPeriodLedger,
)
from app.publication.exposure_qualification import (
    AccountExposureFact,
    PortfolioExposureReader,
    PortfolioFacts,
    QualificationProfile,
)
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_provider_coordinator import GoogleServer, ready
from tests.test_shopify_sales import configuration as configuration


def case(db: Session, config: Settings, path: Any) -> tuple[Any, Any, PortfolioFacts]:
    wid, run_id, actor, store, runtime = ready(db, config, path, GoogleServer())
    assert (
        coordinator.claim_creation_step(db, wid, run_id, actor, store, runtime, lambda: NOW)
        is not None
    )
    run = db.get(ProviderExecutionRun, run_id)
    assert run is not None
    review = db.get(ProviderExecutionReview, run.review_id)
    assert review is not None
    document = CreationExecutionReview.model_validate(review.document)
    e = document.exposure
    facts = PortfolioFacts(
        qualification_id=e.qualification_id,
        profile_id="fixture",
        environment=e.environment,
        plan_digest=document.plan.digest(),
        accounts=[
            AccountExposureFact(
                account=e.account,
                reported_spend_micros=3,
                unreported_upper_micros=2,
                unchanged_future_upper_micros=5,
                reporting_watermark=NOW,
            )
        ],
        complete=True,
        currency=e.currency,
        period_start=e.period_start,
        period_end=e.period_end,
        observed_at=NOW,
        expires_at=NOW + timedelta(seconds=30),
        budget_owner_key=e.budget_owner_key,
        target_set_digest=e.target_set_digest,
        proposed_owner_upper_micros=40,
    )
    return run, document, facts


def reader(facts: PortfolioFacts, **kwargs: Any) -> PortfolioExposureReader:
    return PortfolioExposureReader(
        lambda *_: facts,
        {
            "fixture": QualificationProfile(
                environment="contract_test",
                model_version="fixture_v1",
                semantics="contract_scenario",
                maximum_age_seconds=30,
            )
        },
        clock=kwargs.get("clock", lambda: NOW),
    )


@pytest.mark.retained_execution
@pytest.mark.usefixtures("retained_execution_engine")
def test_exact_reservation_is_counted_once_only_for_activation(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Any,
) -> None:
    with Session(customer_engine) as db:
        run, doc, facts = case(db, configuration, tmp_path)
        port = reader(facts)
        normal = port(db, doc.mandate, doc.plan, NOW)
        assert normal.existing_reservations_micros == 40 and normal.portfolio_upper_micros == 90
        activated = port.for_activation(db, doc.mandate, doc.plan, run.reservation_id, NOW)
        assert (
            activated.existing_reservations_micros == 0 and activated.portfolio_upper_micros == 50
        )
        for wrong_id in ("f" * 32, ""):
            with pytest.raises(HTTPException, match="retained"):
                port.for_activation(db, doc.mandate, doc.plan, wrong_id, NOW)
        ledger = db.get(ProviderPeriodLedger, doc.mandate.ledger_id)
        assert ledger is not None and ledger.spent_high_water_micros == 0


@pytest.mark.retained_execution
@pytest.mark.usefixtures("retained_execution_engine")
@pytest.mark.parametrize(
    "change", ["unknown_profile", "missing_bound", "incomplete", "spend_regressed"]
)
def test_unknown_evidence_never_becomes_zero_exposure(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Any,
    change: str,
) -> None:
    with Session(customer_engine) as db:
        _, doc, facts = case(db, configuration, tmp_path)
        if change == "unknown_profile":
            facts.profile_id = "unregistered"
        elif change == "missing_bound":
            facts.accounts[0].unreported_upper_micros = None
        elif change == "incomplete":
            facts.complete = False
        else:
            ledger = db.get(ProviderPeriodLedger, doc.mandate.ledger_id)
            assert ledger is not None
            ledger.spent_high_water_micros = 4
            db.commit()
        evidence = reader(facts)(db, doc.mandate, doc.plan, NOW)
        assert evidence.cap_semantics == "unqualified"
        assert evidence.portfolio_upper_micros is None
        assert evidence.unreported_upper_micros is None


@pytest.mark.retained_execution
@pytest.mark.usefixtures("retained_execution_engine")
@pytest.mark.parametrize("change", ["foreign", "duplicate", "currency", "plan", "stale_after_read"])
def test_lineage_and_freshness_fail_closed(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Any,
    change: str,
) -> None:
    with Session(customer_engine) as db:
        _, doc, facts = case(db, configuration, tmp_path)
        if change == "foreign":
            facts.accounts[0].account = facts.accounts[0].account.model_copy(
                update={"workspace_id": 999}
            )
        elif change == "duplicate":
            facts.accounts.append(facts.accounts[0])
        elif change == "currency":
            facts.currency = "EUR"
        elif change == "plan":
            facts.plan_digest = "f" * 64

        def clock() -> Any:
            return NOW + timedelta(seconds=31 if change == "stale_after_read" else 0)

        with pytest.raises(HTTPException, match="lineage or time"):
            reader(facts, clock=clock)(db, doc.mandate, doc.plan, NOW)


@pytest.mark.retained_execution
@pytest.mark.usefixtures("retained_execution_engine")
def test_profile_lifetime_limits_downstream_dispatch_eligibility(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Any,
) -> None:
    from app.publication import execution_mandates
    from app.publication.execution_models import ProviderExecutionMandate

    with Session(customer_engine) as db:
        _, doc, facts = case(db, configuration, tmp_path)
        facts.expires_at = NOW + timedelta(seconds=300)
        evidence = reader(facts)(db, doc.mandate, doc.plan, NOW)
        mandate = db.get(ProviderExecutionMandate, doc.mandate.mandate_id)
        assert mandate is not None
        policy = execution_mandates.policy(db, mandate)
        assert evidence.eligible(policy, NOW + timedelta(seconds=29))
        assert not evidence.eligible(policy, NOW + timedelta(seconds=30))
        assert not evidence.eligible(policy, NOW + timedelta(seconds=299))


@pytest.mark.retained_execution
@pytest.mark.usefixtures("retained_execution_engine")
def test_unresolved_prior_period_holds_are_preserved_in_portfolio(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Any,
) -> None:
    from app.publication.execution_models import ProviderExposureReservation

    with Session(customer_engine) as db:
        _, doc, facts = case(db, configuration, tmp_path)
        old = ProviderPeriodLedger(
            id="a" * 32,
            workspace_id=doc.plan.review.scope.workspace_id,
            environment=doc.mandate.environment,
            currency=facts.currency,
            starts_at=facts.period_start - timedelta(days=60),
            ends_at=facts.period_start - timedelta(days=30),
        )
        db.add(old)
        db.flush()
        retained = ProviderExposureReservation(
            id="b" * 32,
            workspace_id=old.workspace_id,
            ledger_id=old.id,
            environment=old.environment,
            budget_owner_key="prior-period-owner",
            amount_micros=40,
            state="held",
            evidence={},
        )
        db.add(retained)
        db.commit()
        port = reader(facts)
        evidence = port(db, doc.mandate, doc.plan, NOW)
        assert evidence.existing_reservations_micros == 80
        assert evidence.portfolio_upper_micros == 130
        facts.budget_owner_key = retained.budget_owner_key
        with pytest.raises(HTTPException, match="retained"):
            port.for_activation(db, doc.mandate, doc.plan, retained.id, NOW)
        assert retained.state == "held"
