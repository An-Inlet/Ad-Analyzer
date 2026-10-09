"""Current planning consent and genuine V1 previews over a scalar retained original."""

from collections.abc import Iterator
from dataclasses import dataclass, field, replace
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from app.collectors import owned_meta_budget
from app.executors.meta_optimization import MetaOptimizationTransport
from app.initial_planning import budget_mandates, calibration, native, native_budget, preview
from app.initial_planning.budget_mandate_contracts import (
    BudgetMandateCustomerIntentV1,
    BudgetMandateSelectionV1,
    ConsentBudgetMandateV1,
    PrepareBudgetMandateV1,
)
from app.initial_planning.contracts import InitialPreviewV1, ObservationV1, PreviewIntentV1
from app.initial_planning.planning_consent_models import PlanningConsentRow
from app.initial_planning.planning_consents import checked_planning_limits
from app.planning_reporting.contracts import PlanningReportingProfileV1
from app.planning_reporting.runtime import assemble_planning_reporting
from app.publication.contracts import fingerprint
from app.publication.customer_intents import account
from app.publication.customer_optimization_catalog import (
    ConfiguredOptimizationCatalog,
    NamedOptimizationTarget,
)
from app.publication.customer_optimization_contracts import (
    CustomerOptimizationRuntime,
    TargetChoice,
)
from app.publication.execution_models import (
    ProviderExecutionConsent,
    ProviderExecutionMandate,
    ProviderPeriodLedger,
)
from app.publication.optimization_contracts import (
    MoneyContext,
    OptimizationContext,
    OptimizationTarget,
)
from app.publication.optimization_execution_contracts import OptimizationRuntime
from app.reported_feedback.runtime import ReportedFeedbackRuntime
from app.settings import Settings, settings
from pydantic import SecretStr
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.reported_feedback_journey_fixture import acquired
from tests.reported_original_fixture import (
    RetainedReportedOriginalIds,
    prepare_reported_read,
)
from tests.reported_planning_original_fixture import ExpectedPlanningConfirmation
from tests.reported_planning_relative_fixture import retained_reported_planning_relative_fixture
from tests.reported_read_acquisition_fixture import (
    PreparedReportedAcquisition,
    prepare_reported_acquisition,
)
from tests.test_budget_mandate_contracts import operating_policy
from tests.test_customer_identity import FakeProvider
from tests.test_planning_reporting_configuration import profile
from tests.test_social_optimization_http import Server


@dataclass
class NativeWireReads:
    server: Server = field(default_factory=lambda: Server("meta_ads"))
    paths: list[str] = field(default_factory=list)

    def read(self, request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        self.paths.append(request.url.path)
        return self.server(request)

    def assert_read_only(self) -> None:
        assert self.paths and self.server.posts == []


@dataclass
class PlanningOrigin:
    ids: RetainedReportedOriginalIds
    expectation: ExpectedPlanningConfirmation
    native: NativeWireReads | None = None


@pytest.fixture()
def planning_origin(customer_engine: Engine, tmp_path: Path) -> Iterator[PlanningOrigin]:
    expectation = ExpectedPlanningConfirmation()
    with retained_reported_planning_relative_fixture(
        customer_engine, tmp_path / "original", expectation=expectation
    ) as (_, ids):
        origin = PlanningOrigin(ids, expectation)
        try:
            yield origin
        finally:
            if origin.native is not None:
                origin.native.assert_read_only()


def acquired_current(
    db: Session,
    configuration: Settings,
    path: Path,
    monkeypatch: pytest.MonkeyPatch,
    origin: PlanningOrigin,
) -> tuple[PreparedReportedAcquisition, ReportedFeedbackRuntime, ObservationV1]:
    prepared = prepare_reported_read(db, origin.ids)
    data = prepare_reported_acquisition(db, configuration, prepared, monkeypatch)
    actual, runtime, observation = acquired(db, configuration, path, monkeypatch, data=data)
    assert actual is data and data.original == origin.ids and origin.ids.original_post_count == 1
    return data, runtime, observation


def baseline_current(
    db: Session,
    acquisition: PreparedReportedAcquisition,
    runtime: ReportedFeedbackRuntime,
    observation: ObservationV1,
    origin: PlanningOrigin,
    path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[ReportedFeedbackRuntime, InitialPreviewV1, NativeWireReads]:
    assert origin.native is None
    ids = origin.ids
    engine = db.get_bind()
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
        lambda: Session(engine),
        configured,
        native_settings,
        clock=lambda: acquisition.clock[0],
    )
    runtime = replace(runtime, initial=bundle.initial)
    policy = operating_policy().model_copy(
        update={"planning_reporting_profile_digest": configured.digest()}
    )
    path = path / "budget-policy.json"
    path.write_text(policy.model_dump_json())
    monkeypatch.setattr(settings, "budget_mandate_policy_path", str(path))
    monkeypatch.setattr(settings, "budget_mandate_policy_digest", policy.digest())
    reads = NativeWireReads()
    reads.server.meta_campaign["daily_budget"] = "4500"
    origin.native = reads
    monkeypatch.setattr(
        owned_meta_budget, "native_budget_transport", lambda: httpx.MockTransport(reads.read)
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
    origin.expectation.bind(db, ids, principal, runtime.initial, result.mandate_id, result.revision)
    limits = checked_planning_limits(
        db, principal, provider, wid, result.mandate_id, result.revision, runtime.initial
    )
    scope = account(db, wid, acquisition.job.account_id)
    money = MoneyContext(
        currency="USD",
        currency_exponent=2,
        account_timezone="UTC",
        period_start=limits.starts_at,
        period_end=limits.ends_at,
    )
    target = OptimizationTarget(kind="campaign", external_id="5", campaign_id="5")
    adapter = MetaOptimizationTransport(transport=httpx.MockTransport(reads.read))
    context = OptimizationContext(
        scope=scope,
        access_token=SecretStr("offline-token"),
        expires_at=acquisition.clock[0] + timedelta(hours=1),
    )

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("Current V1 read cannot request financial qualification")

    execution = OptimizationRuntime(
        "contract_test", forbidden, forbidden, lambda _: context, meta=adapter
    )
    legacy_catalog = ConfiguredOptimizationCatalog(
        execution,
        (
            NamedOptimizationTarget(
                fingerprint("inlet.optimization-catalog-scope.v1", scope.model_dump(mode="json")),
                "Observed Campaign",
                "Owned Account",
                target,
                money,
                "e" * 32,
                1,
            ),
        ),
    )
    native_runtime = CustomerOptimizationRuntime(execution, legacy_catalog, runtime.initial.clock)
    runtime = replace(runtime, initial=replace(runtime.initial, native=native_runtime))
    actual = native.catalog(db, principal, provider, acquisition.request.objective, runtime.initial)
    assert len(actual.options) == 1
    assert (
        actual.options[0].state.budget_owner.target_set_digest() == limits.allowed_target_set_digest
    )
    intent = PreviewIntentV1(
        objective=acquisition.request.objective,
        calibration_id=report.id,
        observation_id=observation.id,
        mandate_id=result.mandate_id,
        mandate_revision=result.revision,
        choice=TargetChoice(
            goal_id=acquisition.request.objective.goal_id,
            goal_revision=acquisition.request.objective.goal_revision,
            account_id=acquisition.job.account_id,
            option_id=actual.options[0].identifier(actual.request),
        ),
    )
    db.commit()
    value = preview.prepare_preview(principal, provider, intent, runtime.initial)
    assert value.after_budget_micros == 46_000_000
    reads.assert_read_only()
    return runtime, value, reads
