"""Persisted approved source -> separate consent -> real mocked social HTTP graphs."""

import base64
import hashlib
import json
from datetime import timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs
from uuid import uuid4

import httpx
import pytest
from app.ads.enums import AdvertisingPlatform
from app.ads.models import AdvertisingAccount
from app.campaign_review import service as source
from app.campaign_review.contracts import RevisionInput
from app.campaign_review.storage import LocalMediaStore
from app.executors.google_publication import GooglePublicationHTTP
from app.executors.meta_publication import MetaPublicationTransport
from app.executors.tiktok_publication import TikTokPublicationTransport
from app.mandates import service as simulation
from app.mandates.models import Mandate
from app.mandates.schemas import AccountScope
from app.meta.models import MetaConnection
from app.publication import coordinator as c
from app.publication import execution_mandates as mandates
from app.publication.coordinator_contracts import (
    ConfigurationQualification,
    CreationPlan,
    CreationRuntime,
)
from app.publication.execution_contracts import (
    ExecutionAccount,
    ExposureEvidence,
    ProviderMandateBinding,
)
from app.publication.execution_models import (
    ProviderExecutionAttempt,
    ProviderExecutionRun,
    ProviderExposureReservation,
)
from app.publication.scoped_media import ScopedProviderMediaReader
from app.publication.social_compiler import compile_social
from app.publication.social_contracts import SocialProviderContext, SocialPublicationReview
from app.settings import Settings
from app.sources.models import SourceConnection
from app.workspaces.models import WorkspaceIntegration
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_campaign_review import png
from tests.test_campaign_video import encoded as encoded
from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_provider_execution_mandates import setup
from tests.test_shopify_sales import configuration as configuration
from tests.test_social_publication_http import reviewed, tiktok_reviewed


class SocialServer:
    def __init__(self, provider: str) -> None:
        self.provider = provider
        self.rows: dict[str, dict[str, Any]] = {}
        self.posts = 0
        self.timeout = False
        self.media: dict[str, Any] = {}

    def __call__(self, req: httpx.Request) -> httpx.Response:
        if req.method == "POST":
            response: dict[str, Any]
            raw: Any
            self.posts += 1
            if self.provider == "meta_ads":
                raw = {
                    k: v[0]
                    for k, v in parse_qs(req.content.decode(), keep_blank_values=True).items()
                }
                body: dict[str, Any] = {}
                for k, v in raw.items():
                    try:
                        body[k] = v if k.endswith("_id") else json.loads(v)
                    except ValueError:
                        body[k] = v
                if req.url.path.endswith("/adimages"):
                    binding = self.media["image"]
                    assert (
                        hashlib.sha256(base64.b64decode(body["bytes"])).hexdigest()
                        == binding.sha256
                    )
                    identity = "imagehash"
                    row = {
                        "account_id": "1234567890",
                        "hash": identity,
                        "original_width": binding.width,
                        "original_height": binding.height,
                    }
                    response = {"images": {"image": {"hash": identity}}}
                else:
                    identity = str(100 + self.posts)
                    row = {**body, "id": identity, "account_id": "1234567890"}
                    if "creative" in row:
                        row["creative"] = {"id": body["creative"]["creative_id"]}
                    if "status" in body:
                        assert body["status"] == "PAUSED"
                    response = {"id": identity}
            else:
                if "/upload/" in req.url.path:
                    from email.parser import BytesParser
                    from email.policy import default

                    msg = BytesParser(policy=default).parsebytes(
                        b"Content-Type: "
                        + req.headers["content-type"].encode()
                        + b"\r\n\r\n"
                        + req.content
                    )
                    parts = {
                        part.get_param("name", header="content-disposition"): part.get_payload(
                            decode=True
                        )
                        for part in msg.iter_parts()
                    }
                    kind = "video" if "/video/" in req.url.path else "image"
                    binding = self.media[kind]
                    raw = parts[kind + "_file"]
                    assert (
                        isinstance(raw, bytes) and hashlib.sha256(raw).hexdigest() == binding.sha256
                    )
                    identity = kind + "id"
                    row = {kind + "_id": identity, "width": binding.width, "height": binding.height}
                    if kind == "video":
                        row.update(
                            signature=hashlib.md5(raw, usedforsecurity=False).hexdigest(),
                            size=len(raw),
                            duration=binding.duration_ms / 1000,
                            allowed_placements=["PLACEMENT_TIKTOK"],
                            displayable=True,
                        )
                    response = {"code": 0, "data": {kind + "_id": identity}}
                else:
                    body = json.loads(req.content)
                    kind = req.url.path.split("/")[-3]
                    identity = str(100 + self.posts)
                    if kind == "ad":
                        row = {
                            "advertiser_id": body["advertiser_id"],
                            "adgroup_id": body["adgroup_id"],
                            **body["creatives"][0],
                        }
                    else:
                        row = dict(body)
                    assert row["operation_status"] == "DISABLE"
                    row[kind + "_id"] = identity
                    response = {
                        "code": 0,
                        "data": {"ad_ids": [identity]}
                        if kind == "ad"
                        else {kind + "_id": identity},
                    }
            self.rows[identity] = row
            if self.timeout:
                raise httpx.ReadTimeout("offline lost acknowledgement")
            return httpx.Response(200, json=response)
        if self.provider == "meta_ads":
            if req.url.path.endswith("/adimages"):
                return httpx.Response(200, json={"data": [self.rows["imagehash"]]})
            return httpx.Response(200, json=self.rows[req.url.path.rsplit("/", 1)[1]])
        params = req.url.params
        if "/file/" in req.url.path:
            ids = json.loads(params["video_ids"] if "video_ids" in params else params["image_ids"])
        else:
            ids = next(iter(json.loads(params["filtering"]).values()))
        return httpx.Response(200, json={"code": 0, "data": {"list": [self.rows[ids[0]]]}})


def ready_legacy(
    db: Session,
    config: Settings,
    path: Path,
    provider: str,
    video: bytes | None,
    server: SocialServer,
) -> tuple[int, str, str, LocalMediaStore, CreationRuntime, Any]:
    # Confirm the matching goal ceiling before constructing the social mandate.
    policy, actor = setup(db, config, path, goal_budget_micros=100_000_000)
    wid = policy.workspace_id
    old = db.scalar(select(Mandate).where(Mandate.workspace_id == wid))
    assert old is not None
    integration = WorkspaceIntegration(
        workspace_id=wid,
        integration_key="social-journey",
        provider=provider,
        display_name="Offline social",
        status="active",
        configuration={},
    )
    db.add(integration)
    db.flush()
    account = AdvertisingAccount(
        workspace_id=wid,
        connection_id=integration.id,
        platform=AdvertisingPlatform(provider),
        external_account_id="1234567890",
        name="Offline",
        currency_code="USD",
        time_zone="UTC",
    )
    db.add(account)
    db.flush()
    native: Any
    if provider == "meta_ads":
        native = MetaConnection(
            workspace_id=wid,
            workspace_integration_id=integration.id,
            account_id=account.id,
            external_account_id=account.external_account_id,
            encrypted_credentials="never-opened-offline",
        )
    else:
        native = SourceConnection(
            id=uuid4().hex,
            workspace_id=wid,
            integration_id=integration.id,
            account_id=account.id,
            provider=provider,
            external_id=account.external_account_id,
            status="connected",
            generation=1,
            window_start=NOW.date(),
            window_end=NOW.date(),
            staged={},
        )
    db.add(native)
    db.flush()
    scope = AccountScope(platform=provider, connection_id=integration.id, account_id=account.id)
    sim = simulation.policy(db, old).model_copy(
        update={
            "accounts": [scope],
            "total_cap_micros": 100_000_000,
            "per_action_cap_micros": 80_000_000,
            "positive_change_cap_micros": 20_000_000,
        }
    )
    simulation.edit(db, old, old.revision, sim, actor, NOW)
    simulation.approve(db, old, old.revision, actor, NOW)
    db.commit()
    store = LocalMediaStore(path)
    media = source.upload(db, wid, actor, video if video is not None else png(), store, NOW)
    cover = source.upload(db, wid, actor, png(), store, NOW)
    content = (
        reviewed() if provider == "meta_ads" else tiktok_reviewed()
    ).source.definition.content.model_dump()
    content["media"] = {"media_id": media.id, "sha256": media.sha256}
    body = RevisionInput(
        account=scope,
        mandate_id=old.id,
        mandate_revision=old.revision,
        currency="USD",
        budget_micros=40_000_000,
        starts_at=NOW,
        ends_at=NOW + timedelta(hours=1),
        content=content,
    )
    revision = source.revise(db, wid, body, actor, store, NOW)
    source.approve(
        db, wid, revision.draft_id, revision.revision, revision.digest, actor, store, NOW
    )
    _, artifact = source.preview(db, wid, revision.draft_id, store, NOW)
    media_reader = ScopedProviderMediaReader(db, store)
    fields = (
        reviewed() if provider == "meta_ads" else tiktok_reviewed()
    ).configuration.model_dump()
    fields["reservation_micros"] = 40_000_000
    if provider == "meta_ads":
        fields.update(
            adset_lifetime_budget_micros=40_000_000, image=media_reader.binding(wid, media.id)
        )
        server.media = {"image": fields["image"]}
    else:
        fields.update(
            lifetime_budget_micros=40_000_000,
            video=media_reader.binding(wid, media.id),
            cover=media_reader.binding(wid, cover.id),
        )
        server.media = {"video": fields["video"], "image": fields["cover"]}
    review = SocialPublicationReview(
        source=artifact,
        source_digest=artifact.fingerprint(),
        scope={
            "workspace_id": wid,
            "account": scope,
            "external_advertiser_id": account.external_account_id,
            "connection_version": artifact.connection_version,
            "mandate_id": old.id,
            "mandate_revision": old.revision,
        },
        configuration=fields,
        qualification_blockers=["live_profile_unqualified"],
    )
    plan = compile_social(review)
    policy = policy.model_copy(
        update={
            "accounts": [ExecutionAccount.from_publication(review.scope)],
            "total_cap_micros": 100_000_000,
            "per_plan_cap_micros": 80_000_000,
            "positive_change_cap_micros": 20_000_000,
        }
    )
    production = mandates.revise(db, wid, policy, actor, lambda: NOW)
    consent = mandates.consent(db, wid, production.id, 1, policy.digest(), actor, lambda: NOW)

    def qualify(p: CreationPlan, now: Any) -> ConfigurationQualification:
        assert p.digest() == plan.digest()
        return ConfigurationQualification(
            environment="contract_test",
            account=policy.accounts[0],
            plan_digest=p.digest(),
            api_version=p.api_version,
            observed_at=now,
            expires_at=now + timedelta(minutes=5),
            evidence_digest=p.digest(),
            checks_version="explicit_mock_http_scenario_not_live_v1",
            unresolved=[],
        )

    def exposure(
        session: Session, b: ProviderMandateBinding, p: CreationPlan, now: Any
    ) -> ExposureEvidence:
        held = (
            session.scalar(
                select(func.coalesce(func.sum(ProviderExposureReservation.amount_micros), 0)).where(
                    ProviderExposureReservation.workspace_id == wid,
                    ProviderExposureReservation.state == "held",
                )
            )
            or 0
        )
        held = int(held)  # PostgreSQL SUM(bigint) returns an exact Decimal.
        return ExposureEvidence(
            environment="contract_test",
            mandate=b,
            account=policy.accounts[0],
            covered_account_ids=[account.id],
            budget_owner_key="new/" + provider + "/" + p.digest(),
            target_set_digest=p.digest(),
            state_digest=p.digest(),
            currency="USD",
            period_start=policy.starts_at,
            period_end=policy.ends_at,
            observed_at=now,
            expires_at=now + timedelta(minutes=5),
            reporting_watermark=now,
            completeness="complete",
            qualification_id="f" * 32,
            model_version="explicit_contract_scenario_v1",
            cap_semantics="contract_scenario",
            reported_spend_micros=0,
            unreported_upper_micros=0,
            unchanged_future_upper_micros=0,
            proposed_owner_upper_micros=40_000_000,
            existing_reservations_micros=held,
            portfolio_upper_micros=held + 40_000_000,
        )

    runtime = CreationRuntime(
        environment="contract_test",
        qualification_reader=qualify,
        exposure_reader=exposure,
        google=GooglePublicationHTTP(
            transport=httpx.MockTransport(
                lambda r: (_ for _ in ()).throw(AssertionError("unexpected Google"))
            )
        ),
        meta=MetaPublicationTransport(media_reader, transport=httpx.MockTransport(server)),
        tiktok=TikTokPublicationTransport(media_reader, transport=httpx.MockTransport(server)),
        google_context=lambda r: (_ for _ in ()).throw(AssertionError("unexpected Google context")),
        social_context=lambda r: SocialProviderContext(
            scope=r.scope,
            access_token=SecretStr("offline-token"),
            expires_at=NOW + timedelta(hours=1),
        ),
    )
    row = c.prepare_creation(db, wid, plan, consent, actor, store, runtime, lambda: NOW)
    c.approve_creation(
        db, wid, row.id, row.digest, row.plan_digest, actor, store, runtime, lambda: NOW
    )
    run = c.create_run(db, wid, row.id, actor, store, runtime, lambda: NOW)
    return wid, run.id, actor, store, runtime, native


def ready(
    db: Session,
    config: Settings,
    path: Path,
    provider: str,
    video: bytes | None,
    server: SocialServer,
) -> tuple[int, str, str, LocalMediaStore, CreationRuntime, Any]:
    if provider == "tiktok_ads":
        from tests.tiktok_linked_coordinator_fixture import ready_linked

        return ready_linked(db, config, path, provider, video, server)
    return ready_legacy(db, config, path, provider, video, server)


@pytest.mark.retained_execution
@pytest.mark.usefixtures("retained_execution_engine")
@pytest.mark.parametrize("provider", ["meta_ads", "tiktok_ads"])
def test_persisted_social_full_graph(
    customer_engine: Engine, configuration: Settings, tmp_path: Path, encoded: Any, provider: str
) -> None:
    server = SocialServer(provider)
    with Session(customer_engine) as db:
        wid, run_id, actor, store, runtime, _ = ready(
            db,
            configuration,
            tmp_path,
            provider,
            encoded() if provider == "tiktok_ads" else None,
            server,
        )
        count = 0
        while claim := c.claim_creation_step(db, wid, run_id, actor, store, runtime, lambda: NOW):
            receipt = c.execute_claim(db, claim, actor, store, runtime, lambda: NOW)
            assert receipt.outcome == "verified_effect"
            projected = c.read_owned_outcome_receipt(db, wid, claim.attempt_id, actor)
            assert projected is not None and projected.environment == "contract_test"
            assert projected.fence == claim.request.fence and projected.effective_upper is None
            with pytest.raises(HTTPException):
                c.execute_claim(db, claim, actor, store, runtime, lambda: NOW)
            db.rollback()
            count += 1
        assert count == server.posts == 5
        run = db.get(ProviderExecutionRun, run_id)
        assert run is not None and run.state == "created_paused"
        reservation = db.get(ProviderExposureReservation, run.reservation_id)
        assert (
            reservation is not None
            and reservation.state == "held"
            and reservation.amount_micros == 40_000_000
        )


@pytest.mark.retained_execution
@pytest.mark.usefixtures("retained_execution_engine")
@pytest.mark.parametrize("provider", ["meta_ads", "tiktok_ads"])
def test_unknown_and_native_revocation_keep_attempt_and_reservation(
    customer_engine: Engine, configuration: Settings, tmp_path: Path, encoded: Any, provider: str
) -> None:
    server = SocialServer(provider)
    server.timeout = True
    with Session(customer_engine) as db:
        wid, run_id, actor, store, runtime, native = ready(
            db,
            configuration,
            tmp_path,
            provider,
            encoded() if provider == "tiktok_ads" else None,
            server,
        )
        claim = c.claim_creation_step(db, wid, run_id, actor, store, runtime, lambda: NOW)
        assert claim is not None
        assert c.execute_claim(db, claim, actor, store, runtime, lambda: NOW).outcome == "unknown"
        assert (
            c.reconcile_attempt(db, wid, claim.attempt_id, runtime, lambda: NOW).outcome
            == "unknown"
        )
        assert c.claim_creation_step(db, wid, run_id, actor, store, runtime, lambda: NOW) is None
        assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 1
        native.generation += 1
        db.commit()
        with pytest.raises(HTTPException):
            c.claim_creation_step(db, wid, run_id, actor, store, runtime, lambda: NOW)
        db.rollback()
        with pytest.raises(HTTPException):
            c.read_owned_outcome_receipt(db, wid + 999, claim.attempt_id, actor)
        db.rollback()
        run = db.get(ProviderExecutionRun, run_id)
        assert run is not None
        reservation = db.get(ProviderExposureReservation, run.reservation_id)
        assert reservation is not None and reservation.state == "held"
        assert server.posts == 1


@pytest.mark.retained_execution
@pytest.mark.usefixtures("retained_execution_engine")
@pytest.mark.parametrize("provider", ["meta_ads", "tiktok_ads"])
@pytest.mark.parametrize("change", ["cancel", "disconnect", "reconnect"])
def test_authority_change_after_claim_prevents_provider_call(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    encoded: Any,
    provider: str,
    change: str,
) -> None:
    server = SocialServer(provider)
    with Session(customer_engine) as db:
        wid, run_id, actor, store, runtime, native = ready(
            db,
            configuration,
            tmp_path,
            provider,
            encoded() if provider == "tiktok_ads" else None,
            server,
        )
        claim = c.claim_creation_step(db, wid, run_id, actor, store, runtime, lambda: NOW)
        assert claim is not None
        if change == "cancel":
            c.cancel_creation(db, wid, run_id, actor, lambda: NOW)
        elif change == "disconnect":
            db.delete(native)
            db.commit()
        else:
            native.generation += 1
            db.commit()
        with pytest.raises(HTTPException):
            c.execute_claim(db, claim, actor, store, runtime, lambda: NOW)
        db.rollback()
        assert server.posts == 0
        attempt = db.get(ProviderExecutionAttempt, claim.attempt_id)
        assert attempt is not None and attempt.fence == claim.request.fence
        run = db.get(ProviderExecutionRun, run_id)
        assert run is not None
        reservation = db.get(ProviderExposureReservation, run.reservation_id)
        assert reservation is not None and reservation.state == "held"


def test_real_media_reader_rejects_foreign_scope_and_changed_review(
    customer_engine: Engine, configuration: Settings, tmp_path: Path
) -> None:
    with Session(customer_engine) as db:
        policy, actor = setup(db, configuration, tmp_path)
        store = LocalMediaStore(tmp_path)
        media = source.upload(db, policy.workspace_id, actor, png(), store, NOW)
        reader = ScopedProviderMediaReader(db, store)
        binding = reader.binding(policy.workspace_id, media.id)
        assert reader.read_verified(policy.workspace_id, binding) == png()
        with pytest.raises(ValueError):
            reader.read_verified(policy.workspace_id + 999, binding)
        with pytest.raises(ValueError):
            reader.read_verified(
                policy.workspace_id, binding.model_copy(update={"validation_digest": "f" * 64})
            )
