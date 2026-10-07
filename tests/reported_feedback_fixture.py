"""Owned actual Meta HTTP optimization receipt; explicit offline numeric policy."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from app.ads.enums import AdvertisingPlatform
from app.ads.models import Campaign
from app.customers.access import CustomerPrincipal
from app.customers.models import CustomerSession, CustomerUser
from app.initial_planning.runtime import InitialPlanningRuntime
from app.meta.models import MetaConnection
from app.meta.security import API_VERSION
from app.publication import execution_mandates, optimization
from app.publication.execution_models import ProviderExecutionMandate
from app.reported_feedback.contracts import (
    ComparisonIntentV1,
    ReportedFeedbackPolicyV1,
    ReportedWindowPolicyV1,
)
from app.reported_feedback.runtime import ReportedFeedbackRuntime
from app.reported_feedback.service import request_comparison
from app.settings import Settings
from sqlalchemy import select
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import FakeProvider
from tests.test_durable_optimization import ready


def window_policy() -> ReportedWindowPolicyV1:
    return ReportedWindowPolicyV1(
        policy_id="a" * 32,
        family="b" * 32,
        revision=1,
        environment="contract_test",
        selected_event="purchase",
        query_version=f"meta.{API_VERSION}.campaign-day.v1",
        window_days=7,
        minimum_close_age_seconds=60,
        distinct_repeat_completions=2,
        minimum_repeat_spacing_seconds=60,
        maximum_acquisition_age_seconds=86400,
        maximum_source_age_seconds=3600,
        daily_spend_absolute_tolerance_micros=0,
        daily_conversion_absolute_tolerance=Decimal(0),
        daily_relative_tolerance=Decimal(0),
        minimum_conversions=Decimal(1),
        minimum_spend_micros=1,
        retention_seconds=86400 * 60,
        maximum_capsules=32,
        maximum_requests=4,
        decision_lifetime_seconds=60,
    )


def seeded(db: Session, config: Settings, path: Path):  # type: ignore[no-untyped-def]
    wid, actor, binding, scope, target, action, execution, server = ready(
        db, config, path, "meta_ads", campaign=True
    )
    row = optimization.prepare_optimization(
        db, wid, binding, scope, target, action, "a" * 64, actor, execution, lambda: NOW
    )
    optimization.approve_optimization(
        db, wid, row.id, row.digest, row.plan_digest, actor, execution, lambda: NOW
    )
    run = optimization.create_run(db, wid, row.id, actor, execution, lambda: NOW)
    claim = optimization.claim_step(db, wid, run.id, actor, execution, lambda: NOW)
    assert claim is not None
    receipt = optimization.execute_claim(db, claim, actor, execution, lambda: NOW)
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
    principal, provider = CustomerPrincipal(user, session), FakeProvider()
    clock = [now]
    engine = db.get_bind()
    runtime = ReportedFeedbackRuntime(
        initial=InitialPlanningRuntime(
            session_factory=lambda: Session(engine), clock=lambda: clock[0]
        ),
        window_policy=window_policy(),
    )
    mandate = db.get(ProviderExecutionMandate, binding.mandate_id)
    assert mandate is not None
    policy = execution_mandates.policy(db, mandate)
    intent = ComparisonIntentV1(
        attempt_id=claim.attempt_id,
        goal_id=policy.goal_id,
        goal_revision=policy.goal_revision,
        maximum_reported_cpa_micros=100_000_000,
    )
    progress = request_comparison(db, principal, provider, wid, intent, runtime)
    db.commit()
    return wid, principal, provider, runtime, intent, progress, clock, server


def feedback_policy() -> ReportedFeedbackPolicyV1:
    return ReportedFeedbackPolicyV1(
        policy_id="c" * 32,
        family="d" * 32,
        revision=1,
        environment="contract_test",
        comparison_policy_digest=window_policy().digest(),
        original_change="decrease",
        favorable_direction="decrease",
        unfavorable_direction="increase",
        minimum_distinct_original_attempts=1,
        neutral_band=Decimal("0.01"),
        weight=Decimal("0.5"),
        contribution_clamp=Decimal("0.5"),
        aggregate_clamp=Decimal("0.5"),
        maximum_preview_delta_micros=1_000_000,
        lifetime_seconds=60,
    )
