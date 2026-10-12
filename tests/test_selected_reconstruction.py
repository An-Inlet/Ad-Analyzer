"""Fresh SQL dependency equality, detached pure replay and unchanged failure positions."""

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta
from types import FrameType
from typing import Any, cast

import pytest
from app.ads.models import Campaign
from app.campaign_performance import selected_reconstruction as replay
from app.campaign_performance import selected_storage as storage
from app.campaign_performance.models import PerformanceCompletion
from app.campaign_performance.selected_contracts import SelectedCaptureV1
from app.campaign_performance.selected_models import (
    EventSelectionRow,
    SelectedCaptureRow,
    SelectedFactRow,
)
from sqlalchemy import Table, delete, event, insert, select
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_google_customer_connections import configured as configured
from tests.test_selected_capture_api import prepare
from tests.test_selected_customer_api import CustomerFixture
from tests.test_selected_customer_api import customer as customer
from tests.test_selected_scope_query_contracts import select_counts


@contextmanager
def decode_calls() -> Iterator[list[int]]:
    counts = [0]
    original = sys.getprofile()
    assert original is None
    code = storage._reconstruct_capture.__code__

    def observe(frame: FrameType, event: str, arg: Any) -> None:
        if event == "call" and frame.f_code is code:
            counts[0] += 1

    sys.setprofile(observe)
    try:
        yield counts
    finally:
        sys.setprofile(original)


def acquired(f: CustomerFixture, value: str | None = "10") -> str:
    body = prepare(f, value)
    response = f.post("/captures", body)
    assert response.status_code == 200, response.text
    return str(body["request_id"])


@pytest.mark.parametrize("value", [None, "10"])
def test_replay_reads_all_dependencies_and_detaches_every_result(
    customer: CustomerFixture, value: str | None
) -> None:
    f = customer
    capture_id = acquired(f, value)
    with (
        Session(f.engine) as db,
        db.begin(),
        replay.generation_reconstruction(db),
        decode_calls() as decodes,
        select_counts(f.engine) as queries,
    ):
        first = storage.historical_capture(db, f.wid, f.aid, capture_id)
        original = first.model_dump_json()
        object.__setattr__(first.request.aggregate.scope, "privacy_revision", 999)
        for _ in range(2):
            current = storage.historical_capture(db, f.wid, f.aid, capture_id)
            assert current.model_dump_json() == original
            object.__setattr__(current.request.aggregate.scope, "privacy_revision", 888)
        assert queries[0] == 15
        assert decodes[0] == 1
    # No cross-invocation success or object retention.
    assert replay._ACTIVE.get() is None
    with (
        Session(f.engine) as db,
        db.begin(),
        replay.generation_reconstruction(db),
        decode_calls() as decodes,
    ):
        assert (
            storage.historical_capture(db, f.wid, f.aid, capture_id).model_dump_json() == original
        )
        assert decodes[0] == 1


@pytest.mark.parametrize("change", ["header", "fact", "campaign", "selection", "completion"])
def test_faulted_loaded_rows_preserve_uncached_error_and_sql_position(
    customer: CustomerFixture,
    change: str,
) -> None:
    """Fault seam after SQL loading; never bypass immutable-row database triggers."""
    f = customer
    capture_id = acquired(f)
    model, field, bad = {
        "header": (SelectedCaptureRow, "payload_digest", "0" * 64),
        "fact": (SelectedFactRow, "payload_digest", "0" * 64),
        "campaign": (Campaign, "external_campaign_id", "2"),
        "selection": (EventSelectionRow, "canonical_json", "{}"),
        "completion": (PerformanceCompletion, "manifest_digest", "0" * 64),
    }[change]

    def fault(target: Any, *_args: Any) -> None:
        target.__dict__[field] = bad

    with Session(f.engine) as db, db.begin(), replay.generation_reconstruction(db):
        storage.historical_capture(db, f.wid, f.aid, capture_id)
        event.listen(model, "load", fault)
        event.listen(model, "refresh", fault)
        try:
            with select_counts(f.engine) as queries:
                with pytest.raises(ValueError) as cached_error:
                    storage.historical_capture(db, f.wid, f.aid, capture_id)
                cached_queries = queries[0]
            # Clear replay without touching the simulated fresh row values.
            active = replay._ACTIVE.get()
            assert active is not None
            active.close()
            with (
                select_counts(f.engine) as queries,
                pytest.raises(type(cached_error.value)) as ordinary_error,
            ):
                storage.historical_capture(db, f.wid, f.aid, capture_id)
            assert str(ordinary_error.value) == str(cached_error.value)
            assert queries[0] == cached_queries
        finally:
            event.remove(model, "load", fault)
            event.remove(model, "refresh", fault)


@pytest.mark.parametrize("change", ["delete", "insert"])
def test_real_fact_membership_changes_are_never_cached(
    customer: CustomerFixture,
    change: str,
) -> None:
    f = customer
    capture_id = acquired(f)
    with Session(f.engine) as db, db.begin(), replay.generation_reconstruction(db):
        value = storage.historical_capture(db, f.wid, f.aid, capture_id)
        if change == "delete":
            db.execute(
                delete(cast(Table, SelectedFactRow.__table__)).where(
                    SelectedFactRow.capture_id == capture_id
                )
            )
        else:
            extra = value.facts[0].model_copy(
                update={"metric_date": value.facts[0].metric_date + timedelta(days=1)}
            )
            db.execute(
                insert(cast(Table, SelectedFactRow.__table__)).values(
                    **storage.fact_values(extra, f.wid, f.aid)
                )
            )
        with pytest.raises(ValueError):
            storage.historical_capture(db, f.wid, f.aid, capture_id)
        db.rollback()


def test_replaced_transaction_disables_reuse(customer: CustomerFixture) -> None:
    f = customer
    capture_id = acquired(f)
    with Session(f.engine) as db:
        db.begin()
        with replay.generation_reconstruction(db), decode_calls() as decodes:
            first = storage.historical_capture(db, f.wid, f.aid, capture_id)
            db.rollback()
            db.begin()
            second = storage.historical_capture(db, f.wid, f.aid, capture_id)
            assert first == second
            assert decodes[0] == 2
        db.rollback()


def test_capacity_falls_back_without_product_rejection(
    customer: CustomerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    f = customer
    capture_id = acquired(f)
    monkeypatch.setattr(replay, "_MAX_FACTS", 0)
    with Session(f.engine) as db, db.begin(), replay.generation_reconstruction(db):
        with decode_calls() as decodes, select_counts(f.engine) as queries:
            first = storage.historical_capture(db, f.wid, f.aid, capture_id)
            second = storage.historical_capture(db, f.wid, f.aid, capture_id)
        assert first == second
        assert decodes[0] == 2 and queries[0] == 10


@pytest.mark.parametrize("change", ["helper", "model_method"])
def test_changed_decoder_behavior_does_not_reuse_old_success(
    customer: CustomerFixture, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    f = customer
    capture_id = acquired(f)
    with Session(f.engine) as db, db.begin(), replay.generation_reconstruction(db):
        storage.historical_capture(db, f.wid, f.aid, capture_id)

        def fail(*args: Any, **kwargs: Any) -> Any:
            raise ValueError("changed pure behavior")

        if change == "helper":
            monkeypatch.setattr(storage, "capture_values", fail)
        else:
            monkeypatch.setattr(SelectedCaptureV1, "model_validate_json", fail)
        with pytest.raises(ValueError, match="changed pure behavior"):
            storage.historical_capture(db, f.wid, f.aid, capture_id)


def test_exception_clears_private_replay(customer: CustomerFixture) -> None:
    f = customer
    capture_id = acquired(f)
    original = RuntimeError("body failure")
    with Session(f.engine) as db, db.begin():
        with pytest.raises(RuntimeError) as caught, replay.generation_reconstruction(db):
            storage.historical_capture(db, f.wid, f.aid, capture_id)
            active = replay._ACTIVE.get()
            assert active is not None and active.entries
            raise original
        assert caught.value is original
        assert active is not None
        assert active.closed and not active.entries and replay._ACTIVE.get() is None
        assert db.scalar(select(SelectedCaptureRow.id).where(SelectedCaptureRow.id == capture_id))


def test_scope_entry_does_not_acquire_connection(customer: CustomerFixture) -> None:
    f = customer
    calls = []

    def began(*_args: Any) -> None:
        calls.append(True)

    event.listen(f.engine, "begin", began)
    try:
        with Session(f.engine) as db, db.begin(), replay.generation_reconstruction(db):
            assert calls == []
        assert calls == []
    finally:
        event.remove(f.engine, "begin", began)


def test_committed_independent_erasure_defeats_replay(customer: CustomerFixture) -> None:
    f = customer
    if f.engine.dialect.name != "postgresql":
        pytest.skip("independent connections require PostgreSQL fixture")
    capture_id = acquired(f)
    with Session(f.engine) as db, db.begin(), replay.generation_reconstruction(db):
        storage.historical_capture(db, f.wid, f.aid, capture_id)
        with f.engine.begin() as writer:
            writer.execute(
                delete(cast(Table, SelectedFactRow.__table__)).where(
                    SelectedFactRow.capture_id == capture_id
                )
            )
        with pytest.raises(ValueError):
            storage.historical_capture(db, f.wid, f.aid, capture_id)


@pytest.mark.parametrize("target", ["model_field", "orm_field"])
def test_new_field_descriptors_fall_back_after_warm_cache(
    customer: CustomerFixture, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    f = customer
    capture_id = acquired(f)
    with Session(f.engine) as db, db.begin(), replay.generation_reconstruction(db):
        storage.historical_capture(db, f.wid, f.aid, capture_id)

        def failed(_self: Any) -> Any:
            raise ValueError("changed field descriptor")

        model, field = (
            (SelectedCaptureV1, "request")
            if target == "model_field"
            else (SelectedFactRow, "canonical_json")
        )
        monkeypatch.setattr(model, field, property(failed), raising=False)
        with pytest.raises(ValueError, match="changed field descriptor"):
            storage.historical_capture(db, f.wid, f.aid, capture_id)


def test_promotion_rechecks_capacity_after_dependency_callbacks(
    customer: CustomerFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    f = customer
    capture_id = acquired(f)

    def lower_capacity(*_args: Any) -> None:
        monkeypatch.setattr(replay, "_MAX_ENTRIES", 0)

    with Session(f.engine) as db, db.begin(), replay.generation_reconstruction(db):
        event.listen(PerformanceCompletion, "load", lower_capacity)
        try:
            storage.historical_capture(db, f.wid, f.aid, capture_id)
            active = replay._ACTIVE.get()
            assert active is not None and not active.entries and active.units == 0
        finally:
            event.remove(PerformanceCompletion, "load", lower_capacity)


def test_failed_dependency_never_promotes(customer: CustomerFixture) -> None:
    f = customer
    capture_id = acquired(f)

    def fault(row: Any, *_args: Any) -> None:
        row.__dict__["manifest_digest"] = "0" * 64

    with Session(f.engine) as db, db.begin(), replay.generation_reconstruction(db):
        event.listen(PerformanceCompletion, "load", fault)
        try:
            with pytest.raises(ValueError):
                storage.historical_capture(db, f.wid, f.aid, capture_id)
            active = replay._ACTIVE.get()
            assert active is not None and not active.entries and active.units == 0
        finally:
            event.remove(PerformanceCompletion, "load", fault)
