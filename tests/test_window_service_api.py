"""Explicit canonical V3 through genuine API inputs, import, composition and persistence."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from app.api import customer_planning_documents as api
from app.campaign_performance.models import PerformanceCompletion
from app.campaign_performance.presence_storage import read_presence
from app.meta.client import MetaClient
from app.meta.models import MetaConnection
from app.meta.sync import MetaSyncService
from app.planning_documents.ports import PlanningCompositionPolicy
from app.planning_documents.service import PlanningDocumentService
from app.publication.execution_models import ProviderExecutionAttempt, ProviderExecutionRun
from app.settings import Settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_meta_connection import campaign, page
from tests.test_planning_documents_api import create_body
from tests.test_planning_evidence_adapter import setup_evidence
from tests.test_shopify_sales import configuration as configuration
from tests.window_service_fixture import configure_paid_workspace, import_meta_window_source

pytestmark = pytest.mark.planning_boundary


def configure_v3(monkeypatch: pytest.MonkeyPatch) -> None:
    original = api.service

    def configured(*args: Any, **kwargs: Any) -> PlanningDocumentService:
        service = original(*args, **kwargs)
        assert service.policy.version == "inlet.descriptive-review.v2"
        service.policy = PlanningCompositionPolicy(
            version="inlet.descriptive-review.v3", generator_version="inlet.descriptive-planning.v3"
        )
        return service

    monkeypatch.setattr(api, "service", configured)


@pytest.mark.parametrize("state", ["positive", "zero", "missing", "sparse"])
def test_actual_56day_import_to_owned_primary_comparison_plan(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    state: str,
) -> None:
    source = import_meta_window_source(customer_engine, configuration, replicas, monkeypatch, state)
    ticket, native_calls = source.ticket, source.native_calls
    imported, payloads, imported_requests = (
        source.imported,
        source.payloads,
        source.imported_requests,
    )
    runtime, header, end = source.runtime, source.header, source.ends_at
    wid = ticket.inputs.workspace_id
    configure_v3(monkeypatch)

    alice, _, _ = replicas
    alice.app.include_router(api.router)
    root = f"/api/customer/v1/workspaces/{wid}/planning/plans"
    body = create_body(ticket.inputs)
    body["inputs"]["reporting_window"] = dict(
        starts_at=(end - timedelta(days=7)).isoformat(), ends_at_exclusive=end.isoformat()
    )
    body["inputs"]["comparison_window"] = dict(
        starts_at=(end - timedelta(days=14)).isoformat(),
        ends_at_exclusive=(end - timedelta(days=7)).isoformat(),
    )
    created = alice.post(root, headers=headers(alice), json=body)
    assert created.status_code == 201, created.text
    url = root + "/" + created.json()["plan_id"]
    generated = alice.post(
        url + "/generate",
        headers=headers(alice),
        json=dict(expected_input_revision=1, expected_version=0, request_key="import-plan-first"),
    )
    assert generated.status_code == 200, generated.text
    document = generated.json()["document"]
    assert document["policy_version"] == "inlet.descriptive-review.v3"
    reporting = [r for r in document["evidence"] if r["kind"] == "reported_metrics"]
    assert len(reporting) == 2 and len({r["key"] for r in reporting}) == 2
    assert {tuple(r["reporting_window"].values()) for r in reporting} == {
        tuple(created.json()["inputs"][key].values())
        for key in ("reporting_window", "comparison_window")
    }
    with Session(customer_engine) as db:
        retained_completion = db.get(PerformanceCompletion, source.completion_id)
        assert retained_completion is not None
        retained = read_presence(db, retained_completion)
        assert retained is not None and retained[0] == header

    rationales = " ".join(action["rationale"] for action in document["actions"])
    assert "100 observed clicks" in rationales
    assert "100 USD observed spend" in rationales
    zero_statement = "Observed zero selected conversions across this requested window."
    primary_text = rationales.split("Comparison", 1)[0]
    assert (zero_statement in primary_text) is (state == "zero")
    if state == "positive":
        assert "selected conversions 10" in rationales
        assert "spend without conversions" not in rationales.lower()
    elif state in {"missing", "sparse"}:
        assert "partial" in rationales or "unavailable" in rationales
    assert native_calls
    current_view = alice.get(url)
    assert current_view.status_code == 200 and current_view.json()["freshness"] == "current"
    exported = alice.get(url + "/export?version=1")
    assert exported.status_code == 200
    assert exported.json()["document_digest"] == generated.json()["document_digest"]
    if state == "positive":
        # A real correction outside BOTH requested subsets still changes the retained
        # whole-source witness, even though primary/comparison values are unchanged.
        imported[0]["clicks"] = "1"
        payloads.extend([page(campaign("5", "123")), page(), page(*imported)])
        with Session(customer_engine) as db:
            runner = MetaSyncService(db, runtime, MetaClient(runtime))
            for expected in ("syncing", "syncing", "complete"):
                assert runner.page(wid, now=datetime.now(UTC), manual=True)["status"] == expected
        assert alice.get(url).json()["freshness"] == "source_changed"
        successor = alice.post(
            url + "/generate",
            headers=headers(alice),
            json=dict(
                expected_input_revision=1,
                expected_version=1,
                request_key="outside-window-correction",
            ),
        )
        assert successor.status_code == 200, successor.text
        assert successor.json()["document"]["parent_digest"] == generated.json()["document_digest"]
        assert "100 observed clicks" in " ".join(
            a["rationale"] for a in successor.json()["document"]["actions"]
        )
        assert alice.get(url + "/versions/1").json()["document"] == document
        assert alice.get(url + "/export?version=1").json()["document"] == document
    if state == "zero":
        # A fresh actual import may withdraw an earlier observed-zero conclusion.
        # Numeric legacy rows remain zero; the new raw source omits selected counts.
        for row in imported:
            row.pop("actions", None)
        payloads.extend([page(campaign("5", "123")), page(), page(*imported)])
        corrected_at = datetime.now(UTC)
        with Session(customer_engine) as db:
            runner = MetaSyncService(db, runtime, MetaClient(runtime))
            for expected in ("syncing", "syncing", "complete"):
                result = runner.page(wid, now=corrected_at, manual=True)
                assert result["status"] == expected, result
        assert not payloads and len(imported_requests) == 6
        assert alice.get(url).json()["freshness"] != "current"
        history = alice.get(url + "/versions/1")
        assert history.status_code == 200 and history.json()["document"] == document
        successor = alice.post(
            url + "/generate",
            headers=headers(alice),
            json=dict(
                expected_input_revision=1, expected_version=1, request_key="import-correction"
            ),
        )
        assert successor.status_code == 200, successor.text
        assert successor.json()["version"] == 2
        next_document = successor.json()["document"]
        assert next_document["parent_digest"] == generated.json()["document_digest"]
        assert zero_statement not in " ".join(a["rationale"] for a in next_document["actions"])
        old_export = alice.get(url + "/export?version=1")
        assert old_export.status_code == 200
        assert old_export.json()["document_digest"] == generated.json()["document_digest"]
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(ProviderExecutionRun)) == 0
        assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 0


@pytest.mark.parametrize("platform", ["google_ads", "meta_ads", "tiktok_ads"])
def test_owned_api_all_three_catalogs_and_explicit_per_window_gaps(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    platform: str,
) -> None:
    _, ticket, principal, calls = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, platform
    )
    configure_paid_workspace(customer_engine, ticket.inputs.workspace_id, monkeypatch)
    configure_v3(monkeypatch)
    alice = replicas[0]
    alice.app.include_router(api.router)
    root = f"/api/customer/v1/workspaces/{ticket.inputs.workspace_id}/planning/plans"
    body = create_body(ticket.inputs)
    primary = ticket.inputs.reporting_window
    body["inputs"]["comparison_window"] = dict(
        starts_at=(primary.starts_at - timedelta(days=1)).isoformat(),
        ends_at_exclusive=primary.starts_at.isoformat(),
    )
    created = alice.post(root, headers=headers(alice), json=body)
    assert created.status_code == 201, created.text
    url = root + "/" + created.json()["plan_id"]
    request = dict(
        expected_input_revision=1, expected_version=0, request_key="gaps-first-generation"
    )
    result = alice.post(url + "/generate", headers=headers(alice), json=request)
    assert result.status_code == 200, result.text
    doc = result.json()["document"]
    assert doc["policy_version"] == "inlet.descriptive-review.v3"
    assert sum(r["kind"] == "native_catalog" for r in doc["evidence"]) == 1
    assert not any(r["kind"] == "reported_metrics" for r in doc["evidence"])
    text = " ".join(a["rationale"] for a in doc["actions"])
    assert "Primary" in text and "Comparison" in text
    assert text.count("reporting_presence_unavailable") >= 2
    assert calls and alice.get(url).json()["freshness"] == "current"
    count = len(calls)
    replay = alice.post(url + "/generate", headers=headers(alice), json=request)
    assert replay.json() == result.json() and len(calls) == count
    assert alice.get(url + "/export?version=1").json()["document"] == doc

    from app.planning_documents.documents import PlanVersion
    from app.planning_documents.read_context import PlanningReadContexts
    from app.planning_documents.retained_sources import (
        RetainedSourcesChanged,
        capture_retained_sources,
    )

    document = PlanVersion.model_validate(doc)
    reads = PlanningReadContexts(
        lambda: Session(customer_engine),
        principal,
        replicas[2],
        ticket.inputs.workspace_id,
        principal.user.id,
    )
    with reads.open() as db:
        v3 = capture_retained_sources(
            db, principal=principal, document=document, now=datetime.now(UTC)
        )
        v2_document = document.model_copy(
            update={
                "policy_version": "inlet.descriptive-review.v2",
                "generator_version": "inlet.descriptive-planning.v2",
            }
        )
        v2 = capture_retained_sources(
            db, principal=principal, document=v2_document, now=datetime.now(UTC)
        )
        assert [w.model_dump(exclude={"observed_at"}) for w in v3] == [
            w.model_dump(exclude={"observed_at"}) for w in v2
        ], "V3 retains the exact V2 local source witness formula"
        for invalid in (
            {"generator_version": "inlet.descriptive-planning.v1"},
            {"policy_version": "unknown"},
        ):
            with pytest.raises(RetainedSourcesChanged) as error:
                capture_retained_sources(
                    db,
                    principal=principal,
                    document=document.model_copy(update=invalid),
                    now=datetime.now(UTC),
                )
            assert error.value.reason == "proof_unavailable"


@pytest.mark.parametrize(
    "change", ["session", "goal", "privacy", "owner", "source", "presence", "paid", "input_cas"]
)
def test_actual_api_change_after_real_composition_rolls_back_entire_generation(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    from app.campaign_performance.presence_models import MetricPresenceRow
    from app.customers.models import CustomerMembership, CustomerSession
    from app.goals.models import Goal
    from app.lifecycle.privacy import bump_workspace_export_revision
    from app.planning_documents.models import (
        PlanDependencyRow,
        PlanRequestRow,
        PlanRow,
        PlanVersionRow,
    )
    from app.planning_documents.window_composer import WindowPlanComposer
    from sqlalchemy import delete, update

    from tests.test_planning_qualified_reporting import install_presence

    _, ticket, principal, _ = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, "meta_ads"
    )
    aid, wid = ticket.inputs.accounts[0].account_id, ticket.inputs.workspace_id
    install_presence(customer_engine, aid)
    configure_paid_workspace(customer_engine, ticket.inputs.workspace_id, monkeypatch)
    configure_v3(monkeypatch)
    alice = replicas[0]
    alice.app.include_router(api.router)
    root = f"/api/customer/v1/workspaces/{wid}/planning/plans"
    created = alice.post(root, headers=headers(alice), json=create_body(ticket.inputs))
    assert created.status_code == 201, created.text
    pid = created.json()["plan_id"]
    compose = WindowPlanComposer.compose
    observed = []

    def change_after_real_compose(self: Any, **kwargs: Any) -> Any:
        candidate = compose(self, **kwargs)
        observed.append(candidate.digest())
        if change == "input_cas":
            from app.planning_documents.requests import EditPlan

            edit = create_body(ticket.inputs)
            edit.update(
                request_key="independent-input-edit", expected_input_revision=1, expected_version=0
            )
            edit["inputs"]["milestone"] = "Customer changed the saved milestone"
            independently_saved = PlanningDocumentService(customer_engine, replicas[2]).revise(
                principal, wid, pid, EditPlan.model_validate(edit)
            )
            assert independently_saved.input_revision == 2
            return candidate
        with Session(customer_engine) as db:
            if change == "session":
                db.execute(
                    update(CustomerSession)
                    .where(CustomerSession.digest == principal.session.digest)
                    .values(revoked_at=int(datetime.now(UTC).timestamp()))
                )
            elif change == "goal":
                db.execute(
                    update(Goal)
                    .where(Goal.id == ticket.inputs.goal.goal_id)
                    .values(confirmed_preview_id=None)
                )
            elif change == "privacy":
                bump_workspace_export_revision(db, wid)
            elif change == "owner":
                db.execute(
                    update(CustomerMembership)
                    .where(
                        CustomerMembership.workspace_id == wid,
                        CustomerMembership.user_id == principal.user.id,
                    )
                    .values(status="suspended")
                )
            elif change == "source":
                db.execute(
                    update(MetaConnection)
                    .where(MetaConnection.account_id == aid)
                    .values(generation=MetaConnection.generation + 1)
                )
            elif change == "presence":
                db.execute(delete(MetricPresenceRow))
            elif change == "paid":
                from app.billing.models import WorkspaceBilling

                db.execute(
                    update(WorkspaceBilling)
                    .where(WorkspaceBilling.workspace_id == wid)
                    .values(status="canceled")
                )
            db.commit()
        return candidate

    monkeypatch.setattr(WindowPlanComposer, "compose", change_after_real_compose)
    response = alice.post(
        root + "/" + pid + "/generate",
        headers=headers(alice),
        json=dict(expected_input_revision=1, expected_version=0, request_key="race-generate-first"),
    )
    assert observed and response.status_code in (
        (404,) if change in {"privacy", "owner"} else (401, 402, 403, 409)
    ), response.text
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
        plan = db.get(PlanRow, (wid, pid))
        if change == "privacy":
            assert plan is None, "privacy maintenance deletes the prior planning graph"
        else:
            assert plan is not None and plan.version_head == 0
            assert plan.input_head == (2 if change == "input_cas" else 1)


def test_real_postgres_final_goal_lock_wait_expires_authority(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if customer_engine.dialect.name != "postgresql":
        pytest.skip("actual PostgreSQL row-lock wait")
    import threading
    import time

    from app.goals.models import Goal
    from app.planning_documents.models import (
        PlanDependencyRow,
        PlanRequestRow,
        PlanRow,
        PlanVersionRow,
    )
    from app.planning_documents.window_composer import WindowPlanComposer
    from sqlalchemy import text

    _, ticket, _, _ = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, "meta_ads"
    )
    configure_paid_workspace(customer_engine, ticket.inputs.workspace_id, monkeypatch)
    configure_v3(monkeypatch)
    alice = replicas[0]
    alice.app.include_router(api.router)
    root = f"/api/customer/v1/workspaces/{ticket.inputs.workspace_id}/planning/plans"
    created = alice.post(root, headers=headers(alice), json=create_body(ticket.inputs))
    assert created.status_code == 201, created.text
    pid = created.json()["plan_id"]
    compose = WindowPlanComposer.compose
    acquired, observed_wait = threading.Event(), threading.Event()
    errors: list[BaseException] = []
    threads = []

    def holder() -> None:
        try:
            with Session(customer_engine) as locked, locked.begin():
                locked.scalar(
                    select(Goal).where(Goal.id == ticket.inputs.goal.goal_id).with_for_update()
                )
                backend = locked.scalar(text("select pg_backend_pid()"))
                acquired.set()
                deadline = time.monotonic() + 15
                with customer_engine.connect() as monitor:
                    while time.monotonic() < deadline:
                        # Statistics snapshots may otherwise hide a newly opened
                        # blocked backend for this monitor transaction's lifetime.
                        monitor.execute(text("select pg_stat_clear_snapshot()"))
                        waiting = monitor.scalar(
                            text(
                                "select count(*) from pg_stat_activity "
                                "where :pid = any(pg_blocking_pids(pid))"
                            ),
                            {"pid": backend},
                        )
                        if waiting:
                            observed_wait.set()
                            # Real time, measured only after an actual blocked final SELECT.
                            time.sleep(5.2)
                            return
                        time.sleep(0.02)
                raise AssertionError("final transaction did not wait on owned goal lock")
        except BaseException as error:
            errors.append(error)
            acquired.set()

    def hold_after_composition(self: Any, **kwargs: Any) -> Any:
        candidate = compose(self, **kwargs)
        worker = threading.Thread(target=holder)
        threads.append(worker)
        worker.start()
        assert acquired.wait(10) and not errors
        return candidate

    monkeypatch.setattr(WindowPlanComposer, "compose", hold_after_composition)
    response = alice.post(
        root + "/" + pid + "/generate",
        headers=headers(alice),
        json=dict(expected_input_revision=1, expected_version=0, request_key="real-pg-lock-expiry"),
    )
    for worker in threads:
        worker.join(20)
        assert not worker.is_alive()
    assert not errors and observed_wait.is_set()
    assert response.status_code == 409 and response.json()["detail"] == "planning_authority_expired"
    with Session(customer_engine) as db:
        plan = db.get(PlanRow, (ticket.inputs.workspace_id, pid))
        assert plan is not None and plan.version_head == 0
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


@pytest.mark.parametrize("expire", [False, True])
def test_actual_api_saved_receipt_reuse_and_final_original_expiry(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    expire: bool,
) -> None:
    from app.api import customer_planning_target_catalog
    from app.planning_documents.models import PlanDependencyRow, PlanRequestRow, PlanVersionRow
    from app.planning_documents.window_composer import WindowPlanComposer

    from tests.test_planning_qualified_reporting import install_presence

    _, ticket, principal, calls = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, "meta_ads"
    )
    install_presence(customer_engine, ticket.inputs.accounts[0].account_id)
    configure_paid_workspace(customer_engine, ticket.inputs.workspace_id, monkeypatch)
    configure_v3(monkeypatch)
    alice = replicas[0]
    alice.app.include_router(api.router)
    alice.app.include_router(customer_planning_target_catalog.router)
    root = f"/api/customer/v1/workspaces/{ticket.inputs.workspace_id}/planning"
    window = ticket.inputs.reporting_window
    catalog = alice.post(
        root + "/target-catalog-v2",
        headers=headers(alice),
        json=dict(
            account_id=ticket.inputs.accounts[0].account_id,
            starts_at=window.starts_at.isoformat(),
            ends_at=window.ends_at_exclusive.isoformat(),
        ),
    )
    assert catalog.status_code == 200, catalog.text
    target = next(t for t in catalog.json()["targets"] if t["entity"]["kind"] == "campaign")
    body = create_body(ticket.inputs)
    body["inputs"]["fixed_allocations"] = [
        dict(
            amount_micros=0,
            target=dict(
                account_id=ticket.inputs.accounts[0].account_id,
                canonical_entity_key=target["canonical_entity_key"],
                selection_key=target["selection_key"],
            ),
        )
    ]
    body["inputs"]["comparison_window"] = dict(
        starts_at=(window.starts_at - timedelta(days=1)).isoformat(),
        ends_at_exclusive=window.starts_at.isoformat(),
    )
    created = alice.post(root + "/plans", headers=headers(alice), json=body)
    assert created.status_code == 201, created.text
    count = len(calls)
    original = WindowPlanComposer.compose
    expired = []

    def advance_after_real_compose(self: Any, **kwargs: Any) -> Any:
        result = original(self, **kwargs)
        assert result.valid_until == min(
            c.reference.expires_at for c in kwargs["evidence"].catalogs
        )
        if expire:
            # Advance this operation's test clock to the ORIGINAL receipt expiry.
            # Independently refresh paid state at that same test instant, so the
            # paid-snapshot age gate does not mask the receipt's own expiry gate.
            from app.billing.service import reconcile
            from app.billing.webhooks import receive

            from tests import test_customer_billing as billing

            now = result.valid_until
            body = billing.payload("evt_window_receipt_refresh")
            with Session(customer_engine) as db:
                assert receive(db, body, billing.signature(body, now), billing.SECRET, now)
                assert reconcile(
                    db,
                    ticket.inputs.workspace_id,
                    "evt_window_receipt_refresh",
                    billing.POLICY,
                    billing.FixtureBilling(),
                    now,
                )
            expired.append(now)
        return result

    monkeypatch.setattr(WindowPlanComposer, "compose", advance_after_real_compose)
    monkeypatch.setattr(api, "utc_now", lambda: expired[0] if expired else datetime.now(UTC))
    url = root + "/plans/" + created.json()["plan_id"]
    response = alice.post(
        url + "/generate",
        headers=headers(alice),
        json=dict(
            expected_input_revision=1, expected_version=0, request_key="receipt-window-generation"
        ),
    )
    assert len(calls) == count, "targeted generation must reuse the exact retained catalog"
    if expire:
        assert response.status_code == 409, response.text
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
    else:
        assert response.status_code == 200, response.text
        text = " ".join(a["rationale"] for a in response.json()["document"]["actions"])
        assert "Primary" in text and "100 observed clicks" in text
        assert "Comparison" in text and "outside_imported_window" in text
        assert alice.get(url).json()["freshness"] == "current"


def test_actual_api_gap_to_available_invalidates_retained_proof_and_new_generation(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.test_planning_qualified_reporting import install_presence

    _, ticket, principal, calls = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, "meta_ads"
    )
    configure_paid_workspace(customer_engine, ticket.inputs.workspace_id, monkeypatch)
    configure_v3(monkeypatch)
    alice = replicas[0]
    alice.app.include_router(api.router)
    root = f"/api/customer/v1/workspaces/{ticket.inputs.workspace_id}/planning/plans"
    created = alice.post(root, headers=headers(alice), json=create_body(ticket.inputs))
    assert created.status_code == 201, created.text
    url = root + "/" + created.json()["plan_id"]
    before = alice.post(
        url + "/generate",
        headers=headers(alice),
        json=dict(
            expected_input_revision=1, expected_version=0, request_key="absence-window-first"
        ),
    )
    assert before.status_code == 200, before.text
    assert not any(r["kind"] == "reported_metrics" for r in before.json()["document"]["evidence"])
    install_presence(customer_engine, ticket.inputs.accounts[0].account_id)
    assert alice.get(url).json()["freshness"] == "source_changed"
    after = alice.post(
        url + "/generate",
        headers=headers(alice),
        json=dict(
            expected_input_revision=1, expected_version=1, request_key="absence-window-second"
        ),
    )
    assert after.status_code == 200, after.text
    assert after.json()["document"]["parent_digest"] == before.json()["document_digest"]
    assert any(r["kind"] == "reported_metrics" for r in after.json()["document"]["evidence"])
    from app.customers.models import CustomerMembership
    from sqlalchemy import update

    with Session(customer_engine) as db, db.begin():
        db.execute(
            update(CustomerMembership)
            .where(
                CustomerMembership.user_id == principal.user.id,
                CustomerMembership.workspace_id == ticket.inputs.workspace_id,
            )
            .values(role="viewer")
        )
    count = len(calls)
    assert alice.get(url).json()["freshness"] == "current"
    assert alice.get(url + "/versions/1").json()["document"] == before.json()["document"]
    assert alice.get(url + "/export?version=1").json()["document"] == before.json()["document"]
    assert len(calls) == count


@pytest.mark.parametrize("change", ["unknown_policy", "mixed_candidate", "sibling_bundle"])
def test_closed_policy_dispatch_never_falls_back_or_accepts_sibling_evidence(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    from app.planning_documents.composer import DescriptivePlanComposer
    from app.planning_documents.models import PlanRequestRow, PlanVersionRow
    from app.planning_documents.ports import EvidenceBundle
    from app.planning_documents.window_adapter import OwnedWindowEvidenceReader
    from app.planning_documents.window_composer import WindowPlanComposer

    _, ticket, _, calls = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, "meta_ads"
    )
    configure_paid_workspace(customer_engine, ticket.inputs.workspace_id, monkeypatch)
    configure_v3(monkeypatch)
    alice = replicas[0]
    alice.app.include_router(api.router)
    root = f"/api/customer/v1/workspaces/{ticket.inputs.workspace_id}/planning/plans"
    created = alice.post(root, headers=headers(alice), json=create_body(ticket.inputs))
    assert created.status_code == 201, created.text
    if change == "unknown_policy":
        original_service = api.service

        def configured(*args: Any, **kwargs: Any) -> PlanningDocumentService:
            value = original_service(*args, **kwargs)
            value.policy = PlanningCompositionPolicy(version="test-v1", generator_version="test-v1")
            return value

        monkeypatch.setattr(api, "service", configured)
    elif change == "mixed_candidate":
        compose = WindowPlanComposer.compose

        def mixed(self: Any, **kwargs: Any) -> Any:
            result = compose(self, **kwargs)
            return result.model_copy(update={"generator_version": "inlet.descriptive-planning.v2"})

        monkeypatch.setattr(WindowPlanComposer, "compose", mixed)
    else:
        collect = OwnedWindowEvidenceReader.collect

        def sibling(self: Any, actual: Any) -> Any:
            value = collect(self, actual)
            # Adversarial port response only: never used as positive generation proof.
            return EvidenceBundle.model_construct(
                **value.model_dump(exclude={"window_gaps", "reporting_pins"})
            )

        monkeypatch.setattr(OwnedWindowEvidenceReader, "collect", sibling)

    def legacy_forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("v3 must never fall back to legacy composition")

    monkeypatch.setattr(DescriptivePlanComposer, "compose", legacy_forbidden)
    response = alice.post(
        root + "/" + created.json()["plan_id"] + "/generate",
        headers=headers(alice),
        json=dict(
            expected_input_revision=1, expected_version=0, request_key="closed-dispatch-test"
        ),
    )
    assert response.status_code == 409, response.text
    if change == "unknown_policy":
        assert not calls
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(PlanVersionRow)) == 0
        assert (
            db.scalar(
                select(func.count())
                .select_from(PlanRequestRow)
                .where(PlanRequestRow.operation == "generate")
            )
            == 0
        )


def test_actual_service_identity_and_native_io_are_outside_sql_transactions(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx
    from app.collectors import account_diagnostics
    from app.planning_documents import authority
    from sqlalchemy import event

    _, ticket, _, _ = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, "meta_ads"
    )
    configure_paid_workspace(customer_engine, ticket.inputs.workspace_id, monkeypatch)
    configure_v3(monkeypatch)
    alice = replicas[0]
    alice.app.include_router(api.router)
    active: set[int] = set()
    refresh_count, native_count = 0, 0
    refresh = authority.refresh
    factory = account_diagnostics.diagnostic_transport

    def begin(connection: Any) -> None:
        active.add(id(connection))

    def end(connection: Any) -> None:
        active.discard(id(connection))

    def checked_refresh(*args: Any, **kwargs: Any) -> Any:
        nonlocal refresh_count
        assert not active, "planning identity refresh occurred inside an SQL transaction"
        refresh_count += 1
        return refresh(*args, **kwargs)

    def wire(request: httpx.Request) -> httpx.Response:
        nonlocal native_count
        assert not active, "native provider read occurred inside an SQL transaction"
        native_count += 1
        transport = factory()
        assert transport is not None
        with transport:
            response = transport.handle_request(request)
            response.read()
        return response

    event.listen(customer_engine, "begin", begin)
    event.listen(customer_engine, "commit", end)
    event.listen(customer_engine, "rollback", end)
    monkeypatch.setattr(authority, "refresh", checked_refresh)
    monkeypatch.setattr(
        account_diagnostics, "diagnostic_transport", lambda: httpx.MockTransport(wire)
    )
    try:
        root = f"/api/customer/v1/workspaces/{ticket.inputs.workspace_id}/planning/plans"
        created = alice.post(root, headers=headers(alice), json=create_body(ticket.inputs))
        assert created.status_code == 201, created.text
        url = root + "/" + created.json()["plan_id"]
        response = alice.post(
            url + "/generate",
            headers=headers(alice),
            json=dict(
                expected_input_revision=1, expected_version=0, request_key="actual-io-ordering"
            ),
        )
        assert response.status_code == 200, response.text
        assert refresh_count > 5 and native_count > 1 and not active
        before = native_count
        assert alice.get(url).json()["freshness"] == "current"
        assert native_count == before and not active
    finally:
        event.remove(customer_engine, "begin", begin)
        event.remove(customer_engine, "commit", end)
        event.remove(customer_engine, "rollback", end)
