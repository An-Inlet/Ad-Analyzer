"""Closed actual pinned reported acquisition, baseline, comparison and slot producer."""

import importlib.util
import json
import os
import sys
from datetime import UTC
from pathlib import Path
from typing import Any, cast

import app
import pytest
from app.publication.execution_models import ProviderExecutionReceipt, ProviderExposureReservation
from app.reported_feedback.contracts import FeedbackPreviewIntentV1
from app.reported_feedback.service import apply_feedback_preview, read_comparison
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import create_engine, func, make_url, select
from sqlalchemy.orm import Session
from tests.reported_feedback_journey_fixture import acquired, baseline
from tests.test_customer_identity import FakeProvider
from tests.test_shopify_sales import configuration


def main() -> None:
    schema, directory = sys.argv[1:]
    artifacts = Path(directory)
    assert os.environ["INLET_RETIRED_EXECUTION_CHILD"] == "2155ff3e3ab00cd62057dd86cb49d45359d4f49f"
    assert Path(app.__file__).resolve().is_relative_to(Path(os.environ["PYTHONPATH"]).resolve())
    root = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location(
        "_reported_boundary", root / "tests/social_restore_boundary.py"
    )
    assert spec and spec.loader
    boundary = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(boundary)
    engine = create_engine(
        make_url(validate_disposable_url()).update_query_dict(
            {"options": f"-csearch_path={schema}"}
        )
    )
    patch = pytest.MonkeyPatch()
    try:
        boundary.owned(engine, "reported")
        snapshot = boundary.fresh(engine)
        config = cast(Any, configuration).__wrapped__()
        with Session(engine) as db:
            data, runtime, observation = acquired(db, config, artifacts, patch)
            wid, principal, _, job, _, source, clock, _, _, _, server = data
            runtime, initial = baseline(db, data, runtime, observation)
            comparison = read_comparison(db, principal, FakeProvider(), wid, job.id, runtime)
            assert comparison.status == "operational_reported_as_of"
            result = apply_feedback_preview(
                db,
                principal,
                FakeProvider(),
                wid,
                FeedbackPreviewIntentV1(
                    comparison_id=comparison.id, baseline_preview_id=initial.id
                ),
                runtime,
            )
            assert result.proposed_budget_micros == 47000000
            receipts = db.scalar(select(func.count()).select_from(ProviderExecutionReceipt))
            holds = db.scalar(select(func.count()).select_from(ProviderExposureReservation))
            assert receipts and holds and len(server.posts) == 1
            output = dict(
                workspace_id=wid,
                source_id=source.id,
                job_id=job.id,
                comparison_id=comparison.id,
                slot_id=result.id,
                session_digest=principal.session.digest,
                slot_digest=result.digest(),
                observed_at=clock[0].astimezone(UTC).isoformat(),
                receipt_count=receipts,
                hold_count=holds,
                provider_posts=len(server.posts),
            )
            db.commit()
        boundary.unchanged(engine, snapshot)
        (artifacts / "ids.json").write_text(json.dumps(output))
    finally:
        patch.undo()
        engine.dispose()


if __name__ == "__main__":
    main()
