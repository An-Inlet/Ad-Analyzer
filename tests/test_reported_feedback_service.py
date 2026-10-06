from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.meta.models import MetaConnection
from app.reported_feedback.models import ReportedFeedbackJob
from app.reported_feedback.service import read_comparison_progress, request_comparison
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.reported_feedback_fixture import seeded
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_shopify_sales import configuration as configuration


def test_actual_receipt_admits_owned_idempotent_job(
    customer_engine: Engine, configuration: Settings, tmp_path: Path
) -> None:
    with Session(customer_engine) as db:
        wid, principal, provider, runtime, intent, progress, _, server = seeded(
            db, configuration, tmp_path
        )
        again = request_comparison(db, principal, provider, wid, intent, runtime)
        assert again.id == progress.id
        assert progress.completed_observations == 0 and progress.required_observations == 4
        assert len(server.posts) == 1
        assert (
            read_comparison_progress(db, principal, provider, wid, progress.id, runtime).id
            == progress.id
        )


@pytest.mark.parametrize("change", ["session", "generation", "event", "environment"])
def test_admission_rejects_original_authority_or_profile_drift(
    customer_engine: Engine, configuration: Settings, tmp_path: Path, change: str
) -> None:
    with Session(customer_engine) as db:
        wid, principal, provider, runtime, intent, progress, _, _ = seeded(
            db, configuration, tmp_path
        )
        if change == "session":
            principal.session.revoked_at = int(datetime.now(UTC).timestamp())
        elif change == "generation":
            source = db.scalar(select(MetaConnection).where(MetaConnection.workspace_id == wid))
            assert source is not None
            source.generation += 1
        elif change == "event":
            assert runtime.window_policy is not None
            runtime = replace(
                runtime,
                window_policy=runtime.window_policy.model_copy(update={"selected_event": "other"}),
            )
        else:
            assert runtime.window_policy is not None
            runtime = replace(
                runtime,
                window_policy=runtime.window_policy.model_copy(update={"environment": "live"}),
            )
        db.commit()
        with pytest.raises(HTTPException):
            request_comparison(db, principal, provider, wid, intent, runtime)


def test_changed_objective_supersedes_same_original_without_older_fallback(
    customer_engine: Engine, configuration: Settings, tmp_path: Path
) -> None:
    with Session(customer_engine) as db:
        wid, principal, provider, runtime, intent, progress, _, _ = seeded(
            db, configuration, tmp_path
        )
        changed = intent.model_copy(
            update={"maximum_reported_cpa_micros": intent.maximum_reported_cpa_micros + 1}
        )
        newer = request_comparison(db, principal, provider, wid, changed, runtime)
        db.commit()
        first, second = (
            db.get(ReportedFeedbackJob, progress.id),
            db.get(ReportedFeedbackJob, newer.id),
        )
        assert first is not None and second is not None
        assert first.opportunity_digest == second.opportunity_digest
        assert first.state == "blocked" and second.completed_observations == 0
        with pytest.raises(HTTPException):
            read_comparison_progress(db, principal, provider, wid, first.id, runtime)
        db.delete(second)
        db.commit()
        with pytest.raises(HTTPException):
            read_comparison_progress(db, principal, provider, wid, first.id, runtime)
