"""Closed scalar financial source; callers retain actual current physical DDL."""

import json
import os
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from app.campaign_review.models import CampaignRevision
from app.customers.models import CustomerMembership
from app.google_connections.models import GoogleCustomerConnection
from app.mandates import service as simulation
from app.mandates.models import Mandate
from app.publication import execution_mandates
from app.publication.execution_contracts import ExecutionAccount, ProviderMandatePolicy
from app.publication.execution_models import ProviderExecutionConsent
from scripts.inlet_producer_source_lifetime import SourceLifetime
from scripts.inlet_restore_bootstrap import expected_bootstrap
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import Engine, MetaData, Table, create_engine, event, inspect, select, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session

from tests.retired_snapshot import PIN, extract, run_bounded

Mode = Literal["source_only", "consented_origin"]


@dataclass(frozen=True)
class SourceIds:
    workspace_id: int
    actor_id: str
    simulation_mandate_id: str
    goal_id: str
    goal_revision: int
    account_id: int
    native_connection_id: str
    source_draft_id: str
    source_draft_revision: int
    source_draft_digest: str
    provider_policy_digest: str


@dataclass(frozen=True)
class ConsentedIds(SourceIds):
    provider_mandate_id: str
    provider_mandate_revision: int
    provider_consent_id: str
    ledger_id: str


def schema_snapshot(engine: Engine) -> str:
    inspector = inspect(engine)
    tables = {}
    for table in sorted(inspector.get_table_names()):
        tables[table] = dict(
            columns=[{**c, "type": str(c["type"])} for c in inspector.get_columns(table)],
            fks=inspector.get_foreign_keys(table),
            indexes=inspector.get_indexes(table),
            checks=inspector.get_check_constraints(table),
        )
    with engine.connect() as db:
        if engine.dialect.name == "sqlite":
            triggers = db.execute(
                text("SELECT name,sql FROM sqlite_master WHERE type='trigger' ORDER BY name")
            ).all()
        else:
            triggers = db.execute(
                text(
                    "SELECT t.tgname,pg_get_triggerdef(t.oid) FROM pg_trigger t "
                    "JOIN pg_class c ON c.oid=t.tgrelid "
                    "JOIN pg_namespace n ON n.oid=c.relnamespace "
                    "WHERE n.nspname=current_schema() AND NOT t.tgisinternal "
                    "ORDER BY t.tgname,c.relname"
                )
            ).all()
        revisions = (
            list(db.scalars(text("SELECT version_num FROM alembic_version")))
            if "alembic_version" in tables
            else []
        )
    return json.dumps(
        dict(tables=tables, triggers=[list(r) for r in triggers], revisions=sorted(revisions)),
        sort_keys=True,
        default=str,
    )


def validate_pg_url(candidate: URL, base: URL, target: str | None = None) -> None:
    assert base.drivername == "postgresql+psycopg"
    assert base.host in {"127.0.0.1", "localhost", "::1"} and not base.query
    assert candidate.set(query={}) == base
    if candidate.query:
        assert set(candidate.query) == {"options"}
        option = candidate.query["options"]
        assert type(option) is str
        assert re.fullmatch(r"-csearch_path=inlet_migration_fixture_[a-f0-9]{32}", option)
        if target is not None:
            assert option == f"-csearch_path={target}"
    if target is not None:
        assert re.fullmatch(r"inlet_(test|migration_fixture)_[a-f0-9]{32}", target)


def fresh_rows(engine: Engine) -> dict[str, list[dict[str, Any]]]:
    tables = set(inspect(engine).get_table_names())
    expected = (
        expected_bootstrap()
        if engine.dialect.name == "postgresql" and "alembic_version" in tables
        else {}
    )
    assert set(expected) <= tables
    snapshot = {}
    with engine.connect() as connection:
        for name in tables - {"alembic_version"}:
            if name not in expected:
                quoted = engine.dialect.identifier_preparer.quote(name)
                assert connection.scalar(text(f"SELECT count(*) FROM {quoted}")) == 0
                continue
            table = Table(name, MetaData(), autoload_with=connection, resolve_fks=False)
            rows = [dict(row) for row in connection.execute(select(table)).mappings()]
            stripped = [
                {k: v for k, v in row.items() if k not in {"created_at", "updated_at"}}
                for row in rows
            ]

            def key(row: dict[str, Any]) -> str:
                return json.dumps(row, sort_keys=True, default=str)

            assert sorted(map(key, stripped)) == sorted(map(key, expected[name]))
            snapshot[name] = rows
    return snapshot


def unchanged_rows(engine: Engine, snapshot: dict[str, list[dict[str, Any]]]) -> None:
    with engine.connect() as connection:
        for name, rows in snapshot.items():
            table = Table(name, MetaData(), autoload_with=connection, resolve_fks=False)
            for before in rows:
                statement = select(table).where(
                    *(c == before[c.name] for c in table.primary_key.columns)
                )
                assert dict(connection.execute(statement).mappings().one()) == before


def retained_financial_source(engine: Engine, artifacts: Path, mode: Mode) -> SourceIds:
    assert mode in {"source_only", "consented_origin"}
    artifacts.mkdir(parents=True)
    if engine.dialect.name == "sqlite":
        assert engine.url.database and not engine.url.query
        assert Path(engine.url.database).resolve().is_relative_to(artifacts.parent.resolve())
        assert Path(engine.url.database).is_file()
        target = str(engine.url)
    else:
        url = make_url(validate_disposable_url())
        validate_pg_url(engine.url, url)
        with engine.connect() as db:
            target = str(db.scalar(text("SELECT current_schema()")))
        validate_pg_url(engine.url, url, target)
    bootstrap = fresh_rows(engine)
    before = schema_snapshot(engine)
    root = Path(__file__).resolve().parents[1]
    with SourceLifetime.open("financial_origin", artifacts) as lifetime:
        extract(root, lifetime.source)
        lifetime.extracted()
        output, log = artifacts / "ids.json", artifacts / "producer.log"
        lifetime.child_started()
        code = run_bounded(
            [
                sys.executable,
                str(root / "tests/fixtures/retired_execution/financial_origin_seed_driver.py"),
                target,
                str(output),
                mode,
            ],
            lifetime.source,
            dict(os.environ, INLET_RETIRED_EXECUTION_CHILD=PIN, PYTHONPATH=str(lifetime.source)),
            log,
            180,
        )
        lifetime.after_reaped(code)
    assert schema_snapshot(engine) == before
    unchanged_rows(engine, bootstrap)
    assert code == 0, log.read_text()[-6000:]
    assert output.stat().st_size <= 4096
    raw = json.loads(output.read_text())
    cls = SourceIds if mode == "source_only" else ConsentedIds
    assert type(raw) is dict and set(raw) == set(cls.__dataclass_fields__)
    for key, value in raw.items():
        if key in {
            "workspace_id",
            "goal_revision",
            "account_id",
            "source_draft_revision",
            "provider_mandate_revision",
        }:
            assert type(value) is int and value > 0
        else:
            assert type(value) is str and re.fullmatch(
                r"[a-f0-9]{64}" if key.endswith("digest") else r"[a-f0-9]{32}", value
            )
    ids = cls(**raw)
    with Session(engine) as db:
        p = current_policy(db, ids)
        if isinstance(ids, ConsentedIds):
            _, row = execution_mandates.owned(db, ids.workspace_id, ids.provider_mandate_id)
            assert row.revision == ids.provider_mandate_revision and row.ledger_id == ids.ledger_id
            assert execution_mandates.policy(db, row) == p
            consent = db.get(ProviderExecutionConsent, ids.provider_consent_id)
            assert consent and consent.mandate_id == row.id and consent.revision == row.revision
        for table in (
            "provider_execution_attempts",
            "provider_execution_receipts",
            "provider_exposure_reservations",
        ):
            assert db.scalar(text(f"SELECT count(*) FROM {table}")) == 0
    return ids


def current_policy(db: Session, ids: SourceIds) -> ProviderMandatePolicy:
    row = db.get(Mandate, ids.simulation_mandate_id)
    assert row and row.workspace_id == ids.workspace_id
    source = simulation.policy(db, row)
    native = db.get(GoogleCustomerConnection, ids.native_connection_id)
    assert (
        native and native.workspace_id == ids.workspace_id and native.account_id == ids.account_id
    )
    member = db.get(CustomerMembership, (ids.actor_id, ids.workspace_id))
    assert member and member.role == "owner" and member.status == "active"
    draft = db.get(CampaignRevision, (ids.source_draft_id, ids.source_draft_revision))
    assert draft and draft.approved_by == ids.actor_id and draft.digest == ids.source_draft_digest
    assert source.goal_id == ids.goal_id and source.goal_revision == ids.goal_revision
    policy = ProviderMandatePolicy(
        environment="contract_test",
        workspace_id=ids.workspace_id,
        goal_id=source.goal_id,
        goal_revision=source.goal_revision,
        currency=source.currency,
        time_zone=source.time_zone,
        starts_at=source.starts_at,
        ends_at=source.ends_at,
        accounts=[
            ExecutionAccount(
                workspace_id=ids.workspace_id,
                account=source.accounts[0],
                external_advertiser_id=native.external_account_id,
                connection_version=f"google:{native.id}:{native.generation}",
            )
        ],
        total_cap_micros=100,
        per_plan_cap_micros=80,
        positive_change_cap_micros=20,
        action_limit=10,
        cooldown_seconds=0,
        freshness_seconds=300,
        aggressiveness_percent=5,
        allowed_purposes=["create_paused", "activate"],
        campaign_and_creative_policy="new_exact_review_required",
        activation_policy="separate_exact_approval",
    )
    assert policy.digest() == ids.provider_policy_digest
    return policy


@contextmanager
def financial_source_engine(original: Engine, path: Path) -> Iterator[Engine]:
    if original.dialect.name != "sqlite":
        yield original
        return
    from app.database.models import register_models

    engine = create_engine(f"sqlite:///{path / 'financial.sqlite'}")
    event.listen(engine, "connect", lambda db, _: db.execute("PRAGMA foreign_keys=ON"))
    register_models().create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()
