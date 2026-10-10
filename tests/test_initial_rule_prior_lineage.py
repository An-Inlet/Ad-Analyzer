"""A real prior native budget attempt consumes bootstrap across periods and policies."""

from pathlib import Path

import pytest
from app.initial_planning.automatic_source import no_prior_budget
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.reported_original_fixture import RetainedReportedOriginalIds
from tests.reported_original_fixture import customer_engine as customer_engine
from tests.reported_rule_current_fixture import ready_current_reported_rule
from tests.reported_rule_current_fixture import reported_rule_original as reported_rule_original
from tests.test_customer_identity import customer_engine as base_customer_engine  # noqa: F401
from tests.test_shopify_sales import configuration as configuration


def test_actual_prior_budget_cannot_be_reinterpreted_as_first_action(
    reported_rule_original: RetainedReportedOriginalIds,
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with Session(customer_engine) as db:
        _, _, work, _, _, _, _ = ready_current_reported_rule(
            db,
            configuration,
            tmp_path,
            monkeypatch,
            original=reported_rule_original,
            engine=customer_engine,
        )
        with pytest.raises(HTTPException, match="initial_rule_current_evidence_unavailable"):
            no_prior_budget(db, work.scope)
        # Changing only a future period/policy reference does not erase protected
        # native budget history. This is not presented as a valid execution mandate.
        future_scope = work.scope.model_copy(
            update={
                "mandate": work.scope.mandate.model_copy(
                    update={"ledger_id": "a" * 32, "revision": work.scope.mandate.revision + 1},
                )
            }
        )
        with pytest.raises(HTTPException, match="initial_rule_current_evidence_unavailable"):
            no_prior_budget(db, future_scope)


def test_actual_creation_history_does_not_consume_budget_history_bound(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.initial_planning import automatic_source
    from app.publication import coordinator
    from app.publication.execution_models import ProviderExecutionRun, ProviderExposureReservation

    from tests.test_commerce_measurement import NOW
    from tests.test_initial_rule_candidates import fixture
    from tests.test_social_coordinator_journeys import SocialServer, ready

    server = SocialServer("meta_ads")
    with Session(customer_engine) as db:
        wid, run_id, actor, media, runtime, _ = ready(
            db,
            configuration,
            tmp_path,
            "meta_ads",
            None,
            server,
        )
        count = 0
        while claim := coordinator.claim_creation_step(
            db, wid, run_id, actor, media, runtime, lambda: NOW
        ):
            receipt = coordinator.execute_claim(db, claim, actor, media, runtime, lambda: NOW)
            assert receipt.outcome == "verified_effect"
            count += 1
        assert count == 5
        template, _, _, _ = fixture()
        scope = template.scope.model_copy(
            update={
                "account": template.scope.account.model_copy(
                    update={"workspace_id": wid},
                )
            }
        )
        monkeypatch.setattr(automatic_source, "MAX_PRIOR_BUDGET_ATTEMPTS", 1)
        assert no_prior_budget(db, scope) is None
        # This grants no execution permission: the creation reservation remains held.
        run = db.get(ProviderExecutionRun, run_id)
        assert run is not None and run.reservation_id is not None
        reservation = db.get(ProviderExposureReservation, run.reservation_id)
        assert reservation is not None and reservation.state == "held"


def test_actual_activation_history_is_not_a_budget_decision(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.initial_planning import automatic_source
    from app.publication import activation
    from app.publication.execution_models import ProviderExposureReservation

    from tests.test_commerce_measurement import NOW
    from tests.test_initial_rule_candidates import fixture
    from tests.test_social_activation_journeys import Server, approved

    server = Server("meta_ads")
    with Session(customer_engine) as db:
        wid, run, actor, store, runtime, _ = approved(
            db, configuration, tmp_path, "meta_ads", None, server
        )
        steps = 0
        while claim := activation.claim_step(db, wid, run.id, actor, store, runtime, lambda: NOW):
            receipt = activation.execute_claim(db, claim, actor, store, runtime, lambda: NOW)
            assert receipt.outcome == "verified_target_state"
            steps += 1
        assert steps == 3
        template, _, _, _ = fixture()
        scope = template.scope.model_copy(
            update={"account": template.scope.account.model_copy(update={"workspace_id": wid})}
        )
        monkeypatch.setattr(automatic_source, "MAX_PRIOR_BUDGET_ATTEMPTS", 1)
        assert no_prior_budget(db, scope) is None
        reservation = db.get(ProviderExposureReservation, run.reservation_id)
        assert reservation is not None and reservation.state == "held"
