"""Closed original configured Google attempt; current APIs never receive old authority."""

import os
import re
import stat
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, Any, Literal

from app import advertising_capabilities
from app.database.models import register_models
from app.database.session import Base
from app.google_connections.models import GoogleCustomerConnection
from app.publication import coordinator, customer_intents
from app.publication.contracts import fingerprint
from app.publication.execution_models import (
    GoogleOriginalCompletion,
    ProviderExecutionAttempt,
    ProviderExecutionReceipt,
    ProviderExecutionResponse,
    ProviderExposureReservation,
)
from app.publication.google_execution_completion_contracts import (
    GoogleExecutionCompletionV2,
    parse_completion,
)
from app.publication.provider_contracts import BoundProviderRequest
from app.publication.service import owner
from pydantic import BaseModel, ConfigDict, Field, model_validator
from scripts.inlet_producer_source_lifetime import SourceLifetime
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import Engine, create_engine, event, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from tests.financial_origin_retained_fixture import fresh_rows, schema_snapshot
from tests.retired_snapshot import PIN, extract, run_bounded

ID = Annotated[str, Field(pattern=r"^[a-f0-9]{32}$")]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Positive = Annotated[int, Field(gt=0)]
Mode = Literal["daily_completed", "daily_unknown"]


class AttemptPin(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    step_id: Literal["budget"]
    attempt_id: ID
    fence: ID
    request_digest: Digest
    response_digest: Digest
    latest_receipt_id: ID
    latest_receipt_digest: Digest
    latest_receipt_sequence: Positive
    completion_digest: Digest | None
    resource_name: Annotated[str, Field(min_length=1, max_length=128)] | None


class GoogleCreatedIds(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    mode: Mode
    workspace_id: Positive
    actor_id: ID
    account_id: Positive
    run_id: ID
    review_id: ID
    mandate_id: ID
    mandate_revision: Positive
    consent_id: ID
    ledger_id: ID
    reservation_id: ID
    native_connection_id: ID
    policy_digest: Digest
    review_digest: Digest
    plan_digest: Digest
    reservation_amount_micros: Positive
    provider_posts: Annotated[int, Field(strict=True, ge=1, le=1)]
    attempts: Annotated[list[AttemptPin], Field(min_length=1, max_length=1)]

    @model_validator(mode="after")
    def completion_shape(self) -> "GoogleCreatedIds":
        pin = self.attempts[0]
        assert type(self.provider_posts) is int
        assert (pin.completion_digest is None) == (self.mode == "daily_unknown")
        assert (pin.resource_name is None) == (self.mode == "daily_unknown")
        return self


def load_source(db: Session, ids: GoogleCreatedIds) -> None:
    owner(db, ids.workspace_id, ids.actor_id)
    pin = ids.attempts[0]
    attempt = db.scalars(select(ProviderExecutionAttempt)).one()
    assert attempt.id == pin.attempt_id and attempt.run_id == ids.run_id
    assert attempt.step_id == pin.step_id
    run, document, attempt, request = coordinator.evidence_lock(
        db, ids.workspace_id, pin.attempt_id
    )
    assert run.review_id == ids.review_id and run.reservation_id == ids.reservation_id
    assert document.digest() == ids.review_digest and document.plan.digest() == ids.plan_digest
    binding = customer_intents.binding(db, ids.workspace_id, ids.mandate_id, ids.mandate_revision)
    assert binding == document.mandate
    assert binding.consent_id == ids.consent_id and binding.ledger_id == ids.ledger_id
    assert binding.policy_digest == ids.policy_digest
    assert request.scope.account.account_id == ids.account_id
    native = db.get(GoogleCustomerConnection, ids.native_connection_id)
    assert (
        native and native.workspace_id == ids.workspace_id and native.account_id == ids.account_id
    )
    assert request.scope.connection_version.split(":")[1] == native.id
    assert attempt.fence == pin.fence and request.digest() == pin.request_digest
    response = db.scalars(select(ProviderExecutionResponse)).one()
    assert response.workspace_id == ids.workspace_id
    assert response.attempt_id == attempt.id and response.digest == pin.response_digest
    assert fingerprint("inlet.provider-response.v1", response.response) == pin.response_digest
    receipt = db.scalars(select(ProviderExecutionReceipt)).one()
    assert receipt.workspace_id == ids.workspace_id
    assert receipt.attempt_id == attempt.id and receipt.id == pin.latest_receipt_id
    assert (
        receipt.sequence == pin.latest_receipt_sequence
        and receipt.digest == pin.latest_receipt_digest
    )
    assert fingerprint("inlet.provider-receipt.v1", receipt.receipt) == pin.latest_receipt_digest
    normalized = coordinator.read_owned_outcome_receipt(
        db, ids.workspace_id, attempt.id, ids.actor_id
    )
    assert normalized and normalized.resource_name == pin.resource_name
    assert normalized.outcome == ("unknown" if ids.mode == "daily_unknown" else "verified_effect")
    completion = db.get(GoogleOriginalCompletion, attempt.id)
    if ids.mode == "daily_unknown":
        assert completion is None
    else:
        assert completion and completion.digest == pin.completion_digest
        parsed = parse_completion(completion.document)
        assert isinstance(parsed, GoogleExecutionCompletionV2)
        assert isinstance(request, BoundProviderRequest)
        parsed.bind(request, request.dispatched_at)
        assert parsed.digest() == pin.completion_digest
    hold = db.scalars(select(ProviderExposureReservation)).one()
    assert (
        hold.id == ids.reservation_id and hold.ledger_id == ids.ledger_id and hold.state == "held"
    )
    assert hold.amount_micros == ids.reservation_amount_micros


def graph(engine: Engine) -> dict[str, list[dict[str, Any]]]:
    assert not advertising_capabilities.advertising_writes_enabled()
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
            or table.name
            in {
                "google_original_completions",
                "mandate_actions",
                "optimization_mandate_preparations",
            }
        }


def owned_sqlite_target(target: str, expected: Path) -> str:
    """Reject aliases and non-owned URL shapes before any database access."""
    url = make_url(target)
    assert url.drivername == "sqlite" and not url.query
    assert url.username is None and url.password is None and url.host is None and url.port is None
    assert url.database is not None and url.database != ":memory:"
    path = Path(url.database)
    assert path.is_absolute() and expected.is_absolute() and path == expected
    assert not path.is_symlink() and all(not parent.is_symlink() for parent in path.parents)
    assert path.resolve() == path and stat.S_ISREG(path.lstat().st_mode)
    return str(url)


@contextmanager
def retained_google_created(
    original: Engine, artifacts: Path, mode: Mode
) -> Iterator[tuple[Engine, GoogleCreatedIds]]:
    assert mode in {"daily_completed", "daily_unknown"}
    assert artifacts.is_absolute() and artifacts.resolve() == artifacts
    assert not artifacts.is_symlink()
    assert all(not parent.is_symlink() for parent in artifacts.parents)
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
        schema = schema_snapshot(engine)
        with SourceLifetime.open("google_created", artifacts) as lifetime:
            extract(root, lifetime.source)
            lifetime.extracted()
            output, log = artifacts / "ids.json", artifacts / "producer.log"
            lifetime.child_started()
            code = run_bounded(
                [
                    sys.executable,
                    str(root / "tests/fixtures/retired_execution/google_created_seed_driver.py"),
                    target,
                    str(output),
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
        assert schema_snapshot(engine) == schema and output.stat().st_size <= 8192
        ids = GoogleCreatedIds.model_validate_json(output.read_bytes())
        assert ids.mode == mode
        with Session(engine) as db:
            load_source(db, ids)
        before = graph(engine)
        try:
            yield engine, ids
        finally:
            assert graph(engine) == before
    finally:
        if engine is not original:
            engine.dispose()
