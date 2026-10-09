"""Explicit dated Q16 acceptance experiment; run by path during October 2026 only."""

import json
from datetime import UTC, timedelta
from pathlib import Path
from typing import Any, Literal

import pytest
from app.api import customer_planning_documents as api
from app.campaign_review import service as media
from app.campaign_review.storage import LocalMediaStore
from app.commerce.models import CommerceEntry, CommerceSnapshot
from app.goals import service as goals
from app.goals.models import GoalConfirmation, GoalPreview, GoalRevision
from app.goals.schemas import GoalDefinition
from app.planning_documents.models import PlanEventRow, PlanInputRow, PlanRequestRow, PlanVersionRow
from app.publication.execution_models import ProviderExecutionAttempt
from app.settings import Settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.q16_clock_feasibility_probe import NOV3, issue_at, paid
from tests.q16_fixture import IMAGE, import_progress_stage, prepare_q16_case
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


def retained_counts(engine: Engine) -> tuple[int | None, ...]:
    with Session(engine) as db:
        return tuple(
            db.scalar(select(func.count()).select_from(model))
            for model in (
                PlanVersionRow,
                PlanInputRow,
                PlanRequestRow,
                PlanEventRow,
                GoalConfirmation,
                GoalPreview,
                GoalRevision,
                CommerceSnapshot,
            )
        )


def test_exact_new_york_progress(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[str] = []
    ids = prepare_q16_case(
        customer_engine,
        configuration,
        replicas,
        monkeypatch,
        tmp_path,
        branch="progress",
        native_calls=calls,
    )
    alice, _, provider = replicas
    url = f"/api/customer/v1/workspaces/{ids.workspace_id}/planning/plans/{ids.plan_id}"
    assert calls
    before = len(calls)
    retained = retained_counts(customer_engine)
    initial = alice.get(url + "/progress", params={"version": 1})
    assert initial.status_code == 200, initial.text
    assert initial.json()["net_sales_micros_exact"] == "0"
    (tmp_path / "initial-progress.json").write_text(json.dumps(initial.json(), indent=2))
    assert initial.json()["sales"]["coverage"] == dict(
        starts_on="2026-11-01",
        ends_on_exclusive="2026-11-03",
        starts_at="2026-11-01T04:00:00Z",
        ends_at_exclusive="2026-11-03T05:00:00Z",
        closed_day_count=2,
        extent="partial_period",
    )
    with Session(customer_engine) as db:
        goal = goals.owned(db, ids.workspace_id, ids.goal_id)
        definition = GoalDefinition.model_validate(goals.current(db, goal).definition)
        assert goals.baseline(db, goal, definition, NOV3)["net_sales_micros"] == 8_000_000_000
        assert (goal.revision, goal.confirmed_preview_id) == (
            ids.goal_revision,
            ids.confirmation_id,
        )
        asset, data = media.download(db, ids.workspace_id, ids.media_id, LocalMediaStore(tmp_path))
        assert asset.sha256 == ids.media_sha256 and data == IMAGE.read_bytes()
    assert retained_counts(customer_engine) == retained
    original = alice.get(url, params={"version": 1})
    assert original.status_code == 200, original.text
    (tmp_path / "original-plan.json").write_text(json.dumps(original.json(), indent=2))
    document = original.json()["document"]
    assert document["version"] == 1 and document["policy_version"] == "inlet.descriptive-review.v3"
    inputs = document["inputs"]
    assert inputs["total_ceiling_micros"] == 1_000_000_000
    assert inputs["goal"]["definition"]["target_micros"] == 12_000_000_000
    assert inputs["goal"]["definition"]["target_window"]["time_zone"] == "America/New_York"
    assert "$25" in inputs["product_offer"] and ids.media_id in inputs["product_offer"]
    missing = [
        text for text in document["section_limitations"] if "current_reporting_unavailable" in text
    ]
    assert len(missing) == 2 and all("Campaign IDs: 1." in text for text in missing)
    assert not any(e["kind"] == "reported_metrics" for e in document["evidence"])
    assert document["advertising_writes_enabled"] is False
    assert document["spending_authority"] == "none"
    stages: tuple[tuple[Literal["later_day", "refund_correction"], str], ...] = (
        ("later_day", "25000000"),
        ("refund_correction", "20000000"),
    )
    for stage, expected in stages:
        now = import_progress_stage(customer_engine, configuration, ids, stage=stage)
        paid(customer_engine, ids.workspace_id, now, monkeypatch, initial=False)
        monkeypatch.setattr(api, "utc_now", lambda now=now: now)
        if stage == "later_day":
            expired = alice.get(url + "/progress", params={"version": 1})
            assert expired.status_code == 401, expired.text
        issue_at(alice, provider, "q16-owner", now)
        retained = retained_counts(customer_engine)
        progress = alice.get(url + "/progress", params={"version": 1})
        assert progress.status_code == 200, progress.text
        assert progress.json()["net_sales_micros_exact"] == expected, progress.text
        assert progress.json()["as_of"] == now.isoformat().replace("+00:00", "Z")
        assert retained_counts(customer_engine) == retained
        current = alice.get(url, params={"version": 1})
        assert current.status_code == 200, current.text
        assert current.json()["document"] == original.json()["document"]
        assert current.json()["document_digest"] == ids.document_digest
        assert progress.json()["goal"] == initial.json()["goal"]
        assert progress.json()["sales"]["coverage"]["closed_day_count"] == 3
        assert progress.json()["sales"]["coverage"]["ends_at_exclusive"] == "2026-11-04T05:00:00Z"
        assert progress.json()["manual_application"] == "not_assessed"
        assert progress.json()["attribution"] == "unavailable"
        with Session(customer_engine) as db:
            assert db.scalar(select(func.count()).select_from(PlanVersionRow)) == 1
            assert db.scalar(select(func.count()).select_from(PlanEventRow)) == 0
            assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 0
    with Session(customer_engine) as db:
        entries = list(
            db.scalars(select(CommerceEntry).where(CommerceEntry.store_id == ids.store_id))
        )
        refund = next(row for row in entries if row.net_micros == -5_000_000)
        sale = next(row for row in entries if row.net_micros == 25_000_000)
        assert refund.order_key == sale.order_key and refund.action == "RETURN"
        assert refund.happened_at.replace(tzinfo=UTC) == NOV3 + timedelta(hours=12)
    assert len(calls) == before
    assert now > NOV3


def test_exact_case_semantic_erasure_old_ids(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from app.lifecycle.contracts import LifecycleScopeV1
    from app.lifecycle.inventory import export_section
    from app.lifecycle.privacy import bump_workspace_export_revision

    from tests.test_customer_optimization_api import headers

    calls: list[str] = []
    ids = prepare_q16_case(
        customer_engine,
        configuration,
        replicas,
        monkeypatch,
        tmp_path,
        branch="privacy",
        native_calls=calls,
    )
    alice, _, _ = replicas
    root = f"/api/customer/v1/workspaces/{ids.workspace_id}/planning/plans"
    url = root + "/" + ids.plan_id
    before = len(calls)
    exported = alice.get(url + "/export", params={"version": 1})
    assert exported.status_code == 200, exported.text
    with Session(customer_engine) as db:
        scope = LifecycleScopeV1(workspace_id=ids.workspace_id)
        section = export_section(db, scope, "planning_document_versions")
        assert len(section["rows"]) == 1
        bump_workspace_export_revision(db, ids.workspace_id)
        db.commit()
    for path in (url, url + "/progress", url + "/export", url + "/versions/1"):
        response = alice.get(path, params={"version": 1})
        assert response.status_code == 404, response.text
    for operation, key in (
        ("create", ids.create_request_key),
        ("generate", ids.generate_request_key),
    ):
        response = alice.get(root + f"/requests/{operation}/{key}")
        assert response.status_code == 404, response.text
    generated = alice.post(
        url + "/generate",
        headers=headers(alice),
        json=dict(expected_input_revision=1, expected_version=1, request_key="q16-erased-retry"),
    )
    assert generated.status_code == 404, generated.text
    with Session(customer_engine) as db:
        for table in (
            "planning_documents",
            "planning_input_revisions",
            "planning_document_versions",
            "planning_document_dependencies",
            "planning_document_events",
            "planning_document_requests",
        ):
            assert export_section(db, scope, table)["rows"] == []
    assert len(calls) == before
