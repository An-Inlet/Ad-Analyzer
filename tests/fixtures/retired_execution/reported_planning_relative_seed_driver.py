"""Relative coherent original: all synthetic dates chosen before the authentic effect."""

import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import app
import httpx
from app.ads.enums import AdvertisingPlatform
from app.ads.models import AdvertisingAccount, Campaign
from app.commerce.ledger import MEASUREMENT_SCOPES, bind_store
from app.commerce.reporting import MeasurementWindow
from app.commerce.sync import CommerceSyncService
from app.customers.models import CustomerMembership, CustomerSession, CustomerUser
from app.executors.meta_optimization import MetaOptimizationTransport
from app.goals import service as goals
from app.goals.models import Goal
from app.goals.schemas import ConfirmInput, GoalDefinition
from app.imports.native import bind_shopify
from app.mandates.schemas import AccountScope
from app.meta.models import MetaConnection
from app.publication import execution_mandates, optimization
from app.publication.execution_contracts import (
    ExecutionAccount,
    ExposureEvidence,
    ProviderMandateBinding,
    ProviderMandatePolicy,
)
from app.publication.execution_models import (
    ProviderExecutionMandate,
    ProviderExecutionReceipt,
    ProviderExposureReservation,
)
from app.publication.optimization_contracts import (
    MetaBudgetSetV1,
    MoneyContext,
    OptimizationContext,
    OptimizationIntent,
    OptimizationState,
    OptimizationTarget,
)
from app.publication.optimization_execution_contracts import (
    OptimizationQualification,
    OptimizationRuntime,
)
from app.settings import Settings
from app.shopify.models import ShopifyConnection
from app.shopify.security import Vault
from app.shopify.service import credentials
from app.workspaces.models import Workspace, WorkspaceIntegration
from pydantic import SecretStr
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import create_engine, event, func, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from tests.test_commerce_measurement import FakeMeasurement, agreement
from tests.test_customer_identity import FakeProvider
from tests.test_shopify_sales import configuration
from tests.test_social_optimization_http import Server


@dataclass(frozen=True)
class RelativePlanningTimeline:
    as_of: datetime
    effect_at: datetime
    baseline_start: date
    baseline_end: date
    order_at: datetime
    target_start: date
    target_end: date
    budget_start: date
    budget_end: date

    @classmethod
    def from_as_of(cls, value: datetime) -> "RelativePlanningTimeline":
        assert value.tzinfo is not None and value.utcoffset() == timedelta(0)
        effect = datetime.combine(value.date() - timedelta(days=15), datetime.min.time(), UTC)
        effect += timedelta(hours=12)
        baseline_end = effect.date().replace(day=1)
        baseline_start = (baseline_end - timedelta(days=1)).replace(day=1)
        target_start = (value.date().replace(day=28) + timedelta(days=4)).replace(day=1)
        target_end = (target_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        return cls(
            value,
            effect,
            baseline_start,
            baseline_end,
            datetime.combine(baseline_start.replace(day=10), datetime.min.time(), UTC)
            + timedelta(hours=12),
            target_start,
            target_end,
            baseline_end,
            target_end,
        )


def coherent_original(
    db: Session, config: Settings, timeline: RelativePlanningTimeline
) -> tuple[Any, ...]:
    config.shopify_measurement_enabled = True
    workspace = Workspace(
        slug="relative-original", name="Offline", client_name="Offline", status="active"
    )
    db.add(workspace)
    db.flush()
    shop = "relative-original.myshopify.com"
    bundle = credentials(
        {
            "access_token": "offline-access-token",
            "refresh_token": "offline-refresh-token",
            "expires_in": 3600,
            "scope": ",".join(sorted(MEASUREMENT_SCOPES)),
        },
        timeline.effect_at,
    )
    connection = ShopifyConnection(
        workspace_id=workspace.id,
        shop_domain=shop,
        shop_name="Offline",
        currency_code="USD",
        time_zone="UTC",
        connected_at=timeline.effect_at,
        encrypted_credentials=Vault(config).seal(workspace.id, shop, bundle),
    )
    db.add(connection)
    db.flush()
    bind_shopify(db, connection)
    store = bind_store(db, connection, "gid://shopify/Shop/123", config, timeline.effect_at)
    db.commit()
    order = {
        "id": "gid://shopify/Order/1",
        "createdAt": timeline.order_at.isoformat(),
        "updatedAt": timeline.order_at.isoformat(),
        "test": False,
        "customer": {"id": "gid://shopify/Customer/100"},
    }
    client = FakeMeasurement(config, [([order], None)])
    client.facts = [agreement(when=timeline.order_at)]
    imported = CommerceSyncService(db, config, client).page(workspace.id, now=timeline.effect_at)
    assert imported == {"status": "complete", "imported": 1}, imported
    assert client.requests and store.last_sync_at is not None and store.covered_from is not None
    wid, actor = connection.workspace_id, uuid4().hex
    db.add(
        CustomerUser(
            id=actor, issuer=FakeProvider.issuer, subject=actor, email="mock@example.invalid"
        )
    )
    db.flush()
    db.add(CustomerMembership(user_id=actor, workspace_id=wid, role="owner"))
    goal = Goal(id=uuid4().hex, workspace_id=wid, revision=0)
    db.add(goal)
    db.flush()
    value = GoalDefinition(
        metric="shopify_merchandise_net_sales_v1",
        store_id=store.id,
        target_micros=100_000_000,
        target_window=MeasurementWindow(
            start=timeline.target_start,
            end=timeline.target_end,
            time_basis="calendar_month",
            currency="USD",
            time_zone="UTC",
        ),
        baseline_window=MeasurementWindow(
            start=timeline.baseline_start,
            end=timeline.baseline_end,
            time_basis="calendar_month",
            currency="USD",
            time_zone="UTC",
        ),
        deadline=timeline.target_end - timedelta(days=1),
        budget_micros=50_000_000,
        budget_start=timeline.budget_start,
        budget_end=timeline.budget_end,
        aggressiveness="balanced",
    )
    goals.revise(db, goal, value, actor, timeline.effect_at)
    preview = goals.preview(db, goal, timeline.effect_at)
    goals.confirm(
        db,
        goal,
        ConfirmInput(
            expected_revision=goal.revision,
            preview_id=preview.id,
            idempotency_key="coherent-original-confirm",
        ),
        timeline.effect_at,
        actor_id=actor,
    )
    db.commit()
    assert goals.assessment(db, goal, timeline.effect_at) == "confirmed"
    integration = WorkspaceIntegration(
        workspace_id=wid,
        integration_key="optimization-test",
        provider="meta_ads",
        display_name="Offline",
        status="active",
        configuration={},
    )
    db.add(integration)
    db.flush()
    account = AdvertisingAccount(
        workspace_id=wid,
        connection_id=integration.id,
        platform=AdvertisingPlatform.META_ADS,
        external_account_id="123",
        name="Offline",
        currency_code="USD",
        time_zone="UTC",
    )
    db.add(account)
    db.flush()
    native = MetaConnection(
        workspace_id=wid,
        workspace_integration_id=integration.id,
        account_id=account.id,
        external_account_id="123",
        encrypted_credentials="never-opened-offline",
    )
    db.add(native)
    db.flush()
    scope = ExecutionAccount(
        workspace_id=wid,
        account=AccountScope(
            platform="meta_ads", connection_id=integration.id, account_id=account.id
        ),
        external_advertiser_id="123",
        connection_version=f"meta:{native.id}:{native.generation}",
    )
    server = Server("meta_ads")
    server.meta_campaign["daily_budget"] = "5000"
    adapter = MetaOptimizationTransport(transport=httpx.MockTransport(server))
    money = MoneyContext(
        currency="USD",
        currency_exponent=2,
        account_timezone="UTC",
        period_start=datetime.combine(timeline.budget_start, datetime.min.time(), UTC),
        period_end=datetime.combine(timeline.budget_end, datetime.min.time(), UTC),
    )
    target = OptimizationTarget(kind="campaign", external_id="5", campaign_id="5")

    def context(scope: ExecutionAccount) -> OptimizationContext:
        return OptimizationContext(
            scope=scope,
            access_token=SecretStr("offline-token"),
            expires_at=timeline.effect_at + timedelta(hours=1),
        )

    before = adapter.read_current(
        scope, target, money, "e" * 32, 1, context(scope), timeline.effect_at
    )
    policy = ProviderMandatePolicy(
        environment="contract_test",
        workspace_id=wid,
        goal_id=goal.id,
        goal_revision=goal.revision,
        currency="USD",
        time_zone="UTC",
        starts_at=money.period_start,
        ends_at=money.period_end,
        accounts=[scope],
        total_cap_micros=100_000_000,
        per_plan_cap_micros=80_000_000,
        positive_change_cap_micros=20_000_000,
        action_limit=10,
        cooldown_seconds=0,
        freshness_seconds=300,
        aggressiveness_percent=5,
        allowed_purposes=["existing_campaign_optimize"],
        allowed_target_set_digest=before.budget_owner.target_set_digest(),
        campaign_and_creative_policy="new_exact_review_required",
        activation_policy="separate_exact_approval",
    )
    db.commit()
    mandate = execution_mandates.revise(db, wid, policy, actor, lambda: timeline.effect_at)
    binding = execution_mandates.consent(
        db, wid, mandate.id, mandate.revision, policy.digest(), actor, lambda: timeline.effect_at
    )
    action = MetaBudgetSetV1(budget_field="daily_budget", amount_micros=45_000_000)

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
        meta=adapter,
    )
    return wid, actor, binding, scope, target, action, runtime, server


def produce(
    db: Session, config: Settings, path: Path, timeline: RelativePlanningTimeline
) -> dict[str, Any]:
    wid, actor, binding, scope, target, action, execution, server = coherent_original(
        db, config, timeline
    )
    row = optimization.prepare_optimization(
        db,
        wid,
        binding,
        scope,
        target,
        action,
        "a" * 64,
        actor,
        execution,
        lambda: timeline.effect_at,
    )
    optimization.approve_optimization(
        db, wid, row.id, row.digest, row.plan_digest, actor, execution, lambda: timeline.effect_at
    )
    run = optimization.create_run(db, wid, row.id, actor, execution, lambda: timeline.effect_at)
    claim = optimization.claim_step(db, wid, run.id, actor, execution, lambda: timeline.effect_at)
    assert claim is not None
    receipt = optimization.execute_claim(db, claim, actor, execution, lambda: timeline.effect_at)
    assert receipt.outcome == "verified_target_state" and len(server.posts) == 1
    user = db.get(CustomerUser, actor)
    assert user is not None
    user.issuer = FakeProvider.issuer
    now = datetime.now(UTC)
    session = CustomerSession(
        digest=uuid4().hex * 2,
        user_id=actor,
        csrf_digest="f" * 64,
        created_at=int(now.timestamp()),
        authenticated_at=int(now.timestamp()),
        expires_at=int((now + timedelta(days=60)).timestamp()),
    )
    db.add(session)
    source = db.scalar(
        select(MetaConnection).where(MetaConnection.account_id == scope.account.account_id)
    )
    assert source is not None
    source.conversion_action_type = "purchase"
    campaign = Campaign(
        account_id=scope.account.account_id,
        external_campaign_id="5",
        platform=AdvertisingPlatform.META_ADS,
        name="Owned Campaign",
        status="ACTIVE",
    )
    db.add(campaign)
    db.commit()
    mandate = db.get(ProviderExecutionMandate, binding.mandate_id)
    assert mandate is not None and run.reservation_id is not None
    policy = execution_mandates.policy(db, mandate)
    saved_receipt = db.scalar(
        select(ProviderExecutionReceipt).where(
            ProviderExecutionReceipt.attempt_id == claim.attempt_id
        )
    )
    assert saved_receipt is not None
    return dict(
        workspace_id=wid,
        actor_id=actor,
        session_digest=session.digest,
        account_id=scope.account.account_id,
        campaign_id=campaign.id,
        source_id=source.id,
        goal_id=policy.goal_id,
        goal_revision=policy.goal_revision,
        mandate_id=mandate.id,
        review_id=row.id,
        run_id=run.id,
        attempt_id=claim.attempt_id,
        receipt_id=saved_receipt.id,
        reservation_id=run.reservation_id,
        original_post_count=len(server.posts),
    )


def main() -> None:
    target, output = sys.argv[1:]
    assert (
        os.environ.get("INLET_RETIRED_EXECUTION_CHILD")
        == "2155ff3e3ab00cd62057dd86cb49d45359d4f49f"
    )
    assert Path(app.__file__).resolve().is_relative_to(Path(os.environ["PYTHONPATH"]).resolve())
    if target.startswith("sqlite:"):
        engine = create_engine(target)
        event.listen(engine, "connect", lambda db, _: db.execute("PRAGMA foreign_keys=ON"))
    else:
        assert re.fullmatch(r"inlet_test_[a-f0-9]{32}", target)
        safe_url = make_url(validate_disposable_url())
        assert safe_url.host in {"localhost", "127.0.0.1", "::1"} and not safe_url.query
        engine = create_engine(
            safe_url,
            connect_args={"options": f"-csearch_path={target}"},
        )
        with engine.connect() as connection_check:
            assert connection_check.scalar(text("select current_schema()")) == target
    try:
        tables = set(inspect(engine).get_table_names())
        with engine.connect() as empty_check:
            for table in sorted(tables - {"alembic_version"}):
                quoted = engine.dialect.identifier_preparer.quote(table)
                assert empty_check.execute(text(f"SELECT 1 FROM {quoted} LIMIT 1")).first() is None
        config = cast(Any, configuration).__wrapped__()
        with Session(engine) as db:
            timeline = RelativePlanningTimeline.from_as_of(datetime.now(UTC))
            result = produce(db, config, Path(output).parent, timeline)
            db.commit()
        assert set(inspect(engine).get_table_names()) == tables
        Path(output).write_text(json.dumps(result))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
