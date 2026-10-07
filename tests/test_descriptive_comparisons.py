"""Actual terminal publications qualify as-of arithmetic, never maturity."""

from collections.abc import Callable
from datetime import datetime, timedelta
from decimal import Decimal, localcontext
from functools import partial
from typing import Any

import pytest
from app.api import customer_descriptive
from app.commerce.evidence import digest
from app.commerce.models import CommerceMeasurementPublication, CommerceStore
from app.commerce.sync import CommerceSyncService
from app.customers.access import CSRF_COOKIE
from app.customers.models import CustomerMembership
from app.goals import service as goals
from app.goals.models import Goal
from app.goals.schemas import ConfirmInput
from app.outcomes import descriptive
from app.outcomes.descriptive_contracts import DescriptiveRequest
from app.settings import Settings
from app.shopify.privacy import process_event
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW, FakeMeasurement, agreement, source
from tests.test_commerce_publications import complete
from tests.test_customer_goals import definition
from tests.test_customer_identity import ORIGIN, FakeProvider, login
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_shopify_sales import SHOP
from tests.test_shopify_sales import configuration as configuration


def at(value: datetime) -> datetime:
    return value


def prepared(db: Session, config: Settings) -> tuple[int, DescriptiveRequest]:
    wid, store, publication = complete(db, config)
    goal = goals.create(db, wid, "fixture-owner", "descriptive-goal", definition(store), NOW)
    preview = goals.preview(db, goal, NOW)
    goals.confirm(
        db,
        goal,
        ConfirmInput(
            expected_revision=1, preview_id=preview.id, idempotency_key="descriptive-confirm"
        ),
        NOW,
        actor_id="fixture-owner",
    )
    db.commit()
    return wid, DescriptiveRequest(
        goal_id=goal.id,
        expected_goal_revision=1,
        publication_id=publication,
        before_start="2026-09-01",
        before_end="2026-09-15",
        after_start="2026-09-15",
        after_end="2026-09-29",
    )


def test_actual_as_of_arithmetic_and_two_reconciliation_stability(
    customer_engine: Engine,
    configuration: Settings,
) -> None:
    with Session(customer_engine) as db:
        wid, body = prepared(db, configuration)
        with localcontext() as context:
            context.prec = 2
            report = descriptive.compare(db, wid, body, lambda: None, lambda: NOW)
        assert report.status == "available_as_of"
        assert report.before.value == Decimal(90_000_000) and report.after.value == 0
        assert report.absolute_difference == -90_000_000 and report.relative_difference == -1
        assert report.maturity == "unqualified" and report.causal_lift is None
        assert report.recommendation_update is None and report.spending_authority == "none"
        assert report.before.coverage.mature_through is None
        assert report.model_dump(mode="json")["absolute_difference"] == "-90000000"
        replay = body.model_copy(update={"prior_publication_id": body.publication_id})
        assert (
            descriptive.compare(db, wid, replay, lambda: None, lambda: NOW).stability.status
            == "unavailable"
        )
        for changed in (False, True):
            later = NOW + timedelta(minutes=60 if not changed else 120)
            client = FakeMeasurement(configuration, [([source(updated=later)], None)])
            if changed:
                client.facts[0]["sales"][0]["totalAmount"]["shopMoney"]["amount"] = "109"
            assert (
                CommerceSyncService(db, configuration, client).page(wid, now=later)["status"]
                == "complete"
            )
            current = db.scalar(
                select(CommerceMeasurementPublication).order_by(
                    CommerceMeasurementPublication.publication_revision.desc()
                )
            )
            assert current
            request = body.model_copy(
                update={"publication_id": current.id, "prior_publication_id": body.publication_id}
            )
            result = descriptive.compare(db, wid, request, lambda: None, partial(at, later))
            assert result.status == "available_as_of"
            assert result.stability.status == (
                "revised_observed" if changed else "unchanged_observed"
            )
            assert result.stability.examined_days == 28
            assert result.maturity == "unqualified"
        assert (
            descriptive.compare(db, wid, body, lambda: None, partial(at, later)).status
            == "insufficient"
        )
        process_event(db, configuration, "orders/delete", SHOP, {"id": 1}, later)
        with pytest.raises(HTTPException) as error:
            descriptive.compare(db, wid, request, lambda: None, partial(at, later))
        assert error.value.status_code == 404


@pytest.mark.parametrize(
    "fault",
    ["stale", "future", "goal_revision", "store_revision", "running", "unequal", "missing", "zero"],
)
def test_incomplete_unknown_or_changed_facts_never_promote(
    customer_engine: Engine,
    configuration: Settings,
    fault: str,
) -> None:
    with Session(customer_engine) as db:
        wid, body = prepared(db, configuration)
        clock = NOW
        if fault == "stale":
            clock = NOW + timedelta(hours=25)
        if fault == "future":
            clock = NOW - timedelta(seconds=1)
        if fault == "goal_revision":
            body = body.model_copy(update={"expected_goal_revision": 2})
        if fault in {"store_revision", "running"}:
            store = db.scalar(select(CommerceStore).where(CommerceStore.workspace_id == wid))
            assert store
            if fault == "store_revision":
                store.revision += 1
            else:
                store.window_end = NOW
            db.commit()
        if fault == "unequal":
            body = body.model_copy(update={"after_end": body.after_end - timedelta(days=1)})
        if fault == "missing":
            body = body.model_copy(update={"before_start": body.before_start - timedelta(days=395)})
        if fault == "zero":
            body = body.model_copy(
                update={
                    "before_start": body.before_start + timedelta(days=10),
                    "before_end": body.before_end - timedelta(days=3),
                    "after_end": body.after_start + timedelta(days=1),
                }
            )
        if fault in {"goal_revision", "missing", "stale"}:
            with pytest.raises((HTTPException, ValueError)):
                descriptive.compare(db, wid, body, lambda: None, lambda: clock)
            return
        result = descriptive.compare(db, wid, body, lambda: None, lambda: clock)
        if fault == "zero":
            assert result.status == "available_as_of" and result.relative_difference is None
            assert "baseline_zero" in result.warnings
        else:
            assert result.status == "insufficient" and result.absolute_difference is None
        assert result.maturity == "unqualified" and result.recommendation_update is None


def test_api_owner_csrf_and_no_persistence(
    customer_engine: Engine,
    configuration: Settings,
    replicas: tuple[TestClient, TestClient, FakeProvider],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    alice, bob, _ = replicas
    assert isinstance(alice.app, FastAPI) and isinstance(bob.app, FastAPI)
    alice.app.include_router(customer_descriptive.router)
    bob.app.include_router(customer_descriptive.router)
    actor = login(alice, "descriptive-owner:1")
    login(bob, "other:1")
    with Session(customer_engine) as db:
        wid, body = prepared(db, configuration)
        db.add(CustomerMembership(user_id=actor, workspace_id=wid, role="owner"))
        db.commit()
    actual = descriptive.compare

    def frozen(
        db: Session, wid: int, body: DescriptiveRequest, authorize: Callable[[], None]
    ) -> Any:
        return actual(db, wid, body, authorize, clock=lambda: NOW)

    monkeypatch.setattr(customer_descriptive, "compare", frozen)
    path = f"/api/customer/v1/workspaces/{wid}/descriptive-comparisons"
    headers = {"Origin": ORIGIN, "X-CSRF-Token": alice.cookies[CSRF_COOKIE]}
    payload = body.model_dump(mode="json")
    assert alice.post(path, json=payload).status_code == 403
    assert (
        bob.post(
            path, json=payload, headers={"Origin": ORIGIN, "X-CSRF-Token": bob.cookies[CSRF_COOKIE]}
        ).status_code
        == 403
    )
    response = alice.post(path, json=payload, headers=headers)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["status"] == "available_as_of"
    assert alice.post(path, json={**payload, "mature": True}, headers=headers).status_code == 422
    with Session(customer_engine) as db:
        goal = db.get(Goal, body.goal_id)
        assert goal and goal.revision == 1
    assert alice.delete("/api/customer/v1/session", headers=headers).status_code == 204
    assert alice.post(path, json=payload, headers=headers).status_code == 401


def test_negative_baseline_and_corrected_source_remain_descriptive(
    customer_engine: Engine,
    configuration: Settings,
) -> None:
    with Session(customer_engine) as db:
        wid, body = prepared(db, configuration)
        later = NOW + timedelta(hours=1)
        client = FakeMeasurement(configuration, [([source(updated=later)], None)])
        client.facts.append(agreement(number=2, gross="198", tax="18", action="RETURN"))
        assert (
            CommerceSyncService(db, configuration, client).page(wid, now=later)["status"]
            == "complete"
        )
        current = db.scalar(
            select(CommerceMeasurementPublication).order_by(
                CommerceMeasurementPublication.publication_revision.desc()
            )
        )
        assert current
        result = descriptive.compare(
            db,
            wid,
            body.model_copy(update={"publication_id": current.id}),
            lambda: None,
            lambda: later,
        )
        assert result.status == "available_as_of"
        assert result.before.value is not None and result.before.value < 0
        assert result.relative_difference is None and "baseline_negative" in result.warnings
        assert result.causal_lift is None and result.maturity == "unqualified"


def test_waiting_reader_cannot_escape_erasure_or_changed_goal(
    customer_engine: Engine,
    configuration: Settings,
) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event, current_thread

    from app.commerce.evidence import lock_workspace
    from sqlalchemy import event

    if customer_engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL row-lock concurrency proof")
    with Session(customer_engine) as db:
        wid, body = prepared(db, configuration)
    waiting = Event()

    def before_query(_conn: Any, _cursor: Any, statement: str, *_args: Any) -> None:
        if (
            current_thread().name.startswith("descriptive-replica")
            and "workspaces" in statement
            and "FOR UPDATE" in statement
        ):
            waiting.set()

    def read_replica() -> int:
        with Session(customer_engine) as db:
            # Deliberately prime identity map before the owner transaction commits.
            db.get(Goal, body.goal_id)
            try:
                descriptive.compare(db, wid, body, lambda: None, lambda: NOW)
            except HTTPException as error:
                return error.status_code
            return 200

    event.listen(customer_engine, "before_cursor_execute", before_query)
    try:
        for erase in (False, True):
            waiting.clear()
            with Session(customer_engine) as writer:
                lock_workspace(writer, wid)
                with ThreadPoolExecutor(
                    max_workers=1, thread_name_prefix="descriptive-replica"
                ) as pool:
                    pending = pool.submit(read_replica)
                    try:
                        assert waiting.wait(5) and not pending.done()
                        if erase:
                            process_event(
                                writer, configuration, "orders/delete", SHOP, {"id": 1}, NOW
                            )
                        else:
                            goal = writer.get(Goal, body.goal_id)
                            assert goal
                            goal.revision += 1
                        writer.commit()
                    finally:
                        writer.rollback()
                    assert pending.result(timeout=10) == (404 if erase else 409)
    finally:
        event.remove(customer_engine, "before_cursor_execute", before_query)


@pytest.mark.parametrize("fault", ["missing_day", "currency", "rehashed_binding", "foreign_prior"])
def test_coverage_basis_and_prior_ownership_fail_closed(
    customer_engine: Engine,
    configuration: Settings,
    fault: str,
) -> None:
    from copy import deepcopy

    with Session(customer_engine) as db:
        wid, body = prepared(db, configuration)
        row = db.get(CommerceMeasurementPublication, body.publication_id)
        assert row
        if fault == "foreign_prior":
            _, _, other = complete(db, configuration, slug="other")
            body = body.model_copy(update={"prior_publication_id": other})
        elif fault == "currency":
            store = db.get(CommerceStore, row.store_id)
            assert store
            store.currency = "EUR"
        else:
            document = deepcopy(row.manifest)
            if fault == "missing_day":
                document["partitions"] = [
                    p for p in document["partitions"] if p["day"] != "2026-09-10"
                ]
            else:
                document["workspace_id"] = wid + 1
            row.manifest = document
            row.manifest_digest = digest(document)
        db.commit()
        if fault in {"foreign_prior", "rehashed_binding"}:
            with pytest.raises(HTTPException) as rejected:
                descriptive.compare(db, wid, body, lambda: None, lambda: NOW)
            assert rejected.value.status_code == (404 if fault == "foreign_prior" else 409)
        else:
            result = descriptive.compare(db, wid, body, lambda: None, lambda: NOW)
            assert result.status == "insufficient" and result.absolute_difference is None
