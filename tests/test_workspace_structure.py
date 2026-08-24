from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from sqlite3 import Connection as SQLiteConnection

import pytest
from app.ads.enums import AdvertisingPlatform, JobRunStatus, RecommendationStatus
from app.ads.models import AdvertisingAccount, JobRun, Recommendation
from app.ads.operations import sync_health
from app.crm.models import CrmConnection, CrmEventRecord
from app.crm.worker import CrmEventProcessor
from app.database.session import Base, get_db
from app.main import app
from app.settings import Settings, settings
from app.workspaces.access import (
    accessible_workspace_ids,
    require_workspace_review,
    require_workspace_view,
    workspace_role,
)
from app.workspaces.models import (
    Workspace,
    WorkspaceConfiguration,
    WorkspaceFinding,
    WorkspaceIntegration,
    WorkspaceMembership,
)
from app.workspaces.repository import WorkspaceRepository
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import ConnectionPoolEntry, StaticPool


def enable_sqlite_foreign_keys(
    dbapi_connection: SQLiteConnection, _connection_record: ConnectionPoolEntry
) -> None:
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    event.listen(engine, "connect", enable_sqlite_foreign_keys)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def add_workspace(
    db: Session,
    *,
    slug: str,
    name: str,
    client_name: str,
    member: str,
) -> Workspace:
    workspace = Workspace(
        slug=slug,
        name=name,
        client_name=client_name,
        status="active",
        is_default=slug == "denticode",
    )
    db.add(workspace)
    db.flush()
    db.add_all(
        [
            WorkspaceConfiguration(
                workspace_id=workspace.id,
                analysis={"target_cpa_micros": 50_000_000},
                automation={"live_writes_enabled": False},
                notifications={"daily_digest": True},
                branding={"workspace_name": name},
            ),
            WorkspaceIntegration(
                workspace_id=workspace.id,
                integration_key="google-ads-primary",
                provider="google_ads",
                display_name="Google Ads",
                status="active",
                configuration={"mode": "read_only"},
                secret_manager_reference=f"projects/example/secrets/{slug}-google-ads",
            ),
            WorkspaceMembership(
                workspace_id=workspace.id,
                principal=member,
                role="viewer",
                status="active",
            ),
        ]
    )
    db.flush()
    return workspace


def request_for(identity: str) -> Request:
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "https",
            "path": "/dashboard",
            "raw_path": b"/dashboard",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 443),
            "server": ("testserver", 443),
        }
    )
    request.state.dashboard_identity = identity
    return request


def test_same_advertising_account_identifier_is_unique_only_inside_workspace(
    db: Session,
) -> None:
    denticode = add_workspace(
        db,
        slug="denticode",
        name="Denticode Ad Analyzer",
        client_name="Denticode",
        member="denticode@example.com",
    )
    second = add_workspace(
        db,
        slug="second-client",
        name="Second Client Ad Analyzer",
        client_name="Second Client",
        member="second@example.com",
    )
    db.add_all(
        [
            AdvertisingAccount(
                workspace_id=denticode.id,
                platform=AdvertisingPlatform.GOOGLE_ADS,
                external_account_id="shared-external-id",
                name="Denticode Google Ads",
                currency_code="USD",
            ),
            AdvertisingAccount(
                workspace_id=second.id,
                platform=AdvertisingPlatform.GOOGLE_ADS,
                external_account_id="shared-external-id",
                name="Second Client Google Ads",
                currency_code="USD",
            ),
        ]
    )
    db.commit()

    db.add(
        AdvertisingAccount(
            workspace_id=denticode.id,
            platform=AdvertisingPlatform.GOOGLE_ADS,
            external_account_id="shared-external-id",
            name="Duplicate Denticode account",
            currency_code="USD",
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()


def test_repository_returns_only_workspace_owned_resources(db: Session) -> None:
    denticode = add_workspace(
        db,
        slug="denticode",
        name="Denticode Ad Analyzer",
        client_name="Denticode",
        member="denticode@example.com",
    )
    second = add_workspace(
        db,
        slug="second-client",
        name="Second Client Ad Analyzer",
        client_name="Second Client",
        member="second@example.com",
    )
    db.add_all(
        [
            AdvertisingAccount(
                workspace_id=denticode.id,
                platform=AdvertisingPlatform.GOOGLE_ADS,
                external_account_id="denticode-account",
                name="Denticode account",
                currency_code="USD",
            ),
            AdvertisingAccount(
                workspace_id=second.id,
                platform=AdvertisingPlatform.GOOGLE_ADS,
                external_account_id="second-account",
                name="Second account",
                currency_code="USD",
            ),
        ]
    )
    db.commit()

    repository = WorkspaceRepository(db)
    workspaces, total = repository.list_workspaces({denticode.id}, 25, 0)
    accounts, account_total = repository.list_advertising_accounts(denticode.id, 25, 0)

    assert total == 1
    assert [workspace.name for workspace in workspaces] == ["Denticode Ad Analyzer"]
    assert account_total == 1
    assert [account.name for account in accounts] == ["Denticode account"]
    configuration = repository.configuration(denticode.id)
    assert configuration is not None
    assert configuration.branding == {"workspace_name": "Denticode Ad Analyzer"}
    assert [item.workspace_id for item in repository.integrations(denticode.id)] == [denticode.id]
    assert [item.principal for item in repository.memberships(denticode.id)] == [
        "denticode@example.com"
    ]


def test_cross_workspace_recommendation_and_finding_references_are_rejected(
    db: Session,
) -> None:
    denticode = add_workspace(
        db,
        slug="denticode",
        name="Denticode Ad Analyzer",
        client_name="Denticode",
        member="denticode@example.com",
    )
    second = add_workspace(
        db,
        slug="second-client",
        name="Second Client Ad Analyzer",
        client_name="Second Client",
        member="second@example.com",
    )
    account = AdvertisingAccount(
        workspace_id=denticode.id,
        platform=AdvertisingPlatform.GOOGLE_ADS,
        external_account_id="denticode-account",
        name="Denticode account",
        currency_code="USD",
    )
    db.add(account)
    db.commit()

    db.add(
        Recommendation(
            workspace_id=second.id,
            platform=AdvertisingPlatform.GOOGLE_ADS,
            account_id=account.id,
            recommendation_type="test",
            severity="low",
            confidence=Decimal("0.5000"),
            rationale="cross-workspace reference must fail",
            supporting_metrics={},
            planned_action={},
            status=RecommendationStatus.PENDING_REVIEW,
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    db.add(
        WorkspaceFinding(
            workspace_id=second.id,
            advertising_account_id=account.id,
            dedupe_key="cross-workspace",
            code="test",
            severity="low",
            message="cross-workspace reference must fail",
            supporting_metrics={},
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()


def test_workspace_memberships_enforce_view_and_review_roles(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    denticode = add_workspace(
        db,
        slug="denticode",
        name="Denticode Ad Analyzer",
        client_name="Denticode",
        member="viewer@example.com",
    )
    second = add_workspace(
        db,
        slug="second-client",
        name="Second Client Ad Analyzer",
        client_name="Second Client",
        member="second@example.com",
    )
    db.commit()
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "platform_admin_emails_csv", "platform@example.com")
    request = request_for("viewer@example.com")

    assert accessible_workspace_ids(request, db) == {denticode.id}
    assert workspace_role(request, db, denticode.id) == "viewer"
    assert require_workspace_view(request, db, denticode.id) == "viewer"
    with pytest.raises(HTTPException) as hidden:
        require_workspace_view(request, db, second.id)
    assert hidden.value.status_code == 404
    with pytest.raises(HTTPException) as denied:
        require_workspace_review(request, db, denticode.id)
    assert denied.value.status_code == 403

    platform_request = request_for("platform@example.com")
    assert accessible_workspace_ids(platform_request, db) is None
    assert require_workspace_review(platform_request, db, second.id) == "platform_admin"


def test_sync_health_isolated_to_accessible_workspaces(db: Session) -> None:
    denticode = add_workspace(
        db,
        slug="denticode",
        name="Denticode Ad Analyzer",
        client_name="Denticode",
        member="denticode@example.com",
    )
    second = add_workspace(
        db,
        slug="second-client",
        name="Second Client Ad Analyzer",
        client_name="Second Client",
        member="second@example.com",
    )
    now = datetime(2026, 8, 2, 12, tzinfo=UTC)
    db.add_all(
        [
            JobRun(
                workspace_id=denticode.id,
                platform=AdvertisingPlatform.GOOGLE_ADS,
                job_name="google_ads_read_only_sync",
                status=JobRunStatus.SUCCEEDED,
                started_at=now - timedelta(minutes=20),
                finished_at=now - timedelta(minutes=19),
            ),
            JobRun(
                workspace_id=second.id,
                platform=AdvertisingPlatform.GOOGLE_ADS,
                job_name="google_ads_read_only_sync",
                status=JobRunStatus.FAILED,
                started_at=now - timedelta(minutes=1),
                finished_at=now,
                error_message="private failure detail",
            ),
        ]
    )
    db.commit()

    scoped = sync_health(
        db,
        Settings(AD_ANALYZER_SYNC_STALE_AFTER_MINUTES=60),
        now,
        workspace_ids={denticode.id},
    )
    other = sync_health(
        db,
        Settings(AD_ANALYZER_SYNC_STALE_AFTER_MINUTES=60),
        now,
        workspace_ids={second.id},
    )

    assert scoped.status == "Healthy"
    assert scoped.last_failure_at is None
    assert other.status == "Failed"


def test_crm_worker_routes_events_to_the_selected_workspace_integration(db: Session) -> None:
    denticode = add_workspace(
        db,
        slug="denticode",
        name="Denticode Ad Analyzer",
        client_name="Denticode",
        member="denticode@example.com",
    )
    second = add_workspace(
        db,
        slug="second-client",
        name="Second Client Ad Analyzer",
        client_name="Second Client",
        member="second@example.com",
    )
    db.add_all(
        [
            CrmConnection(
                workspace_id=denticode.id,
                name="primary",
                status="active",
                secret_manager_reference="projects/example/secrets/denticode-crm",
            ),
            CrmConnection(
                workspace_id=second.id,
                name="primary",
                status="active",
                secret_manager_reference="projects/example/secrets/second-crm",
            ),
        ]
    )
    db.commit()

    processed = CrmEventProcessor(db).process(
        {
            "workspace_id": second.id,
            "payload_version": 1,
            "event_id": "evt-second-client",
            "event_type": "lead_created",
            "occurred_at": datetime.now(UTC).isoformat(),
            "crm_lead_id": "lead-second-client",
            "utm_source": "google",
        }
    )
    record = db.query(CrmEventRecord).one()
    connection = db.get(CrmConnection, record.connection_id)

    assert processed is True
    assert connection is not None
    assert connection.workspace_id == second.id


def test_workspace_operator_api_uses_platform_and_workspace_names(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = "w" * 48
    denticode = add_workspace(
        db,
        slug="denticode",
        name="Denticode Ad Analyzer",
        client_name="Denticode",
        member="denticode@example.com",
    )
    db.add(
        AdvertisingAccount(
            workspace_id=denticode.id,
            platform=AdvertisingPlatform.GOOGLE_ADS,
            external_account_id="denticode-account",
            name="Denticode Google Ads",
            currency_code="USD",
        )
    )
    db.commit()
    monkeypatch.setattr(settings, "api_token", SecretStr(token))
    monkeypatch.setattr(settings, "app_env", "development")

    def override_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app, base_url="https://testserver")
        headers = {"Authorization": f"Bearer {token}"}
        root = client.get("/")
        dashboard = client.get("/dashboard", headers=headers)
        workspace_dashboard = client.get("/dashboard/workspaces/denticode")
        workspace = client.get("/api/v1/workspaces/denticode", headers=headers)
        accounts = client.get("/api/v1/workspaces/denticode/advertising-accounts", headers=headers)
        integrations = client.get("/api/v1/workspaces/denticode/integrations", headers=headers)
    finally:
        app.dependency_overrides.clear()

    assert root.json()["name"] == "ad-analyzer"
    assert dashboard.status_code == 200
    assert "Ad Analyzer" in dashboard.text
    assert "Denticode Ad Analyzer" in dashboard.text
    assert workspace_dashboard.status_code == 200
    assert "Workspace boundary" in workspace_dashboard.text
    assert workspace.json()["name"] == "Denticode Ad Analyzer"
    assert accounts.json()["items"][0]["workspace_id"] == denticode.id
    assert integrations.json()[0]["credential_reference_configured"] is True
    assert "secret_manager_reference" not in integrations.json()[0]
    assert "projects/example" not in integrations.text
