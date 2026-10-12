"""Real configured V6 API: fresh authority between provisional collection stages."""

import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from app.campaign_review.models import MediaObject
from app.customers.models import CustomerMembership, CustomerSession, CustomerUser
from app.goals.models import Goal
from app.google_connections.models import GoogleCustomerConnection
from app.planning_documents import creative_paired_reader as reader
from app.planning_documents.read_context import PlanningReadContexts
from app.workspaces.models import Workspace
from sqlalchemy import Engine, update
from sqlalchemy.orm import Session

from tests.creative_q07_fixture import planning_snapshot
from tests.planning_release_evidence import record_intentional_delay
from tests.test_creative_common_basis import financial_counts
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_owner_review_runtime_api import generation
from tests.test_owner_runtime_composition import actual_owner as actual_owner
from tests.test_prepared_generation_runtime import create, trace_preparation
from tests.test_shopify_sales import configuration as configuration

FAULTS = (
    "none",
    "expired_stage",
    "session",
    "provider",
    "identity",
    "workspace",
    "membership",
    "privacy",
    "connection",
    "goal",
    "media",
    "exception",
)


@pytest.mark.parametrize("fault", FAULTS)
def test_original_authority_and_sources_between_closed_stages(
    actual_owner: Any,
    customer_engine: Engine,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
) -> None:
    client, url = create(actual_owner)
    before, effects = planning_snapshot(customer_engine), financial_counts(customer_engine)
    fixture, _, calls, _, _, _ = actual_owner
    provider_counts = len(calls), len(fixture.calls)
    preparations = trace_preparation(monkeypatch)
    original_open = PlanningReadContexts.open
    original_reporting = vars(reader)["recheck_selected_paired_sources"]
    original_creative = vars(reader)["recheck_collected_creative"]
    stages: list[tuple[str, Session, Any]] = []
    closed: list[str] = []
    contexts: list[PlanningReadContexts] = []
    changed: list[str] = []
    unexpected = RuntimeError("controlled between-stage failure")

    def reporting(db: Session, *args: Any, **kwargs: Any) -> None:
        original_reporting(db, *args, **kwargs)
        label = "reporting_before" if not stages else "reporting_after"
        stages.append((label, db, kwargs["ticket"]))
        db.info["test_collection_stage"] = label
        if fault == "expired_stage" and label == "reporting_before":
            active = kwargs["authorize"].__self__.active
            assert active is not None and active[0] is db
            record_intentional_delay(active[1], "lock", 6)
            time.sleep(6)

    def creative(db: Session, *args: Any, **kwargs: Any) -> Any:
        result = original_creative(db, *args, **kwargs)
        stages.append(("media", db, kwargs["ticket"]))
        db.info["test_collection_stage"] = "media"
        return result

    def change(ticket: Any) -> None:
        changed.append(fault)
        if fault == "provider":
            replicas[2].revoked.add("q16-owner")
            return
        if fault == "exception":
            raise unexpected
        with Session(customer_engine) as db, db.begin():
            wid = ticket.inputs.workspace_id
            if fault == "session":
                db.execute(
                    update(CustomerSession)
                    .where(CustomerSession.digest == ticket.session_digest)
                    .values(revoked_at=1)
                )
            elif fault == "identity":
                db.execute(
                    update(CustomerUser)
                    .where(CustomerUser.id == ticket.actor_id)
                    .values(subject="replacement-subject")
                )
            elif fault == "workspace":
                db.execute(update(Workspace).where(Workspace.id == wid).values(status="suspended"))
            elif fault == "membership":
                db.execute(
                    update(CustomerMembership)
                    .where(
                        CustomerMembership.workspace_id == wid,
                        CustomerMembership.user_id == ticket.actor_id,
                    )
                    .values(status="suspended")
                )
            elif fault == "privacy":
                db.execute(
                    update(Workspace)
                    .where(Workspace.id == wid)
                    .values(export_privacy_revision=Workspace.export_privacy_revision + 1)
                )
            elif fault == "connection":
                db.execute(
                    update(GoogleCustomerConnection)
                    .where(GoogleCustomerConnection.workspace_id == wid)
                    .values(
                        status="disconnected", generation=GoogleCustomerConnection.generation + 1
                    )
                )
            elif fault == "goal":
                db.execute(
                    update(Goal)
                    .where(Goal.id == ticket.inputs.goal.goal_id)
                    .values(confirmed_preview_id=None)
                )
            elif fault == "media":
                db.execute(
                    update(MediaObject)
                    .where(MediaObject.workspace_id == wid)
                    .values(width=MediaObject.width + 1)
                )
            else:
                raise AssertionError("unknown test fault")

    @contextmanager
    def opened(context: PlanningReadContexts) -> Iterator[Session]:
        with original_open(context) as db:
            yield db
        assert context.active is None and db.get_transaction() is None
        label = db.info.get("test_collection_stage")
        if label is None:
            return
        closed.append(label)
        contexts.append(context)
        target = "media" if fault == "media" else "reporting_before"
        if fault not in ("none", "expired_stage") and label == target and not changed:
            change(stages[-1][2])

    monkeypatch.setattr(reader, "recheck_selected_paired_sources", reporting)
    monkeypatch.setattr(reader, "recheck_collected_creative", creative)
    monkeypatch.setattr(PlanningReadContexts, "open", opened)
    if fault == "exception":
        with pytest.raises(RuntimeError) as caught:
            client.post(url + "/generate", headers=headers(client), json=generation())
        assert caught.value is unexpected
    else:
        response = client.post(url + "/generate", headers=headers(client), json=generation())
        if fault == "none":
            assert response.status_code == 200, response.status_code
            assert closed == ["reporting_before", "media", "reporting_after"]
            assert len({id(db) for _, db, _ in stages}) == 3
            assert all(ticket is stages[0][2] for _, _, ticket in stages)
            assert len(preparations) == 1
        else:
            expected = {
                "expired_stage": (409, "planning_authority_expired"),
                "session": (401, "customer authentication required"),
                "provider": (401, "authentication failed"),
                "identity": (401, "customer authentication required"),
                "workspace": (404, "workspace not found"),
                "membership": (404, "workspace not found"),
                "privacy": (409, "creative image source changed"),
                "connection": (409, "provider connection unavailable"),
                "goal": (409, "confirmed goal changed"),
                "media": (409, "creative image source changed"),
            }[fault]
            assert response.status_code == expected[0], response.status_code
            assert response.json() == {"detail": expected[1]}
            if fault == "expired_stage":
                assert response.json() == {"detail": "planning_authority_expired"}
                assert len(stages) == 1 and closed == [] and preparations == []
            else:
                assert response.json() != {"detail": "planning_authority_expired"}
            if fault == "media":
                # The preparatory stages may finish; fresh atomic publication
                # must detect this changed image even though it was checked earlier.
                assert closed == ["reporting_before", "media", "reporting_after"]
                assert len(preparations) == 1
    if fault not in ("none", "media"):
        assert preparations == []
        assert closed == (
            []
            if fault == "expired_stage"
            else ["reporting_before", "media"]
            if fault == "connection"
            else ["reporting_before"]
        )
    assert changed == ([] if fault in ("none", "expired_stage") else [fault])
    assert all(context.active is None for context in contexts)
    assert all(db.get_transaction() is None for _, db, _ in stages)
    assert all(item[0].snapshots is None for item in preparations)
    if fault != "none":
        assert planning_snapshot(customer_engine) == before
    assert financial_counts(customer_engine) == effects
    assert (len(calls), len(fixture.calls)) == provider_counts
