"""Owned queue and local publication boundaries. Provider IO belongs to the worker."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import HTTPException
from sqlalchemy import Engine, delete, select, text
from sqlalchemy.orm import Session

from app.commerce.acquisition_contracts import (
    AcquisitionIntent,
    AcquisitionProfile,
    AcquisitionRecovery,
    AcquisitionRecoveryItem,
    AcquisitionStatus,
    Checkpoint,
    NativeHandles,
    initial_checkpoint,
)
from app.commerce.acquisition_handles import open_handles, seal_handles
from app.commerce.acquisition_models import (
    CommerceAcquisitionCheckpoint as CheckpointRow,
)
from app.commerce.acquisition_models import (
    CommerceAcquisitionJob as Job,
)
from app.commerce.acquisition_models import (
    CommerceAcquisitionSeen as Seen,
)
from app.commerce.acquisition_runtime import require_owned_controls
from app.commerce.evidence import digest, lock_workspace
from app.commerce.independent_contracts import ScanRequest, ScanUnavailable
from app.commerce.independent_owned import OwnedAcquisition
from app.customers.access import CustomerPrincipal
from app.customers.identity import IdentityProvider
from app.customers.models import CustomerSession, CustomerUser
from app.goals.models import Goal, GoalRevision
from app.goals.schemas import GoalDefinition
from app.settings import Settings
from app.shopify.models import ShopifyConnection
from app.shopify.security import Vault, utc


def now() -> datetime:
    return datetime.now(UTC)


def identity_digest(principal: CustomerPrincipal) -> str:
    return digest(
        [
            "inlet.acquisition-original-identity.v1",
            principal.user.id,
            principal.user.issuer,
            principal.user.subject,
        ]
    )


def bind_job(job: Job) -> tuple[ScanRequest, AcquisitionProfile]:
    request = ScanRequest.model_validate(job.request)
    profile = AcquisitionProfile.model_validate(job.profile)
    if (
        request.request_digest != job.request_digest
        or profile.digest() != job.profile_digest
        or (
            request.acquisition_id,
            request.scope.workspace_id,
            request.scope.store_id,
            request.scope.goal_id,
            request.scope.goal_revision,
            request.connection_id,
        )
        != (
            job.id,
            job.workspace_id,
            job.store_id,
            job.goal_id,
            job.goal_revision,
            job.integration_id,
        )
        or utc(job.deadline_at)
        != utc(job.created_at) + timedelta(seconds=profile.limits.lifetime_seconds)
    ):
        raise ScanUnavailable("acquisition_binding_invalid")
    return request, profile


def owned_service(
    engine: Engine,
    job: Job,
    identity: IdentityProvider,
    settings: Settings,
    clock: Callable[[], datetime],
    db: Session,
) -> OwnedAcquisition:
    user = db.get(CustomerUser, job.actor_id, populate_existing=True)
    session = db.get(CustomerSession, job.session_digest, populate_existing=True)
    if user is None or session is None or session.user_id != user.id:
        raise ScanUnavailable("acquisition_authority_unavailable")
    principal = CustomerPrincipal(user, session)
    if (
        identity_digest(principal) != job.identity_digest
        or session.authenticated_at != job.authenticated_at
        or job.environment not in {"contract_test", "live"}
    ):
        raise ScanUnavailable("acquisition_authority_unavailable")
    environment: Literal["contract_test", "live"] = (
        "live" if job.environment == "live" else "contract_test"
    )
    return OwnedAcquisition(
        lambda: Session(engine), principal, identity, settings, environment=environment, clock=clock
    )


def erase_staging(db: Session, job: Job) -> None:
    for model in (CheckpointRow, Seen):
        db.execute(
            delete(model).where(model.job_id == job.id, model.workspace_id == job.workspace_id)
        )


def terminal(
    db: Session, job: Job, state: str, code: str | None, clock: Callable[[], datetime]
) -> None:
    job.state, job.error_code = state, code
    job.lease_token = job.lease_until = None
    job.terminal_at = utc(clock())
    job.cleanup_at = job.terminal_at + timedelta(hours=24)
    erase_staging(db, job)


def enqueue(
    engine: Engine,
    principal: CustomerPrincipal,
    identity: IdentityProvider,
    settings: Settings,
    profile: AcquisitionProfile,
    environment: Literal["live", "contract_test"],
    wid: int,
    intent: AcquisitionIntent,
    clock: Callable[[], datetime] = now,
) -> str:
    service = OwnedAcquisition(
        lambda: Session(engine), principal, identity, settings, environment=environment, clock=clock
    )
    with Session(engine) as db:
        if db.get_bind().dialect.name == "sqlite" and db.scalar(text("PRAGMA foreign_keys")) != 1:
            raise ScanUnavailable("acquisition_storage_unavailable")
        require_owned_controls(db, settings, wid, environment)
        service._authorize(db, wid)
        goal = db.get(Goal, intent.goal_id)
        revision = db.get(GoalRevision, (intent.goal_id, intent.expected_goal_revision))
        if (
            goal is None
            or revision is None
            or goal.workspace_id != wid
            or goal.revision != intent.expected_goal_revision
        ):
            raise HTTPException(409, "acquisition_goal_changed")
        sid = GoalDefinition.model_validate(revision.definition).store_id
    request = service.capture(
        wid, sid, intent.goal_id, intent.expected_goal_revision, intent.start, intent.end
    )
    with Session(engine) as db:
        if db.get_bind().dialect.name == "sqlite" and db.scalar(text("PRAGMA foreign_keys")) != 1:
            raise ScanUnavailable("acquisition_storage_unavailable")
        require_owned_controls(db, settings, wid, environment)
        service._check(db, request)
        current = db.scalar(
            select(Job)
            .where(
                Job.workspace_id == wid, Job.store_id == sid, Job.state.in_(("pending", "running"))
            )
            .with_for_update()
        )
        if current is not None:
            saved, _ = bind_job(current)
            if (
                current.actor_id == principal.user.id
                and current.session_digest == principal.session.digest
                and saved.scope == request.scope
                and (saved.start, saved.end) == (request.start, request.end)
                and current.profile_digest == profile.digest()
                and utc(current.deadline_at) > utc(clock())
            ):
                return current.id
            raise HTTPException(409, "acquisition_active_conflict")
        native = db.scalar(
            select(ShopifyConnection).where(
                ShopifyConnection.workspace_id == wid, ShopifyConnection.commerce_store_id == sid
            )
        )
        assert native is not None
        created = utc(clock())
        deadline = created + timedelta(seconds=profile.limits.lifetime_seconds)
        job = Job(
            id=request.acquisition_id,
            workspace_id=wid,
            store_id=sid,
            native_connection_id=native.id,
            integration_id=request.connection_id,
            goal_id=intent.goal_id,
            goal_revision=intent.expected_goal_revision,
            actor_id=principal.user.id,
            session_digest=principal.session.digest,
            authenticated_at=principal.session.authenticated_at,
            identity_digest=identity_digest(principal),
            environment=environment,
            request=request.model_dump(mode="json"),
            request_digest=request.request_digest,
            profile=profile.model_dump(mode="json"),
            profile_digest=profile.digest(),
            state="pending",
            created_at=created,
            deadline_at=deadline,
            due_at=created,
            step_sequence=0,
            request_attempts=0,
            requests_completed=0,
            charged_bytes=0,
            response_bytes=0,
        )
        db.add(job)
        db.flush()
        checkpoint = initial_checkpoint(request, profile)
        handles = NativeHandles(
            order_ids=(),
            last_order_number="0",
            order_cursor=None,
            agreement_cursor=None,
            sale_cursor=None,
            agreement_id=None,
        )
        db.add(
            CheckpointRow(
                job_id=job.id,
                workspace_id=wid,
                phase=checkpoint.phase,
                sequence=0,
                state_document=checkpoint.model_dump(mode="json"),
                state_digest=checkpoint.digest(),
                updated_at=created,
                encrypted_handles=seal_handles(
                    Vault(settings), request, checkpoint, handles, deadline_at=deadline
                ),
            )
        )
        db.flush()
        service._check(db, request)
        db.commit()
        return job.id


def checkpoint_state(
    db: Session, job: Job, settings: Settings, clock: Callable[[], datetime]
) -> tuple[CheckpointRow, Checkpoint, NativeHandles]:
    request, _ = bind_job(job)
    row = db.scalar(
        select(CheckpointRow)
        .where(CheckpointRow.job_id == job.id, CheckpointRow.workspace_id == job.workspace_id)
        .with_for_update()
    )
    if row is None:
        raise ScanUnavailable("acquisition_checkpoint_unavailable")
    state = Checkpoint.model_validate(row.state_document)
    if (
        state.digest() != row.state_digest
        or state.sequence != row.sequence
        or state.sequence != job.step_sequence
        or state.phase != row.phase
        or state.request_digest != job.request_digest
        or state.profile_digest != job.profile_digest
    ):
        raise ScanUnavailable("acquisition_checkpoint_invalid")
    handles = open_handles(
        Vault(settings),
        request,
        state,
        row.encrypted_handles,
        deadline_at=utc(job.deadline_at),
        now=utc(clock()),
    )
    return row, state, handles


def status(
    engine: Engine,
    principal: CustomerPrincipal,
    identity: IdentityProvider,
    settings: Settings,
    wid: int,
    identifier: str,
    *,
    cancel: bool = False,
    clock: Callable[[], datetime] = now,
) -> AcquisitionStatus:
    with Session(engine) as db:
        lock_workspace(db, wid, active=True)
        job = db.scalar(select(Job).where(Job.id == identifier, Job.workspace_id == wid))
        if (
            job is None
            or job.actor_id != principal.user.id
            or job.session_digest != principal.session.digest
        ):
            raise HTTPException(404, "acquisition_unavailable")
        service = owned_service(engine, job, identity, settings, clock, db)
        request, _ = bind_job(job)
        service._authorize(db, wid)
        if job.state in {"pending", "running"} and not cancel:
            service._check(db, request)
        db.execute(
            select(Job.id).where(Job.id == job.id, Job.workspace_id == wid).with_for_update()
        )
        if cancel and job.state in {"pending", "running"}:
            terminal(db, job, "cancelled", None, clock)
        checkpoint = db.get(CheckpointRow, job.id)
        result = AcquisitionStatus.model_validate(
            dict(
                job_id=job.id,
                state=job.state,
                phase=checkpoint.phase if checkpoint else None,
                deadline_at=utc(job.deadline_at),
                publication_id=job.publication_id,
                error_code=job.error_code,
            )
        )
        service._authorize(db, wid)
        if cancel:
            db.commit()
        return result


def recover(
    engine: Engine,
    principal: CustomerPrincipal,
    identity: IdentityProvider,
    settings: Settings,
    wid: int,
    goal_id: str,
    *,
    clock: Callable[[], datetime] = now,
) -> AcquisitionRecovery:
    """Bounded operational metadata, not current source readiness or replay authority."""
    owner = OwnedAcquisition(
        lambda: Session(engine),
        principal,
        identity,
        settings,
        environment=settings.independent_acquisition_environment,
        clock=clock,
    )  # Authorization has no environment/provider IO; each saved request binds its own environment.
    with Session(engine) as db:
        owner._authorize(db, wid)
        goal = db.get(Goal, goal_id)
        if goal is None or goal.workspace_id != wid:
            raise HTTPException(404, "acquisition_unavailable")
        revision = db.get(GoalRevision, (goal.id, goal.revision))
        if revision is None:
            raise HTTPException(409, "acquisition_goal_changed")
        sid = GoalDefinition.model_validate(revision.definition).store_id
        rows = list(
            db.scalars(
                select(Job)
                .where(
                    Job.workspace_id == wid,
                    Job.goal_id == goal_id,
                    Job.store_id == sid,
                    Job.actor_id == principal.user.id,
                    Job.session_digest == principal.session.digest,
                )
                .order_by(Job.created_at.desc(), Job.id.desc())
                .limit(21)
            )
        )
        items = []
        for job in rows[:20]:
            request, _ = bind_job(job)
            checkpoint = db.get(CheckpointRow, job.id)
            items.append(
                AcquisitionRecoveryItem(
                    goal_id=job.goal_id,
                    goal_revision=job.goal_revision,
                    start=request.start,
                    end=request.end,
                    status=AcquisitionStatus(
                        job_id=job.id,
                        state=job.state,
                        phase=checkpoint.phase if checkpoint else None,
                        deadline_at=utc(job.deadline_at),
                        publication_id=job.publication_id,
                        error_code=job.error_code,
                    ),
                )
            )
        owner._authorize(db, wid)
        return AcquisitionRecovery(
            workspace_id=wid,
            goal_id=goal_id,
            items=tuple(items),
            truncated=len(rows) > 20,
        )
