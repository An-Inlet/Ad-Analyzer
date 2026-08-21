from collections.abc import Generator
from email.message import Message
from importlib import import_module
from pathlib import Path
from sqlite3 import Connection as SQLiteConnection
from types import TracebackType
from urllib.error import HTTPError
from urllib.request import Request

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.automation import AutomationControlKey, AutomationControlService
from app.automation.github import (
    GITHUB_HOURLY_AUDIT_VARIABLE,
    GitHubActionsVariableClient,
    GitHubAutomationControlError,
)
from app.automation.models import (
    AutomationControlAudit,
    PlatformAutomationControl,
    WorkspaceAutomationControl,
)
from app.automation.service import UnknownAutomationControlError
from app.dashboard.auth import require_dashboard_session
from app.database.session import Base, get_db
from app.main import app
from app.settings import settings
from app.workspaces.models import Workspace, WorkspaceConfiguration, WorkspaceMembership
from fastapi import Request as FastAPIRequest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, event, func, inspect, select, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import ConnectionPoolEntry, StaticPool


def enable_foreign_keys(
    dbapi_connection: SQLiteConnection,
    _connection_record: ConnectionPoolEntry,
) -> None:
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


@pytest.fixture()
def database() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    event.listen(engine, "connect", enable_foreign_keys)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def seed_workspace(
    db: Session,
    *,
    slug: str,
    member: str = "owner@example.com",
    role: str = "owner",
) -> Workspace:
    workspace = Workspace(
        slug=slug,
        name=f"{slug.title()} Ad Analyzer",
        client_name=slug.title(),
        status="active",
        is_default=slug == "denticode",
    )
    db.add(workspace)
    db.flush()
    db.add_all(
        [
            WorkspaceConfiguration(
                workspace_id=workspace.id,
                analysis={},
                automation={"live_writes_enabled": False},
                notifications={},
                branding={"workspace_name": workspace.name},
            ),
            WorkspaceMembership(
                workspace_id=workspace.id,
                principal=member,
                role=role,
                status="active",
            ),
        ]
    )
    db.commit()
    return workspace


def test_master_controls_override_workspace_controls_and_are_audited(
    database: Session,
) -> None:
    first = seed_workspace(database, slug="denticode")
    second = seed_workspace(database, slug="second")
    controls = AutomationControlService(database)

    assert controls.master_enabled(AutomationControlKey.GITHUB_HOURLY_PRODUCTION_AUDIT) is False
    assert controls.effective_enabled(first.id, AutomationControlKey.NIGHTLY_ANALYSIS) is True
    assert controls.effective_enabled(second.id, AutomationControlKey.NIGHTLY_ANALYSIS) is True

    controls.set_workspace(
        first.id,
        AutomationControlKey.NIGHTLY_ANALYSIS,
        enabled=False,
        actor="first-owner@example.com",
    )
    controls.set_master(
        AutomationControlKey.WEEKLY_ANALYSIS,
        enabled=False,
        actor="platform@example.com",
    )
    database.commit()

    assert controls.effective_enabled(first.id, AutomationControlKey.NIGHTLY_ANALYSIS) is False
    assert controls.effective_enabled(second.id, AutomationControlKey.NIGHTLY_ANALYSIS) is True
    assert controls.workspace_enabled(first.id, AutomationControlKey.WEEKLY_ANALYSIS) is True
    assert controls.effective_enabled(first.id, AutomationControlKey.WEEKLY_ANALYSIS) is False
    assert controls.effective_enabled(second.id, AutomationControlKey.WEEKLY_ANALYSIS) is False
    assert database.scalar(select(func.count()).select_from(AutomationControlAudit)) == 2

    with pytest.raises(UnknownAutomationControlError):
        controls.set_workspace(
            first.id,
            AutomationControlKey.GITHUB_HOURLY_PRODUCTION_AUDIT,
            enabled=True,
            actor="first-owner@example.com",
        )


def dashboard_client(
    db: Session,
    *,
    identity: str,
) -> Generator[TestClient, None, None]:
    def override_db() -> Generator[Session, None, None]:
        yield db

    def authorize(request: FastAPIRequest) -> None:
        request.state.dashboard_identity = identity
        request.state.dashboard_csrf = "test"

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[require_dashboard_session] = authorize
    try:
        yield TestClient(app, base_url="https://testserver")
    finally:
        app.dependency_overrides.clear()


def test_dashboard_renders_and_updates_master_and_workspace_controls(
    database: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.dashboard import router as dashboard_router

    workspace = seed_workspace(database, slug="denticode")
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "platform_admin_emails_csv", "platform@example.com")
    monkeypatch.setattr(dashboard_router, "validate_csrf", lambda _request: None)
    monkeypatch.setattr(settings, "github_control_token", SecretStr("test-github-token"))
    synced: list[bool] = []
    monkeypatch.setattr(
        GitHubActionsVariableClient,
        "set_hourly_production_audit_enabled",
        lambda _client, enabled: synced.append(enabled),
    )

    client_generator = dashboard_client(database, identity="platform@example.com")
    client = next(client_generator)
    try:
        overview = client.get("/dashboard")
        workspace_page = client.get(f"/dashboard/workspaces/{workspace.slug}")
        master_update = client.post(
            "/dashboard/automation-controls/nightly_analysis",
            data={"csrf_token": "test", "enabled": "false"},
            follow_redirects=False,
        )
        workspace_update = client.post(
            f"/dashboard/workspaces/{workspace.slug}/automation-controls/weekly_analysis",
            data={"csrf_token": "test", "enabled": "false"},
            follow_redirects=False,
        )
        github_update = client.post(
            "/dashboard/automation-controls/github_hourly_production_audit",
            data={"csrf_token": "test", "enabled": "true"},
            follow_redirects=False,
        )
    finally:
        with pytest.raises(StopIteration):
            next(client_generator)

    assert overview.status_code == 200
    assert "Master automation toggles" in overview.text
    assert "GitHub hourly production audit" in overview.text
    assert workspace_page.status_code == 200
    assert "Individual Ad Analyzer toggles" in workspace_page.text
    assert "live-write safeguards are not toggleable here" in workspace_page.text
    assert master_update.status_code == 303
    assert workspace_update.status_code == 303
    assert github_update.status_code == 303
    assert synced == [True]
    nightly_control = database.get(PlatformAutomationControl, "nightly_analysis")
    weekly_control = database.get(
        WorkspaceAutomationControl,
        (workspace.id, "weekly_analysis"),
    )
    github_control = database.get(
        PlatformAutomationControl,
        "github_hourly_production_audit",
    )
    assert nightly_control is not None and nightly_control.enabled is False
    assert weekly_control is not None and weekly_control.enabled is False
    assert github_control is not None and github_control.enabled is True
    assert database.scalar(select(func.count()).select_from(AutomationControlAudit)) == 3


def test_viewer_cannot_see_or_change_platform_and_workspace_controls(
    database: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.dashboard import router as dashboard_router

    workspace = seed_workspace(
        database,
        slug="denticode",
        member="viewer@example.com",
        role="viewer",
    )
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "platform_admin_emails_csv", "platform@example.com")
    monkeypatch.setattr(dashboard_router, "validate_csrf", lambda _request: None)

    client_generator = dashboard_client(database, identity="viewer@example.com")
    client = next(client_generator)
    try:
        overview = client.get("/dashboard")
        workspace_page = client.get(f"/dashboard/workspaces/{workspace.slug}")
        master_update = client.post(
            "/dashboard/automation-controls/nightly_analysis",
            data={"csrf_token": "test", "enabled": "false"},
        )
        workspace_update = client.post(
            f"/dashboard/workspaces/{workspace.slug}/automation-controls/nightly_analysis",
            data={"csrf_token": "test", "enabled": "false"},
        )
    finally:
        with pytest.raises(StopIteration):
            next(client_generator)

    assert "Master automation toggles" not in overview.text
    assert "Individual Ad Analyzer toggles" in workspace_page.text
    assert f'action="/dashboard/workspaces/{workspace.slug}/automation-controls/' not in (
        workspace_page.text
    )
    assert master_update.status_code == 403
    assert workspace_update.status_code == 403
    assert database.scalar(select(func.count()).select_from(AutomationControlAudit)) == 0


class FakeResponse:
    def __init__(self, status: int) -> None:
        self.status = status

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(
        self,
        _exception_type: type[BaseException] | None,
        _exception: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        return None

    def getcode(self) -> int:
        return self.status


def test_github_variable_client_creates_missing_variable_without_exposing_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.automation import github as github_module

    calls: list[Request] = []

    def fake_urlopen(request: Request, *, timeout: int) -> FakeResponse:
        assert timeout == 10
        calls.append(request)
        if request.method == "PATCH":
            raise HTTPError(request.full_url, 404, "not found", Message(), None)
        return FakeResponse(201)

    monkeypatch.setattr(github_module, "urlopen", fake_urlopen)
    client = GitHubActionsVariableClient(
        token=SecretStr("private-test-token"),
        repository="Konner-An-Inlet/Denticode-Ads-Optimizer",
    )
    client.set_hourly_production_audit_enabled(False)

    assert [request.method for request in calls] == ["PATCH", "POST"]
    request_data = [request.data for request in calls]
    assert all(isinstance(data, bytes) for data in request_data)
    encoded_data = [data for data in request_data if isinstance(data, bytes)]
    assert all(GITHUB_HOURLY_AUDIT_VARIABLE in data.decode() for data in encoded_data)
    assert all(b"private-test-token" not in data for data in encoded_data)


def test_github_variable_client_failure_is_sanitized(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.automation import github as github_module

    def fail_urlopen(request: Request, *, timeout: int) -> FakeResponse:
        raise HTTPError(request.full_url, 403, "private-test-token", Message(), None)

    monkeypatch.setattr(github_module, "urlopen", fail_urlopen)
    client = GitHubActionsVariableClient(
        token=SecretStr("private-test-token"),
        repository="Konner-An-Inlet/Denticode-Ads-Optimizer",
    )
    with pytest.raises(GitHubAutomationControlError) as exc_info:
        client.set_hourly_production_audit_enabled(True)
    assert str(exc_info.value) == "GitHub automation control is temporarily unavailable."
    assert "private-test-token" not in str(exc_info.value)


def test_hourly_github_audit_fails_closed_but_manual_dispatch_remains_available() -> None:
    workflow = Path(".github/workflows/production-operations-audit.yml").read_text()
    assert "cron: '17 * * * *'" in workflow
    assert "github.event_name == 'workflow_dispatch'" in workflow
    assert "vars.PRODUCTION_OPERATIONS_AUDIT_ENABLED == 'true'" in workflow
    assert "GCP_SYNC_JOB: denticode-sync" in workflow
    assert "google_ads_write_enabled" not in workflow


def test_automation_control_migration_seeds_defaults_and_reverses() -> None:
    engine = create_engine("sqlite://")
    migration = import_module(
        "migrations.versions.20260820_0015_automation_controls"
    )
    with engine.begin() as connection:
        Workspace.metadata.create_all(
            connection,
            tables=[Workspace.metadata.tables["workspaces"]],
        )
        migration.__dict__["op"] = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        table_names = set(inspect(connection).get_table_names())
        defaults: dict[str, int] = {
            str(key): int(enabled)
            for key, enabled in connection.execute(
                text("SELECT key, enabled FROM platform_automation_controls")
            ).tuples()
        }

        assert {
            "platform_automation_controls",
            "workspace_automation_controls",
            "automation_control_audits",
        } <= table_names
        assert defaults == {
            "github_hourly_production_audit": 0,
            "post_sync_analysis": 1,
            "nightly_analysis": 1,
            "weekly_analysis": 1,
            "automatic_recommendation_drafts": 1,
        }

        migration.downgrade()
        reversed_tables = set(inspect(connection).get_table_names())
        assert reversed_tables == {"workspaces"}
    engine.dispose()
