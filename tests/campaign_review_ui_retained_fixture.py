"""Closed three-account original prefix and current owned offline-review source."""

import hashlib
import json
import os
import re
import stat
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from app.ads.models import AdvertisingAccount
from app.campaign_review.storage import LocalMediaStore
from app.customers.models import CustomerMembership, CustomerUser
from app.database.session import Base
from app.google_connections.models import GoogleCustomerConnection
from app.mandates import service as mandates
from app.mandates.models import Mandate
from app.mandates.schemas import AccountScope
from app.meta.models import MetaConnection
from app.sources.models import SourceConnection
from app.workspaces.models import WorkspaceIntegration
from scripts.inlet_producer_source_lifetime import SourceLifetime
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import Engine, create_engine, event, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from tests.campaign_review_retained_fixture import no_effects
from tests.financial_origin_retained_fixture import schema_snapshot
from tests.retired_snapshot import PIN, extract, run_bounded
from tests.social_producer_retained_fixture import graph, owned_sqlite_target
from tests.test_commerce_measurement import NOW

if TYPE_CHECKING:
    from tests.campaign_review_ui_evidence import CampaignUiEvidence


@dataclass(frozen=True)
class CampaignReviewUiIds:
    workspace_id: int
    actor_id: str
    mandate_id: str
    mandate_revision: int
    mandate_policy_digest: str
    google_account_id: int
    google_integration_id: int
    meta_account_id: int
    meta_integration_id: int
    tiktok_account_id: int
    tiktok_integration_id: int
    google_source_id: str
    meta_source_id: int
    tiktok_source_id: str
    provider_posts: int


def read_ids(output: Path) -> CampaignReviewUiIds:
    info = output.lstat()
    assert not output.is_symlink() and stat.S_ISREG(info.st_mode)
    assert 0 < info.st_size <= 8192
    raw = json.loads(output.read_text())
    assert type(raw) is dict and set(raw) == set(CampaignReviewUiIds.__dataclass_fields__)
    for key, value in raw.items():
        if key in {"actor_id", "mandate_id", "google_source_id", "tiktok_source_id",
                   "mandate_policy_digest"}:
            assert type(value) is str and re.fullmatch(
                r"[a-f0-9]{64}" if key == "mandate_policy_digest" else r"[a-f0-9]{32}", value)
        else:
            assert type(value) is int and (value == 0 if key == "provider_posts" else value > 0)
    return CampaignReviewUiIds(**raw)


def binding(db: Session, ids: CampaignReviewUiIds) -> tuple[Mandate, AccountScope]:
    row = db.get(Mandate, ids.mandate_id)
    assert row and row.workspace_id == ids.workspace_id and row.revision == ids.mandate_revision
    assert row.state == "approved" and not row.paused
    policy = mandates.policy(db, row)
    assert hashlib.sha256(json.dumps(policy.model_dump(mode="json"), sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest() == (
        ids.mandate_policy_digest)
    assert (policy.total_cap_micros, policy.per_action_cap_micros,
            policy.positive_change_cap_micros) == (100, 80, 50)
    expected = [("google_ads", ids.google_integration_id, ids.google_account_id, "1234567890"),
                ("meta_ads", ids.meta_integration_id, ids.meta_account_id, "101"),
                ("tiktok_ads", ids.tiktok_integration_id, ids.tiktok_account_id, "202")]
    assert [(s.platform, s.connection_id, s.account_id) for s in policy.accounts] == [
        item[:3] for item in expected]
    for provider, integration_id, account_id, native_id in expected:
        integration = db.get(WorkspaceIntegration, integration_id)
        account = db.get(AdvertisingAccount, account_id)
        assert integration and account
        assert integration.workspace_id == account.workspace_id == ids.workspace_id
        assert integration.provider == str(account.platform) == provider
        assert integration.status == "active" and account.connection_id == integration_id
        assert account.external_account_id == native_id and account.currency_code == "USD"
        assert account.time_zone == (None if provider == "google_ads" else "UTC")
    google = db.get(GoogleCustomerConnection, ids.google_source_id)
    meta = db.get(MetaConnection, ids.meta_source_id)
    tiktok = db.get(SourceConnection, ids.tiktok_source_id)
    assert google and meta and tiktok
    assert google.account_id == ids.google_account_id and google.integration_id == (
        ids.google_integration_id)
    assert meta.account_id == ids.meta_account_id and meta.workspace_integration_id == (
        ids.meta_integration_id)
    assert tiktok.account_id == ids.tiktok_account_id and tiktok.integration_id == (
        ids.tiktok_integration_id)
    assert google.workspace_id == meta.workspace_id == tiktok.workspace_id == ids.workspace_id
    assert google.generation == meta.generation == tiktok.generation == 1
    assert tiktok.provider == "tiktok_ads" and tiktok.external_id == "202"
    assert tiktok.status == "connected" and tiktok.window_start == tiktok.window_end == NOW.date()
    user = db.get(CustomerUser, ids.actor_id)
    member = db.get(CustomerMembership, (ids.actor_id, ids.workspace_id))
    assert user and member and user.subject == "review-owner"
    assert user.email == "review@example.invalid" and user.status == "active"
    assert member.role == "owner" and member.status == "active"
    return row, policy.accounts[0]


@dataclass
class CampaignUiSource:
    engine: Engine
    ids: CampaignReviewUiIds
    artifacts: Path
    store: LocalMediaStore
    evidence: "CampaignUiEvidence"


@contextmanager
def retained_campaign_ui(original: Engine, artifacts: Path) -> Iterator[CampaignUiSource]:
    from tests.campaign_review_ui_evidence import CampaignUiEvidence

    assert artifacts.is_absolute() and artifacts.resolve() == artifacts
    assert not artifacts.is_symlink() and all(not p.is_symlink() for p in artifacts.parents)
    artifacts.mkdir(parents=True)
    engine = original
    if original.dialect.name == "sqlite":
        path = artifacts / "current.sqlite"
        path.touch(exist_ok=False)
        target = owned_sqlite_target(f"sqlite:///{path}", path)
        engine = create_engine(target)
        event.listen(engine, "connect", lambda db, _: db.execute("PRAGMA foreign_keys=ON"))
        Base.metadata.create_all(engine)
    else:
        safe = make_url(validate_disposable_url())
        assert safe.host in {"localhost", "127.0.0.1", "::1"} and not safe.query
        assert engine.url == safe
        with engine.connect() as connection:
            target = str(connection.scalar(text("SELECT current_schema()")))
        assert re.fullmatch(r"inlet_test_[a-f0-9]{32}", target)
    try:
        with engine.connect() as connection:
            for name in set(inspect(engine).get_table_names()) - {"alembic_version"}:
                quoted = engine.dialect.identifier_preparer.quote(name)
                assert connection.scalar(text(f"SELECT count(*) FROM {quoted}")) == 0
        schema = schema_snapshot(engine)
        root = Path(__file__).resolve().parents[1]
        output, log = artifacts / "ids.json", artifacts / "producer.log"
        with SourceLifetime.open("campaign_review_ui", artifacts) as lifetime:
            extract(root, lifetime.source)
            lifetime.extracted()
            lifetime.child_started()
            code = run_bounded([
                sys.executable,
                str(root / "tests/fixtures/retired_execution/campaign_review_ui_seed_driver.py"),
                target, str(output),
            ], lifetime.source, dict(os.environ, INLET_RETIRED_EXECUTION_CHILD=PIN,
                                    PYTHONPATH=str(lifetime.source)), log, 180)
            lifetime.after_reaped(code)
        assert code == 0, log.read_text()[-6000:]
        ids = read_ids(output)
        with Session(engine) as db:
            binding(db, ids)
        no_effects(engine)
        before = graph(engine)
        source = CampaignUiSource(engine, ids, artifacts, LocalMediaStore(artifacts / "media"),
                                  CampaignUiEvidence(ids, deepcopy(before)))
        assert source.evidence.original is not before
        try:
            yield source
        finally:
            source.evidence.assert_final(source, before, graph(engine))
            no_effects(engine)
            assert schema_snapshot(engine) == schema
    finally:
        if engine is not original:
            engine.dispose()


@pytest.fixture
def campaign_ui_source(customer_engine: Engine, tmp_path: Path,
                       request: pytest.FixtureRequest) -> Iterator[CampaignUiSource]:
    assert request.node.originalname == "test_review_browser_real_api"
    with retained_campaign_ui(customer_engine, tmp_path / "campaign-ui-original") as source:
        yield source
