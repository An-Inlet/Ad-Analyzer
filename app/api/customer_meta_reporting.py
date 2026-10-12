"""Count-only customer reporting; explicit injected runtime, no live default."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.customers.access import Database, MutationPrincipal, Principal, Provider
from app.google_connections.selected_customer import InvalidationIntent
from app.meta.selected_customer import (
    AvailableRangeIntent,
    AvailableRangeView,
    BasisIntent,
    MetaCaptureIntent,
    MetaCapturePrepareIntent,
    MetaCaptureView,
    MetaCustomerRuntime,
    MetaCustomerService,
    MetaOptionsView,
    MetaSelectionIntent,
    MetaSelectionView,
)

router = APIRouter(
    prefix="/api/customer/v1/workspaces/{workspace_id}/reporting/meta", tags=["customer"]
)


def get_meta_reporting_runtime() -> MetaCustomerRuntime | None:
    return None


Runtime = Annotated[MetaCustomerRuntime | None, Depends(get_meta_reporting_runtime)]


@contextmanager
def boundary(response: Response) -> Iterator[None]:
    response.headers["Cache-Control"] = "no-store"
    try:
        yield
    except ValueError:
        raise HTTPException(409, "meta_reporting_unavailable") from None


def service(
    db: Database, principal: Principal, provider: Provider, wid: int, runtime: Runtime
) -> MetaCustomerService:
    engine = db.get_bind()
    value = MetaCustomerService(principal, provider, wid, lambda: Session(engine), runtime)
    db.rollback()
    return value


@router.get("/event-selection", response_model=MetaSelectionView)
def state(
    workspace_id: int,
    db: Database,
    principal: Principal,
    provider: Provider,
    runtime: Runtime,
    response: Response,
    account_id: Annotated[str, Query(pattern=r"^[1-9][0-9]{0,9}$")],
) -> MetaSelectionView:
    if int(account_id) > 2**31 - 1:
        raise HTTPException(422, "invalid account")
    with boundary(response):
        return service(db, principal, provider, workspace_id, runtime).state(int(account_id))


@router.post("/available-range", response_model=AvailableRangeView)
def available(
    workspace_id: int,
    intent: AvailableRangeIntent,
    db: Database,
    principal: MutationPrincipal,
    provider: Provider,
    runtime: Runtime,
    response: Response,
) -> AvailableRangeView:
    with boundary(response):
        return service(db, principal, provider, workspace_id, runtime).available_range(intent)


@router.post("/event-options", response_model=MetaOptionsView)
def options(
    workspace_id: int,
    intent: BasisIntent,
    db: Database,
    principal: MutationPrincipal,
    provider: Provider,
    runtime: Runtime,
    response: Response,
) -> MetaOptionsView:
    with boundary(response):
        return service(db, principal, provider, workspace_id, runtime).options(intent)


@router.post("/event-selection", response_model=MetaSelectionView)
def confirm(
    workspace_id: int,
    intent: MetaSelectionIntent,
    db: Database,
    principal: MutationPrincipal,
    provider: Provider,
    runtime: Runtime,
    response: Response,
) -> MetaSelectionView:
    with boundary(response):
        return service(db, principal, provider, workspace_id, runtime).confirm(intent)


@router.post("/event-selection/invalidate", response_model=MetaSelectionView)
def invalidate(
    workspace_id: int,
    intent: InvalidationIntent,
    db: Database,
    principal: MutationPrincipal,
    provider: Provider,
    runtime: Runtime,
    response: Response,
) -> MetaSelectionView:
    with boundary(response):
        return service(db, principal, provider, workspace_id, runtime).invalidate(intent)


@router.post("/captures", response_model=MetaCaptureView)
def capture(
    workspace_id: int,
    intent: MetaCaptureIntent,
    db: Database,
    principal: MutationPrincipal,
    provider: Provider,
    runtime: Runtime,
    response: Response,
) -> MetaCaptureView:
    with boundary(response):
        return service(db, principal, provider, workspace_id, runtime).capture(intent)


@router.post("/capture-intents", response_model=MetaCaptureIntent)
def prepare_capture(
    workspace_id: int,
    intent: MetaCapturePrepareIntent,
    db: Database,
    principal: MutationPrincipal,
    provider: Provider,
    runtime: Runtime,
    response: Response,
) -> MetaCaptureIntent:
    with boundary(response):
        return service(db, principal, provider, workspace_id, runtime).prepare_capture(intent)
