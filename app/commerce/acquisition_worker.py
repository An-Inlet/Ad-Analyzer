"""Fair bounded leased read steps; no transaction remains open during provider IO."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from time import monotonic
from uuid import uuid4

import httpx
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import Engine, delete, func, or_, select
from sqlalchemy.orm import Session

from app.commerce import acquisition_service as service
from app.commerce.acquisition_contracts import AcquisitionProfile, Checkpoint, NativeHandles
from app.commerce.acquisition_handles import seal_handles
from app.commerce.acquisition_models import CommerceAcquisitionJob as Job
from app.commerce.acquisition_models import CommerceAcquisitionSeen as Seen
from app.commerce.acquisition_runtime import require_owned_controls
from app.commerce.acquisition_step import execute_step
from app.commerce.evidence import lock_workspace
from app.commerce.independent_contracts import (
    ScanCompletion,
    ScanPermit,
    ScanRequest,
    ScanUnavailable,
)
from app.commerce.independent_owned import OwnedAcquisition
from app.customers.identity import IdentityProvider
from app.outcomes.maturity import ReconciledDay
from app.settings import Settings
from app.shopify.security import ShopifyError, Vault, utc


@dataclass(frozen=True)
class Claim:
    wid: int
    identifier: str
    token: str
    request: ScanRequest
    profile: AcquisitionProfile
    state: Checkpoint
    handles: NativeHandles
    owned: OwnedAcquisition
    started_at: datetime
    deadline_at: datetime


def _job(db: Session, wid: int, identifier: str, *, lock: bool = True) -> Job | None:
    lock_workspace(db, wid, active=True)
    query = select(Job).where(Job.id == identifier, Job.workspace_id == wid)
    return db.scalar(query.with_for_update() if lock else query)


def claim(
    engine: Engine,
    wid: int,
    identifier: str,
    identity: IdentityProvider,
    settings: Settings,
    profile: AcquisitionProfile,
    clock: Callable[[], datetime],
) -> Claim | None:
    with Session(engine) as db:
        job = _job(db, wid, identifier, lock=False)
        if job is None or job.state not in {"pending", "running"}:
            return None
        # Guard locks precede the queue row: workspace -> principal -> source -> job.
        # Session revocation may delete its jobs, so never hold a job while waiting
        # for the same user's/session's canonical authentication locks.
        try:
            owned = service.owned_service(engine, job, identity, settings, clock, db)
            request, saved_profile = service.bind_job(job)
            owned._check(db, request)
        except (ScanUnavailable, HTTPException, ShopifyError, ValidationError):
            job = _job(db, wid, identifier)
            if job is not None:
                service.terminal(db, job, "unavailable", "acquisition_authority_unavailable", clock)
                db.commit()
            return None
        job = _job(db, wid, identifier)
        current = utc(clock())
        if (
            job is None
            or job.state not in {"pending", "running"}
            or utc(job.due_at) > current
            or (job.lease_until is not None and utc(job.lease_until) > current)
        ):
            return None
        job.last_served_at = current
        if current >= utc(job.deadline_at):
            service.terminal(db, job, "expired", "acquisition_expired", clock)
            db.commit()
            return None
        try:
            require_owned_controls(db, settings, wid, job.environment)
            request, saved_profile = service.bind_job(job)
            if saved_profile != profile:
                job.due_at = current + timedelta(seconds=profile.backoff_seconds)
                job.error_code = "acquisition_configuration_unavailable"
                db.commit()
                return None
            owned = service.owned_service(engine, job, identity, settings, clock, db)
            owned._check(db, request)
            checkpoint_row, state, handles = service.checkpoint_state(db, job, settings, clock)
            current = utc(clock())
            if current >= utc(job.deadline_at):
                raise ScanUnavailable("acquisition_expired")
            if state.phase == "publish":
                values = {row.day: row for row in state.committed}
                days = tuple(
                    ReconciledDay(
                        day=request.start + timedelta(days=i),
                        state="complete",
                        value_micros=values[request.start + timedelta(days=i)].value_micros
                        if request.start + timedelta(days=i) in values
                        else 0,
                        entry_count=values[request.start + timedelta(days=i)].entry_count
                        if request.start + timedelta(days=i) in values
                        else 0,
                    )
                    for i in range((request.end - request.start).days)
                )
                if job.started_at is None:
                    raise ScanUnavailable("acquisition_checkpoint_invalid")
                completion = ScanCompletion(
                    request=request,
                    started_at=utc(job.started_at),
                    completed_at=utc(checkpoint_row.updated_at),
                    orders_enumerated=state.orders_enumerated,
                    agreements_enumerated=state.agreements_enumerated,
                    sales_enumerated=state.sales_enumerated,
                    requests_completed=job.requests_completed,
                    response_bytes=job.response_bytes,
                    days=days,
                )
                # The publication writer flushes before its own final authority check.
                # Roll back every publication/fence/job change together if that check
                # or any later boundary fails; only then persist unavailable cleanup.
                with db.begin_nested():
                    identifier = owned.publish_in_transaction(db, completion)
                    job.publication_id = identifier
                    service.terminal(db, job, "completed", None, clock)
                    db.flush()
                    if utc(clock()) >= utc(job.deadline_at):
                        raise ScanUnavailable("acquisition_expired")
                    require_owned_controls(db, settings, wid, job.environment)
                    owned._check(db, request)
                db.commit()
                return None
            reserve = profile.limits.response_bytes
            if (
                job.request_attempts >= profile.limits.requests
                or job.charged_bytes + reserve > profile.limits.total_bytes
            ):
                raise ScanUnavailable("acquisition_request_limit")
            job.request_attempts += 1
            job.charged_bytes += reserve
            job.started_at = job.started_at or current
            job.state = "running"
            job.lease_token = uuid4().hex
            job.lease_until = min(
                utc(job.deadline_at), current + timedelta(seconds=profile.lease_seconds)
            )
            result = Claim(
                wid,
                job.id,
                job.lease_token,
                request,
                profile,
                state,
                handles,
                owned,
                utc(job.started_at),
                utc(job.deadline_at),
            )
            db.commit()
            return result
        except (ScanUnavailable, HTTPException, ShopifyError, ValidationError) as exc:
            code = (
                exc.code
                if isinstance(exc, ScanUnavailable)
                else "acquisition_authority_unavailable"
            )
            service.terminal(db, job, "unavailable", code, clock)
            db.commit()
            return None


def perform(
    engine: Engine,
    claimed: Claim,
    settings: Settings,
    transport: httpx.BaseTransport,
    clock: Callable[[], datetime],
    monotonic_clock: Callable[[], float] = monotonic,
) -> bool:
    error: ScanUnavailable | None = None
    result = None

    def authority(request: ScanRequest, observed: datetime) -> ScanPermit:
        with Session(engine) as db:
            require_owned_controls(db, settings, claimed.wid, claimed.owned.environment)
        return claimed.owned.authority(request, observed)

    try:
        result = execute_step(
            claimed.request,
            claimed.state,
            claimed.handles,
            authority,
            claimed.profile,
            transport=transport,
            clock=clock,
            started_at=claimed.started_at,
            deadline_at=claimed.deadline_at,
            monotonic_clock=monotonic_clock,
        )
    except ScanUnavailable as exc:
        error = exc
    with Session(engine) as db:
        try:
            claimed.owned._check(db, claimed.request)
        except (ScanUnavailable, HTTPException, ShopifyError, ValidationError):
            job = _job(db, claimed.wid, claimed.identifier)
            if job is not None and job.lease_token == claimed.token:
                service.terminal(db, job, "unavailable", "acquisition_authority_unavailable", clock)
                db.commit()
            return False
        job = _job(db, claimed.wid, claimed.identifier)
        if (
            job is None
            or job.state != "running"
            or job.lease_token != claimed.token
            or job.step_sequence != claimed.state.sequence
        ):
            return False
        try:
            current = utc(clock())
            if (
                current >= utc(job.deadline_at)
                or job.lease_until is None
                or current >= utc(job.lease_until)
            ):
                raise ScanUnavailable("acquisition_expired")
            require_owned_controls(db, settings, claimed.wid, job.environment)
            claimed.owned._check(db, claimed.request)
            row, existing, _ = service.checkpoint_state(db, job, settings, clock)
            if existing != claimed.state:
                raise ScanUnavailable("acquisition_checkpoint_invalid")
            if error is not None:
                if error.code in {
                    "acquisition_throttled",
                    "acquisition_transport_unavailable",
                    "acquisition_http_unavailable",
                }:
                    job.due_at = current + timedelta(
                        seconds=error.retry_after or claimed.profile.backoff_seconds
                    )
                    job.error_code = error.code
                    job.lease_token = job.lease_until = None
                    db.commit()
                    return False
                raise error
            assert result is not None
            count = (
                db.scalar(select(func.count()).select_from(Seen).where(Seen.job_id == job.id)) or 0
            )
            if count + len(result.seen) > claimed.profile.seen_key_limit:
                raise ScanUnavailable("acquisition_identity_limit")
            for kind, key in result.seen:
                if db.get(Seen, (job.id, kind, key)) is not None:
                    raise ScanUnavailable("source_duplicate_identity")
                db.add(
                    Seen(
                        job_id=job.id, workspace_id=job.workspace_id, kind=kind, identity_digest=key
                    )
                )
            job.step_sequence = result.checkpoint.sequence
            job.requests_completed += 1
            job.response_bytes += result.response_bytes
            job.charged_bytes -= claimed.profile.limits.response_bytes - result.response_bytes
            job.lease_token = job.lease_until = None
            job.error_code = None
            job.due_at = current
            db.flush()  # Parent step sequence is current before checkpoint binding guard.
            row.phase, row.sequence = result.checkpoint.phase, result.checkpoint.sequence
            row.state_document, row.state_digest = (
                result.checkpoint.model_dump(mode="json"),
                result.checkpoint.digest(),
            )
            row.encrypted_handles = seal_handles(
                Vault(settings),
                claimed.request,
                result.checkpoint,
                result.handles,
                deadline_at=utc(job.deadline_at),
            )
            row.updated_at = current
            db.flush()
            require_owned_controls(db, settings, claimed.wid, job.environment)
            claimed.owned._check(db, claimed.request)
            db.commit()
            return True
        except (ScanUnavailable, HTTPException, ShopifyError, ValidationError) as exc:
            code = (
                exc.code
                if isinstance(exc, ScanUnavailable)
                else "acquisition_authority_unavailable"
            )
            service.terminal(db, job, "unavailable", code, clock)
            db.commit()
            return False


def cleanup(engine: Engine, clock: Callable[[], datetime] = service.now, limit: int = 100) -> int:
    """No credentials/identity/provider; remains callable while acquisition is disabled."""
    with Session(engine) as db:
        rows = list(
            db.execute(
                select(Job.workspace_id, Job.id)
                .where(
                    or_(
                        (Job.state.in_(("pending", "running"))) & (Job.deadline_at <= clock()),
                        Job.cleanup_at <= clock(),
                    )
                )
                .order_by(Job.created_at, Job.id)
                .limit(min(max(limit, 1), 100))
            )
        )
    changed = 0
    for wid, identifier in rows:
        with Session(engine) as db:
            # Closing workspaces must still permit erasure.
            lock_workspace(db, wid, active=False)
            job = db.scalar(
                select(Job).where(Job.id == identifier, Job.workspace_id == wid).with_for_update()
            )
            if job is None:
                continue
            current = utc(clock())
            if job.cleanup_at and utc(job.cleanup_at) <= current:
                db.execute(delete(Job).where(Job.id == identifier, Job.workspace_id == wid))
                changed += 1
            elif job.state in {"pending", "running"} and utc(job.deadline_at) <= current:
                service.terminal(db, job, "expired", "acquisition_expired", clock)
                changed += 1
            db.commit()
    return changed


def run_tick(
    engine: Engine,
    settings: Settings,
    identity: IdentityProvider,
    profile: AcquisitionProfile,
    transport_factory: Callable[[], httpx.BaseTransport],
    *,
    clock: Callable[[], datetime] = service.now,
    monotonic_clock: Callable[[], float] = monotonic,
    stop_requested: Callable[[], bool] = lambda: False,
) -> dict[str, int]:
    end = monotonic_clock() + profile.tick_time_budget_seconds
    attempted = completed = 0
    admitted: set[int] = set()
    cleanup(engine, clock)
    while (
        attempted < profile.tick_request_budget and monotonic_clock() < end and not stop_requested()
    ):
        with Session(engine) as db:
            current = utc(clock())
            rows = list(
                db.execute(
                    select(Job.workspace_id, Job.id)
                    .where(
                        Job.state.in_(("pending", "running")),
                        Job.due_at <= current,
                        Job.deadline_at > current,
                        or_(Job.lease_until.is_(None), Job.lease_until <= current),
                    )
                    .order_by(func.coalesce(Job.last_served_at, Job.created_at), Job.id)
                    .limit(501)
                )
            )
        round_seen: set[int] = set()
        progressed = False
        for wid, identifier in rows[:500]:
            if wid in round_seen or (
                wid not in admitted and len(admitted) >= profile.tick_workspace_budget
            ):
                continue
            if (
                attempted >= profile.tick_request_budget
                or end - monotonic_clock() < profile.step_io_timeout_seconds
                or stop_requested()
            ):
                break
            admitted.add(wid)
            round_seen.add(wid)
            attempted += 1  # Bounds local/admission work too; never an unbounded None loop.
            try:
                claimed = claim(engine, wid, identifier, identity, settings, profile, clock)
            except (HTTPException, ScanUnavailable):
                continue  # A concurrently erased/closing owner cannot stop another owner.
            if claimed is None:
                continue
            progressed = True
            if end - monotonic_clock() < profile.step_io_timeout_seconds or stop_requested():
                break  # Durable lease is retained; no emission after stop/budget boundary.
            try:
                transport = transport_factory()
            except Exception:
                # No provider request was emitted. Keep the charged crash reservation,
                # original deadline and generation; defer only this exact owned lease.
                with Session(engine) as db:
                    try:
                        job = _job(db, claimed.wid, claimed.identifier)
                    except HTTPException:
                        continue
                    if job is not None and job.lease_token == claimed.token:
                        job.lease_token = job.lease_until = None
                        job.due_at = utc(clock()) + timedelta(seconds=profile.backoff_seconds)
                        job.error_code = "acquisition_transport_unavailable"
                        db.commit()
                continue
            completed += int(perform(engine, claimed, settings, transport, clock, monotonic_clock))
        if not progressed:
            break
    return {"attempted": attempted, "completed_steps": completed}
