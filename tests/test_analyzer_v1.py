from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, cast

import pytest
from app.ads.enums import ExecutionStatus, RecommendationStatus
from app.ads.models import DailyMetric, ExecutionAudit, JobRun, Recommendation, RecommendationAudit
from app.optimizer.analytics import MetricWindow
from app.optimizer.recommendations import generate_findings, recommendations_from_findings
from app.settings import settings

from tests.test_api_v1_read_only import make_client


def test_deterministic_findings_and_recommendation_drafts() -> None:
    window = MetricWindow(
        date(2026, 7, 1), date(2026, 7, 7), 7, 7, 2000, 25, 5_000_000, Decimal("0"), 0
    )
    findings = generate_findings(
        window,
        None,
        last_success_at=datetime(2026, 7, 7, tzinfo=UTC),
        now=datetime(2026, 7, 8, tzinfo=UTC),
    )
    assert [f.code for f in findings] == ["spend_without_conversions", "low_ctr"]
    drafts = recommendations_from_findings(findings, expires_at=datetime(2026, 7, 22, tzinfo=UTC))
    assert drafts[0].planned_action["mode"] == "dry_run_only"


@pytest.mark.parametrize("conversions", [Decimal("10"), Decimal("0.5")])
def test_positive_conversions_never_produce_no_conversions_finding(conversions: Decimal) -> None:
    window = MetricWindow(
        date(2026, 7, 1), date(2026, 7, 7), 7, 7, 2000, 100, 100_000_000, conversions, 0
    )
    now = datetime(2026, 7, 8, tzinfo=UTC)
    findings = generate_findings(window, None, last_success_at=now, now=now)
    assert "spend_without_conversions" not in {finding.code for finding in findings}
    drafts = recommendations_from_findings(findings, expires_at=now)
    assert "spend_without_conversions" not in {draft.recommendation_type for draft in drafts}


@pytest.mark.parametrize(
    ("cost_micros", "clicks", "available", "days_with_rows", "expected"),
    [
        (100_000_000, 100, True, 7, True),
        (1, 20, True, 7, True),
        (0, 100, True, 7, False),
        (100_000_000, 19, True, 7, False),
        (100_000_000, 100, False, 7, False),
        (100_000_000, 100, True, 0, False),
    ],
)
def test_zero_conversion_finding_requires_spend_traffic_and_available_data(
    cost_micros: int, clicks: int, available: bool, days_with_rows: int, expected: bool
) -> None:
    window = MetricWindow(
        date(2026, 7, 1), date(2026, 7, 7), 7, days_with_rows,
        2000, clicks, cost_micros, Decimal("0"), 0,
    )
    now = datetime(2026, 7, 8, tzinfo=UTC)
    findings = generate_findings(
        window, None, last_success_at=now, now=now, conversion_metrics_available=available
    )
    assert ("spend_without_conversions" in {finding.code for finding in findings}) is expected


def add_current_window_metrics(db: Any, c1: int) -> None:
    for offset in range(3, 9):
        db.add(
            DailyMetric(
                platform="google_ads",
                metric_date=date(2026, 7, offset),
                entity_type="campaign",
                entity_id=c1,
                campaign_id=c1,
                impressions=300,
                clicks=4,
                cost_micros=700_000,
                conversions=Decimal("0"),
                conversion_value_micros=0,
            )
        )


def add_comparison_window_metrics(db: Any, c1: int) -> None:
    for offset in range(23, 31):
        db.add(
            DailyMetric(
                platform="google_ads",
                metric_date=date(2026, 6, offset),
                entity_type="campaign",
                entity_id=c1,
                campaign_id=c1,
                impressions=500,
                clicks=20,
                cost_micros=200_000,
                conversions=Decimal("0.25"),
                conversion_value_micros=1_000_000,
            )
        )


def add_successful_sync(db: Any, account_id: int) -> None:
    db.add(
        JobRun(workspace_id=1,
            platform="google_ads",
            account_id=account_id,
            job_name="sync",
            status="succeeded",
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            records_processed=1,
        )
    )


def generate_and_approve(client: Any, account_id: int) -> int:
    recs = client.post(
        f"/api/v1/accounts/{account_id}/recommendations/generate?"
        "date_from=2026-07-01&date_to=2026-07-08"
    ).json()
    rec_id = cast(int, recs[0]["id"])
    approved = client.post(
        f"/api/v1/recommendations/{rec_id}/approve",
        json={"actor": "operator", "reason": "test"},
    ).json()
    assert approved["status"] == RecommendationStatus.APPROVED
    return rec_id


def test_authenticated_analytics_recommendation_approval_and_blocked_dry_run_api() -> None:
    with make_client() as (client, db, ids):
        add_current_window_metrics(db, ids["c1"])
        add_successful_sync(db, ids["a1"])
        db.commit()
        analytics = client.get(
            f"/api/v1/accounts/{ids['a1']}/analytics/window?date_from=2026-07-01&date_to=2026-07-08"
        ).json()
        assert analytics["data_coverage"] == "sufficient"
        assert analytics["window_days"] == 8
        assert analytics["days_with_metric_rows"] == 8
        assert analytics["data_coverage_ratio"] == "1"
        findings = client.get(
            f"/api/v1/accounts/{ids['a1']}/findings?date_from=2026-07-01&date_to=2026-07-08"
        ).json()
        # The shared fixture includes 2.5 conversions; high CPA is not zero conversions.
        assert "low_ctr" in {f["code"] for f in findings}
        assert "spend_without_conversions" not in {f["code"] for f in findings}
        rec_id = generate_and_approve(client, ids["a1"])
        dry = client.post(
            f"/api/v1/recommendations/{rec_id}/execute-dry-run?idempotency_key=abc123"
        ).json()
        assert dry["dry_run"] is True
        assert dry["status"] == ExecutionStatus.BLOCKED
        assert "live Google Ads writes are disabled" in dry["validation_errors"][0]
        recommendation = db.get(Recommendation, rec_id)
        assert recommendation is not None
        assert recommendation.status == RecommendationStatus.APPROVED
        assert db.query(RecommendationAudit).count() == 1
        assert db.query(ExecutionAudit).count() == 1


def test_api_findings_pass_comparison_window_and_generate_cpa_recommendation() -> None:
    with make_client() as (client, db, ids):
        add_current_window_metrics(db, ids["c1"])
        add_comparison_window_metrics(db, ids["c1"])
        add_successful_sync(db, ids["a1"])
        db.commit()
        findings = client.get(
            f"/api/v1/accounts/{ids['a1']}/findings?date_from=2026-07-01&date_to=2026-07-08"
        ).json()
        assert "cpa_regression" in {finding["code"] for finding in findings}
        assert "spend_without_conversions" not in {finding["code"] for finding in findings}
        recs = client.post(
            f"/api/v1/accounts/{ids['a1']}/recommendations/generate?"
            "date_from=2026-07-01&date_to=2026-07-08"
        ).json()
        assert "cpa_regression" in {rec["recommendation_type"] for rec in recs}


def test_short_observed_window_is_not_automatically_insufficient() -> None:
    with make_client() as (client, _db, ids):
        findings = client.get(
            f"/api/v1/accounts/{ids['a1']}/findings?date_from=2026-07-01&date_to=2026-07-01"
        ).json()
        assert "insufficient_data" not in {finding["code"] for finding in findings}
        analytics = client.get(
            f"/api/v1/accounts/{ids['a1']}/analytics/window?date_from=2026-07-01&date_to=2026-07-01"
        ).json()
        assert analytics["window_days"] == 1
        assert analytics["days_with_metric_rows"] == 1
        assert analytics["data_coverage"] == "sufficient"


def test_successful_dry_run_marks_executed_when_safeguards_are_explicitly_satisfied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with make_client() as (client, db, ids):
        add_current_window_metrics(db, ids["c1"])
        add_successful_sync(db, ids["a1"])
        db.commit()
        rec_id = generate_and_approve(client, ids["a1"])
        monkeypatch.setattr(settings, "google_ads_write_enabled", True)
        monkeypatch.setattr(settings, "google_ads_execution_kill_switch", False)
        monkeypatch.setattr(settings, "allowed_execution_account_ids_csv", str(ids["a1"]))
        monkeypatch.setattr(
            settings, "allowed_google_ads_mutations_csv", "none_without_human_approval"
        )
        dry = client.post(
            f"/api/v1/recommendations/{rec_id}/execute-dry-run?idempotency_key=success-key"
        ).json()
        assert dry["status"] == ExecutionStatus.DRY_RUN_SUCCEEDED
        assert dry["validation_errors"] == []
        recommendation = db.get(Recommendation, rec_id)
        assert recommendation is not None
        assert recommendation.status == RecommendationStatus.EXECUTED_DRY_RUN


def test_execution_idempotency_is_recommendation_scoped() -> None:
    with make_client() as (client, db, ids):
        add_current_window_metrics(db, ids["c1"])
        add_successful_sync(db, ids["a1"])
        db.commit()
        first_id = generate_and_approve(client, ids["a1"])
        second_id = generate_and_approve(client, ids["a1"])
        first = client.post(
            f"/api/v1/recommendations/{first_id}/execute-dry-run?idempotency_key=reused"
        ).json()
        repeat = client.post(
            f"/api/v1/recommendations/{first_id}/execute-dry-run?idempotency_key=reused"
        ).json()
        second = client.post(
            f"/api/v1/recommendations/{second_id}/execute-dry-run?idempotency_key=reused"
        ).json()
        assert repeat["id"] == first["id"]
        assert second["id"] != first["id"]
        assert second["recommendation_id"] == second_id
        assert db.query(ExecutionAudit).count() == 2


def test_dashboard_displays_analytics_findings_recommendations_and_dry_run_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.dashboard import router as dashboard_router
    from app.dashboard.auth import require_dashboard_session
    from app.main import app

    with make_client() as (client, db, ids):
        app.dependency_overrides[require_dashboard_session] = lambda: None
        monkeypatch.setattr(dashboard_router, "validate_csrf", lambda _request: None)
        add_current_window_metrics(db, ids["c1"])
        add_successful_sync(db, ids["a1"])
        db.commit()
        rec_id = generate_and_approve(client, ids["a1"])
        page = client.get(
            f"/dashboard/accounts/{ids['a1']}?date_from=2026-07-01&date_to=2026-07-08"
        )
        assert page.status_code == 200
        assert "Analytics window" in page.text
        assert "Deterministic findings" in page.text
        assert "Recommendation review queue" in page.text
        assert "low_ctr" in page.text
        assert "spend_without_conversions" not in page.text
        blocked = client.post(
            f"/dashboard/recommendations/{rec_id}/execute-dry-run",
            data={"csrf_token": "test", "idempotency_key": "dashboard-key"},
            follow_redirects=False,
        )
        assert blocked.status_code == 303
        page_after = client.get(
            f"/dashboard/accounts/{ids['a1']}?date_from=2026-07-01&date_to=2026-07-08"
        )
        assert "blocked" in page_after.text
        recommendation = db.get(Recommendation, rec_id)
        assert recommendation is not None
        assert recommendation.status == RecommendationStatus.APPROVED


def test_execution_operations_dashboard_is_account_scoped_and_redacted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.dashboard import router as dashboard_router
    from app.dashboard.auth import require_dashboard_session
    from app.main import app

    with make_client() as (client, db, ids):
        app.dependency_overrides[require_dashboard_session] = lambda: None
        monkeypatch.setattr(dashboard_router, "validate_csrf", lambda _request: None)
        add_current_window_metrics(db, ids["c1"])
        add_successful_sync(db, ids["a1"])
        db.commit()
        rec_id = generate_and_approve(client, ids["a1"])
        blocked = client.post(
            f"/dashboard/recommendations/{rec_id}/execute-dry-run",
            data={"csrf_token": "test", "idempotency_key": "ops-key"},
            follow_redirects=False,
        )
        assert blocked.status_code == 303

        page = client.get(
            f"/dashboard/accounts/{ids['a1']}/execution-operations?limit=1&offset=0"
        )
        assert page.status_code == 200
        assert "Execution safety state" in page.text
        assert "Kill switch" in page.text
        assert "Active" in page.text
        assert "Write enabled" in page.text
        assert "Disabled" in page.text
        assert "Blocked dry run" in page.text
        assert "Redacted validation errors" in page.text
        assert "Redacted planned payload" in page.text
        assert "No live execution control is available" in page.text
        assert "No synchronization trigger is available" in page.text
        assert "100" not in page.text
        assert "ops-key" not in page.text

        isolated = client.get(f"/dashboard/accounts/{ids['a2']}/execution-operations")
        assert isolated.status_code == 200
        assert "No dry-run execution audits for this account" in isolated.text
        assert "Blocked dry run" not in isolated.text
