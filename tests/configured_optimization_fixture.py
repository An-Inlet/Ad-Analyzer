"""Ordinary API composition with explicit offline evidence and actual provider HTTP."""

from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from app.ads.models import AdvertisingAccount
from app.api.customer_optimization import router
from app.customers.access import SESSION_COOKIE, digest
from app.customers.models import CustomerSession
from app.goals import service as goals
from app.goals.models import Goal
from app.goals.schemas import ConfirmInput, GoalDefinition
from app.production_runtime import optimization_assembly as assembly
from app.production_runtime.optimization_contracts import (
    OptimizationEvidenceDescriptor,
    OptimizationExecutionEvidence,
    RegisteredOptimizationEvidenceSource,
)
from app.production_runtime.optimization_policy_contracts import OptimizationOperatingPolicyV1
from app.publication import execution_mandates
from app.publication.execution_contracts import ExposureEvidence
from app.publication.execution_models import (
    ProviderExecutionMandate,
    ProviderExecutionReview,
    ProviderExposureReservation,
)
from app.publication.optimization_execution_contracts import OptimizationQualification
from app.settings import Settings, settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.google_runtime_fixture import configured_customer
from tests.meta_runtime_fixture import configured_meta_customer
from tests.test_commerce_measurement import NOW
from tests.test_optimization_runtime_contracts import manifest, policy
from tests.test_owned_optimization_catalog import Wire


def configured(
    engine: Engine,
    config: Settings,
    path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    platform: str,
) -> Any:
    if engine.dialect.name == "sqlite":
        with engine.connect() as c:
            c.exec_driver_sql("PRAGMA foreign_keys=ON")
            c.commit()
    bootstrap = configured_customer if platform == "google_ads" else configured_meta_customer
    alice, base, *_ = bootstrap(engine, config, path, monkeypatch, replicas)
    wid = int(base.split("/workspaces/")[1].split("/")[0])
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(ProviderExecutionMandate)) == 0
        assert db.scalar(select(func.count()).select_from(ProviderExecutionReview)) == 0
        goal = db.scalar(select(Goal).where(Goal.workspace_id == wid))
        account = db.scalar(
            select(AdvertisingAccount).where(
                AdvertisingAccount.workspace_id == wid, AdvertisingAccount.platform == platform
            )
        )
        assert goal and account
        session = db.get(CustomerSession, digest(alice.cookies[SESSION_COOKIE]))
        assert session
        definition = GoalDefinition.model_validate(goals.current(db, goal).definition)
        goals.revise(
            db,
            goal,
            definition.model_copy(update={"budget_start": NOW.date()}),
            session.user_id,
            NOW,
        )
        preview = goals.preview(db, goal, NOW)
        goals.confirm(
            db,
            goal,
            ConfirmInput(
                expected_revision=goal.revision,
                preview_id=preview.id,
                idempotency_key="configured-optimization-goal",
            ),
            NOW,
            actor_id=session.user_id,
        )
        db.commit()
        query = dict(goal_id=goal.id, goal_revision=goal.revision, account_id=account.id)
    raw = policy().model_dump()
    for rule in raw["rules"]:
        rule.update(
            per_plan_cap_micros=50_000_000,
            positive_change_cap_micros=10_000_000,
            action_limit=10,
            freshness_seconds=120,
        )
    operating = OptimizationOperatingPolicyV1.model_validate(raw)
    selected = manifest().model_copy(
        update={
            "operating_policy_digest": operating.digest(),
            "replacement_enabled": False,
            "settlement_enabled": False,
        }
    )
    mp, pp = path / "optimization-manifest.json", path / "optimization-policy.json"
    mp.write_text(selected.model_dump_json())
    pp.write_text(operating.model_dump_json())
    monkeypatch.setattr(settings, "optimization_execution_manifest_path", str(mp))
    monkeypatch.setattr(settings, "optimization_execution_manifest_digest", selected.digest())
    monkeypatch.setattr(settings, "optimization_operating_policy_path", str(pp))
    descriptor = OptimizationEvidenceDescriptor(
        source_id=selected.evidence_source_id,
        profile_digest=selected.evidence_profile_digest,
        environment="contract_test",
        kind="contract_scenario",
        providers=selected.providers,
    )
    control: dict[str, Any] = {"opened": 0, "closed": 0, "factory": 0, "admissions": []}
    control["now"] = NOW
    control["qualification_revision"] = 1
    monkeypatch.setattr(assembly, "utc_now", lambda: control["now"])
    wire = Wire(platform)
    if platform == "meta_ads":
        wire.meta.meta_campaign["account_id"] = "1234567890"
        wire.meta.meta_child["account_id"] = "1234567890"

    def build(
        sessions: Any, authorize: Any, actor: str, clock: Any
    ) -> OptimizationExecutionEvidence:
        control["factory"] += 1

        def admission(request: Any, candidate: Any, now: Any) -> OptimizationQualification:
            control["admissions"].append(candidate)
            return OptimizationQualification(
                environment="contract_test",
                scope=request.request.scope,
                target=candidate.target,
                money=request.money,
                qualification_id="c" * 32,
                qualification_revision=control["qualification_revision"],
                profile="explicit_offline_only",
                allowed_operations=["google_budget_set_v1", "google_status_set_v1"]
                if platform == "google_ads"
                else ["meta_budget_set_v1", "meta_status_set_v1"],
                observed_at=now,
                expires_at=now + timedelta(seconds=120),
                evidence_digest="d" * 64,
                unresolved=[],
            )

        def qualification(
            db: Session, binding: Any, scope: Any, target: Any, now: Any
        ) -> OptimizationQualification:
            authorize(db, wid, actor)
            _, current = execution_mandates.checked(db, wid, binding, actor, clock)
            from app.publication.optimization_contracts import MoneyContext

            return OptimizationQualification(
                environment="contract_test",
                scope=scope,
                target=target,
                money=MoneyContext(
                    currency=current.currency,
                    currency_exponent=2,
                    account_timezone=current.time_zone,
                    period_start=current.starts_at,
                    period_end=current.ends_at,
                ),
                qualification_id="c" * 32,
                qualification_revision=control["qualification_revision"],
                profile="explicit_offline_only",
                allowed_operations=["google_budget_set_v1", "google_status_set_v1"]
                if platform == "google_ads"
                else ["meta_budget_set_v1", "meta_status_set_v1"],
                observed_at=now,
                expires_at=now + timedelta(seconds=120),
                evidence_digest="d" * 64,
                unresolved=[],
            )

        def exposure(db: Session, intent: Any, state: Any, q: Any, now: Any) -> ExposureEvidence:
            authorize(db, wid, actor)
            _, current = execution_mandates.checked(db, wid, intent.mandate, actor, clock)
            held = int(
                db.scalar(
                    select(
                        func.coalesce(func.sum(ProviderExposureReservation.amount_micros), 0)
                    ).where(
                        ProviderExposureReservation.workspace_id == wid,
                        ProviderExposureReservation.state == "held",
                    )
                )
                or 0
            )
            return ExposureEvidence(
                environment="contract_test",
                mandate=intent.mandate,
                account=intent.scope,
                covered_account_ids=[intent.scope.account.account_id],
                budget_owner_key=intent.budget_owner.key(intent.scope),
                target_set_digest=intent.approved_target_set_digest,
                state_digest=state.digest(),
                currency=current.currency,
                period_start=current.starts_at,
                period_end=current.ends_at,
                observed_at=now,
                expires_at=now + timedelta(seconds=120),
                reporting_watermark=now,
                completeness="complete",
                qualification_id=q.qualification_id,
                model_version="explicit_offline_only",
                cap_semantics="contract_scenario",
                reported_spend_micros=0,
                unreported_upper_micros=0,
                unchanged_future_upper_micros=0,
                proposed_owner_upper_micros=40_000_000,
                existing_reservations_micros=held,
                portfolio_upper_micros=held + 40_000_000,
            )

        return OptimizationExecutionEvidence(
            descriptor, admission, qualification, exposure, None, None
        )

    registration = RegisteredOptimizationEvidenceSource(descriptor, build)
    monkeypatch.setattr(
        assembly,
        "registered_optimization_evidence",
        lambda name: registration if name == descriptor.source_id else None,
    )

    def dispatch(request: httpx.Request) -> httpx.Response:
        callback = control.pop("callback", None)
        if callback:
            callback()
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(
                200,
                json={"access_token": "offline-token", "expires_in": 3600, "token_type": "Bearer"},
            )
        if platform == "google_ads" and not request.url.path.endswith("googleAds:search"):
            return wire.google(request)
        if platform == "meta_ads":
            path = request.url.path
            if path == "/v26.0/act_1234567890":
                return httpx.Response(
                    200,
                    json={
                        "account_id": "1234567890",
                        "currency": "USD",
                        "timezone_name": "UTC",
                        "account_status": 1,
                    },
                )
            if path == "/v26.0/act_1234567890/campaigns":
                return httpx.Response(200, json={"data": [wire.meta.meta_campaign]})
            if path == "/v26.0/act_1234567890/adsets":
                return httpx.Response(200, json={"data": [wire.meta.meta_child]})
            if path == "/v26.0/5/adsets":
                return httpx.Response(
                    200,
                    json={"data": [{"id": "6", "account_id": "1234567890", "campaign_id": "5"}]},
                )
        return wire(request)

    class Transport(httpx.MockTransport):
        def close(self) -> None:
            control["closed"] += 1
            super().close()

    def transport(_: Any) -> httpx.BaseTransport:
        control["opened"] += 1
        return Transport(dispatch)

    monkeypatch.setattr(assembly, "optimization_execution_transport", transport)
    alice.app.include_router(router)
    return alice, base, query, wire, control
