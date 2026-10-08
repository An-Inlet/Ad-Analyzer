"""Owned, CSRF-protected account observations independent of spending mandates."""

from fastapi import APIRouter, HTTPException, Response
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.billing.entitlements import paid_work
from app.collectors import account_diagnostics
from app.collectors.google_native_inventory import GoogleNativeInventoryUnavailable
from app.collectors.meta_native_inventory import MetaNativeInventoryUnavailable
from app.collectors.native_diagnostics import AccountDiagnosticRequest
from app.collectors.tiktok_native_inventory import TikTokNativeInventoryUnavailable
from app.customers.access import Database, MutationPrincipal, Provider
from app.google_connections.http import GoogleReadError
from app.planning_catalog.contracts import TargetCatalogIntentV1, TargetCatalogV1
from app.planning_catalog.metadata_contracts import TargetCatalogV2
from app.planning_catalog.metadata_http import PlanningMetadataUnavailable
from app.planning_catalog.projection import project
from app.planning_catalog.projection_v2 import project_v2
from app.publication import customer_intents
from app.publication.customer_authority import bind_authority
from app.publication.customer_runtime import utc_now
from app.settings import settings

router = APIRouter(prefix="/api/customer/v1/workspaces/{workspace_id}/planning", tags=["customer"])


@router.post("/target-catalog", response_model=TargetCatalogV1)
def read_target_catalog(
    workspace_id: int,
    body: TargetCatalogIntentV1,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    response: Response,
) -> TargetCatalogV1:
    authorize = bind_authority(principal, provider)
    authorize(db, workspace_id, principal.user.id)
    response.headers["Cache-Control"] = "no-store"
    if not settings.customer_native_diagnostics_enabled:
        raise HTTPException(503, "Account diagnostics are not available yet.")
    scope = customer_intents.account(db, workspace_id, body.account_id)
    if body.ends_at > utc_now():
        raise HTTPException(422, "Choose an observation period that ends in the past.")
    request = AccountDiagnosticRequest(
        workspace_id=workspace_id,
        actor=principal.user.id,
        expected_account=scope,
        **body.model_dump(),
    )
    engine = db.get_bind()
    db.rollback()  # no API transaction/locks across token exchange or provider reads
    try:
        with account_diagnostics.get_native_account_diagnostic_service(
            lambda: Session(engine), authorize, scope.account.platform, utc_now
        ) as service:
            result = service.read(request, utc_now())
        authorize(db, workspace_id, principal.user.id)
        current = customer_intents.account(db, workspace_id, body.account_id)
        paid_work(db, workspace_id, utc_now())
        authorize(db, workspace_id, principal.user.id)
        if current != scope or result.request.account != current or utc_now() >= result.expires_at:
            raise HTTPException(409, "The account changed during this read. Please try again.")
        return project(result)
    except (
        GoogleNativeInventoryUnavailable,
        MetaNativeInventoryUnavailable,
        TikTokNativeInventoryUnavailable,
        GoogleReadError,
        ValidationError,
        ValueError,
    ):
        raise HTTPException(
            409, "Account diagnostics could not be completed. Check your connection and try again."
        ) from None


@router.post("/target-catalog-v2", response_model=TargetCatalogV2)
def read_target_catalog_v2(
    workspace_id: int,
    body: TargetCatalogIntentV1,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    response: Response,
) -> TargetCatalogV2:
    authorize = bind_authority(principal, provider)
    authorize(db, workspace_id, principal.user.id)
    response.headers["Cache-Control"] = "no-store"
    if not settings.customer_native_diagnostics_enabled:
        raise HTTPException(503, "Account diagnostics are not available yet.")
    scope = customer_intents.account(db, workspace_id, body.account_id)
    if body.ends_at > utc_now():
        raise HTTPException(422, "Choose an observation period that ends in the past.")
    request = AccountDiagnosticRequest(
        workspace_id=workspace_id,
        actor=principal.user.id,
        expected_account=scope,
        **body.model_dump(),
    )
    engine = db.get_bind()
    db.rollback()  # no API transaction/locks across token exchange or provider reads
    try:
        with account_diagnostics.get_native_account_diagnostic_service(
            lambda: Session(engine), authorize, scope.account.platform, utc_now
        ) as service:
            result, metadata = service.read_catalog(request, utc_now())
        authorize(db, workspace_id, principal.user.id)
        current = customer_intents.account(db, workspace_id, body.account_id)
        paid_work(db, workspace_id, utc_now())
        authorize(db, workspace_id, principal.user.id)
        if (
            current != scope
            or result.request.account != current
            or utc_now() >= min(result.expires_at, metadata.expires_at)
        ):
            raise HTTPException(409, "The account changed during this read. Please try again.")
        return project_v2(result, metadata)
    except (
        PlanningMetadataUnavailable,
        GoogleNativeInventoryUnavailable,
        MetaNativeInventoryUnavailable,
        TikTokNativeInventoryUnavailable,
        GoogleReadError,
        ValidationError,
        ValueError,
    ):
        raise HTTPException(
            409, "Account diagnostics could not be completed. Check your connection and try again."
        ) from None
