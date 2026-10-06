from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()
STATIC = Path(__file__).parent / "static"


@router.get("/app", include_in_schema=False)
@router.get("/app/", include_in_schema=False)
@router.get("/app/settings", include_in_schema=False)
def customer_application() -> FileResponse:
    # Public shell contains no customer data; all reads/mutations use scoped customer APIs.
    return FileResponse(STATIC / "index.html", media_type="text/html")


@router.get("/app/campaign-review", include_in_schema=False)
def customer_campaign_review() -> FileResponse:
    return FileResponse(STATIC / "campaign-review.html", media_type="text/html")


@router.get("/app/workspace-closure", include_in_schema=False)
@router.get("/app/workspace-closure/{workspace_id}/{request_id}", include_in_schema=False)
def customer_workspace_closure() -> FileResponse:
    return FileResponse(STATIC / "workspace-closure.html", media_type="text/html")


@router.get("/app/measurement-history", include_in_schema=False)
def customer_measurement_history() -> FileResponse:
    return FileResponse(STATIC / "measurement-history.html", media_type="text/html")
