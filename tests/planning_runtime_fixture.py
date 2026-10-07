"""Actual configured API/worker acquisition and native v2 producer, offline only."""

from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from app.api import customer_initial_planning, customer_reported_feedback
from app.collectors import owned_meta_budget
from app.commerce.sync import CommerceSyncService
from app.customers.access import CustomerPrincipal
from app.customers.models import CustomerSession, CustomerUser
from app.initial_planning import capture, native_budget
from app.initial_planning.contracts import EfficiencyObjectiveV1
from app.meta.security import utc
from app.meta.sync import MetaSyncService, run_meta_tick
from app.planning_reporting import runtime as assembly
from app.planning_reporting.contracts import PlanningReportingProfileV1
from app.publication import customer_intents, execution_mandates
from app.publication.execution_contracts import ProviderMandatePolicy
from app.reported_feedback.contracts import ReportedAcquisitionRequestV1
from app.reported_feedback.models import ReportedFeedbackJob
from app.settings import Settings, settings
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import FakeMeasurement
from tests.test_customer_identity import login
from tests.test_customer_optimization_api import headers
from tests.test_planning_reporting_configuration import profile
from tests.test_reported_feedback_acquisition import acquisition_fixture


def configured_journey(
    db: Session,
    engine: Engine,
    configuration: Settings,
    path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
) -> Any:
    alice, _, provider = replicas
    data = acquisition_fixture(db, configuration, path, monkeypatch)
    wid, principal, _, old_job, acquisition, source, clock, old_runner, _, control, server = data
    user = db.get(CustomerUser, principal.user.id)
    assert user is not None
    user.subject = "configured-planning"
    db.commit()
    configured = profile()
    initial = configured.initial.model_copy(update={"preview_lifetime_seconds": 300})
    configured = PlanningReportingProfileV1.model_validate(
        {**configured.model_dump(), "initial": initial.model_dump()}
    )
    config_path = path / "planning-profile.json"
    config_path.write_text(configured.model_dump_json())
    for config in (settings, old_runner.settings):
        monkeypatch.setattr(config, "planning_reporting_profile_path", str(config_path))
        monkeypatch.setattr(config, "planning_reporting_profile_digest", configured.digest())
    for name in (
        "meta_enabled",
        "meta_client_id",
        "meta_client_secret",
        "meta_token_encryption_key",
        "meta_redirect_uri",
    ):
        monkeypatch.setattr(settings, name, getattr(old_runner.settings, name))
    monkeypatch.setattr(assembly, "planning_clock", lambda: clock[0])
    # Existing original-session contract is retained; the actual browser/API login
    # below creates the session subsequently bound to the API request and worker.
    import app.api.customer as customer_api

    monkeypatch.setattr(customer_api, "TTL_SECONDS", 60 * 86400)
    login(alice, "configured-planning:first")
    alice.app.include_router(customer_initial_planning.router)
    alice.app.include_router(customer_reported_feedback.router)
    assert (
        customer_initial_planning.get_initial_planning_runtime not in alice.app.dependency_overrides
    )
    from app.reported_feedback.runtime import get_reported_feedback_runtime

    assert get_reported_feedback_runtime not in alice.app.dependency_overrides
    reporting_root = f"/api/customer/v1/workspaces/{wid}/reported-feedback"
    result = alice.post(
        reporting_root + "/comparisons",
        headers=headers(alice),
        json={
            "attempt_id": acquisition.anchor.original_attempt_id,
            "goal_id": acquisition.objective.goal_id,
            "goal_revision": acquisition.objective.goal_revision,
            "maximum_reported_cpa_micros": acquisition.objective.maximum_reported_cpa_micros,
        },
    )
    assert result.status_code == 200, result.text
    job = db.get(ReportedFeedbackJob, result.json()["id"], populate_existing=True)
    assert job is not None and job.id != old_job.id
    original_user = db.get(CustomerUser, job.original_actor_id, populate_existing=True)
    original_session = db.get(CustomerSession, job.original_session_digest, populate_existing=True)
    assert original_user and original_session
    principal = CustomerPrincipal(original_user, original_session)
    request = ReportedAcquisitionRequestV1.model_validate(job.document)
    clock[0] = max(clock[0], utc(job.next_due_at) + timedelta(seconds=1))
    control.update(before_conversions="2", after_conversions="4")
    runner = MetaSyncService(
        db, old_runner.settings
    )  # Real configured factory, no runtime injection.
    assert runner.reported_feedback is not None
    runtime = runner.reported_feedback
    assert runtime.initial.profile is configured or runtime.initial.profile == configured
    monkeypatch.setattr(settings, "meta_sync_pages", 3)

    def complete_configured() -> None:
        db.commit()
        run_meta_tick(engine)
        db.expire_all()

    complete_configured()
    assert job.completed_observations == 0
    saved_rolling_time = utc(source.last_sync_at)
    complete_configured()
    assert job.completed_observations == 1 and utc(source.last_sync_at) == saved_rolling_time
    capture.capture_current(
        db, principal, provider, wid, job.account_id, job.campaign_id, runtime.initial
    )
    db.commit()
    clock[0] += timedelta(seconds=1)
    complete_configured()
    clock[0] += timedelta(seconds=61)
    complete_configured()
    clock[0] += timedelta(seconds=1)
    complete_configured()
    assert job.state == "ready" and job.completed_observations == 4
    assert utc(source.last_sync_at) == saved_rolling_time
    configuration.shopify_measurement_enabled = True
    commerce = CommerceSyncService(db, configuration, FakeMeasurement(configuration, [([], None)]))
    assert commerce.page(wid, now=clock[0])["status"] == "complete"
    db.commit()
    native_requests: list[httpx.Request] = []

    def wire(outgoing: httpx.Request) -> httpx.Response:
        assert outgoing.method == "GET"
        native_requests.append(outgoing)
        return httpx.Response(200, json=server(outgoing).json())

    monkeypatch.setattr(
        owned_meta_budget, "native_budget_transport", lambda: httpx.MockTransport(wire)
    )
    root = f"/api/customer/v1/workspaces/{wid}/initial-planning"
    result = alice.post(
        root + "/captures",
        headers=headers(alice),
        json={"account_id": job.account_id, "campaign_id": job.campaign_id},
    )
    assert result.status_code == 200, result.text
    observation_id = result.json()["id"]
    result = alice.post(
        root + "/calibrations",
        headers=headers(alice),
        json={
            "observation_id": observation_id,
            "goal_id": request.objective.goal_id,
            "goal_revision": request.objective.goal_revision,
            "maximum_reported_cpa_micros": request.objective.maximum_reported_cpa_micros,
        },
    )
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "evaluated", result.text
    calibration_id = result.json()["id"]
    objective = EfficiencyObjectiveV1.model_validate(request.objective.model_dump())
    catalog = native_budget.catalog(db, principal, provider, objective, runtime.initial)
    native = catalog.options[0].observation
    scope = customer_intents.account(db, wid, job.account_id)
    policy = ProviderMandatePolicy(
        environment="contract_test",
        workspace_id=wid,
        goal_id=objective.goal_id,
        goal_revision=objective.goal_revision,
        currency="USD",
        time_zone="UTC",
        starts_at=clock[0] - timedelta(minutes=1),
        ends_at=clock[0] + timedelta(hours=1),
        accounts=[scope],
        total_cap_micros=50000000,
        per_plan_cap_micros=50000000,
        positive_change_cap_micros=5000000,
        action_limit=1,
        cooldown_seconds=60,
        freshness_seconds=300,
        aggressiveness_percent=10,
        allowed_purposes=["existing_campaign_optimize"],
        allowed_target_set_digest=native.budget_owner.target_set_digest(),
        campaign_and_creative_policy="new_exact_review_required",
        activation_policy="separate_exact_approval",
    )
    mandate = execution_mandates.revise(db, wid, policy, principal.user.id, runtime.initial.clock)
    execution_mandates.consent(
        db,
        wid,
        mandate.id,
        mandate.revision,
        policy.digest(),
        principal.user.id,
        runtime.initial.clock,
    )
    db.commit()
    selection = {"calibration_id": calibration_id, "observation_id": observation_id}
    result = alice.post(root + "/native-options", headers=headers(alice), json=selection)
    assert result.status_code == 200, result.text
    options = result.json()
    assert len(options["options"]) == 1 and len(options["mandates"]) >= 1
    chosen = {
        **selection,
        "choice": options["options"][0]["choice"],
        "mandate_id": mandate.id,
        "mandate_revision": mandate.revision,
    }
    clock[0] += timedelta(seconds=1)  # Stable choice across real rediscovery time.
    result = alice.post(root + "/previews", headers=headers(alice), json=chosen)
    assert result.status_code == 200, result.text
    value = result.json()
    assert value["schema_version"] == "inlet.initial-efficiency-preview.v2"
    assert value["before_budget_micros"] == 45000000 and value["after_budget_micros"] == 46000000
    assert len(server.posts) == 1  # Only the historical fixture's reviewed original action.
    return alice, provider, wid, principal, runtime, job, value, clock, native_requests, configured
