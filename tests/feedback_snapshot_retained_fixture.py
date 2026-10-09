"""Current snapshot contracts over one genuine immutable original receipt."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from app import advertising_capabilities
from app.database.session import Base
from app.settings import Settings
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.candidate_receipt_fixture import load_receipt_candidate, retained_receipt_source

EXTRA_HISTORY = (
    "spending_mandates", "spending_mandate_revisions", "mandate_actions", "mandate_audits",
    "customer_campaign_drafts", "customer_campaign_revisions", "customer_media_objects",
)


def history(engine: Engine) -> dict[str, list[dict[str, Any]]]:
    assert advertising_capabilities.advertising_writes_enabled() is False
    with engine.connect() as connection:
        return {
            table.name: [dict(row) for row in connection.execute(
                select(table).order_by(*table.primary_key.columns)
            ).mappings()]
            for table in Base.metadata.sorted_tables
            if table.name.startswith("provider_") or table.name in EXTRA_HISTORY
        }


@pytest.fixture
def snapshot_receipt_source(
    customer_engine: Engine, tmp_path: Path, configuration: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Engine]:
    from tests import test_feedback_snapshot as consumer

    # Original commerce setup enables this same test-local read setting.
    configuration.shopify_measurement_enabled = True
    with retained_receipt_source(customer_engine, tmp_path / "snapshot-source") as (engine, ids, _):
        before = history(engine)
        for name in (
            "provider_execution_attempts", "provider_execution_responses",
            "provider_execution_receipts", "provider_exposure_reservations",
        ):
            assert len(before[name]) == 1
            assert before[name][0]["workspace_id"] == ids.workspace_id
        assert before["provider_execution_receipts"][0]["id"] == ids.receipt_id
        calls: list[Any] = []

        def source(
            db: Session, config: Settings, path: Path,
            with_receipt: bool = False, provider: str = "google_ads",
        ) -> Any:
            assert with_receipt is True and provider == "google_ads"
            assert db.get_bind() is engine and config is configuration
            result = load_receipt_candidate(db, ids)
            calls.append(result[-1])
            assert not result[-1].writes
            return result

        with monkeypatch.context() as scoped:
            scoped.setattr(consumer, "fixture", source)
            try:
                yield engine
            finally:
                assert len(calls) == 1 and not calls[0].writes
                assert history(engine) == before
