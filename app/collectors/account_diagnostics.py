"""Concrete per-request read-only assembly, with no execution runtime dependency."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.ads.models import AdvertisingAccount
from app.collectors.account_diagnostic_contracts import (
    AccountDiagnosticViewV1,
    DiagnosticInventoryCountV1,
    DiagnosticReasonV1,
)
from app.collectors.native_diagnostics import Inventory, NativeDiagnosticService
from app.google_connections.http import GoogleHTTPRead
from app.publication.execution_authorization import ExecutionAuthorizer
from app.settings import settings


def diagnostic_transport() -> httpx.BaseTransport:
    """Concrete fixed-endpoint clients use this low-level injection seam in tests."""
    return httpx.HTTPTransport(retries=0, trust_env=False)


class _BorrowedTransport(httpx.BaseTransport):
    """Collectors own short-lived clients; the composition owns their shared transport."""

    def __init__(self, transport: httpx.BaseTransport) -> None:
        self.transport = transport

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        return self.transport.handle_request(request)

    def close(self) -> None:
        pass


@contextmanager
def get_native_account_diagnostic_service(
    sessions: Callable[[], Session],
    authorize: ExecutionAuthorizer,
    platform: str,
    clock: Callable[[], datetime],
) -> Iterator[NativeDiagnosticService]:
    """Caller authorizes the owned scope before entering; service rechecks around IO."""
    if not settings.customer_native_diagnostics_enabled:
        raise HTTPException(503, "Account diagnostics are not available yet.")
    if platform not in {"google_ads", "meta_ads", "tiktok_ads"}:
        raise HTTPException(409, "Account diagnostics are unavailable for this connection.")
    oauth = None
    if platform == "google_ads" and (
        not settings.google_customer_client_id
        or settings.google_customer_client_secret is None
        or settings.google_customer_encryption_key is None
    ):
        raise HTTPException(503, "Account diagnostics are not available yet.")
    transport = diagnostic_transport()
    borrowed = _BorrowedTransport(transport)
    try:
        if platform == "google_ads":
            assert settings.google_customer_client_secret is not None
            oauth = GoogleHTTPRead(
                settings.google_customer_client_id,
                settings.google_customer_client_secret,
                settings.google_customer_developer_token,
                "v25",
                transport=borrowed,
            )
        yield NativeDiagnosticService(
            sessions, authorize, transports={platform: borrowed}, google_oauth=oauth, clock=clock
        )
    finally:
        transport.close()


def project(result: Inventory, account: AdvertisingAccount) -> AccountDiagnosticViewV1:
    from app.collectors.google_native_inventory import GoogleNativeInventory
    from app.collectors.meta_native_inventory import MetaNativeInventory

    counts = [DiagnosticInventoryCountV1(kind="campaign", count=len(result.campaigns))]
    if isinstance(result, GoogleNativeInventory):
        counts.extend(
            [
                DiagnosticInventoryCountV1(
                    kind="campaign_budget", count=len(result.campaign_budgets)
                ),
                DiagnosticInventoryCountV1(
                    kind="account_budget", count=len(result.account_budgets)
                ),
                DiagnosticInventoryCountV1(kind="billing_setup", count=len(result.billing_setups)),
            ]
        )
        complete = (
            result.advertising_inventory_read_complete and result.billing_inventory_read_complete
        )
    elif isinstance(result, MetaNativeInventory):
        counts.append(DiagnosticInventoryCountV1(kind="adset", count=len(result.adsets)))
        complete = result.advertising_inventory_read_complete
    else:
        counts.append(DiagnosticInventoryCountV1(kind="adgroup", count=len(result.adgroups)))
        complete = result.regular_inventory_read_complete
    reasons = [
        DiagnosticReasonV1(
            code="financial_bounds_unavailable",
            message="These observations do not establish a safe spending limit for optimization.",
        ),
        DiagnosticReasonV1(
            code="reporting_not_final",
            message="Provider reports do not establish that all spending has been reported.",
        ),
        DiagnosticReasonV1(
            code="external_changes_uncontrolled",
            message="Changes made outside Inlet are not controlled by this account read.",
        ),
    ]
    if not complete:
        reasons.append(
            DiagnosticReasonV1(
                code="inventory_incomplete",
                message="Some requested account inventory could not be read completely.",
            )
        )
    return AccountDiagnosticViewV1(
        account_id=account.id,
        account_name=(account.name or "Connected advertising account")[:160],
        platform=result.request.account.account.platform,
        observed_at=result.observed_at,
        expires_at=result.expires_at,
        inventory_counts=counts,
        read_complete=complete,
        reasons=reasons,
    )
