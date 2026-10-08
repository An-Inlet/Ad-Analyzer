"""Exact initial Start uses actual configured preview and native HTTP, no approval seed."""

import importlib
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from threading import Barrier
from typing import Any

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.initial_planning.automatic_models import InitialRuleAdmissionOrigin
from app.initial_planning.automatic_source import INITIAL_RULE_PRODUCER_FAMILY
from app.initial_planning.start_contracts import (
    INITIAL_AUTOMATIC_FAMILY,
    InitialRuleAutomaticPolicyV1,
    StartInitialReportedRuleAutomationV1,
)
from app.initial_planning.start_models import InitialRuleSessionStart
from app.optimization_candidates import review_bridge
from app.optimization_candidates import service as candidates
from app.optimization_candidates.selection import CandidateSelectionRuntime
from app.optimization_candidates.selection_contracts import CandidatePolicyRef
from app.publication.execution_models import ProviderExecutionApproval, ProviderExecutionAttempt
from app.session_automation import service, worker
from app.session_automation.contracts import AutomaticPolicyRef
from app.session_automation.models import AutomaticDecisionAdmission
from app.session_automation.runtime import SessionAutomationRuntime
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.initial_rule_fixture import configured_initial_rule
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_shopify_sales import configuration as configuration


@contextmanager
def initial_start_case(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
) -> Iterator[Any]:
    from tests import budget_mandate_fixture
    from tests.test_planning_reporting_configuration import profile

    configured_profile = profile()
    # Explicit positive execution scenario; the ordinary profile remains 30 seconds.
    configured_profile = configured_profile.model_copy(
        update={
            "native_read": configured_profile.native_read.model_copy(
                update={"observation_lifetime_seconds": 120}
            ),
            "initial": configured_profile.initial.model_copy(
                update={"preview_lifetime_seconds": 120}
            ),
        }
    )
    monkeypatch.setattr(budget_mandate_fixture, "profile", lambda: configured_profile)
    with configured_initial_rule(
        customer_engine, configuration, tmp_path, monkeypatch, replicas
    ) as c:
        native = c.planning.optimization
        assert native
        candidate = candidates.CandidateRuntime(
            "contract_test",
            c.provider,
            c.reads.read,
            lambda *_: None,
            native.clock,
            operational_policies=(c.policy,),
            initial_planning=c.planning,
        )
        policy = InitialRuleAutomaticPolicyV1(
            decision_basis="initial_reported_efficiency_rule",
            workspace_id=c.work.scope.account.workspace_id,
            environment="contract_test",
            policy_family=INITIAL_AUTOMATIC_FAMILY,
            policy_id="d" * 32,
            revision=1,
            candidate_policy=CandidatePolicyRef(
                policy_id=c.policy.policy_id, revision=c.policy.revision
            ),
            candidate_policy_digest=c.policy.digest(),
            allowed_operations=("meta_budget_set_v1",),
            semantic_producer_families=(INITIAL_RULE_PRODUCER_FAMILY,),
            lifetime_seconds=120,
            cadence_seconds=60,
        )

        def catalog(request: Any, now: Any) -> Any:
            return c.reads.catalog(request, now, c.work.scope.mandate)

        runtime = SessionAutomationRuntime(
            CandidateSelectionRuntime(candidate, catalog, c.reads.source_fence, native.clock),
            review_bridge.CandidateReviewRuntime(candidate, native.execution, native.clock),
            (policy,),
            (),
            native.clock,
        )
        intent = StartInitialReportedRuleAutomationV1(
            schema_version="inlet.start-initial-reported-rule-automation.v1",
            decision_basis="initial_reported_efficiency_rule",
            preview_id=c.work.basis.preview_id,
            expected_preview_digest=c.work.basis.preview_digest,
            mandate=c.work.scope.mandate,
            policy=AutomaticPolicyRef(policy_id=policy.policy_id, revision=policy.revision),
            expected_policy_digest=policy.digest(),
        )
        wid = c.work.scope.account.workspace_id
        c.db.commit()
        yield c, runtime, intent, wid


@pytest.mark.parametrize(
    "mode", ["stale_consent", "spent_budget", "competing", "downgrade", "maintenance"]
)
def historical_contract_initial_start_admission_boundaries(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    mode: str,
) -> None:
    if mode == "competing" and customer_engine.dialect.name != "postgresql":
        pytest.skip("independent worker transactions require PostgreSQL row locks")
    with initial_start_case(customer_engine, configuration, tmp_path, monkeypatch, replicas) as (
        c,
        runtime,
        intent,
        wid,
    ):
        started = service.start(c.db, c.principal, wid, intent, runtime)
        identifier = started.id
        c.db.commit()
        if mode == "downgrade":
            migration = importlib.import_module(
                "migrations.versions.20261007_0085_initial_rule_session_starts"
            )
            with (
                customer_engine.begin() as connection,
                Operations.context(MigrationContext.configure(connection)),
                pytest.raises(RuntimeError, match="cannot discard retained initial Start"),
            ):
                migration.downgrade()
            assert c.db.get(InitialRuleSessionStart, identifier)
            return
        if mode in {"stale_consent", "spent_budget"}:
            from app.publication.execution_models import (
                ProviderExecutionMandate,
                ProviderPeriodLedger,
            )

            if mode == "stale_consent":
                mandate = c.db.get(ProviderExecutionMandate, intent.mandate.mandate_id)
                assert mandate
                mandate.state = "revoked"
            else:
                ledger = c.db.get(ProviderPeriodLedger, intent.mandate.ledger_id)
                assert ledger
                ledger.spent_high_water_micros = 50_000_000
            c.db.commit()
            try:
                assert worker.advance(customer_engine, wid, identifier, runtime) in {
                    "blocked",
                    "waiting",
                    "retry",
                }
            except HTTPException as exc:
                assert exc.status_code in {403, 409}
            assert not c.server.posts
            for model in (
                ProviderExecutionAttempt,
                ProviderExecutionApproval,
                AutomaticDecisionAdmission,
            ):
                assert c.db.scalar(select(func.count()).select_from(model)) == 0
            return
        if mode == "maintenance":
            from app.production_runtime.reported_automation import run_configured_session_automation
            from app.settings import settings

            from tests.initial_start_configuration import configure

            configure(c, runtime.policies[0], tmp_path, monkeypatch)
            monkeypatch.setattr("app.customers.identity.get_identity_provider", lambda: c.provider)
            c.db.commit()
            run_configured_session_automation(customer_engine, settings)
        else:
            barrier = Barrier(2)

            def advance() -> str:
                barrier.wait(timeout=10)
                return worker.advance(customer_engine, wid, identifier, runtime)

            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(advance) for _ in range(2)]
                outcomes = [f.result(timeout=45) for f in futures]
            assert sorted(outcomes) == ["completed", "not_due"]
        c.db.rollback()
        with Session(customer_engine) as db:
            assert db.scalar(select(func.count()).select_from(InitialRuleAdmissionOrigin)) == 1
            assert db.scalar(select(func.count()).select_from(AutomaticDecisionAdmission)) == 1
            assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 1
            assert db.scalar(select(func.count()).select_from(ProviderExecutionApproval)) == 0
        assert len(c.server.posts) == 1
