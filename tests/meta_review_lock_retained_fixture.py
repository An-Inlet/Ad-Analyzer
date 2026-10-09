"""Current native lifecycle concurrency over one genuine original simulation approval."""

import os
import re
import sys
from collections.abc import Iterator
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any

import pytest
from app.campaign_review import service as review
from app.campaign_review.contracts import RevisionInput
from app.mandates import service as mandates
from app.mandates.models import Mandate, MandateRevision
from app.meta.models import MetaConnection, MetaPendingGrant
from app.meta.security import Vault, utc
from app.settings import Settings
from pydantic import BaseModel, ConfigDict, Field
from scripts.inlet_producer_source_lifetime import SourceLifetime
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import Engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from tests.financial_origin_retained_fixture import fresh_rows, schema_snapshot
from tests.retired_snapshot import PIN, extract, run_bounded
from tests.social_producer_retained_fixture import graph
from tests.test_commerce_measurement import NOW

Positive = Annotated[int, Field(strict=True, gt=0)]


class MetaLockIds(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    workspace_id: Positive
    mandate_id: Annotated[str, Field(pattern=r"^[a-f0-9]{32}$")]
    mandate_revision: Positive
    account_id: Positive
    integration_id: Positive
    native_id: Positive


def load_source(db: Session, ids: MetaLockIds) -> tuple[int, RevisionInput]:
    mandate = db.get(Mandate, ids.mandate_id)
    assert mandate and mandate.workspace_id == ids.workspace_id
    assert mandate.revision == ids.mandate_revision and mandate.state == "approved"
    revision = db.get(MandateRevision, (ids.mandate_id, ids.mandate_revision))
    assert revision and revision.approved_by == "owner" and revision.approved_at is not None
    assert utc(revision.approved_at) == NOW
    policy = mandates.policy(db, mandate)
    assert len(policy.accounts) == 1
    scope = policy.accounts[0]
    assert scope.platform == "meta_ads"
    assert (scope.account_id, scope.connection_id) == (ids.account_id, ids.integration_id)
    native = db.get(MetaConnection, ids.native_id)
    assert native and native.workspace_id == ids.workspace_id and native.generation == 1
    assert (native.account_id, native.workspace_integration_id, native.external_account_id) == (
        ids.account_id, ids.integration_id, "101",
    )
    body = RevisionInput(
        account=scope, mandate_id=ids.mandate_id, mandate_revision=ids.mandate_revision,
        currency="USD", budget_micros=60, starts_at=NOW, ends_at=NOW + timedelta(hours=1),
        content={
            "kind": "meta_website_sales_image_v1", "objective": "website_sales",
            "name": "Fixture", "landing_page": "https://example.invalid/shop",
            "audience": {"countries": ["US"], "languages": ["en"]},
            "headline": "Shop", "text": "Supplied", "call_to_action": "SHOP_NOW",
            "media": {"media_id": "b" * 32, "sha256": "a" * 64},
        },
    )
    assert review.binding(db, ids.workspace_id, body, NOW).endswith(":1")
    return ids.workspace_id, body


def assert_lifecycle_delta(
    before: dict[str, list[dict[str, Any]]], after: dict[str, list[dict[str, Any]]],
    ids: MetaLockIds, operation: str, config: Settings, bundle: dict[str, Any],
    started: datetime, ended: datetime,
) -> None:
    expected = deepcopy(before)

    def owned(table: str, column: str, value: Any) -> dict[str, Any]:
        rows = [row for row in expected[table] if row[column] == value]
        assert len(rows) == 1
        return rows[0]

    def updated(table: str, column: str, value: Any) -> None:
        old = owned(table, column, value)
        rows = [row for row in after[table] if row[column] == value]
        assert len(rows) == 1
        stamp = rows[0]["updated_at"]
        if stamp != old["updated_at"]:
            assert started <= utc(stamp) <= ended
            old["updated_at"] = stamp

    workspace = owned("workspaces", "id", ids.workspace_id)
    workspace["export_privacy_revision"] += 1
    updated("workspaces", "id", ids.workspace_id)
    grant = owned("meta_pending_grants", "workspace_id", ids.workspace_id)
    expected["meta_pending_grants"].remove(grant)
    native = owned("meta_connections", "id", ids.native_id)
    if operation == "disconnect":
        expected["meta_connections"].remove(native)
        expected["meta_oauth_states"] = [
            row for row in expected["meta_oauth_states"] if row["workspace_id"] != ids.workspace_id
        ]
        owned("workspace_integrations", "id", ids.integration_id)["status"] = "revoked"
        updated("workspace_integrations", "id", ids.integration_id)
        action = "disconnected"
    else:
        assert operation == "reauthorize"
        rows = [row for row in after["meta_connections"] if row["id"] == ids.native_id]
        assert len(rows) == 1
        assert (
            Vault(config).open(ids.workspace_id, "101", rows[0]["encrypted_credentials"]) == bundle
        )
        native.update(
            generation=2, encrypted_credentials=rows[0]["encrypted_credentials"],
            status="connected", conversion_action_type="purchase", connected_at=NOW,
            last_sync_at=None, covered_from=None, covered_through=None, last_attempt_at=None,
            next_attempt_at=None, error_code=None, window_start=None, window_end=None,
            cursor=None, phase="campaigns",
        )
        updated("advertising_accounts", "id", ids.account_id)
        action = "connected"
    audit_ids = {row["id"] for row in before["meta_audits"]}
    added = [row for row in after["meta_audits"] if row["id"] not in audit_ids]
    assert len(added) == 1
    audit = added[0]
    assert type(audit["id"]) is int and audit["id"] > 0
    assert started <= utc(audit["created_at"]) <= ended
    assert audit == dict(
        id=audit["id"], workspace_id=ids.workspace_id, action=action, actor_role="owner",
        record_count=0, created_at=audit["created_at"],
    )
    expected["meta_audits"].append(audit)
    expected["meta_audits"].sort(key=lambda row: row["id"])
    assert after == expected


@pytest.fixture
def meta_review_source(
    customer_engine: Engine, meta_configuration: Settings,
    tmp_path: Path, request: pytest.FixtureRequest,
) -> Iterator[MetaLockIds | None]:
    assert request.node.originalname == "test_review_native_meta_lock_order"
    if customer_engine.dialect.name != "postgresql":
        yield None
        return
    operation = request.node.callspec.params["operation"]
    assert operation in {"disconnect", "reauthorize"}
    safe = make_url(validate_disposable_url())
    assert safe.host in {"localhost", "127.0.0.1", "::1"} and not safe.query
    assert customer_engine.url == safe
    with customer_engine.connect() as connection:
        target = str(connection.scalar(text("SELECT current_schema()")))
    assert re.fullmatch(r"inlet_test_[a-f0-9]{32}", target)
    assert fresh_rows(customer_engine) == {}
    schema = schema_snapshot(customer_engine)
    artifacts = tmp_path / "meta-lock-original"
    assert artifacts.is_absolute() and artifacts.resolve() == artifacts
    assert not artifacts.is_symlink() and all(not p.is_symlink() for p in artifacts.parents)
    artifacts.mkdir()
    root = Path(__file__).resolve().parents[1]
    with SourceLifetime.open("meta_review_lock", artifacts) as lifetime:
        extract(root, lifetime.source)
        lifetime.extracted()
        output, log = artifacts / "ids.json", artifacts / "producer.log"
        lifetime.child_started()
        code = run_bounded(
            [sys.executable,
             str(root / "tests/fixtures/retired_execution/meta_review_lock_seed_driver.py"),
             target, str(output)],
            lifetime.source,
            dict(os.environ, INLET_RETIRED_EXECUTION_CHILD=PIN, PYTHONPATH=str(lifetime.source)),
            log, 180,
        )
        lifetime.after_reaped(code)
    assert code == 0, log.read_text()[-6000:]
    assert 0 < output.stat().st_size <= 8192
    ids = MetaLockIds.model_validate_json(output.read_bytes())
    with Session(customer_engine) as db:
        load_source(db, ids)
        grant = db.scalars(select(MetaPendingGrant)).one()
        assert grant.workspace_id == ids.workspace_id
        assert grant.actor_digest == Vault(meta_configuration).digest("actor", "owner-session")
        assert utc(grant.expires_at) > NOW
        bundle = Vault(meta_configuration).open(
            ids.workspace_id, "grant:" + grant.actor_digest, grant.encrypted_credentials
        )
    assert schema_snapshot(customer_engine) == schema
    before = graph(customer_engine)
    assert all(not rows for name, rows in before.items() if name.startswith("provider_"))
    assert before["mandate_actions"] == []
    # Every unrelated row is compared exactly; no staging/derived table exception.
    started = datetime.now(UTC)
    try:
        yield ids
    finally:
        assert_lifecycle_delta(
            before, graph(customer_engine), ids, operation, meta_configuration, bundle,
            started, datetime.now(UTC),
        )
        assert schema_snapshot(customer_engine) == schema
