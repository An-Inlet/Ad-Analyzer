"""Owned actual configured preview/report/native reads, no execution record seeds."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from app.initial_planning.automatic_compiler import compile_initial_rule
from app.initial_planning.automatic_source import read_initial_rule
from app.initial_planning.preview_v2 import InitialPreviewV2
from app.settings import Settings
from sqlalchemy import Engine

from tests.initial_rule_fixture import configured_initial_rule
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize(
    "mode", ["current", "revoked", "expired", "historical_erased", "native_drift"]
)
def test_actual_retained_preview_to_initial_operational_rule(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    mode: str,
) -> None:
    with configured_initial_rule(
        customer_engine, configuration, tmp_path, monkeypatch, replicas
    ) as context:
        db, principal, provider = context.db, context.principal, context.provider
        work, native, planning = context.work, context.native, context.planning
        policy = context.policy
        runtime = planning.optimization
        assert runtime is not None
        scope, binding = work.scope, work.scope.mandate
        wid, user, session = scope.account.workspace_id, principal.user, principal.session
        value = InitialPreviewV2.model_validate(context.preview)
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

        from datetime import timedelta
        from uuid import uuid4

        from app.initial_planning.automatic_dependencies import bind_initial_dependency
        from app.initial_planning.automatic_source import (
            assert_initial_rule_current,
            initial_rule_epoch,
        )
        from app.optimization_candidates.models import CandidateJob
        from fastapi import HTTPException

        queued = CandidateJob(
            id=uuid4().hex,
            workspace_id=wid,
            environment="contract_test",
            publication_id=scope.source.publication_id,
            attempt_id=None,
            actor_id=user.id,
            auth_session_digest=session.digest,
            input_digest=work.digest(),
            work=work.model_dump(mode="json"),
            state="pending",
            attempts=0,
            due_at=runtime.clock(),
            created_at=runtime.clock(),
        )
        db.add(queued)
        db.flush()
        bind_initial_dependency(db, queued, work)
        assert_initial_rule_current(
            db, principal, provider, work, decision, planning, runtime.clock
        )
        epoch = initial_rule_epoch(db, principal, provider, work, decision, planning, runtime.clock)
        assert epoch.source_reference == work.basis.opportunity_id
        assert epoch.semantic_digest == work.basis.semantic_key_digest
        if mode == "current":
            return
        if mode == "revoked":
            session.revoked_at = int(datetime.now(UTC).timestamp())
            db.flush()
        elif mode == "historical_erased":
            from app.initial_planning.models import ObservationRow
            from sqlalchemy import delete

            historical = next(
                ref.observation_id
                for ref in work.basis.observation_references
                if ref.observation_id != work.basis.selected_observation_id
            )
            db.execute(delete(ObservationRow).where(ObservationRow.id == historical))
            db.flush()
        elif mode == "native_drift":
            from app.publication.optimization_contracts import MetaCurrentState

            assert isinstance(native.state, MetaCurrentState)
            assert native.state.daily_budget_micros is not None
            native = native.model_copy(
                update={
                    "state": native.state.model_copy(
                        update={"daily_budget_micros": native.state.daily_budget_micros + 10_000},
                    )
                }
            )
        clock = (
            (lambda: decision.expires_at + timedelta(seconds=1))
            if mode == "expired"
            else runtime.clock
        )
        with pytest.raises(HTTPException):
            if mode == "native_drift":
                read_initial_rule(db, principal, provider, work, native, planning, clock)
            else:
                assert_initial_rule_current(
                    db, principal, provider, work, decision, planning, clock
                )
