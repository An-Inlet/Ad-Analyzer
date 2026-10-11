"""Explicit selected-report acquisition, injected runtime only and no ad writes."""

from fastapi import APIRouter, HTTPException, Response
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.customer_reporting import Runtime, boundary
from app.customers.access import Database, MutationPrincipal, Provider
from app.google_connections.selected_acquisition import CaptureIntent, CaptureView, acquire_selected
from app.google_connections.selected_collection import GoogleSelectedCollectionUnavailable
from app.google_connections.selected_customer import SelectedCustomerService

router = APIRouter(
    prefix="/api/customer/v1/workspaces/{workspace_id}/reporting/google", tags=["customer"]
)


@router.post("/captures", response_model=CaptureView)
def acquire(
    workspace_id: int,
    intent: CaptureIntent,
    db: Database,
    principal: MutationPrincipal,
    provider: Provider,
    runtime: Runtime,
    response: Response,
) -> CaptureView:
    with boundary(response):
        engine = db.get_bind()
        service = SelectedCustomerService(
            principal, provider, workspace_id, runtime, sessions=lambda: Session(engine)
        )
        db.rollback()
        with service.open(intent.account_id, read=True):
            pass
        try:
            return acquire_selected(service, intent)
        except (GoogleSelectedCollectionUnavailable, ValidationError):
            raise HTTPException(409, "reporting_capture_unavailable") from None
