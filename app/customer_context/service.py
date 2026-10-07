"""Transient enrichment of existing canonical identities; no financial mutation path."""

from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.commerce.ledger import identity_key, lock_store
from app.commerce.models import CommerceOrder, CommerceSuppression
from app.customer_context.contracts import (
    ContextReader,
    CustomerProvider,
    FixtureIdentityMapping,
    ProfileContext,
)
from app.settings import settings
from app.shopify.privacy_identity import markers
from app.shopify.security import Vault
from app.sources.service import owned, token
from app.workspaces.models import WorkspaceIntegration


def preview(
    db: Session,
    workspace_id: int,
    provider: CustomerProvider,
    connection_id: str,
    generation: int,
    store_id: str,
    reader: ContextReader,
    mapping: FixtureIdentityMapping,
    now: datetime,
) -> dict[str, Any]:
    if (
        reader.mode != "fixture"
        or reader.provider != provider
        or type(mapping) is not FixtureIdentityMapping
    ):
        raise HTTPException(503, "customer context unavailable")
    row = owned(db, workspace_id, provider, connection_id)
    if row.generation != generation:
        raise HTTPException(409, "source generation unavailable")
    integration = db.get(WorkspaceIntegration, row.integration_id)
    if (
        integration is None
        or integration.status != "active"
        or integration.workspace_id != workspace_id
        or integration.provider != provider
    ):
        raise HTTPException(404, "customer context connection unavailable")
    store = lock_store(db, store_id, workspace_id)
    if markers(db, store):
        raise HTTPException(409, "customer context privacy reconciliation required")
    if (
        db.scalar(
            select(CommerceSuppression.object_key)
            .where(
                CommerceSuppression.workspace_id == workspace_id,
                CommerceSuppression.shop_key == store.shop_key,
            )
            .limit(1)
        )
        is not None
    ):
        raise HTTPException(409, "customer context privacy reconciliation required")
    grant = token(row, now)
    vault = Vault(settings)
    cursor, seen = None, set()
    profiles: dict[str, ProfileContext] = {}
    for _ in range(20):
        try:
            page = reader.page(row.external_id, grant, cursor, now)
        except Exception:
            raise HTTPException(502, "customer context read unavailable") from None
        if page.account_id != row.external_id:
            raise HTTPException(409, "customer context account mismatch")
        for profile in page.profiles:
            if profile.source_id in profiles and profiles[profile.source_id] != profile:
                raise HTTPException(409, "conflicting customer context")
            profiles[profile.source_id] = profile
        if page.next_cursor is None:
            break
        if page.next_cursor in seen:
            raise HTTPException(409, "repeated customer context cursor")
        cursor = page.next_cursor
        seen.add(cursor)
    else:
        raise HTTPException(409, "customer context capacity exceeded")
    result: dict[str, list[dict[str, Any]]] = {}
    unresolved = 0
    for source_id, profile in profiles.items():
        verified = mapping.mappings.get(source_id)
        if verified is None or verified.shop_key != store.shop_key:
            unresolved += 1
            continue
        key = identity_key(vault, store, "customer", verified.shopify_customer_id)
        if (
            db.scalar(
                select(CommerceOrder.order_key)
                .where(
                    CommerceOrder.workspace_id == workspace_id,
                    CommerceOrder.store_id == store.id,
                    CommerceOrder.customer_key == key,
                )
                .limit(1)
            )
            is None
        ):
            unresolved += 1
            continue
        value = profile.model_dump(mode="json", exclude={"source_id"})
        value["source_key"] = vault.digest(
            f"customer_context:{workspace_id}:{row.integration_id}", source_id
        )
        result.setdefault(key, []).append(value)
    return {
        "provider": provider,
        "mode": "fixture",
        "live_verified": False,
        "store_id": store.id,
        "customers": result,
        "unresolved_profiles": unresolved,
        "sales_contribution": "none",
        "persisted": False,
        "as_of": now.isoformat(),
    }
