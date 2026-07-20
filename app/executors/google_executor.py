from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from app.ads.models import Recommendation

SAFE_MOCK_ADAPTER_NAME = "mock_google_ads_mutation_adapter"


@dataclass(frozen=True)
class MockMutationResult:
    """Deterministic non-live mutation simulation result."""

    adapter: str
    operation_id: str
    account_id: int
    mutation_type: str
    would_mutate: bool
    rollback_action: dict[str, object]
    compensating_action: dict[str, object]


class GoogleAdsMutationAdapter(Protocol):
    """Boundary for future Google Ads mutation adapters."""

    def preflight(
        self, recommendation: Recommendation, *, mutation_type: str
    ) -> MockMutationResult:
        """Return a deterministic preflight result without making external calls."""


class MockGoogleAdsMutationAdapter:
    """Safe mocked adapter that never imports or calls the Google Ads client."""

    def preflight(
        self, recommendation: Recommendation, *, mutation_type: str
    ) -> MockMutationResult:
        operation_id = (
            f"mock-google-ads:{recommendation.id}:{recommendation.account_id}:{mutation_type}"
        )
        rollback_action: dict[str, object] = {
            "mode": "non_live_model",
            "operation_id": operation_id,
            "action": "no_live_state_to_restore",
        }
        compensating_action: dict[str, object] = {
            "mode": "non_live_model",
            "operation_id": operation_id,
            "action": "operator_review_required_before_any_future_compensation",
            "modeled_at": datetime(2026, 7, 20, tzinfo=UTC).isoformat(),
        }
        return MockMutationResult(
            adapter=SAFE_MOCK_ADAPTER_NAME,
            operation_id=operation_id,
            account_id=recommendation.account_id,
            mutation_type=mutation_type,
            would_mutate=False,
            rollback_action=rollback_action,
            compensating_action=compensating_action,
        )


class LiveGoogleAdsMutationAttemptBlocked(RuntimeError):
    """Raised if code attempts to cross the fail-closed live mutation boundary."""


def live_google_ads_mutation_boundary(*_args: object, **_kwargs: object) -> None:
    """Fail closed until a future human-approved live executor replaces this stub."""

    raise LiveGoogleAdsMutationAttemptBlocked("live Google Ads mutation boundary is disabled")
