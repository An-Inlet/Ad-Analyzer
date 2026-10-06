"""Release retained exposure only from original-attempt and terminal reporting evidence.

Settlement never mutates a provider or infers authority from period end, paused status,
missing readback, age, or one no-effect step among earlier successful resources.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal, Protocol

from fastapi import HTTPException
from pydantic import AwareDatetime, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.goals.schemas import StrictModel
from app.publication import coordinator
from app.publication.contracts import fingerprint
from app.publication.execution_contracts import (
    Environment,
    ExposureEvidence,
    NormalizedProviderReceipt,
)
from app.publication.execution_models import (
    ProviderExecutionAttempt,
    ProviderExecutionRun,
    ProviderExposureReservation,
    ProviderPeriodLedger,
)
from app.publication.provider_contracts import Digest, Id
from app.publication.service import owner
from app.shopify.security import utc
from app.workspaces.models import Workspace


class SettlementSnapshot(StrictModel):
    workspace_id: int = Field(strict=True, gt=0)
    reservation_id: Id
    ledger_id: Id
    environment: Environment
    budget_owner_key: str = Field(min_length=1, max_length=256)
    amount_micros: int = Field(strict=True, ge=0)
    ledger_spent_high_water_micros: int = Field(strict=True, ge=0)
    original_exposure: ExposureEvidence
    canceled_run_ids: list[Id] = Field(min_length=1, max_length=128)
    receipts: list[NormalizedProviderReceipt] = Field(max_length=256)

    def digest(self) -> str:
        return fingerprint("inlet.provider-settlement-snapshot.v1", self.model_dump(mode="json"))


class SettlementObservation(StrictModel):
    snapshot_digest: Digest
    environment: Environment
    observed_at: AwareDatetime
    expires_at: AwareDatetime
    status: Literal["qualified", "unavailable"]
    qualification_profile: str = Field(min_length=1, max_length=80)
    proof_kind: Literal["authoritative_terminal_complete", "contract_scenario", "unavailable"]
    proof_digest: Digest
    terminal_effect_upper: AwareDatetime | None
    reporting_watermark: AwareDatetime | None
    reported_portfolio_spend_micros: int | None = Field(default=None, strict=True, ge=0)
    remaining_future_upper_micros: int | None = Field(default=None, strict=True, ge=0)
    # Exact target state alone does not prove the original network operation finished.
    # The source must prove every original request is terminal or incapable of a
    # later effect (e.g. a qualified non-resumable terminal resource), never mere absence.
    closed_attempt_ids: list[Id] = Field(max_length=256)
    complete_account_ids: list[int] = Field(max_length=128)
    missing: list[str] = Field(max_length=32)

    @model_validator(mode="after")
    def qualified(self) -> "SettlementObservation":
        if not self.observed_at < self.expires_at <= self.observed_at + timedelta(minutes=5):
            raise ValueError("bounded settlement proof lifetime required")
        if self.environment == "live" and self.proof_kind == "contract_scenario":
            raise ValueError("contract scenario cannot qualify live settlement")
        if self.status == "qualified" and (
            self.proof_kind == "unavailable"
            or self.missing
            or self.terminal_effect_upper is None
            or self.reporting_watermark is None
            or not self.terminal_effect_upper <= self.reporting_watermark <= self.observed_at
            or self.reported_portfolio_spend_micros is None
            or self.remaining_future_upper_micros != 0
        ):
            raise ValueError("authoritative terminal exposure and complete reporting required")
        if len(set(self.closed_attempt_ids)) != len(self.closed_attempt_ids):
            raise ValueError("unique terminal original attempts required")
        if len(set(self.complete_account_ids)) != len(self.complete_account_ids):
            raise ValueError("unique reporting accounts required")
        return self


class SettlementReader(Protocol):
    def __call__(self, snapshot: SettlementSnapshot, now: datetime, /) -> SettlementObservation:
        """Server-owned read-only source, not customer supplied evidence or mutation authority."""
        ...


@dataclass(frozen=True)
class SettlementRuntime:
    environment: Environment
    reader: SettlementReader
    live_enabled: bool = False


def get_settlement_runtime() -> SettlementRuntime | None:
    return None


def locked_snapshot(
    db: Session,
    wid: int,
    reservation_id: str,
    actor: str,
) -> tuple[ProviderExposureReservation, ProviderPeriodLedger, SettlementSnapshot]:
    workspace = db.scalar(select(Workspace).where(Workspace.id == wid).with_for_update())
    if workspace is None:
        raise HTTPException(404, "workspace unavailable")
    owner(db, wid, actor)
    # Discover scope without locking the reservation before the period ledger.
    reservation = db.scalar(
        select(ProviderExposureReservation).where(
            ProviderExposureReservation.id == reservation_id,
            ProviderExposureReservation.workspace_id == wid,
        )
    )
    if reservation is None:
        raise HTTPException(404, "owned reservation unavailable")
    ledger = db.scalar(
        select(ProviderPeriodLedger)
        .where(
            ProviderPeriodLedger.id == reservation.ledger_id,
            ProviderPeriodLedger.workspace_id == wid,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if ledger is None:
        raise HTTPException(409, "original period ledger unavailable")
    db.refresh(reservation, with_for_update=True)
    if reservation.state != "held":
        raise HTTPException(409, "reservation is no longer held")
    original = ExposureEvidence.model_validate(reservation.evidence)
    if (
        original.environment != reservation.environment
        or ledger.environment != reservation.environment
        or original.mandate.ledger_id != ledger.id
        or original.account.workspace_id != wid
        or original.budget_owner_key != reservation.budget_owner_key
        or original.proposed_owner_upper_micros != reservation.amount_micros
        or original.currency != ledger.currency
        or (original.period_start, original.period_end)
        != (utc(ledger.starts_at), utc(ledger.ends_at))
    ):
        raise HTTPException(409, "reservation lineage changed")
    runs = list(
        db.scalars(
            select(ProviderExecutionRun)
            .where(
                ProviderExecutionRun.reservation_id == reservation.id,
                ProviderExecutionRun.workspace_id == wid,
            )
            .order_by(ProviderExecutionRun.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    )
    if not runs or any(run.canceled_at is None for run in runs):
        raise HTTPException(409, "cancel all related runs before settlement")
    receipts = []
    for run in runs:
        for attempt in db.scalars(
            select(ProviderExecutionAttempt)
            .where(
                ProviderExecutionAttempt.run_id == run.id,
                ProviderExecutionAttempt.workspace_id == wid,
            )
            .order_by(ProviderExecutionAttempt.id)
        ):
            receipt = coordinator.read_owned_outcome_receipt(db, wid, attempt.id, actor)
            if receipt is None or receipt.outcome not in {
                "verified_effect",
                "verified_target_state",
                "verified_no_effect",
            }:
                raise HTTPException(409, "unresolved original attempt retains exposure")
            if receipt.environment != original.environment or receipt.account != original.account:
                raise HTTPException(409, "original attempt exposure scope changed")
            receipts.append(receipt)
    snapshot = SettlementSnapshot(
        workspace_id=wid,
        reservation_id=reservation.id,
        ledger_id=ledger.id,
        environment=original.environment,
        budget_owner_key=reservation.budget_owner_key,
        amount_micros=reservation.amount_micros,
        ledger_spent_high_water_micros=ledger.spent_high_water_micros,
        original_exposure=original,
        canceled_run_ids=[r.id for r in runs],
        receipts=receipts,
    )
    return reservation, ledger, snapshot


def settle_unemitted(
    db: Session,
    wid: int,
    reservation_id: str,
    actor: str,
    clock: coordinator.Clock,
) -> ProviderExposureReservation:
    """A zero-attempt canceled graph has no possible dispatched original request."""
    reservation, _, snapshot = locked_snapshot(db, wid, reservation_id, actor)
    if snapshot.receipts:
        raise HTTPException(409, "provider terminal reporting proof required")
    reservation.settled_evidence = {
        "schema_version": "inlet.provider-settlement.v1",
        "kind": "no_committed_attempt",
        "snapshot": snapshot.model_dump(mode="json"),
        "snapshot_digest": snapshot.digest(),
        "actor": actor,
        "settled_at": clock().isoformat(),
    }
    reservation.state = "settled"
    db.commit()
    return reservation


def settle(
    db: Session,
    wid: int,
    reservation_id: str,
    actor: str,
    runtime: SettlementRuntime,
    clock: coordinator.Clock,
) -> ProviderExposureReservation:
    _, _, snapshot = locked_snapshot(db, wid, reservation_id, actor)
    if runtime.environment != snapshot.environment or (
        snapshot.environment == "live" and not runtime.live_enabled
    ):
        raise HTTPException(409, "settlement qualification runtime unavailable")
    if not snapshot.receipts:
        raise HTTPException(409, "use exact local unemitted settlement")
    db.commit()
    evidence = runtime.reader(snapshot, clock())  # bounded read-only IO; no provider locks held
    evidence = SettlementObservation.model_validate(evidence.model_dump(mode="json"))
    reservation, ledger, latest = locked_snapshot(db, wid, reservation_id, actor)
    now = clock()
    if (
        latest != snapshot
        or evidence.snapshot_digest != snapshot.digest()
        or evidence.environment != snapshot.environment
        or evidence.status != "qualified"
        or not evidence.observed_at <= now < evidence.expires_at
        or set(evidence.closed_attempt_ids) != {r.attempt_id for r in snapshot.receipts}
        or set(evidence.complete_account_ids) != set(snapshot.original_exposure.covered_account_ids)
        or evidence.reported_portfolio_spend_micros is None
        or evidence.reported_portfolio_spend_micros < ledger.spent_high_water_micros
        or evidence.terminal_effect_upper is None
        or any(
            receipt.observed_at > evidence.terminal_effect_upper for receipt in snapshot.receipts
        )
    ):
        raise HTTPException(409, "current authoritative terminal reporting proof required")
    # No spend/action reset, refund or erased history. Settlement can reveal an over-cap
    # spend; retaining the true high-water is mandatory even when it exceeds the mandate.
    ledger.spent_high_water_micros = evidence.reported_portfolio_spend_micros
    reservation.settled_evidence = {
        "schema_version": "inlet.provider-settlement.v1",
        "kind": "qualified_terminal",
        "snapshot": snapshot.model_dump(mode="json"),
        "snapshot_digest": snapshot.digest(),
        "observation": evidence.model_dump(mode="json"),
        "actor": actor,
        "settled_at": now.isoformat(),
    }
    reservation.state = "settled"
    db.commit()
    return reservation
