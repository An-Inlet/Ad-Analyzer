from pathlib import Path

import pytest
from app.reported_feedback.contracts import FeedbackPreviewIntentV1
from app.reported_feedback.service import apply_feedback_preview, read_comparison
from app.settings import Settings
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.reported_feedback_journey_fixture import acquired, baseline
from tests.reported_original_fixture import (
    RetainedReportedOriginalIds,
    prepare_reported_read,
)
from tests.reported_original_fixture import customer_engine as customer_engine
from tests.reported_original_fixture import reported_original as reported_original
from tests.reported_read_acquisition_fixture import prepare_reported_acquisition
from tests.test_customer_identity import FakeProvider
from tests.test_customer_identity import customer_engine as base_customer_engine  # noqa: F401
from tests.test_shopify_sales import configuration as configuration


def test_actual_acquisitions_produce_real_calibrated_baseline_and_changed_preview(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with Session(customer_engine) as db:
        data, runtime, observation = acquired(db, configuration, tmp_path, monkeypatch)
        wid, principal, _, job, _, _, _, _, _, _, server = data
        runtime, initial = baseline(db, data, runtime, observation)
        comparison = read_comparison(db, principal, FakeProvider(), wid, job.id, runtime)
        assert comparison.status == "operational_reported_as_of", comparison
        result = apply_feedback_preview(
            db,
            principal,
            FakeProvider(),
            wid,
            FeedbackPreviewIntentV1(comparison_id=comparison.id, baseline_preview_id=initial.id),
            runtime,
        )
        db.commit()
        assert initial.after_budget_micros == 46000000
        assert result.baseline_budget_micros == 46000000
        assert result.proposed_budget_micros == 47000000
        assert len(server.posts) == 1


@pytest.mark.parametrize(
    "change",
    [
        "capsule_deleted",
        "job_deleted",
        "expired",
        "superseded",
        "generation",
        "session",
        "other_campaign",
    ],
)
def test_fixed_current_report_requires_retained_owned_terminal_proof(
    change: str,
    reported_original: RetainedReportedOriginalIds,
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.ads.models import Campaign
    from app.campaign_performance.models import CurrentPerformance
    from app.campaign_performance.service import read_current
    from app.meta.security import utc
    from app.publication.customer_authority import bind_authority
    from app.reported_feedback import current_report
    from app.reported_feedback.models import ReportedWindowCapsule
    from fastapi import HTTPException
    from sqlalchemy import select

    with Session(customer_engine) as db:
        prepared = prepare_reported_read(db, reported_original)
        acquisition = prepare_reported_acquisition(db, configuration, prepared, monkeypatch)
        data, runtime, _ = acquired(
            db, configuration, tmp_path, monkeypatch, data=acquisition
        )
        wid, principal, _, job, _, source, _, _, _, _, _ = data
        cid = job.campaign_id
        current = db.get(CurrentPerformance, job.account_id)
        assert current
        capsule = db.scalar(
            select(ReportedWindowCapsule).where(
                ReportedWindowCapsule.completion_id == current.completion_id,
                ReportedWindowCapsule.campaign_id == cid,
            )
        )
        assert capsule
        if change == "capsule_deleted":
            db.delete(capsule)
        elif change == "job_deleted":
            db.delete(job)
        elif change == "expired":
            expiry = utc(capsule.expires_at)
            monkeypatch.setattr(current_report, "database_utc_now", lambda _: expiry)
        elif change == "superseded":
            job.state = "blocked"
        elif change == "generation":
            source.generation += 1
        elif change == "session":
            principal.session.revoked_at = 1
        elif change == "other_campaign":
            original = db.get(Campaign, cid)
            assert original
            other = Campaign(
                account_id=job.account_id,
                external_campaign_id="6",
                platform=original.platform,
                name="Other",
                status="ACTIVE",
            )
            db.add(other)
            db.flush()
            cid = other.id
        db.commit()
        with pytest.raises(HTTPException) as rejected:
            read_current(
                db,
                wid,
                principal.user.id,
                job.account_id,
                cid,
                None,
                bind_authority(principal, FakeProvider()),
            )
        assert rejected.value.status_code in {401, 409}
