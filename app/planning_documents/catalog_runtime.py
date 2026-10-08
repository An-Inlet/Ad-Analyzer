"""Owned V2 reads with atomic catalog receipts and bounded independent maintenance."""

from collections.abc import Callable
from datetime import datetime

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.collectors import account_diagnostics
from app.collectors.google_native_inventory import GoogleNativeInventoryUnavailable
from app.collectors.meta_native_inventory import MetaNativeInventoryUnavailable
from app.collectors.native_diagnostics import AccountDiagnosticRequest
from app.collectors.tiktok_native_inventory import TikTokNativeInventoryUnavailable
from app.customers.access import CustomerPrincipal
from app.customers.identity import IdentityProvider
from app.google_connections.http import GoogleReadError
from app.planning_catalog.contracts import TargetCatalogIntentV1
from app.planning_catalog.metadata_contracts import TargetCatalogV2
from app.planning_catalog.metadata_http import PlanningMetadataUnavailable
from app.planning_documents import authority
from app.planning_documents.catalog_receipts import (
    CatalogReceiptUnavailable,
    cleanup_expired_unused_receipts,
    write_catalog_receipt,
)
from app.planning_documents.context import AccountRef
from app.planning_documents.evidence_local import resolve_source_fences
from app.planning_documents.read_context import PlanningReadContexts, snapshot
from app.publication import customer_intents
from app.settings import settings


def read_catalog_receipt(
    engine: Engine,
    provider: IdentityProvider,
    principal: CustomerPrincipal,
    workspace_id: int,
    intent: TargetCatalogIntentV1,
    clock: Callable[[], datetime],
) -> TargetCatalogV2:
    """Caller releases authentication transaction; never holds locks over provider IO."""
    principal = snapshot(principal)
    fact = authority.refresh(principal, provider)
    # Exactly one separately committed bounded maintenance batch per explicit read.
    # Later native/receipt failure does not undo deletion of expired unused receipts.
    with Session(engine) as db, db.begin():
        current = authority.lock(db, principal, workspace_id, fact)
        if not settings.customer_native_diagnostics_enabled:
            raise HTTPException(503, "Account diagnostics are not available yet.")
        if intent.ends_at > clock():
            raise HTTPException(422, "Choose an observation period that ends in the past.")
        scope = customer_intents.account(db, workspace_id, intent.account_id)
        account = AccountRef(
            workspace_id=workspace_id,
            account_id=intent.account_id,
            connection_id=scope.account.connection_id,
            platform=scope.account.platform,
            connection_version=scope.connection_version,
        )
        source = resolve_source_fences(db, principal=current, accounts=(account,), now=clock())[0]
        cleanup_expired_unused_receipts(db, workspace_id=workspace_id, now=clock(), limit=100)
        if resolve_source_fences(db, principal=current, accounts=(account,), now=clock()) != (
            source,
        ):
            raise HTTPException(409, "The account changed during maintenance. Read again.")
        authority.final(current, fact)
    reads = PlanningReadContexts(
        lambda: Session(engine), principal, provider, workspace_id, principal.user.id
    )
    request = AccountDiagnosticRequest(
        workspace_id=workspace_id,
        actor=principal.user.id,
        expected_account=scope,
        **intent.model_dump(),
    )
    try:
        with account_diagnostics.get_native_account_diagnostic_service(
            reads.open, reads.authorize, scope.account.platform, clock
        ) as service:
            inventory, metadata = service.read_catalog(request, clock())
        fact = authority.refresh(principal, provider)
        with Session(engine) as db, db.begin():
            current = authority.lock(db, principal, workspace_id, fact)
            if resolve_source_fences(db, principal=current, accounts=(account,), now=clock()) != (
                source,
            ):
                raise HTTPException(409, "The account changed during this read. Read again.")
            result = write_catalog_receipt(
                db,
                principal=current,
                source=source,
                inventory=inventory,
                metadata=metadata,
                now=clock(),
            )
            db.flush()
            if clock() >= result.expires_at:
                raise HTTPException(
                    409, "This catalog expired before it could be saved. Read again."
                )
            authority.final(current, fact)
        return result
    except CatalogReceiptUnavailable as error:
        detail = (
            "Catalog storage limit reached. Existing plans are preserved; additional target "
            "reads are unavailable."
            if error.reason == "capacity_exceeded"
            else "This catalog could not be retained. Read fresh targets before selecting them."
        )
        raise HTTPException(409, detail) from error
    except (
        PlanningMetadataUnavailable,
        GoogleNativeInventoryUnavailable,
        MetaNativeInventoryUnavailable,
        TikTokNativeInventoryUnavailable,
        GoogleReadError,
        ValidationError,
        ValueError,
    ) as error:
        raise HTTPException(
            409, "Account diagnostics could not be completed. Check your connection and try again."
        ) from error
