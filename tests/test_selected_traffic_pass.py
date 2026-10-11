"""Fresh SQL pass reuse, never authority or a cross-pass cache."""

from datetime import UTC, datetime
from typing import Any, cast

import pytest
from app.ads.models import Campaign
from app.campaign_performance.presence_models import MetricPresenceRow
from app.planning_documents import selected_plan_retained as retained
from app.planning_documents import selected_traffic_reader as traffic
from app.planning_documents.selected_inputs import SelectedCaptureSelectorV1
from app.planning_documents.selected_plan_reader import load_selected_plan_graph
from app.planning_documents.selected_traffic import RawRangeTrafficGraphV1
from app.workspaces.models import Workspace
from fastapi import HTTPException
from sqlalchemy import Table, create_engine, delete, event, update
from sqlalchemy.orm import Session

from tests.test_selected_traffic_reader import (
    configured as configured,
)
from tests.test_selected_traffic_reader import (
    customer as customer,
)
from tests.test_selected_traffic_reader import (
    customer_engine as customer_engine,
)
from tests.test_selected_traffic_reader import (
    range_customer as range_customer,
)
from tests.test_selected_traffic_reader import (
    ready,
)
from tests.test_selected_traffic_reader import (
    replicas as replicas,
)


@pytest.mark.parametrize("fault", ["flush", "reentry", "rollback", "nested"])
def test_pass_guard_detects_events_and_detaches(fault: str) -> None:
    engine = create_engine("sqlite://")
    cast(Table, Workspace.__table__).create(engine)
    try:
        with Session(engine) as db:
            db.begin()
            with pytest.raises(HTTPException), traffic._proof_pass_guard(db):
                try:
                    if fault == "flush":
                        db.add(Workspace(slug="x", name="X", client_name="X"))
                        db.flush()
                    elif fault == "reentry":
                        with traffic._proof_pass_guard(db):
                            pass
                    elif fault == "rollback":
                        db.rollback()
                    else:
                        db.begin_nested()
                except HTTPException:
                    db.expunge_all()
            assert traffic._PASS_KEY not in db.info
            db.rollback()
            # No poisoned flush/transaction listeners survive the failed invocation.
            db.add(Workspace(slug="after", name="After", client_name="After"))
            db.commit()
    finally:
        engine.dispose()


def test_actual_pass_preserves_proof_with_two_fresh_selected_reads(
    range_customer: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    contexts, args, _ = ready(range_customer, monkeypatch=monkeypatch)
    selector = SelectedCaptureSelectorV1(
        account_id=range_customer.aid, capture_id=args["selected_pin"].capture_id
    )
    with contexts.open() as db:

        def legacy_pass(db: Session, *, account: Any, expected_source: Any, capture_id: str) -> Any:
            # Exact former read sequence: selected graph, then standalone traffic
            # reader independently reloads selected. Compare complete resulting proof.
            pin = load_selected_plan_graph(
                db, account=account, expected_source=expected_source, capture_id=capture_id
            ).pin()
            return pin, traffic.load_raw_range_traffic(
                db, account=account, expected_source=expected_source, selected_pin=pin
            )

        with monkeypatch.context() as legacy:
            legacy.setattr(retained, "_read_selected_traffic_pass", legacy_pass)
            expected = retained.capture_selected_reporting_pin(
                db,
                contexts.principal,
                args["account"],
                args["expected_source"].privacy_revision,
                selector,
                datetime.now(UTC),
            )
        queries: list[str] = []

        def record(
            conn: Any, cursor: Any, statement: str, parameters: Any, context: Any, executemany: Any
        ) -> None:
            if "SELECT" in statement and "FROM selected_reporting_captures" in statement:
                queries.append(statement)

        event.listen(db.connection(), "before_cursor_execute", record)
        calls = 0
        original = load_selected_plan_graph

        def load(*a: Any, **kw: Any) -> Any:
            nonlocal calls
            calls += 1
            return original(*a, **kw)

        monkeypatch.setattr(traffic, "load_selected_plan_graph", load)
        try:
            actual = retained.capture_selected_reporting_pin(
                db,
                contexts.principal,
                args["account"],
                args["expected_source"].privacy_revision,
                selector,
                datetime.now(UTC),
            )
        finally:
            event.remove(db.connection(), "before_cursor_execute", record)
        assert actual == expected
        assert calls == 2
        assert len(queries) == 2
        assert actual.capture_pin == args["selected_pin"]
        assert actual.traffic_pin is not None
        assert traffic._PASS_KEY not in db.info
        event.listen(db.connection(), "before_cursor_execute", record)
        try:
            public = traffic.load_raw_range_traffic(db, **args)
        finally:
            event.remove(db.connection(), "before_cursor_execute", record)
        assert isinstance(public, RawRangeTrafficGraphV1)
        assert public.pin() == actual.traffic_pin
        assert calls == 3 and len(queries) == 3  # Public entry owns a NEW actual SQL read.
        with pytest.raises(HTTPException):
            traffic.load_raw_range_traffic(
                db,
                **{
                    **args,
                    "selected_pin": args["selected_pin"].model_copy(
                        update={"campaign_map_digest": "0" * 64}
                    ),
                },
            )


@pytest.mark.parametrize("fault", ["campaign_after_selected", "corrupt_presence"])
def test_actual_midpass_mutation_cannot_become_gap(
    range_customer: Any, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    contexts, args, _ = ready(range_customer, monkeypatch=monkeypatch)
    original = load_selected_plan_graph
    changed = False

    def load(db: Session, **kw: Any) -> Any:
        nonlocal changed
        result = original(db, **kw)
        if not changed:
            changed = True
            if fault == "campaign_after_selected":
                db.execute(
                    update(Campaign)
                    .where(Campaign.account_id == range_customer.aid)
                    .values(external_campaign_id="999")
                )
            else:
                db.execute(delete(MetricPresenceRow))
        return result

    monkeypatch.setattr(traffic, "load_selected_plan_graph", load)
    with Session(range_customer.engine) as db, db.begin():
        with pytest.raises(HTTPException):
            retained.capture_selected_reporting_pin(
                db,
                contexts.principal,
                args["account"],
                args["expected_source"].privacy_revision,
                SelectedCaptureSelectorV1(
                    account_id=range_customer.aid, capture_id=args["selected_pin"].capture_id
                ),
                datetime.now(UTC),
            )
        assert traffic._PASS_KEY not in db.info
        db.rollback()


def test_pass_rejects_already_failed_transaction() -> None:
    from sqlalchemy.exc import IntegrityError

    engine = create_engine("sqlite://")
    cast(Table, Workspace.__table__).create(engine)
    try:
        with Session(engine) as db:
            db.add(Workspace(slug="duplicate", name="First", client_name="First"))
            db.commit()
            db.add(Workspace(slug="duplicate", name="Second", client_name="Second"))
            with pytest.raises(IntegrityError):
                db.flush()
            with pytest.raises(HTTPException), traffic._proof_pass_guard(db):
                raise AssertionError("inactive root transaction admitted")
            assert traffic._PASS_KEY not in db.info
            db.rollback()
    finally:
        engine.dispose()
