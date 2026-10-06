"""Narrow original synchronous Google request closure; not financial/effect finality."""

from datetime import datetime, timedelta
from typing import Literal

from fastapi import HTTPException
from pydantic import AwareDatetime, Field, model_validator
from sqlalchemy.orm import Session

from app.goals.schemas import StrictModel
from app.publication import execution_mandates as mandates
from app.publication import replacement
from app.publication.contracts import fingerprint
from app.publication.execution_authorization import ExecutionAuthorizer
from app.publication.execution_contracts import ExecutionAccount, ProviderMandateBinding
from app.publication.google_completion import read_owned
from app.publication.provider_contracts import Digest
from app.publication.replacement_contracts import ClosedOriginalRequest, ReplacementSnapshot


class GoogleTerminalBatch(StrictModel):
    schema_version: Literal["inlet.google-original-terminal-batch.v1"] = (
        "inlet.google-original-terminal-batch.v1"
    )
    profile: Literal["google.v25.single_update.synchronous_response.v1"] = (
        "google.v25.single_update.synchronous_response.v1"
    )
    snapshot_digest: Digest
    account: ExecutionAccount
    mandate: ProviderMandateBinding
    observed_at: AwareDatetime
    expires_at: AwareDatetime
    closed_requests: list[ClosedOriginalRequest] = Field(min_length=1, max_length=256)
    assertion: Literal["original_configuration_requests_completed"] = (
        "original_configuration_requests_completed"
    )

    @model_validator(mode="after")
    def narrow(self) -> "GoogleTerminalBatch":
        if (
            self.account.account.platform != "google_ads"
            or not self.observed_at < self.expires_at <= self.observed_at + timedelta(minutes=5)
            or len({r.attempt_id for r in self.closed_requests}) != len(self.closed_requests)
            or any(r.basis != "authoritative_request_terminal" for r in self.closed_requests)
        ):
            raise ValueError("bounded Google original request closure required")
        return self

    def bind(
        self, snapshot: ReplacementSnapshot, mandate: ProviderMandateBinding, now: datetime
    ) -> None:
        GoogleTerminalBatch.model_validate(self.model_dump())
        if (
            self.snapshot_digest != snapshot.digest()
            or self.account != snapshot.account
            or self.mandate != mandate
            or self.mandate.environment != snapshot.environment
            or self.mandate.ledger_id != snapshot.ledger_id
            or not self.observed_at <= now < self.expires_at
            or {(r.attempt_id, r.request_digest, r.fence) for r in self.closed_requests}
            != {(r.attempt_id, r.request_digest, r.fence) for r in snapshot.receipts}
            or any(r.observed_at > self.observed_at for r in snapshot.receipts)
        ):
            raise ValueError("original request closure batch epoch or scope changed")

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


def read_terminal_batch(
    db: Session,
    workspace_id: int,
    binding: ProviderMandateBinding,
    snapshot: ReplacementSnapshot,
    actor: str,
    now: datetime,
    *,
    authorize: ExecutionAuthorizer,
) -> GoogleTerminalBatch:
    """Caller owns transaction; no IO, commits, hold updates or financial proof.

    Mandatory server-bound authorizer can bind the original customer session. Complete
    current ancestry is reconstructed rather than trusting a caller-supplied subset.
    Historical capture has no invented expiry; this read's authorization/evidence epoch does.
    """
    authorize(db, workspace_id, actor)
    if snapshot.workspace_id != workspace_id or snapshot.account.account.platform != "google_ads":
        raise HTTPException(409, "Google original request closure scope unavailable")
    ledger, policy = mandates.checked(db, workspace_id, binding, actor, lambda: now)
    if snapshot.account not in policy.accounts:
        raise HTTPException(409, "Google original request closure account unavailable")
    current = replacement.snapshot(
        db, workspace_id, snapshot.predecessor_id, actor, ledger, policy, snapshot.account
    )
    if current != snapshot:
        raise HTTPException(409, "Google original request closure epoch changed")
    closed = []
    for receipt in current.receipts:
        document = read_owned(db, workspace_id, receipt.attempt_id, actor, now)
        if document is None:
            raise HTTPException(409, "complete Google original response evidence unavailable")
        capture = document.capture
        if (
            capture.account != current.account
            or capture.environment != current.environment
            or capture.attempt_id != receipt.attempt_id
            or capture.fence != receipt.fence
            or capture.request_digest != receipt.request_digest
        ):
            raise HTTPException(409, "Google original response receipt binding changed")
        closed.append(
            ClosedOriginalRequest(
                attempt_id=capture.attempt_id,
                request_digest=capture.request_digest,
                fence=capture.fence,
                basis="authoritative_request_terminal",
                evidence_digest=document.digest(),
            )
        )
    batch = GoogleTerminalBatch(
        snapshot_digest=current.digest(),
        account=current.account,
        mandate=binding,
        observed_at=now,
        expires_at=now + timedelta(seconds=min(policy.freshness_seconds, 300)),
        closed_requests=closed,
    )
    try:
        batch.bind(current, binding, now)
    except ValueError:
        raise HTTPException(409, "Google original request closure epoch changed") from None
    return batch
