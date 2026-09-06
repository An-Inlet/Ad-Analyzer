from datetime import timedelta

from app.ads.models import DailyMetric
from app.intelligence.schemas import Strategy
from app.intelligence.service import IntelligenceService
from app.meta.models import MetaConnection
from sqlalchemy import select
from sqlalchemy.orm import Session

from tests.test_available_evidence import NOW, campaign, metrics, workspace

pytest_plugins = ["tests.test_available_evidence"]


def test_meta_only_report_and_answers_work_without_optional_sources(db: Session) -> None:
    owner = workspace(db)
    active = campaign(db, owner)
    metrics(db, active)
    service = IntelligenceService(db)
    report = service.report(owner.id, as_of=NOW)
    assert report["strategy"] is None
    assert report["available_analysis_ready"]
    assert report["readiness_label"] == "Platform insights available"
    assert not report["analysis_ready"]
    assert not report["business_outcome_analysis_ready"]
    assert report["health"]["scope"] == "business_outcomes"
    assert all(
        issue["severity"] == "optional"
        for issue in report["health"]["issues"]
        if issue["code"] in {"crm_missing", "analytics_missing"}
    )
    assert report["recommendations"][0]["confidence"] == "directional"
    assert not any(r["key"] == "repair_measurement" for r in report["recommendations"])
    assert report["scenarios"] == []
    assert report["allocation"] is None
    answer = service.answer(report, "Why is my Meta campaign performance changing?")
    assert answer["topic"] == "platform"
    assert any("USD 560.00 recorded spend" in fact for fact in answer["facts"])
    assert report["execution"]["live_changes_enabled"] is False


def test_evidence_fingerprint_survives_page_refresh_but_tracks_new_metrics(db: Session) -> None:
    owner = workspace(db)
    active = campaign(db, owner)
    metrics(db, active)
    service = IntelligenceService(db)
    first = service.report(owner.id, as_of=NOW)
    second = service.report(owner.id, as_of=NOW + timedelta(minutes=1))
    assert (
        first["recommendations"][0]["evidence_fingerprint"]
        == second["recommendations"][0]["evidence_fingerprint"]
    )
    isolated = workspace(db, "other-client")
    other = campaign(db, isolated)
    metrics(db, other, cost_micros=9_000_000_000)
    unchanged = service.report(owner.id, as_of=NOW)
    assert (
        first["recommendations"][0]["evidence_fingerprint"]
        == unchanged["recommendations"][0]["evidence_fingerprint"]
    )
    assert len(unchanged["available_evidence"]["accounts"]) == 1
    changed_metric = db.scalars(
        select(DailyMetric).where(DailyMetric.campaign_id == active.id)
    ).first()
    assert changed_metric is not None
    changed_metric.clicks += 100
    db.flush()
    changed = service.report(owner.id, as_of=NOW)
    assert (
        first["recommendations"][0]["evidence_fingerprint"]
        != changed["recommendations"][0]["evidence_fingerprint"]
    )


def test_empty_workspace_has_actionable_planning_and_a_scheduled_brief(db: Session) -> None:
    owner = workspace(db)
    service = IntelligenceService(db)
    report = service.report(owner.id, as_of=NOW)
    assert report["readiness_label"] == "Planning ready"
    assert report["available_evidence"]["capabilities"]["planning"]["ready"]
    assert not report["available_analysis_ready"]
    assert report["recommendations"][0]["key"] == "set_strategy"
    brief = service.brief(report)
    assert brief["strategy_version"] is None
    assert brief["capabilities"]["planning"]["ready"]
    assert service.answer(report, "Meta performance")["facts"]


def test_meta_completed_zero_delivery_days_support_budget_pacing(db: Session) -> None:
    owner = workspace(db)
    active = campaign(db, owner)
    metrics(db, active, first_day_ago=1, last_day_ago=1)
    strategy = Strategy.model_validate(
        {
            "title": "Acquisition plan",
            "primary_metric": "customers",
            "target": "20",
            "period_start": "2026-09-01",
            "period_end": "2026-09-30",
            "budget_micros": 1_000_000_000,
            "currency_code": "USD",
        }
    )
    service = IntelligenceService(db)
    assert service._spend(owner.id, strategy, NOW.date())[1] is False
    connection = MetaConnection(
        workspace_id=owner.id,
        account_id=active.account_id,
        external_account_id="local-test-account",
        encrypted_credentials="offline-fixture",
        last_sync_at=NOW,
        covered_from=strategy.period_start,
        covered_through=NOW.date() - timedelta(days=1),
    )
    db.add(connection)
    db.flush()
    spend, complete, last = service._spend(owner.id, strategy, NOW.date())
    assert spend == 20_000_000 and complete and last == NOW.date() - timedelta(days=1)
    connection.covered_through = NOW.date() - timedelta(days=2)
    db.flush()
    assert service._spend(owner.id, strategy, NOW.date())[1] is False
