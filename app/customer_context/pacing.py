"""Acknowledged, one-page Klaviyo reads. No scheduler enrollment or profile storage."""

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import delete, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.customer_context.contracts import ContextPage
from app.customer_context.http import CRMRateLimited, CRMReadError, KlaviyoHTTPRead
from app.customer_context.models import CRMCheckpoint, CRMQuota
from app.settings import settings
from app.shopify.security import utc
from app.sources.models import SourceConnection
from app.sources.security import SourceVault
from app.sources.service import owned, token
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


def connection(db: Session, wid: int, cid: str, generation: int) -> SourceConnection:
    row = owned(db, wid, "klaviyo", cid)
    integration = db.get(WorkspaceIntegration, row.integration_id, populate_existing=True)
    if (
        row.generation != generation
        or row.status != "connected"
        or integration is None
        or integration.workspace_id != wid
        or integration.provider != "klaviyo"
        or integration.status != "active"
    ):
        raise HTTPException(409, "customer context connection unavailable")
    return row


def context(row: SourceConnection) -> str:
    return f"crm-progress:{row.id}:{row.generation}:{row.integration_id}:{row.external_id}"


def quota_key(reader: KlaviyoHTTPRead, row: SourceConnection) -> str:
    secret = settings.source_token_encryption_key
    if secret is None:
        raise HTTPException(503, "source encryption unavailable")
    payload = json.dumps(["crm-quota-v1", "klaviyo", reader.client_id, row.external_id])
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


def read_page(
    db: Session,
    workspace_id: int,
    connection_id: str,
    generation: int,
    reader: KlaviyoHTTPRead,
    now: datetime,
) -> PageDelivery | DeferredRead | None:
    """Return None when acknowledged complete; retry same page if no acknowledgement.

    The caller must own this transaction/session. Each reservation commits before HTTP.
    Only this boundary is paced; OAuth/refresh account proofs are not enrolled here.
    """
    if not isinstance(reader, KlaviyoHTTPRead) or reader.provider != "klaviyo":
        raise HTTPException(503, "paced customer context unavailable")
    prune_expired_quotas(db, now)
    row = connection(db, workspace_id, connection_id, generation)
    access = token(row, now)
    vault = SourceVault()
    grant_digest = digest(row.encrypted_grant or "")
    checkpoint = db.get(CRMCheckpoint, row.id)
    if checkpoint is None:
        checkpoint = CRMCheckpoint(connection_id=row.id)
        db.add(checkpoint)
    if checkpoint.generation != generation or checkpoint.grant_digest != grant_digest:
        checkpoint.generation = generation
        checkpoint.grant_digest = grant_digest
        checkpoint.encrypted_progress = vault.seal(
            workspace_id, "klaviyo", context(row), {"cursor": None, "seen": [], "pages": 0}
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
    progress = vault.open(workspace_id, "klaviyo", context(row), checkpoint.encrypted_progress)
    if progress["pages"] >= 20:
        raise HTTPException(409, "customer context page capacity exceeded")
    account = row.external_id
    key = quota_key(reader, row)
    limit = quota(db, key, now)
    due = max(utc(limit.due_at), utc(limit.lease_until) if limit.lease_until else now)
    if due > now:
        db.commit()
        return DeferredRead(due)
    fence = uuid4().hex
    limit.due_at, limit.lease_until, limit.fence = now + SPACING, now + LEASE, fence
    checkpoint.state, checkpoint.fence, checkpoint.lease_until = "reading", fence, now + LEASE
    db.commit()
    page = None
    failure: CRMReadError | None = None
    try:
        page = reader.page(account, access, progress["cursor"], now)
        if page.account_id != account:
            raise CRMReadError("crm_account_mismatch")
        if page.next_cursor is not None and digest(page.next_cursor) in progress["seen"]:
            raise CRMReadError("crm_cursor_repeated")
    except CRMReadError as exc:
        failure = exc
    completed = max(now, reader.clock())
    # Recheck ownership and generation after IO; late results cannot advance a new grant.
    row = connection(db, workspace_id, connection_id, generation)
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
    if failure:
        checkpoint.state, checkpoint.fence, checkpoint.lease_until = "ready", None, None
        due = utc(limit.due_at)
        db.commit()
        if isinstance(failure, CRMRateLimited):
            return DeferredRead(due)
        raise failure
    assert page is not None
    receipt = uuid4().hex
    progress["pending_next"] = page.next_cursor
    progress["receipt"] = digest(receipt)
    checkpoint.encrypted_progress = vault.seal(workspace_id, "klaviyo", context(row), progress)
    checkpoint.state = "awaiting_ack"
    db.commit()
    return PageDelivery(page, receipt)


def acknowledge_page(
    db: Session, workspace_id: int, connection_id: str, generation: int, receipt: str, now: datetime
) -> None:
    row = connection(db, workspace_id, connection_id, generation)
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
    progress = vault.open(workspace_id, "klaviyo", context(row), checkpoint.encrypted_progress)
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
    checkpoint.encrypted_progress = vault.seal(workspace_id, "klaviyo", context(row), progress)
    checkpoint.state = "done" if cursor is None else "ready"
    checkpoint.ack_digest, checkpoint.fence, checkpoint.lease_until = digest(receipt), None, None
    db.commit()
