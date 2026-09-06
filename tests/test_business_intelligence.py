from collections.abc import Generator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from sqlite3 import Connection as SQLiteConnection
from typing import Any

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.ads.enums import AdvertisingPlatform, JobRunStatus
from app.ads.models import AdGroup, AdvertisingAccount, JobRun
from app.dashboard.intelligence import _csv_cell, _fields, _form_payload
from app.database.session import Base, get_db
from app.intelligence.calculations import (
    allocation_preview,
    budget_pacing,
    experiment_result,
    scenario_forecast,
)
from app.intelligence.models import IntelligenceRevision
from app.intelligence.repository import ContextConflict, ContextNotFound, IntelligenceRepository
from app.intelligence.schemas import (
    BusinessEvent,
    Experiment,
    RecordKind,
    SaveRecord,
    ScenarioRequest,
    Strategy,
)
from app.intelligence.service import IntelligenceService
from app.main import app
from app.measurement.ingestion import WebAnalyticsRepository
from app.settings import settings
from app.workspaces.models import WorkspaceMembership
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import ConnectionPoolEntry, StaticPool

from tests.test_unified_outcome_data import (
    add_complete_journey,
    add_metric,
    ga4_event,
    seed_workspace,
)

NOW = datetime(2026, 7, 11, 12, tzinfo=UTC)


def _foreign_keys(connection: SQLiteConnection, _record: ConnectionPoolEntry) -> None:
    connection.execute("PRAGMA foreign_keys=ON")


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    event.listen(engine, "connect", _foreign_keys)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


def plan(**values: Any) -> Strategy:
    return Strategy.model_validate(
        {
            "title": "Acquire valuable customers",
            "primary_metric": "customers",
            "target": "40",
            "period_start": "2026-07-01",
            "period_end": "2026-07-31",
            "budget_micros": 1_000_000_000,
            "currency_code": "USD",
            **values,
        }
    )


def command(payload: Any, version: int = 0) -> SaveRecord:
    return SaveRecord(expected_version=version, payload=payload.model_dump(mode="json"))


def test_strategy_versions_conflicts_and_restoration_are_audited(db: Session) -> None:
    workspace, _account, _campaign = seed_workspace(db, "alpha")
    repository = IntelligenceRepository(db)
    record = repository.save(workspace.id, RecordKind.STRATEGY, command(plan()), actor_role="owner")
    db.commit()
    original_revision = repository.revisions(workspace.id)[0]
    record = repository.save(
        workspace.id, RecordKind.STRATEGY, command(plan(target="50"), 1), actor_role="owner"
    )
    db.commit()
    assert record.version == 2
    with pytest.raises(ContextConflict):
        repository.save(
            workspace.id, RecordKind.STRATEGY, command(plan(target="60"), 1), actor_role="owner"
        )
    restored = repository.restore_strategy(workspace.id, original_revision.id, 2, "owner")
    db.commit()
    assert restored.version == 3 and restored.data["target"] == "40"
    revisions = repository.revisions(workspace.id)
    assert len(revisions) == 3 and revisions[0].action == "restore"
    assert revisions[1].before_data is not None
    assert revisions[1].before_data["target"] == "40"


def test_record_and_revision_boundaries_reject_cross_workspace_access(db: Session) -> None:
    alpha, _account, _campaign = seed_workspace(db, "alpha")
    beta, _other, other_campaign = seed_workspace(db, "beta")
    repository = IntelligenceRepository(db)
    record = repository.save(alpha.id, RecordKind.STRATEGY, command(plan()), actor_role="owner")
    db.commit()
    revision = repository.revisions(alpha.id)[0]
    with pytest.raises(ContextNotFound):
        repository.get(beta.id, record.id)
    with pytest.raises(ContextNotFound):
        repository.restore_strategy(beta.id, revision.id, 1, "owner")
    with pytest.raises(ValueError, match="unavailable"):
        repository.save(
            alpha.id,
            RecordKind.CREATIVE,
            SaveRecord(
                payload={
                    "title": "Foreign concept",
                    "campaign_id": other_campaign.id,
                    "audience": "Owners",
                    "hook": "Time back",
                    "starts_on": "2026-07-01",
                    "ends_on": "2026-07-31",
                }
            ),
            actor_role="owner",
        )
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(
            IntelligenceRevision(
                workspace_id=beta.id,
                record_id=record.id,
                version=9,
                kind="strategy",
                action="update",
                actor_role="owner",
                after_data={},
            )
        )
        db.flush()


@pytest.mark.parametrize(
    "values",
    [
        {"budget_micros": -1},
        {"target": "NaN"},
        {"target": "2.5"},
        {"period_end": "2026-06-01"},
        {"period_end": "2028-01-01"},
        {"currency_code": "US"},
        {"primary_metric": "contribution_profit"},
        {"contribution_margin_bps": 10001},
        {"unexpected_field": "ignored?"},
    ],
)
def test_invalid_strategy_values_are_rejected(values: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        plan(**values)


def test_budget_pacing_handles_reserves_completed_days_and_overspend() -> None:
    strategy = plan(period_end="2026-07-30")
    result = budget_pacing(
        strategy, date(2026, 7, 11), 200_000_000, 100_000_000, data_complete=True
    )
    assert result["elapsed_days"] == 10 and result["remaining_days"] == 20
    assert result["projected_spend_micros"] == 600_000_000
    assert result["available_micros"] == 700_000_000
    assert result["suggested_daily_ceiling_micros"] == 35_000_000
    missing = budget_pacing(strategy, date(2026, 7, 11), 200_000_000, 0, data_complete=False)
    assert missing["projected_spend_micros"] is None
    over = budget_pacing(strategy, date(2026, 8, 1), 1_100_000_000, 20_000_000, data_complete=True)
    assert over["available_micros"] == 0 and over["overspend_micros"] == 100_000_000
    assert over["remaining_days"] == 0 and over["suggested_daily_ceiling_micros"] is None


def test_scenario_is_a_bounded_sensitivity_model_with_financial_gate() -> None:
    strategy = plan()
    pacing = budget_pacing(strategy, date(2026, 7, 11), 200_000_000, 0, data_complete=True)
    result = scenario_forecast(
        strategy,
        pacing,
        ScenarioRequest(proposed_budget_micros=1_200_000_000),
        historical_value=40,
        historical_cost_micros=1_000_000_000,
        sample_size=40,
        ready=True,
    )
    assert result["requires_financial_approval"] is True and result["changes_applied"] is False
    assert result["low"] < result["expected"] < result["high"]
    assert result["expected"] < 40  # diminishing response versus a linear 40-customer forecast
    sparse = scenario_forecast(
        strategy,
        pacing,
        ScenarioRequest(proposed_budget_micros=1_200_000_000),
        historical_value=2,
        historical_cost_micros=100,
        sample_size=2,
        ready=True,
    )
    assert sparse["expected"] is None
    unavailable = scenario_forecast(
        strategy,
        pacing,
        ScenarioRequest(proposed_budget_micros=100),
        historical_value=40,
        historical_cost_micros=100,
        sample_size=40,
        ready=True,
    )
    assert unavailable["status"] == "below_spend_and_reservations"


def experiment(**values: Any) -> Experiment:
    return Experiment.model_validate(
        {
            "title": "Offer test",
            "hypothesis": "A clearer offer increases customer conversion.",
            "control_description": "Original",
            "treatment_description": "Clearer offer",
            "starts_on": "2026-06-01",
            "ends_on": "2026-06-15",
            "measurement_delay_days": 14,
            "randomized_assignment": True,
            "status": "completed",
            "control_units": 2000,
            "control_outcomes": 100,
            "treatment_units": 2000,
            "treatment_outcomes": 200,
            "observed_through": "2026-06-30",
            "evidence_reference": "Controlled experiment report",
            **values,
        }
    )


def test_experiments_require_final_mature_sufficient_randomized_evidence() -> None:
    strong = experiment_result(experiment(), date(2026, 7, 11))
    assert strong["status"] == "treatment_promising"
    assert strong["interval_low"] > 0.01
    assert (
        experiment_result(experiment(randomized_assignment=False), date(2026, 7, 11))["status"]
        == "observational_only"
    )
    assert (
        experiment_result(experiment(status="running"), date(2026, 7, 11))["status"]
        == "awaiting_completion_and_maturity"
    )
    assert (
        experiment_result(experiment(observed_through="2026-06-20"), date(2026, 7, 11))["status"]
        == "observation_period_incomplete"
    )
    sparse = experiment(
        control_units=50, control_outcomes=5, treatment_units=50, treatment_outcomes=10
    )
    assert experiment_result(sparse, date(2026, 7, 11))["status"] == "insufficient_sample"
    with pytest.raises(ValidationError):
        experiment(control_units=10, control_outcomes=11)


def test_experiment_design_locks_after_start_but_results_can_update(db: Session) -> None:
    workspace, _account, _campaign = seed_workspace(db, "alpha")
    repository = IntelligenceRepository(db)
    record = repository.save(
        workspace.id,
        RecordKind.EXPERIMENT,
        command(experiment(status="running")),
        actor_role="owner",
    )
    db.commit()
    with pytest.raises(ValueError, match="design"):
        repository.save(
            workspace.id,
            RecordKind.EXPERIMENT,
            command(experiment(minimum_lift_bps=0), 1),
            record_id=record.id,
            actor_role="owner",
        )
    result = repository.save(
        workspace.id,
        RecordKind.EXPERIMENT,
        command(experiment(treatment_outcomes=210), 1),
        record_id=record.id,
        actor_role="owner",
    )
    assert result.version == 2


def test_report_uses_canonical_spend_and_recalculates_event_dates(db: Session) -> None:
    workspace, account, campaign = seed_workspace(db, "alpha")
    repository = IntelligenceRepository(db)
    repository.save(workspace.id, RecordKind.STRATEGY, command(plan()), actor_role="owner")
    ad_group = AdGroup(
        campaign_id=campaign.id,
        platform=AdvertisingPlatform.GOOGLE_ADS,
        external_ad_group_id="test-group",
        name="Group",
    )
    db.add(ad_group)
    db.flush()
    for day in range(1, 11):
        add_metric(db, campaign, metric_date=date(2026, 7, day), cost_micros=10_000_000)
        add_metric(
            db, campaign, metric_date=date(2026, 7, day), cost_micros=10_000_000, ad_group=ad_group
        )
    event_plan = BusinessEvent(
        title="Launch",
        category="launch",
        starts_on=date(2026, 7, 20),
        ends_on=date(2026, 7, 21),
        status="confirmed",
        remaining_reserve_micros=50_000_000,
    )
    event_record = repository.save(
        workspace.id, RecordKind.EVENT, command(event_plan), actor_role="owner"
    )
    db.commit()
    report = IntelligenceService(db).report(workspace.id, as_of=NOW)
    assert report["budget"]["spend_micros"] == 100_000_000
    assert report["budget"]["reserved_micros"] == 50_000_000
    assert report["events"][0]["phase"] == "preparation"
    changed = event_plan.model_copy(
        update={"starts_on": date(2026, 8, 20), "ends_on": date(2026, 8, 21)}
    )
    repository.save(
        workspace.id,
        RecordKind.EVENT,
        command(changed, 1),
        actor_role="owner",
        record_id=event_record.id,
    )
    db.commit()
    updated = IntelligenceService(db).report(workspace.id, as_of=NOW)
    assert updated["budget"]["reserved_micros"] == 0
    assert updated["events"][0]["phase"] == "upcoming"
    assert updated["execution"]["live_changes_enabled"] is False
    assert updated["execution"]["conversion_uploads_enabled"] is False
    assert account.workspace_id == workspace.id


def test_mixed_currency_never_sums_incompatible_spend(db: Session) -> None:
    workspace, _account, campaign = seed_workspace(db, "alpha")
    IntelligenceRepository(db).save(
        workspace.id, RecordKind.STRATEGY, command(plan()), actor_role="owner"
    )
    db.add(
        AdvertisingAccount(
            workspace_id=workspace.id,
            platform=AdvertisingPlatform.GOOGLE_ADS,
            external_account_id="euro-account",
            name="EUR",
            currency_code="EUR",
        )
    )
    add_metric(db, campaign, metric_date=date(2026, 7, 1))
    report = IntelligenceService(db).report(workspace.id, as_of=NOW)
    assert report["budget"]["spend_micros"] is None
    assert all(s["expected"] is None for s in report["scenarios"])


def test_report_correlates_existing_crm_data_without_identifiers(db: Session) -> None:
    workspace, account, campaign = seed_workspace(db, "alpha")
    for offset in range(28):
        add_metric(db, campaign, metric_date=date(2026, 5, 15) + timedelta(days=offset))
    WebAnalyticsRepository(db).record_ga4_event(ga4_event(workspace, account, campaign))
    add_complete_journey(db, workspace)
    db.add(
        JobRun(
            workspace_id=workspace.id,
            account_id=account.id,
            platform=AdvertisingPlatform.GOOGLE_ADS,
            job_name="google_ads_read_only_sync",
            status=JobRunStatus.SUCCEEDED,
            started_at=NOW - timedelta(minutes=1),
            finished_at=NOW,
            records_processed=1,
        )
    )
    db.commit()
    report = IntelligenceService(db).report(workspace.id, as_of=NOW)
    assert report["current"]["business_outcome_count"] == 1
    assert report["current"]["observed_revenue_micros"] == 500_000_000
    rendered = str(report)
    for private in ("paid-click-001", "practice-pseudo-001", "lead-001", "ga4-user-001"):
        assert private not in rendered
    assert report["window"]["previous_end"] < report["window"]["start"]


@pytest.fixture()
def client(db: Session, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    monkeypatch.setattr(settings, "api_token", SecretStr("x" * 48))
    monkeypatch.setattr(settings, "app_env", "development")

    def override_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(
        app, base_url="https://testserver", headers={"Authorization": "Bearer " + "x" * 48}
    ) as browser:
        yield browser
    app.dependency_overrides.clear()


def csrf(html: str) -> str:
    import re

    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match is not None
    return match.group(1)


def test_authenticated_api_dashboard_forms_and_exports(client: TestClient, db: Session) -> None:
    workspace, _account, _campaign = seed_workspace(db, "alpha")
    base = "/api/v1/workspaces/alpha/intelligence"
    created = client.post(base + "/records/strategy", json=command(plan()).model_dump(mode="json"))
    assert created.status_code == 201
    assert client.get(base).status_code == 200
    page = client.get("/dashboard/workspaces/alpha/intelligence")
    assert page.status_code == 200 and "What should change next?" in page.text
    assert "script-src 'none'" in page.headers["content-security-policy"]
    assert client.get("/dashboard/portfolio").status_code == 200
    for kind in ("strategy", "event", "creative", "experiment", "cost", "change"):
        form = client.get(f"/dashboard/workspaces/alpha/intelligence/edit/{kind}")
        assert form.status_code == 200
    saved = client.post(
        "/dashboard/workspaces/alpha/intelligence/save/event",
        data={
            "csrf_token": csrf(page.text),
            "expected_version": "0",
            "title": "Launch",
            "category": "launch",
            "starts_on": "2026-07-20",
            "ends_on": "2026-07-21",
            "remaining_reserve_micros": "50.50",
        },
        follow_redirects=False,
    )
    assert saved.status_code == 303
    event_record = IntelligenceRepository(db).list_records(workspace.id, RecordKind.EVENT)[0]
    assert event_record.data["remaining_reserve_micros"] == 50_500_000
    assert client.get("/dashboard/workspaces/alpha/intelligence/brief.csv").status_code == 200
    answer = client.post(base + "/ask", json={"question": "What can I spend?"})
    assert answer.status_code == 200 and answer.json()["topic"] == "budget"


def test_csrf_and_workspace_viewer_permissions_block_business_writes(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, _account, _campaign = seed_workspace(db, "alpha")
    beta, _other, _other_campaign = seed_workspace(db, "beta")
    page = client.get("/dashboard/workspaces/alpha/intelligence")
    denied = client.post(
        "/dashboard/workspaces/alpha/intelligence/save/event", data={"title": "Blocked"}
    )
    assert denied.status_code == 403
    assert IntelligenceRepository(db).count(workspace.id, RecordKind.EVENT) == 0
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "iap_audience", "test-audience")
    monkeypatch.setattr(
        "app.dashboard.auth.verify_iap_jwt",
        lambda assertion, audience: {"email": "viewer@example.test"},
    )
    client.headers["x-goog-iap-jwt-assertion"] = "synthetic-test-assertion"
    db.add(
        WorkspaceMembership(
            workspace_id=workspace.id,
            principal="viewer@example.test",
            role="viewer",
            status="active",
        )
    )
    db.commit()
    assert client.get("/dashboard/workspaces/alpha/intelligence").status_code == 200
    assert client.get("/dashboard/workspaces/beta/intelligence").status_code == 404
    denied = client.post(
        "/dashboard/workspaces/alpha/intelligence/save/event", data={"csrf_token": csrf(page.text)}
    )
    assert denied.status_code == 403
    assert IntelligenceRepository(db).count(beta.id, RecordKind.EVENT) == 0


def test_forms_preserve_money_precision_and_csv_formula_safety() -> None:
    payload = _form_payload(
        RecordKind.STRATEGY,
        {
            "title": "Plan",
            "target": "10",
            "primary_metric": "customers",
            "period_start": "2026-07-01",
            "period_end": "2026-07-31",
            "budget_micros": "12.345678",
            "contribution_margin_bps": "35.5",
        },
    )
    assert payload["budget_micros"] == 12_345_678 and payload["contribution_margin_bps"] == 3550
    fields = _fields(RecordKind.STRATEGY, payload)
    assert next(f for f in fields if f["name"] == "budget_micros")["value"] == Decimal("12.345678")
    assert _csv_cell("=HYPERLINK(1)").startswith("'")
    assert _csv_cell(" @formula").startswith("'")


def test_new_migration_upgrades_in_disposable_sqlite() -> None:
    from importlib import import_module

    migration = import_module("migrations.versions.20260906_0017_business_intelligence")
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        # Only the local disposable schema is used; no application or production URL.
        connection.exec_driver_sql("CREATE TABLE workspaces (id INTEGER PRIMARY KEY)")
        connection.exec_driver_sql("CREATE TABLE analysis_runs (id INTEGER PRIMARY KEY)")
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            migration.upgrade()
    engine.dispose()


def test_profit_forecasts_charge_the_full_proposed_spend() -> None:
    strategy = plan(primary_metric="contribution_profit", contribution_margin_bps=5000)
    pacing = budget_pacing(strategy, NOW.date(), 0, 0, data_complete=True)
    result = scenario_forecast(
        strategy,
        pacing,
        ScenarioRequest(proposed_budget_micros=2_000_000_000, response_elasticity=Decimal("0.5")),
        historical_value=1000,
        historical_cost_micros=1_000_000_000,
        sample_size=40,
        ready=True,
    )
    # Historical contribution before ads = 2000; forecast = 2000 * sqrt(2) - 2000.
    assert result["expected"] == 828.43
    assert result["requires_financial_approval"] is True


def test_allocation_preserves_total_and_reserves_and_bounds_each_change() -> None:
    strategy = plan()
    pacing = budget_pacing(strategy, NOW.date(), 200_000_000, 100_000_000, data_complete=True)
    campaigns = [
        {"id": 1, "name": "Control", "spend_micros": 400_000_000, "sample": 40, "goal_value": 40},
        {"id": 2, "name": "Candidate", "spend_micros": 100_000_000, "sample": 30, "goal_value": 30},
    ]
    result = allocation_preview(strategy, pacing, campaigns, ready=True)
    assert result["status"] == "review_transfer" and not result["changes_applied"]
    assert sum(r["proposed_micros"] for r in result["rows"]) == 700_000_000
    for row in result["rows"]:
        assert abs(row["proposed_micros"] - row["baseline_micros"]) <= row["baseline_micros"] // 10
    campaigns[1]["sample"] = 1
    assert allocation_preview(strategy, pacing, campaigns, ready=True)["status"] == (
        "insufficient_campaign_outcomes"
    )
    assert allocation_preview(strategy, pacing, campaigns, ready=False)["rows"] == []


def test_an_account_without_metrics_blocks_workspace_forecasts(db: Session) -> None:
    workspace, _account, campaign = seed_workspace(db, "alpha")
    for offset in range(10):
        add_metric(db, campaign, metric_date=date(2026, 7, 1) + timedelta(days=offset))
    db.add(
        AdvertisingAccount(
            workspace_id=workspace.id,
            platform=AdvertisingPlatform.GOOGLE_ADS,
            external_account_id="additional-account",
            name="Additional account",
            currency_code="USD",
        )
    )
    db.flush()
    spend, complete, _last = IntelligenceService(db)._spend(workspace.id, plan(), NOW.date())
    assert spend and not complete


def test_decision_evidence_is_immutable_deduplicated_and_checked_when_accepted(
    client: TestClient,
    db: Session,
) -> None:
    seed_workspace(db, "alpha")
    base = "/api/v1/workspaces/alpha/intelligence"
    client.post(base + "/records/strategy", json=command(plan()).model_dump(mode="json"))
    item = client.get(base).json()["recommendations"][0]
    payload = {
        "title": item["title"],
        "recommendation_key": item["key"],
        "evidence_fingerprint": item["evidence_fingerprint"],
        "review_on": item["review_on"],
        "status": "planned",
        "evidence_snapshot": {"invented": "not trusted"},
    }
    created = client.post(base + "/records/decision", json={"payload": payload})
    assert created.status_code == 201
    record = created.json()
    assert "invented" not in record["data"]["evidence_snapshot"]
    assert client.post(base + "/records/decision", json={"payload": payload}).status_code == 409
    client.post(
        base + "/records/strategy", json=command(plan(target=50), 1).model_dump(mode="json")
    )
    updated = client.put(
        base + f"/records/decision/{record['id']}",
        json={
            "expected_version": 1,
            "payload": {**record["data"], "status": "accepted", "reason": "Review completed"},
        },
    )
    assert updated.status_code == 409


def test_scheduled_strategy_briefs_are_saved_once_and_workspace_scoped(db: Session) -> None:
    from app.analysis.enums import AnalysisCadence, AnalysisRunStatus
    from app.analysis.service import AnalysisRunService

    alpha, _account, _campaign = seed_workspace(db, "alpha")
    beta, _other, _other_campaign = seed_workspace(db, "beta")
    IntelligenceRepository(db).save(
        alpha.id, RecordKind.STRATEGY, command(plan()), actor_role="owner"
    )
    db.commit()
    args: dict[str, Any] = dict(
        workspace_id=alpha.id,
        cadence=AnalysisCadence.NIGHTLY,
        run_key="nightly:2026-07-11:business-test",
        scheduled_for=NOW,
        window_days=28,
        as_of=NOW,
    )
    first = AnalysisRunService(db).execute(**args)
    assert first.status == AnalysisRunStatus.SUCCEEDED and first.decision_brief is not None
    assert first.decision_brief["strategy_version"] == 1
    assert AnalysisRunService(db).execute(**args).id == first.id
    assert len(IntelligenceService(db).report(alpha.id, as_of=NOW)["saved_briefs"]) == 1
    assert IntelligenceService(db).report(beta.id, as_of=NOW)["saved_briefs"] == []


def test_custom_scenario_and_form_errors_are_reviewable(client: TestClient, db: Session) -> None:
    seed_workspace(db, "alpha")
    root = "/dashboard/workspaces/alpha/intelligence"
    client.post(
        "/api/v1/workspaces/alpha/intelligence/records/strategy",
        json=command(plan()).model_dump(mode="json"),
    )
    page = client.get(root)
    scenario = client.post(
        root + "/scenario",
        data={
            "csrf_token": csrf(page.text),
            "proposed_budget": "1200.50",
            "response_elasticity": "0.5",
        },
    )
    assert scenario.status_code == 200 and "Your custom scenario" in scenario.text
    assert "Financial approval required" in scenario.text
    invalid = client.post(
        root + "/save/event",
        data={
            "csrf_token": csrf(page.text),
            "title": "Keep my entered title",
            "category": "launch",
            "starts_on": "2026-07-31",
            "ends_on": "2026-07-01",
        },
    )
    assert invalid.status_code == 422 and "Keep my entered title" in invalid.text
    answer = client.post(
        root + "/ask",
        data={
            "csrf_token": csrf(page.text),
            "question": "What is my budget?",
        },
    )
    assert "USD 1,000.00" in answer.text and "coverage is incomplete" in answer.text
