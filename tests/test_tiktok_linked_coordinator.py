"""Persisted linked review/consent through durable coordinator with actual MockHTTP."""

from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from app.publication import coordinator as c
from app.publication.execution_models import ProviderExecutionRun, ProviderExposureReservation
from app.publication.social_review_models import SocialConfigurationReview
from app.publication.tiktok_linked_review_service import verify_plan
from app.settings import Settings
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.test_campaign_video import encoded as encoded
from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_shopify_sales import configuration as configuration
from tests.test_social_coordinator_journeys import SocialServer
from tests.tiktok_linked_coordinator_fixture import ready_linked


@pytest.mark.retained_execution
@pytest.mark.usefixtures("retained_execution_engine")
def test_linked_persisted_configuration_and_complete_disabled_graph(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    encoded: Any,
) -> None:
    server = SocialServer("tiktok_ads")
    with Session(customer_engine) as db:
        wid, run_id, actor, store, runtime, _ = ready_linked(
            db, configuration, tmp_path, "tiktok_ads", encoded(), server
        )
        run = db.get(ProviderExecutionRun, run_id)
        assert run is not None
        _, original = c.checked_review(db, wid, run.review_id, actor, store, runtime, lambda: NOW)
        from app.publication.tiktok_linked_plan import LinkedPushPlanV1

        assert isinstance(original.plan, LinkedPushPlanV1)
        row = db.get(SocialConfigurationReview, original.plan.review.configuration_review.review_id)
        assert row is not None
        db.expire_all()
        checked = verify_plan(db, wid, original.plan, actor)
        assert checked.digest() == row.digest
        count = 0
        later = NOW + timedelta(seconds=30)
        while claim := c.claim_creation_step(db, wid, run_id, actor, store, runtime, lambda: later):
            receipt = c.execute_claim(db, claim, actor, store, runtime, lambda: later)
            assert receipt.outcome == "verified_effect", claim.request.step.step_id
            count += 1
        assert count == server.posts == 5
        db.expire_all()
        run = db.get(ProviderExecutionRun, run_id)
        assert run is not None and run.state == "created_paused"
        held = db.scalar(
            select(ProviderExposureReservation).where(
                ProviderExposureReservation.workspace_id == wid
            )
        )
        assert held is not None and held.state == "held"


@pytest.mark.retained_execution
@pytest.mark.usefixtures("retained_execution_engine")
def test_linked_missing_current_validator_and_erased_approval_block_forward_only(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    encoded: Any,
) -> None:
    from dataclasses import replace

    from app.publication.social_review_models import SocialConfigurationApproval
    from fastapi import HTTPException

    server = SocialServer("tiktok_ads")
    with Session(customer_engine) as db:
        wid, run_id, actor, store, runtime, _ = ready_linked(
            db, configuration, tmp_path, "tiktok_ads", encoded(), server
        )
        with pytest.raises(HTTPException, match="linked configuration runtime unavailable"):
            c.claim_creation_step(
                db,
                wid,
                run_id,
                actor,
                store,
                replace(runtime, linked_configuration_current=None),
                lambda: NOW,
            )
        db.rollback()
        assert server.posts == 0
        claim = c.claim_creation_step(db, wid, run_id, actor, store, runtime, lambda: NOW)
        assert claim is not None
        server.timeout = True
        receipt = c.execute_claim(db, claim, actor, store, runtime, lambda: NOW)
        assert receipt.outcome == "unknown" and server.posts == 1
        from app.publication.tiktok_linked_plan import LinkedPushBoundRequestV1

        assert isinstance(claim.request, LinkedPushBoundRequestV1)
        approval = db.get(
            SocialConfigurationApproval, claim.request.review.configuration_review.review_id
        )
        assert approval is not None
        db.delete(approval)
        db.commit()
        with pytest.raises(HTTPException, match="exact confirmed linked configuration"):
            c.claim_creation_step(db, wid, run_id, actor, store, runtime, lambda: NOW)
        db.rollback()
        again = c.reconcile_attempt(db, wid, claim.attempt_id, runtime, lambda: NOW)
        assert again.outcome == "unknown" and server.posts == 1
        held = db.scalar(
            select(ProviderExposureReservation).where(
                ProviderExposureReservation.workspace_id == wid
            )
        )
        assert held is not None and held.state == "held"
