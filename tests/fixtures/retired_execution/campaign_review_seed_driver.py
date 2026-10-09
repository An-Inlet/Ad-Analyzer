"""Closed genuine legacy mandate producer; no current guard override or provider IO."""

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import app
from app.ads.enums import AdvertisingPlatform
from app.ads.models import AdvertisingAccount
from app.google_connections.models import GoogleCustomerConnection
from app.mandates import service as mandates
from app.mandates.schemas import AccountScope
from app.meta.models import MetaConnection
from app.sources.models import SourceConnection
from app.workspaces.models import WorkspaceIntegration
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import create_engine, event, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from tests.test_commerce_measurement import NOW
from tests.test_google_action_plans import setup
from tests.test_shopify_sales import configuration


def owned_sqlite_target(target: str, expected: Path) -> str:
    url = make_url(target)
    assert url.drivername == "sqlite" and not url.query
    assert url.username is None and url.password is None and url.host is None and url.port is None
    assert url.database is not None
    path = Path(url.database)
    assert path.is_absolute() and path == expected.absolute()
    assert path.is_file() and not path.is_symlink()
    assert all(not parent.is_symlink() for parent in path.parents)
    assert path.resolve() == path
    return str(url)


def main() -> None:
    target, output, provider = sys.argv[1:]
    assert provider in {"google_ads", "meta_ads", "tiktok_ads"}
    assert (
        os.environ.get("INLET_RETIRED_EXECUTION_CHILD")
        == "2155ff3e3ab00cd62057dd86cb49d45359d4f49f"
    )
    assert Path(app.__file__).resolve().is_relative_to(Path(os.environ["PYTHONPATH"]).resolve())
    if target.startswith("sqlite") and provider == "tiktok_ads":
        target = owned_sqlite_target(target, Path(output).parent / "current.sqlite")
    if target.startswith("sqlite:"):
        engine = create_engine(target)
        event.listen(engine, "connect", lambda db, _: db.execute("PRAGMA foreign_keys=ON"))
    else:
        assert re.fullmatch(r"inlet_test_[a-f0-9]{32}", target)
        assert os.environ.get("AD_ANALYZER_CI_DISPOSABLE_POSTGRES") == "true"
        if provider == "tiktok_ads":
            safe = make_url(validate_disposable_url())
            assert safe.host in {"localhost", "127.0.0.1", "::1"} and not safe.query
        engine = create_engine(
            os.environ["AD_ANALYZER_TEST_POSTGRES_URL"],
            connect_args={"options": f"-csearch_path={target}"},
        )
        with engine.connect() as connection_check:
            assert connection_check.scalar(text("select current_schema()")) == target
    try:
        tables = set(inspect(engine).get_table_names())
        if provider == "tiktok_ads":
            with engine.connect() as connection_check:
                for table in sorted(tables - {"alembic_version"}):
                    quoted = engine.dialect.identifier_preparer.quote(table)
                    assert (
                        connection_check.execute(text(f"SELECT 1 FROM {quoted} LIMIT 1")).first()
                        is None
                    )
        config = cast(Any, configuration).__wrapped__()
        with Session(engine) as db:
            mandate, scope, _ = setup(db, config)
            if provider == "meta_ads":
                integration = WorkspaceIntegration(
                    workspace_id=mandate.workspace_id,
                    integration_key="meta-review",
                    provider="meta_ads",
                    display_name="Meta",
                    status="active",
                    configuration={},
                )
                db.add(integration)
                db.flush()
                account = AdvertisingAccount(
                    workspace_id=mandate.workspace_id,
                    connection_id=integration.id,
                    platform=AdvertisingPlatform.META_ADS,
                    external_account_id="101",
                    name="Meta",
                    currency_code="USD",
                    time_zone="UTC",
                )
                db.add(account)
                db.flush()
                connection = MetaConnection(
                    workspace_id=mandate.workspace_id,
                    workspace_integration_id=integration.id,
                    account_id=account.id,
                    external_account_id="101",
                    encrypted_credentials="unopened-fixture",
                )
                db.add(connection)
                policy = mandates.policy(db, mandate)
                scope = AccountScope(
                    platform="meta_ads", connection_id=integration.id, account_id=account.id
                )
                policy.accounts = [scope]
                mandates.edit(db, mandate, mandate.revision, policy, "owner", NOW)
                mandates.approve(db, mandate, mandate.revision, "owner", NOW)
                db.commit()
                source_id = str(connection.id)
            elif provider == "tiktok_ads":
                integration = WorkspaceIntegration(
                    workspace_id=mandate.workspace_id,
                    integration_key="video-review",
                    provider="tiktok_ads",
                    display_name="Fixture TikTok",
                    status="active",
                    configuration={},
                )
                db.add(integration)
                db.flush()
                account = AdvertisingAccount(
                    workspace_id=mandate.workspace_id,
                    connection_id=integration.id,
                    platform=AdvertisingPlatform.TIKTOK_ADS,
                    external_account_id="123",
                    name="Fixture TikTok",
                    currency_code="USD",
                    time_zone="UTC",
                )
                db.add(account)
                db.flush()
                connection_source = SourceConnection(
                    id=uuid4().hex,
                    workspace_id=mandate.workspace_id,
                    integration_id=integration.id,
                    account_id=account.id,
                    provider="tiktok_ads",
                    external_id="123",
                    status="connected",
                    generation=1,
                    window_start=NOW.date(),
                    window_end=NOW.date(),
                    staged={},
                )
                db.add(connection_source)
                policy = mandates.policy(db, mandate)
                scope = AccountScope(
                    platform="tiktok_ads", connection_id=integration.id, account_id=account.id
                )
                policy.accounts = [scope]
                mandates.edit(db, mandate, mandate.revision, policy, "owner", NOW)
                mandates.approve(db, mandate, mandate.revision, "owner", NOW)
                db.commit()
                source_id = connection_source.id
            else:
                source = db.scalar(
                    select(GoogleCustomerConnection).where(
                        GoogleCustomerConnection.account_id == scope.account_id
                    )
                )
                assert source
                source_id = source.id
            policy = mandates.policy(db, mandate)
            assert (policy.total_cap_micros, policy.per_action_cap_micros) == (100, 80)
            assert mandate.state == "approved" and not mandate.paused
            result = dict(
                workspace_id=mandate.workspace_id,
                mandate_id=mandate.id,
                mandate_revision=mandate.revision,
                integration_id=scope.connection_id,
                account_id=scope.account_id,
                source_id=source_id,
                provider=provider,
                provider_posts=0,
            )
            db.commit()
        assert set(inspect(engine).get_table_names()) == tables
        Path(output).write_text(json.dumps(result))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
