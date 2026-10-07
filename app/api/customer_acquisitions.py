"""Customer-owned independent read jobs; no caller source facts or maturity flags."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import Engine

from app.commerce import acquisition_runtime as runtime
from app.commerce import acquisition_service as service
from app.commerce.acquisition_contracts import (
    AcquisitionIntent,
    AcquisitionRecovery,
    AcquisitionStatus,
)
from app.commerce.independent_contracts import ScanUnavailable
from app.customers.access import Database, MutationPrincipal, Principal, Provider
from app.settings import settings

router = APIRouter(
    prefix="/api/customer/v1/workspaces/{workspace_id}/commerce/acquisitions", tags=["customer"]
)


def engine_for(db: Database) -> Engine:
    engine = db.get_bind()
    if not isinstance(engine, Engine):
        raise HTTPException(409, "acquisition_runtime_unavailable")
    return engine


@router.post("", response_model=AcquisitionStatus)
def enqueue(
    workspace_id: int,
    body: AcquisitionIntent,
    db: Database,
    principal: MutationPrincipal,
    provider: Provider,
    response: Response,
) -> AcquisitionStatus:
    response.headers["Cache-Control"] = "no-store"
    engine = engine_for(db)
    try:
        profile = runtime.load_profile(settings)
        if profile is None or not runtime.enabled(engine, settings):
            raise HTTPException(409, "acquisition_runtime_unavailable")
        # This route owns the dependency transaction; private service transactions
        # must not compete with its auth read locks. Capture loaded identity first.
        _ = principal.user.issuer, principal.user.subject, principal.session.authenticated_at
        db.expunge(principal.user)
        db.expunge(principal.session)
        db.rollback()
        identifier = service.enqueue(
            engine,
            principal,
            provider,
            settings,
            profile,
            settings.independent_acquisition_environment,
            workspace_id,
            body,
            clock=runtime.utcnow,
        )
        return service.status(
            engine, principal, provider, settings, workspace_id, identifier, clock=runtime.utcnow
        )
    except ScanUnavailable as exc:
        raise HTTPException(409, exc.code) from None


@router.get("/{identifier}", response_model=AcquisitionStatus)
def read(
    workspace_id: int,
    identifier: str,
    db: Database,
    principal: Principal,
    provider: Provider,
    response: Response,
) -> AcquisitionStatus:
    response.headers["Cache-Control"] = "no-store"
    engine = engine_for(db)
    db.expunge(principal.user)
    db.expunge(principal.session)
    db.rollback()
    try:
        return service.status(
            engine, principal, provider, settings, workspace_id, identifier, clock=runtime.utcnow
        )
    except ScanUnavailable as exc:
        raise HTTPException(409, exc.code) from None


@router.post("/{identifier}/cancel", response_model=AcquisitionStatus)
def cancel(
    workspace_id: int,
    identifier: str,
    db: Database,
    principal: MutationPrincipal,
    provider: Provider,
    response: Response,
) -> AcquisitionStatus:
    response.headers["Cache-Control"] = "no-store"
    engine = engine_for(db)
    db.expunge(principal.user)
    db.expunge(principal.session)
    db.rollback()
    try:
        return service.status(
            engine,
            principal,
            provider,
            settings,
            workspace_id,
            identifier,
            cancel=True,
            clock=runtime.utcnow,
        )
    except ScanUnavailable as exc:
        raise HTTPException(409, exc.code) from None


@router.get("", response_model=AcquisitionRecovery)
def recover(
    workspace_id: int,
    goal_id: Annotated[str, Query(pattern=r"^[a-f0-9]{32}$")],
    db: Database,
    principal: Principal,
    provider: Provider,
    response: Response,
) -> AcquisitionRecovery:
    response.headers["Cache-Control"] = "no-store"
    engine = engine_for(db)
    _ = principal.user.issuer, principal.user.subject, principal.session.authenticated_at
    db.expunge(principal.user)
    db.expunge(principal.session)
    db.rollback()
    try:
        return service.recover(
            engine, principal, provider, settings, workspace_id, goal_id, clock=runtime.utcnow
        )
    except ScanUnavailable as exc:
        raise HTTPException(409, exc.code) from None
