"""Owned, CSRF-protected account observations independent of spending mandates."""

from fastapi import APIRouter, HTTPException, Response
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.ads.models import AdvertisingAccount
from app.billing.entitlements import paid_work
from app.collectors import account_diagnostics
from app.collectors.account_diagnostic_contracts import (
    AccountDiagnosticIntentV1,
    AccountDiagnosticViewV1,
)
from app.collectors.google_native_inventory import GoogleNativeInventoryUnavailable
from app.collectors.meta_native_inventory import MetaNativeInventoryUnavailable
from app.collectors.native_diagnostics import AccountDiagnosticRequest
from app.collectors.tiktok_native_inventory import TikTokNativeInventoryUnavailable
from app.customers.access import Database, MutationPrincipal, Provider
from app.google_connections.http import GoogleReadError
from app.publication import customer_intents
from app.publication.customer_authority import bind_authority
from app.publication.customer_runtime import utc_now
from app.publication.google_total_envelope_contracts import GoogleTotalEnvelopeViewV1
from app.settings import settings

router = APIRouter(prefix="/api/customer/v1/workspaces/{workspace_id}/execution", tags=["customer"])


@router.post("/diagnostics", response_model=AccountDiagnosticViewV1)
def read_account_diagnostics(
    workspace_id: int,
    body: AccountDiagnosticIntentV1,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    response: Response,
) -> AccountDiagnosticViewV1:
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
        account = db.get(AdvertisingAccount, body.account_id)
        if (
            current != scope
            or result.request.account != current
            or account is None
            or utc_now() >= result.expires_at
        ):
            raise HTTPException(409, "The account changed during this read. Please try again.")
        return account_diagnostics.project(result, account)
    except (
        GoogleNativeInventoryUnavailable,
        MetaNativeInventoryUnavailable,
        TikTokNativeInventoryUnavailable,
        GoogleReadError,
        ValidationError,
    ):
        raise HTTPException(
            409, "Account diagnostics could not be completed. Check your connection and try again."
        ) from None


@router.post("/runs/{run_id}/envelope-observation")
def read_total_envelope(
    workspace_id: int,
    run_id: str,
    principal: MutationPrincipal,
    provider: Provider,
    db: Database,
    response: Response,
) -> "GoogleTotalEnvelopeViewV1":
    from datetime import UTC, datetime, timedelta

    from app.collectors.google_native_inventory import GoogleNativeInventory
    from app.lifecycle.privacy import database_utc_now
    from app.publication.google_total_envelope_observation import (
        bind_owned_original_total_envelope,
        observe_total_envelope,
    )

    authorize = bind_authority(principal, provider)
    response.headers["Cache-Control"] = "no-store"

    def now() -> datetime:
        return max(utc_now(), database_utc_now(db))

    original = bind_owned_original_total_envelope(
        db, workspace_id, run_id, principal.user.id, authorize=authorize, clock=now
    )
    # This interval is only the collector's auxiliary reported-cost query. It is not
    # the campaign envelope period or a claim about covered liabilities.
    ended = now().replace(hour=0, minute=0, second=0, microsecond=0)
    request = AccountDiagnosticRequest(
        workspace_id=workspace_id,
        actor=principal.user.id,
        account_id=original.account.account.account_id,
        expected_account=original.account,
        starts_at=ended - timedelta(days=1),
        ends_at=ended,
    )
    engine = db.get_bind()
    db.rollback()
    try:
        with account_diagnostics.get_native_account_diagnostic_service(
            lambda: Session(engine), authorize, "google_ads", utc_now
        ) as service:
            result = service.read(request, utc_now())
        current = bind_owned_original_total_envelope(
            db, workspace_id, run_id, principal.user.id, authorize=authorize, clock=now
        )
        paid_work(db, workspace_id, now())
        if current != original or not isinstance(result, GoogleNativeInventory):
            raise HTTPException(409, "Original allocation or source evidence changed.")
        authorize(db, workspace_id, principal.user.id)
        session_expiry = datetime.fromtimestamp(principal.session.expires_at, UTC)
        return observe_total_envelope(current, result, now=now(), expires_at=session_expiry)
    except (GoogleNativeInventoryUnavailable, GoogleReadError, ValidationError):
        raise HTTPException(409, "The budget observation could not be completed.") from None
