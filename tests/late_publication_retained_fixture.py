"""One original local late receipt; current closure retains its original reservation."""

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
from typing import Any

from app import advertising_capabilities
from app.database.models import register_models
from app.database.session import Base
from app.publication import service as publication
from app.publication.contracts import BoundRequest, PublishReceipt, fingerprint
from app.publication.models import PublicationReceiptRecord, PublicationStepRecord
from app.shopify.security import utc
from scripts.inlet_producer_source_lifetime import SourceLifetime
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import Engine, create_engine, event, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from tests.financial_origin_retained_fixture import fresh_rows, schema_snapshot
from tests.retired_snapshot import PIN, extract, run_bounded
from tests.test_commerce_measurement import NOW


@dataclass(frozen=True)
class LatePublicationIds:
    workspace_id: int
    actor_id: str
    plan_id: str
    mandate_id: str
    mandate_revision: int
    action_id: str
    first_receipt_id: str
    fence: str
    step_id: str
    plan_digest: str
    request_digest: str
    late_receipt_digest: str
    fixture_calls: int
    late_receipt: PublishReceipt


def load_source(db: Session, ids: LatePublicationIds) -> BoundRequest:
    publication.owner(db, ids.workspace_id, ids.actor_id)
    row, plan, mandate, action = publication.locked(db, ids.workspace_id, ids.plan_id)
    assert row.digest == plan.digest() == ids.plan_digest and row.approved_by == ids.actor_id
    assert mandate.id == ids.mandate_id and mandate.revision == ids.mandate_revision
    assert (
        action.id == ids.action_id == row.action_id
        and mandate.reserved_micros == plan.exposure_micros
    )
    step = db.get(PublicationStepRecord, (ids.plan_id, ids.step_id))
    assert step is not None and step.request is not None and step.attempt == 2
    assert step.state == "dispatching" and step.receipt is None
    bound = BoundRequest.model_validate(step.request)
    assert (
        bound.scope == plan.scope
        and bound.plan_id == ids.plan_id
        and bound.plan_digest == row.digest
    )
    assert bound.step in plan.steps and bound.step.step_id == ids.step_id
    assert bound.fence == step.fence == ids.fence and bound.digest() == ids.request_digest
    old = db.scalars(select(PublicationReceiptRecord)).one()
    assert old.id == ids.first_receipt_id and old.workspace_id == ids.workspace_id
    first = BoundRequest.model_validate(old.request)
    prior = PublishReceipt.model_validate(old.receipt)
    assert first is not None and bound is not None
    assert (
        first.scope == bound.scope and first.step == bound.step and first.plan_id == bound.plan_id
    )
    assert first.fence != bound.fence and first.digest() != bound.digest()
    assert prior.scope == first.scope and prior.plan_id == ids.plan_id
    assert prior.step_id == ids.step_id and prior.fence == first.fence
    assert prior.request_digest == first.digest() and prior.outcome == "verified_no_effect"
    assert old.digest == fingerprint("inlet.publication-receipt.v1", prior.model_dump(mode="json"))
    receipt = ids.late_receipt
    assert (
        receipt.scope == bound.scope
        and receipt.plan_id == ids.plan_id
        and receipt.step_id == ids.step_id
    )
    assert receipt.fence == bound.fence and receipt.request_digest == bound.digest()
    assert receipt.observed_at == bound.dispatched_at == NOW
    assert receipt.outcome == "verified_effect" and receipt.status == "PAUSED"
    assert (
        fingerprint("inlet.publication-receipt.v1", receipt.model_dump(mode="json"))
        == ids.late_receipt_digest
    )
    return bound


def graph(engine: Engine) -> dict[str, list[dict[str, Any]]]:
    assert not advertising_capabilities.advertising_writes_enabled()
    names = {
        "spending_mandates",
        "spending_mandate_revisions",
        "mandate_audits",
        "mandate_actions",
        "publication_plans",
        "publication_steps",
        "publication_receipts",
    }
    with engine.connect() as connection:
        return {
            table.name: [
                dict(row)
                for row in connection.execute(
                    select(table).order_by(*table.primary_key.columns)
                ).mappings()
            ]
            for table in Base.metadata.sorted_tables
            if table.name in names or table.name.startswith("provider_")
        }


def check_delta(
    before: dict[str, list[dict[str, Any]]],
    after: dict[str, list[dict[str, Any]]],
    ids: LatePublicationIds,
    bound: BoundRequest,
) -> None:
    expected = deepcopy(before)
    for row in expected["spending_mandates"]:
        assert row["workspace_id"] == ids.workspace_id
        row["paused"] = True
    for row in expected["mandate_actions"]:
        assert row["workspace_id"] == ids.workspace_id
        row["cancel_requested"] = True
    prior = expected["publication_receipts"]
    assert len(prior) == 1 and prior[0]["id"] == ids.first_receipt_id
    additions = [row for row in after["publication_receipts"] if row["id"] != ids.first_receipt_id]
    assert len(additions) == 1
    added = additions[0]
    assert type(added["id"]) is str and re.fullmatch(r"[a-f0-9]{32}", added["id"])
    assert utc(added["recorded_at"]) == NOW
    desired = dict(
        id=added["id"],
        plan_id=ids.plan_id,
        step_id=ids.step_id,
        workspace_id=ids.workspace_id,
        digest=ids.late_receipt_digest,
        request=bound.model_dump(mode="json"),
        receipt=ids.late_receipt.model_dump(mode="json"),
        recorded_at=added["recorded_at"],
    )
    assert added == desired
    expected["publication_receipts"] = sorted([*prior, desired], key=lambda row: row["id"])
    assert after == expected


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
def retained_late_publication(
    original: Engine, artifacts: Path
) -> Iterator[tuple[Engine, LatePublicationIds]]:
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
        with SourceLifetime.open("late_publication", artifacts) as lifetime:
            extract(root, lifetime.source)
            lifetime.extracted()
            output, log = artifacts / "ids.json", artifacts / "producer.log"
            lifetime.child_started()
            code = run_bounded(
                [
                    sys.executable,
                    str(root / "tests/fixtures/retired_execution/late_publication_seed_driver.py"),
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
        assert code == 0, log.read_text()[-6000:]
        assert schema_snapshot(engine) == schema and output.stat().st_size <= 16384
        raw = json.loads(output.read_text())
        assert type(raw) is dict and set(raw) == set(LatePublicationIds.__dataclass_fields__)
        for key, value in raw.items():
            if key == "late_receipt":
                assert type(value) is dict
            elif key == "step_id":
                assert value == "budget"
            elif key in {"workspace_id", "mandate_revision", "fixture_calls"}:
                assert type(value) is int and value > 0
            else:
                assert type(value) is str and re.fullmatch(
                    r"[a-f0-9]{64}" if key.endswith("digest") else r"[a-f0-9]{32}", value
                )
        raw["late_receipt"] = PublishReceipt.model_validate(raw["late_receipt"])
        ids = LatePublicationIds(**raw)
        assert ids.fixture_calls == 1
        with Session(engine) as db:
            bound = load_source(db, ids)
        before = graph(engine)
        assert all(not rows for name, rows in before.items() if name.startswith("provider_"))
        try:
            yield engine, ids
        finally:
            check_delta(before, graph(engine), ids, bound)
    finally:
        if engine is not original:
            engine.dispose()
