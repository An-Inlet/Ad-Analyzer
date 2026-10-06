"""Populated environment upgrade preserves old evidence and refuses qualified downgrade."""

import os
import runpy
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.settings import settings
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import Table, create_engine, make_url, text

from tests.test_commerce_measurement import NOW


@pytest.mark.parametrize("backend", ["sqlite", "postgres"])
def test_billing_scope_migration(
    backend: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    admin = None
    schema = "inlet_billing_scope_" + uuid4().hex
    if backend == "postgres":
        if (
            not os.environ.get("AD_ANALYZER_TEST_POSTGRES_URL")
            or os.environ.get("AD_ANALYZER_CI_DISPOSABLE_POSTGRES") != "true"
        ):
            pytest.skip("explicit disposable PostgreSQL required")
        url = validate_disposable_url()
        admin = create_engine(url)
        with admin.begin() as db:
            db.execute(text(f'CREATE SCHEMA "{schema}"'))
        scoped = make_url(url).update_query_dict({"options": f"-csearch_path={schema}"})
        target = scoped.render_as_string(hide_password=False)
    else:
        target = "sqlite:///" + str(tmp_path / "billing.sqlite")
    engine = create_engine(target)
    monkeypatch.setattr(settings, "database_url", target)
    config = Config("alembic.ini")
    try:
        if backend == "sqlite":
            # Historical 0002 uses PostgreSQL-only ALTER. Exercise this migration
            # from the exact original 0031 billing schema, not a weakened substitute.
            from app.workspaces.models import Workspace

            cast(Table, Workspace.__table__).create(engine)
            with (
                engine.begin() as connection,
                Operations.context(MigrationContext.configure(connection)),
            ):
                runpy.run_path("migrations/versions/20261006_0031_customer_billing.py")["upgrade"]()
            command.stamp(config, "20261006_0060")
        else:
            command.upgrade(config, "20261006_0060")
        with engine.begin() as db:
            db.execute(
                text(
                    "INSERT INTO workspaces "
                    "(slug,name,client_name,status,is_default,created_at,updated_at) "
                    "VALUES ('billing','Billing','Billing','active',false,:now,:now)"
                ),
                {"now": NOW},
            )
            wid = db.scalar(text("SELECT id FROM workspaces WHERE slug='billing'"))
            db.execute(
                text(
                    "INSERT INTO customer_workspace_billing "
                    "(workspace_id,customer_request_key,customer_id,status,cancel_at_period_end) "
                    "VALUES (:wid,'key','cus_fixture','active',false)"
                ),
                {"wid": wid},
            )
            db.execute(
                text(
                    "INSERT INTO customer_billing_events "
                    "(id,body_hash,customer_id,subscription_id,event_type,state,received_at) "
                    "VALUES "
                    "('evt_fixture','hash','cus_fixture','sub_fixture','customer.subscription.updated','pending',:now)"
                ),
                {"now": NOW},
            )
        command.upgrade(config, "20261006_0061")
        with engine.connect() as db:
            assert db.execute(
                text(
                    "SELECT provider,environment,merchant_account_id FROM "
                    "customer_workspace_billing"
                )
            ).one() == ("stripe", "test", "legacy_unqualified")
        command.downgrade(config, "20261006_0060")
        with engine.connect() as db:
            assert (
                db.scalar(text("SELECT customer_id FROM customer_workspace_billing"))
                == "cus_fixture"
            )
            assert db.scalar(text("SELECT body_hash FROM customer_billing_events")) == "hash"
        command.upgrade(config, "20261006_0061")
        with engine.begin() as db:
            db.execute(
                text(
                    "INSERT INTO customer_workspace_billing "
                    "(workspace_id,provider,environment,merchant_account_id,"
                    "customer_request_key,customer_id,status,cancel_at_period_end) "
                    "VALUES "
                    "(:wid,'stripe','live','acct_fixture','key','cus_fixture','active',false)"
                ),
                {"wid": wid},
            )
        with pytest.raises(RuntimeError, match="qualified billing identities"):
            command.downgrade(config, "20261006_0060")
        with engine.connect() as db:
            assert db.scalar(text("SELECT count(*) FROM customer_workspace_billing")) == 2
    finally:
        engine.dispose()
        if admin is not None:
            with admin.begin() as db:
                db.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            admin.dispose()
