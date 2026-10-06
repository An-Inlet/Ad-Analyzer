"""Request-bound export leases and fresh authorization, separate from snapshot reads."""

import hashlib
import threading
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any, BinaryIO
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.customers.access import CustomerPrincipal
from app.customers.identity import IdentityProvider, denied
from app.customers.models import CustomerMembership, CustomerSession, CustomerUser
from app.lifecycle.archive import encoded
from app.lifecycle.models import LifecycleRequest, LifecycleStep
from app.lifecycle.quiescing import owner
from app.shopify.security import utc
from app.workspaces.models import Workspace

SLOTS = threading.BoundedSemaphore(2)
BUILD_LEASE_SECONDS = 180
STREAM_SECONDS = 300


class Authority:
    def __init__(
        self,
        engine: Engine,
        principal: CustomerPrincipal,
        provider: IdentityProvider,
        wid: int,
        request_id: str,
    ) -> None:
        self.engine, self.provider = engine, provider
        self.user_id, self.session_digest = principal.user.id, principal.session.digest
        self.wid, self.request_id = wid, request_id
        self.revision: int | None = None
        self.fence: str | None = None

    def check(self) -> None:
        # One fresh READ COMMITTED transaction per check; never the export snapshot/session.
        with Session(self.engine) as db:
            user = db.get(CustomerUser, self.user_id)
            session = db.get(CustomerSession, self.session_digest)
            member = db.get(CustomerMembership, (self.user_id, self.wid))
            workspace = db.get(Workspace, self.wid)
            row = db.get(LifecycleRequest, self.request_id)
            if (
                user is None
                or session is None
                or user.status != "active"
                or user.issuer != self.provider.issuer
                or session.user_id != user.id
                or session.revoked_at is not None
                or session.expires_at <= int(time.time())
            ):
                raise denied()
            if (
                workspace is None
                or workspace.status not in {"active", "closing"}
                or member is None
                or member.status != "active"
                or member.role != "owner"
                or row is None
                or row.workspace_id != self.wid
                or row.operation != "export"
                or row.requested_by != self.user_id
            ):
                raise HTTPException(404, "export unavailable")
            if self.revision is not None and (
                row.revision != self.revision or row.fence != self.fence
            ):
                raise HTTPException(409, "export attempt superseded")
            self.provider.check_active(user.subject, session.authenticated_at)
            if session.expires_at <= int(time.time()):
                raise denied()
            # Observe local revocation during potentially slow provider IO, using
            # a new transaction rather than the ORM identity map or snapshot.
            db.rollback()
            accepted = db.scalar(
                select(CustomerSession.digest)
                .join(CustomerUser, CustomerUser.id == CustomerSession.user_id)
                .join(CustomerMembership, CustomerMembership.user_id == CustomerUser.id)
                .join(Workspace, Workspace.id == CustomerMembership.workspace_id)
                .join(LifecycleRequest, LifecycleRequest.workspace_id == Workspace.id)
                .where(
                    CustomerSession.digest == self.session_digest,
                    CustomerSession.user_id == self.user_id,
                    CustomerSession.revoked_at.is_(None),
                    CustomerSession.expires_at > int(time.time()),
                    CustomerUser.status == "active",
                    CustomerUser.issuer == self.provider.issuer,
                    CustomerMembership.workspace_id == self.wid,
                    CustomerMembership.role == "owner",
                    CustomerMembership.status == "active",
                    Workspace.status.in_(["active", "closing"]),
                    LifecycleRequest.id == self.request_id,
                    LifecycleRequest.requested_by == self.user_id,
                    LifecycleRequest.operation == "export",
                    *(
                        [
                            LifecycleRequest.revision == self.revision,
                            LifecycleRequest.fence == self.fence,
                        ]
                        if self.revision is not None
                        else []
                    ),
                )
            )
            if accepted is None:
                raise denied()

    def claim(self) -> tuple[int, str]:
        with Session(self.engine) as db:
            user, session = (
                db.get(CustomerUser, self.user_id),
                db.get(CustomerSession, self.session_digest),
            )
            if user is None or session is None:
                raise denied()
            owner(db, CustomerPrincipal(user, session), self.provider, self.wid)
            row = db.scalar(
                select(LifecycleRequest)
                .where(LifecycleRequest.id == self.request_id)
                .with_for_update()
            )
            if (
                row is None
                or row.workspace_id != self.wid
                or row.operation != "export"
                or row.requested_by != self.user_id
            ):
                raise HTTPException(404, "export unavailable")
            step = db.get(LifecycleStep, (row.id, "export_build"))
            now = datetime.now(UTC)
            if step is not None and step.lease_until is not None and utc(step.lease_until) > now:
                raise HTTPException(409, "export build already running")
            row.revision += 1
            row.fence, row.state, row.blockers = uuid4().hex, "building", []
            if step is None:
                step = LifecycleStep(
                    request_id=row.id, step_key="export_build", workspace_id=self.wid, attempts=0
                )
                db.add(step)
            step.request_revision, step.fence = row.revision, row.fence
            step.state, step.evidence_digest = "running", None
            step.lease_until = now + timedelta(seconds=BUILD_LEASE_SECONDS)
            step.attempts += 1
            self.revision, self.fence = row.revision, row.fence
            db.commit()
            return self.revision, self.fence

    def finish(self, manifest: dict[str, Any] | None) -> None:
        # Failure bookkeeping must work after revocation; it cannot authorize reads or delivery.
        with Session(self.engine) as db:
            db.scalar(select(Workspace).where(Workspace.id == self.wid).with_for_update())
            row = db.scalar(
                select(LifecycleRequest)
                .where(LifecycleRequest.id == self.request_id)
                .with_for_update()
            )
            step = db.get(LifecycleStep, (self.request_id, "export_build"))
            if (
                row is None
                or step is None
                or row.revision != self.revision
                or row.fence != self.fence
            ):
                raise HTTPException(409, "export attempt superseded")
            if (
                step.state != "running"
                or step.lease_until is None
                or utc(step.lease_until) <= datetime.now(UTC)
            ):
                raise HTTPException(409, "export build lease expired")
            if manifest is None:
                row.state, step.state = "interrupted", "blocked"
                row.blockers = [{"code": "export_build_interrupted"}]
            else:
                row.updated_at = datetime.fromisoformat(manifest["snapshot_as_of"])
                row.state, step.state = "archive_built", "complete"
                step.evidence_digest = hashlib.sha256(encoded(manifest)).hexdigest()
                row.blockers = [
                    {
                        "code": "export_snapshot",
                        **{
                            key: manifest[key]
                            for key in (
                                "snapshot_revision",
                                "snapshot_as_of",
                                "supported_customer_data_complete",
                                "media_archive_complete",
                                "all_stored_workspace_data_complete",
                            )
                        },
                    }
                ]
            step.lease_until = None
            db.commit()


class Download:
    """Idempotent cleanup supports both iterator cancellation and response background fallback."""

    def __init__(self, file: BinaryIO, authority: Authority) -> None:
        self.file, self.authority = file, authority
        self.started = time.monotonic()
        self.lock = threading.Lock()
        self.closed = False

    def close(self) -> None:
        with self.lock:
            if not self.closed:
                self.closed = True
                self.file.close()
                SLOTS.release()

    def chunks(self) -> Iterator[bytes]:
        try:
            while True:
                if time.monotonic() - self.started >= STREAM_SECONDS:
                    raise RuntimeError("export stream expired")
                self.authority.check()
                chunk = self.file.read(64 * 1024)
                if not chunk:
                    return  # Delivery remains unconfirmed even on clean iterator exhaustion.
                yield chunk
        finally:
            self.close()
