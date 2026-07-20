from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.ads.enums import ExecutionStatus
from app.ads.models import Recommendation
from app.executors.google_executor import GoogleAdsMutationAdapter, MockGoogleAdsMutationAdapter
from app.settings import Settings


@dataclass(frozen=True)
class ExecutionPlan:
    status: ExecutionStatus
    dry_run: bool
    validation_errors: list[str]
    rollback_instructions: str
    preflight: dict[str, object] = field(default_factory=dict)


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _planned_mutation_type(recommendation: Recommendation) -> str:
    mutation = recommendation.planned_action.get("mutation")
    if isinstance(mutation, str) and mutation.strip():
        return mutation.strip()
    return "unspecified"


def _build_rollback_instructions(preflight: dict[str, object] | None = None) -> str:
    base = "No live Google Ads mutation is performed by Phase 11.3 controlled execution."
    if not preflight:
        return f"{base} Revert by discarding this non-live plan."
    return (
        f"{base} Mock rollback model: {preflight['rollback_action']}. "
        f"Compensating-action model: {preflight['compensating_action']}."
    )


def plan_dry_run(
    recommendation: Recommendation,
    settings: Settings,
    *,
    now: datetime | None = None,
    adapter: GoogleAdsMutationAdapter | None = None,
) -> ExecutionPlan:
    errors: list[str] = []
    now = now or datetime.now(UTC)
    mutation_type = _planned_mutation_type(recommendation)
    if not settings.google_ads_write_enabled:
        errors.append("live Google Ads writes are disabled by configuration")
    if settings.google_ads_execution_kill_switch:
        errors.append("execution kill switch is active")
    if recommendation.account_id not in settings.allowed_execution_account_ids:
        errors.append("account is not in the execution allowlist")
    if mutation_type not in settings.allowed_google_ads_mutations:
        errors.append("mutation type is not in the execution allowlist")
    if _as_aware_utc(recommendation.expires_at) <= _as_aware_utc(now):
        errors.append("recommendation is stale or expired")

    if errors:
        return ExecutionPlan(
            status=ExecutionStatus.BLOCKED,
            dry_run=True,
            validation_errors=errors,
            rollback_instructions=_build_rollback_instructions(),
        )

    mock_adapter = adapter or MockGoogleAdsMutationAdapter()
    result = mock_adapter.preflight(recommendation, mutation_type=mutation_type)
    preflight = {
        "adapter": result.adapter,
        "operation_id": result.operation_id,
        "account_id": result.account_id,
        "mutation_type": result.mutation_type,
        "would_mutate": result.would_mutate,
        "rollback_action": result.rollback_action,
        "compensating_action": result.compensating_action,
    }
    return ExecutionPlan(
        status=ExecutionStatus.DRY_RUN_SUCCEEDED,
        dry_run=True,
        validation_errors=[],
        rollback_instructions=_build_rollback_instructions(preflight),
        preflight=preflight,
    )
