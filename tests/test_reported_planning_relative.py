"""Durable relative-source current acquisition and planning confirmation acceptance."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from app.campaign_review.models import CampaignDraft
from app.collectors import owned_meta_budget
from app.goals import service as goals
from app.goals.models import Goal
from app.goals.schemas import GoalDefinition
from app.initial_planning import budget_mandates, calibration, native_budget
from app.initial_planning.budget_mandate_contracts import (
    BudgetMandateCustomerIntentV1,
    BudgetMandateSelectionV1,
    ConsentBudgetMandateV1,
    PrepareBudgetMandateV1,
)
from app.initial_planning.planning_consent_models import PlanningConsentRow
from app.meta.security import utc
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
from app.settings import Settings, settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.reported_feedback_journey_fixture import acquired
from tests.reported_original_fixture import customer_engine as customer_engine
from tests.reported_original_fixture import (
    prepare_reported_read,
)
from tests.reported_planning_original_fixture import ExpectedPlanningConfirmation
from tests.reported_planning_relative_fixture import retained_reported_planning_relative_fixture
from tests.reported_read_acquisition_fixture import prepare_reported_acquisition
from tests.test_budget_mandate_contracts import operating_policy
from tests.test_customer_identity import FakeProvider
from tests.test_customer_identity import customer_engine as base_customer_engine  # noqa: F401
from tests.test_planning_reporting_configuration import profile
from tests.test_shopify_sales import configuration as configuration
from tests.test_social_optimization_http import Server


def test_coherent_original_allows_actual_current_planning_confirmation(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started_on = datetime.now(UTC).date()
    expectation = ExpectedPlanningConfirmation()
    with (
        retained_reported_planning_relative_fixture(
            customer_engine, tmp_path / "original", expectation=expectation
        ) as (_, ids),
        Session(customer_engine) as db,
    ):
        prepared = prepare_reported_read(db, ids)
        assert prepared.progress.next_due_at is not None
        assert prepared.progress.next_due_at <= datetime.now(UTC)
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
        goal = db.get(Goal, ids.goal_id)
        assert goal and goal.confirmed_preview_id is not None
        # Historical commerce frontier is stale until the actual current importer runs.
        assert goals.assessment(db, goal, acquisition.clock[0]) == "baseline_unavailable"
        revision = goals.current(db, goal)
        definition = GoalDefinition.model_validate(revision.definition)
        assert revision.confirmed_at is not None and attempt.dispatched_at is not None
        assert utc(revision.confirmed_at) <= utc(attempt.dispatched_at)
        assert started_on - timedelta(days=15) <= utc(attempt.dispatched_at).date() <= (
            datetime.now(UTC).date() - timedelta(days=15)
        )
        assert definition.baseline_window.end <= utc(attempt.dispatched_at).date()
        assert definition.target_window.start > started_on
        assert definition.budget_micros == 50_000_000
        assert definition.target_micros == 100_000_000
        assert db.scalar(select(func.count()).select_from(CampaignDraft)) == 0
        assert ids.original_post_count == 1
        _, runtime, observation = acquired(
            db, configuration, tmp_path, monkeypatch, data=acquisition
        )
        assert goals.assessment(db, goal, acquisition.clock[0]) == "confirmed"
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
        assert ledger.starts_at.date() == definition.budget_start
        assert ledger.ends_at.date() == definition.budget_end
        assert ledger.starts_at.date() <= datetime.now(UTC).date() < ledger.ends_at.date()
        assert goals.baseline(db, goal, definition, acquisition.clock[0])["net_sales_micros"] == (
            90_000_000
        )
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
