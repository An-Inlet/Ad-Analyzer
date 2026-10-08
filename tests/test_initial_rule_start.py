"""Exact initial Start uses actual configured preview and native HTTP, no approval seed."""

from pathlib import Path
from typing import Any

import pytest
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
from sqlalchemy import Engine, func, select

from tests.initial_rule_fixture import configured_initial_rule
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize(
    "mode",
    [
        "internal",
        "configured",
        "erased",
        "session",
        "expired",
        "expired30",
        "source",
        "rollback",
        "unknown",
    ],
)
def historical_contract_exact_start_and_worker(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    mode: str,
) -> None:
    from tests import budget_mandate_fixture
    from tests.test_planning_reporting_configuration import profile

    configured_profile = profile()
    # Explicit positive execution scenario; the ordinary profile remains 30 seconds.
    configured_profile = configured_profile.model_copy(
        update={
            "native_read": configured_profile.native_read.model_copy(
                update={"observation_lifetime_seconds": 30 if mode == "expired30" else 120}
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
        if mode == "expired30":
            from dataclasses import replace
            from datetime import timedelta

            from app.session_automation.models import SessionAutomationRun
            from fastapi import HTTPException

            expired = replace(runtime, clock=lambda: native.clock() + timedelta(seconds=31))
            with pytest.raises(HTTPException):
                service.start(c.db, c.principal, wid, intent, expired)
            c.db.rollback()
            for model in (
                SessionAutomationRun,
                AutomaticDecisionAdmission,
                ProviderExecutionAttempt,
                ProviderExecutionApproval,
            ):
                assert c.db.scalar(select(func.count()).select_from(model)) == 0
            assert not c.server.posts
            return
        if mode == "configured":
            from app.api import customer_session_automation
            from app.production_runtime.reported_automation import configured_session_automation
            from app.settings import settings

            from tests.initial_start_configuration import configure
            from tests.test_customer_optimization_api import headers

            configure(c, policy, tmp_path, monkeypatch)
            c.alice.app.include_router(customer_session_automation.router)
            c.db.commit()
            options = c.alice.get(c.base + "/automation/initial-options/" + intent.preview_id)
            assert options.status_code == 200, options.text
            assert options.json()["preview_digest"] == intent.expected_preview_digest
            assert options.json()["options"][0]["policy_digest"] == policy.digest()
            started = c.alice.post(
                c.base + "/automation/start",
                json=intent.model_dump(mode="json"),
                headers=headers(c.alice),
            )
            assert started.status_code == 200, started.text
            identifier = started.json()["run_id"]
            c.db.commit()
            with configured_session_automation(
                c.db, c.principal, c.provider, settings
            ) as configured_runtime:
                assert configured_runtime
                assert (
                    worker.advance(customer_engine, wid, identifier, configured_runtime)
                    == "completed"
                )
            assert c.db.scalar(select(func.count()).select_from(ProviderExecutionApproval)) == 0
            assert c.db.scalar(select(func.count()).select_from(AutomaticDecisionAdmission)) == 1
            assert c.db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 1
            return
        run = service.start(c.db, c.principal, wid, intent, runtime)
        identifier = run.id
        assert c.db.get(InitialRuleSessionStart, identifier)
        assert service.start(c.db, c.principal, wid, intent, runtime).id == identifier
        from fastapi import HTTPException
        from sqlalchemy import text
        from sqlalchemy.exc import DBAPIError

        with pytest.raises(HTTPException):
            service.start(
                c.db,
                c.principal,
                wid,
                intent.model_copy(update={"expected_preview_digest": "0" * 64}),
                runtime,
            )
        c.db.rollback()
        with pytest.raises(DBAPIError):
            c.db.execute(
                text(
                    "UPDATE initial_rule_session_starts SET input_digest=:changed "
                    "WHERE session_run_id=:identifier"
                ),
                {"changed": "0" * 64, "identifier": identifier},
            )
        c.db.rollback()
        with pytest.raises(DBAPIError):
            c.db.execute(
                text("DELETE FROM initial_rule_session_starts WHERE session_run_id=:identifier"),
                {"identifier": identifier},
            )
        c.db.rollback()
        c.db.commit()
        from app.initial_planning.automatic_models import InitialRuleAdmissionOrigin
        from app.optimization_candidates.models import CandidateJob
        from sqlalchemy import delete

        if mode in {"erased", "session", "expired", "source", "rollback"}:
            if mode == "erased":
                from app.initial_planning.models import ObservationRow

                c.db.execute(
                    delete(ObservationRow).where(
                        ObservationRow.id == c.work.basis.observation_references[0].observation_id
                    )
                )
                c.db.commit()
                link = c.db.get(InitialRuleSessionStart, identifier, populate_existing=True)
                assert (
                    link and link.candidate_job_id is None and link.candidate_workspace_id is None
                )
                c.db.commit()
            elif mode == "session":
                from app.customers.models import CustomerSession

                session = c.db.get(CustomerSession, c.principal.session.digest)
                assert session
                session.revoked_at = int(native.clock().timestamp())
                c.db.commit()
            elif mode == "expired":
                from dataclasses import replace
                from datetime import timedelta

                runtime = replace(runtime, clock=lambda: native.clock() + timedelta(seconds=121))
            elif mode == "source":
                from app.workspaces.models import Workspace

                workspace = c.db.get(Workspace, wid)
                assert workspace
                workspace.export_privacy_revision += 1
                c.db.commit()
            else:
                from app.initial_planning import automatic_dependencies

                original_consume = automatic_dependencies.consume_origin

                def fail_after_consumption(*args: Any, **kwargs: Any) -> None:
                    original_consume(*args, **kwargs)
                    raise RuntimeError("fixture admission transaction failure")

                monkeypatch.setattr(
                    automatic_dependencies, "consume_origin", fail_after_consumption
                )
            try:
                state = worker.advance(customer_engine, wid, identifier, runtime)
                assert state in {"blocked", "waiting", "retry"}
            except HTTPException:
                pass
            assert c.db.scalar(select(func.count()).select_from(AutomaticDecisionAdmission)) == 0
            assert c.db.scalar(select(func.count()).select_from(InitialRuleAdmissionOrigin)) == 0
            assert c.db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 0
            assert c.db.scalar(select(func.count()).select_from(ProviderExecutionApproval)) == 0
            if mode != "session":
                service.stop(c.db, c.principal, wid, identifier, c.provider, runtime)
                assert service.status(c.db, wid, identifier, runtime).status == "stopped"
            return
        c.server.timeout = c.server.ignore = mode == "unknown"
        assert worker.advance(customer_engine, wid, identifier, runtime) == "completed"
        if mode == "unknown":
            from app.publication import optimization
            from app.publication.execution_models import ProviderExposureReservation
            from app.publication.optimization_contracts import MetaBudgetSetV1, OptimizationRequest

            attempt = c.db.scalar(select(ProviderExecutionAttempt))
            assert attempt
            attempt_id, fence = attempt.id, attempt.fence
            request = OptimizationRequest.model_validate(attempt.request)
            service.stop(c.db, c.principal, wid, identifier, c.provider, runtime)
            c.db.execute(delete(CandidateJob).where(CandidateJob.workspace_id == wid))
            c.db.commit()
            assert isinstance(request.intent.action, MetaBudgetSetV1)
            c.server.meta_campaign["daily_budget"] = str(
                request.intent.action.amount_micros // 10_000
            )
            receipt = optimization.reconcile_attempt(
                c.db, wid, attempt_id, runtime.review.execution, runtime.clock
            )
            assert receipt.outcome == "verified_target_state"
            stored_attempt = c.db.get(ProviderExecutionAttempt, attempt_id)
            assert stored_attempt and stored_attempt.fence == fence
            assert c.db.scalar(select(ProviderExposureReservation.state)) == "held"
            assert len(c.server.posts) == 1

        assert c.db.scalar(select(func.count()).select_from(ProviderExecutionApproval)) == 0
        assert c.db.scalar(select(func.count()).select_from(AutomaticDecisionAdmission)) == 1
        assert c.db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 1
