from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from app.ads.enums import AdvertisingPlatform, ExecutionStatus, RecommendationStatus
from app.ads.models import Recommendation
from app.executors.google_executor import (
    LiveGoogleAdsMutationAttemptBlocked,
    live_google_ads_mutation_boundary,
)
from app.executors.planner import plan_dry_run
from app.settings import Settings


class ExplodingLiveAdapter:
    def preflight(self, recommendation: Recommendation, *, mutation_type: str) -> Any:
        raise AssertionError("a live Google Ads adapter must not be called")


def make_recommendation(**overrides: Any) -> Recommendation:
    values: dict[str, Any] = {
        "id": 77,
        "platform": AdvertisingPlatform.GOOGLE_ADS,
        "account_id": 123,
        "campaign_id": 456,
        "recommendation_type": "budget_guardrail",
        "severity": "medium",
        "confidence": Decimal("0.7000"),
        "rationale": "deterministic test recommendation",
        "supporting_metrics": {"clicks": "25"},
        "planned_action": {"mode": "dry_run_only", "mutation": "pause_campaign"},
        "status": RecommendationStatus.APPROVED,
        "generated_at": datetime(2026, 7, 20, tzinfo=UTC),
        "expires_at": datetime(2026, 7, 21, tzinfo=UTC),
    }
    values.update(overrides)
    return Recommendation(**values)


def safe_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "DENTICODE_GOOGLE_ADS_WRITE_ENABLED": True,
        "DENTICODE_GOOGLE_ADS_EXECUTION_KILL_SWITCH": False,
        "DENTICODE_ALLOWED_EXECUTION_ACCOUNT_IDS": "123",
        "DENTICODE_ALLOWED_GOOGLE_ADS_MUTATIONS": "pause_campaign",
    }
    values.update(overrides)
    return Settings(**values)


def test_defaults_fail_closed_without_live_google_ads_adapter() -> None:
    plan = plan_dry_run(
        make_recommendation(),
        Settings(),
        now=datetime(2026, 7, 20, tzinfo=UTC),
        adapter=ExplodingLiveAdapter(),
    )

    assert plan.status == ExecutionStatus.BLOCKED
    assert plan.preflight == {}
    assert plan.validation_errors == [
        "live Google Ads writes are disabled by configuration",
        "execution kill switch is active",
        "account is not in the execution allowlist",
        "mutation type is not in the execution allowlist",
    ]


def test_account_allowlist_and_mutation_allowlist_are_validated() -> None:
    plan = plan_dry_run(
        make_recommendation(account_id=999, planned_action={"mutation": "raise_budget"}),
        safe_settings(),
        now=datetime(2026, 7, 20, tzinfo=UTC),
        adapter=ExplodingLiveAdapter(),
    )

    assert plan.status == ExecutionStatus.BLOCKED
    assert "account is not in the execution allowlist" in plan.validation_errors
    assert "mutation type is not in the execution allowlist" in plan.validation_errors
    assert plan.preflight == {}


def test_stale_recommendation_blocks_preflight() -> None:
    plan = plan_dry_run(
        make_recommendation(expires_at=datetime(2026, 7, 19, tzinfo=UTC)),
        safe_settings(),
        now=datetime(2026, 7, 20, tzinfo=UTC),
        adapter=ExplodingLiveAdapter(),
    )

    assert plan.status == ExecutionStatus.BLOCKED
    assert plan.validation_errors == ["recommendation is stale or expired"]
    assert plan.rollback_instructions.startswith("No live Google Ads mutation is performed")


def test_mocked_google_ads_preflight_is_deterministic_and_non_live() -> None:
    recommendation = make_recommendation()
    settings = safe_settings()

    first = plan_dry_run(recommendation, settings, now=datetime(2026, 7, 20, tzinfo=UTC))
    second = plan_dry_run(
        recommendation,
        settings,
        now=datetime(2026, 7, 20, tzinfo=UTC) + timedelta(hours=1),
    )

    assert first.status == ExecutionStatus.DRY_RUN_SUCCEEDED
    assert first.preflight == second.preflight
    assert first.preflight["adapter"] == "mock_google_ads_mutation_adapter"
    assert first.preflight["would_mutate"] is False
    assert first.preflight["rollback_action"] == {
        "mode": "non_live_model",
        "operation_id": "mock-google-ads:77:123:pause_campaign",
        "action": "no_live_state_to_restore",
    }
    assert first.preflight["compensating_action"] == {
        "mode": "non_live_model",
        "operation_id": "mock-google-ads:77:123:pause_campaign",
        "action": "operator_review_required_before_any_future_compensation",
        "modeled_at": "2026-07-20T00:00:00+00:00",
    }


def test_live_google_ads_mutation_boundary_raises_before_any_call() -> None:
    try:
        live_google_ads_mutation_boundary()
    except LiveGoogleAdsMutationAttemptBlocked as exc:
        assert str(exc) == "live Google Ads mutation boundary is disabled"
    else:  # pragma: no cover
        raise AssertionError("live mutation boundary did not fail closed")
