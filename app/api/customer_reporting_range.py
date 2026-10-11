"""Explicit owned aggregate-range reads; default injected runtime remains unavailable."""

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.customer_reporting import Runtime
from app.campaign_performance.selected_storage import SelectedReportingUnavailable
from app.customers.access import Database, MutationPrincipal, Provider
from app.google_connections.http import GoogleReadError
from app.google_connections.range_http import GoogleAggregateRangeUnavailable
from app.google_connections.range_publication import RangeIntent, RangeView, acquire_range
from app.google_connections.selected_customer import SelectedCustomerService

router = APIRouter(
    prefix="/api/customer/v1/workspaces/{workspace_id}/reporting/google", tags=["customer"]
)


@router.post("/aggregate-range", response_model=RangeView)
def acquire(
    workspace_id: int,
    intent: RangeIntent,
    db: Database,
    principal: MutationPrincipal,
    provider: Provider,
    runtime: Runtime,
    response: Response,
) -> RangeView:
    response.headers["Cache-Control"] = "no-store"
    engine = db.get_bind()
    service = SelectedCustomerService(
        principal, provider, workspace_id, runtime, sessions=lambda: Session(engine)
    )
    db.rollback()
    try:
        return acquire_range(service, intent)
    except (
        SelectedReportingUnavailable,
        GoogleAggregateRangeUnavailable,
        GoogleReadError,
        ValueError,
    ):
        raise HTTPException(409, "reporting_range_unavailable") from None
