from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ads.enums import AdvertisingPlatform
from app.ads.models import AdvertisingAccount
from app.meta.models import MetaConnection
from app.meta.security import CONVERSION_ACTIONS, PURCHASE_ACTIONS, utc

ATTRIBUTION_BASIS = (
    "Meta-reported campaign metrics using Meta's current attribution and reporting defaults. "
    "Clicks include all clicks. Only the explicitly selected action type is counted; overlapping "
    "action types are never added together. Reported purchase value is "
    "not verified sales or profit."
)


def connection_report(
    session: Session, workspace_id: int, *, now: datetime | None = None
) -> dict[str, Any]:
    now = utc(now or datetime.now(UTC))
    row = session.scalar(select(MetaConnection).where(MetaConnection.workspace_id == workspace_id))
    result: dict[str, Any] = {
        "connected": False,
        "ready": False,
        "status": "not_connected",
        "partial": False,
        "account_id": None,
        "account_name": None,
        "external_account_id": None,
        "currency_code": None,
        "time_zone": None,
        "last_sync_at": None,
        "next_attempt_at": None,
        "error_code": None,
        "covered_from": None,
        "covered_through": None,
        "conversion_action_type": None,
        "conversion_label": CONVERSION_ACTIONS[""],
        "conversions_available": False,
        "revenue_available": False,
        "attribution_basis": ATTRIBUTION_BASIS,
        "warnings": [
            "Connect one Meta ad account to analyze its spend and traffic. "
            "Other connections are optional."
        ],
    }
    if row is None:
        return result
    account = session.scalar(
        select(AdvertisingAccount).where(
            AdvertisingAccount.id == row.account_id,
            AdvertisingAccount.workspace_id == workspace_id,
            AdvertisingAccount.platform == AdvertisingPlatform.META_ADS,
            AdvertisingAccount.external_account_id == row.external_account_id,
        )
    )
    if account is None:
        return result
    latest_day = now.astimezone(ZoneInfo(account.time_zone or "UTC")).date() - timedelta(days=1)
    fresh = bool(
        row.last_sync_at
        and utc(row.last_sync_at) >= now - timedelta(hours=24)
        and row.covered_through
        and row.covered_through >= latest_day
    )
    completed = bool(row.last_sync_at and row.covered_from and row.covered_through)
    result.update(
        connected=True,
        ready=completed and fresh and row.status == "connected" and not row.error_code,
        status=row.status,
        partial=row.window_end is not None,
        phase=row.phase,
        account_id=account.id,
        account_name=account.name,
        external_account_id=account.external_account_id,
        currency_code=account.currency_code,
        time_zone=account.time_zone,
        last_sync_at=row.last_sync_at.isoformat() if row.last_sync_at else None,
        next_attempt_at=row.next_attempt_at.isoformat() if row.next_attempt_at else None,
        error_code=row.error_code,
        covered_from=row.covered_from.isoformat() if row.covered_from else None,
        covered_through=row.covered_through.isoformat() if row.covered_through else None,
        conversion_action_type=row.conversion_action_type,
        conversion_label=CONVERSION_ACTIONS.get(
            row.conversion_action_type or "", CONVERSION_ACTIONS[""]
        ),
        conversions_available=bool(row.conversion_action_type and completed),
        revenue_available=bool(row.conversion_action_type in PURCHASE_ACTIONS and completed),
        warnings=[],
    )
    if not completed:
        result["warnings"].append(
            "The first complete import is pending. Partial pages are not "
            "presented as complete performance."
        )
    elif not fresh:
        result["warnings"].append(
            "The latest completed Meta reporting day is not fully covered or the import is stale."
        )
    if row.window_end:
        result["warnings"].append(
            "An import is in progress. Performance retains the last complete "
            "snapshot until all pages finish."
        )
    if not row.conversion_action_type:
        result["warnings"].append(
            "Conversion and revenue metrics are unavailable because no "
            "conversion event was selected. Spend and traffic analysis still "
            "works."
        )
    if row.status == "reconnect_required":
        result["warnings"].append(
            "Meta authorization needs renewal. Reconnect this account to resume imports."
        )
    elif row.error_code:
        result["warnings"].append(
            "The latest refresh did not complete. Previous imported data is "
            "retained; retry after the indicated time."
        )
    return result
