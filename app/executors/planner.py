from dataclasses import dataclass

from app.ads.enums import ExecutionStatus
from app.ads.models import Recommendation
from app.settings import Settings


@dataclass(frozen=True)
class ExecutionPlan:
    status: ExecutionStatus
    dry_run: bool
    validation_errors: list[str]
    rollback_instructions: str


def plan_dry_run(recommendation: Recommendation, settings: Settings) -> ExecutionPlan:
    errors: list[str] = []
    if not settings.google_ads_write_enabled:
        errors.append("live Google Ads writes are disabled by configuration")
    if settings.google_ads_execution_kill_switch:
        errors.append("execution kill switch is active")
    if recommendation.account_id not in settings.allowed_execution_account_ids:
        errors.append("account is not in the execution allowlist")
    return ExecutionPlan(
        status=ExecutionStatus.BLOCKED if errors else ExecutionStatus.DRY_RUN_SUCCEEDED,
        dry_run=True,
        validation_errors=errors,
        rollback_instructions=(
            "No live mutation is performed in dry-run mode. Revert by discarding this plan."
        ),
    )
