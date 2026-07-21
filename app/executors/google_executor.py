"""Fail-closed Google Ads execution adapters.

This module intentionally does not import or call the Google Ads SDK. It provides
mockable adapter boundaries and policy-only execution results so the analyzer can
exercise controlled-execution workflows without enabling live mutations.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from app.ads.enums import ExecutionStatus
from app.ads.models import Recommendation
from app.settings import Settings


@dataclass(frozen=True)
class MutationPreflight:
    """Safe preflight result for a proposed Google Ads mutation."""

    status: ExecutionStatus
    dry_run: bool
    validation_errors: list[str]
    rollback_instructions: str
    attempted_live_mutation: bool = False
    checked_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class GoogleAdsMutationAdapter(Protocol):
    """Adapter boundary for future controlled mutation implementations."""

    def preflight(self, recommendation: Recommendation, settings: Settings) -> MutationPreflight:
        """Return a policy-only preflight result without performing a live mutation."""


class FailClosedGoogleAdsMutationAdapter:
    """Default adapter that blocks every live Google Ads mutation path."""

    def preflight(self, recommendation: Recommendation, settings: Settings) -> MutationPreflight:
        errors = live_mutation_policy_errors(recommendation, settings)
        return MutationPreflight(
            status=ExecutionStatus.BLOCKED,
            dry_run=True,
            validation_errors=errors or ["live Google Ads mutations are not implemented"],
            rollback_instructions=(
                "No live mutation was attempted. Keep the execution kill switch enabled, "
                "leave write access disabled, and discard the blocked plan."
            ),
            attempted_live_mutation=False,
        )


class MockGoogleAdsMutationAdapter:
    """Deterministic test adapter for non-production controlled-write workflows."""

    def preflight(self, recommendation: Recommendation, settings: Settings) -> MutationPreflight:
        errors = live_mutation_policy_errors(recommendation, settings)
        status = ExecutionStatus.BLOCKED if errors else ExecutionStatus.DRY_RUN_SUCCEEDED
        return MutationPreflight(
            status=status,
            dry_run=True,
            validation_errors=errors,
            rollback_instructions=compensating_action_instructions(recommendation),
            attempted_live_mutation=False,
        )


def live_mutation_policy_errors(recommendation: Recommendation, settings: Settings) -> list[str]:
    """Return fail-closed policy errors for any live Google Ads mutation attempt."""

    errors: list[str] = ["live Google Ads mutations are disabled for this buildout"]
    if not settings.google_ads_write_enabled:
        errors.append("live Google Ads writes are disabled by configuration")
    if settings.google_ads_execution_kill_switch:
        errors.append("execution kill switch is active")
    if recommendation.account_id not in settings.allowed_execution_account_ids:
        errors.append("account is not in the execution allowlist")
    return errors


def compensating_action_instructions(recommendation: Recommendation) -> str:
    """Describe reversible operator steps without exposing raw API payloads."""

    return (
        "No live Google Ads mutation is performed by this adapter. If a future approved "
        f"operator executes recommendation {recommendation.id}, record the external change ID, "
        "restore the prior campaign setting through an approved manual runbook, and append the "
        "compensating action to the immutable execution audit."
    )
