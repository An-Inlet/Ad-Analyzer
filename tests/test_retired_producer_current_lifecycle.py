"""Feasibility: actual pinned producer, CURRENT schema/export/privacy/denial code."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from app.advertising_capabilities import AdvertisingWritesDisabled
from app.initial_planning.invalidation import erase_workspace_observations
from app.initial_planning.models import PreviewRow
from app.lifecycle.contracts import LifecycleScopeV1
from app.lifecycle.inventory import export_section
from app.publication import optimization
from app.publication.execution_models import (
    ProviderExecutionAttempt,
    ProviderExecutionReview,
    ProviderExposureReservation,
)
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.retired_producer_fixture import retained_review_fixture
from tests.test_customer_identity import customer_engine as customer_engine

pytestmark = pytest.mark.planning_boundary


def test_genuine_archived_producer_rows_use_current_lifecycle(
    customer_engine: Engine, tmp_path: Path,
) -> None:
    with retained_review_fixture(customer_engine, tmp_path / "seed") as (engine, result):
        with Session(engine) as db:
            scope = LifecycleScopeV1(workspace_id=result.workspace_id)
            before = export_section(db, scope, "initial_preview_reviews")
            assert len(before["rows"]) == 1
            assert before["rows"][0]["review_id"] == result.review_id
            assert export_section(db, LifecycleScopeV1(workspace_id=scope.workspace_id + 1),
                                  "initial_preview_reviews")["rows"] == []
            assert db.get(PreviewRow, result.preview_id) is not None
            assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 1
            with pytest.raises(AdvertisingWritesDisabled):
                optimization.claim_step(
                    db, scope.workspace_id, result.run_id, result.actor_id,
                    cast(Any, None), lambda: datetime.now(UTC),
                )
            erase_workspace_observations(db, scope.workspace_id)
            db.commit()
        with Session(engine) as db:
            assert db.get(PreviewRow, result.preview_id) is None
            assert db.get(ProviderExecutionReview, result.review_id) is not None
            hold = db.get(ProviderExposureReservation, result.reservation_id)
            assert hold is not None and hold.state == "held"
            after = export_section(db, scope, "initial_preview_reviews")["rows"]
            assert len(after) == 1
            erased = {
                "preview_id", "preview_workspace_id", "preview_account_id", "preview_campaign_id"
            }
            assert all(after[0][key] is None for key in erased)
            assert {key: value for key, value in after[0].items() if key not in erased} == {
                key: value for key, value in before["rows"][0].items() if key not in erased
            }
            assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 1
