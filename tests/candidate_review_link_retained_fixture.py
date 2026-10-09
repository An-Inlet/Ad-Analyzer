"""One exact historical review-link source; current export and migration consumers."""

import json
import os
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from alembic.script import ScriptDirectory
from app import advertising_capabilities
from app.customers.models import CustomerSession
from app.database.models import register_models
from app.optimization_candidates.models import CandidateJob, CandidateResult
from app.optimization_candidates.review_models import CandidateReviewLink
from app.publication.execution_models import ProviderExecutionReview
from scripts.inlet_producer_source_lifetime import SourceLifetime
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session

from tests.financial_origin_retained_fixture import fresh_rows, schema_snapshot, unchanged_rows
from tests.retired_snapshot import PIN, extract, run_bounded

ZERO = (
    "provider_execution_approvals",
    "provider_execution_attempts",
    "provider_execution_receipts",
    "provider_execution_responses",
    "provider_exposure_reservations",
    "provider_execution_runs",
    "provider_execution_steps",
)
DIGESTS = (
    "candidate_digest",
    "input_digest",
    "selection_digest",
    "policy_digest",
    "evidence_digest",
    "source_digest",
    "review_digest",
    "plan_digest",
)


@dataclass(frozen=True)
class CandidateReviewLinkIds:
    workspace_id: int
    actor_id: str
    job_id: str
    result_id: str
    review_id: str
    candidate_digest: str
    input_digest: str
    selection_digest: str
    policy_digest: str
    evidence_digest: str
    source_digest: str
    review_digest: str
    plan_digest: str
    provider_posts: int


def validate_url(candidate: URL, base: URL, schema: str | None = None) -> None:
    assert base.drivername == "postgresql+psycopg"
    assert base.host in {"localhost", "127.0.0.1", "::1"} and not base.query
    assert candidate.set(query={}) == base
    if candidate.query:
        assert set(candidate.query) == {"options"}
        option = candidate.query["options"]
        assert type(option) is str and re.fullmatch(
            r"-csearch_path=inlet_candidates_[a-f0-9]{32}", option
        )
        if schema is not None:
            assert option == f"-csearch_path={schema}"
    if schema is not None:
        assert re.fullmatch(r"inlet_(test|candidates)_[a-f0-9]{32}", schema)


def no_effects(engine: Engine) -> None:
    assert not advertising_capabilities.advertising_writes_enabled()
    with engine.connect() as db:
        for name in ZERO:
            assert db.scalar(text(f"SELECT count(*) FROM {name}")) == 0


@contextmanager
def retained_candidate_review_link(
    original: Engine, artifacts: Path
) -> Iterator[tuple[Engine, CandidateReviewLinkIds]]:
    artifacts.mkdir(parents=True)
    root = Path(__file__).resolve().parents[1]
    engine = original
    if original.dialect.name == "sqlite":
        engine = create_engine(f"sqlite:///{artifacts / 'current.sqlite'}")
        event.listen(engine, "connect", lambda db, _: db.execute("PRAGMA foreign_keys=ON"))
        register_models().create_all(engine)
        target = str(engine.url)
    else:
        base = make_url(validate_disposable_url())
        validate_url(engine.url, base)
        with engine.connect() as connection:
            target = str(connection.scalar(text("SELECT current_schema()")))
            validate_url(engine.url, base, target)
            if target.startswith("inlet_candidates_"):
                assert set(
                    connection.scalars(text("SELECT version_num FROM alembic_version"))
                ) == set(ScriptDirectory(str(root / "migrations")).get_heads())
    try:
        before = schema_snapshot(engine)
        bootstrap = fresh_rows(engine)
        no_effects(engine)
        with SourceLifetime.open("candidate_review_link", artifacts) as lifetime:
            extract(root, lifetime.source)
            lifetime.extracted()
            output, log = artifacts / "ids.json", artifacts / "producer.log"
            lifetime.child_started()
            code = run_bounded(
                [
                    sys.executable,
                    str(
                        root
                        / "tests/fixtures/retired_execution/candidate_review_link_seed_driver.py"
                    ),
                    target,
                    str(output),
                ],
                lifetime.source,
                dict(
                    os.environ, INLET_RETIRED_EXECUTION_CHILD=PIN, PYTHONPATH=str(lifetime.source)
                ),
                log,
                180,
            )
            lifetime.after_reaped(code)
        assert schema_snapshot(engine) == before
        unchanged_rows(engine, bootstrap)
        assert code == 0, log.read_text()[-6000:]
        assert output.stat().st_size <= 4096
        raw = json.loads(output.read_text())
        assert type(raw) is dict and set(raw) == set(CandidateReviewLinkIds.__dataclass_fields__)
        assert type(raw["workspace_id"]) is int and raw["workspace_id"] > 0
        assert type(raw["provider_posts"]) is int and raw["provider_posts"] == 0
        for key in set(raw) - {"workspace_id", "provider_posts"}:
            assert type(raw[key]) is str and re.fullmatch(
                r"[a-f0-9]{64}" if key in DIGESTS else r"[a-f0-9]{32}", raw[key]
            )
        ids = CandidateReviewLinkIds(**raw)
        with Session(engine) as db:
            link = db.get(CandidateReviewLink, ids.review_id)
            review = db.get(ProviderExecutionReview, ids.review_id)
            result = db.get(CandidateResult, ids.result_id)
            job = db.get(CandidateJob, ids.job_id)
            assert link and review and result and job
            assert (
                link.workspace_id
                == review.workspace_id
                == result.workspace_id
                == job.workspace_id
                == ids.workspace_id
            )
            assert link.actor_id == review.actor == job.actor_id == ids.actor_id
            assert job.state == "completed" and result.job_id == job.id
            assert (
                link.candidate_result_id == result.id
                and link.candidate_workspace_id == ids.workspace_id
            )
            assert (
                result.decision_digest == ids.candidate_digest
                and result.input_digest == ids.input_digest
            )
            assert (
                review.candidate_provenance_required
                and review.digest == ids.review_digest
                and review.plan_digest == ids.plan_digest
            )
            for name in DIGESTS:
                assert getattr(link, name) == getattr(ids, name)
            session = db.get(CustomerSession, link.original_session_digest)
            assert (
                session
                and session.user_id == ids.actor_id
                and job.auth_session_digest == session.digest
            )
        no_effects(engine)
        try:
            yield engine, ids
        finally:
            no_effects(engine)
    finally:
        if engine is not original:
            engine.dispose()
