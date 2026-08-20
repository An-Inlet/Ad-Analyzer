from collections.abc import Generator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from sqlite3 import Connection as SQLiteConnection
from typing import cast

import pytest
from app.ads.enums import AdvertisingPlatform, RecommendationStatus
from app.ads.models import AdvertisingAccount, Recommendation, RecommendationAudit
from app.analysis.enums import AnalysisCadence, AnalysisRunStatus
from app.analysis.models import AnalysisRun
from app.database.session import Base
from app.learning import DecisionLearningService
from app.optimizer.recommendations import Finding
from app.recommendations import RecommendationCandidate, RecommendationGenerationService
from app.workspaces.models import Workspace
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import ConnectionPoolEntry, StaticPool

from tests.test_api_v1_read_only import make_client


def enable_sqlite_foreign_keys(
    dbapi_connection: SQLiteConnection,
    _connection_record: ConnectionPoolEntry,
) -> None:
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


@pytest.fixture()
def database() -> Generator[tuple[Session, Engine], None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    event.listen(engine, "connect", enable_sqlite_foreign_keys)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session, engine
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def add_workspace(db: Session, slug: str) -> tuple[Workspace, AdvertisingAccount]:
    workspace = Workspace(
        slug=slug,
        name=f"{slug.title()} Ad Analyzer",
        client_name=slug.title(),
        status="active",
        is_default=slug == "denticode",
    )
    db.add(workspace)
    db.flush()
    account = AdvertisingAccount(
        workspace_id=workspace.id,
        platform=AdvertisingPlatform.GOOGLE_ADS,
        external_account_id=f"{slug}-account",
        name=f"{slug.title()} Ads",
        currency_code="USD",
        time_zone="UTC",
    )
    db.add(account)
    db.flush()
    return workspace, account


def add_decision(
    db: Session,
    *,
    workspace: Workspace,
    account: AdvertisingAccount,
    recommendation_type: str,
    scope_type: str,
    review_action: str,
    action: str,
    decided_at: datetime,
    reason: str = "operator context",
) -> Recommendation:
    status = (
        RecommendationStatus.APPROVED if action == "approved" else RecommendationStatus.REJECTED
    )
    recommendation = Recommendation(
        workspace_id=workspace.id,
        platform=account.platform,
        account_id=account.id,
        recommendation_type=recommendation_type,
        severity="medium",
        confidence=Decimal("0.7000"),
        rationale="Deterministic test recommendation.",
        supporting_metrics={},
        planned_action={
            "mode": "human_review_required",
            "mutation": "none_without_human_approval",
            "review_action": review_action,
            "scope": {"type": scope_type, "id": account.id, "label": account.name},
        },
        status=status,
        generated_at=decided_at - timedelta(days=1),
        expires_at=decided_at + timedelta(days=13),
    )
    db.add(recommendation)
    db.flush()
    db.add(
        RecommendationAudit(
            recommendation_id=recommendation.id,
            actor="operator@example.com",
            action=action,
            reason=reason,
            created_at=decided_at,
            updated_at=decided_at,
        )
    )
    db.flush()
    return recommendation


def test_learning_aggregates_decisions_without_cross_workspace_or_reason_text(
    database: tuple[Session, Engine],
) -> None:
    db, _engine = database
    workspace, account = add_workspace(db, "denticode")
    other, other_account = add_workspace(db, "other-client")
    base_time = datetime(2026, 8, 18, 12, tzinfo=UTC)
    for index, action in enumerate(("approved", "rejected", "approved", "rejected", "approved")):
        add_decision(
            db,
            workspace=workspace,
            account=account,
            recommendation_type="low_ctr",
            scope_type="campaign",
            review_action="review_relevance_and_creative",
            action=action,
            decided_at=base_time + timedelta(hours=index),
            reason="private-reason-marker",
        )
    add_decision(
        db,
        workspace=other,
        account=other_account,
        recommendation_type="low_ctr",
        scope_type="campaign",
        review_action="review_relevance_and_creative",
        action="rejected",
        decided_at=base_time,
    )
    db.commit()

    snapshot = DecisionLearningService(db).snapshot(workspace.id)

    assert snapshot.decision_count == 5
    assert snapshot.approved_count == 3
    assert snapshot.rejected_count == 2
    assert len(snapshot.profiles) == 1
    profile = snapshot.profiles[0]
    assert profile.acceptance_rate == Decimal("0.6000")
    assert profile.smoothed_acceptance_rate == Decimal("0.5714")
    assert profile.evidence_state == "established"
    assert profile.last_decision_at.replace(tzinfo=UTC) == base_time + timedelta(hours=4)
    assert "private-reason-marker" not in repr(snapshot)
    assert "operator@example.com" not in repr(snapshot)


def test_generation_uses_learning_only_after_severity_and_impact(
    database: tuple[Session, Engine],
) -> None:
    db, _engine = database
    workspace, account = add_workspace(db, "denticode")
    base_time = datetime(2026, 8, 18, 12, tzinfo=UTC)
    for index in range(3):
        add_decision(
            db,
            workspace=workspace,
            account=account,
            recommendation_type="low_ctr",
            scope_type="account",
            review_action="review_relevance_and_creative",
            action="rejected",
            decided_at=base_time + timedelta(minutes=index),
        )
        add_decision(
            db,
            workspace=workspace,
            account=account,
            recommendation_type="unusual_spend_change",
            scope_type="account",
            review_action="review_spend_shift",
            action="approved",
            decided_at=base_time + timedelta(minutes=10 + index),
        )
    source_run = AnalysisRun(
        workspace_id=workspace.id,
        run_key="nightly:decision-learning",
        cadence=AnalysisCadence.NIGHTLY,
        status=AnalysisRunStatus.RUNNING,
        schedule_policy_version="v1",
        scheduled_for=datetime(2026, 8, 19, 2, tzinfo=UTC),
        metric_date_from=date(2026, 7, 20),
        metric_date_to=date(2026, 8, 18),
        outcome_date_from=date(2026, 4, 21),
        outcome_date_to=date(2026, 5, 20),
        started_at=datetime(2026, 8, 19, 12, tzinfo=UTC),
        blocking_reasons=[],
    )
    db.add(source_run)
    db.commit()
    candidates = [
        RecommendationCandidate(
            workspace_id=workspace.id,
            platform=account.platform,
            account_id=account.id,
            campaign_id=None,
            scope_type="account",
            scope_id=account.id,
            scope_label=account.name,
            source_text_redacted=False,
            finding=Finding(
                code="low_ctr",
                severity="medium",
                message="CTR is below the deterministic threshold.",
                supporting_metrics={"ctr": "0.01"},
            ),
            impact_micros=1_000_000,
        ),
        RecommendationCandidate(
            workspace_id=workspace.id,
            platform=account.platform,
            account_id=account.id,
            campaign_id=None,
            scope_type="account",
            scope_id=account.id,
            scope_label=account.name,
            source_text_redacted=False,
            finding=Finding(
                code="unusual_spend_change",
                severity="medium",
                message="Spend changed beyond the deterministic threshold.",
                supporting_metrics={"spend_change_ratio": "0.75"},
            ),
            impact_micros=1_000_000,
        ),
    ]

    result = RecommendationGenerationService(db).generate(
        candidates,
        source_analysis_run_id=source_run.id,
        as_of=datetime(2026, 8, 19, 12, tzinfo=UTC),
        limit=1,
    )

    assert result.created_count == 1
    assert result.capped_count == 1
    recommendation = result.recommendations[0]
    assert recommendation.recommendation_type == "unusual_spend_change"
    learning = cast(dict[str, object], recommendation.planned_action["decision_learning"])
    assert learning == {
        "policy_version": "v1",
        "approved_count": 3,
        "rejected_count": 0,
        "decision_count": 3,
        "acceptance_rate": "1.0000",
        "smoothed_acceptance_rate": "0.8000",
        "evidence_state": "limited",
        "effect": "context_and_equal_impact_tie_break_only",
        "reason_text_used": False,
    }


def test_operator_api_and_dashboard_expose_only_workspace_learning() -> None:
    from app.dashboard.auth import require_dashboard_session
    from app.main import app

    with make_client() as (client, db, ids):
        workspace = db.get(Workspace, ids["workspace"])
        account = db.get(AdvertisingAccount, ids["a1"])
        assert workspace is not None
        assert account is not None
        add_decision(
            db,
            workspace=workspace,
            account=account,
            recommendation_type="low_ctr",
            scope_type="account",
            review_action="review_relevance_and_creative",
            action="approved",
            decided_at=datetime(2026, 8, 18, 12, tzinfo=UTC),
            reason="api-private-reason-marker",
        )
        other, other_account = add_workspace(db, "other-client")
        add_decision(
            db,
            workspace=other,
            account=other_account,
            recommendation_type="other_workspace_signal",
            scope_type="account",
            review_action="review_performance_signal",
            action="rejected",
            decided_at=datetime(2026, 8, 18, 13, tzinfo=UTC),
        )
        db.commit()
        app.dependency_overrides[require_dashboard_session] = lambda: None

        response = client.get("/api/v1/workspaces/denticode/decision-learning")
        dashboard = client.get("/dashboard/workspaces/denticode")

        assert response.status_code == 200
        payload = response.json()
        assert payload["workspace_id"] == workspace.id
        assert payload["decision_count"] == 1
        assert payload["reason_text_used"] is False
        assert payload["profiles"][0]["acceptance_rate"] == "1.0000"
        assert "other_workspace_signal" not in response.text
        assert "api-private-reason-marker" not in response.text
        assert "operator@example.com" not in response.text
        assert dashboard.status_code == 200
        assert "Decision learning" in dashboard.text
        assert "100.00%" in dashboard.text
        assert "other workspace signal" not in dashboard.text
