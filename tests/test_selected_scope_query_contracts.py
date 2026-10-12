"""Baseline query counts for actual retained capture and fresh scope observations."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from app.campaign_performance.selected_storage import current_scope, historical_capture
from sqlalchemy import Engine, event
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_google_customer_connections import configured as configured
from tests.test_selected_capture_api import prepare
from tests.test_selected_customer_api import CustomerFixture
from tests.test_selected_customer_api import customer as customer


@contextmanager
def select_counts(engine: Engine) -> Iterator[list[int]]:
    """Count executions only; never retain statement text, bindings or returned data."""
    counts = [0]

    def counted(
        connection: Any,
        cursor: Any,
        statement: Any,
        parameters: Any,
        context: Any,
        executemany: Any,
    ) -> None:
        assert context.compiled is not None and context.compiled.statement.is_select
        counts[0] += 1

    event.listen(engine, "before_cursor_execute", counted)
    try:
        yield counts
    finally:
        event.remove(engine, "before_cursor_execute", counted)


@pytest.mark.parametrize("value", [None, "10"])
def test_retained_capture_batches_and_scope_requeries(
    customer: CustomerFixture, value: str | None
) -> None:
    """Zero/one-fact baseline; no assertion of maximum-cardinality or latency proof."""
    f = customer
    body = prepare(f, value)
    response = f.post("/captures", body)
    assert response.status_code == 200, response.text
    with Session(f.engine) as db, db.no_autoflush:
        expected = historical_capture(db, f.wid, f.aid, body["request_id"])
        assert len(expected.facts) == (0 if value is None else 1)
        original = expected.model_dump_json()
        root = db.get_transaction()
        assert root is not None
        with select_counts(f.engine) as queries:
            for repeat in range(1, 4):
                actual = historical_capture(db, f.wid, f.aid, body["request_id"])
                assert actual.model_dump_json() == original
                assert queries[0] == 5 * repeat
        with select_counts(f.engine) as queries:
            for repeat in range(1, 4):
                current_scope(db, expected.request.aggregate.scope)
                assert queries[0] == 7 * repeat
        assert db.get_transaction() is root and root.is_active
        assert not db.new and not db.dirty and not db.deleted
        assert expected.model_dump_json() == original
