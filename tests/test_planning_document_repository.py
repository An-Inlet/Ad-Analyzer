"""Owned repository transactions over actual confirmed customer goal/source fixtures."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from app.ads.models import AdvertisingAccount
from app.customers.access import SESSION_COOKIE, CustomerPrincipal, digest
from app.customers.models import CustomerSession, CustomerUser
from app.goals import service as goals
from app.goals.models import Goal
from app.goals.schemas import GoalDefinition
from app.planning_documents import authority, repository
from app.planning_documents.common import fingerprint
from app.planning_documents.context import PlanInputRevision
from app.planning_documents.models import PlanInputRow, PlanRequestRow, PlanRow
from app.publication import customer_intents
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.budget_mandate_fixture import first_customer
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


def prepare(
    engine: Engine,
    configuration: Settings,
    path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
) -> tuple[CustomerPrincipal, Any, PlanInputRevision]:
    client, _, _, _, _, _, wid, _ = first_customer(
        engine, configuration, path, monkeypatch, replicas
    )
    now = datetime.now(UTC)
    with Session(engine) as db:
        session = db.get(CustomerSession, digest(client.cookies[SESSION_COOKIE]))
        assert session is not None
        user = db.get(CustomerUser, session.user_id)
        assert user is not None
        goal = db.scalar(select(Goal).where(Goal.workspace_id == wid))
        account = db.scalar(
            select(AdvertisingAccount).where(
                AdvertisingAccount.workspace_id == wid,
                AdvertisingAccount.connection_id.is_not(None),
            )
        )
        assert goal is not None and account is not None
        definition = GoalDefinition.model_validate(goals.current(db, goal).definition)
        scope = customer_intents.account(db, wid, account.id)
        document = PlanInputRevision.model_validate(
            dict(
                workspace_id=wid,
                plan_id="e" * 32,
                revision=1,
                goal=dict(
                    workspace_id=wid,
                    goal_id=goal.id,
                    revision=goal.revision,
                    definition=definition,
                    definition_digest=fingerprint(
                        "goal-definition", definition.model_dump(mode="json")
                    ),
                    confirmation_reference=goal.confirmed_preview_id,
                ),
                accounts=[
                    dict(
                        workspace_id=wid,
                        account_id=account.id,
                        connection_id=scope.account.connection_id,
                        platform=scope.account.platform,
                        connection_version=scope.connection_version,
                    )
                ],
                budget_period=dict(
                    starts_on=definition.budget_start,
                    ends_on_exclusive=definition.budget_end,
                    currency=definition.target_window.currency,
                    time_zone=definition.target_window.time_zone,
                ),
                total_ceiling_micros=definition.budget_micros,
                aggressiveness=definition.aggressiveness,
                reporting_window=dict(
                    starts_at=now - timedelta(days=2), ends_at_exclusive=now - timedelta(days=1)
                ),
                comparison_window=None,
                milestone="Review owned campaigns",
                product_offer=None,
                constraints=[],
                assumptions=[],
                excluded_entity_keys=[],
                fixed_allocations=[],
                scenario_intents=[],
                created_by=user.id,
                created_at=now,
            )
        )
        principal = CustomerPrincipal(user, session)
        db.expunge_all()
    return principal, replicas[2], document


def test_owned_create_replay_cas_and_rollback(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
) -> None:
    principal, provider, document = prepare(
        customer_engine, configuration, tmp_path, monkeypatch, replicas
    )
    now = datetime.now(UTC)

    def save(
        item: PlanInputRevision, expected: int, key: str, body_digest: str = "a" * 64
    ) -> PlanInputRevision:
        fact = authority.refresh(principal, provider)
        with Session(customer_engine) as db, db.begin():
            return repository.save_input(
                db,
                principal=principal,
                fact=fact,
                document=item,
                expected_input_revision=expected,
                expected_version=0,
                request_key=key,
                request_digest=body_digest,
                now=now,
            )

    assert save(document, 0, "create-one") == document
    assert save(document, 0, "create-one") == document
    with pytest.raises(HTTPException) as changed:
        save(document, 0, "create-one", "b" * 64)
    assert changed.value.status_code == 409
    second = document.model_copy(update={"revision": 2, "milestone": "Edited customer milestone"})
    assert save(second, 1, "edit-one") == second
    with pytest.raises(HTTPException) as stale:
        save(second.model_copy(update={"milestone": "stale"}), 1, "edit-stale")
    assert stale.value.status_code == 409
    bad = document.model_copy(
        update={"plan_id": "f" * 32, "goal": document.goal.model_copy(update={"revision": 1})}
    )
    with pytest.raises(HTTPException):
        save(bad, 0, "bad-goal")
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(PlanRow)) == 1
        assert db.scalar(select(func.count()).select_from(PlanInputRow)) == 2
        assert db.scalar(select(func.count()).select_from(PlanRequestRow)) == 2
        stored_plan = db.get(PlanRow, (document.workspace_id, document.plan_id))
        assert stored_plan is not None and stored_plan.input_head == 2


def test_postgres_independent_sessions_same_key_and_cas_races(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    if customer_engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL row-lock concurrency; SQLite sequential behavior covered")
    principal, provider, document = prepare(
        customer_engine, configuration, tmp_path, monkeypatch, replicas
    )
    barrier = Barrier(2)

    def create(index: int) -> PlanInputRevision:
        fact = authority.refresh(principal, provider)
        barrier.wait(timeout=10)
        with Session(customer_engine) as db, db.begin():
            return repository.save_input(
                db,
                principal=principal,
                fact=fact,
                document=document.model_copy(update={"plan_id": f"{index + 50:032x}"}),
                expected_input_revision=0,
                expected_version=0,
                request_key="concurrent-create",
                request_digest="a" * 64,
                now=datetime.now(UTC),
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        created = list(pool.map(create, (0, 1)))
    assert created[0] == created[1]
    barrier = Barrier(2)

    def edit(index: int) -> str:
        fact = authority.refresh(principal, provider)
        barrier.wait(timeout=10)
        try:
            with Session(customer_engine) as db, db.begin():
                repository.save_input(
                    db,
                    principal=principal,
                    fact=fact,
                    document=created[0].model_copy(
                        update={"revision": 2, "milestone": f"Choice {index}"}
                    ),
                    expected_input_revision=1,
                    expected_version=0,
                    request_key=f"edit-choice-{index}",
                    request_digest=f"{index + 1:064x}",
                    now=datetime.now(UTC),
                )
            return "saved"
        except HTTPException as error:
            assert error.status_code == 409
            return error.detail

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(edit, (0, 1)))
    assert sorted(results) == ["plan input or version changed", "saved"]
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(PlanRow)) == 1
        assert db.scalar(select(func.count()).select_from(PlanInputRow)) == 2
        assert db.scalar(select(func.count()).select_from(PlanRequestRow)) == 2


def test_resolve_owned_customer_intent_and_reject_unread_selection(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
) -> None:
    from app.planning_documents import input_resolution
    from app.planning_documents.requests import CustomerInputs, TargetSelector

    principal, provider, original = prepare(
        customer_engine, configuration, tmp_path, monkeypatch, replicas
    )
    intent = CustomerInputs(
        goal_id=original.goal.goal_id,
        goal_revision=original.goal.revision,
        account_ids=tuple(a.account_id for a in original.accounts),
        reporting_window=original.reporting_window,
        comparison_window=None,
        milestone="Owned customer milestone",
        product_offer="Customer supplied offer",
        constraints=(),
        assumptions=("Customer supplied hypothesis",),
        exclusions=(),
        fixed_allocations=(),
        scenario_intents=(),
        maximum_creative_assets=0,
    )
    fact = authority.refresh(principal, provider)
    with Session(customer_engine) as db, db.begin():
        current = authority.lock(db, principal, original.workspace_id, fact)
        prepared = input_resolution.prepare(
            db,
            workspace_id=original.workspace_id,
            plan_id=original.plan_id,
            revision=1,
            actor_id=current.user.id,
            intent=intent,
            now=datetime.now(UTC),
        )
        authority.final(current, fact)
    resolved = input_resolution.resolve(prepared, intent, ())
    assert resolved.total_ceiling_micros == original.goal.definition.budget_micros
    assert resolved.goal == original.goal and resolved.accounts == original.accounts
    assert resolved.assumptions[0].author_id == principal.user.id
    assert resolved.maximum_creative_assets == 0
    selected = intent.model_copy(
        update={
            "exclusions": (
                TargetSelector(
                    account_id=original.accounts[0].account_id,
                    canonical_entity_key="a" * 64,
                    selection_key="b" * 64,
                ),
            )
        }
    )
    with pytest.raises(HTTPException) as caught:
        input_resolution.resolve(prepared, selected, ())
    assert caught.value.status_code == 409

    from app.planning_documents.requests import CreatePlan, EditPlan
    from app.planning_documents.service import PlanningDocumentService

    service = PlanningDocumentService(customer_engine, provider)
    with pytest.raises(HTTPException) as pending_receipt:
        service.create(
            principal,
            original.workspace_id,
            CreatePlan(inputs=selected, request_key="unresolved-target-01"),
        )
    assert pending_receipt.value.status_code == 409
    assert (
        "The exact catalog selection is unavailable. Read fresh targets"
        in pending_receipt.value.detail
    )
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(PlanRow)) == 0
    request = CreatePlan(inputs=intent, request_key="service-create-01")
    created = service.create(principal, original.workspace_id, request)
    replay = service.create(principal, original.workspace_id, request)
    assert replay == created
    edited = service.revise(
        principal,
        original.workspace_id,
        created.plan_id,
        EditPlan(
            inputs=intent.model_copy(update={"milestone": "Changed milestone"}),
            request_key="service-edit-01",
            expected_input_revision=1,
            expected_version=0,
        ),
    )
    assert edited.input_revision == 2
    assert service.create(principal, original.workspace_id, request) == created

    assert (
        service.request_result(principal, original.workspace_id, "create", request.request_key)
        == created
    )
    assert service.listing(principal, original.workspace_id).items[0].input_revision == 2
    assert service.history(principal, original.workspace_id, created.plan_id).items == ()
    assert service.events(principal, original.workspace_id, created.plan_id).items == ()
    with pytest.raises(HTTPException) as invalid:
        service.listing(principal, original.workspace_id, cursor="invalid")
    assert invalid.value.status_code == 422

    with Session(customer_engine) as db, db.begin():
        draft = goals.create(
            db, original.workspace_id, principal.user.id, "draft-goal-01", None, datetime.now(UTC)
        )
        draft_id, draft_revision = draft.id, draft.revision
    with pytest.raises(HTTPException) as incomplete:
        service.create(
            principal,
            original.workspace_id,
            CreatePlan(
                inputs=intent.model_copy(
                    update={"goal_id": draft_id, "goal_revision": draft_revision}
                ),
                request_key="draft-plan-01",
            ),
        )
    assert incomplete.value.status_code == 409
    assert incomplete.value.detail == "confirm the current goal before planning"


@pytest.mark.parametrize("platform", ["google_ads", "meta_ads", "tiktok_ads"])
def test_actual_service_create_generate_and_stable_history(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    platform: str,
) -> None:
    from app.planning_documents.requests import CreatePlan, CustomerInputs, GeneratePlan
    from app.planning_documents.service import PlanningDocumentService

    from tests.test_planning_evidence_adapter import setup_evidence

    _, ticket, principal, calls = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, platform
    )
    inputs = ticket.inputs
    service = PlanningDocumentService(customer_engine, replicas[2])
    created = service.create(
        principal,
        inputs.workspace_id,
        CreatePlan(
            request_key="service-create-01",
            inputs=CustomerInputs(
                goal_id=inputs.goal.goal_id,
                goal_revision=inputs.goal.revision,
                account_ids=tuple(a.account_id for a in inputs.accounts),
                reporting_window=inputs.reporting_window,
                comparison_window=None,
                milestone=inputs.milestone,
                product_offer=None,
                constraints=(),
                assumptions=(),
                exclusions=(),
                fixed_allocations=(),
                scenario_intents=(),
            ),
        ),
    )
    request = GeneratePlan(
        expected_input_revision=1, expected_version=0, request_key="generate-first-01"
    )
    generated = service.generate(principal, inputs.workspace_id, created.plan_id, request)
    assert generated.version == 1 and generated.document.inputs == created.inputs
    assert calls
    count = len(calls)
    assert service.generate(principal, inputs.workspace_id, created.plan_id, request) == generated
    assert len(calls) == count
    assert service.history(principal, inputs.workspace_id, created.plan_id).items == (generated,)
    from app.planning_documents.requests import AssertionIntent, DecisionIntent

    action = generated.document.actions[0]
    decision_request = DecisionIntent(
        expected_version=1,
        expected_event_sequence=0,
        document_digest=generated.document.digest(),
        action_key=action.key,
        action_digest=action.digest(),
        decision="deferred",
        reason="Review manually",
        supersedes_event_id=None,
        request_key="decision-first-01",
    )
    decision = service.decide(principal, inputs.workspace_id, created.plan_id, decision_request)
    assert decision.event_sequence == 1

    for index, change in enumerate(
        (
            {"document_digest": "f" * 64},
            {"action_digest": "f" * 64},
            {"action_key": "unknown-action"},
        )
    ):
        with pytest.raises(HTTPException) as mismatch:
            service.decide(
                principal,
                inputs.workspace_id,
                created.plan_id,
                decision_request.model_copy(
                    update={
                        **change,
                        "expected_event_sequence": 1,
                        "request_key": f"bad-binding-{index}",
                    }
                ),
            )
        assert mismatch.value.status_code == 409
    assert (
        service.decide(principal, inputs.workspace_id, created.plan_id, decision_request)
        == decision
    )
    assertion_request = AssertionIntent(
        expected_version=1,
        expected_event_sequence=1,
        document_digest=generated.document.digest(),
        action_key=action.key,
        action_digest=action.digest(),
        assertion="customer_reports_applied",
        reported_applied_at=datetime.now(UTC),
        statement="Customer reports manual change",
        supersedes_event_id=None,
        request_key="assertion-first-01",
    )
    reported = service.assert_applied(
        principal, inputs.workspace_id, created.plan_id, assertion_request
    )
    assert reported.event_sequence == 2
    assert (
        service.assert_applied(principal, inputs.workspace_id, created.plan_id, assertion_request)
        == reported
    )
    with pytest.raises(HTTPException) as stale:
        service.decide(
            principal,
            inputs.workspace_id,
            created.plan_id,
            decision_request.model_copy(update={"request_key": "stale-decision-01"}),
        )
    assert stale.value.status_code == 409
    retraction = assertion_request.model_copy(
        update={
            "expected_event_sequence": 2,
            "assertion": "retracted",
            "reported_applied_at": None,
            "supersedes_event_id": reported.event.event_id,
            "request_key": "retract-first-01",
        }
    )
    retracted = service.assert_applied(principal, inputs.workspace_id, created.plan_id, retraction)
    assert retracted.event_sequence == 3
    page = service.events(principal, inputs.workspace_id, created.plan_id, limit=2)
    assert page.items == (decision, reported) and page.next_cursor == "2"
    assert service.events(principal, inputs.workspace_id, created.plan_id, cursor="2").items == (
        retracted,
    )
    assert (
        service.request_result(
            principal, inputs.workspace_id, "decide", decision_request.request_key
        )
        == decision
    )
    assert len(calls) == count

    # A later report can be explicitly withdrawn after a newer plan is generated
    # and the original observation expires. It never becomes a new acceptance.
    again = service.assert_applied(
        principal,
        inputs.workspace_id,
        created.plan_id,
        assertion_request.model_copy(
            update={
                "expected_event_sequence": 3,
                "supersedes_event_id": retracted.event.event_id,
                "request_key": "report-again-01",
            }
        ),
    )
    second = service.generate(
        principal,
        inputs.workspace_id,
        created.plan_id,
        GeneratePlan(
            expected_input_revision=1, expected_version=1, request_key="generate-second-01"
        ),
    )
    from app.planning_documents.service import PlanningDocumentService

    later = PlanningDocumentService(
        customer_engine,
        replicas[2],
        clock=lambda: generated.document.valid_until + timedelta(seconds=1),
    )
    withdrawal = retraction.model_copy(
        update={
            "expected_event_sequence": 4,
            "supersedes_event_id": again.event.event_id,
            "request_key": "historical-withdraw-01",
        }
    )
    with pytest.raises(HTTPException) as old_chain:
        later.assert_applied(
            principal,
            inputs.workspace_id,
            created.plan_id,
            withdrawal.model_copy(
                update={
                    "supersedes_event_id": reported.event.event_id,
                    "request_key": "obsolete-chain-01",
                }
            ),
        )
    assert old_chain.value.status_code == 409
    withdrawn = later.assert_applied(principal, inputs.workspace_id, created.plan_id, withdrawal)
    assert withdrawn.event_sequence == 5 and withdrawn.event.version == 1
    assert (
        later.assert_applied(principal, inputs.workspace_id, created.plan_id, withdrawal)
        == withdrawn
    )
    count = len(calls)
    current_read = service.read(principal, inputs.workspace_id, created.plan_id)
    assert current_read.freshness == "current" and current_read.document == second.document
    assert service.export(principal, inputs.workspace_id, created.plan_id, 2) == current_read
    from app.customers.models import CustomerMembership

    with Session(customer_engine) as db, db.begin():
        member = db.scalar(
            select(CustomerMembership).where(
                CustomerMembership.workspace_id == inputs.workspace_id,
                CustomerMembership.user_id == principal.user.id,
            )
        )
        assert member is not None
        member.role = "viewer"
    assert service.read(principal, inputs.workspace_id, created.plan_id).freshness == "current"
    assert service.history(principal, inputs.workspace_id, created.plan_id).items == (
        generated,
        second,
    )
    with pytest.raises(HTTPException) as viewer_write:
        service.decide(principal, inputs.workspace_id, created.plan_id, decision_request)
    assert viewer_write.value.status_code == 403
    with pytest.raises(HTTPException) as foreign:
        service.read(principal, inputs.workspace_id + 999, created.plan_id)
    assert foreign.value.status_code in (403, 404)
    assert len(calls) == count

    with pytest.raises(HTTPException) as foreign_correction:
        later.assert_applied(principal, inputs.workspace_id + 999, created.plan_id, withdrawal)
    assert foreign_correction.value.status_code in (403, 404)
    with pytest.raises(HTTPException) as viewer_correction:
        later.assert_applied(principal, inputs.workspace_id, created.plan_id, withdrawal)
    assert viewer_correction.value.status_code == 403
    from app.lifecycle.privacy import bump_workspace_export_revision

    with Session(customer_engine) as db, db.begin():
        member = db.scalar(
            select(CustomerMembership).where(
                CustomerMembership.workspace_id == inputs.workspace_id,
                CustomerMembership.user_id == principal.user.id,
            )
        )
        assert member is not None
        member.role = "owner"
        bump_workspace_export_revision(db, inputs.workspace_id)
    with pytest.raises(HTTPException) as erased:
        later.assert_applied(principal, inputs.workspace_id, created.plan_id, withdrawal)
    assert erased.value.status_code == 404
    import time

    with Session(customer_engine) as db, db.begin():
        session = db.get(CustomerSession, principal.session.digest)
        assert session is not None
        session.revoked_at = int(time.time())
    with pytest.raises(HTTPException) as revoked:
        later.assert_applied(principal, inputs.workspace_id, created.plan_id, withdrawal)
    assert revoked.value.status_code == 401


def test_new_catalog_observation_changes_snapshot_selection(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.test_planning_evidence_adapter import setup_evidence

    reader, ticket, _, _ = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, "google_ads"
    )
    first = reader.collect(ticket).catalogs[0].catalog
    second = reader.collect(ticket).catalogs[0].catalog
    assert first.targets[0].canonical_entity_key == second.targets[0].canonical_entity_key
    assert first.targets[0].entity == second.targets[0].entity
    assert first.targets[0].selection_key != second.targets[0].selection_key


@pytest.mark.parametrize("legacy", [False, True])
def test_generation_revoked_during_actual_reads_rolls_back(
    legacy: bool,
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import time

    from app.planning_documents.evidence_adapter import OwnedPlanningEvidenceReader
    from app.planning_documents.models import PlanDependencyRow, PlanVersionRow
    from app.planning_documents.requests import CreatePlan, CustomerInputs, GeneratePlan
    from app.planning_documents.service import PlanningDocumentService
    from app.planning_documents.window_adapter import OwnedWindowEvidenceReader

    from tests.planning_legacy_policy_fixture import legacy_v2_policy
    from tests.test_planning_evidence_adapter import setup_evidence

    _, ticket, principal, calls = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, "meta_ads"
    )
    inputs = ticket.inputs
    service = PlanningDocumentService(customer_engine, replicas[2])
    if legacy:
        service.policy = legacy_v2_policy()
    reader_type = OwnedPlanningEvidenceReader if legacy else OwnedWindowEvidenceReader
    created = service.create(
        principal,
        inputs.workspace_id,
        CreatePlan(
            request_key="adverse-create-01",
            inputs=CustomerInputs(
                goal_id=inputs.goal.goal_id,
                goal_revision=inputs.goal.revision,
                account_ids=tuple(a.account_id for a in inputs.accounts),
                reporting_window=inputs.reporting_window,
                comparison_window=None,
                milestone=inputs.milestone,
                product_offer=None,
                constraints=(),
                assumptions=(),
                exclusions=(),
                fixed_allocations=(),
                scenario_intents=(),
            ),
        ),
    )
    original = reader_type.collect

    def revoke(reader: Any, ticket: Any) -> Any:
        result = original(reader, ticket)
        with Session(customer_engine) as db, db.begin():
            session = db.get(CustomerSession, principal.session.digest)
            assert session is not None
            session.revoked_at = int(time.time())
        return result

    monkeypatch.setattr(reader_type, "collect", revoke)
    with pytest.raises(HTTPException) as denied:
        service.generate(
            principal,
            inputs.workspace_id,
            created.plan_id,
            GeneratePlan(
                expected_input_revision=1, expected_version=0, request_key="adverse-generate-01"
            ),
        )
    assert denied.value.status_code == 401 and calls
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(PlanVersionRow)) == 0
        assert db.scalar(select(func.count()).select_from(PlanDependencyRow)) == 0
        assert db.scalar(select(func.count()).select_from(PlanRequestRow)) == 1
        plan = db.get(PlanRow, (inputs.workspace_id, created.plan_id))
        assert plan is not None and plan.version_head == 0


@pytest.mark.parametrize("same_key", [True, False])
def test_postgres_concurrent_generation_receipt_and_head_cas(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    same_key: bool,
) -> None:
    if customer_engine.dialect.name != "postgresql":
        pytest.skip("independent transaction race requires PostgreSQL")
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from app.planning_documents.models import PlanVersionRow
    from app.planning_documents.requests import CreatePlan, CustomerInputs, GeneratePlan
    from app.planning_documents.service import PlanningDocumentService

    from tests.test_planning_evidence_adapter import setup_evidence

    _, ticket, principal, _ = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, "meta_ads"
    )
    inputs = ticket.inputs
    service = PlanningDocumentService(customer_engine, replicas[2])
    created = service.create(
        principal,
        inputs.workspace_id,
        CreatePlan(
            request_key="race-create-01",
            inputs=CustomerInputs(
                goal_id=inputs.goal.goal_id,
                goal_revision=inputs.goal.revision,
                account_ids=tuple(a.account_id for a in inputs.accounts),
                reporting_window=inputs.reporting_window,
                comparison_window=None,
                milestone=inputs.milestone,
                product_offer=None,
                constraints=(),
                assumptions=(),
                exclusions=(),
                fixed_allocations=(),
                scenario_intents=(),
            ),
        ),
    )
    barrier = Barrier(2)

    def generate(index: int) -> str:
        barrier.wait(timeout=10)
        try:
            result = service.generate(
                principal,
                inputs.workspace_id,
                created.plan_id,
                GeneratePlan(
                    expected_input_revision=1,
                    expected_version=0,
                    request_key=f"race-generate-{0 if same_key else index}",
                ),
            )
            return result.document.digest()
        except HTTPException as error:
            assert error.status_code == 409
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(generate, (0, 1)))
    if same_key:
        assert results[0] == results[1] != "conflict"
    else:
        assert results.count("conflict") == 1
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(PlanVersionRow)) == 1
        assert db.scalar(select(func.count()).select_from(PlanRequestRow)) == 2

    from app.planning_documents.models import PlanEventRow
    from app.planning_documents.requests import AssertionIntent

    document = service.history(principal, inputs.workspace_id, created.plan_id).items[0].document
    action = document.actions[0]
    reported = service.assert_applied(
        principal,
        inputs.workspace_id,
        created.plan_id,
        AssertionIntent(
            expected_version=1,
            expected_event_sequence=0,
            document_digest=document.digest(),
            action_key=action.key,
            action_digest=action.digest(),
            assertion="customer_reports_applied",
            reported_applied_at=datetime.now(UTC),
            statement="Manual report",
            supersedes_event_id=None,
            request_key="race-report-01",
        ),
    )
    later = PlanningDocumentService(
        customer_engine, replicas[2], clock=lambda: document.valid_until + timedelta(seconds=1)
    )

    def retract(index: int) -> str:
        barrier.wait(timeout=10)
        try:
            result = later.assert_applied(
                principal,
                inputs.workspace_id,
                created.plan_id,
                AssertionIntent(
                    expected_version=1,
                    expected_event_sequence=1,
                    document_digest=document.digest(),
                    action_key=action.key,
                    action_digest=action.digest(),
                    assertion="retracted",
                    reported_applied_at=None,
                    statement="Withdraw report",
                    supersedes_event_id=reported.event.event_id,
                    request_key=f"race-retract-{0 if same_key else index}",
                ),
            )
            return result.event.digest()
        except HTTPException as error:
            assert error.status_code == 409
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        corrections = list(pool.map(retract, (0, 1)))
    if same_key:
        assert corrections[0] == corrections[1] != "conflict"
    else:
        assert corrections.count("conflict") == 1
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(PlanEventRow)) == 2


def test_final_revision_receipt_cannot_replay_another_plan(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
) -> None:
    principal, provider, original = prepare(
        customer_engine, configuration, tmp_path, monkeypatch, replicas
    )
    plans = (original, original.model_copy(update={"plan_id": "f" * 32}))
    for index, document in enumerate(plans):
        fact = authority.refresh(principal, provider)
        with Session(customer_engine) as db, db.begin():
            repository.save_input(
                db,
                principal=principal,
                fact=fact,
                document=document,
                expected_input_revision=0,
                expected_version=0,
                request_key=f"create-cross-{index}",
                request_digest=f"{index:064x}",
                now=datetime.now(UTC),
            )
    # Both callers may have passed their initial lookup before this first final
    # transaction commits. The second final transaction must bind the route plan.
    for index, document in enumerate(plans):
        fact = authority.refresh(principal, provider)
        try:
            with Session(customer_engine) as db, db.begin():
                repository.save_input(
                    db,
                    principal=principal,
                    fact=fact,
                    document=document.model_copy(update={"revision": 2}),
                    expected_input_revision=1,
                    expected_version=0,
                    request_key="same-revision-key",
                    request_digest="a" * 64,
                    now=datetime.now(UTC),
                )
        except HTTPException as error:
            assert index == 1 and error.status_code == 409
            assert error.detail == "request key belongs to another plan"
        else:
            assert index == 0
    with Session(customer_engine) as db:
        second = db.get(PlanRow, (original.workspace_id, plans[1].plan_id))
        assert second is not None and second.input_head == 1
        assert db.scalar(select(func.count()).select_from(PlanInputRow)) == 3
        assert db.scalar(select(func.count()).select_from(PlanRequestRow)) == 3
