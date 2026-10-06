"""B09 deterministic execution and read-back; existing live boundary remains blocked."""

from datetime import timedelta
from uuid import uuid4

import pytest
from app.ads.models import AdvertisingAccount
from app.executors import google_actions as g
from app.executors.google_executor import (
    LiveGoogleAdsMutationAttemptBlocked,
    live_google_ads_mutation_boundary,
)
from app.google_connections.models import GoogleCustomerConnection
from app.mandates import service as m
from app.mandates.models import Mandate
from app.mandates.schemas import AccountScope
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_mandates import evidence, seed
from tests.test_shopify_sales import configuration as configuration


def setup(db: Session, config: Settings) -> tuple[Mandate, AccountScope, g.GoogleState]:
    mandate = seed(db, config)
    policy = m.policy(db, mandate)
    policy.allowed_actions.append("negative_keyword")
    m.edit(db, mandate, mandate.revision, policy, "owner", NOW)
    m.approve(db, mandate, mandate.revision, "owner", NOW)
    scope = policy.accounts[0]
    account = db.get(AdvertisingAccount, scope.account_id)
    assert account is not None
    account.external_account_id = "1234567890"
    db.add(
        GoogleCustomerConnection(
            id=uuid4().hex,
            workspace_id=mandate.workspace_id,
            integration_id=scope.connection_id,
            account_id=scope.account_id,
            external_account_id=account.external_account_id,
            encrypted_grant="fixture-unopened",
            generation=1,
            window_start=NOW.date(),
            window_end=NOW.date(),
            backfill_through=NOW.date(),
            history_floor=NOW.date() - timedelta(days=90),
            phase="recent",
            staged={},
        )
    )
    db.commit()
    state = g.GoogleState(
        customer_id=account.external_account_id,
        campaign_id="1",
        budget_id="2",
        channel="SEARCH",
        shared_budget=False,
        status="ENABLED",
        budget_micros=10,
        observed_at=NOW,
    )
    return mandate, scope, state


@pytest.mark.parametrize("kind", ["budget_change", "pause", "resume", "negative_keyword"])
def test_claim_apply_readback_retains_future_exposure(
    customer_engine: Engine, configuration: Settings, kind: str
) -> None:
    with Session(customer_engine) as db:
        mandate, scope, state = setup(db, configuration)
        if kind == "resume":
            state = state.model_copy(update={"status": "PAUSED"})
        body = {"kind": kind, "modeled_exposure_micros": 60}
        if kind == "budget_change":
            body["new_budget_micros"] = 20
        elif kind == "negative_keyword":
            body.update(keyword="fixture exclusion", match_type="EXACT")
        change = g.GoogleChange.model_validate(body)
        action = g.prepare(db, mandate, scope, state, change, "owner", NOW)
        preview = g.request_preview(action)
        assert preview["validate_only"] is True and preview["partial_failure"] is False
        assert (
            preview["customer_id"] == state.customer_id and len(preview["mutate_operations"]) == 1
        )
        adapter = g.FixtureGoogleActions({"1": state})
        adapter.timeout_after_apply = True
        if kind == "negative_keyword":
            with pytest.raises(HTTPException, match="action not eligible"):
                g.run_fixture(
                    db,
                    mandate,
                    action,
                    adapter,
                    evidence(db, mandate),
                    "fixture-attempt",
                    "owner",
                    NOW,
                )
            assert adapter.calls == 0
            m.review(db, mandate, action, action.digest, "owner", NOW)
            db.commit()
        g.run_fixture(
            db, mandate, action, adapter, evidence(db, mandate), "fixture-attempt", "owner", NOW
        )
        assert (
            adapter.calls == 1
            and action.state == "outcome_unknown"
            and mandate.reserved_micros == 60
        )
        assert g.reconcile_fixture(db, mandate, action, adapter, 10, "owner", NOW)
        assert (
            mandate.reserved_micros == 60
        )  # Matching settings do not erase future spend exposure.
        with pytest.raises(HTTPException):
            g.run_fixture(
                db, mandate, action, adapter, evidence(db, mandate), "fixture-attempt", "owner", NOW
            )
        assert adapter.calls == 1
        assert g.reconcile_fixture(
            db, mandate, action, adapter, 50, "owner", NOW + timedelta(days=2)
        )
        assert mandate.reserved_micros == 0 and mandate.observed_micros == 50
        assert action.state == "simulated_success"
        with pytest.raises(LiveGoogleAdsMutationAttemptBlocked):
            live_google_ads_mutation_boundary(preview)


def test_current_state_generation_and_unmatched_outcome_fail_closed(
    customer_engine: Engine, configuration: Settings
) -> None:
    with Session(customer_engine) as db:
        mandate, scope, state = setup(db, configuration)
        change = g.GoogleChange(
            kind="budget_change", new_budget_micros=20, modeled_exposure_micros=60
        )
        for bad in [
            state.model_copy(update={"shared_budget": True}),
            state.model_copy(update={"channel": "PERFORMANCE_MAX"}),
            state.model_copy(update={"customer_id": "9999999999"}),
            state.model_copy(update={"observed_at": NOW - timedelta(hours=1)}),
        ]:
            with pytest.raises(HTTPException):
                g.prepare(db, mandate, scope, bad, change, "owner", NOW)
        action = g.prepare(db, mandate, scope, state, change, "owner", NOW)
        adapter = g.FixtureGoogleActions({"1": state.model_copy(update={"budget_micros": 15})})
        with pytest.raises(HTTPException, match="current state"):
            g.run_fixture(
                db, mandate, action, adapter, evidence(db, mandate), "fixture-state", "owner", NOW
            )
        assert adapter.calls == 0
        adapter.states["1"] = state
        adapter.ignore_change = True
        g.run_fixture(
            db, mandate, action, adapter, evidence(db, mandate), "fixture-state", "owner", NOW
        )
        assert not g.reconcile_fixture(db, mandate, action, adapter, 10, "owner", NOW)
        assert mandate.reserved_micros == 60
        connection = g.connection(db, mandate, scope)
        connection.generation += 1
        db.commit()
        with pytest.raises(HTTPException, match="generation changed"):
            g.reconcile_fixture(db, mandate, action, adapter, 10, "owner", NOW)
        assert mandate.reserved_micros == 60 and adapter.calls == 1
