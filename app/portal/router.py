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
