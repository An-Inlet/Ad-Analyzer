"""Owned actual configured preview/report/native reads, no execution record seeds."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from app.api.customer_initial_planning import get_initial_planning_runtime
from app.commerce.models import CommerceStore
from app.commerce.sync import CommerceSyncService
from app.customers.access import SESSION_COOKIE, CustomerPrincipal, digest
from app.customers.models import CustomerSession, CustomerUser
from app.initial_planning.automatic_compiler import compile_initial_rule
from app.initial_planning.automatic_contracts import InitialReportedRulePolicyV1
from app.initial_planning.automatic_source import read_initial_rule, resolve_initial_work
from app.initial_planning.review_v2_api_contracts import InitialPreviewExecutionRuntime
from app.optimization_candidates.contracts import CandidateScope
from app.optimization_candidates.selection import SelectionReadRequest, catalog_digest
from app.optimization_candidates.selection_contracts import SelectionProvenance
from app.production_runtime.candidate_assembly import OwnedCandidateReads
from app.production_runtime.optimization_assembly import configured_optimization
from app.publication import customer_intents, customer_optimization
from app.publication.customer_optimization_contracts import TargetQuery
from app.settings import Settings, settings
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import FakeMeasurement
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration
from tests.v2_execution_fixture import ready


def test_actual_retained_preview_to_initial_operational_rule(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
) -> None:
    alice, _, base, query, preview, _, _, _ = ready(
        customer_engine,
        configuration,
        tmp_path,
        monkeypatch,
        replicas,
    )
    wid = int(base.split("/workspaces/")[1].split("/")[0])
    opt = base + "/optimization"
    options = alice.post(opt + "/target-options", json=query, headers=headers(alice))
    assert options.status_code == 200, options.text
    selected = {**query, "option_id": options.json()["options"][0]["id"]}
    result = alice.post(
        opt + "/budget-mandates",
        headers=headers(alice),
        json={
            "intent": {
                "selection": selected,
                "total_cap_micros": 50_000_000,
                "aggressiveness": "balanced",
            }
        },
    )
    assert result.status_code == 201, result.text
    budget = result.json()
    consent = alice.post(
        opt + "/budget-mandates/" + budget["mandate_id"] + "/consent",
        headers=headers(alice),
        json={
            "selection": selected,
            "expected_revision": budget["revision"],
            "policy_digest": budget["policy_digest"],
            "preparation_digest": budget["preparation_digest"],
        },
    )
    assert consent.status_code == 200, consent.text
    with Session(customer_engine) as db:
        store = db.scalar(select(CommerceStore).where(CommerceStore.workspace_id == wid))
        assert store
        # Schedule a genuine empty terminal page now; no historical metrics are invented.
        store.last_sync_at = None
        db.commit()
        imported = CommerceSyncService(
            db, configuration, FakeMeasurement(configuration, [([], None)])
        ).page(wid, now=datetime.now(UTC))
        assert imported["status"] == "complete", imported
        session = db.get(CustomerSession, digest(alice.cookies[SESSION_COOKIE]))
        assert session
        user = db.get(CustomerUser, session.user_id)
        assert user
        principal = CustomerPrincipal(user, session)
        provider = replicas[2]
        initial = get_initial_planning_runtime(db)
        with configured_optimization(db, principal, provider, settings) as runtime:
            assert runtime and initial.configuration and initial.profile
            binding = customer_intents.binding(db, wid, budget["mandate_id"], budget["revision"])
            catalog = customer_optimization.discover(
                db, wid, TargetQuery(**query), user.id, runtime, binding
            )
            db.rollback()
            reads = OwnedCandidateReads(
                customer_engine,
                principal,
                provider,
                runtime,
                "inlet.initial-reported-efficiency-rule.v1",
            )
            fence = reads.source_fence(
                db,
                SelectionReadRequest(target_request=catalog.request, mandate=binding),
                runtime.clock(),
            )
            state = catalog.options[0].state
            scope = CandidateScope(
                account=state.scope,
                mandate=binding,
                goal_id=query["goal_id"],
                goal_revision=query["goal_revision"],
                goal_digest=catalog.request.goal_digest,
                target=state.target,
                budget_owner_key=state.budget_owner.key(state.scope),
                target_set_digest=state.budget_owner.target_set_digest(),
                source=fence,
            )
            policy = InitialReportedRulePolicyV1(
                workspace_id=wid,
                environment="contract_test",
                policy_id="a" * 32,
                revision=1,
                policy_family="b" * 32,
                planning_profile_digest=initial.profile.digest(),
                initial=initial.configuration,
                allowed_operation="meta_budget_set_v1",
                maximum_candidate_age_seconds=120,
            )
            provenance = SelectionProvenance(
                actor_id=user.id,
                scope_digest=scope.digest(),
                policy_digest=policy.digest(),
                catalog_digest=catalog_digest(catalog),
                option_id=catalog.options[0].identifier(catalog.request),
                state_digest=state.digest(),
                manifest_digest="c" * 64,
                observed_at=catalog.observed_at,
                expires_at=catalog.expires_at,
            )
            native = reads.read(db, scope, runtime.clock())
            planning = InitialPreviewExecutionRuntime(initial, runtime)
            from app.initial_planning.preview_v2 import InitialPreviewV2

            value = InitialPreviewV2.model_validate(preview)
            work = resolve_initial_work(
                db,
                principal,
                provider,
                scope,
                provenance,
                value.id,
                value.digest(),
                policy,
                planning,
            )
            observation = read_initial_rule(
                db, principal, provider, work, native, planning, runtime.clock
            )
            from app.publication.execution_mandates import checked

            _, mandate = checked(db, wid, binding, user.id, runtime.clock)
            decision = compile_initial_rule(observation, policy, mandate, 0, 0, runtime.clock())
            assert decision.status == "suggested" and decision.action is not None
            assert decision.action.amount_micros == value.after_budget_micros
            assert decision.evidence.basis.preview_id == value.id
            assert decision.spending_authority == "none" and not decision.dispatch_ready
            assert not decision.evidence.empirical_qualification
