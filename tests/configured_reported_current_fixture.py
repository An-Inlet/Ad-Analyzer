"""Actual current configured reported read over one immutable owned original."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from app.api import customer as customer_api
from app.api import customer_candidates, customer_reported_feedback, customer_session_automation
from app.commerce.sync import CommerceSyncService
from app.customers import identity
from app.customers.access import SESSION_COOKIE, CustomerPrincipal, digest
from app.customers.models import CustomerSession, CustomerUser
from app.meta.models import MetaConnection
from app.meta.sync import MetaSyncService, run_meta_tick
from app.planning_reporting import runtime as planning
from app.production_runtime import candidate_assembly, optimization_assembly
from app.production_runtime.candidate_sources import RegisteredReportedRuleSource
from app.production_runtime.optimization_contracts import RegisteredOptimizationEvidenceSource
from app.reported_feedback.automatic_contracts import (
    REPORTED_RULE_EPOCH_FAMILY,
    REPORTED_RULE_FAMILY,
    ReportedRuleAutomaticPolicyV1,
)
from app.reported_feedback.candidate_configuration import (
    ReportedRuleAssemblyManifestV1,
    ReportedRuleEvidenceDescriptorV1,
    ReportedRulePolicyBundleV1,
)
from app.reported_feedback.candidate_contracts import ReportedRulePolicyV1
from app.reported_feedback.contracts import ComparisonProgressV1
from app.settings import Settings, settings
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.configured_candidate_current_wiring import configured_current_optimization
from tests.configured_reported_original_fixture import ConfiguredReportedOriginalIds
from tests.test_commerce_measurement import FakeMeasurement
from tests.test_customer_optimization_api import headers
from tests.test_planning_reporting_configuration import profile
from tests.test_repeat_optimization import reader
from tests.test_reported_feedback_acquisition import acquisition_fixture


def configured_current_reported_customer(
    engine: Engine,
    configuration: Settings,
    path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    ids: ConfiguredReportedOriginalIds,
) -> Any:
    monkeypatch.setattr(customer_api, "TTL_SECONDS", 60 * 86400)
    alice, base, _, wire, control = configured_current_optimization(
        engine,
        configuration,
        path,
        monkeypatch,
        replicas,
        ids,
        replacement_enabled=True,
        now=datetime.now(UTC),
    )
    wid = ids.workspace_id
    mandate = {"mandate_id": ids.mandate_id, "revision": ids.mandate_revision}
    attempt = ids.attempt_id
    # Validated current receipt in the source loader establishes this GET state.
    wire.meta.meta_campaign["daily_budget"] = "4500"
    assert not wire.meta.posts and not wire.google.writes
    native = optimization_assembly.pinned(
        settings.optimization_execution_manifest_path,
        settings.optimization_execution_manifest_digest,
        settings.optimization_operating_policy_path,
    )
    assert native
    manifest = native[0]
    assert manifest.replacement_enabled and manifest.digest() == ids.optimization_manifest_digest
    registration = optimization_assembly.registered_optimization_evidence(  # type: ignore[attr-defined]
        manifest.evidence_source_id
    )
    assert registration

    def finance(*args: Any) -> Any:
        evidence = registration.build(*args)
        return replace(
            evidence, replacement=reader(SimpleNamespace(exposure_reader=evidence.exposure))
        )

    monkeypatch.setattr(
        optimization_assembly,
        "registered_optimization_evidence",
        lambda _: RegisteredOptimizationEvidenceSource(registration.descriptor, finance),
    )
    configuration.shopify_measurement_enabled = True
    original_profile = profile()
    windows = original_profile.windows
    assert original_profile.feedback is not None
    feedback = original_profile.feedback.model_copy(
        update={"comparison_policy_digest": windows.digest()}
    )
    configured = original_profile.model_copy(update={"windows": windows, "feedback": feedback})
    profile_file = path / "reported-planning-profile.json"
    profile_file.write_text(configured.model_dump_json())
    monkeypatch.setattr(settings, "planning_reporting_profile_path", str(profile_file))
    monkeypatch.setattr(settings, "planning_reporting_profile_digest", configured.digest())
    clock = [max(control["now"], datetime.now(UTC))]
    monkeypatch.setattr(planning, "planning_clock", lambda: clock[0])
    monkeypatch.setattr(optimization_assembly, "utc_now", lambda: clock[0])
    from app.publication import clock as execution_clock

    monkeypatch.setattr(execution_clock, "utc_now", lambda: clock[0])
    monkeypatch.setattr(identity, "get_identity_provider", lambda: replicas[2])
    alice.app.include_router(customer_candidates.router)
    alice.app.include_router(customer_reported_feedback.router)
    alice.app.include_router(customer_session_automation.router)
    report_base = base.removesuffix("/execution") + "/reported-feedback"
    with Session(engine) as db:
        session = db.get(CustomerSession, digest(alice.cookies[SESSION_COOKIE]))
        assert session
        user = db.get(CustomerUser, session.user_id)
        assert user
        principal = CustomerPrincipal(user, session)
        source = db.scalar(select(MetaConnection).where(MetaConnection.workspace_id == wid))
        assert source
        source.conversion_action_type = "purchase"
        from app.meta.security import Vault

        source.encrypted_credentials = Vault(settings).seal(
            wid,
            source.external_account_id,
            {
                "access_token": "offline-report-token",
                "expires_at": (clock[0] + timedelta(days=90)).isoformat(),
            },
        )
        db.commit()
    # Actual rolling import discovers the selected campaign before comparison options.
    import io
    import json
    from urllib.parse import parse_qs, urlsplit

    from app.meta import client as meta_wire

    from tests.test_meta_connection import campaign, insight, page

    class Rolling:
        def open(self, request: Any, timeout: int) -> Any:
            parsed = urlsplit(request.full_url)
            if parsed.path.endswith("/campaigns"):
                value = page(campaign("5", "1234567890"))
            elif parsed.path.endswith("/adsets"):
                value = page()
            else:
                query = parse_qs(parsed.query)
                window = json.loads(query["time_range"][0])
                value = page(
                    insight(
                        account_id="1234567890",
                        campaign_id="5",
                        date_start=window["since"],
                        date_stop=window["since"],
                    )
                )
            return io.BytesIO(json.dumps(value).encode())

    monkeypatch.setattr(meta_wire, "build_opener", lambda *_: Rolling())
    for name in ("meta_enabled", "meta_client_id", "meta_client_secret", "meta_redirect_uri"):
        # Reuse the actual configured source's offline integration settings.
        if name == "meta_enabled":
            monkeypatch.setattr(settings, name, True)
        elif name == "meta_client_id":
            monkeypatch.setattr(settings, name, "100000000000001")
        elif name == "meta_redirect_uri":
            monkeypatch.setattr(settings, name, "https://example.test/dashboard/meta/callback")
        else:
            from pydantic import SecretStr

            monkeypatch.setattr(settings, name, SecretStr("offline-secret-" * 3))
    with Session(engine) as db:
        from tests.test_reported_feedback_acquisition import complete

        complete(MetaSyncService(db, settings), wid, clock[0])
    response = alice.get(report_base + "/options")
    assert response.status_code == 200 and response.json()["actions"], response.text
    option = response.json()["actions"][0]
    intent = dict(
        attempt_id=attempt,
        goal_id=option["goal_id"],
        goal_revision=option["goal_revision"],
        maximum_reported_cpa_micros=100_000_000,
    )
    response = alice.post(report_base + "/comparisons", headers=headers(alice), json=intent)
    assert response.status_code == 200, response.text
    progress = ComparisonProgressV1.model_validate(response.json())
    with Session(engine) as db:
        runtime = planning.configured_bundle(lambda: Session(engine), settings)
        assert runtime
        data = acquisition_fixture(
            db,
            configuration,
            path,
            monkeypatch,
            existing=(
                wid,
                principal,
                replicas[2],
                runtime.reported,
                intent,
                progress,
                clock,
                wire.meta,
            ),
        )
        _, _, _, job, _, source, _, fixture_runner, requests, report_control, _ = data
        for name in (
            "meta_enabled",
            "meta_client_id",
            "meta_client_secret",
            "meta_token_encryption_key",
            "meta_redirect_uri",
        ):
            monkeypatch.setattr(settings, name, getattr(fixture_runner.settings, name))
        monkeypatch.setattr(settings, "meta_sync_pages", 3)
        report_control.update(before_conversions="2", after_conversions="4")
        for index in range(5):
            if index == 3:
                clock[0] += timedelta(seconds=61)
            db.commit()
            run_meta_tick(engine)
            db.expire_all()
        assert job.state == "ready" and job.completed_observations == 4
        db.commit()
        CommerceSyncService(db, configuration, FakeMeasurement(configuration, [([], None)])).page(
            wid, now=clock[0]
        )
    response = alice.get(report_base + f"/comparisons/{progress.id}")
    assert (
        response.status_code == 200 and response.json()["status"] == "operational_reported_as_of"
    ), response.text

    policy = ReportedRulePolicyV1(
        workspace_id=wid,
        environment="contract_test",
        policy_id="e" * 32,
        revision=1,
        policy_family="f" * 32,
        feedback_policy=feedback,
        comparison_policy_digest=windows.digest(),
        allowed_operation="meta_budget_set_v1",
        maximum_candidate_age_seconds=60,
    )
    automatic = ReportedRuleAutomaticPolicyV1(
        workspace_id=wid,
        environment="contract_test",
        decision_basis="operational_reported_efficiency_rule",
        policy_family=REPORTED_RULE_FAMILY,
        policy_id="a" * 32,
        revision=1,
        candidate_policy={"policy_id": policy.policy_id, "revision": 1},
        candidate_policy_digest=policy.digest(),
        allowed_operations=("meta_budget_set_v1",),
        semantic_producer_families=(REPORTED_RULE_EPOCH_FAMILY,),
        lifetime_seconds=60,
        cadence_seconds=30,
    )
    bundle = ReportedRulePolicyBundleV1(
        environment="contract_test", candidate_policies=(policy,), automatic_policies=(automatic,)
    )
    descriptor = ReportedRuleEvidenceDescriptorV1(
        source_id="actual_reported_fixture",
        environment="contract_test",
        kind="operational_reported_efficiency_rule",
        source_schema="inlet.operational-reported-comparison.v1",
        policy_bundle_digest=bundle.digest(),
        source_scope="one_current_owned_original_campaign_comparison",
        causal_lift="unavailable",
        financial_qualification="not_provided",
    )
    candidate_manifest = ReportedRuleAssemblyManifestV1(
        manifest_id="reported_fixture",
        revision=1,
        environment="contract_test",
        optimization_manifest_digest=manifest.digest(),
        policy_bundle_digest=bundle.digest(),
        evidence_source_id=descriptor.source_id,
        evidence_descriptor_digest=descriptor.digest(),
        mode="session_automatic",
    )
    mp, pp = path / "reported-candidate-manifest.json", path / "reported-candidate-policies.json"
    mp.write_text(candidate_manifest.model_dump_json())
    pp.write_text(bundle.model_dump_json())
    monkeypatch.setattr(settings, "candidate_assembly_manifest_path", str(mp))
    monkeypatch.setattr(settings, "candidate_assembly_manifest_digest", candidate_manifest.digest())
    monkeypatch.setattr(settings, "candidate_policy_bundle_path", str(pp))
    monkeypatch.setattr(settings, "customer_candidate_reads_enabled", True)
    monkeypatch.setattr(settings, "customer_session_automation_enabled", True)
    monkeypatch.setattr(
        candidate_assembly,
        "registered_candidate_source",
        lambda _: RegisteredReportedRuleSource(descriptor),
    )
    return alice, base, wire, clock, mandate, policy, automatic, progress.id, requests
