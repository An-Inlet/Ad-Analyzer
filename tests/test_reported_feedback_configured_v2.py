"""Actual configured producer/worker/native GET to owned adjusted-preview APIs."""

from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from app.initial_planning.models import PreviewRow
from app.lifecycle.export_serializers import serialize
from app.meta.models import MetaConnection
from app.reported_feedback.models import ReportedFeedbackSlot
from app.reported_feedback.service import validate_preview_dependencies
from app.settings import Settings
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.planning_runtime_fixture import configured_journey
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize("invalidate", ["session", "generation", "expiry", "baseline"])
def test_configured_v2_adjustment_export_and_current_fences(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    invalidate: str,
) -> None:
    with Session(customer_engine) as db:
        alice, provider, wid, principal, runtime, job, baseline, clock, requests, profile = (
            configured_journey(db, customer_engine, configuration, tmp_path, monkeypatch, replicas)
        )
        root = f"/api/customer/v1/workspaces/{wid}/reported-feedback"
        options = alice.get(root + "/options")
        assert options.status_code == 200, options.text
        assert baseline["id"] in {x["id"] for x in options.json()["baselines"]}
        response = alice.get(root + f"/comparisons/{job.id}")
        assert response.status_code == 200, response.text
        comparison = response.json()
        request = {"comparison_id": comparison["id"], "baseline_preview_id": baseline["id"]}
        before_reads = len(requests)
        response = alice.post(root + "/previews", headers=headers(alice), json=request)
        assert response.status_code == 200, response.text
        value = response.json()
        assert value["baseline_budget_micros"] == 46000000
        assert value["proposed_budget_micros"] != value["baseline_budget_micros"]
        assert value["spending_authority"] == "none" and not value["review_available"]
        assert profile.feedback is not None
        assert value["policy_digest"] == profile.feedback.digest()
        replay = alice.post(root + "/previews", headers=headers(alice), json=request)
        assert replay.status_code == 200 and replay.json() == value, replay.text
        read = alice.get(root + "/previews/" + value["id"])
        assert read.status_code == 200 and read.json() == value, read.text
        row = db.get(ReportedFeedbackSlot, value["id"])
        assert row is not None
        assert validate_preview_dependencies(db, row, clock[0]).model_dump(mode="json") == value
        exported, _ = serialize(
            "reported_feedback_slots", {c.name: getattr(row, c.name) for c in row.__table__.columns}
        )
        assert exported["document"] == value
        assert "original_session_digest" not in exported
        # Neither feedback nor export invokes native reads or writes.
        assert len(requests) == before_reads
        db.rollback()
        if invalidate == "session":
            provider.revoked.add(principal.user.subject)
        elif invalidate == "generation":
            source = db.get(MetaConnection, job.source_connection_id)
            assert source is not None
            source.generation += 1
            db.commit()
        elif invalidate == "baseline":
            old = db.get(PreviewRow, baseline["id"])
            assert old is not None
            db.delete(old)
            db.commit()
        else:
            clock[0] += timedelta(seconds=301)
        denied = alice.get(root + "/previews/" + value["id"])
        assert denied.status_code in {401, 403, 404, 409}, denied.text
        assert len(requests) == before_reads
