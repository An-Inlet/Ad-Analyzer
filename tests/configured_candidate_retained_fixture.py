"""Genuine configured origin and commerce source; no candidate work in child."""

import json
import os
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from app import advertising_capabilities
from app.commerce.models import CommerceMeasurementPublication
from app.customers.models import CustomerMembership
from app.database.models import register_models
from app.database.session import Base
from app.goals import service as goals
from app.production_runtime.optimization_origin_contracts import OptimizationMandatePreparationV1
from app.production_runtime.optimization_origin_models import OptimizationMandatePreparationRow
from app.publication import customer_intents, execution_mandates
from app.publication.contracts import fingerprint
from scripts.inlet_producer_source_lifetime import SourceLifetime
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import Engine, create_engine, event, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from tests.financial_origin_retained_fixture import fresh_rows, schema_snapshot
from tests.retired_snapshot import PIN, extract, run_bounded

ZERO = (
    "optimization_candidate_jobs",
    "optimization_candidate_results",
    "provider_execution_reviews",
    "provider_execution_approvals",
    "provider_execution_runs",
    "provider_execution_steps",
    "provider_execution_attempts",
    "provider_execution_receipts",
    "provider_execution_responses",
    "provider_exposure_reservations",
)


@dataclass(frozen=True)
class ConfiguredCandidateIds:
    platform: Literal["google_ads", "meta_ads"]
    workspace_id: int
    account_id: int
    goal_revision: int
    mandate_revision: int
    actor_id: str
    goal_id: str
    mandate_id: str
    consent_id: str
    ledger_id: str
    store_id: str
    publication_id: str
    native_connection_id: str | int
    policy_digest: str
    preparation_digest: str
    goal_digest: str
    account_scope_digest: str
    operating_policy_digest: str
    optimization_manifest_digest: str
    candidate_policy_digest: str
    candidate_manifest_digest: str
    evidence_descriptor_digest: str
    publication_manifest_digest: str
    provider_posts: int


def no_execution(engine: Engine, *, before_enqueue: bool) -> None:
    assert not advertising_capabilities.advertising_writes_enabled()
    with engine.connect() as db:
        for name in ZERO if before_enqueue else ZERO[2:]:
            assert db.scalar(text(f"SELECT count(*) FROM {name}")) == 0


def financial_graph(engine: Engine) -> dict[str, list[dict[str, Any]]]:
    """Exact current physical rows, excluding only unrelated session/candidate domains."""
    with engine.connect() as connection:
        return {
            table.name: [
                dict(row)
                for row in connection.execute(
                    select(table).order_by(*table.primary_key.columns)
                ).mappings()
            ]
            for table in Base.metadata.sorted_tables
            if table.name.startswith("provider_")
            or table.name in {
                "mandate_actions",
                "optimization_mandate_preparations",
                "google_original_completions",
            }
        }


@contextmanager
def retained_configured_candidate(
    original: Engine, artifacts: Path, platform: str, mode: str
) -> Iterator[tuple[Engine, ConfiguredCandidateIds]]:
    assert platform in {"google_ads", "meta_ads"}
    assert mode in {"unqualified", "scenario", "revoked", "revoked_during_read"}
    artifacts.mkdir(parents=True)
    engine = original
    if original.dialect.name == "sqlite":
        engine = create_engine(f"sqlite:///{artifacts / 'current.sqlite'}")
        event.listen(engine, "connect", lambda db, _: db.execute("PRAGMA foreign_keys=ON"))
        register_models().create_all(engine)
        target = str(engine.url)
    else:
        base = make_url(validate_disposable_url())
        assert (
            base.host in {"localhost", "127.0.0.1", "::1"} and not base.query and engine.url == base
        )
        with engine.connect() as connection:
            target = str(connection.scalar(text("SELECT current_schema()")))
        assert re.fullmatch(r"inlet_test_[a-f0-9]{32}", target)
    try:
        assert fresh_rows(engine) == {}
        before = schema_snapshot(engine)
        root = Path(__file__).resolve().parents[1]
        with SourceLifetime.open("configured_candidate", artifacts) as lifetime:
            extract(root, lifetime.source)
            lifetime.extracted()
            output, log = artifacts / "ids.json", artifacts / "producer.log"
            lifetime.child_started()
            code = run_bounded(
                [
                    sys.executable,
                    str(
                        root
                        / "tests/fixtures/retired_execution/configured_candidate_seed_driver.py"
                    ),
                    target,
                    str(output),
                    platform,
                    mode,
                ],
                lifetime.source,
                dict(
                    os.environ, INLET_RETIRED_EXECUTION_CHILD=PIN, PYTHONPATH=str(lifetime.source)
                ),
                log,
                180,
            )
            lifetime.after_reaped(code)
        assert code == 0, log.read_text()[-6000:]
        assert schema_snapshot(engine) == before and output.stat().st_size <= 8192
        raw = json.loads(output.read_text())
        assert type(raw) is dict and set(raw) == set(ConfiguredCandidateIds.__dataclass_fields__)
        assert raw["platform"] == platform
        for key, value in raw.items():
            if key == "platform":
                continue
            if key == "provider_posts":
                assert type(value) is int and value == 0
            elif key in {"workspace_id", "account_id", "goal_revision", "mandate_revision"} or (
                key == "native_connection_id" and platform == "meta_ads"
            ):
                assert type(value) is int and value > 0
            else:
                assert type(value) is str and re.fullmatch(
                    r"[a-f0-9]{64}" if key.endswith("digest") else r"[a-f0-9]{32}", value
                )
        ids = ConfiguredCandidateIds(**raw)
        with Session(engine) as db:
            binding = customer_intents.binding(
                db, ids.workspace_id, ids.mandate_id, ids.mandate_revision
            )
            assert (
                binding.consent_id == ids.consent_id
                and binding.ledger_id == ids.ledger_id
                and binding.policy_digest == ids.policy_digest
            )
            _, row = execution_mandates.owned(db, ids.workspace_id, ids.mandate_id)
            policy = execution_mandates.policy(db, row)
            assert row.state == "active" and policy.total_cap_micros == 50_000_000
            assert policy.goal_id == ids.goal_id and policy.goal_revision == ids.goal_revision
            assert (
                len(policy.accounts) == 1
                and policy.accounts[0].account.account_id == ids.account_id
            )
            assert policy.accounts[0].account.platform == platform and policy.accounts[
                0
            ].connection_version.split(":")[1] == str(ids.native_connection_id)
            stored = db.get(
                OptimizationMandatePreparationRow, (ids.mandate_id, ids.mandate_revision)
            )
            assert stored
            origin = OptimizationMandatePreparationV1.model_validate(stored.document)
            assert origin.digest() == stored.preparation_digest == ids.preparation_digest
            assert (
                origin.provider_policy_digest == ids.policy_digest
                and origin.operating_policy_digest == ids.operating_policy_digest
            )
            assert (
                origin.goal_digest == ids.goal_digest
                and origin.account_scope_digest == ids.account_scope_digest
            )
            goal = goals.owned(db, ids.workspace_id, ids.goal_id)
            assert goal.revision == ids.goal_revision
            assert (
                fingerprint(
                    "inlet.optimization-goal.v1", {"definition": goals.current(db, goal).definition}
                )
                == ids.goal_digest
            )
            member = db.get(CustomerMembership, (ids.actor_id, ids.workspace_id))
            assert member and member.role == "owner" and member.status == "active"
            publication = db.get(CommerceMeasurementPublication, ids.publication_id)
            assert (
                publication
                and publication.workspace_id == ids.workspace_id
                and publication.store_id == ids.store_id
                and publication.manifest_digest == ids.publication_manifest_digest
            )
        no_execution(engine, before_enqueue=True)
        before_financial = financial_graph(engine)
        try:
            yield engine, ids
        finally:
            no_execution(engine, before_enqueue=False)
            assert financial_graph(engine) == before_financial
    finally:
        if engine is not original:
            engine.dispose()
