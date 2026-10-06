"""Actual acquisitions and initial-planning services; no fabricated preview/capsule rows."""

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest
from app.commerce.sync import CommerceSyncService
from app.executors.meta_optimization import MetaOptimizationTransport
from app.initial_planning import calibration, capture, preview
from app.initial_planning.contracts import PreviewIntentV1
from app.publication import execution_mandates
from app.publication.contracts import fingerprint
from app.publication.customer_optimization_catalog import (
    ConfiguredOptimizationCatalog,
    NamedOptimizationTarget,
)
from app.publication.customer_optimization_contracts import (
    CustomerOptimizationRuntime,
    TargetChoice,
)
from app.publication.execution_contracts import ProviderMandatePolicy
from app.publication.optimization_contracts import (
    MoneyContext,
    OptimizationContext,
    OptimizationTarget,
)
from app.publication.optimization_execution_contracts import OptimizationRuntime
from app.reported_feedback.contracts import ReportedFeedbackPolicyV1
from app.settings import Settings
from pydantic import SecretStr
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import FakeMeasurement
from tests.test_customer_identity import FakeProvider
from tests.test_initial_planning_api import explicit_policy
from tests.test_reported_feedback_acquisition import acquisition_fixture, complete


def acquired(
    db: Session,
    configuration: Settings,
    path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    data: Any = None,
) -> Any:
    if data is None:
        data = acquisition_fixture(db, configuration, path, monkeypatch)
    wid, principal, runtime, job, request, source, clock, runner, wires, control, server = data
    control.update(before_conversions="2", after_conversions="4")
    initial = replace(
        runtime.initial,
        configuration=explicit_policy().model_copy(
            update={
                "preview_lifetime_seconds": 300,
            }
        ),
    )
    assert runtime.window_policy
    runtime = replace(
        runtime,
        initial=initial,
        feedback_policy=ReportedFeedbackPolicyV1(
            policy_id="1" * 32,
            family="2" * 32,
            revision=1,
            environment="contract_test",
            comparison_policy_digest=runtime.window_policy.digest(),
            original_change="decrease",
            favorable_direction="increase",
            unfavorable_direction="decrease",
            minimum_distinct_original_attempts=1,
            neutral_band=Decimal("0.1"),
            weight=Decimal(1),
            contribution_clamp=Decimal("0.5"),
            aggregate_clamp=Decimal("0.5"),
            maximum_preview_delta_micros=2000000,
            lifetime_seconds=60,
        ),
    )
    runner.reported_feedback = runtime
    complete(runner, wid, clock[0])
    complete(runner, wid, clock[0])
    capture.capture_current(
        db, principal, FakeProvider(), wid, job.account_id, job.campaign_id, initial
    )
    db.commit()
    clock[0] += timedelta(seconds=1)
    complete(runner, wid, clock[0])
    clock[0] += timedelta(seconds=61)
    complete(runner, wid, clock[0])
    clock[0] += timedelta(seconds=1)
    complete(runner, wid, clock[0])
    observation = capture.capture_current(
        db, principal, FakeProvider(), wid, job.account_id, job.campaign_id, initial
    )
    db.commit()
    assert job.state == "ready" and job.completed_observations == 4
    # Refresh actual commerce acquisition; do not move source timestamps by hand.
    configuration.shopify_measurement_enabled = True
    commerce = CommerceSyncService(db, configuration, FakeMeasurement(configuration, [([], None)]))
    result = commerce.page(wid, now=clock[0])
    assert result["status"] == "complete", result
    db.commit()
    return data, runtime, observation


def baseline(db: Session, data: Any, runtime: Any, observation: Any) -> Any:
    wid, principal, _, job, request, _, clock, _, _, _, server = data
    from app.publication.customer_intents import account

    scope = account(db, wid, job.account_id)
    money = MoneyContext(
        currency="USD",
        currency_exponent=2,
        account_timezone="UTC",
        period_start=clock[0] - timedelta(minutes=1),
        period_end=clock[0] + timedelta(hours=1),
    )
    target = OptimizationTarget(kind="campaign", external_id="5", campaign_id="5")
    adapter = MetaOptimizationTransport(transport=httpx.MockTransport(server))
    context = OptimizationContext(
        scope=scope,
        access_token=SecretStr("offline-token"),
        expires_at=clock[0] + timedelta(hours=1),
    )

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("Non-authorizing preview cannot request financial qualification")

    execution = OptimizationRuntime(
        "contract_test", forbidden, forbidden, lambda _: context, meta=adapter
    )
    catalog = ConfiguredOptimizationCatalog(
        execution,
        (
            NamedOptimizationTarget(
                fingerprint("inlet.optimization-catalog-scope.v1", scope.model_dump(mode="json")),
                "Observed Campaign",
                "Owned Account",
                target,
                money,
                "e" * 32,
                1,
            ),
        ),
    )
    native = CustomerOptimizationRuntime(execution, catalog, runtime.initial.clock)
    initial = replace(runtime.initial, native=native)
    runtime = replace(runtime, initial=initial)
    state = adapter.read_current(scope, target, money, "e" * 32, 1, context, clock[0])
    policy = ProviderMandatePolicy(
        environment="contract_test",
        workspace_id=wid,
        goal_id=request.objective.goal_id,
        goal_revision=request.objective.goal_revision,
        currency="USD",
        time_zone="UTC",
        starts_at=money.period_start,
        ends_at=money.period_end,
        accounts=[scope],
        total_cap_micros=50000000,
        per_plan_cap_micros=50000000,
        positive_change_cap_micros=5000000,
        action_limit=1,
        cooldown_seconds=60,
        freshness_seconds=300,
        aggressiveness_percent=10,
        allowed_purposes=["existing_campaign_optimize"],
        allowed_target_set_digest=state.budget_owner.target_set_digest(),
        campaign_and_creative_policy="new_exact_review_required",
        activation_policy="separate_exact_approval",
    )
    mandate = execution_mandates.revise(db, wid, policy, principal.user.id, initial.clock)
    execution_mandates.consent(
        db, wid, mandate.id, mandate.revision, policy.digest(), principal.user.id, initial.clock
    )
    report = calibration.run_calibration(db, principal, FakeProvider(), request.objective, initial)
    assert report.status == "evaluated", report
    from app.publication import customer_optimization
    from app.publication.customer_optimization_contracts import TargetQuery

    catalog_result = customer_optimization.discover(
        db,
        wid,
        TargetQuery(
            goal_id=request.objective.goal_id,
            goal_revision=request.objective.goal_revision,
            account_id=job.account_id,
        ),
        principal.user.id,
        native,
    )
    intent = PreviewIntentV1(
        objective=request.objective,
        calibration_id=report.id,
        observation_id=observation.id,
        mandate_id=mandate.id,
        mandate_revision=mandate.revision,
        choice=TargetChoice(
            goal_id=request.objective.goal_id,
            goal_revision=request.objective.goal_revision,
            account_id=job.account_id,
            option_id=catalog_result.options[0].identifier(catalog_result.request),
        ),
    )
    db.commit()
    value = preview.prepare_preview(principal, FakeProvider(), intent, initial)
    return runtime, value
