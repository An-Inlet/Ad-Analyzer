"""Closed genuine legacy mandate producer; no current guard override or provider IO."""

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, cast

import app
from app.ads.enums import AdvertisingPlatform
from app.ads.models import AdvertisingAccount
from app.google_connections.models import GoogleCustomerConnection
from app.mandates import service as mandates
from app.mandates.schemas import AccountScope
from app.meta.models import MetaConnection
from app.workspaces.models import WorkspaceIntegration
from sqlalchemy import create_engine, event, inspect, select, text
from sqlalchemy.orm import Session
from tests.test_commerce_measurement import NOW
from tests.test_google_action_plans import setup
from tests.test_shopify_sales import configuration


def main() -> None:
    target, output, provider = sys.argv[1:]
    assert provider in {"google_ads", "meta_ads"}
    assert (
        os.environ.get("INLET_RETIRED_EXECUTION_CHILD")
        == "2155ff3e3ab00cd62057dd86cb49d45359d4f49f"
    )
    assert Path(app.__file__).resolve().is_relative_to(Path(os.environ["PYTHONPATH"]).resolve())
    if target.startswith("sqlite:"):
        engine = create_engine(target)
        event.listen(engine, "connect", lambda db, _: db.execute("PRAGMA foreign_keys=ON"))
    else:
        assert re.fullmatch(r"inlet_test_[a-f0-9]{32}", target)
        assert os.environ.get("AD_ANALYZER_CI_DISPOSABLE_POSTGRES") == "true"
        engine = create_engine(
            os.environ["AD_ANALYZER_TEST_POSTGRES_URL"],
            connect_args={"options": f"-csearch_path={target}"},
        )
        with engine.connect() as connection_check:
            assert connection_check.scalar(text("select current_schema()")) == target
    try:
        tables = set(inspect(engine).get_table_names())
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
