"""Availability of platform outcomes, separate from business-outcome measurement."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ads.enums import AdvertisingPlatform


def has_platform_conversion_metrics(
    session: Session,
    account_id: int,
    platform: AdvertisingPlatform,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
) -> bool:
    if platform == AdvertisingPlatform.GOOGLE_ADS:
        return True
    if platform != AdvertisingPlatform.META_ADS:
        return False
    # An unselected event uses storage placeholders, not observed zero outcomes.
    from app.meta.models import MetaConnection

    statement = select(MetaConnection.id).where(
        MetaConnection.account_id == account_id,
        MetaConnection.conversion_action_type.is_not(None),
        MetaConnection.covered_from.is_not(None),
        MetaConnection.covered_through.is_not(None),
        MetaConnection.last_sync_at.is_not(None),
    )
    if date_from is not None:
        statement = statement.where(MetaConnection.covered_from <= date_from)
    if date_to is not None:
        statement = statement.where(MetaConnection.covered_through >= date_to)
    return session.scalar(statement.limit(1)) is not None


def has_platform_conversion_value_metrics(
    session: Session,
    account_id: int,
    platform: AdvertisingPlatform,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
) -> bool:
    if platform == AdvertisingPlatform.GOOGLE_ADS:
        return True
    if platform != AdvertisingPlatform.META_ADS:
        return False
    from app.meta.models import MetaConnection
    from app.meta.security import PURCHASE_ACTIONS

    return (
        has_platform_conversion_metrics(
            session, account_id, platform, date_from=date_from, date_to=date_to
        )
        and session.scalar(
            select(MetaConnection.id)
            .where(
                MetaConnection.account_id == account_id,
                MetaConnection.conversion_action_type.in_(PURCHASE_ACTIONS),
            )
            .limit(1)
        )
        is not None
    )
