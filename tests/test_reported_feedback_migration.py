"""0077 actual DDL and downgrade safety; separate scoped PostgreSQL schemas."""

import pytest
from alembic import command
from alembic.config import Config
from app.ads.enums import AdvertisingPlatform
from app.ads.models import AdvertisingAccount
from app.meta.models import MetaConnection
from app.reported_feedback.triggers import TABLES
from app.workspaces.models import WorkspaceIntegration
from sqlalchemy import Engine, inspect, text
from sqlalchemy.orm import Session

from tests.migration_engine import migration_customer_engine as migration_customer_engine
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_lifecycle import seed


def test_actual0077_phase_guard_and_roundtrip(migration_customer_engine: Engine) -> None:
    engine = migration_customer_engine
    if engine.dialect.name != "postgresql":
        pytest.skip("actual Alembic PostgreSQL DDL roundtrip")
    assert set(TABLES) <= set(inspect(engine).get_table_names())
    with Session(engine) as db:
        _, wid = seed(db)
        integration = WorkspaceIntegration(
            workspace_id=wid,
            integration_key="rf-fixture",
            provider="meta_ads",
            display_name="Synthetic",
            status="active",
            configuration={},
        )
        db.add(integration)
        db.flush()
        account = AdvertisingAccount(
            workspace_id=wid,
            connection_id=integration.id,
            platform=AdvertisingPlatform.META_ADS,
            external_account_id="123",
            name="Synthetic",
            currency_code="USD",
            time_zone="UTC",
        )
        db.add(account)
        db.flush()
        source = MetaConnection(
            workspace_id=wid,
            account_id=account.id,
            workspace_integration_id=integration.id,
            external_account_id="123",
            encrypted_credentials="unusable-offline",
            phase="rf_campaigns",
        )
        db.add(source)
        db.commit()
    with pytest.raises(RuntimeError, match="fixed-window acquisition"):
        command.downgrade(Config("alembic.ini"), "20261006_0076")
    assert set(TABLES) <= set(inspect(engine).get_table_names())
    with engine.begin() as db:
        db.execute(text("UPDATE meta_connections SET phase='campaigns'"))
    command.downgrade(Config("alembic.ini"), "20261006_0076")
    assert not set(TABLES) & set(inspect(engine).get_table_names())
    command.upgrade(Config("alembic.ini"), "20261006_0077")
    assert set(TABLES) <= set(inspect(engine).get_table_names())
    with engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM meta_connections")) == 1
        names = set(db.scalars(text("SELECT tgname FROM pg_trigger WHERE NOT tgisinternal")))
        assert {
            name + suffix for name in TABLES for suffix in ("_guard", "_erase", "_immutable")
        } <= names


def test_phase_constraint_change_preserves_native_staging(customer_engine: Engine) -> None:
    import importlib
    from datetime import date
    from decimal import Decimal

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from app.ads.models import Campaign
    from app.meta.models import MetaDetailCheckpoint, MetaDetailStagedPage, MetaStagedMetric
    from sqlalchemy import select

    engine = customer_engine
    with engine.connect() as connection:
        if engine.dialect.name == "sqlite":
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        connection.commit()
    with Session(engine) as db:
        _, wid = seed(db)
        integration = WorkspaceIntegration(
            workspace_id=wid,
            integration_key="phase-fixture",
            provider="meta_ads",
            display_name="Synthetic",
            status="active",
            configuration={},
        )
        db.add(integration)
        db.flush()
        account = AdvertisingAccount(
            workspace_id=wid,
            connection_id=integration.id,
            platform=AdvertisingPlatform.META_ADS,
            external_account_id="456",
            name="Synthetic",
            currency_code="USD",
            time_zone="UTC",
        )
        db.add(account)
        db.flush()
        campaign = Campaign(
            account_id=account.id,
            platform=AdvertisingPlatform.META_ADS,
            external_campaign_id="789",
            name="Synthetic",
        )
        source = MetaConnection(
            workspace_id=wid,
            account_id=account.id,
            workspace_integration_id=integration.id,
            external_account_id="456",
            encrypted_credentials="unusable",
            phase="insights",
        )
        db.add_all([campaign, source])
        db.flush()
        db.add(
            MetaStagedMetric(
                connection_id=source.id,
                campaign_id=campaign.id,
                metric_date=date(2026, 10, 1),
                impressions=100,
                clicks=10,
                cost_micros=1000000,
                conversions=Decimal(2),
                conversion_value_micros=3000000,
            )
        )
        db.add(
            MetaDetailCheckpoint(
                connection_id=source.id,
                workspace_id=wid,
                account_id=account.id,
                integration_id=integration.id,
                generation=1,
                window_start=date(2026, 10, 1),
                window_end=date(2026, 10, 1),
                phase="ad_insights",
                cursor="opaque-fixture",
                seen_cursors=["previous-fixture"],
                page_count=1,
                row_count=1,
                byte_count=100,
            )
        )
        db.flush()
        db.add(
            MetaDetailStagedPage(connection_id=source.id, page_number=1, payload={"synthetic": 1})
        )
        db.commit()
    models = (MetaStagedMetric, MetaDetailCheckpoint, MetaDetailStagedPage)

    def snapshots() -> list[list[dict[str, object]]]:
        with Session(engine) as db:
            return [
                [dict(row) for row in db.execute(select(model.__table__)).mappings()]
                for model in models
            ]

    before = snapshots()
    migration = importlib.import_module("migrations.versions.20261006_0077_reported_feedback")
    revisions = importlib.import_module(
        "migrations.versions.20261007_0078_reported_preview_revisions"
    )
    rules = importlib.import_module("migrations.versions.20261007_0083_reported_rule_dependencies")
    with engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
        rules.downgrade()
        revisions.downgrade()
        migration.downgrade()
    assert snapshots() == before
    with engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
        migration.upgrade()
        revisions.upgrade()
        rules.upgrade()
    assert snapshots() == before
