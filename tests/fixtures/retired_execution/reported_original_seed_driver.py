"""Owned actual Meta HTTP optimization receipt; explicit offline numeric policy."""

import json
import os
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import app
from app.ads.enums import AdvertisingPlatform
from app.ads.models import Campaign
from app.customers.models import CustomerSession, CustomerUser
from app.meta.models import MetaConnection
from app.publication import execution_mandates, optimization
from app.publication.execution_models import ProviderExecutionMandate, ProviderExecutionReceipt
from app.settings import Settings
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import create_engine, event, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import FakeProvider
from tests.test_durable_optimization import ready
from tests.test_shopify_sales import configuration


def produce(db: Session, config: Settings, path: Path) -> dict[str, Any]:
    wid, actor, binding, scope, target, action, execution, server = ready(
        db, config, path, "meta_ads", campaign=True, period_end=None
    )
    row = optimization.prepare_optimization(
        db, wid, binding, scope, target, action, "a" * 64, actor, execution, lambda: NOW
    )
    optimization.approve_optimization(
        db, wid, row.id, row.digest, row.plan_digest, actor, execution, lambda: NOW
    )
    run = optimization.create_run(db, wid, row.id, actor, execution, lambda: NOW)
    claim = optimization.claim_step(db, wid, run.id, actor, execution, lambda: NOW)
    assert claim is not None
    receipt = optimization.execute_claim(db, claim, actor, execution, lambda: NOW)
    assert receipt.outcome == "verified_target_state" and len(server.posts) == 1
    user = db.get(CustomerUser, actor)
    assert user is not None
    user.issuer = FakeProvider.issuer
    now = datetime.now(UTC)
    session = CustomerSession(
        digest=uuid4().hex * 2,
        user_id=actor,
        csrf_digest="f" * 64,
        created_at=int(now.timestamp()),
        authenticated_at=int(now.timestamp()),
        expires_at=int((now + timedelta(days=60)).timestamp()),
    )
    db.add(session)
    source = db.scalar(
        select(MetaConnection).where(MetaConnection.account_id == scope.account.account_id)
    )
    assert source is not None
    source.conversion_action_type = "purchase"
    campaign = Campaign(
        account_id=scope.account.account_id,
        external_campaign_id="5",
        platform=AdvertisingPlatform.META_ADS,
        name="Owned Campaign",
        status="ACTIVE",
    )
    db.add(campaign)
    db.commit()
    mandate = db.get(ProviderExecutionMandate, binding.mandate_id)
    assert mandate is not None and run.reservation_id is not None
    policy = execution_mandates.policy(db, mandate)
    saved_receipt = db.scalar(
        select(ProviderExecutionReceipt).where(
            ProviderExecutionReceipt.attempt_id == claim.attempt_id
        )
    )
    assert saved_receipt is not None
    return dict(
        workspace_id=wid,
        actor_id=actor,
        session_digest=session.digest,
        account_id=scope.account.account_id,
        campaign_id=campaign.id,
        source_id=source.id,
        goal_id=policy.goal_id,
        goal_revision=policy.goal_revision,
        mandate_id=mandate.id,
        review_id=row.id,
        run_id=run.id,
        attempt_id=claim.attempt_id,
        receipt_id=saved_receipt.id,
        reservation_id=run.reservation_id,
        original_post_count=len(server.posts),
    )


def main() -> None:
    target, output = sys.argv[1:]
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
        safe_url = make_url(validate_disposable_url())
        assert safe_url.host in {"localhost", "127.0.0.1", "::1"} and not safe_url.query
        engine = create_engine(
            safe_url,
            connect_args={"options": f"-csearch_path={target}"},
        )
        with engine.connect() as connection_check:
            assert connection_check.scalar(text("select current_schema()")) == target
    try:
        tables = set(inspect(engine).get_table_names())
        with engine.connect() as empty_check:
            for table in sorted(tables - {"alembic_version"}):
                quoted = engine.dialect.identifier_preparer.quote(table)
                assert empty_check.execute(text(f"SELECT 1 FROM {quoted} LIMIT 1")).first() is None
        config = cast(Any, configuration).__wrapped__()
        with Session(engine) as db:
            result = produce(db, config, Path(output).parent)
            db.commit()
        assert set(inspect(engine).get_table_names()) == tables
        Path(output).write_text(json.dumps(result))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
