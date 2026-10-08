"""Owned local planning catalog, independent of execution source qualification."""
from typing import Any

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import select

from app.ads.models import AdvertisingAccount
from app.customers.access import Database, Principal, Provider
from app.publication import customer_intents as intents
from app.publication.customer_authority import bind_authority

router = APIRouter(prefix="/api/customer/v1/workspaces/{workspace_id}/planning", tags=["customer"])


@router.get("/accounts")
def accounts(
    workspace_id: int, principal: Principal, provider: Provider, db: Database, response: Response
) -> dict[str, Any]:
    authorize = bind_authority(principal, provider)
    authorize(db, workspace_id, principal.user.id)
    rows = list(
        db.scalars(
            select(AdvertisingAccount)
            .where(AdvertisingAccount.workspace_id == workspace_id)
            .order_by(AdvertisingAccount.id)
            .limit(51)
        )
    )
    if len(rows) > 50:
        raise intents.unavailable("owned_account_catalog_limit")
    choices = []
    for row in rows:
        try:
            scope = intents.account(db, workspace_id, row.id)
        except HTTPException as exc:
            if exc.status_code not in {404, 409}:
                raise
            continue
        choices.append({"id": row.id, "name": row.name, "platform": scope.account.platform})
    authorize(db, workspace_id, principal.user.id)
    response.headers["Cache-Control"] = "no-store"
    return {"accounts": choices, "complete": True}
