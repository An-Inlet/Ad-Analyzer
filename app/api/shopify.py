from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.auth import require_api_token
from app.api.intelligence import workspace_or_404
from app.database.session import get_db
from app.shopify.reporting import sales_report

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_slug}/shopify",
    tags=["Shopify sales"],
    dependencies=[Depends(require_api_token)],
)


@router.get("")
def sales(workspace_slug: str, db: Annotated[Session, Depends(get_db)]) -> dict[str, Any]:
    return sales_report(db, workspace_or_404(db, workspace_slug).id)
