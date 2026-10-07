"""Strict export contract for stored settlement receipts, not new settlement authority."""

from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from app.goals.schemas import StrictModel
from app.publication.provider_contracts import Digest
from app.publication.settlement import SettlementObservation, SettlementSnapshot


class SettlementEvidence(StrictModel):
    schema_version: Literal["inlet.provider-settlement.v1"]
    kind: Literal["no_committed_attempt", "qualified_terminal"]
    snapshot: SettlementSnapshot
    snapshot_digest: Digest
    actor: str = Field(min_length=1, max_length=320)
    settled_at: AwareDatetime
    observation: SettlementObservation | None = None

    @model_validator(mode="after")
    def exact_evidence(self) -> "SettlementEvidence":
        snapshot = self.snapshot
        original = snapshot.original_exposure
        if (
            snapshot.digest() != self.snapshot_digest
            or original.account.workspace_id != snapshot.workspace_id
            or original.environment != snapshot.environment
            or original.mandate.ledger_id != snapshot.ledger_id
            or original.budget_owner_key != snapshot.budget_owner_key
            or original.proposed_owner_upper_micros != snapshot.amount_micros
            or any(
                r.account.workspace_id != snapshot.workspace_id
                or r.environment != snapshot.environment
                for r in snapshot.receipts
            )
        ):
            raise ValueError("settlement snapshot ownership mismatch")
        if self.kind == "no_committed_attempt":
            if snapshot.receipts or self.observation is not None:
                raise ValueError("unemitted settlement cannot contain provider effects")
        else:
            proof = self.observation
            if (
                not snapshot.receipts
                or proof is None
                or proof.status != "qualified"
                or proof.snapshot_digest != self.snapshot_digest
                or proof.environment != snapshot.environment
                or not proof.observed_at <= self.settled_at < proof.expires_at
                or set(proof.closed_attempt_ids) != {r.attempt_id for r in snapshot.receipts}
                or set(proof.complete_account_ids) != set(original.covered_account_ids)
                or proof.reported_portfolio_spend_micros is None
                or proof.reported_portfolio_spend_micros < snapshot.ledger_spent_high_water_micros
                or proof.terminal_effect_upper is None
                or any(r.observed_at > proof.terminal_effect_upper for r in snapshot.receipts)
            ):
                raise ValueError("settlement reporting evidence mismatch")
        return self
