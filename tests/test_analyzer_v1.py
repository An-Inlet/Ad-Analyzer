from datetime import UTC, date, datetime
from decimal import Decimal

from app.ads.enums import RecommendationStatus
from app.ads.models import DailyMetric, ExecutionAudit, JobRun, RecommendationAudit
from app.optimizer.analytics import MetricWindow
from app.optimizer.recommendations import generate_findings, recommendations_from_findings

from tests.test_api_v1_read_only import make_client


def test_deterministic_findings_and_recommendation_drafts() -> None:
    window = MetricWindow(
        date(2026, 7, 1), date(2026, 7, 7), 7, 2000, 25, 5_000_000, Decimal("0"), 0
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


def test_authenticated_analytics_recommendation_approval_and_dry_run_api() -> None:
    with make_client() as (client, db, ids):
        c1 = ids["c1"]
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
        db.add(
            JobRun(
                platform="google_ads",
                account_id=ids["a1"],
                job_name="sync",
                status="succeeded",
                started_at=datetime(2026, 7, 9, tzinfo=UTC),
                finished_at=datetime(2026, 7, 9, tzinfo=UTC),
                records_processed=1,
            )
        )
        db.commit()
        analytics = client.get(
            f"/api/v1/accounts/{ids['a1']}/analytics/window?date_from=2026-07-01&date_to=2026-07-08"
        ).json()
        assert analytics["data_coverage"] == "sufficient"
        findings = client.get(
            f"/api/v1/accounts/{ids['a1']}/findings?date_from=2026-07-01&date_to=2026-07-08"
        ).json()
        assert {f["code"] for f in findings} >= {"spend_without_conversions", "low_ctr"}
        recs = client.post(
            f"/api/v1/accounts/{ids['a1']}/recommendations/generate?date_from=2026-07-01&date_to=2026-07-08"
        ).json()
        rec_id = recs[0]["id"]
        approved = client.post(
            f"/api/v1/recommendations/{rec_id}/approve",
            json={"actor": "operator", "reason": "test"},
        ).json()
        assert approved["status"] == RecommendationStatus.APPROVED
        dry = client.post(
            f"/api/v1/recommendations/{rec_id}/execute-dry-run?idempotency_key=abc123"
        ).json()
        assert dry["dry_run"] is True
        assert "live Google Ads writes are disabled" in dry["validation_errors"][0]
        assert db.query(RecommendationAudit).count() == 1
        assert db.query(ExecutionAudit).count() == 1
