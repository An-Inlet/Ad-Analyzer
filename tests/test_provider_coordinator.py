import json
from datetime import timedelta
from typing import Any

import httpx
import pytest
from app.campaign_review.models import CampaignDraft
from app.campaign_review.storage import LocalMediaStore
from app.executors.google_publication import GooglePublicationHTTP
from app.executors.meta_publication import MetaPublicationTransport
from app.executors.tiktok_publication import TikTokPublicationTransport
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
from app.publication.provider_contracts import (
    ProviderContext,
    ProviderPublishPlan,
    ProviderResponse,
)
from app.settings import Settings
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_provider_execution_mandates import setup
from tests.test_provider_qualification import prepare
from tests.test_shopify_sales import configuration as configuration
from tests.test_social_publication_http import Media


class GoogleServer:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}
        self.posts = 0
        self.timeout = False
        self.absent = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if request.url.path.endswith("googleAds:search"):
            query = body["query"]
            table = query.split(" FROM ")[1].split()[0]
            key = table.split("_")[0] + "".join(p.title() for p in table.split("_")[1:])
            name = query.split("resource_name = '")[1].split("'")[0]
            row = self.rows.get(name)
            return httpx.Response(
                200, json={"results": [] if row is None or self.absent else [{key: row}]}
            )
        if body.get("validateOnly"):
            return httpx.Response(200, json={})
        self.posts += 1
        operation = body["operations"][0]
        row = dict(operation.get("create", operation.get("update", {})))
        collection = request.url.path.split("/")[-1].split(":")[0]
        suffix = str(self.posts)
        if collection in {"campaignCriteria", "adGroupCriteria", "adGroupAds"}:
            parent = row.get("campaign", row.get("adGroup"))
            assert isinstance(parent, str)
            suffix = parent.rsplit("/", 1)[1] + "~" + suffix
        resource = row.get("resourceName", f"customers/1234567890/{collection}/{suffix}")
        row["resourceName"] = resource
        if "manualCpc" in row:
            row.pop("manualCpc")
            row["biddingStrategyType"] = "MANUAL_CPC"
        self.rows[resource] = row
        if self.timeout:
            raise httpx.ReadTimeout("simulated lost response after provider effect")
        return httpx.Response(200, json={"results": [{"resourceName": resource}]})


def ready(
    db: Session, config: Settings, path: Any, server: GoogleServer, *, total_budget: bool = False
) -> tuple[int, str, str, LocalMediaStore, CreationRuntime]:
    policy, actor = setup(db, config, path, total_budget=total_budget)
    wid = policy.workspace_id
    draft = db.scalar(select(CampaignDraft).where(CampaignDraft.workspace_id == wid))
    assert draft is not None
    store = LocalMediaStore(path)
    reviewed = prepare(db, wid, draft.id, actor, store, total_budget=total_budget)
    plan = ProviderPublishPlan.model_validate(reviewed.plan)
    mandate = mandates.revise(db, wid, policy, actor, lambda: NOW)
    binding = mandates.consent(db, wid, mandate.id, 1, policy.digest(), actor, lambda: NOW)

    def qualify(plan: CreationPlan, now: Any) -> ConfigurationQualification:
        assert isinstance(plan, ProviderPublishPlan) and plan.review.qualification is not None
        proof = plan.review.qualification  # actual Google read qualifier used by prepare()
        return ConfigurationQualification(
            environment="contract_test",
            account=ExecutionAccount.from_publication(plan.review.scope),
            plan_digest=plan.digest(),
            api_version=plan.api_version,
            observed_at=proof.observed_at,
            expires_at=proof.expires_at,
            evidence_digest=proof.evidence_digest,
            checks_version=proof.checks,
            unresolved=[],
        )

    def exposure(
        session: Session, b: ProviderMandateBinding, plan: CreationPlan, now: Any
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
        return ExposureEvidence(
            environment="contract_test",
            mandate=b,
            account=ExecutionAccount.from_publication(plan.review.scope),
            covered_account_ids=[policy.accounts[0].account.account_id],
            budget_owner_key="new/google/" + plan.digest(),
            target_set_digest=plan.digest(),
            state_digest=plan.digest(),
            currency=policy.currency,
            period_start=policy.starts_at,
            period_end=policy.ends_at,
            observed_at=now,
            expires_at=now + timedelta(minutes=5),
            reporting_watermark=now,
            completeness="complete",
            qualification_id="f" * 32,
            model_version="controlled_contract_scenario_v1",
            cap_semantics="contract_scenario",
            reported_spend_micros=0,
            unreported_upper_micros=0,
            unchanged_future_upper_micros=0,
            proposed_owner_upper_micros=40,
            existing_reservations_micros=int(held),
            portfolio_upper_micros=int(held) + 40,
        )

    def unused(_: httpx.Request) -> httpx.Response:
        raise AssertionError("unexpected social provider access")

    runtime = CreationRuntime(
        environment="contract_test",
        qualification_reader=qualify,
        exposure_reader=exposure,
        google=GooglePublicationHTTP(transport=httpx.MockTransport(server)),
        meta=MetaPublicationTransport(Media(), transport=httpx.MockTransport(unused)),
        tiktok=TikTokPublicationTransport(Media(), transport=httpx.MockTransport(unused)),
        google_context=lambda request: ProviderContext(
            scope=request.scope,
            login_customer_id=request.login_customer_id,
            access_token=SecretStr("mock-only"),
            expires_at=NOW + timedelta(hours=1),
        ),
        social_context=lambda _: (_ for _ in ()).throw(AssertionError("unexpected social context")),
    )
    row = c.prepare_creation(db, wid, plan, binding, actor, store, runtime, lambda: NOW)
    c.approve_creation(
        db, wid, row.id, row.digest, row.plan_digest, actor, store, runtime, lambda: NOW
    )
    run = c.create_run(db, wid, row.id, actor, store, runtime, lambda: NOW)
    return wid, run.id, actor, store, runtime


@pytest.mark.parametrize("total_budget", [False, True])
def test_actual_google_full_durable_creation_and_owned_projection(
    customer_engine: Engine, configuration: Settings, tmp_path: Any, total_budget: bool
) -> None:
    server = GoogleServer()
    with Session(customer_engine) as db:
        wid, run_id, actor, store, runtime = ready(
            db, configuration, tmp_path, server, total_budget=total_budget
        )
        count = 0
        while claim := c.claim_creation_step(db, wid, run_id, actor, store, runtime, lambda: NOW):
            receipt = c.execute_claim(db, claim, actor, store, runtime, lambda: NOW)
            assert receipt.outcome == "verified_effect"
            projection = c.read_owned_outcome_receipt(db, wid, claim.attempt_id, actor)
            assert projection is not None and projection.environment == "contract_test"
            assert projection.purpose == "create_paused" and projection.effective_upper is None
            assert projection.fence == claim.request.fence
            with pytest.raises(HTTPException):
                c.execute_claim(db, claim, actor, store, runtime, lambda: NOW)
            db.rollback()
            count += 1
        assert count >= 7 and server.posts == count
        run = db.get(ProviderExecutionRun, run_id)
        assert run is not None and run.state == "created_paused"
        reservation = db.get(ProviderExposureReservation, run.reservation_id)
        assert (
            reservation is not None
            and reservation.state == "held"
            and reservation.amount_micros == 40
        )
        with pytest.raises(HTTPException):
            c.read_owned_outcome_receipt(
                db, wid + 999, claim.attempt_id if claim else "0" * 32, actor
            )


@pytest.mark.parametrize("total_budget", [False, True])
def test_unknown_keeps_original_attempt_and_late_response_reconciles_without_replay(
    customer_engine: Engine, configuration: Settings, tmp_path: Any, total_budget: bool
) -> None:
    server = GoogleServer()
    server.timeout = True
    with Session(customer_engine) as db:
        wid, run_id, actor, store, runtime = ready(
            db, configuration, tmp_path, server, total_budget=total_budget
        )
        claim = c.claim_creation_step(db, wid, run_id, actor, store, runtime, lambda: NOW)
        assert claim is not None
        assert c.execute_claim(db, claim, actor, store, runtime, lambda: NOW).outcome == "unknown"
        assert (
            c.reconcile_attempt(db, wid, claim.attempt_id, runtime, lambda: NOW).outcome
            == "unknown"
        )
        assert c.claim_creation_step(db, wid, run_id, actor, store, runtime, lambda: NOW) is None
        assert server.posts == 1
        assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 1
        # Original worker's recovered acknowledgement is bound to the original immutable request.
        c.record_response(
            db,
            wid,
            claim.attempt_id,
            ProviderResponse(
                request_digest=claim.request.digest(),
                outcome="acknowledged",
                resource_name=next(iter(server.rows)),
            ),
            lambda: NOW,
        )
        receipt = c.reconcile_attempt(db, wid, claim.attempt_id, runtime, lambda: NOW)
        assert receipt.outcome == "verified_effect" and server.posts == 1
        latest = c.read_owned_outcome_receipt(db, wid, claim.attempt_id, actor)
        assert (
            latest is not None and latest.sequence == 2 and latest.supersedes_receipt_id is not None
        )
        # A later absence supersedes success as unknown; it cannot authorize a replacement.
        server.absent = True
        c.reconcile_attempt(db, wid, claim.attempt_id, runtime, lambda: NOW + timedelta(seconds=1))
        latest = c.read_owned_outcome_receipt(db, wid, claim.attempt_id, actor)
        assert latest is not None and latest.outcome == "unknown" and latest.sequence == 3
        assert (
            c.claim_creation_step(
                db, wid, run_id, actor, store, runtime, lambda: NOW + timedelta(seconds=1)
            )
            is None
        )
        assert server.posts == 1


def test_cancel_after_parent_reservation_commit_prevents_first_attempt(
    customer_engine: Engine, configuration: Settings, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    server = GoogleServer()
    with Session(customer_engine) as db:
        wid, run_id, actor, store, runtime = ready(db, configuration, tmp_path, server)
        original_commit = db.commit
        canceled = False

        def commit() -> None:
            nonlocal canceled
            original_commit()
            if not canceled:
                canceled = True
                with Session(customer_engine) as other:
                    c.cancel_creation(other, wid, run_id, actor, lambda: NOW)

        monkeypatch.setattr(db, "commit", commit)
        with pytest.raises(HTTPException, match="canceled"):
            c.claim_creation_step(db, wid, run_id, actor, store, runtime, lambda: NOW)
        db.rollback()
        assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 0
        assert server.posts == 0


@pytest.mark.parametrize("change", ["generation", "owner", "master", "ledger"])
def test_claim_rechecks_current_authority_and_reservations(
    customer_engine: Engine, configuration: Settings, tmp_path: Any, change: str
) -> None:
    from uuid import uuid4

    from app.automation.models import PlatformAutomationControl
    from app.customers.models import CustomerMembership
    from app.google_connections.models import GoogleCustomerConnection
    from app.publication.execution_models import ProviderPeriodLedger

    server = GoogleServer()
    with Session(customer_engine) as db:
        wid, run_id, actor, store, runtime = ready(db, configuration, tmp_path, server)
        if change == "generation":
            native = db.scalar(
                select(GoogleCustomerConnection).where(GoogleCustomerConnection.workspace_id == wid)
            )
            assert native is not None
            native.generation += 1
        elif change == "owner":
            member = db.get(CustomerMembership, (actor, wid))
            assert member is not None
            member.status = "suspended"
        elif change == "master":
            db.add(
                PlatformAutomationControl(
                    key="all_data_syncs", enabled=False, updated_by="operator"
                )
            )
        else:
            ledger = db.scalar(
                select(ProviderPeriodLedger).where(ProviderPeriodLedger.workspace_id == wid)
            )
            assert ledger is not None
            db.add(
                ProviderExposureReservation(
                    id=uuid4().hex,
                    workspace_id=wid,
                    ledger_id=ledger.id,
                    environment="contract_test",
                    budget_owner_key="other-budget-owner",
                    amount_micros=1,
                    state="held",
                    evidence={},
                )
            )
        db.commit()
        with pytest.raises(HTTPException):
            c.claim_creation_step(db, wid, run_id, actor, store, runtime, lambda: NOW)
        db.rollback()
        assert server.posts == 0
        assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 0


def test_owned_projection_and_future_foreign_receipts_fail_closed(
    customer_engine: Engine, configuration: Settings, tmp_path: Any
) -> None:
    server = GoogleServer()
    with Session(customer_engine) as db:
        wid, run_id, actor, store, runtime = ready(db, configuration, tmp_path, server)
        claim = c.claim_creation_step(db, wid, run_id, actor, store, runtime, lambda: NOW)
        assert claim is not None
        receipt = c.execute_claim(db, claim, actor, store, runtime, lambda: NOW)
        for changed in [
            receipt.model_copy(update={"observed_at": NOW + timedelta(seconds=1)}),
            receipt.model_copy(update={"fence": "f" * 32}),
        ]:
            with pytest.raises(HTTPException):
                c.record_receipt(db, wid, claim.attempt_id, changed, lambda: NOW)
            db.rollback()
        with pytest.raises(HTTPException):
            c.read_owned_outcome_receipt(db, wid + 999, claim.attempt_id, actor)
        db.rollback()
        with pytest.raises(HTTPException):
            c.read_owned_outcome_receipt(db, wid, claim.attempt_id, "unknown")


def test_closure_preserves_original_receipt_reconciliation_without_new_claim(
    customer_engine: Engine, configuration: Settings, tmp_path: Any
) -> None:
    import time
    from uuid import uuid4

    from app.customers.access import CustomerPrincipal
    from app.customers.models import CustomerSession, CustomerUser
    from app.lifecycle.quiescing import quiesce

    from tests.test_customer_identity import FakeProvider
    from tests.test_customer_quiescing import confirmed

    server = GoogleServer()
    server.timeout = True
    with Session(customer_engine) as db:
        wid, run_id, actor, store, runtime = ready(db, configuration, tmp_path, server)
        claim = c.claim_creation_step(db, wid, run_id, actor, store, runtime, lambda: NOW)
        assert claim is not None
        c.execute_claim(db, claim, actor, store, runtime, lambda: NOW)
        user = db.get(CustomerUser, actor)
        assert user is not None
        user.issuer = FakeProvider.issuer
        session = CustomerSession(
            digest=uuid4().hex * 2,
            user_id=actor,
            csrf_digest="a" * 64,
            created_at=int(time.time()),
            expires_at=int(time.time()) + 3600,
            authenticated_at=int(time.time()),
        )
        db.add(session)
        db.commit()
        principal = CustomerPrincipal(user, session)
        request, digest = confirmed(db, principal, wid, NOW)
        quiesce(db, principal, FakeProvider(), wid, request, 1, digest, NOW)
        db.commit()
        with pytest.raises(HTTPException):
            c.claim_creation_step(db, wid, run_id, actor, store, runtime, lambda: NOW)
        db.rollback()
        c.record_response(
            db,
            wid,
            claim.attempt_id,
            ProviderResponse(
                request_digest=claim.request.digest(),
                resource_name=next(iter(server.rows)),
                outcome="acknowledged",
            ),
            lambda: NOW,
        )
        assert (
            c.reconcile_attempt(db, wid, claim.attempt_id, runtime, lambda: NOW).outcome
            == "verified_effect"
        )
        latest = c.read_owned_outcome_receipt(db, wid, claim.attempt_id, actor)
        assert latest is not None and latest.outcome == "verified_effect" and server.posts == 1
        run = db.get(ProviderExecutionRun, run_id)
        assert run is not None and run.state == "canceled" and run.canceled_at is not None
        reservation = db.get(ProviderExposureReservation, run.reservation_id)
        assert reservation is not None and reservation.state == "held"


def test_concurrent_claims_create_one_original_attempt(
    customer_engine: Engine, configuration: Settings, tmp_path: Any
) -> None:
    from concurrent.futures import ThreadPoolExecutor

    if customer_engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL independent worker locking")
    server = GoogleServer()
    with Session(customer_engine) as db:
        wid, run_id, actor, store, runtime = ready(db, configuration, tmp_path, server)

    def claim() -> Any:
        with Session(customer_engine) as db:
            return c.claim_creation_step(db, wid, run_id, actor, store, runtime, lambda: NOW)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: claim(), range(2)))
    assert sum(result is not None for result in results) == 1
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 1
    assert server.posts == 0


def test_conflicting_resource_cannot_replace_verified_original(
    customer_engine: Engine, configuration: Settings, tmp_path: Any
) -> None:
    server = GoogleServer()
    with Session(customer_engine) as db:
        wid, run_id, actor, store, runtime = ready(db, configuration, tmp_path, server)
        claim = c.claim_creation_step(db, wid, run_id, actor, store, runtime, lambda: NOW)
        assert claim is not None
        receipt = c.execute_claim(db, claim, actor, store, runtime, lambda: NOW)
        assert receipt.resource_name is not None
        conflicting = receipt.model_copy(
            update={"resource_name": receipt.resource_name.rsplit("/", 1)[0] + "/999"}
        )
        c.record_receipt(db, wid, claim.attempt_id, conflicting, lambda: NOW)
        latest = c.read_owned_outcome_receipt(db, wid, claim.attempt_id, actor)
        assert latest is not None and latest.outcome == "conflict" and latest.resource_name is None
        assert c.claim_creation_step(db, wid, run_id, actor, store, runtime, lambda: NOW) is None
        assert server.posts == 1


def test_default_live_gate_and_environment_cannot_be_promoted(
    customer_engine: Engine, configuration: Settings, tmp_path: Any
) -> None:
    from dataclasses import replace

    from app.publication.coordinator_contracts import get_creation_runtime

    assert get_creation_runtime() is None
    server = GoogleServer()
    with Session(customer_engine) as db:
        wid, run_id, actor, store, runtime = ready(db, configuration, tmp_path, server)
        changed = replace(runtime, environment="live", live_enabled=True)
        with pytest.raises(HTTPException, match="runtime"):
            c.claim_creation_step(db, wid, run_id, actor, store, changed, lambda: NOW)
        with pytest.raises(HTTPException, match="runtime"):
            c.gate(replace(runtime, environment="live"), "live")
        assert server.posts == 0
