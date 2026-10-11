"""Primitive customer hypotheses only; no source evidence, authority or consumers."""

from typing import Literal

from pydantic import model_validator

from app.planning_documents.common import Amount, Currency, Digest, Frozen, Key, Positive


class GoogleDailyBudgetIntentV1(Frozen):
    schema_version: Literal["inlet.google-daily-budget-intent.v1"] = (
        "inlet.google-daily-budget-intent.v1"
    )
    account_id: Positive
    owner_selection_id: Digest
    expected_observation_digest: Digest
    expected_owner_facts_digest: Digest
    scenario_key: Key
    currency: Currency
    cadence: Literal["daily"]
    unit: Literal["micros"]
    requested_amount_micros: Amount


class ResolvedGoogleDailyBudgetIntentV1(GoogleDailyBudgetIntentV1):
    """Validated values, not an owned discovery receipt or economic qualification."""

    owner_key: Digest
    representative_canonical_key: Digest
    observed_amount_micros: Amount
    source_binding_digest: Digest

    @model_validator(mode="after")
    def non_increasing_snapshot(self) -> "ResolvedGoogleDailyBudgetIntentV1":
        if self.requested_amount_micros > self.observed_amount_micros:
            raise ValueError("requested amount exceeds observed native amount")
        return self
