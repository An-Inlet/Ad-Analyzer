"""Policy rollout against genuine pre-policy financial graphs, no live provider."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from app.publication import coordinator as c
from app.publication.coordinator_contracts import CreationExecutionReview
from app.publication.execution_models import (
    ProviderExecutionAttempt,
    ProviderExecutionReview,
    ProviderExecutionRun,
    ProviderExposureReservation,
)
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_campaign_video import encoded as encoded
from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_shopify_sales import configuration as configuration
from tests.test_social_coordinator_journeys import SocialServer, ready


@pytest.mark.parametrize("emitted", [False, True])
def test_legacy_forward_creation_stops_without_erasing_original_history(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    encoded: Any,
    emitted: bool,
) -> None:
    server = SocialServer("tiktok_ads")
    server.timeout = emitted
    with Session(customer_engine) as db:
        # Explicit historical fixture: execute the old policy through real coordinator
        # methods only inside this setup context. No product runtime exemption exists.
        with monkeypatch.context() as historical:
            historical.setattr(c, "new_creation_allowed", lambda _: None)
            wid, run_id, actor, store, runtime, _ = ready(
                db, configuration, tmp_path, "tiktok_ads", encoded(), server
            )
            claim = c.claim_creation_step(db, wid, run_id, actor, store, runtime, lambda: NOW)
            assert claim is not None
            if emitted:
                assert (
                    c.execute_claim(db, claim, actor, store, runtime, lambda: NOW).outcome
                    == "unknown"
                )
        run = db.get(ProviderExecutionRun, run_id)
        assert run is not None
        review = db.get(ProviderExecutionReview, run.review_id)
        assert review is not None
        document = CreationExecutionReview.model_validate(review.document)
        original_hash = document.digest()
        posts = server.posts
        forward: list[Callable[[], object]] = [
            lambda: c.prepare_creation(
                db, wid, document.plan, document.mandate, actor, store, runtime, lambda: NOW
            ),
            lambda: c.approve_creation(
                db,
                wid,
                review.id,
                review.digest,
                review.plan_digest,
                actor,
                store,
                runtime,
                lambda: NOW,
            ),
            lambda: c.create_run(db, wid, review.id, actor, store, runtime, lambda: NOW),
            lambda: c.claim_creation_step(db, wid, run_id, actor, store, runtime, lambda: NOW),
            lambda: c.execute_claim(db, claim, actor, store, runtime, lambda: NOW),
        ]
        for operation in forward:
            with pytest.raises(HTTPException) as caught:
                operation()
            assert caught.value.status_code == 409
            assert caught.value.detail == "tiktok_new_custom_identity_creation_unavailable"
            db.rollback()
        assert server.posts == posts
        # Historical parsing/readback survives; an unknown original is never replayed.
        assert CreationExecutionReview.model_validate(review.document).digest() == original_hash
        receipt = c.reconcile_attempt(db, wid, claim.attempt_id, runtime, lambda: NOW)
        assert receipt.outcome == "unknown"
        assert server.posts == posts
        assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 1
        reservation = db.scalar(select(ProviderExposureReservation))
        assert reservation is not None and reservation.state == "held"
