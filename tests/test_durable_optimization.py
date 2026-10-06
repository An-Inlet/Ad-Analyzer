from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from app.ads.enums import AdvertisingPlatform
from app.ads.models import AdvertisingAccount
from app.executors.google_optimization import GoogleOptimizationTransport
from app.executors.meta_optimization import MetaOptimizationTransport
from app.executors.tiktok_optimization import TikTokOptimizationTransport
from app.mandates.schemas import AccountScope
from app.meta.models import MetaConnection
from app.publication import coordinator as c
from app.publication import execution_mandates as mandates
from app.publication import optimization as o
from app.publication.execution_contracts import (
    ExecutionAccount,
    ExposureEvidence,
    ProviderMandateBinding,
    ProviderMandatePolicy,
)
from app.publication.execution_models import ProviderExposureReservation
from app.publication.optimization_contracts import (
    GoogleBudgetSetV1,
    GoogleStatusSetV1,
    MetaBudgetSetV1,
    MetaStatusSetV1,
    MoneyContext,
    OptimizationAction,
    OptimizationContext,
    OptimizationIntent,
    OptimizationState,
    OptimizationTarget,
    OptimizationTransport,
    TikTokBudgetSetV1,
    TikTokStatusSetV1,
)
from app.publication.optimization_execution_contracts import (
    OptimizationQualification,
    OptimizationRuntime,
)
from app.settings import Settings
from app.sources.models import SourceConnection
from app.workspaces.models import WorkspaceIntegration
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_google_optimization_http import Server as GoogleServer
from tests.test_provider_execution_mandates import setup
from tests.test_shopify_sales import configuration as configuration
from tests.test_social_optimization_http import Server


def ready(  # type: ignore[no-untyped-def]
    db: Session,
    config: Settings,
    path: Path,
    provider: str,
    kind: str = "budget",
    *,
    goal_budget_micros: int = 50_000_000,
    campaign: bool = False,
):
    old, actor = setup(db, config, path, goal_budget_micros=goal_budget_micros)
    wid = old.workspace_id
    if provider != "google_ads":
        integration = WorkspaceIntegration(
            workspace_id=wid,
            integration_key="optimization-test",
            provider=provider,
            display_name="Offline",
            status="active",
            configuration={},
        )
        db.add(integration)
        db.flush()
        account = AdvertisingAccount(
            workspace_id=wid,
            connection_id=integration.id,
            platform=AdvertisingPlatform(provider),
            external_account_id="123",
            name="Offline",
            currency_code="USD",
            time_zone="UTC",
        )
        db.add(account)
        db.flush()
        native: MetaConnection | SourceConnection
        if provider == "meta_ads":
            native = MetaConnection(
                workspace_id=wid,
                workspace_integration_id=integration.id,
                account_id=account.id,
                external_account_id="123",
                encrypted_credentials="never-opened-offline",
            )
        else:
            native = SourceConnection(
                id=uuid4().hex,
                workspace_id=wid,
                integration_id=integration.id,
                account_id=account.id,
                provider=provider,
                external_id="123",
                status="connected",
                generation=1,
                window_start=NOW.date(),
                window_end=NOW.date(),
                staged={},
            )
        db.add(native)
        db.flush()
        scope = ExecutionAccount(
            workspace_id=wid,
            account=AccountScope(
                platform=provider, connection_id=integration.id, account_id=account.id
            ),
            external_advertiser_id="123",
            connection_version=f"{provider.removesuffix('_ads')}:{native.id}:{native.generation}",
        )
    else:
        scope = old.accounts[0]
    server = GoogleServer() if provider == "google_ads" else Server(provider)
    if campaign and isinstance(server, Server) and provider == "meta_ads":
        server.meta_campaign["daily_budget"] = "5000"
    adapter: OptimizationTransport
    if provider == "google_ads":
        adapter = GoogleOptimizationTransport(transport=httpx.MockTransport(server))
    elif provider == "meta_ads":
        adapter = MetaOptimizationTransport(transport=httpx.MockTransport(server))
    else:
        adapter = TikTokOptimizationTransport(transport=httpx.MockTransport(server))
    money = MoneyContext(
        currency="USD",
        currency_exponent=2,
        account_timezone="UTC",
        period_start=old.starts_at,
        period_end=old.ends_at,
    )
    target = OptimizationTarget(
        kind="campaign"
        if provider == "google_ads" or campaign
        else ("adset" if provider == "meta_ads" else "adgroup"),
        external_id="5" if provider == "google_ads" or campaign else "6",
        campaign_id="5",
    )

    def context(scope: ExecutionAccount) -> OptimizationContext:
        return OptimizationContext(
            scope=scope,
            access_token=SecretStr("offline-token"),
            expires_at=NOW + timedelta(hours=1),
        )

    before = adapter.read_current(scope, target, money, "e" * 32, 1, context(scope), NOW)
    policy = ProviderMandatePolicy.model_validate(
        old.model_copy(
            update={
                "accounts": [scope],
                "allowed_purposes": ["existing_campaign_optimize"],
                "allowed_target_set_digest": before.budget_owner.target_set_digest(),
                "total_cap_micros": 100_000_000,
                "per_plan_cap_micros": 80_000_000,
                "positive_change_cap_micros": 20_000_000,
            }
        ).model_dump(mode="json")
    )
    db.commit()
    row = mandates.revise(db, wid, policy, actor, lambda: NOW)
    binding = mandates.consent(db, wid, row.id, row.revision, policy.digest(), actor, lambda: NOW)
    action: OptimizationAction
    if provider == "google_ads":
        action = (
            GoogleBudgetSetV1(amount_micros=45_000_000)
            if kind == "budget"
            else GoogleStatusSetV1(status="PAUSED")
        )
    elif provider == "meta_ads":
        action = (
            MetaBudgetSetV1(budget_field="daily_budget", amount_micros=45_000_000)
            if kind == "budget"
            else MetaStatusSetV1(status="PAUSED")
        )
    else:
        action = (
            TikTokBudgetSetV1(budget_mode="BUDGET_MODE_DAY", amount_micros=45_000_000)
            if kind == "budget"
            else TikTokStatusSetV1(operation_status="DISABLE")
        )

    def qualify(
        db: Session,
        binding: ProviderMandateBinding,
        scope: ExecutionAccount,
        target: OptimizationTarget,
        now: datetime,
    ) -> OptimizationQualification:
        return OptimizationQualification(
            environment="contract_test",
            scope=scope,
            target=target,
            money=money,
            qualification_id="e" * 32,
            qualification_revision=1,
            profile="controlled_contract_profile",
            allowed_operations=[action.kind],
            observed_at=now,
            expires_at=now + timedelta(minutes=2),
            evidence_digest="f" * 64,
            unresolved=[],
        )

    def exposure(
        db: Session,
        intent: OptimizationIntent,
        state: OptimizationState,
        qualification: OptimizationQualification,
        now: datetime,
    ) -> ExposureEvidence:
        held = int(
            db.scalar(
                select(func.coalesce(func.sum(ProviderExposureReservation.amount_micros), 0)).where(
                    ProviderExposureReservation.workspace_id == wid,
                    ProviderExposureReservation.environment == "contract_test",
                    ProviderExposureReservation.state == "held",
                )
            )
            or 0
        )
        return ExposureEvidence(
            environment="contract_test",
            mandate=intent.mandate,
            account=scope,
            covered_account_ids=[scope.account.account_id],
            budget_owner_key=intent.budget_owner.key(scope),
            target_set_digest=intent.approved_target_set_digest,
            state_digest=state.digest(),
            currency="USD",
            period_start=policy.starts_at,
            period_end=policy.ends_at,
            observed_at=now,
            expires_at=now + timedelta(minutes=2),
            reporting_watermark=now,
            completeness="complete",
            qualification_id=qualification.qualification_id,
            model_version="controlled_contract_scenario",
            cap_semantics="contract_scenario",
            reported_spend_micros=0,
            unreported_upper_micros=0,
            unchanged_future_upper_micros=0,
            proposed_owner_upper_micros=40_000_000,
            existing_reservations_micros=held,
            portfolio_upper_micros=held + 40_000_000,
        )

    runtime = OptimizationRuntime(
        environment="contract_test",
        qualification_reader=qualify,
        exposure_reader=exposure,
        context=context,
        google=adapter if provider == "google_ads" else None,
        meta=adapter if provider == "meta_ads" else None,
        tiktok=adapter if provider == "tiktok_ads" else None,
    )
    return wid, actor, binding, scope, target, action, runtime, server


@pytest.mark.parametrize("provider", ["google_ads", "meta_ads", "tiktok_ads"])
@pytest.mark.parametrize("kind", ["budget", "pause"])
def test_actual_persisted_exact_optimization_and_owned_receipt(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    provider: str,
    kind: str,
) -> None:
    with Session(customer_engine) as db:
        wid, actor, binding, scope, target, action, runtime, server = ready(
            db, configuration, tmp_path, provider, kind
        )
        row = o.prepare_optimization(
            db, wid, binding, scope, target, action, "a" * 64, actor, runtime, lambda: NOW
        )
        with pytest.raises(HTTPException, match="exact optimization approval"):
            o.create_run(db, wid, row.id, actor, runtime, lambda: NOW)
        db.rollback()
        o.approve_optimization(
            db, wid, row.id, row.digest, row.plan_digest, actor, runtime, lambda: NOW
        )
        run = o.create_run(db, wid, row.id, actor, runtime, lambda: NOW)
        claim = o.claim_step(db, wid, run.id, actor, runtime, lambda: NOW)
        assert claim is not None
        receipt = o.execute_claim(db, claim, actor, runtime, lambda: NOW)
        assert (
            receipt.outcome == "verified_target_state"
            and len(server.writes if provider == "google_ads" else server.posts) == 1
        )
        assert o.claim_step(db, wid, run.id, actor, runtime, lambda: NOW) is None
        with pytest.raises(HTTPException, match="claim unavailable"):
            o.execute_claim(db, claim, actor, runtime, lambda: NOW)
        db.rollback()
        projection = c.read_owned_outcome_receipt(db, wid, claim.attempt_id, actor)
        assert projection is not None and projection.purpose == "existing_campaign_optimize"
        assert (
            projection.effective_time_evidence == "unavailable"
            and projection.source_draft_id is None
        )
        reservation = db.get(ProviderExposureReservation, run.reservation_id)
        assert reservation is not None and reservation.state == "held"
        assert len(server.writes if provider == "google_ads" else server.posts) == 1


@pytest.mark.parametrize("provider", ["google_ads", "meta_ads", "tiktok_ads"])
def test_unknown_reconciles_original_without_new_attempt(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    provider: str,
) -> None:
    with Session(customer_engine) as db:
        wid, actor, binding, scope, target, action, runtime, server = ready(
            db, configuration, tmp_path, provider
        )
        row = o.prepare_optimization(
            db, wid, binding, scope, target, action, "a" * 64, actor, runtime, lambda: NOW
        )
        o.approve_optimization(
            db, wid, row.id, row.digest, row.plan_digest, actor, runtime, lambda: NOW
        )
        run = o.create_run(db, wid, row.id, actor, runtime, lambda: NOW)
        claim = o.claim_step(db, wid, run.id, actor, runtime, lambda: NOW)
        assert claim is not None
        server.ignore = server.timeout = True
        assert o.execute_claim(db, claim, actor, runtime, lambda: NOW).outcome == "unknown"
        assert o.claim_step(db, wid, run.id, actor, runtime, lambda: NOW) is None
        assert (
            o.reconcile_attempt(db, wid, claim.attempt_id, runtime, lambda: NOW).outcome
            == "unknown"
        )
        if provider == "google_ads":
            server.budget["amountMicros"] = "45000000"
        elif provider == "meta_ads":
            server.meta_child["daily_budget"] = "4500"
        else:
            server.tk_child["budget"] = 45
        latest = o.reconcile_attempt(
            db, wid, claim.attempt_id, runtime, lambda: NOW + timedelta(seconds=1)
        )
        assert latest.outcome == "verified_target_state" and latest.fence == claim.request.fence
        assert len(server.writes if provider == "google_ads" else server.posts) == 1


@pytest.mark.parametrize("change", ["cancel", "generation", "state", "expiry", "foreign"])
def test_current_authority_and_preconditions_rechecked_after_claim(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    change: str,
) -> None:
    with Session(customer_engine) as db:
        wid, actor, binding, scope, target, action, runtime, server = ready(
            db, configuration, tmp_path, "meta_ads"
        )
        row = o.prepare_optimization(
            db, wid, binding, scope, target, action, "a" * 64, actor, runtime, lambda: NOW
        )
        o.approve_optimization(
            db, wid, row.id, row.digest, row.plan_digest, actor, runtime, lambda: NOW
        )
        run = o.create_run(db, wid, row.id, actor, runtime, lambda: NOW)
        claim = o.claim_step(db, wid, run.id, actor, runtime, lambda: NOW)
        assert claim is not None
        now = NOW
        if change == "cancel":
            c.cancel_creation(db, wid, run.id, actor, lambda: NOW)
        elif change == "generation":
            native = db.scalar(select(MetaConnection).where(MetaConnection.workspace_id == wid))
            assert native is not None
            native.generation += 1
            db.commit()
        elif change == "state":
            server.meta_child["daily_budget"] = "7000"
        elif change == "expiry":
            now += timedelta(minutes=3)
        else:
            claim = claim.model_copy(update={"workspace_id": wid + 100})
        with pytest.raises(HTTPException):
            o.execute_claim(db, claim, actor, runtime, lambda: now)
        assert server.posts == []


def test_cancel_in_reservation_commit_gap_blocks_original_attempt(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.publication.execution_models import ProviderExecutionAttempt

    with Session(customer_engine) as db:
        wid, actor, binding, scope, target, action, runtime, server = ready(
            db, configuration, tmp_path, "meta_ads"
        )
        row = o.prepare_optimization(
            db, wid, binding, scope, target, action, "a" * 64, actor, runtime, lambda: NOW
        )
        o.approve_optimization(
            db, wid, row.id, row.digest, row.plan_digest, actor, runtime, lambda: NOW
        )
        run = o.create_run(db, wid, row.id, actor, runtime, lambda: NOW)
        commit = db.commit
        once = False

        def cancel() -> None:
            nonlocal once
            commit()
            if not once:
                once = True
                with Session(customer_engine) as other:
                    c.cancel_creation(other, wid, run.id, actor, lambda: NOW)

        monkeypatch.setattr(db, "commit", cancel)
        with pytest.raises(HTTPException, match="canceled"):
            o.claim_step(db, wid, run.id, actor, runtime, lambda: NOW)
        assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 0
        assert server.posts == []


def test_aggressiveness_is_not_permission_to_increase_total_cap(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
) -> None:
    with Session(customer_engine) as db:
        wid, actor, binding, scope, target, action, runtime, _ = ready(
            db, configuration, tmp_path, "meta_ads"
        )
        # Existing budget50, proposed55 is10%, but policy permits5%; total cap remains100.
        action = action.model_copy(update={"amount_micros": 55_000_000})
        with pytest.raises(HTTPException, match="aggressiveness"):
            o.prepare_optimization(
                db, wid, binding, scope, target, action, "a" * 64, actor, runtime, lambda: NOW
            )


def test_current_same_budget_owner_hold_cannot_be_replaced_after_verified_state(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
) -> None:
    with Session(customer_engine) as db:
        wid, actor, binding, scope, target, action, runtime, server = ready(
            db, configuration, tmp_path, "meta_ads"
        )
        row = o.prepare_optimization(
            db, wid, binding, scope, target, action, "a" * 64, actor, runtime, lambda: NOW
        )
        o.approve_optimization(
            db, wid, row.id, row.digest, row.plan_digest, actor, runtime, lambda: NOW
        )
        run = o.create_run(db, wid, row.id, actor, runtime, lambda: NOW)
        claim = o.claim_step(db, wid, run.id, actor, runtime, lambda: NOW)
        assert claim is not None
        o.execute_claim(db, claim, actor, runtime, lambda: NOW)
        next_action = action.model_copy(update={"amount_micros": 44_000_000})
        row2 = o.prepare_optimization(
            db, wid, binding, scope, target, next_action, "b" * 64, actor, runtime, lambda: NOW
        )
        o.approve_optimization(
            db, wid, row2.id, row2.digest, row2.plan_digest, actor, runtime, lambda: NOW
        )
        run2 = o.create_run(db, wid, row2.id, actor, runtime, lambda: NOW)
        with pytest.raises(HTTPException, match="retained exposure"):
            o.claim_step(db, wid, run2.id, actor, runtime, lambda: NOW)
        assert len(server.posts) == 1


def test_positive_change_counter_survives_canceled_admission_settlement_and_policy_revision(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.publication import settlement

    with Session(customer_engine) as db:
        wid, actor, binding, scope, target, action, runtime, _ = ready(
            db, configuration, tmp_path, "meta_ads"
        )
        _, mandate = mandates.owned(db, wid, binding.mandate_id)
        policy = mandates.policy(db, mandate).model_copy(
            update={"positive_change_cap_micros": 3_000_000}
        )
        row = mandates.revise(
            db,
            wid,
            policy,
            actor,
            lambda: NOW,
            mandate_id=mandate.id,
            expected_revision=mandate.revision,
        )
        binding = mandates.consent(
            db, wid, row.id, row.revision, policy.digest(), actor, lambda: NOW
        )
        action = action.model_copy(update={"amount_micros": 52_000_000})
        review = o.prepare_optimization(
            db, wid, binding, scope, target, action, "a" * 64, actor, runtime, lambda: NOW
        )
        o.approve_optimization(
            db, wid, review.id, review.digest, review.plan_digest, actor, runtime, lambda: NOW
        )
        run = o.create_run(db, wid, review.id, actor, runtime, lambda: NOW)
        commit = db.commit
        once = False

        def cancel() -> None:
            nonlocal once
            commit()
            if not once:
                once = True
                with Session(customer_engine) as other:
                    c.cancel_creation(other, wid, run.id, actor, lambda: NOW)

        monkeypatch.setattr(db, "commit", cancel)
        with pytest.raises(HTTPException, match="canceled"):
            o.claim_step(db, wid, run.id, actor, runtime, lambda: NOW)
        db.rollback()
        db.refresh(run)
        assert run.reservation_id is not None
        settlement.settle_unemitted(db, wid, run.reservation_id, actor, lambda: NOW)
        assert o.positive_changes_used(db, wid, binding.ledger_id) == 2_000_000
        _, mandate = mandates.owned(db, wid, binding.mandate_id)
        next_policy = policy.model_copy(update={"aggressiveness_percent": 10})
        revised = mandates.revise(
            db,
            wid,
            next_policy,
            actor,
            lambda: NOW,
            mandate_id=mandate.id,
            expected_revision=mandate.revision,
        )
        next_binding = mandates.consent(
            db, wid, revised.id, revised.revision, next_policy.digest(), actor, lambda: NOW
        )
        review2 = o.prepare_optimization(
            db, wid, next_binding, scope, target, action, "b" * 64, actor, runtime, lambda: NOW
        )
        o.approve_optimization(
            db, wid, review2.id, review2.digest, review2.plan_digest, actor, runtime, lambda: NOW
        )
        run2 = o.create_run(db, wid, review2.id, actor, runtime, lambda: NOW)
        with pytest.raises(HTTPException, match="cumulative"):
            o.claim_step(db, wid, run2.id, actor, runtime, lambda: NOW)
