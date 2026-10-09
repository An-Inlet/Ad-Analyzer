"""Actual configured API/worker acquisition and native v2 producer, offline only."""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from app.api import customer_budget_mandates, customer_initial_planning, customer_reported_feedback
from app.collectors import owned_meta_budget
from app.commerce.sync import CommerceSyncService
from app.customers.access import SESSION_COOKIE, TTL_SECONDS, CustomerPrincipal, digest
from app.customers.models import CustomerSession, CustomerUser
from app.initial_planning import capture, native_budget
from app.initial_planning.contracts import EfficiencyObjectiveV1
from app.initial_planning.planning_consent_models import PlanningConsentRow
from app.meta.security import utc
from app.meta.sync import MetaSyncService, run_meta_tick
from app.planning_reporting import runtime as assembly
from app.planning_reporting.contracts import PlanningReportingProfileV1
from app.publication.execution_models import (
    ProviderExecutionConsent,
    ProviderExecutionMandate,
    ProviderPeriodLedger,
)
from app.reported_feedback.contracts import ReportedAcquisitionRequestV1
from app.reported_feedback.models import ReportedFeedbackJob
from app.reported_feedback.runtime import ReportedFeedbackRuntime
from app.settings import Settings, settings
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.reported_original_fixture import prepare_reported_read
from tests.reported_planning_journey_fixture import NativeWireReads, PlanningOrigin
from tests.reported_read_acquisition_fixture import prepare_reported_acquisition
from tests.test_budget_mandate_contracts import operating_policy
from tests.test_commerce_measurement import FakeMeasurement
from tests.test_customer_identity import FakeProvider, login
from tests.test_customer_optimization_api import headers
from tests.test_planning_reporting_configuration import profile


def configured_journey(
    db: Session,
    engine: Engine,
    configuration: Settings,
    path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    *,
    origin: PlanningOrigin,
) -> tuple[
    TestClient,
    FakeProvider,
    int,
    CustomerPrincipal,
    ReportedFeedbackRuntime,
    ReportedFeedbackJob,
    dict[str, Any],
    list[datetime],
    list[httpx.Request],
    PlanningReportingProfileV1,
]:
    alice, _, provider = replicas
    prepared = prepare_reported_read(db, origin.ids)
    data = prepare_reported_acquisition(db, configuration, prepared, monkeypatch)
    wid, principal, _, old_job, acquisition, source, clock, old_runner, _, control, _ = data
    original_subject = principal.user.subject
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
    assert login(alice, origin.ids.actor_id + ":first") == origin.ids.actor_id
    user = db.get(CustomerUser, origin.ids.actor_id, populate_existing=True)
    session = db.get(CustomerSession, digest(alice.cookies[SESSION_COOKIE]))
    assert user and user.subject == original_subject and session
    assert session.user_id == user.id and session.digest != origin.ids.session_digest
    assert session.expires_at - session.created_at == TTL_SECONDS
    alice.app.include_router(customer_budget_mandates.router)
    assert customer_budget_mandates.get_budget_mandate_policy not in alice.app.dependency_overrides
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
    assert original_user.id == origin.ids.actor_id
    assert original_session.digest == session.digest
    principal = CustomerPrincipal(original_user, original_session)
    request = ReportedAcquisitionRequestV1.model_validate(job.document)
    assert request.before == acquisition.before and request.after == acquisition.after
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
    assert source.last_sync_at is not None
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
    reads = NativeWireReads()
    reads.server.meta_campaign["daily_budget"] = "4500"
    origin.native = reads

    def wire(outgoing: httpx.Request) -> httpx.Response:
        assert outgoing.method == "GET"
        native_requests.append(outgoing)
        return reads.read(outgoing)

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
    assert len(catalog.options) == 1
    policy = operating_policy().model_copy(
        update={"planning_reporting_profile_digest": configured.digest()}
    )
    policy_path = path / "budget-policy.json"
    policy_path.write_text(policy.model_dump_json())
    monkeypatch.setattr(settings, "budget_mandate_policy_path", str(policy_path))
    monkeypatch.setattr(settings, "budget_mandate_policy_digest", policy.digest())
    budget_selection = {
        "calibration_id": calibration_id,
        "observation_id": observation_id,
        "native_option_id": catalog.options[0].identifier(),
    }
    db.commit()
    result = alice.post(
        root + "/budget-mandates",
        headers=headers(alice),
        json={
            "intent": {
                "selection": budget_selection,
                "total_cap_micros": 50000000,
                "aggressiveness": "balanced",
            }
        },
    )
    assert result.status_code == 201, result.text
    prepared_budget = result.json()
    result = alice.post(
        root + "/budget-mandates/" + prepared_budget["mandate_id"] + "/consent",
        headers=headers(alice),
        json={
            "selection": budget_selection,
            "expected_revision": prepared_budget["revision"],
            "policy_digest": prepared_budget["policy_digest"],
            "preparation_digest": prepared_budget["preparation_digest"],
        },
    )
    assert result.status_code == 200, result.text
    assert result.json()["state"] == "confirmed"
    mandate = db.get(
        ProviderExecutionMandate, prepared_budget["mandate_id"], populate_existing=True
    )
    original = db.get(ProviderExecutionMandate, origin.ids.mandate_id)
    assert mandate and original and mandate.state == "draft"
    assert mandate.ledger_id == original.ledger_id
    assert db.scalar(select(func.count()).select_from(ProviderPeriodLedger)) == 1
    assert db.scalar(select(func.count()).select_from(PlanningConsentRow)) == 1
    assert (
        db.scalar(
            select(ProviderExecutionConsent).where(
                ProviderExecutionConsent.mandate_id == mandate.id
            )
        )
        is None
    )
    origin.expectation.bind(
        db, origin.ids, principal, runtime.initial, mandate.id, mandate.revision
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
    assert origin.ids.original_post_count == 1 and reads.server.posts == []
    return alice, provider, wid, principal, runtime, job, value, clock, native_requests, configured
