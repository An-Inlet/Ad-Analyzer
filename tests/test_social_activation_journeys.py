"""Actual social adapters behind durable separate activation consent and ledger."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

import httpx
import pytest
from app.executors.google_activation import GoogleActivationHTTP
from app.executors.meta_activation import MetaActivationHTTP
from app.executors.tiktok_activation import TikTokActivationHTTP
from app.publication import activation as a
from app.publication import activation_review as r
from app.publication import coordinator as c
from app.publication.activation_contracts import ActivationContext, ActivationRequest
from app.publication.coordinator_contracts import CreationExecutionReview, CreationPlan
from app.publication.execution_contracts import ExposureEvidence, ProviderMandateBinding
from app.publication.execution_models import (
    ProviderExecutionAttempt,
    ProviderExecutionReview,
    ProviderExecutionRun,
    ProviderExposureReservation,
)
from app.publication.scoped_media import ScopedProviderMediaReader
from app.settings import Settings
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_campaign_video import encoded as encoded
from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_shopify_sales import configuration as configuration
from tests.test_social_coordinator_journeys import SocialServer, ready


class Server(SocialServer):
    def __init__(self, provider: str) -> None:
        super().__init__(provider)
        self.activations = 0
        self.activation_timeout = False
        self.delay = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        last = request.url.path.rsplit("/", 1)[-1]
        if request.method == "POST" and (
            (self.provider == "meta_ads" and last.isdigit())
            or request.url.path.endswith("/status/update/")
        ):
            self.activations += 1
            if self.provider == "meta_ads":
                body = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
                assert body == {"status": "ACTIVE"}
                external = last
                response: dict[str, Any] = {"success": True}
            else:
                body = json.loads(request.content)
                kind = request.url.path.split("/")[-4]
                external = body[kind + "_ids"][0]
                assert (
                    body["operation_status"] == "ENABLE" and body["advertiser_id"] == "1234567890"
                )
                body = {"operation_status": "ENABLE"}
                response = {"code": 0, "data": {}}
            if not self.delay:
                self.rows[external].update(body)
            if self.activation_timeout:
                raise httpx.ReadTimeout("offline uncertain activation")
            return httpx.Response(200, json=response)
        return super().__call__(request)


def prepared(
    db: Session, config: Settings, path: Path, provider: str, video: bytes | None, server: Server
) -> tuple[int, str, str, Any, r.ActivationReviewRuntime, ProviderMandateBinding, Any]:
    wid, parent, actor, store, creation, native = ready(db, config, path, provider, video, server)
    while claim := c.claim_creation_step(db, wid, parent, actor, store, creation, lambda: NOW):
        assert (
            c.execute_claim(db, claim, actor, store, creation, lambda: NOW).outcome
            == "verified_effect"
        )
    parent_run = db.get(ProviderExecutionRun, parent)
    assert parent_run is not None
    row = db.get(ProviderExecutionReview, parent_run.review_id)
    assert row is not None
    binding = CreationExecutionReview.model_validate(row.document).mandate

    def exposure(
        session: Session,
        b: ProviderMandateBinding,
        plan: CreationPlan,
        reservation_id: str,
        now: datetime,
    ) -> ExposureEvidence:
        base = creation.exposure_reader(session, b, plan, now)
        held = session.get(ProviderExposureReservation, reservation_id)
        assert held is not None and base.portfolio_upper_micros is not None
        assert held.amount_micros == base.proposed_owner_upper_micros
        return ExposureEvidence.model_validate(
            base.model_copy(
                update={
                    "existing_reservations_micros": base.existing_reservations_micros
                    - held.amount_micros,
                    "portfolio_upper_micros": base.portfolio_upper_micros - held.amount_micros,
                }
            ).model_dump()
        )

    return wid, parent, actor, store, r.ActivationReviewRuntime(creation, exposure), binding, native


def runtime_for(
    db: Session, store: Any, review: r.ActivationReviewRuntime, server: Server
) -> a.ActivationRuntime:
    media = ScopedProviderMediaReader(db, store)

    def context(request: ActivationRequest) -> ActivationContext:
        return ActivationContext(
            account=request.account,
            access_token=SecretStr("offline-token"),
            expires_at=NOW + timedelta(hours=1),
        )

    return a.ActivationRuntime(
        review,
        GoogleActivationHTTP(
            transport=httpx.MockTransport(
                lambda _: (_ for _ in ()).throw(AssertionError("unexpected Google"))
            )
        ),
        MetaActivationHTTP(media, transport=httpx.MockTransport(server)),
        TikTokActivationHTTP(media, transport=httpx.MockTransport(server)),
        context,
    )


def approved(
    db: Session, config: Settings, path: Path, provider: str, video: bytes | None, server: Server
) -> tuple[int, Any, str, Any, a.ActivationRuntime, Any]:
    wid, parent, actor, store, review, binding, native = prepared(
        db, config, path, provider, video, server
    )
    row = r.prepare_activation(db, wid, parent, binding, actor, store, review, lambda: NOW)
    with pytest.raises(HTTPException, match="separate exact"):
        r.create_run(db, wid, row.id, actor, store, review, lambda: NOW)
    db.rollback()
    r.approve_activation(
        db, wid, row.id, row.digest, row.plan_digest, actor, store, review, lambda: NOW
    )
    run = r.create_run(db, wid, row.id, actor, store, review, lambda: NOW)
    return wid, run, actor, store, runtime_for(db, store, review, server), native


@pytest.mark.parametrize("provider", ["meta_ads", "tiktok_ads"])
def test_full_persisted_social_activation_reuses_original_reservation(
    customer_engine: Engine, configuration: Settings, tmp_path: Path, encoded: Any, provider: str
) -> None:
    server = Server(provider)
    with Session(customer_engine) as db:
        wid, run, actor, store, runtime, _ = approved(
            db,
            configuration,
            tmp_path,
            provider,
            encoded() if provider == "tiktok_ads" else None,
            server,
        )
        parent = db.get(ProviderExecutionRun, run.parent_run_id)
        assert parent is not None and parent.reservation_id == run.reservation_id
        order = []
        while claim := a.claim_step(db, wid, run.id, actor, store, runtime, lambda: NOW):
            receipt = a.execute_claim(db, claim, actor, store, runtime, lambda: NOW)
            assert receipt.outcome == "verified_target_state"
            order.append(claim.request.target.step_id)
            projection = c.read_owned_outcome_receipt(db, wid, claim.attempt_id, actor)
            assert projection is not None and projection.purpose == "activate"
            assert projection.effective_lower is None and projection.effective_upper is None
            assert projection.fence == claim.request.fence
            with pytest.raises(HTTPException):
                a.execute_claim(db, claim, actor, store, runtime, lambda: NOW)
            db.rollback()
            with pytest.raises(HTTPException):
                c.read_owned_outcome_receipt(db, wid + 999, claim.attempt_id, actor)
            db.rollback()
        assert len(order) == server.activations == 3 and order[-1] == "campaign"
        assert db.scalar(select(func.count()).select_from(ProviderExposureReservation)) == 1
        held = db.get(ProviderExposureReservation, run.reservation_id)
        assert held is not None and held.state == "held" and held.amount_micros == 40_000_000
        finished = db.get(ProviderExecutionRun, run.id)
        assert finished is not None and finished.state == "activation_observed"


@pytest.mark.parametrize("provider", ["meta_ads", "tiktok_ads"])
def test_unknown_social_activation_retains_attempt_then_reconciles_without_replay(
    customer_engine: Engine, configuration: Settings, tmp_path: Path, encoded: Any, provider: str
) -> None:
    server = Server(provider)
    with Session(customer_engine) as db:
        wid, run, actor, store, runtime, _ = approved(
            db,
            configuration,
            tmp_path,
            provider,
            encoded() if provider == "tiktok_ads" else None,
            server,
        )
        claim = a.claim_step(db, wid, run.id, actor, store, runtime, lambda: NOW)
        assert claim is not None
        server.delay = True
        server.activation_timeout = True
        assert a.execute_claim(db, claim, actor, store, runtime, lambda: NOW).outcome == "unknown"
        assert a.claim_step(db, wid, run.id, actor, store, runtime, lambda: NOW) is None
        assert (
            a.reconcile_attempt(db, wid, claim.attempt_id, runtime, lambda: NOW).outcome
            == "unknown"
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(ProviderExecutionAttempt)
                .where(ProviderExecutionAttempt.run_id == run.id)
            )
            == 1
        )
        external = claim.request.target.resource_name.rsplit("/", 1)[1]
        server.rows[external]["status" if provider == "meta_ads" else "operation_status"] = (
            "ACTIVE" if provider == "meta_ads" else "ENABLE"
        )
        late = a.reconcile_attempt(
            db, wid, claim.attempt_id, runtime, lambda: NOW + timedelta(seconds=1)
        )
        assert late.outcome == "verified_target_state" and late.fence == claim.request.fence
        assert server.activations == 1
        projected = c.read_owned_outcome_receipt(db, wid, claim.attempt_id, actor)
        assert projected is not None and projected.sequence == 2
        held = db.get(ProviderExposureReservation, run.reservation_id)
        assert held is not None and held.state == "held"


@pytest.mark.parametrize("provider", ["meta_ads", "tiktok_ads"])
@pytest.mark.parametrize("change", ["creative_or_media", "cancel", "disconnect", "generation"])
def test_post_claim_graph_or_authority_drift_prevents_activation(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    encoded: Any,
    provider: str,
    change: str,
) -> None:
    server = Server(provider)
    with Session(customer_engine) as db:
        wid, run, actor, store, runtime, native = approved(
            db,
            configuration,
            tmp_path,
            provider,
            encoded() if provider == "tiktok_ads" else None,
            server,
        )
        claim = a.claim_step(db, wid, run.id, actor, store, runtime, lambda: NOW)
        assert claim is not None
        if change == "creative_or_media":
            if provider == "meta_ads":
                server.rows["104"]["object_story_spec"]["link_data"]["message"] = (
                    "unreviewed outside edit"
                )
            else:
                server.rows["imageid"]["width"] = 999
        elif change == "cancel":
            c.cancel_creation(db, wid, run.id, actor, lambda: NOW)
        elif change == "disconnect":
            db.delete(native)
            db.commit()
        else:
            native.generation += 1
            db.commit()
        with pytest.raises(HTTPException):
            a.execute_claim(db, claim, actor, store, runtime, lambda: NOW)
        db.rollback()
        assert server.activations == 0
        held = db.get(ProviderExposureReservation, run.reservation_id)
        assert held is not None and held.state == "held"
