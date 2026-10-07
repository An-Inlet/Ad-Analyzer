"""Actual configured API/job worker with native HTTP mocks, no seeded candidates."""

from pathlib import Path
from typing import Any

import pytest
from app.api import customer_candidates
from app.commerce.models import CommerceStore
from app.commerce.sync import CommerceSyncService
from app.customers import identity
from app.jobs.customer_runtime import run_customer_tick
from app.optimization_candidates.models import CandidateJob, CandidateResult
from app.production_runtime import candidate_assembly
from app.production_runtime.candidate_configuration import (
    CandidateAssemblyManifestV1,
    CandidateEvidenceDescriptorV1,
    CandidatePolicyBundleV1,
    FrozenCandidatePolicy,
)
from app.production_runtime.candidate_sources import (
    CandidateEvidenceBinding,
    RegisteredCandidateEvidenceSource,
)
from app.production_runtime.optimization_assembly import pinned
from app.publication.execution_models import ProviderExecutionAttempt, ProviderExposureReservation
from app.settings import Settings, settings
from app.shopify.models import ShopifyConnection
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.configured_optimization_fixture import configured
from tests.test_commerce_measurement import NOW, FakeMeasurement, source
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize("platform", ["google_ads", "meta_ads"])
@pytest.mark.parametrize("mode", ["unqualified", "scenario", "revoked", "revoked_during_read"])
def test_configured_candidate_api_and_actual_tick(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    platform: str,
    mode: str,
) -> None:
    alice, base, query, wire, control = configured(
        customer_engine, configuration, tmp_path, monkeypatch, replicas, platform
    )
    wid = int(base.split("/workspaces/")[1].split("/")[0])
    with Session(customer_engine) as db:
        shop = db.scalar(select(ShopifyConnection).where(ShopifyConnection.workspace_id == wid))
        assert shop
        store = db.get(CommerceStore, shop.commerce_store_id)
        assert store
        store.last_sync_at = None
        db.commit()
        CommerceSyncService(
            db, configuration, FakeMeasurement(configuration, [([source()], None)])
        ).page(wid, now=NOW)
    policies = CandidatePolicyBundleV1(
        environment="contract_test",
        automatic_policies=(),
        candidate_policies=(
            FrozenCandidatePolicy(
                workspace_id=wid,
                environment="contract_test",
                policy_id="a" * 32,
                revision=1,
                budget_step_micros=1_000_000,
                minimum_observations=2,
            ),
        ),
    )
    descriptor = CandidateEvidenceDescriptorV1(
        source_id="unqualified_fixture",
        environment="contract_test",
        kind="contract_scenario" if mode == "scenario" else "unqualified_observation",
        source_schema="inlet.explicit-candidate-scenario.v1"
        if mode == "scenario"
        else "inlet.owned-reconciliation-observations.v1",
        policy_bundle_digest=policies.digest(),
        feedback_dependent=False,
        qualified_profiles=(),
        semantic_producer_families=(),
    )

    def transform(db: Session, principal: Any, work: Any, observation: Any, now: Any) -> Any:
        return observation.model_copy(
            update={
                "evidence": observation.evidence.model_copy(
                    update={
                        "qualification": "contract_scenario",
                        "direction": "decrease",
                        "observation_count": 2,
                    }
                )
            }
        )

    source_registration = RegisteredCandidateEvidenceSource(
        descriptor,
        lambda *_: CandidateEvidenceBinding(
            descriptor.digest(),
            transform if mode == "scenario" else None,
            (lambda *_: None) if mode == "scenario" else None,
            (),
        ),
    )
    monkeypatch.setattr(
        candidate_assembly, "registered_candidate_source", lambda _: source_registration
    )
    optimization = pinned(
        settings.optimization_execution_manifest_path,
        settings.optimization_execution_manifest_digest,
        settings.optimization_operating_policy_path,
    )
    assert optimization
    manifest = CandidateAssemblyManifestV1(
        manifest_id="candidate_fixture",
        revision=1,
        environment="contract_test",
        optimization_manifest_digest=optimization[0].digest(),
        policy_bundle_digest=policies.digest(),
        evidence_source_id=descriptor.source_id,
        evidence_descriptor_digest=descriptor.digest(),
        mode="candidates_only",
    )
    manifest_file, policy_file = (
        tmp_path / "candidate_manifest.json",
        tmp_path / "candidate_policy.json",
    )
    manifest_file.write_text(manifest.model_dump_json())
    policy_file.write_text(policies.model_dump_json())
    monkeypatch.setattr(settings, "candidate_assembly_manifest_path", str(manifest_file))
    monkeypatch.setattr(settings, "candidate_assembly_manifest_digest", manifest.digest())
    monkeypatch.setattr(settings, "candidate_policy_bundle_path", str(policy_file))
    monkeypatch.setattr(settings, "customer_candidate_reads_enabled", True)
    monkeypatch.setattr(identity, "get_identity_provider", lambda: replicas[2])
    from app.publication import clock

    monkeypatch.setattr(clock, "utc_now", lambda: control["now"])
    alice.app.include_router(customer_candidates.router)
    opt = base + "/optimization"
    response = alice.post(opt + "/target-options", json=query, headers=headers(alice))
    assert response.status_code == 200, response.text
    choice = {**query, "option_id": response.json()["options"][0]["id"]}
    response = alice.post(
        opt + "/budget-mandates",
        headers=headers(alice),
        json={
            "intent": {
                "selection": choice,
                "total_cap_micros": 50_000_000,
                "aggressiveness": "balanced",
            }
        },
    )
    assert response.status_code == 201, response.text
    draft = response.json()
    response = alice.post(
        opt + f"/budget-mandates/{draft['mandate_id']}/consent",
        headers=headers(alice),
        json=dict(
            selection=choice,
            expected_revision=draft["revision"],
            policy_digest=draft["policy_digest"],
            preparation_digest=draft["preparation_digest"],
        ),
    )
    assert response.status_code == 200, response.text
    endpoint = base + "/candidates"
    capability = alice.get(endpoint + "/capabilities")
    assert capability.status_code == 200 and capability.json()["configured"], capability.text
    response = alice.post(
        endpoint + "/reads",
        headers=headers(alice),
        json=dict(
            mandate_id=draft["mandate_id"],
            mandate_revision=draft["revision"],
            policy=dict(policy_id="a" * 32, revision=1),
        ),
    )
    assert response.status_code == 201, response.text
    assert len(response.json()["job_ids"]) == 1, response.text
    job_id = response.json()["job_ids"][0]
    if mode == "revoked":
        from app.customers.access import SESSION_COOKIE, digest
        from app.customers.models import CustomerSession

        with Session(customer_engine) as db:
            session = db.get(CustomerSession, digest(alice.cookies[SESSION_COOKIE]))
            assert session
            session.revoked_at = int(control["now"].timestamp())
            db.commit()
    if mode == "revoked_during_read":

        def revoke() -> None:
            from app.customers.access import SESSION_COOKIE, digest
            from app.customers.models import CustomerSession

            with Session(customer_engine) as db:
                original = db.get(CustomerSession, digest(alice.cookies[SESSION_COOKIE]))
                assert original
                original.revoked_at = int(control["now"].timestamp())
                db.commit()

        control["callback"] = revoke
    outcomes = run_customer_tick(customer_engine, configuration=settings, now=control["now"])
    assert outcomes["candidate_reads"] == "completed"
    if mode in {"revoked", "revoked_during_read"}:
        with Session(customer_engine) as db:
            assert db.scalar(select(func.count()).select_from(CandidateResult)) == 0
        assert not wire.google.writes and not wire.meta.posts
        assert control["opened"] == control["closed"]
        return
    status = alice.get(endpoint + "/reads/" + job_id)
    assert status.status_code == 200, status.text
    assert status.json()["state"] == "completed", status.text
    assert status.json()["decision"]["status"] == (
        "suggested" if mode == "scenario" else "blocked"
    ), status.text
    assert status.json()["decision"]["evidence"]["qualification"] == (
        "contract_scenario" if mode == "scenario" else "unqualified"
    )
    from app.optimization_candidates.contracts import CandidateDecision
    from app.optimization_candidates.customer_contracts import CandidateReadStatus
    from pydantic import ValidationError

    assert status.json()["decision_digest"] == CandidateDecision.model_validate(
        status.json()["decision"]
    ).digest()
    with pytest.raises(ValidationError):
        CandidateReadStatus.model_validate({**status.json(), "decision_digest": "0" * 64})
    if mode == "scenario":

        result = status.json()
        review = alice.post(
            endpoint + f"/results/{result['result_id']}/review",
            headers=headers(alice),
            json={
                "result_id": result["result_id"],
                "expected_decision_digest": result["decision_digest"],
            },
        )
        assert review.status_code == 200, review.text
        reviewed = review.json()
        approval = alice.post(
            base + f"/reviews/{reviewed['review_id']}/approval",
            headers=headers(alice),
            json={
                "review_digest": reviewed["review_digest"],
                "plan_digest": reviewed["plan_digest"],
            },
        )
        assert approval.status_code == 200, approval.text
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(CandidateJob)) == 1
        assert db.scalar(select(func.count()).select_from(CandidateResult)) == 1
        assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 0
        assert db.scalar(select(func.count()).select_from(ProviderExposureReservation)) == 0
    assert not wire.google.writes and not wire.meta.posts
    assert control["opened"] == control["closed"]
