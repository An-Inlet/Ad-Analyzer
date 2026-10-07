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


@pytest.mark.parametrize("change", ["historical_erased", "session", "expired"])
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
