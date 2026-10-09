"""Real current planning confirmation with coherent test-owned policy inputs."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from app.api.customer_initial_planning import get_initial_planning_runtime
from app.customers.access import SESSION_COOKIE, digest
from app.initial_planning.planning_consent_models import PlanningConsentRow
from app.initial_planning.runtime import InitialPlanningRuntime
from app.planning_reporting.contracts import PlanningReportingProfileV1
from app.publication import execution_mandates
from app.publication.execution_contracts import ProviderMandatePolicy
from app.publication.execution_models import ProviderExecutionMandate
from app.settings import Settings
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests import budget_mandate_fixture
from tests.test_planning_consents import confirm
from tests.test_planning_reporting_configuration import profile


@dataclass(frozen=True)
class ConfirmedNativeCase:
    client: Any
    root: str
    body: dict[str, Any]
    runtime: InitialPlanningRuntime
    policy: ProviderMandatePolicy
    workspace_id: int
    mandate_id: str
    session_digest: str
    requests: list[Any]
    control: dict[str, Any]
    server: Any


def confirmed_native_case(
    engine: Engine,
    configuration: Settings,
    path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    *,
    precision: bool,
) -> ConfirmedNativeCase:
    document = profile().model_dump(mode="json")
    if precision:
        document["initial"]["rules"][0]["budget_step_micros"] = 1
    configured = PlanningReportingProfileV1.model_validate(document)
    # Test policy input only, before real file loading, calibration and confirmation.
    monkeypatch.setattr(budget_mandate_fixture, "profile", lambda: configured)
    client, root, body, _, requests, control, wid, server = budget_mandate_fixture.first_customer(
        engine, configuration, path, monkeypatch, replicas
    )
    prepared, _, _ = confirm(client, root, body)
    with Session(engine) as db:
        row = db.get(ProviderExecutionMandate, prepared["mandate_id"])
        assert row and row.state == "draft"
        assert db.get(PlanningConsentRow, (row.id, row.revision))
        policy = execution_mandates.policy(db, row)
        runtime = get_initial_planning_runtime(db)
        assert runtime.profile == configured and runtime.configuration == configured.initial
    selection = body["intent"]["selection"]
    return ConfirmedNativeCase(
        client,
        root,
        {
            "calibration_id": selection["calibration_id"],
            "observation_id": selection["observation_id"],
            "choice": {"option_id": selection["native_option_id"]},
            "mandate_id": prepared["mandate_id"],
            "mandate_revision": prepared["revision"],
        },
        runtime,
        policy,
        wid,
        prepared["mandate_id"],
        digest(client.cookies[SESSION_COOKIE]),
        requests,
        control,
        server,
    )
