from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from app.ads.enums import AdvertisingPlatform, RecommendationStatus
from app.ads.models import AdvertisingAccount, Recommendation, RecommendationAudit
from app.analysis.enums import AnalysisCadence, AnalysisRunStatus
from app.analysis.models import AnalysisRun
from app.learning import WeeklyLearningReportService
from app.workspaces.models import Workspace
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tests.test_api_v1_read_only import make_client


def add_analysis_run(
    db: Session,
    *,
    workspace_id: int,
    scheduled_for: datetime,
    findings: int,
    high_severity: int,
    created: int,
    deduplicated: int,
) -> AnalysisRun:
    row = AnalysisRun(
        workspace_id=workspace_id,
        run_key=f"weekly-report-test:{scheduled_for.isoformat()}",
        cadence=AnalysisCadence.WEEKLY,
        status=AnalysisRunStatus.SUCCEEDED,
        schedule_policy_version="v1",
        scheduled_for=scheduled_for,
        metric_date_from=scheduled_for.date() - timedelta(days=7),
        metric_date_to=scheduled_for.date() - timedelta(days=1),
        outcome_date_from=scheduled_for.date() - timedelta(days=97),
        outcome_date_to=scheduled_for.date() - timedelta(days=91),
        started_at=scheduled_for,
        finished_at=scheduled_for + timedelta(minutes=1),
        accounts_analyzed=1,
        findings_count=findings,
        high_severity_findings_count=high_severity,
        recommendations_created_count=created,
        recommendations_deduplicated_count=deduplicated,
        outcome_analysis_ready=False,
        outcome_campaign_count=0,
        attributed_journey_count=0,
        unattributed_journey_count=0,
        blocking_reasons=["measurement_contract_missing"],
    )
    db.add(row)
    db.flush()
    return row


def add_recommendation(
    db: Session,
    *,
    workspace_id: int,
    account: AdvertisingAccount,
    recommendation_type: str,
    generated_at: datetime,
    action: str | None = None,
    decided_at: datetime | None = None,
    reason: str = "private-weekly-reason",
) -> Recommendation:
    status = RecommendationStatus.PENDING_REVIEW
    if action == "approved":
        status = RecommendationStatus.APPROVED
    elif action == "rejected":
        status = RecommendationStatus.REJECTED
    row = Recommendation(
        workspace_id=workspace_id,
        platform=account.platform,
        account_id=account.id,
        recommendation_type=recommendation_type,
        severity="medium",
        confidence=Decimal("0.7000"),
        rationale="Deterministic weekly report test recommendation.",
        supporting_metrics={},
        planned_action={
            "mode": "human_review_required",
            "mutation": "none_without_human_approval",
            "review_action": "review_relevance_and_creative",
            "scope": {"type": "campaign", "id": 1, "label": "Masked scope"},
            "source_text_redacted": True,
        },
        status=status,
        generated_at=generated_at,
        expires_at=generated_at + timedelta(days=30),
    )
    db.add(row)
    db.flush()
    if action is not None:
        assert decided_at is not None
        db.add(
            RecommendationAudit(
                recommendation_id=row.id,
                actor="private-operator@example.com",
                action=action,
                reason=reason,
                created_at=decided_at,
                updated_at=decided_at,
            )
        )
        db.flush()
    return row


def add_other_workspace(db: Session) -> tuple[Workspace, AdvertisingAccount]:
    workspace = Workspace(
        slug="other-client",
        name="Other Client Ad Analyzer",
        client_name="Other Client",
        status="active",
        is_default=False,
    )
    db.add(workspace)
    db.flush()
    account = AdvertisingAccount(
        workspace_id=workspace.id,
        platform=AdvertisingPlatform.GOOGLE_ADS,
        external_account_id="other-client-account",
        name="Other Client Ads",
        currency_code="USD",
        time_zone="UTC",
    )
    db.add(account)
    db.flush()
    return workspace, account


def test_weekly_report_compares_completed_weeks_and_emits_bounded_improvements() -> None:
    with make_client() as (_client, db, ids):
        workspace_id = ids["workspace"]
        account = db.get(AdvertisingAccount, ids["a1"])
        assert account is not None
        add_analysis_run(
            db,
            workspace_id=workspace_id,
            scheduled_for=datetime(2026, 8, 5, 3, tzinfo=UTC),
            findings=8,
            high_severity=1,
            created=3,
            deduplicated=0,
        )
        add_analysis_run(
            db,
            workspace_id=workspace_id,
            scheduled_for=datetime(2026, 8, 12, 3, tzinfo=UTC),
            findings=20,
            high_severity=5,
            created=4,
            deduplicated=12,
        )
        decisions = (
            ("approved", datetime(2026, 8, 5, 12, tzinfo=UTC)),
            ("rejected", datetime(2026, 8, 6, 12, tzinfo=UTC)),
            ("approved", datetime(2026, 8, 11, 12, tzinfo=UTC)),
            ("rejected", datetime(2026, 8, 12, 12, tzinfo=UTC)),
            ("rejected", datetime(2026, 8, 13, 12, tzinfo=UTC)),
        )
        for index, (action, decided_at) in enumerate(decisions):
            add_recommendation(
                db,
                workspace_id=workspace_id,
                account=account,
                recommendation_type="low_ctr",
                generated_at=decided_at - timedelta(days=1),
                action=action,
                decided_at=decided_at,
                reason=f"private-weekly-reason-{index}",
            )
        add_recommendation(
            db,
            workspace_id=workspace_id,
            account=account,
            recommendation_type="low_ctr",
            generated_at=datetime(2026, 8, 14, 12, tzinfo=UTC),
        )
        other, other_account = add_other_workspace(db)
        add_recommendation(
            db,
            workspace_id=other.id,
            account=other_account,
            recommendation_type="other_workspace_private_signal",
            generated_at=datetime(2026, 8, 12, 12, tzinfo=UTC),
            action="rejected",
            decided_at=datetime(2026, 8, 13, 12, tzinfo=UTC),
        )
        db.commit()

        report = WeeklyLearningReportService(db).build(
            workspace_id,
            as_of=date(2026, 8, 17),
        )

        assert report.report_key == "weekly-learning:2026-08-16"
        assert report.current_period.date_from == date(2026, 8, 10)
        assert report.current_period.date_to == date(2026, 8, 16)
        assert report.comparison_period.date_from == date(2026, 8, 3)
        assert report.comparison_period.date_to == date(2026, 8, 9)
        assert report.current.analysis_run_count == 1
        assert report.current.findings_count == 20
        assert report.current.high_severity_findings_count == 5
        assert report.current.proposals_generated_count == 4
        assert report.current.proposals_deduplicated_count == 12
        assert report.current.decision_count == 3
        assert report.current.acceptance_rate == Decimal("0.3333")
        assert report.previous.proposals_generated_count == 2
        assert report.previous.decision_count == 2
        assert report.previous.acceptance_rate == Decimal("0.5000")
        assert report.changes.findings_per_run == Decimal("12.0000")
        assert report.evidence_state == "established"
        assert report.summary_state == "attention"
        codes = {item.code for item in report.suggestions}
        assert "review_low_acceptance_profile" in codes
        assert "investigate_rising_finding_density" in codes
        assert "improve_recurring_signal_context" in codes
        assert all(item.automatic_change is False for item in report.suggestions)
        assert report.safety.local_data_only is True
        assert report.safety.automatic_change_applied is False
        rendered = repr(report)
        assert "private-weekly-reason" not in rendered
        assert "private-operator@example.com" not in rendered
        assert "other_workspace_private_signal" not in rendered


def test_historical_report_excludes_later_decisions_and_makes_no_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with make_client() as (_client, db, ids):
        workspace_id = ids["workspace"]
        account = db.get(AdvertisingAccount, ids["a1"])
        assert account is not None
        add_recommendation(
            db,
            workspace_id=workspace_id,
            account=account,
            recommendation_type="low_ctr",
            generated_at=datetime(2026, 8, 12, 12, tzinfo=UTC),
            action="approved",
            decided_at=datetime(2026, 8, 18, 12, tzinfo=UTC),
        )
        db.commit()
        recommendation_count = db.scalar(select(func.count()).select_from(Recommendation))
        audit_count = db.scalar(select(func.count()).select_from(RecommendationAudit))
        monkeypatch.setattr(
            "app.collectors.google_ads.collect_account",
            lambda: pytest.fail("weekly reports must not call the Google Ads collector"),
        )
        monkeypatch.setattr(
            "app.executors.google_executor.live_google_ads_mutation_boundary",
            lambda *_args, **_kwargs: pytest.fail(
                "weekly reports must not call an advertising mutation boundary"
            ),
        )

        report = WeeklyLearningReportService(db).build(
            workspace_id,
            as_of=date(2026, 8, 17),
        )

        assert report.decision_learning.decision_count == 0
        assert report.current.decision_count == 0
        assert report.evidence_state == "no_history"
        assert db.scalar(select(func.count()).select_from(Recommendation)) == recommendation_count
        assert db.scalar(select(func.count()).select_from(RecommendationAudit)) == audit_count
        assert not db.new
        assert not db.dirty
        assert not db.deleted


def test_weekly_report_api_and_dashboard_are_workspace_scoped_and_private() -> None:
    from app.dashboard.auth import require_dashboard_session
    from app.main import app

    with make_client() as (client, db, ids):
        workspace_id = ids["workspace"]
        account = db.get(AdvertisingAccount, ids["a1"])
        assert account is not None
        add_analysis_run(
            db,
            workspace_id=workspace_id,
            scheduled_for=datetime(2026, 8, 12, 3, tzinfo=UTC),
            findings=4,
            high_severity=1,
            created=1,
            deduplicated=0,
        )
        add_recommendation(
            db,
            workspace_id=workspace_id,
            account=account,
            recommendation_type="low_ctr",
            generated_at=datetime(2026, 8, 11, 12, tzinfo=UTC),
            action="approved",
            decided_at=datetime(2026, 8, 12, 12, tzinfo=UTC),
            reason="api-private-weekly-reason",
        )
        other, other_account = add_other_workspace(db)
        add_recommendation(
            db,
            workspace_id=other.id,
            account=other_account,
            recommendation_type="api_other_workspace_signal",
            generated_at=datetime(2026, 8, 11, 12, tzinfo=UTC),
            action="rejected",
            decided_at=datetime(2026, 8, 12, 12, tzinfo=UTC),
        )
        db.commit()
        app.dependency_overrides[require_dashboard_session] = lambda: None

        response = client.get(
            "/api/v1/workspaces/denticode/weekly-learning-report?as_of=2026-08-17"
        )
        dashboard = client.get("/dashboard/workspaces/denticode")

        assert response.status_code == 200
        payload = response.json()
        assert payload["workspace_id"] == workspace_id
        assert payload["report_key"] == "weekly-learning:2026-08-16"
        assert payload["current"]["analysis_run_count"] == 1
        assert payload["current"]["acceptance_rate"] == "1.0000"
        assert payload["safety"] == {
            "local_data_only": True,
            "actor_identity_used": False,
            "reason_text_used": False,
            "search_term_text_used": False,
            "external_service_called": False,
            "automatic_change_applied": False,
        }
        assert "api-private-weekly-reason" not in response.text
        assert "private-operator@example.com" not in response.text
        assert "api_other_workspace_signal" not in response.text
        assert dashboard.status_code == 200
        assert "Weekly learning report" in dashboard.text
        assert "Suggested analyzer improvements" in dashboard.text
        assert "api-private-weekly-reason" not in dashboard.text
        assert "api_other_workspace_signal" not in dashboard.text
