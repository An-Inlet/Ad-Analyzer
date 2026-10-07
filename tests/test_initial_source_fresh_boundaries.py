"""Factored immutable input reads retain their late authority and expiry boundaries."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from app.initial_planning import calibration, preview
from app.initial_planning.models import ObservationRow
from app.publication import execution_mandates
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, delete

from tests.initial_rule_fixture import configured_initial_rule
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize(
    "change", ["historical_erased", "session", "expired", "source", "goal_revision"]
)
def test_preview_rechecks_after_mandate_boundary(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    change: str,
) -> None:
    with configured_initial_rule(
        customer_engine, configuration, tmp_path, monkeypatch, replicas
    ) as c:
        original = execution_mandates.checked
        triggered = False
        now = c.planning.planning.clock()
        planning = replace(c.planning.planning, clock=lambda: now)

        def checked(*args: Any, **kwargs: Any) -> Any:
            nonlocal triggered, now
            result = original(*args, **kwargs)
            assert not triggered
            triggered = True
            if change == "historical_erased":
                historical = next(
                    ref.observation_id
                    for ref in c.work.basis.observation_references
                    if ref.observation_id != c.work.basis.selected_observation_id
                )
                c.db.execute(delete(ObservationRow).where(ObservationRow.id == historical))
            elif change == "session":
                c.principal.session.revoked_at = int(datetime.now(UTC).timestamp())
                c.db.flush()
            elif change == "source":
                from app.meta.models import MetaConnection
                from sqlalchemy import select

                source = c.db.scalar(select(MetaConnection))
                assert source
                source.generation += 1
                c.db.flush()
            elif change == "goal_revision":
                from app.goals import service as goals
                from app.goals.schemas import GoalDefinition

                goal = goals.owned(c.db, c.work.scope.account.workspace_id, c.work.scope.goal_id)
                definition = GoalDefinition.model_validate(goals.current(c.db, goal).definition)
                goals.revise(c.db, goal, definition, c.principal.user.id, now)
                c.db.flush()
            else:
                now += timedelta(seconds=301)
            return result

        monkeypatch.setattr(execution_mandates, "checked", checked)
        with pytest.raises(HTTPException):
            preview.read_preview(
                c.db,
                c.principal,
                c.provider,
                c.work.scope.account.workspace_id,
                c.work.basis.preview_id,
                planning,
            )
        assert triggered


def test_standalone_objective_reader_does_not_reuse_previous_validation(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
) -> None:
    with configured_initial_rule(
        customer_engine, configuration, tmp_path, monkeypatch, replicas
    ) as c:
        args = (
            c.db,
            c.principal,
            c.provider,
            c.work.scope.account.workspace_id,
            c.work.basis.calibration_id,
            c.planning.planning,
        )
        report = calibration.read_calibration(*args)
        objective = calibration.read_objective(*args)
        assert report.objective_digest == objective.digest()
        historical = next(
            ref.observation_id
            for ref in c.work.basis.observation_references
            if ref.observation_id != c.work.basis.selected_observation_id
        )
        c.db.execute(delete(ObservationRow).where(ObservationRow.id == historical))
        c.db.commit()
        with pytest.raises(HTTPException):
            calibration.read_objective(*args)


@pytest.mark.parametrize("change", ["selected_completion", "late_baseline_staleness"])
def test_preview_input_reuse_keeps_completion_and_late_assessment_guards(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    change: str,
) -> None:
    from app.initial_planning.models import PreviewRow
    from app.initial_planning.preview_v2 import PreviewIntentV2

    with configured_initial_rule(
        customer_engine, configuration, tmp_path, monkeypatch, replicas
    ) as c:
        row = c.db.get(PreviewRow, c.work.basis.preview_id)
        assert row
        intent = PreviewIntentV2.model_validate(row.intent)
        if change == "selected_completion":
            historical = next(
                ref.observation_id
                for ref in c.work.basis.observation_references
                if ref.observation_id != c.work.basis.selected_observation_id
            )
            intent = intent.model_copy(update={"observation_id": historical})
        else:
            original = calibration._read_calibration_inputs
            observed = []

            def checked(*args: Any, **kwargs: Any) -> Any:
                value = original(*args, **kwargs)
                from app.commerce.models import CommerceStore
                from app.goals import service as goals
                from app.goals.schemas import GoalDefinition

                goal = goals.owned(c.db, c.work.scope.account.workspace_id, c.work.scope.goal_id)
                definition = GoalDefinition.model_validate(goals.current(c.db, goal).definition)
                store = c.db.get(CommerceStore, definition.store_id)
                assert store
                # Adverse same-operation source change after actual calibration validation.
                # A cached confirmed result must not replace the later real assessment.
                store.last_sync_at = c.planning.planning.clock() - timedelta(hours=24, seconds=1)
                c.db.flush()
                observed.append(True)
                return value

            monkeypatch.setattr(calibration, "_read_calibration_inputs", checked)
        with pytest.raises(HTTPException):
            preview.inputs(c.db, c.principal, c.provider, intent, c.planning.planning)
        if change == "late_baseline_staleness":
            assert observed == [True]
