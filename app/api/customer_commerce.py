"""Customer-scoped measurement previews and persisted as-of assessments."""

from typing import Any

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import select

from app.commerce.models import CommerceSnapshot, CommerceStore
from app.commerce.reporting import MeasurementWindow, measurement
from app.customers.access import Database, MutationPrincipal, Principal, customer_workspace
from app.shopify.security import ShopifyError

router = APIRouter(prefix="/api/customer/v1/workspaces/{workspace_id}/commerce", tags=["customer"])


@router.get("/stores")
def stores(
    workspace_id: int, principal: Principal, db: Database, response: Response
) -> list[dict[str, Any]]:
    customer_workspace(db, principal.user.id, workspace_id)
    response.headers["Cache-Control"] = "no-store"
    return [
        {
            "id": s.id,
            "status": s.status,
            "currency": s.currency,
            "time_zone": s.time_zone,
            "last_sync_at": s.last_sync_at,
            "error_code": s.error_code,
        }
        for s in db.scalars(select(CommerceStore).where(CommerceStore.workspace_id == workspace_id))
    ]


def assess(
    workspace_id: int,
    store_id: str,
    body: MeasurementWindow,
    principal: Any,
    db: Database,
    response: Response,
    *,
    persist: bool,
) -> dict[str, Any]:
    _, role = customer_workspace(db, principal.user.id, workspace_id)
    if persist and role not in {"owner", "admin", "analyst"}:
        raise HTTPException(403, "insufficient role")
    response.headers["Cache-Control"] = "no-store"
    try:
        result = measurement(db, workspace_id, store_id, body, snapshot=persist)
    except ShopifyError:
        raise HTTPException(404, "measurement source unavailable") from None
    except ValueError:
        raise HTTPException(422, "measurement basis does not match store") from None
    if persist:
        db.commit()
    return result


@router.post("/stores/{store_id}/preview")
def preview(
    workspace_id: int,
    store_id: str,
    body: MeasurementWindow,
    principal: MutationPrincipal,
    db: Database,
    response: Response,
) -> dict[str, Any]:
    return assess(workspace_id, store_id, body, principal, db, response, persist=False)


@router.post("/stores/{store_id}/snapshots", status_code=201)
def snapshot(
    workspace_id: int,
    store_id: str,
    body: MeasurementWindow,
    principal: MutationPrincipal,
    db: Database,
    response: Response,
) -> dict[str, Any]:
    return assess(workspace_id, store_id, body, principal, db, response, persist=True)


@router.get("/snapshots/{snapshot_id}")
def saved(
    workspace_id: int, snapshot_id: str, principal: Principal, db: Database, response: Response
) -> dict[str, Any]:
    customer_workspace(db, principal.user.id, workspace_id)
    item = db.scalar(
        select(CommerceSnapshot)
        .join(CommerceStore)
        .where(CommerceSnapshot.id == snapshot_id, CommerceStore.workspace_id == workspace_id)
    )
    if item is None:
        raise HTTPException(404, "snapshot not found")
    response.headers["Cache-Control"] = "no-store"
    return {**item.result, "snapshot_id": item.id}


@router.get("/stores/{store_id}/publications/latest")
def latest_publication(
    workspace_id: int, store_id: str, principal: Principal, db: Database, response: Response
) -> dict[str, Any]:
    return publication(workspace_id, store_id, None, principal, db, response)


@router.get("/stores/{store_id}/publications/{publication_id}")
def publication(
    workspace_id: int,
    store_id: str,
    publication_id: str | None,
    principal: Principal,
    db: Database,
    response: Response,
) -> dict[str, Any]:
    from app.commerce.evidence import read_publication

    customer_workspace(db, principal.user.id, workspace_id)
    response.headers["Cache-Control"] = "no-store"
    try:
        return read_publication(db, workspace_id, store_id, publication_id)
    except ShopifyError:
        raise HTTPException(404, "measurement publication unavailable") from None
