"""Ordinary API composition with explicit offline evidence and actual provider HTTP."""

from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from app.api.customer_execution import router as execution_router
from app.api.customer_optimization import router
from app.customers.access import SESSION_COOKIE, digest
from app.customers.models import CustomerSession
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
    ProviderExposureReservation,
)
from app.publication.optimization_execution_contracts import OptimizationQualification
from app.settings import Settings, settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_optimization_runtime_contracts import manifest, policy
from tests.test_owned_optimization_catalog import Wire


def configured_current_optimization(
    engine: Engine,
    config: Settings,
    path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    ids: Any,
) -> Any:
    import base64

    from pydantic import SecretStr

    from tests.test_customer_identity import login

    wid = ids.workspace_id
    platform = ids.platform
    alice = replicas[0]
    monkeypatch.setattr(settings, "google_customer_client_id", "offline-client")
    monkeypatch.setattr(settings, "google_customer_client_secret", SecretStr("offline-secret"))
    monkeypatch.setattr(
        settings,
        "google_customer_encryption_key",
        SecretStr(base64.urlsafe_b64encode(b"g" * 32).decode()),
    )
    monkeypatch.setattr(
        settings,
        "meta_token_encryption_key",
        SecretStr(base64.urlsafe_b64encode(b"m" * 32).decode()),
    )
    with Session(engine) as db:
        old = set(db.scalars(select(CustomerSession.digest)))
    assert (
        login(
            alice,
            ("configured-google" if platform == "google_ads" else "configured-meta")
            + ":current-candidate",
        )
        == ids.actor_id
    )
    with Session(engine) as db:
        token = digest(alice.cookies[SESSION_COOKIE])
        row = db.get(CustomerSession, token)
        assert row and row.user_id == ids.actor_id and token not in old
    base = f"/api/customer/v1/workspaces/{ids.workspace_id}/execution"
    query = dict(goal_id=ids.goal_id, goal_revision=ids.goal_revision, account_id=ids.account_id)
    raw = policy().model_dump()
    for rule in raw["rules"]:
        rule.update(
            per_plan_cap_micros=50_000_000,
            positive_change_cap_micros=10_000_000,
            action_limit=10,
            freshness_seconds=120,
        )
    operating = OptimizationOperatingPolicyV1.model_validate(raw)
    assert operating.digest() == ids.operating_policy_digest
    selected = manifest().model_copy(
        update={
            "operating_policy_digest": operating.digest(),
            "replacement_enabled": False,
            "settlement_enabled": False,
        }
    )
    assert selected.digest() == ids.optimization_manifest_digest
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
    alice.app.include_router(execution_router)
    alice.app.include_router(router)
    return alice, base, query, wire, control
