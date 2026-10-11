"""Customer-owned reporting selection; default runtime unavailable and no ad writes."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.campaign_performance.selected_storage import SelectedReportingUnavailable
from app.customers.access import Database, MutationPrincipal, Principal, Provider
from app.google_connections.selected_customer import (
    AccountIntent,
    InvalidationIntent,
    OptionsView,
    SelectedCustomerRuntime,
    SelectedCustomerService,
    SelectionIntent,
    SelectionView,
)

router = APIRouter(
    prefix="/api/customer/v1/workspaces/{workspace_id}/reporting/google", tags=["customer"]
)


def get_selected_customer_runtime() -> SelectedCustomerRuntime | None:
    """Explicit infrastructure injection only; no default live factory."""
    return None


Runtime = Annotated[SelectedCustomerRuntime | None, Depends(get_selected_customer_runtime)]


@contextmanager
def boundary(response: Response) -> Iterator[None]:
    response.headers["Cache-Control"] = "no-store"
    try:
        yield
    except SelectedReportingUnavailable:
        raise HTTPException(409, "reporting_selection_unavailable") from None


@router.post("/event-options", response_model=OptionsView)
def options(
    workspace_id: int,
    intent: AccountIntent,
    db: Database,
    principal: MutationPrincipal,
    provider: Provider,
    runtime: Runtime,
    response: Response,
) -> OptionsView:
    with boundary(response):
        engine = db.get_bind()
        service = SelectedCustomerService(
            principal, provider, workspace_id, runtime, sessions=lambda: Session(engine)
        )
        db.rollback()
        return service.options(intent)


@router.post("/event-selection", response_model=SelectionView)
def confirm(
    workspace_id: int,
    intent: SelectionIntent,
    db: Database,
    principal: MutationPrincipal,
    provider: Provider,
    runtime: Runtime,
    response: Response,
) -> SelectionView:
    with boundary(response):
        engine = db.get_bind()
        service = SelectedCustomerService(
            principal, provider, workspace_id, runtime, sessions=lambda: Session(engine)
        )
        db.rollback()
        return service.confirm(intent)


@router.get("/event-selection", response_model=SelectionView)
def state(
    workspace_id: int,
    db: Database,
    principal: Principal,
    provider: Provider,
    runtime: Runtime,
    response: Response,
    account_id: Annotated[str, Query(pattern=r"^[1-9][0-9]{0,9}$")],
) -> SelectionView:
    # Query text has no JSON integer type; reject signs, decimals, booleans, zero and
    # overflow explicitly before producing the strict internal positive integer.
    if int(account_id) > 2**31 - 1:
        raise HTTPException(422, "invalid account")
    with boundary(response):
        engine = db.get_bind()
        service = SelectedCustomerService(
            principal, provider, workspace_id, runtime, sessions=lambda: Session(engine)
        )
        db.rollback()
        with service.open(int(account_id), read=False) as owned:
            return service.state(owned, int(account_id))


@router.post("/event-selection/invalidate", response_model=SelectionView)
def invalidate(
    workspace_id: int,
    intent: InvalidationIntent,
    db: Database,
    principal: MutationPrincipal,
    provider: Provider,
    runtime: Runtime,
    response: Response,
) -> SelectionView:
    with boundary(response):
        engine = db.get_bind()
        service = SelectedCustomerService(
            principal, provider, workspace_id, runtime, sessions=lambda: Session(engine)
        )
        db.rollback()
        with service.open(intent.account_id, read=False) as owned:
            result = service.invalidate(owned, intent)
            owned.flush()
            service.guard(owned, intent.account_id)
            owned.commit()
            return result
