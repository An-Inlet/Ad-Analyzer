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


@router.get("/app/workspace-export", include_in_schema=False)
def customer_workspace_export() -> FileResponse:
    return FileResponse(STATIC / "workspace-export.html", media_type="text/html")


@router.get("/app/workspace-closure", include_in_schema=False)
@router.get("/app/workspace-closure/{workspace_id}/{request_id}", include_in_schema=False)
def customer_workspace_closure() -> FileResponse:
    return FileResponse(STATIC / "workspace-closure.html", media_type="text/html")


@router.get("/app/activity", include_in_schema=False)
def customer_activity() -> FileResponse:
    return FileResponse(STATIC / "activity.html", media_type="text/html")


@router.get("/app/measurement-history", include_in_schema=False)
def customer_measurement_history() -> FileResponse:
    return FileResponse(STATIC / "measurement-history.html", media_type="text/html")


@router.get("/app/execution", include_in_schema=False)
@router.get("/app/execution/{workspace_id}/{run_id}", include_in_schema=False)
def customer_execution() -> FileResponse:
    return FileResponse(STATIC / "execution.html", media_type="text/html")


@router.get("/app/social-configuration", include_in_schema=False)
def customer_social_configuration() -> FileResponse:
    return FileResponse(STATIC / "social-configuration.html", media_type="text/html")


@router.get("/app/optimization", include_in_schema=False)
@router.get("/app/optimization/{workspace_id}/{run_id}", include_in_schema=False)
def customer_optimization() -> FileResponse:
    return FileResponse(STATIC / "optimization.html", media_type="text/html")
