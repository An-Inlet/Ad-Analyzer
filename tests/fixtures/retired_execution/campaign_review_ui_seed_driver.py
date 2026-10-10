"""Closed original three-account campaign-review prefix; no transport or current guard."""
import hashlib
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
from app.customers.models import CustomerMembership, CustomerUser
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
from tests.test_customer_identity import ISSUER
from tests.test_google_action_plans import setup
from tests.test_shopify_sales import configuration as configuration_fixture


def main() -> None:
    target, output = sys.argv[1:]
    assert os.environ.get("INLET_RETIRED_EXECUTION_CHILD") == (
        "2155ff3e3ab00cd62057dd86cb49d45359d4f49f"
    )
    assert Path(app.__file__).resolve().is_relative_to(Path(os.environ["PYTHONPATH"]).resolve())
    if target.startswith("sqlite"):
        url = make_url(target)
        expected = Path(output).parent / "current.sqlite"
        assert url.drivername == "sqlite" and not url.query
        assert url.username is None and url.password is None and url.host is None
        assert url.port is None and url.database is not None
        path = Path(url.database)
        assert path == expected and path.is_absolute() and path.resolve() == path
        assert path.is_file() and not path.is_symlink()
        assert all(not parent.is_symlink() for parent in path.parents)
        engine = create_engine(target)
        event.listen(engine, "connect", lambda db, _: db.execute("PRAGMA foreign_keys=ON"))
    else:
        safe = make_url(validate_disposable_url())
        assert safe.host in {"localhost", "127.0.0.1", "::1"} and not safe.query
        assert re.fullmatch(r"inlet_test_[a-f0-9]{32}", target)
        engine = create_engine(safe, connect_args={"options": f"-csearch_path={target}"})
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT current_schema()")) == target
    try:
        tables = set(inspect(engine).get_table_names())
        with engine.connect() as connection:
            for name in tables - {"alembic_version"}:
                quoted = engine.dialect.identifier_preparer.quote(name)
                assert connection.scalar(text(f"SELECT count(*) FROM {quoted}")) == 0
        configuration = cast(Any, configuration_fixture).__wrapped__()
        actor = uuid4().hex
        with Session(engine) as db:
            mandate, account, _ = setup(db, configuration)
            db.add(
                CustomerUser(
                    id=actor, issuer=ISSUER, subject="review-owner", email="review@example.invalid"
                )
            )
            db.flush()
            db.add(CustomerMembership(
                user_id=actor, workspace_id=mandate.workspace_id, role="owner"))
            db.commit()
            integration = WorkspaceIntegration(
                workspace_id=mandate.workspace_id,
                integration_key="review-image",
                provider="meta_ads",
                display_name="Meta",
                status="active",
                configuration={},
            )
            db.add(integration)
            db.flush()
            meta = AdvertisingAccount(
                workspace_id=mandate.workspace_id,
                connection_id=integration.id,
                platform=AdvertisingPlatform.META_ADS,
                external_account_id="101",
                name="Meta",
                currency_code="USD",
                time_zone="UTC",
            )
            db.add(meta)
            db.flush()
            db.add(
                MetaConnection(
                    workspace_id=mandate.workspace_id,
                    workspace_integration_id=integration.id,
                    account_id=meta.id,
                    external_account_id="101",
                    encrypted_credentials="unopened-fixture",
                )
            )
            policy = mandates.policy(db, mandate)
            policy.accounts.append(
                AccountScope(platform="meta_ads", connection_id=integration.id, account_id=meta.id)
            )
            tiktok = WorkspaceIntegration(
                workspace_id=mandate.workspace_id,
                integration_key="review-video",
                provider="tiktok_ads",
                display_name="TikTok",
                status="active",
                configuration={},
            )
            db.add(tiktok)
            db.flush()
            video_account = AdvertisingAccount(
                workspace_id=mandate.workspace_id,
                connection_id=tiktok.id,
                platform=AdvertisingPlatform.TIKTOK_ADS,
                external_account_id="202",
                name="TikTok",
                currency_code="USD",
                time_zone="UTC",
            )
            db.add(video_account)
            db.flush()
            db.add(
                SourceConnection(
                    id=uuid4().hex,
                    workspace_id=mandate.workspace_id,
                    integration_id=tiktok.id,
                    account_id=video_account.id,
                    provider="tiktok_ads",
                    external_id="202",
                    status="connected",
                    generation=1,
                    window_start=NOW.date(),
                    window_end=NOW.date(),
                    staged={},
                )
            )
            policy.accounts.append(
                AccountScope(
                    platform="tiktok_ads", connection_id=tiktok.id, account_id=video_account.id
                )
            )
            mandates.edit(db, mandate, mandate.revision, policy, actor, NOW)
            mandates.approve(db, mandate, mandate.revision, actor, NOW)
            db.commit()
            google = db.scalar(select(GoogleCustomerConnection).where(
                GoogleCustomerConnection.account_id == account.account_id))
            meta_source = db.scalar(select(MetaConnection).where(
                MetaConnection.account_id == meta.id))
            tiktok_source = db.scalar(select(SourceConnection).where(
                SourceConnection.account_id == video_account.id))
            assert google and meta_source and tiktok_source
            policy = mandates.policy(db, mandate)
            result = dict(
                workspace_id=mandate.workspace_id, actor_id=actor, mandate_id=mandate.id,
                mandate_revision=mandate.revision,
                mandate_policy_digest=hashlib.sha256(json.dumps(
                    policy.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
                ).encode()).hexdigest(),
                google_account_id=account.account_id, google_integration_id=account.connection_id,
                meta_account_id=meta.id, meta_integration_id=integration.id,
                tiktok_account_id=video_account.id, tiktok_integration_id=tiktok.id,
                google_source_id=google.id, meta_source_id=meta_source.id,
                tiktok_source_id=tiktok_source.id, provider_posts=0,
            )
        assert set(inspect(engine).get_table_names()) == tables
        Path(output).write_text(json.dumps(result))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
