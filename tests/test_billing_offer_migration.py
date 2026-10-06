"""0063 preserves old unqualified rows and refuses loss of commercial lineage."""

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
from app.billing import offer_bindings
from app.billing.models import BillingOfferBinding
from app.billing.service import owned
from app.settings import settings
from app.workspaces.models import Workspace
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import Table, create_engine, make_url, select, text
from sqlalchemy.orm import Session

from tests.test_billing_offers import LIVE, PROFILE
from tests.test_commerce_measurement import NOW


@pytest.mark.parametrize("backend", ["sqlite", "postgres"])
def test_offer_migration(backend: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    admin = None
    schema = "inlet_offer_" + uuid4().hex
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
        target = (
            make_url(url)
            .update_query_dict({"options": f"-csearch_path={schema}"})
            .render_as_string(hide_password=False)
        )
    else:
        target = "sqlite:///" + str(tmp_path / "offer.sqlite")
    engine = create_engine(target)
    monkeypatch.setattr(settings, "database_url", target)
    config = Config("alembic.ini")
    try:
        if backend == "sqlite":
            cast(Table, Workspace.__table__).create(engine)
            with (
                engine.begin() as connection,
                Operations.context(MigrationContext.configure(connection)),
            ):
                runpy.run_path("migrations/versions/20261006_0031_customer_billing.py")["upgrade"]()
            command.stamp(config, "20261006_0060")
        command.upgrade(config, "20261006_0061")
        with engine.begin() as db:
            db.execute(
                text(
                    "INSERT INTO workspaces "
                    "(slug,name,client_name,status,is_default,created_at,updated_at) "
                    "VALUES ('offer','Offer','Offer','active',false,:now,:now)"
                ),
                {"now": NOW},
            )
            wid = db.scalar(text("SELECT id FROM workspaces WHERE slug='offer'"))
            db.execute(
                text(
                    "INSERT INTO customer_workspace_billing "
                    "(workspace_id,customer_request_key,status,cancel_at_period_end) "
                    "VALUES (:wid,'legacy','active',false)"
                ),
                {"wid": wid},
            )
        command.upgrade(config, "20261006_0063")
        with engine.connect() as db:
            assert (
                db.scalar(text("SELECT qualification_digest FROM customer_workspace_billing"))
                is None
            )
        command.downgrade(config, "20261006_0061")
        command.upgrade(config, "20261006_0063")
        with Session(engine) as db:
            row = owned(db, int(wid), NOW, scope=LIVE)
            row.checkout_key = f"{int(NOW.timestamp())}_" + "a" * 32
            offer_bindings.install(db, row, PROFILE, NOW)
            db.commit()
        with pytest.raises(RuntimeError, match="lineage requires preservation"):
            command.downgrade(config, "20261006_0061")
        with Session(engine) as db:
            assert db.scalar(select(BillingOfferBinding.id)) is not None
    finally:
        engine.dispose()
        if admin is not None:
            with admin.begin() as db:
                db.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            admin.dispose()
