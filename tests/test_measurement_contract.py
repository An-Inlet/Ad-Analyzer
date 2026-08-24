from collections.abc import Generator
from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path
from sqlite3 import Connection as SQLiteConnection

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.crm.schemas import CrmEventType
from app.database.session import Base, get_db
from app.main import app
from app.measurement.models import (
    MeasurementContract,
    MeasurementEventMapping,
    MeasurementStageDefinition,
)
from app.measurement.repository import MeasurementRepository
from app.measurement.schemas import MeasurementContractResponse
from app.measurement.service import evaluate_measurement_readiness
from app.settings import settings
from app.workspaces.models import Workspace
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, event, select, text
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


def add_workspace(db: Session, slug: str) -> Workspace:
    workspace = Workspace(
        slug=slug,
        name=f"{slug.title()} Ad Analyzer",
        client_name=slug.title(),
        status="active",
        is_default=slug == "denticode",
    )
    db.add(workspace)
    db.flush()
    return workspace


def add_contract(
    db: Session,
    workspace: Workspace,
    *,
    status: str = "draft",
    currency_code: str = "USD",
) -> MeasurementContract:
    contract = MeasurementContract(
        workspace_id=workspace.id,
        version=1,
        status=status,
        effective_at=datetime.now(UTC) if status == "active" else None,
        currency_code=currency_code,
        source_of_truth="crm",
        platform_conversion_role="diagnostic_only",
        attribution_model="last_eligible_paid_touch",
        click_lookback_days=90,
        engaged_view_lookback_days=0,
        outcome_maturity_days=90,
        customer_value_mode="observed_revenue_only",
        customer_value_horizon_days=365,
        optimization_goal_stage_key="qualified_lead",
        business_value_stage_key="sale",
    )
    db.add(contract)
    db.flush()
    stages = [
        ("lead", "Lead", 10, "leading_indicator", False),
        ("qualified_lead", "Qualified lead", 20, "optimization_outcome", False),
        ("sale", "Sale won", 30, "business_outcome", True),
        ("revenue_adjustment", "Revenue adjustment", 40, "value_adjustment", True),
    ]
    db.add_all(
        [
            MeasurementStageDefinition(
                workspace_id=workspace.id,
                stage_key=stage_key,
                display_name=display_name,
                position=position,
                category=category,
                counts_toward_funnel=category != "value_adjustment",
                accepts_monetary_value=accepts_value,
                description=f"Definition for {display_name}.",
            )
            for stage_key, display_name, position, category, accepts_value in stages
        ]
    )
    db.flush()
    db.add_all(
        [
            MeasurementEventMapping(
                workspace_id=workspace.id,
                event_source="crm",
                source_event_type="lead_created",
                stage_key="lead",
                authority="authoritative",
                value_behavior="ignore",
            ),
            MeasurementEventMapping(
                workspace_id=workspace.id,
                event_source="crm",
                source_event_type="lead_qualified",
                stage_key="qualified_lead",
                authority="authoritative",
                value_behavior="ignore",
            ),
            MeasurementEventMapping(
                workspace_id=workspace.id,
                event_source="crm",
                source_event_type="sale_won",
                stage_key="sale",
                authority="authoritative",
                value_behavior="set",
            ),
            MeasurementEventMapping(
                workspace_id=workspace.id,
                event_source="crm",
                source_event_type="revenue_adjusted",
                stage_key="revenue_adjustment",
                authority="authoritative",
                value_behavior="adjust",
            ),
        ]
    )
    db.flush()
    return contract


def test_draft_contract_fails_closed_until_approved(db: Session) -> None:
    workspace = add_workspace(db, "denticode")
    add_contract(db, workspace)
    db.commit()

    snapshot = MeasurementRepository(db).get_for_workspace(workspace.id)

    assert snapshot is not None
    readiness = evaluate_measurement_readiness(snapshot)
    response = MeasurementContractResponse.from_snapshot(snapshot)
    assert readiness.analysis_ready is False
    assert readiness.blocking_reasons == ("measurement_contract_not_active",)
    assert response.platform_conversion_role.value == "diagnostic_only"
    assert response.customer_value_mode.value == "observed_revenue_only"
    assert response.engaged_view_lookback_days == 0


def test_active_structurally_complete_contract_is_analysis_ready(db: Session) -> None:
    workspace = add_workspace(db, "denticode")
    add_contract(db, workspace, status="active")
    db.commit()

    snapshot = MeasurementRepository(db).get_for_workspace(workspace.id)

    assert snapshot is not None
    assert evaluate_measurement_readiness(snapshot).analysis_ready is True


def test_active_contract_requires_an_effective_timestamp(db: Session) -> None:
    workspace = add_workspace(db, "denticode")
    db.add(
        MeasurementContract(
            workspace_id=workspace.id,
            status="active",
            effective_at=None,
            optimization_goal_stage_key="qualified_lead",
            business_value_stage_key="sale",
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()


def test_cross_workspace_event_mapping_is_rejected(db: Session) -> None:
    denticode = add_workspace(db, "denticode")
    second = add_workspace(db, "second-client")
    add_contract(db, denticode)
    db.add(
        MeasurementContract(
            workspace_id=second.id,
            status="draft",
            optimization_goal_stage_key="qualified_lead",
            business_value_stage_key="sale",
        )
    )
    db.flush()
    db.add(
        MeasurementEventMapping(
            workspace_id=second.id,
            event_source="crm",
            source_event_type="lead_created",
            stage_key="lead",
            authority="authoritative",
            value_behavior="ignore",
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()


def test_repository_returns_only_the_requested_workspace_contract(db: Session) -> None:
    denticode = add_workspace(db, "denticode")
    second = add_workspace(db, "second-client")
    add_contract(db, denticode, currency_code="USD")
    add_contract(db, second, currency_code="CAD")
    db.commit()

    repository = MeasurementRepository(db)
    first = repository.get_for_workspace(denticode.id)
    other = repository.get_for_workspace(second.id)

    assert first is not None and other is not None
    assert first.contract.currency_code == "USD"
    assert other.contract.currency_code == "CAD"
    assert {stage.workspace_id for stage in first.stages} == {denticode.id}
    assert {mapping.workspace_id for mapping in other.mappings} == {second.id}


def test_operator_api_and_dashboard_show_only_workspace_measurement_contract(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = "m" * 48
    denticode = add_workspace(db, "denticode")
    second = add_workspace(db, "second-client")
    add_contract(db, denticode, currency_code="USD")
    add_contract(db, second, currency_code="CAD")
    db.commit()
    monkeypatch.setattr(settings, "api_token", SecretStr(token))
    monkeypatch.setattr(settings, "app_env", "development")

    def override_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app, base_url="https://testserver")
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get(
            "/api/v1/workspaces/denticode/measurement-contract",
            headers=headers,
        )
        client.get("/dashboard", headers=headers)
        dashboard = client.get("/dashboard/workspaces/denticode")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["workspace_id"] == denticode.id
    assert response.json()["currency_code"] == "USD"
    assert response.json()["source_of_truth"] == "crm"
    assert response.json()["analysis_ready"] is False
    assert "CAD" not in response.text
    assert dashboard.status_code == 200
    assert "Measurement contract" in dashboard.text
    assert "Outcome analysis remains blocked" in dashboard.text


def test_migration_maps_every_current_crm_event_type() -> None:
    migration = Path(
        "migrations/versions/20260806_0009_workspace_measurement_contract.py"
    ).read_text()

    for event_type in CrmEventType:
        assert f'("{event_type.value}",' in migration
    assert '"status": "draft"' in migration
    assert '"platform_conversion_role": "diagnostic_only"' in migration
    assert '"customer_value_mode": "observed_revenue_only"' in migration


def test_duplicate_source_event_mapping_is_rejected_inside_workspace(db: Session) -> None:
    workspace = add_workspace(db, "denticode")
    add_contract(db, workspace)
    db.commit()
    db.add(
        MeasurementEventMapping(
            workspace_id=workspace.id,
            event_source="crm",
            source_event_type="lead_created",
            stage_key="lead",
            authority="authoritative",
            value_behavior="ignore",
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()


def test_repository_returns_none_when_workspace_has_no_contract(db: Session) -> None:
    workspace = add_workspace(db, "denticode")
    db.commit()

    assert MeasurementRepository(db).get_for_workspace(workspace.id) is None
    assert db.scalars(select(MeasurementContract)).all() == []


def test_measurement_migration_seeds_and_reverses_on_disposable_schema() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    migration = import_module(
        "migrations.versions.20260806_0009_workspace_measurement_contract"
    )
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE workspaces ("
                "id INTEGER PRIMARY KEY, slug VARCHAR(64) NOT NULL UNIQUE)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE advertising_accounts ("
                "id INTEGER PRIMARY KEY, workspace_id INTEGER NOT NULL, "
                "currency_code VARCHAR(3) NOT NULL)"
            )
        )
        connection.execute(text("INSERT INTO workspaces VALUES (1, 'denticode')"))
        connection.execute(text("INSERT INTO advertising_accounts VALUES (1, 1, 'USD')"))
        migration.__dict__["op"] = Operations(MigrationContext.configure(connection))

        migration.upgrade()

        contract = connection.execute(
            text(
                "SELECT status, source_of_truth, platform_conversion_role, "
                "optimization_goal_stage_key, business_value_stage_key "
                "FROM measurement_contracts WHERE workspace_id = 1"
            )
        ).one()
        assert tuple(contract) == (
            "draft",
            "crm",
            "diagnostic_only",
            "qualified_lead",
            "sale",
        )
        assert connection.scalar(text("SELECT count(*) FROM measurement_stage_definitions")) == 8
        assert connection.scalar(text("SELECT count(*) FROM measurement_event_mappings")) == 8

        migration.downgrade()

        tables = {
            row[0]
            for row in connection.execute(
                text("SELECT name FROM sqlite_master WHERE type = 'table'")
            )
        }
        assert "measurement_contracts" not in tables
        assert "measurement_stage_definitions" not in tables
        assert "measurement_event_mappings" not in tables
    engine.dispose()
