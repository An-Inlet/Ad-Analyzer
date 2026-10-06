"""Project actual persisted synthetic commerce snapshots on SQLite and PostgreSQL."""

from app.commerce.ledger import apply_order
from app.commerce.models import CommerceSnapshot
from app.commerce.privacy import remove_store
from app.commerce.reporting import measurement
from app.outcomes.commerce import project_commerce_snapshot
from app.settings import Settings
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW, agreement, setup, source, window
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_shopify_sales import configuration as configuration


def test_persisted_canonical_projection_and_privacy_invalidation(
    customer_engine: Engine, configuration: Settings
) -> None:
    with Session(customer_engine) as db:
        connection, store = setup(db, configuration)
        apply_order(db, store, connection, source(), [agreement()], configuration, NOW)
        result = measurement(db, store.workspace_id, store.id, window(), now=NOW, snapshot=True)
        db.commit()
        snapshot = db.get(CommerceSnapshot, result["snapshot_id"])
        assert snapshot is not None
        projected = project_commerce_snapshot(
            snapshot, store, workspace_id=store.workspace_id, privacy="available"
        )
        assert projected.value == 90_000_000
        assert projected.data_revision == store.revision
        assert "historical_manifest_unavailable" in projected.coverage.reasons
        remove_store(db, store.id)
        db.commit()
        assert db.scalar(select(CommerceSnapshot)) is None
        # Even an old in-memory snapshot cannot recover value against the current
        # revoked store. Callers must always check current privacy/source state.
        invalid = project_commerce_snapshot(
            snapshot, store, workspace_id=store.workspace_id, privacy="invalidated"
        )
        assert invalid.value is None and invalid.privacy == "invalidated"
