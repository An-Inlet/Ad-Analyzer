"""Copy existing commerce snapshot aggregates into conservative consumer inputs.

The caller reads store/snapshot consistently in its existing authorized transaction.
This function performs no queries, writes, collection or privacy-retention changes.
"""

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Literal

from app.commerce.ledger import DEFINITION
from app.commerce.reporting import MeasurementWindow
from app.outcomes.contracts import Coverage, MetricBasis, Observation, SourceScope, Window
from app.outcomes.evaluator import canonical

if TYPE_CHECKING:
    from app.commerce.models import CommerceSnapshot, CommerceStore


def utc(value: datetime) -> datetime:
    # Existing SQLite timestamp columns omit tzinfo; their storage convention is UTC.
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def project_commerce_snapshot(
    snapshot: "CommerceSnapshot",
    store: "CommerceStore",
    *,
    workspace_id: int,
    privacy: Literal["available", "invalidated", "unknown"],
) -> Observation:
    result = snapshot.result
    if snapshot.store_id != store.id or store.workspace_id != workspace_id:
        raise ValueError("commerce snapshot owner mismatch")
    window = MeasurementWindow.model_validate(result.get("window"))
    local = Window.local(window.start, window.end, window.time_zone)
    if (
        result.get("source") != "shopify"
        or result.get("definition") != DEFINITION
        or result.get("store_id") != store.id
        or result.get("revision") != snapshot.revision
        or result.get("currency") != window.currency
        or result.get("time_zone") != window.time_zone
        or utc(snapshot.starts_at) != local.start_utc
        or utc(snapshot.ends_at) != local.end_utc
        or utc(snapshot.as_of).isoformat() != canonical(datetime.fromisoformat(result["as_of"]))
    ):
        raise ValueError("commerce snapshot basis mismatch")
    # Currency/time-zone changes cannot be retroactively applied to a saved snapshot.
    reasons = set(result.get("reasons", ()))
    reasons.add("historical_manifest_unavailable")
    if (store.currency, store.time_zone) != (window.currency, window.time_zone):
        reasons.add("source_basis_changed")
    if store.status != "active":
        reasons.add("source_error")
    if store.revision != snapshot.revision:
        reasons.add("source_correction_pending")
    value = result.get("net_sales_micros") if result.get("quality") == "complete" else None
    if isinstance(value, bool) or (value is not None and not isinstance(value, int)):
        raise ValueError("integer commerce amount required")
    if privacy != "available" or store.status == "revoked":
        value = None
        privacy = "invalidated" if store.status == "revoked" else privacy
    definition_digest = hashlib.sha256(DEFINITION.encode()).hexdigest()
    # Digest only the explicit projected aggregate: never copy customer/order keys or
    # arbitrary caller-supplied result fields into the outcome document.
    observation = Observation(
        source=SourceScope(
            workspace_id=workspace_id,
            provider="shopify",
            connection_id=store.connection_id,
            source_id=store.id,
            generation=None,
        ),
        basis=MetricBasis(
            definition=DEFINITION,
            definition_digest=definition_digest,
            currency=window.currency,
            unit="micros",
            grain="store",
            entity_id=store.id,
            time_zone=window.time_zone,
            time_basis=window.time_basis,
            attribution="not_applicable_store_total",
            attribution_digest=None,
            maturity_policy=None,
        ),
        window=local,
        snapshot_id=snapshot.id,
        snapshot_digest="0" * 64,
        data_revision=snapshot.revision,
        as_of=utc(snapshot.as_of),
        value=Decimal(value) if value is not None else None,
        coverage=Coverage(
            complete=False,
            covered_days=(),
            zero_days=(),
            mature_through=None,
            fresh_through=datetime.fromisoformat(result["source_watermark"])
            if result.get("source_watermark")
            else None,
            correction_state="unknown",
            reasons=tuple(sorted(reasons)),
        ),
        privacy=privacy,
    )
    from app.outcomes.evaluator import fingerprint

    # No digest recursion: the projection hash fixes snapshot_digest to its sentinel.
    return observation.model_copy(update={"snapshot_digest": fingerprint(observation)})
