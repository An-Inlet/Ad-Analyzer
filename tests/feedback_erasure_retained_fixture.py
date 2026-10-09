"""Closed original source records; current tests exercise feedback erasure."""

import json
import os
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from app import advertising_capabilities
from app.database.session import Base
from app.outcomes.owned_v3 import OwnedV3Assessment
from app.settings import Settings
from scripts.inlet_producer_source_lifetime import SourceLifetime
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import Engine, create_engine, event, func, inspect, make_url, select, text
from sqlalchemy.orm import Session

from tests.retired_snapshot import PIN, extract, run_bounded


@dataclass(frozen=True)
class FeedbackSourceIds:
    workspace_id: int
    actor_id: str
    account_id: int
    attempt_id: str
    receipt_id: str
    receipt_sequence: int
    publication_id: str
    store_id: str
    provider_posts: int


PROTECTED = (
    "provider_period_ledgers",
    "provider_execution_mandates",
    "provider_execution_revisions",
    "provider_execution_consents",
    "provider_execution_reviews",
    "provider_execution_approvals",
    "provider_exposure_reservations",
    "provider_execution_runs",
    "provider_execution_steps",
    "provider_execution_attempts",
    "provider_execution_responses",
    "provider_execution_receipts",
    "provider_reservation_replacements",
    "provider_qualifications",
    "provider_reviews",
    "provider_review_approvals",
    "spending_mandates",
    "spending_mandate_revisions",
    "mandate_actions",
    "mandate_audits",
    "customer_campaign_drafts",
    "customer_campaign_revisions",
    "customer_media_objects",
)


def protected(engine: Engine) -> dict[str, list[dict[str, Any]]]:
    assert advertising_capabilities.advertising_writes_enabled() is False
    with engine.connect() as connection:
        result = {}
        for name in PROTECTED:
            table = Base.metadata.tables[name]
            result[name] = [dict(row) for row in connection.execute(
                select(table).order_by(*table.primary_key.columns)
            ).mappings()]
        return result


@contextmanager
def retained_feedback_sources(
    customer_engine: Engine, artifacts: Path
) -> Iterator[tuple[Engine, OwnedV3Assessment, Any]]:
    from app.optimization_candidates.models import CandidateJob, CandidateResult

    from tests.candidate_read_retained_fixture import (
        CandidateReadIds,
        load_candidate_read_fixture,
    )

    artifacts.mkdir(parents=True)
    engine = customer_engine
    if engine.dialect.name == "sqlite":
        engine = create_engine(f"sqlite:///{artifacts / 'current.sqlite'}")
        event.listen(engine, "connect", lambda db, _: db.execute("PRAGMA foreign_keys=ON"))
        Base.metadata.create_all(engine)
        target = str(engine.url)
    else:
        url = make_url(validate_disposable_url())
        assert url.host in {"localhost", "127.0.0.1", "::1"} and not url.query
        assert engine.url == url
        with engine.connect() as connection:
            target = str(connection.scalar(text("SELECT current_schema()")))
        assert re.fullmatch(r"inlet_test_[a-f0-9]{32}", target)
    try:
        assert all(not rows for rows in protected(engine).values())
        tables = set(inspect(engine).get_table_names())
        with engine.connect() as connection:
            for name in tables - {"alembic_version"}:
                quoted = engine.dialect.identifier_preparer.quote(name)
                assert connection.scalar(text(f"SELECT count(*) FROM {quoted}")) == 0
        root = Path(__file__).resolve().parents[1]
        with SourceLifetime.open("feedback_erasure", artifacts) as lifetime:
            snapshot = lifetime.source
            extract(root, snapshot)
            lifetime.extracted()
            output, log = artifacts / "ids.json", artifacts / "producer.log"
            lifetime.child_started()
            code = run_bounded(
                [
                    sys.executable,
                    str(root / "tests/fixtures/retired_execution/feedback_erasure_seed_driver.py"),
                    target,
                    str(output),
                ],
                snapshot,
                dict(os.environ, INLET_RETIRED_EXECUTION_CHILD=PIN, PYTHONPATH=str(snapshot)),
                log,
                180,
            )
            lifetime.after_reaped(code)
        assert code == 0, log.read_text()[-6000:]
        assert output.stat().st_size <= 16384
        raw = json.loads(output.read_text())
        assert type(raw) is dict and set(raw) == {"first", "second"}
        first = raw["first"]
        assert type(first) is dict and set(first) == set(FeedbackSourceIds.__dataclass_fields__)
        for key, value in first.items():
            if key in {"workspace_id", "account_id", "receipt_sequence", "provider_posts"}:
                assert type(value) is int and value > 0
            else:
                assert type(value) is str and re.fullmatch(r"[a-f0-9]{32}", value)
        ids = FeedbackSourceIds(**first)
        assert ids.receipt_sequence == ids.provider_posts == 1
        values = {}
        for name in ("second",):
            item = raw[name]
            assert type(item) is dict and set(item) == set(CandidateReadIds.__dataclass_fields__)
            for field in ("workspace_id", "mandate_revision", "account_id"):
                assert type(item[field]) is int and item[field] > 0
            assert type(item["provider_posts"]) is int and item["provider_posts"] == 0
            assert item["provider"] == "google_ads"
            for field in (
                "actor_id",
                "mandate_id",
                "consent_id",
                "ledger_id",
                "store_id",
                "publication_id",
            ):
                assert type(item[field]) is str and re.fullmatch(r"[a-f0-9]{32}", item[field])
            for field in ("session_digest", "policy_digest"):
                assert type(item[field]) is str and re.fullmatch(r"[a-f0-9]{64}", item[field])
            values[name] = CandidateReadIds(**item)
        for field in ("workspace_id", "actor_id", "account_id", "store_id", "publication_id"):
            assert getattr(ids, field) != getattr(values["second"], field)
        assert set(inspect(engine).get_table_names()) == tables
        with Session(engine) as db:
            for model in (CandidateJob, CandidateResult):
                assert db.scalar(select(func.count()).select_from(model)) == 0
            load_candidate_read_fixture(db, values["second"])
        before = protected(engine)
        for name in (
            "provider_execution_attempts",
            "provider_execution_responses",
            "provider_execution_receipts",
            "provider_exposure_reservations",
        ):
            assert len(before[name]) == 1
            assert before[name][0]["workspace_id"] == ids.workspace_id
        assert before["provider_execution_attempts"][0]["id"] == ids.attempt_id
        assert before["provider_execution_receipts"][0]["id"] == ids.receipt_id
        assert before["provider_exposure_reservations"][0]["state"] == "held"
        value = load_assessment(engine, ids)
        try:
            yield engine, value, values["second"]
        finally:
            assert protected(engine) == before
    finally:
        if engine is not customer_engine:
            engine.dispose()


@pytest.fixture
def feedback_erasure_sources(
    customer_engine: Engine, tmp_path: Path, configuration: Settings
) -> Iterator[Any]:
    # Original test_commerce_measurement.setup makes this same per-test read setting.
    configuration.shopify_measurement_enabled = True
    with retained_feedback_sources(customer_engine, tmp_path / "feedback-erasure-source") as value:
        yield value


def load_assessment(customer_engine: Engine, ids: FeedbackSourceIds) -> OwnedV3Assessment:
    from datetime import date, timedelta

    from app.outcomes.contracts import Window
    from app.outcomes.owned_v3 import OwnedV3Request, _snapshot, compare_owned_v3
    from app.publication.service import owner

    from tests.test_commerce_measurement import NOW
    from tests.test_owned_outcomes_v3 import facts
    from tests.test_owned_outcomes_v3 import policy as maturity_policy

    request = OwnedV3Request(
        attempt_id=ids.attempt_id,
        publication_id=ids.publication_id,
        before_start=date(2026, 9, 1),
        before_end=date(2026, 9, 15),
        after_start=date(2026, 9, 15),
        after_end=date(2026, 9, 29),
    )
    with Session(customer_engine) as db:
        snap = _snapshot(
            db,
            ids.workspace_id,
            ids.actor_id,
            request,
            lambda db: owner(db, ids.workspace_id, ids.actor_id),
            lambda: NOW,
        )
        assert snap.receipt.receipt_id == ids.receipt_id
        assert snap.receipt.sequence == ids.receipt_sequence
        assert snap.receipt.account.account.account_id == ids.account_id
        assert snap.context.scope.store_id == ids.store_id
    boundary = Window.local(
        request.before_start, request.before_end, snap.context.scope.time_zone
    ).end_utc
    snap = snap.model_copy(
        update={
            "receipt": snap.receipt.model_copy(
                update={
                    "purpose": "activate",
                    "outcome": "verified_effect",
                    "dispatched_at": boundary,
                    "observed_at": boundary + timedelta(minutes=1),
                    "effective_lower": boundary,
                    "effective_upper": boundary,
                    "effective_time_evidence": "authoritative_interval",
                }
            )
        }
    )
    return compare_owned_v3(
        snap,
        request,
        maturity_policy(snap.context),
        facts(snap.context, request.before_start, request.before_end, 10),
        facts(snap.context, request.after_start, request.after_end, 15),
    )
