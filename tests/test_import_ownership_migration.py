"""Real PostgreSQL upgrade with existing native connections and historical jobs."""

import os
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from app.settings import settings
from sqlalchemy import create_engine, make_url, text


def test_native_ownership_backfill_and_legacy_google_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = os.environ.get("AD_ANALYZER_TEST_POSTGRES_URL")
    if not url or os.environ.get("AD_ANALYZER_CI_DISPOSABLE_POSTGRES") != "true":
        pytest.skip("explicit disposable PostgreSQL configuration required")
    schema = "inlet_migration_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped = make_url(url).update_query_dict({"options": f"-csearch_path={schema}"})
    engine = create_engine(scoped)
    monkeypatch.setattr(settings, "database_url", scoped.render_as_string(hide_password=False))
    config = Config("alembic.ini")
    try:
        command.upgrade(config, "20261005_0021")
        with engine.begin() as db:
            db.execute(
                text("""INSERT INTO advertising_accounts
                (id, workspace_id, platform, external_account_id, name, currency_code,
                 created_at, updated_at)
                VALUES (101, 1, 'meta_ads', '1234567', 'Fixture', 'USD',
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
                       (102, 1, 'google_ads', '7654321', 'Legacy', 'USD',
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """)
            )
            db.execute(
                text("""INSERT INTO meta_connections
                (id, workspace_id, account_id, external_account_id, status, encrypted_credentials,
                 connected_at, phase)
                VALUES (41, 1, 101, '1234567', 'connected', 'synthetic-fixture',
                        CURRENT_TIMESTAMP, 'campaigns')
            """)
            )
            db.execute(
                text("""INSERT INTO crm_connections
                (id, workspace_id, name, status, secret_manager_reference, created_at, updated_at)
                VALUES (51, 1, 'CRM fixture', 'active', 'projects/fake/secrets/crm/versions/1',
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """)
            )
            db.execute(
                text("""INSERT INTO job_runs
                (id, workspace_id, platform, account_id, job_name, status, started_at,
                 records_processed,
                 created_at, updated_at)
                VALUES (61, 1, 'meta_ads', 101, 'meta_ads_sync', 'succeeded', CURRENT_TIMESTAMP, 0,
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
                       (62, 1, 'google_ads', 102, 'google_ads_sync', 'succeeded',
                        CURRENT_TIMESTAMP, 0,
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """)
            )
        command.upgrade(config, "20261005_0022")
        with engine.connect() as db:
            meta = db.execute(
                text("SELECT workspace_integration_id FROM meta_connections WHERE id=41")
            ).scalar_one()
            assert meta is not None
            assert (
                db.execute(
                    text("SELECT connection_id FROM advertising_accounts WHERE id=101")
                ).scalar_one()
                == meta
            )
            assert (
                db.execute(text("SELECT connection_id FROM job_runs WHERE id=61")).scalar_one()
                == meta
            )
            assert (
                db.execute(text("SELECT connection_id FROM job_runs WHERE id=62")).scalar_one()
                is None
            )
            crm = db.execute(
                text("SELECT workspace_integration_id FROM crm_connections WHERE id=51")
            ).scalar_one()
            assert crm is not None and crm != meta
            assert (
                db.execute(
                    text("SELECT workspace_id FROM workspace_integrations WHERE id=:id"),
                    {"id": crm},
                ).scalar_one()
                == 1
            )
        with engine.begin() as db:
            db.execute(
                text("UPDATE workspace_integrations SET status='revoked' WHERE id=:id"),
                {"id": meta},
            )
        command.downgrade(config, "20261005_0021")
        command.upgrade(config, "20261005_0022")
        with engine.connect() as db:
            assert (
                db.execute(
                    text("SELECT workspace_integration_id FROM meta_connections WHERE id=41")
                ).scalar_one()
                == meta
            )
            assert (
                db.execute(
                    text("SELECT status FROM workspace_integrations WHERE id=:id"), {"id": meta}
                ).scalar_one()
                == "revoked"
            )
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
