"""Explicit private v4 policy through real input/API collection and persistence.

Only provider HTTP and identity fixtures are injected; no selected proof, catalog,
collector, composer or retained witness is fabricated for positive journeys.
"""

from functools import partial
from typing import Any, Literal

import pytest
from app.api import customer_planning_documents as api
from app.planning_documents.models import PlanDependencyRow, PlanRequestRow, PlanRow, PlanVersionRow
from app.planning_documents.ports import PlanningCompositionPolicy
from app.planning_documents.service import PlanningDocumentService
from app.settings import Settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.selected_range_plan_fixture import prepared_range_plan
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_planning_documents_api import create_body
from tests.test_shopify_sales import configuration as configuration

POLICY = PlanningCompositionPolicy(
    version="inlet.descriptive-review.v4", generator_version="inlet.descriptive-planning.v4"
)


def configured(
    engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    *,
    value: str | None = "10",
    family: Literal["conversions", "all_conversions"] = "conversions",
) -> Any:
    reader, ticket, f, _, native_calls = prepared_range_plan(
        engine, configuration, replicas, monkeypatch, value=value, family=family
    )
    # Test/private dependency configuration only. Production route still creates
    # canonical v3. Actual service and every provider/proof boundary remain real.
    monkeypatch.setattr(
        api, "PlanningDocumentService", partial(PlanningDocumentService, policy=POLICY)
    )
    for client in (f.alice, f.bob):
        client.app.include_router(api.router)
    root = f"/api/customer/v1/workspaces/{f.wid}/planning/plans"
    body = create_body(ticket.inputs)
    body["inputs"]["comparison_window"] = ticket.inputs.comparison_window.model_dump(mode="json")
    body["inputs"]["selected_reporting"] = [
        x.model_dump(mode="json") for x in ticket.inputs.selected_reporting
    ]
    return f, root, body, native_calls, reader


def create(f: Any, root: str, body: Any) -> str:
    response = f.alice.post(root, headers=headers(f.alice), json=body)
    assert response.status_code == 201, response.text
    assert response.json()["inputs"]["selected_reporting"] == body["inputs"]["selected_reporting"]
    plan_id = response.json()["plan_id"]
    assert isinstance(plan_id, str)
    return root + "/" + plan_id


def generation() -> dict[str, Any]:
    return dict(expected_input_revision=1, expected_version=0, request_key="selected-v4-generate")


@pytest.mark.parametrize("family", ["conversions", "all_conversions"])
@pytest.mark.parametrize("value", ["10", "0", None])
def test_actual_range_capture_input_generation_persistence_and_replay(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    family: Literal["conversions", "all_conversions"],
    value: str | None,
) -> None:
    f, root, body, calls, _ = configured(
        customer_engine, configuration, replicas, monkeypatch, value=value, family=family
    )
    url = create(f, root, body)
    response = f.alice.post(url + "/generate", headers=headers(f.alice), json=generation())
    assert response.status_code == 200, response.text
    saved = response.json()
    doc = saved["document"]
    assert doc["policy_version"] == POLICY.version
    assert doc["inputs"]["selected_reporting"] == body["inputs"]["selected_reporting"]
    proof = doc["selected_reporting_proof"]["accounts"][0]
    assert proof["capture_pin"] is not None and proof["traffic_pin"] is not None
    rationale = doc["actions"][0]["rationale"]
    assert "100 observed clicks" in rationale and "100 USD observed spend" in rationale
    assert f"metric family {family}" in rationale
    assert ("Observed zero selected conversions" in rationale.split("Comparison")[0]) == (
        value == "0"
    )
    counts = len(calls), len(f.calls)
    replay = f.alice.post(url + "/generate", headers=headers(f.alice), json=generation())
    assert replay.status_code == 200 and replay.json() == saved
    assert (len(calls), len(f.calls)) == counts
    current = f.alice.get(url)
    assert current.status_code == 200, current.text
    assert current.json()["freshness"] == "current"
    assert current.json()["document_digest"] == saved["document_digest"]
    if value == "10" and family == "conversions":
        view = current.json()
        action = view["document"]["actions"][0]
        decision = dict(
            expected_version=1,
            expected_event_sequence=0,
            document_digest=view["document_digest"],
            action_key=action["key"],
            action_digest=view["action_digests"][action["key"]],
            decision="accepted_for_manual_application",
            reason="Customer reviewed reported values",
            supersedes_event_id=None,
            request_key="selected-v4-decision",
        )
        accepted = f.alice.post(url + "/decisions", headers=headers(f.alice), json=decision)
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["event_sequence"] == 1
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(PlanVersionRow)) == 1
        kinds = list(db.scalars(select(PlanDependencyRow.kind)))
        assert kinds.count("local_reporting_v3") == 1
        assert kinds.count("reported_metrics") == 4
        from app.publication.execution_models import ProviderExecutionAttempt, ProviderExecutionRun

        assert db.scalar(select(func.count()).select_from(ProviderExecutionRun)) == 0
        assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 0


@pytest.mark.parametrize(
    "change", ["receipt", "session", "proof", "traffic_reference", "flush_expiry"]
)
def test_original_session_and_final_graph_change_abort_before_persist(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    from app.campaign_performance.range_receipt_models import RangeReceiptRow
    from app.customers.models import CustomerSession
    from app.planning_documents.selected_composer import SelectedPlanComposer
    from sqlalchemy import delete, update

    f, root, body, _, _ = configured(customer_engine, configuration, replicas, monkeypatch)
    url = create(f, root, body)
    original = SelectedPlanComposer.compose

    def compose(self: SelectedPlanComposer, **kwargs: Any) -> Any:
        plan = original(self, **kwargs)
        if change == "flush_expiry":
            from app.lifecycle.privacy import database_utc_now
            from app.planning_documents import repository

            clock = database_utc_now
            flush = Session.flush
            state = {"flushed": False}

            def flushed(db: Session, *args: Any, **kw: Any) -> None:
                pending = any(isinstance(row, PlanVersionRow) for row in db.new)
                flush(db, *args, **kw)
                if pending:
                    state["flushed"] = True

            monkeypatch.setattr(Session, "flush", flushed)
            monkeypatch.setattr(
                repository,
                "database_utc_now",
                lambda db: plan.valid_until if state["flushed"] else clock(db),
            )
            return plan
        if change == "proof":
            proof = plan.selected_reporting_proof
            assert proof is not None
            return plan.model_copy(
                update={
                    "selected_reporting_proof": proof.model_copy(
                        update={
                            "accounts": (
                                proof.accounts[0].model_copy(update={"traffic_pin": None}),
                            )
                        }
                    )
                }
            )
        if change == "traffic_reference":
            return plan.model_copy(
                update={
                    "evidence": tuple(
                        ref.model_copy(update={"document_digest": "f" * 64})
                        if ref.key.startswith("traffic_window:")
                        else ref
                        for ref in plan.evidence
                    )
                }
            )
        with Session(customer_engine) as db, db.begin():
            if change == "receipt":
                db.execute(delete(RangeReceiptRow).where(RangeReceiptRow.account_id == f.aid))
            else:
                db.execute(
                    update(CustomerSession)
                    .where(CustomerSession.digest == f.sid)
                    .values(revoked_at=1)
                )
        return plan

    monkeypatch.setattr(SelectedPlanComposer, "compose", compose)
    result = f.alice.post(url + "/generate", headers=headers(f.alice), json=generation())
    assert result.status_code in ({401, 403} if change == "session" else {409}), result.text
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(PlanVersionRow)) == 0
        assert db.scalar(select(func.count()).select_from(PlanDependencyRow)) == 0
        assert (
            db.scalar(
                select(func.count())
                .select_from(PlanRequestRow)
                .where(PlanRequestRow.operation == "generate")
            )
            == 0
        )
        assert (
            db.scalar(select(PlanRow.version_head).where(PlanRow.id == url.rsplit("/", 1)[1])) == 0
        )


@pytest.mark.parametrize("mode", ["none", "foreign", "csrf", "empty", "missing"])
def test_selector_intent_authentication_and_explicit_empty(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    f, root, body, calls, _ = configured(customer_engine, configuration, replicas, monkeypatch)
    before = len(calls), len(f.calls)
    if mode == "none":
        body["inputs"].pop("selected_reporting")
    elif mode == "empty":
        body["inputs"]["selected_reporting"] = []
    elif mode == "missing":
        body["inputs"]["selected_reporting"][0]["capture_id"] = "f" * 32
    if mode == "foreign":
        from tests.test_customer_identity import login

        login(f.bob, "selected-runtime-outsider:1")
    client = f.bob if mode == "foreign" else f.alice
    response = client.post(root, headers={} if mode == "csrf" else headers(client), json=body)
    if mode in {"empty", "missing"}:
        assert response.status_code == 201, response.text
        assert (
            response.json()["inputs"]["selected_reporting"] == body["inputs"]["selected_reporting"]
        )
        result = f.alice.post(
            root + "/" + response.json()["plan_id"] + "/generate",
            headers=headers(f.alice),
            json=generation(),
        )
        if mode == "missing":
            assert result.status_code == 409, result.text
            with Session(customer_engine) as db:
                assert db.scalar(select(func.count()).select_from(PlanVersionRow)) == 0
        else:
            assert result.status_code == 200, result.text
            assert (
                result.json()["document"]["selected_reporting_proof"]["accounts"][0]["capture_pin"]
                is None
            )
    else:
        assert response.status_code == (
            409 if mode == "none" else 404 if mode == "foreign" else 403
        ), response.text
        assert (len(calls), len(f.calls)) == before


def test_constructor_requires_canonical_policy_and_preserves_default() -> None:
    from sqlalchemy import create_engine

    from tests.test_customer_identity import FakeProvider

    engine = create_engine("sqlite://")
    try:
        assert (
            PlanningDocumentService(engine, FakeProvider()).policy.version
            == "inlet.descriptive-review.v3"
        )
        assert PlanningDocumentService(engine, FakeProvider(), policy=POLICY).policy == POLICY
        with pytest.raises(ValueError):
            PlanningDocumentService(
                engine,
                FakeProvider(),
                policy=POLICY.model_copy(
                    update={"generator_version": "inlet.descriptive-planning.v3"}
                ),
            )
        with pytest.raises(ValueError):
            PlanningDocumentService(
                engine,
                FakeProvider(),
                policy=POLICY.model_copy(update={"version": "inlet.descriptive-review.v99"}),
            )
    finally:
        engine.dispose()
