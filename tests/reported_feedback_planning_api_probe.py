"""Actual current V2 baseline to reported-feedback regression; explicit October lane."""

import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from app.api import customer as customer_api
from app.api import customer_initial_planning as initial_api
from app.api import customer_reported_feedback as feedback_api
from app.campaign_review.models import CampaignDraft
from app.collectors import owned_meta_budget
from app.customers import access as customer_access
from app.customers.access import SESSION_COOKIE, TTL_SECONDS, CustomerPrincipal, digest
from app.customers.identity import verified_identity
from app.customers.models import CustomerSession, CustomerUser
from app.initial_planning import (
    budget_mandates,
    calibration,
    native_budget,
    preview,
)
from app.initial_planning.api_contracts import NativeBudgetChoice, PreviewIntent
from app.initial_planning.budget_mandate_contracts import (
    BudgetMandateCustomerIntentV1,
    BudgetMandateSelectionV1,
    ConsentBudgetMandateV1,
    PrepareBudgetMandateV1,
)
from app.initial_planning.planning_consent_models import PlanningConsentRow
from app.initial_planning.preview_v2 import InitialPreviewV2
from app.initial_planning.runtime import InitialPlanningRuntime
from app.planning_reporting.contracts import PlanningReportingProfileV1
from app.planning_reporting.runtime import assemble_planning_reporting
from app.publication.execution_models import (
    ProviderExecutionAttempt,
    ProviderExecutionConsent,
    ProviderExecutionMandate,
    ProviderExecutionReceipt,
    ProviderExecutionReview,
    ProviderExecutionRun,
    ProviderPeriodLedger,
)
from app.reported_feedback.contracts import (
    ComparisonIntentV1,
    ComparisonProgressV1,
    FeedbackPreviewIntentV1,
    OperationalReportedComparisonV1,
)
from app.reported_feedback.models import ReportedFeedbackCurrent, ReportedFeedbackSlot
from app.reported_feedback.runtime import ReportedFeedbackRuntime, get_reported_feedback_runtime
from app.settings import Settings, settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.reported_feedback_fixture import window_policy
from tests.reported_feedback_journey_fixture import acquired
from tests.reported_original_fixture import (
    PreparedReportedRead,
)
from tests.reported_original_fixture import customer_engine as customer_engine
from tests.reported_planning_original_fixture import (
    ExpectedPlanningConfirmation,
    retained_reported_planning_original_fixture,
)
from tests.reported_read_acquisition_fixture import prepare_reported_acquisition
from tests.test_budget_mandate_contracts import operating_policy
from tests.test_customer_identity import FakeProvider, login
from tests.test_customer_identity import customer_engine as base_customer_engine  # noqa: F401
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_planning_reporting_configuration import profile
from tests.test_shopify_sales import configuration as configuration
from tests.test_social_optimization_http import Server


def issue_at(client: Any, provider: FakeProvider, subject: str, now: datetime) -> None:
    stamp = int(now.timestamp())
    project = provider.issuer.rsplit("/", 1)[1]
    real_time = time.time

    def verify(token: str) -> Any:
        assert token == f"reported-planning-{stamp}"
        provider.check_active(subject, stamp)
        return verified_identity(
            dict(
                iss=provider.issuer,
                aud=project,
                sub=subject,
                email="same@example.test",
                email_verified=True,
                auth_time=stamp,
                iat=stamp,
                exp=stamp + 3600,
            ),
            project,
            stamp,
        )

    with pytest.MonkeyPatch.context() as issuance:
        issuance.setattr(customer_api, "time", SimpleNamespace(time=lambda: stamp))
        issuance.setattr(provider, "verify", verify)
        assert login(client, f"reported-planning-{stamp}") == subject
        assert time.time is real_time
    assert vars(customer_api)["time"] is time


@pytest.mark.parametrize("mode", ["valid", "session", "planning_policy"])
def test_authenticated_current_planning_baseline_to_feedback(
    replicas: Any,
    mode: str,
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Explicit October diagnostic: finite validity, never a default-collected test.
    assert datetime.now(UTC).strftime("%Y-%m") == "2026-10"
    expectation = ExpectedPlanningConfirmation()
    clock = [datetime.now(UTC)]
    with (
        retained_reported_planning_original_fixture(
            customer_engine, tmp_path / "original", expectation=expectation
        ) as (_, ids),
        pytest.MonkeyPatch.context() as request_clock,
        Session(customer_engine) as db,
    ):
        alice, _, provider = replicas
        assert login(alice, ids.actor_id + ":first") == ids.actor_id
        user = db.get(CustomerUser, ids.actor_id)
        session = db.get(CustomerSession, digest(alice.cookies[SESSION_COOKIE]))
        assert user and session and session.digest != ids.session_digest
        principal = CustomerPrincipal(user, session)
        runtime = ReportedFeedbackRuntime(
            initial=InitialPlanningRuntime(
                session_factory=lambda: Session(customer_engine), clock=lambda: clock[0]
            ),
            window_policy=window_policy(),
        )
        alice.app.include_router(feedback_api.router)
        alice.app.include_router(initial_api.router)
        alice.app.dependency_overrides[get_reported_feedback_runtime] = lambda: runtime
        alice.app.dependency_overrides[initial_api.get_initial_planning_runtime] = lambda: (
            runtime.initial
        )
        root = f"/api/customer/v1/workspaces/{ids.workspace_id}"
        request_intent = ComparisonIntentV1(
            attempt_id=ids.attempt_id,
            goal_id=ids.goal_id,
            goal_revision=ids.goal_revision,
            maximum_reported_cpa_micros=100_000_000,
        )
        db.rollback()
        response = alice.post(
            root + "/reported-feedback/comparisons",
            headers=headers(alice),
            json=request_intent.model_dump(mode="json"),
        )
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        progress = ComparisonProgressV1.model_validate(response.json())
        assert progress.next_due_at is not None
        first_job = progress.id
        old_session_digest = session.digest
        assert session.expires_at < progress.next_due_at.timestamp()
        clock[0] = progress.next_due_at + timedelta(seconds=1)
        request_clock.setattr(
            customer_access, "time", SimpleNamespace(time=lambda: clock[0].timestamp())
        )
        assert alice.get("/api/customer/v1/session").status_code == 401
        issue_at(alice, provider, ids.actor_id, clock[0])
        db.rollback()
        user = db.get(CustomerUser, ids.actor_id)
        session = db.get(CustomerSession, digest(alice.cookies[SESSION_COOKIE]))
        assert user and session and session.digest not in {old_session_digest, ids.session_digest}
        assert session.expires_at - session.created_at == TTL_SECONDS
        principal = CustomerPrincipal(user, session)
        db.rollback()
        response = alice.post(
            root + "/reported-feedback/comparisons",
            headers=headers(alice),
            json=request_intent.model_dump(mode="json"),
        )
        assert response.status_code == 200, response.text
        progress = ComparisonProgressV1.model_validate(response.json())
        assert progress.id != first_job
        prepared = PreparedReportedRead(
            ids.workspace_id, principal, provider, runtime, request_intent, progress, clock, ids
        )
        acquisition = prepare_reported_acquisition(db, configuration, prepared, monkeypatch)
        anchor = acquisition.request.anchor
        review = db.get(ProviderExecutionReview, ids.review_id)
        run = db.get(ProviderExecutionRun, ids.run_id)
        attempt = db.get(ProviderExecutionAttempt, ids.attempt_id)
        receipt = db.get(ProviderExecutionReceipt, ids.receipt_id)
        assert review and run and attempt and receipt
        assert (
            run.review_id == review.id
            and attempt.run_id == run.id
            and receipt.attempt_id == attempt.id
        )
        assert (
            anchor.original_attempt_id == ids.attempt_id
            and anchor.latest_receipt_id == ids.receipt_id
        )
        assert anchor.original_plan_digest == review.plan_digest
        assert (
            anchor.before_budget_micros == 50_000_000 and anchor.after_budget_micros == 45_000_000
        )
        assert db.scalar(select(func.count()).select_from(CampaignDraft)) == 0
        assert ids.original_post_count == 1
        _, runtime, observation = acquired(
            db, configuration, tmp_path, monkeypatch, data=acquisition
        )
        assert runtime.initial.configuration and runtime.window_policy and runtime.feedback_policy
        configured = PlanningReportingProfileV1.model_validate(
            profile()
            .model_copy(
                update={
                    "initial": runtime.initial.configuration,
                    "windows": runtime.window_policy,
                    "feedback": runtime.feedback_policy,
                }
            )
            .model_dump()
        )
        native_settings = acquisition.runner.settings
        bundle = assemble_planning_reporting(
            lambda: Session(customer_engine),
            configured,
            native_settings,
            clock=lambda: acquisition.clock[0],
        )
        runtime = replace(runtime, initial=bundle.initial)
        policy = operating_policy().model_copy(
            update={"planning_reporting_profile_digest": configured.digest()}
        )
        path = tmp_path / "budget-policy.json"
        path.write_text(policy.model_dump_json())
        monkeypatch.setattr(settings, "budget_mandate_policy_path", str(path))
        monkeypatch.setattr(settings, "budget_mandate_policy_digest", policy.digest())
        server = Server("meta_ads")
        server.meta_campaign["daily_budget"] = "4500"
        wires: list[str] = []

        def wire(request: httpx.Request) -> httpx.Response:
            assert request.method == "GET"
            wires.append(request.url.path)
            return server(request)

        monkeypatch.setattr(
            owned_meta_budget, "native_budget_transport", lambda: httpx.MockTransport(wire)
        )
        principal, provider, wid = acquisition.principal, FakeProvider(), ids.workspace_id
        report = calibration.run_calibration(
            db, principal, provider, acquisition.request.objective, runtime.initial
        )
        assert report.status == "evaluated"
        db.commit()
        catalog = native_budget.catalog(
            db, principal, provider, acquisition.request.objective, runtime.initial
        )
        assert len(catalog.options) == 1
        selection = BudgetMandateSelectionV1(
            calibration_id=report.id,
            observation_id=observation.id,
            native_option_id=catalog.options[0].identifier(),
        )
        result = budget_mandates.prepare_budget_mandate(
            db,
            wid,
            principal,
            provider,
            PrepareBudgetMandateV1(
                intent=BudgetMandateCustomerIntentV1(
                    selection=selection,
                    total_cap_micros=50000000,
                    aggressiveness="balanced",
                )
            ),
            runtime.initial,
            policy,
        )
        draft = db.get(ProviderExecutionMandate, result.mandate_id)
        assert draft and draft.state == "draft"
        ledger = db.get(ProviderPeriodLedger, draft.ledger_id)
        assert ledger and ledger.action_count == 1 and ledger.spent_high_water_micros == 0
        assert ledger.starts_at.strftime("%Y-%m-%d") == "2026-10-01"
        original = db.get(ProviderExecutionMandate, ids.mandate_id)
        assert original and original.ledger_id == draft.ledger_id
        assert db.scalar(select(func.count()).select_from(ProviderPeriodLedger)) == 1
        result = budget_mandates.consent_budget_mandate(
            db,
            wid,
            principal,
            provider,
            result.mandate_id,
            ConsentBudgetMandateV1(
                selection=selection,
                expected_revision=result.revision,
                policy_digest=result.policy_digest,
                preparation_digest=result.preparation_digest,
            ),
            runtime.initial,
            policy,
        )
        assert result.state == "confirmed"
        assert (
            db.scalar(
                select(ProviderExecutionConsent).where(
                    ProviderExecutionConsent.mandate_id == result.mandate_id,
                    ProviderExecutionConsent.revision == result.revision,
                )
            )
            is None
        )
        assert db.scalar(select(func.count()).select_from(PlanningConsentRow)) == 1
        expectation.bind(db, ids, principal, runtime.initial, result.mandate_id, result.revision)
        assert wires and server.posts == []
        body = PreviewIntent(
            calibration_id=report.id,
            observation_id=observation.id,
            choice=NativeBudgetChoice(option_id=selection.native_option_id),
            mandate_id=result.mandate_id,
            mandate_revision=result.revision,
        )
        db.rollback()
        response = alice.post(
            root + "/initial-planning/previews",
            headers=headers(alice),
            json=body.model_dump(mode="json"),
        )
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        initial = InitialPreviewV2.model_validate(response.json())
        assert initial.after_budget_micros == 46_000_000
        assert (
            preview.read_preview(db, principal, provider, wid, initial.id, runtime.initial)
            == initial
        )
        request_id = acquisition.job.id
        db.rollback()
        observed = alice.get(root + f"/reported-feedback/comparisons/{request_id}")
        assert observed.status_code == 200, observed.text
        assert observed.headers["cache-control"] == "no-store"
        comparison = OperationalReportedComparisonV1.model_validate(observed.json())
        if mode == "session":
            principal.session.revoked_at = int(acquisition.clock[0].timestamp())
            db.commit()
        elif mode == "planning_policy":
            monkeypatch.setattr(settings, "budget_mandate_policy_digest", "0" * 64)
        feedback_body = FeedbackPreviewIntentV1(
            comparison_id=comparison.id, baseline_preview_id=initial.id
        )
        db.rollback()
        response = alice.post(
            root + "/reported-feedback/previews",
            headers=headers(alice),
            json=feedback_body.model_dump(mode="json"),
        )
        if mode != "valid":
            assert response.status_code == (401 if mode == "session" else 409), response.text
            if mode == "planning_policy":
                assert response.json()["detail"] == "planning_confirmation_changed"
            for model in (ReportedFeedbackSlot, ReportedFeedbackCurrent):
                assert db.scalar(select(func.count()).select_from(model)) == 0
        else:
            assert response.status_code == 200, response.text
            assert response.headers["cache-control"] == "no-store"
            assert response.json()["baseline_budget_micros"] == 46_000_000
            assert response.json()["proposed_budget_micros"] == 47_000_000
        assert server.posts == []
    assert vars(customer_access)["time"] is time
