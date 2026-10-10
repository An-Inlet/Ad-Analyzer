"""Genuine candidate-review checkpoints; current code owns privacy and readback."""

import json
import os
import re
import stat
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
from app import advertising_capabilities
from app.customers.models import CustomerSession, CustomerUser
from app.database.models import register_models
from app.database.session import Base
from app.executors.google_optimization import GoogleOptimizationTransport
from app.optimization_candidates.models import CandidateJob, CandidateResult
from app.optimization_candidates.review_models import CandidateReviewLink
from app.publication import customer_intents, optimization
from app.publication.contracts import fingerprint
from app.publication.execution_models import (
    GoogleOriginalCompletion,
    ProviderExecutionApproval,
    ProviderExecutionReceipt,
    ProviderExecutionResponse,
    ProviderExposureReservation,
)
from app.publication.google_completion import read_owned
from app.publication.optimization_contracts import (
    GoogleBudgetSetV1,
    GoogleCurrentState,
    OptimizationContext,
    OptimizationReceipt,
    OptimizationResponse,
)
from app.publication.optimization_execution_contracts import OptimizationClaim, OptimizationRuntime
from app.publication.service import owner
from pydantic import SecretStr
from scripts.inlet_producer_source_lifetime import SourceLifetime
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import Engine, create_engine, event, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from tests.financial_origin_retained_fixture import fresh_rows, schema_snapshot
from tests.google_completion_retained_fixture import owned_sqlite_target
from tests.retired_snapshot import PIN, extract, run_bounded
from tests.test_commerce_measurement import NOW
from tests.test_google_optimization_http import Server


@dataclass(frozen=True)
class FeedbackReviewIds:
    stage: str
    workspace_id: int
    actor_id: str
    session_digest: str
    job_id: str
    result_id: str
    review_id: str
    run_id: str
    attempt_id: str
    fence: str
    reservation_id: str
    review_digest: str
    plan_digest: str
    request_digest: str
    reservation_amount_micros: int
    native_budget_amount_micros: int
    provider_posts: int
    response_digest: str | None
    receipt_id: str | None
    receipt_digest: str | None
    receipt_sequence: int | None
    completion_digest: str | None


def parse_ids(raw: Any, stage: str) -> FeedbackReviewIds:
    assert type(raw) is dict and set(raw) == set(FeedbackReviewIds.__dataclass_fields__)
    assert raw["stage"] == stage and stage in {"claimed_final_context", "completed"}
    nullable = {
        "response_digest",
        "receipt_id",
        "receipt_digest",
        "receipt_sequence",
        "completion_digest",
    }
    integers = {"workspace_id", "reservation_amount_micros", "native_budget_amount_micros"}
    for key, value in raw.items():
        if key == "stage":
            continue
        if key in nullable and stage == "claimed_final_context":
            assert value is None
        elif key == "provider_posts":
            assert type(value) is int and value == (1 if stage == "completed" else 0)
        elif key == "receipt_sequence":
            assert type(value) is int and value == 1
        elif key in integers:
            assert type(value) is int and 0 < value <= 10**15
        else:
            assert type(value) is str and re.fullmatch(
                r"[a-f0-9]{64}" if key.endswith("digest") else r"[a-f0-9]{32}", value
            )
    return FeedbackReviewIds(**raw)


def read_ids(output: Path, stage: str) -> FeedbackReviewIds:
    metadata = output.lstat()
    assert not output.is_symlink() and stat.S_ISREG(metadata.st_mode)
    assert 0 < metadata.st_size <= 8192
    return parse_ids(json.loads(output.read_text()), stage)


def graph(engine: Engine) -> dict[str, list[dict[str, Any]]]:
    assert not advertising_capabilities.advertising_writes_enabled()
    with engine.connect() as db:
        return {
            table.name: [
                dict(row)
                for row in db.execute(select(table).order_by(*table.primary_key.columns)).mappings()
            ]
            for table in Base.metadata.sorted_tables
        }


def source_readback(db: Session, ids: FeedbackReviewIds) -> OptimizationClaim:
    owner(db, ids.workspace_id, ids.actor_id)
    user, session = db.get(CustomerUser, ids.actor_id), db.get(CustomerSession, ids.session_digest)
    assert user and session and session.user_id == user.id
    link = db.get(CandidateReviewLink, ids.review_id)
    result, job = db.get(CandidateResult, ids.result_id), db.get(CandidateJob, ids.job_id)
    assert link and result and job
    assert link.actor_id == job.actor_id == ids.actor_id
    assert link.original_session_digest == job.auth_session_digest == ids.session_digest
    assert link.candidate_result_id == result.id and result.job_id == job.id
    assert link.workspace_id == result.workspace_id == job.workspace_id == ids.workspace_id
    assert link.review_digest == ids.review_digest and link.plan_digest == ids.plan_digest
    assert (
        link.candidate_digest == result.decision_digest and link.input_digest == result.input_digest
    )
    run, review, attempt, request = optimization.evidence_lock(db, ids.workspace_id, ids.attempt_id)
    assert run.id == ids.run_id and run.review_id == ids.review_id
    assert review.digest() == ids.review_digest and review.plan.digest() == ids.plan_digest
    assert attempt.fence == ids.fence and request.digest() == ids.request_digest
    approval = db.scalars(select(ProviderExecutionApproval)).one()
    assert approval.review_id == ids.review_id and approval.actor == ids.actor_id
    assert approval.review_digest == ids.review_digest and approval.plan_digest == ids.plan_digest
    binding = customer_intents.binding(
        db, ids.workspace_id, request.intent.mandate.mandate_id, request.intent.mandate.revision
    )
    assert binding == request.intent.mandate
    hold = db.scalars(select(ProviderExposureReservation)).one()
    assert hold.id == ids.reservation_id == run.reservation_id
    assert hold.ledger_id == binding.ledger_id and hold.state == "held"
    assert hold.amount_micros == ids.reservation_amount_micros
    assert isinstance(request.intent.action, GoogleBudgetSetV1)
    assert isinstance(request.before, GoogleCurrentState)
    assert request.before.native_budget_resource == Server().budget["resourceName"]
    assert ids.native_budget_amount_micros == (
        request.intent.action.amount_micros
        if ids.stage == "completed"
        else request.before.budget_amount_micros
    )
    response = db.scalars(select(ProviderExecutionResponse)).one_or_none()
    receipt = db.scalars(select(ProviderExecutionReceipt)).one_or_none()
    completion = db.scalars(select(GoogleOriginalCompletion)).one_or_none()
    if ids.stage == "claimed_final_context":
        assert response is None and receipt is None and completion is None
    else:
        assert response and receipt and completion
        assert response.attempt_id == receipt.attempt_id == completion.attempt_id == ids.attempt_id
        parsed_response = OptimizationResponse.model_validate(response.response)
        assert parsed_response.request_digest == ids.request_digest
        assert (
            response.digest
            == ids.response_digest
            == fingerprint(
                "inlet.optimization-response.v1", parsed_response.model_dump(mode="json")
            )
        )
        parsed = OptimizationReceipt.model_validate(receipt.receipt)
        optimization.validate_receipt(request, parsed)
        assert parsed.outcome == "verified_target_state"
        assert receipt.id == ids.receipt_id and receipt.sequence == ids.receipt_sequence
        assert (
            receipt.digest
            == ids.receipt_digest
            == fingerprint("inlet.optimization-receipt.v1", parsed.model_dump(mode="json"))
        )
        document = read_owned(db, ids.workspace_id, ids.attempt_id, ids.actor_id, NOW)
        assert document and document.digest() == ids.completion_digest
    return OptimizationClaim(
        workspace_id=ids.workspace_id,
        run_id=ids.run_id,
        attempt_id=ids.attempt_id,
        environment="contract_test",
        request=request,
    )


def read_runtime(
    claim: OptimizationClaim, ids: FeedbackReviewIds
) -> tuple[OptimizationRuntime, Server]:
    server = Server()
    server.budget["amountMicros"] = str(ids.native_budget_amount_micros)
    adapter = GoogleOptimizationTransport(transport=httpx.MockTransport(server))

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("readback cannot qualify financial execution")

    def context(scope: Any) -> OptimizationContext:
        assert scope == claim.request.intent.scope
        assert ids.stage == "completed", "claimed denial must precede context"
        return OptimizationContext(
            scope=scope,
            access_token=SecretStr("offline-token"),
            expires_at=NOW + timedelta(hours=1),
        )

    return OptimizationRuntime(
        environment="contract_test",
        qualification_reader=forbidden,
        exposure_reader=forbidden,
        context=context,
        google=adapter,
    ), server


@contextmanager
def retained_feedback_review(
    original: Engine, artifacts: Path, stage: str
) -> Iterator[tuple[Engine, FeedbackReviewIds]]:
    assert stage in {"claimed_final_context", "completed"}
    assert artifacts.is_absolute() and artifacts.resolve() == artifacts
    assert not artifacts.is_symlink() and all(not p.is_symlink() for p in artifacts.parents)
    artifacts.mkdir(parents=True)
    root = Path(__file__).resolve().parents[1]
    engine = original
    if original.dialect.name == "sqlite":
        database = artifacts / "current.sqlite"
        with database.open("xb"):
            pass
        target = owned_sqlite_target(f"sqlite:///{database}", database)
        engine = create_engine(target)
        event.listen(engine, "connect", lambda db, _: db.execute("PRAGMA foreign_keys=ON"))
        register_models().create_all(engine)
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
        schema = schema_snapshot(engine)
        with SourceLifetime.open("feedback_review_original", artifacts) as lifetime:
            extract(root, lifetime.source)
            lifetime.extracted()
            output, log = artifacts / "ids.json", artifacts / "producer.log"
            lifetime.child_started()
            code = run_bounded(
                [
                    sys.executable,
                    str(root / "tests/fixtures/retired_execution/feedback_review_seed_driver.py"),
                    target,
                    str(output),
                    stage,
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
        assert schema_snapshot(engine) == schema
        ids = read_ids(output, stage)
        with Session(engine) as db:
            source_readback(db, ids)
        try:
            yield engine, ids
        finally:
            assert schema_snapshot(engine) == schema
    finally:
        if engine is not original:
            engine.dispose()


def assert_erased(
    before: dict[str, list[dict[str, Any]]],
    after: dict[str, list[dict[str, Any]]],
    ids: FeedbackReviewIds,
    assessment_id: str,
    dependency_id: str,
) -> None:
    from copy import deepcopy

    expected = deepcopy(before)
    for table, field, value in (
        ("commerce_measurement_publications", "id", dependency_id),
        ("outcome_assessments_v3", "id", assessment_id),
        ("outcome_assessment_v3_evidence", "assessment_id", assessment_id),
        ("optimization_candidate_jobs", "workspace_id", ids.workspace_id),
        ("optimization_candidate_results", "workspace_id", ids.workspace_id),
    ):
        expected[table] = [row for row in expected[table] if row[field] != value]
    for row in expected["optimization_candidate_reviews"]:
        assert row["review_id"] == ids.review_id
        row["candidate_result_id"] = row["candidate_workspace_id"] = None
    for row in expected["workspaces"]:
        if row["id"] == ids.workspace_id:
            row["export_privacy_revision"] += 1
    assert after == expected, [name for name in after if after[name] != expected[name]]


def assert_structural(
    before: dict[str, list[dict[str, Any]]],
    after: dict[str, list[dict[str, Any]]],
    ids: FeedbackReviewIds,
    assessment_id: str,
    dependency_id: str,
) -> None:
    """The existing structural fixture adds exact rows, never delivery evidence."""
    from copy import deepcopy

    expected = deepcopy(before)
    anchor = expected["commerce_measurement_publications"][0]
    now = NOW if anchor["published_at"].tzinfo is not None else NOW.replace(tzinfo=None)
    publication = dict(
        anchor,
        id=dependency_id,
        publication_revision=anchor["publication_revision"] + 1,
        completion_digest="2" * 64,
        manifest_digest="3" * 64,
        manifest={"schema_version": "explicit_historical_dependency_fixture.v1"},
        published_at=now - timedelta(days=1),
    )
    receipt_id = ids.receipt_id
    if ids.stage == "claimed_final_context":
        receipt_id = after["provider_execution_receipts"][0]["id"]
        assert re.fullmatch(r"[a-f0-9]{32}", receipt_id)
        expected["provider_execution_receipts"] = [
            dict(
                id=receipt_id,
                workspace_id=ids.workspace_id,
                attempt_id=ids.attempt_id,
                sequence=1,
                supersedes_id=None,
                digest="1" * 64,
                receipt={},
                projection={},
                observed_at=now,
            )
        ]
    expected["commerce_measurement_publications"].append(publication)
    expected["outcome_assessments_v3"] = [
        dict(
            id=assessment_id,
            workspace_id=ids.workspace_id,
            store_id=anchor["store_id"],
            environment="contract_test",
            attempt_id=ids.attempt_id,
            receipt_id=receipt_id,
            receipt_sequence=1,
            generation=anchor["generation"],
            privacy_epoch=anchor["privacy_epoch"],
            input_digest="4" * 64,
            document_digest="5" * 64,
            document={"explicit_schema_fixture": True, "numeric_value": "123"},
            created_at=now,
        )
    ]
    expected["outcome_assessment_v3_evidence"] = [
        dict(
            assessment_id=assessment_id,
            ordinal=n,
            workspace_id=ids.workspace_id,
            publication_id=pub["id"],
            manifest_digest=pub["manifest_digest"],
            completion_digest=pub["completion_digest"],
        )
        for n, pub in enumerate((anchor, publication))
    ]
    for table in Base.metadata.sorted_tables:
        expected[table.name].sort(
            key=lambda row: tuple(row[c.name] for c in table.primary_key.columns)
        )
    assert after == expected, [name for name in after if after[name] != expected[name]]
