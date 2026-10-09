"""Actual current V2 baseline to reported-feedback regression; explicit October lane."""

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from app.campaign_review.models import CampaignDraft
from app.collectors import owned_meta_budget
from app.initial_planning import (
    budget_mandates,
    calibration,
    native_budget,
    preview,
    preview_v2_service,
)
from app.initial_planning.api_contracts import NativeBudgetChoice, PreviewIntent
from app.initial_planning.budget_mandate_contracts import (
    BudgetMandateCustomerIntentV1,
    BudgetMandateSelectionV1,
    ConsentBudgetMandateV1,
    PrepareBudgetMandateV1,
)
from app.initial_planning.planning_consent_models import PlanningConsentRow
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
from app.reported_feedback.contracts import FeedbackPreviewIntentV1
from app.reported_feedback.models import ReportedFeedbackCurrent, ReportedFeedbackSlot
from app.reported_feedback.service import apply_feedback_preview, read_comparison
from app.settings import Settings, settings
from fastapi import HTTPException
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.reported_feedback_journey_fixture import acquired
from tests.reported_original_fixture import customer_engine as customer_engine
from tests.reported_original_fixture import (
    prepare_reported_read,
)
from tests.reported_planning_original_fixture import (
    ExpectedPlanningConfirmation,
    retained_reported_planning_original_fixture,
)
from tests.reported_read_acquisition_fixture import prepare_reported_acquisition
from tests.test_budget_mandate_contracts import operating_policy
from tests.test_customer_identity import FakeProvider
from tests.test_customer_identity import customer_engine as base_customer_engine  # noqa: F401
from tests.test_planning_reporting_configuration import profile
from tests.test_shopify_sales import configuration as configuration
from tests.test_social_optimization_http import Server


@pytest.mark.parametrize("mode", ["valid", "session", "planning_policy", "cap", "quantum"])
def test_actual_current_planning_baseline_allows_reported_preview_without_execution_consent(
    mode: str,
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Explicit October diagnostic: finite validity, never a default-collected test.
    assert datetime.now(UTC).strftime("%Y-%m") == "2026-10"
    expectation = ExpectedPlanningConfirmation()
    with (
        retained_reported_planning_original_fixture(
            customer_engine, tmp_path / "original", expectation=expectation
        ) as (_, ids),
        Session(customer_engine) as db,
    ):
        prepared = prepare_reported_read(db, ids)
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
        if mode == "quantum":
            runtime = replace(
                runtime,
                feedback_policy=runtime.feedback_policy.model_copy(
                    update={"maximum_preview_delta_micros": 2}
                ),
            )
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
        if mode == "cap":
            policy = type(policy).model_validate(
                policy.model_copy(
                    update={
                        "rules": tuple(
                            rule.model_copy(update={"per_plan_cap_micros": 46_000_000})
                            for rule in policy.rules
                        )
                    }
                ).model_dump()
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
        intent = preview_v2_service.resolve_intent(
            db,
            principal,
            provider,
            acquisition.request.objective,
            PreviewIntent(
                calibration_id=report.id,
                observation_id=observation.id,
                choice=NativeBudgetChoice(option_id=selection.native_option_id),
                mandate_id=result.mandate_id,
                mandate_revision=result.revision,
            ),
            runtime.initial,
        )
        db.commit()
        initial = preview_v2_service.prepare_preview(principal, provider, intent, runtime.initial)
        assert initial.after_budget_micros == 46_000_000
        assert (
            preview.read_preview(db, principal, provider, wid, initial.id, runtime.initial)
            == initial
        )
        comparison = read_comparison(db, principal, provider, wid, acquisition.job.id, runtime)
        if mode == "session":
            principal.session.revoked_at = int(acquisition.clock[0].timestamp())
            db.commit()
        elif mode == "planning_policy":
            monkeypatch.setattr(settings, "budget_mandate_policy_digest", "0" * 64)
        body = FeedbackPreviewIntentV1(comparison_id=comparison.id, baseline_preview_id=initial.id)
        if mode != "valid":
            with pytest.raises(HTTPException) as rejected:
                apply_feedback_preview(db, principal, provider, wid, body, runtime)
            assert rejected.value.status_code == (401 if mode == "session" else 409)
            if mode == "planning_policy":
                assert rejected.value.detail == "planning_confirmation_changed"
            elif mode == "cap":
                assert rejected.value.detail == "reported_feedback_nominal_plan_limit"
            elif mode == "quantum":
                assert rejected.value.detail == "reported_feedback_native_amount_unrepresentable"
            db.rollback()
            for model in (ReportedFeedbackSlot, ReportedFeedbackCurrent):
                assert db.scalar(select(func.count()).select_from(model)) == 0
        else:
            feedback = apply_feedback_preview(db, principal, provider, wid, body, runtime)
            db.commit()
            assert feedback.baseline_budget_micros == 46_000_000
            assert feedback.proposed_budget_micros == 47_000_000
        assert server.posts == []
