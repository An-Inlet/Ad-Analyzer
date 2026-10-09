"""Scalar original Start history; current parent owns every migration operation."""

import json
import os
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from app import advertising_capabilities
from app.customers.models import CustomerSession, CustomerUser
from app.publication.execution_models import (
    ProviderExecutionConsent,
    ProviderExecutionMandate,
    ProviderExecutionRevision,
    ProviderPeriodLedger,
)
from app.session_automation.models import SessionAutomationRun
from scripts.inlet_producer_source_lifetime import SourceLifetime
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import Engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from tests.financial_origin_retained_fixture import fresh_rows, schema_snapshot, unchanged_rows
from tests.fixtures.retired_execution.session_migration_seed_driver import ZERO_TABLES
from tests.retired_snapshot import PIN, extract, run_bounded


@dataclass(frozen=True)
class SessionMigrationIds:
    workspace_id: int
    actor_id: str
    run_id: str
    mandate_id: str
    mandate_revision: int
    consent_id: str
    ledger_id: str
    policy_id: str
    policy_revision: int
    mandate_digest: str
    policy_digest: str
    provider_posts: int


def no_effects(engine: Engine) -> None:
    assert not advertising_capabilities.advertising_writes_enabled()
    with engine.connect() as db:
        for name in ZERO_TABLES:
            assert db.scalar(text(f"SELECT count(*) FROM {name}")) == 0


@contextmanager
def retained_session_migration_source(
    engine: Engine, artifacts: Path
) -> Iterator[SessionMigrationIds]:
    base = make_url(validate_disposable_url())
    assert base.drivername == "postgresql+psycopg"
    assert base.host in {"127.0.0.1", "localhost", "::1"} and not base.query
    assert engine.url.set(query={}) == base
    assert set(engine.url.query) == {"options"}
    options = engine.url.query["options"]
    assert type(options) is str
    assert re.fullmatch(r"-csearch_path=inlet_auto_[a-f0-9]{32}", options)
    with engine.connect() as db:
        target = str(db.scalar(text("SELECT current_schema()")))
        assert options == f"-csearch_path={target}"
        assert re.fullmatch(r"inlet_auto_[a-f0-9]{32}", target)
        assert set(db.scalars(text("SELECT version_num FROM alembic_version"))) == set(
            ScriptDirectory.from_config(Config("alembic.ini")).get_heads()
        )
    bootstrap = fresh_rows(engine)
    before = schema_snapshot(engine)
    artifacts.mkdir(parents=True)
    root = Path(__file__).resolve().parents[1]
    with SourceLifetime.open("session_migration", artifacts) as lifetime:
        extract(root, lifetime.source)
        lifetime.extracted()
        output, log = artifacts / "ids.json", artifacts / "producer.log"
        lifetime.child_started()
        code = run_bounded(
            [
                sys.executable,
                str(root / "tests/fixtures/retired_execution/session_migration_seed_driver.py"),
                target,
                str(output),
            ],
            lifetime.source,
            dict(os.environ, INLET_RETIRED_EXECUTION_CHILD=PIN, PYTHONPATH=str(lifetime.source)),
            log,
            180,
        )
        lifetime.after_reaped(code)
    assert code == 0, log.read_text()[-6000:]
    assert schema_snapshot(engine) == before
    unchanged_rows(engine, bootstrap)
    assert output.stat().st_size <= 4096
    raw = json.loads(output.read_text())
    assert type(raw) is dict and set(raw) == set(SessionMigrationIds.__dataclass_fields__)
    for name, value in raw.items():
        if name in {"workspace_id", "mandate_revision", "policy_revision"}:
            assert type(value) is int and value > 0
        elif name == "provider_posts":
            assert type(value) is int and value == 0
        else:
            assert type(value) is str and re.fullmatch(
                r"[a-f0-9]{64}" if name.endswith("digest") else r"[a-f0-9]{32}", value
            )
    ids = SessionMigrationIds(**raw)
    with Session(engine) as db:
        row = db.get(SessionAutomationRun, ids.run_id)
        assert row and row.state == "running"
        for name, value in raw.items():
            if name not in {"run_id", "provider_posts"}:
                assert getattr(row, name) == value
        session = db.get(CustomerSession, row.original_session_digest)
        user = db.get(CustomerUser, ids.actor_id)
        assert session and user and session.user_id == user.id
        mandate = db.get(ProviderExecutionMandate, ids.mandate_id)
        revision = db.get(ProviderExecutionRevision, (ids.mandate_id, ids.mandate_revision))
        consent = db.get(ProviderExecutionConsent, ids.consent_id)
        ledger = db.get(ProviderPeriodLedger, ids.ledger_id)
        assert mandate and revision and consent and ledger
        assert all(
            item.workspace_id == ids.workspace_id for item in (mandate, revision, consent, ledger)
        )
        assert mandate.ledger_id == ledger.id and mandate.revision == ids.mandate_revision
        assert consent.mandate_id == mandate.id and consent.revision == ids.mandate_revision
        assert revision.digest == ids.mandate_digest
    no_effects(engine)
    try:
        yield ids
    finally:
        no_effects(engine)
