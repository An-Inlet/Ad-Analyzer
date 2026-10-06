"""Acknowledged CRM pages and durable renewal. No scheduler enrollment/profile storage."""

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, cast
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import delete, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.customer_context.contracts import ContextPage, CustomerProvider, RefreshCandidate
from app.customer_context.http import (
    CRMHTTP,
    CRMAuthenticationUnavailable,
    CRMInvalidGrant,
    CRMProofRejected,
    CRMRateLimited,
    CRMReadError,
    HubSpotHTTPRead,
    KlaviyoHTTPRead,
    OmnisendHTTPRead,
)
from app.customer_context.models import CRMCheckpoint, CRMQuota
from app.settings import settings
from app.shopify.security import utc
from app.sources.models import SourceConnection
from app.sources.security import SourceVault
from app.sources.service import discard_context_checkpoint, owned
from app.workspaces.models import WorkspaceIntegration

SPACING = timedelta(seconds=4.1)
LEASE = timedelta(seconds=120)


@dataclass(frozen=True)
class DeferredRead:
    due_at: datetime


@dataclass(frozen=True)
class PageDelivery:
    page: ContextPage
    receipt: str


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def connection(
    db: Session, wid: int, cid: str, generation: int, provider: CustomerProvider = "klaviyo"
) -> SourceConnection:
    row = owned(db, wid, provider, cid)
    integration = db.get(WorkspaceIntegration, row.integration_id, populate_existing=True)
    if (
        row.generation != generation
        or row.status != "connected"
        or integration is None
        or integration.workspace_id != wid
        or integration.provider != provider
        or integration.status != "active"
    ):
        raise HTTPException(409, "customer context connection unavailable")
    return row


def context(row: SourceConnection) -> str:
    return f"crm-progress:{row.id}:{row.generation}:{row.integration_id}:{row.external_id}"


def quota_key(reader: CRMHTTP, row: SourceConnection) -> str:
    secret = settings.source_token_encryption_key
    if secret is None:
        raise HTTPException(503, "source encryption unavailable")
    payload = json.dumps(["crm-quota-v1", row.provider, reader.client_id, row.external_id])
    return hmac.new(
        secret.get_secret_value().encode(), payload.encode(), hashlib.sha256
    ).hexdigest()


def quota(db: Session, key: str, now: datetime) -> CRMQuota:
    insert = pg_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
    db.execute(insert(CRMQuota).values(key=key, due_at=now).on_conflict_do_nothing())
    return db.scalars(
        select(CRMQuota)
        .where(CRMQuota.key == key)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one()


def prune_expired_quotas(db: Session, now: datetime) -> int:
    """Bounded opportunistic cleanup; never remove an active lease or cooldown."""
    keys = list(
        db.scalars(
            select(CRMQuota.key)
            .where(
                CRMQuota.due_at < now - timedelta(days=1),
                or_(CRMQuota.lease_until.is_(None), CRMQuota.lease_until < now),
            )
            .order_by(CRMQuota.key)
            .limit(100)
            .with_for_update(skip_locked=True)
        )
    )
    if keys:
        db.execute(delete(CRMQuota).where(CRMQuota.key.in_(keys)))
    db.commit()
    return len(keys)


def expires_at(bundle: dict[str, Any]) -> datetime | None:
    value = bundle.get("expires_at")
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 64:
        raise CRMReadError("crm_grant_invalid")
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError
        return utc(parsed)
    except (ValueError, OverflowError):
        raise CRMReadError("crm_grant_invalid") from None


def needs_attention(db: Session, row: SourceConnection, *, uncertain: bool = False) -> None:
    # Provider-error/uncertain is distinct from a revoked grant. Nothing here calls
    # provider revocation. Reconnect retires this generation through existing Source logic.
    row.status = "provider_error" if uncertain else "reconnect_required"
    row.error_code = "renewal_uncertain" if uncertain else "crm_reconnect_required"
    row.encrypted_grant = None
    row.next_attempt_at = None
    discard_context_checkpoint(db, row)


def candidate_payload(candidate: RefreshCandidate) -> dict[str, Any]:
    return {
        "provider": candidate.provider,
        "access_token": candidate.access_token.get_secret_value(),
        "refresh_token": candidate.refresh_token.get_secret_value()
        if candidate.refresh_token
        else None,
        "expires_at": candidate.expires_at.isoformat() if candidate.expires_at else None,
        "scopes": sorted(candidate.scopes) if candidate.scopes is not None else None,
    }


def read_page(
    db: Session,
    workspace_id: int,
    connection_id: str,
    generation: int,
    reader: CRMHTTP,
    now: datetime,
) -> PageDelivery | DeferredRead | None:
    """One HTTP phase per committed lease: issue, prove, or read then acknowledge.

    Renewal candidates are encrypted before account proof and never used for profiles
    until proved. All phases share conservative global account pacing. No sleep/retry.
    """
    if not isinstance(reader, (KlaviyoHTTPRead, HubSpotHTTPRead, OmnisendHTTPRead)):
        raise HTTPException(503, "paced customer context unavailable")
    provider = reader.provider
    prune_expired_quotas(db, now)
    row = connection(db, workspace_id, connection_id, generation, provider)
    vault = SourceVault()
    bundle = vault.open(workspace_id, provider, row.id, row.encrypted_grant or "")
    expiry = expires_at(bundle)
    grant_digest = digest(row.encrypted_grant or "")
    checkpoint = db.get(CRMCheckpoint, row.id, populate_existing=True)
    if checkpoint is None:
        checkpoint = CRMCheckpoint(connection_id=row.id)
        db.add(checkpoint)
    if checkpoint.generation != generation or checkpoint.grant_digest != grant_digest:
        checkpoint.generation = generation
        checkpoint.grant_digest = grant_digest
        checkpoint.encrypted_progress = vault.seal(
            workspace_id, provider, context(row), {"cursor": None, "seen": [], "pages": 0}
        )
        checkpoint.state, checkpoint.fence, checkpoint.lease_until, checkpoint.ack_digest = (
            "ready",
            None,
            None,
            None,
        )
    if checkpoint.state == "done":
        db.commit()
        return None
    if checkpoint.lease_until and utc(checkpoint.lease_until) > now:
        due = utc(checkpoint.lease_until)
        db.commit()
        return DeferredRead(due)
    if checkpoint.state == "refreshing":
        # A worker may have consumed the rotating credential before crashing.
        needs_attention(db, row, uncertain=True)
        db.commit()
        raise HTTPException(409, "customer renewal outcome unknown; reconnect required")
    if row.next_attempt_at and utc(row.next_attempt_at) > now:
        due = utc(row.next_attempt_at)
        db.commit()
        return DeferredRead(due)
    progress = vault.open(workspace_id, provider, context(row), checkpoint.encrypted_progress)
    if progress["pages"] >= 20:
        raise HTTPException(409, "customer context page capacity exceeded")
    phase = (
        "proof"
        if "candidate" in progress
        else (
            "issue"
            if progress.get("refresh_required")
            or expiry is not None
            and expiry <= now + timedelta(seconds=60)
            else "read"
        )
    )
    refresh = bundle.get("refresh_token")
    if phase == "issue" and (not isinstance(refresh, str) or not refresh):
        needs_attention(db, row)
        db.commit()
        raise HTTPException(409, "customer renewal unavailable; reconnect required")
    pending = None
    if phase == "proof":
        try:
            pending = RefreshCandidate.model_validate(progress["candidate"])
        except ValueError:
            needs_attention(db, row, uncertain=True)
            db.commit()
            raise HTTPException(409, "customer renewal candidate unavailable") from None
        if pending.expires_at is not None and pending.expires_at <= now:
            needs_attention(db, row)
            db.commit()
            raise HTTPException(409, "customer renewal candidate expired; reconnect required")
    account = row.external_id
    key = quota_key(reader, row)
    limit = quota(db, key, now)
    due = max(utc(limit.due_at), utc(limit.lease_until) if limit.lease_until else now)
    if due > now:
        db.commit()
        return DeferredRead(due)
    fence = uuid4().hex
    limit.due_at, limit.lease_until, limit.fence = now + SPACING, now + LEASE, fence
    checkpoint.state = {"issue": "refreshing", "proof": "proving", "read": "reading"}[phase]
    checkpoint.fence, checkpoint.lease_until = fence, now + LEASE
    db.commit()
    page = None
    issued = None
    proved = None
    failure: CRMReadError | None = None
    try:
        if phase == "issue":
            issued = reader.issue_refresh(cast(str, refresh))
        elif phase == "proof":
            assert pending is not None
            proved = reader.prove_refresh(pending, account)
        else:
            access = bundle.get("access_token")
            if not isinstance(access, str) or not access:
                raise CRMReadError("crm_grant_invalid")
            page = reader.page(account, access, progress["cursor"], now)
            if page.account_id != account:
                raise CRMReadError("crm_account_mismatch")
            if page.next_cursor is not None and digest(page.next_cursor) in progress["seen"]:
                raise CRMReadError("crm_cursor_repeated")
    except CRMReadError as exc:
        failure = exc
    completed = max(now, reader.clock())
    row = connection(db, workspace_id, connection_id, generation, provider)
    checkpoint = db.get(CRMCheckpoint, connection_id, populate_existing=True)
    limit = quota(db, key, now)
    if limit.fence == fence:
        limit.lease_until, limit.fence = None, None
        limit.due_at = max(utc(limit.due_at), completed + SPACING)
        if isinstance(failure, CRMRateLimited):
            limit.due_at = max(
                utc(limit.due_at), completed + timedelta(seconds=failure.retry_after)
            )
    if (
        checkpoint is None
        or checkpoint.fence != fence
        or checkpoint.generation != generation
        or checkpoint.grant_digest != digest(row.encrypted_grant or "")
        or checkpoint.lease_until is None
        or utc(checkpoint.lease_until) <= completed
    ):
        db.commit()
        raise HTTPException(409, "customer context attempt superseded")
    checkpoint.fence, checkpoint.lease_until = None, None
    if failure:
        if isinstance(failure, (CRMInvalidGrant, CRMProofRejected)):
            needs_attention(db, row)
            db.commit()
            raise HTTPException(409, "customer grant rejected; reconnect required") from None
        if phase == "issue":
            # Even a token endpoint 429/5xx may follow issuance. Without a documented
            # no-effect guarantee do not replay a possibly consumed refresh token.
            needs_attention(db, row, uncertain=True)
            db.commit()
            raise HTTPException(
                409, "customer renewal outcome unknown; reconnect required"
            ) from None
        if isinstance(failure, CRMAuthenticationUnavailable):
            if phase == "proof" or progress.get("auth_retried") or not refresh:
                needs_attention(db, row)
                db.commit()
                raise HTTPException(
                    409, "customer authorization rejected; reconnect required"
                ) from None
            progress["refresh_required"] = True
        elif str(failure) in {"crm_scope_mismatch", "crm_account_mismatch"} and phase == "proof":
            needs_attention(db, row)
            db.commit()
            raise HTTPException(
                409, "customer renewal identity rejected; reconnect required"
            ) from None
        checkpoint.state = "proof_ready" if phase == "proof" else "ready"
        checkpoint.encrypted_progress = vault.seal(workspace_id, provider, context(row), progress)
        delay = failure.retry_after if isinstance(failure, CRMRateLimited) else 60
        due = max(utc(limit.due_at), completed + timedelta(seconds=delay))
        row.next_attempt_at, row.error_code = due, "crm_read_backoff"
        db.commit()
        if isinstance(failure, (CRMRateLimited, CRMAuthenticationUnavailable)) or phase == "proof":
            return DeferredRead(due)
        raise failure
    row.next_attempt_at, row.error_code = None, None
    if phase == "issue":
        assert issued is not None
        progress["candidate"] = candidate_payload(issued)
        checkpoint.state = "proof_ready"
    elif phase == "proof":
        assert proved is not None
        if (
            len(proved.accounts) != 1
            or proved.accounts[0].external_id != account
            or (proved.expires_at is not None and proved.expires_at <= completed)
        ):
            needs_attention(db, row)
            db.commit()
            raise HTTPException(409, "customer renewal proof invalid")
        row.encrypted_grant = vault.seal(
            workspace_id,
            provider,
            row.id,
            {
                "access_token": proved.access_token.get_secret_value(),
                "refresh_token": proved.refresh_token.get_secret_value()
                if proved.refresh_token
                else None,
                "expires_at": proved.expires_at.isoformat() if proved.expires_at else None,
            },
        )
        checkpoint.grant_digest = digest(row.encrypted_grant)
        progress.pop("candidate")
        progress.pop("refresh_required", None)
        progress["auth_retried"] = True
        checkpoint.state = "ready"
    else:
        assert page is not None
        receipt = uuid4().hex
        progress.pop("auth_retried", None)
        progress["pending_next"], progress["receipt"] = page.next_cursor, digest(receipt)
        checkpoint.encrypted_progress = vault.seal(workspace_id, provider, context(row), progress)
        checkpoint.state, checkpoint.lease_until = "awaiting_ack", now + LEASE
        db.commit()
        return PageDelivery(page, receipt)
    checkpoint.encrypted_progress = vault.seal(workspace_id, provider, context(row), progress)
    due = utc(limit.due_at)
    row.next_attempt_at = due
    db.commit()
    return DeferredRead(due)


def acknowledge_page(
    db: Session,
    workspace_id: int,
    connection_id: str,
    generation: int,
    receipt: str,
    now: datetime,
    *,
    provider: CustomerProvider = "klaviyo",
) -> None:
    row = connection(db, workspace_id, connection_id, generation, provider)
    checkpoint = db.get(CRMCheckpoint, connection_id, populate_existing=True)
    if (
        checkpoint is None
        or checkpoint.generation != generation
        or checkpoint.grant_digest != digest(row.encrypted_grant or "")
    ):
        raise HTTPException(409, "customer context acknowledgement unavailable")
    if checkpoint.ack_digest == digest(receipt):
        db.commit()
        return
    vault = SourceVault()
    progress = vault.open(workspace_id, provider, context(row), checkpoint.encrypted_progress)
    if (
        checkpoint.state != "awaiting_ack"
        or checkpoint.lease_until is None
        or utc(checkpoint.lease_until) <= now
        or progress.get("receipt") != digest(receipt)
    ):
        raise HTTPException(409, "customer context acknowledgement unavailable")
    cursor = progress.pop("pending_next")
    progress.pop("receipt")
    progress["cursor"] = cursor
    progress["pages"] += 1
    if cursor is not None:
        progress["seen"].append(digest(cursor))
    checkpoint.encrypted_progress = vault.seal(workspace_id, provider, context(row), progress)
    checkpoint.state = "done" if cursor is None else "ready"
    checkpoint.ack_digest, checkpoint.fence, checkpoint.lease_until = digest(receipt), None, None
    db.commit()
