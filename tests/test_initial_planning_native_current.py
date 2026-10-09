"""Current V2 API equivalence; original V1 route remains at the authentic pin."""

import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from app.api.customer_initial_planning import get_initial_planning_runtime
from app.collectors.owned_meta_budget import owned_meta_budget_reader
from app.customers.models import CustomerSession
from app.initial_planning.models import PreviewRow
from app.initial_planning.planning_consent_models import PlanningConsentRow
from app.meta.models import MetaConnection
from app.planning_reporting.contracts import PlanningReportingProfileV1
from app.publication.execution_models import (
    ProviderExecutionAttempt,
    ProviderExecutionConsent,
    ProviderExecutionMandate,
    ProviderExecutionReceipt,
    ProviderExecutionResponse,
    ProviderExecutionReview,
    ProviderExposureReservation,
)
from app.reported_feedback.contracts import ReportedWindowPolicyV1
from app.settings import Settings, settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.native_planning_confirmation_fixture import confirmed_native_case
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


@pytest.mark.parametrize("change", [None, "session", "generation", "precision", "environment"])
def test_confirmed_native_preview_current_api(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    change: str | None,
) -> None:
    case = confirmed_native_case(
        customer_engine,
        configuration,
        tmp_path,
        monkeypatch,
        replicas,
        precision=change == "precision",
    )
    runtime = case.runtime
    assert runtime.profile
    if change == "environment":
        raw = runtime.profile.model_dump(mode="json")
        raw["environment"] = raw["initial"]["environment"] = raw["windows"]["environment"] = "live"
        if raw["feedback"]:
            raw["feedback"]["environment"] = "live"
            raw["feedback"]["comparison_policy_digest"] = ReportedWindowPolicyV1.model_validate(
                raw["windows"]
            ).digest()
        other = PlanningReportingProfileV1.model_validate(raw)
        runtime = replace(
            runtime,
            native_budget=lambda principal, provider: owned_meta_budget_reader(
                lambda: Session(customer_engine),
                principal,
                provider,
                other,
                settings,
                clock=case.runtime.clock,
            ),
        )
    case.client.app.dependency_overrides[get_initial_planning_runtime] = lambda: runtime

    def changed() -> None:
        with Session(customer_engine) as db:
            if change == "session":
                session = db.get(CustomerSession, case.session_digest)
                assert session
                session.revoked_at = int(time.time())
            else:
                source = db.scalar(
                    select(MetaConnection).where(MetaConnection.workspace_id == case.workspace_id)
                )
                assert source
                source.generation += 1
            db.commit()

    if change in {"session", "generation"}:
        case.control["callback"] = changed
    before = len(case.requests)
    response = case.client.post(
        case.root + "/previews", headers=headers(case.client), json=case.body
    )
    if change:
        assert response.status_code in {401, 409}, response.text
        if change == "precision":
            assert response.status_code == 409
            assert response.json()["detail"] == "native_budget_proposal_outside_consented_limits"
        if change == "environment":
            assert response.status_code == 409
            assert response.json()["detail"] == "native_budget_unavailable"
    else:
        assert response.status_code == 200, response.text
        value = response.json()
        assert value["schema_version"] == "inlet.initial-efficiency-preview.v2"
        assert (value["before_budget_micros"], value["after_budget_micros"]) == (10000000, 11000000)
        assert value["direction"] == "increase" and value["review_available"] is False
        assert "provider_acceptance_unverified" in value["reasons"]
        assert value["spending_authorized"] is False
    assert len(case.requests) == before if change == "environment" else len(case.requests) > before
    assert case.server.posts == []
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(PreviewRow)) == (0 if change else 1)
        assert db.scalar(select(func.count()).select_from(PlanningConsentRow)) == 1
        row = db.get(ProviderExecutionMandate, case.mandate_id)
        assert row and row.state == "draft"
        for model in (
            ProviderExecutionConsent,
            ProviderExecutionAttempt,
            ProviderExecutionReview,
            ProviderExecutionResponse,
            ProviderExecutionReceipt,
            ProviderExposureReservation,
        ):
            assert db.scalar(select(func.count()).select_from(model)) == 0
