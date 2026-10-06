"""One bounded child HTTP read per durable checkpoint advancement."""

import json
from typing import Any

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.ads.enums import AdvertisingPlatform
from app.ads.models import AdvertisingAccount
from app.imports.scope import AdvertisingImportScope, validate_advertising_scope
from app.meta.client import MetaClient, unpack_page
from app.meta.detail import DetailBatch, DetailMetric, InventoryAd, normalize_page, publish
from app.meta.models import MetaConnection, MetaDetailCheckpoint, MetaDetailStagedPage
from app.meta.security import MetaError


def clear(db: Session, connection_id: int) -> None:
    db.execute(
        delete(MetaDetailStagedPage).where(MetaDetailStagedPage.connection_id == connection_id)
    )
    db.execute(
        delete(MetaDetailCheckpoint).where(MetaDetailCheckpoint.connection_id == connection_id)
    )


def begin(db: Session, row: MetaConnection) -> None:
    assert row.window_start is not None and row.window_end is not None
    clear(db, row.id)
    db.add(
        MetaDetailCheckpoint(
            connection_id=row.id,
            workspace_id=row.workspace_id,
            account_id=row.account_id,
            integration_id=row.workspace_integration_id,
            generation=row.generation,
            window_start=row.window_start,
            window_end=row.window_end,
        )
    )
    db.flush()


def advance(
    db: Session,
    row: MetaConnection,
    account: AdvertisingAccount,
    checkpoint: MetaDetailCheckpoint,
    client: MetaClient,
    token: str,
) -> bool:
    """Caller holds native connection lock until commit; complete publish shares its transaction."""
    if (
        checkpoint.generation != row.generation
        or checkpoint.workspace_id != row.workspace_id
        or checkpoint.account_id != row.account_id
        or checkpoint.integration_id != row.workspace_integration_id
        or checkpoint.window_start != row.window_start
        or checkpoint.window_end != row.window_end
    ):
        raise MetaError("meta_detail_checkpoint_stale")
    scope = AdvertisingImportScope(
        row.workspace_id, checkpoint.integration_id, row.account_id, AdvertisingPlatform.META_ADS
    )
    validate_advertising_scope(db, scope)
    if checkpoint.phase != "complete":
        if checkpoint.page_count >= 300 or len(checkpoint.seen_cursors) >= 100:
            raise MetaError("meta_detail_capacity_exceeded")
        items, cursor = unpack_page(
            client.detail_page(
                row.external_account_id,
                token,
                checkpoint.phase,
                checkpoint.cursor,
                checkpoint.window_start,
                checkpoint.window_end,
            ),
            checkpoint.cursor,
        )
        inventory, metrics = normalize_page(
            items,
            checkpoint.phase,
            row.external_account_id,
            checkpoint.window_start,
            checkpoint.window_end,
            account.currency_code,
            row.conversion_action_type,
        )
        payload: dict[str, Any] = {
            "inventory": [item.model_dump(mode="json") for item in inventory],
            "metrics": [item.model_dump(mode="json") for item in metrics],
        }
        byte_count = len(json.dumps(payload, separators=(",", ":")).encode())
        if (
            checkpoint.row_count + len(items) > 30000
            or checkpoint.byte_count + byte_count > 16000000
        ):
            raise MetaError("meta_detail_capacity_exceeded")
        if cursor is not None and cursor in checkpoint.seen_cursors:
            raise MetaError("meta_invalid_cursor")
        checkpoint.page_count += 1
        checkpoint.row_count += len(items)
        checkpoint.byte_count += byte_count
        db.add(
            MetaDetailStagedPage(
                connection_id=row.id, page_number=checkpoint.page_count, payload=payload
            )
        )
        if cursor is not None:
            checkpoint.cursor = cursor
            checkpoint.seen_cursors = [*checkpoint.seen_cursors, cursor]
        else:
            checkpoint.phase = {
                "ads": "adset_insights",
                "adset_insights": "ad_insights",
                "ad_insights": "complete",
            }[checkpoint.phase]
            checkpoint.cursor, checkpoint.seen_cursors = None, []
        db.flush()
    if checkpoint.phase != "complete":
        return False
    inventory_all: list[InventoryAd] = []
    metrics_all: list[DetailMetric] = []
    for staged in db.scalars(
        select(MetaDetailStagedPage)
        .where(MetaDetailStagedPage.connection_id == row.id)
        .order_by(MetaDetailStagedPage.page_number)
    ):
        inventory_all.extend(
            InventoryAd.model_validate(item) for item in staged.payload["inventory"]
        )
        metrics_all.extend(DetailMetric.model_validate(item) for item in staged.payload["metrics"])
    batch = DetailBatch(
        complete=True,
        account_external_id=row.external_account_id,
        start=checkpoint.window_start,
        end=checkpoint.window_end,
        inventory=inventory_all,
        metrics=metrics_all,
    )
    try:
        publish(db, scope, batch)
    except HTTPException:
        raise MetaError("meta_detail_invalid_snapshot") from None
    clear(db, row.id)
    return True
