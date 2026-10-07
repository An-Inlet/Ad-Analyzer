"""Real customer consent, configured report/candidate workers and explicit Start."""

from pathlib import Path
from typing import Any

import pytest
from app.jobs.customer_runtime import run_customer_tick
from app.settings import Settings, settings
from sqlalchemy import Engine

from tests.configured_reported_rule_fixture import configured_reported_customer
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration


def test_actual_configured_reported_candidate(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
) -> None:
    alice, base, wire, clock, mandate, policy, automatic, _, _ = configured_reported_customer(
        customer_engine, configuration, tmp_path, monkeypatch, replicas
    )
    response = alice.post(
        base + "/candidates/reads",
        headers=headers(alice),
        json={
            "mandate_id": mandate["mandate_id"],
            "mandate_revision": mandate["revision"],
            "policy": {"policy_id": policy.policy_id, "revision": policy.revision},
        },
    )
    assert response.status_code == 201, response.text
    assert len(response.json()["job_ids"]) == 1, response.text
    job = response.json()["job_ids"][0]
    result = run_customer_tick(customer_engine, configuration=settings, now=clock[0])
    assert result["candidate_reads"] == "completed", result
    response = alice.get(base + "/candidates/reads/" + job)
    assert response.status_code == 200, response.text
    assert response.json()["decision"]["status"] == "suggested", response.text
    assert response.json()["basis_details"]["causal_lift"] == "unavailable"
    assert len(wire.meta.posts) == 1

    reviewed = alice.post(
        base + f"/candidates/results/{response.json()['result_id']}/review",
        headers=headers(alice),
        json={
            "result_id": response.json()["result_id"],
            "expected_decision_digest": response.json()["decision_digest"],
        },
    )
    assert reviewed.status_code == 200, reviewed.text


@pytest.mark.parametrize("change", ["none", "session", "capsule", "source", "unknown"])
def test_actual_configured_reported_automatic_start(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    change: str,
) -> None:
    from app.publication.execution_models import (
        ProviderExecutionApproval,
        ProviderExposureReservation,
    )
    from app.session_automation.models import AutomaticDecisionAdmission
    from sqlalchemy import func, select
    from sqlalchemy.orm import Session

    alice, base, wire, clock, mandate, _, automatic, _, _ = configured_reported_customer(
        customer_engine, configuration, tmp_path, monkeypatch, replicas
    )
    response = alice.get(base + "/automation/capabilities")
    assert response.status_code == 200, response.text
    caps = response.json()
    assert len(caps["policies"]) == 1 and len(caps["mandates"]) == 1, caps
    with Session(customer_engine) as db:
        before = db.scalar(select(func.count()).select_from(ProviderExecutionApproval))
    response = alice.post(
        base + "/automation/start",
        headers=headers(alice),
        json={
            "schema_version": "inlet.start-reported-rule-automation.v1",
            "decision_basis": "operational_reported_efficiency_rule",
            "mandate": caps["mandates"][0]["mandate"],
            "policy": {"policy_id": automatic.policy_id, "revision": automatic.revision},
            "expected_policy_digest": automatic.digest(),
        },
    )
    assert response.status_code == 200, response.text
    identifier = response.json()["run_id"]
    if change == "session":
        from app.customers.access import SESSION_COOKIE, digest
        from app.customers.models import CustomerSession

        with Session(customer_engine) as db:
            original = db.get(CustomerSession, digest(alice.cookies[SESSION_COOKIE]))
            assert original
            original.revoked_at = int(clock[0].timestamp())
            db.commit()
    elif change == "capsule":
        from app.reported_feedback.models import ReportedWindowCapsule

        with Session(customer_engine) as db:
            capsule = db.scalar(select(ReportedWindowCapsule))
            assert capsule
            db.delete(capsule)
            db.commit()
    elif change == "source":
        from app.production_runtime import candidate_assembly

        monkeypatch.setattr(candidate_assembly, "registered_candidate_source", lambda _: None)
    elif change == "unknown":
        wire.meta.ignore = wire.meta.timeout = True
    result = run_customer_tick(customer_engine, configuration=settings, now=clock[0])
    status = alice.get(base + "/automation/" + identifier)
    if change in {"session", "capsule", "source"}:
        assert len(wire.meta.posts) == 1, (result, status.text)
        with Session(customer_engine) as db:
            assert db.scalar(select(func.count()).select_from(AutomaticDecisionAdmission)) == 0
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(ProviderExposureReservation)
                    .where(ProviderExposureReservation.state == "held")
                )
                == 1
            )
        return
    assert status.status_code == 200, status.text
    assert len(wire.meta.posts) == 2, (result, status.text)
    assert wire.meta.meta_campaign["daily_budget"] == ("4500" if change == "unknown" else "4475")
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(ProviderExecutionApproval)) == before
        assert db.scalar(select(func.count()).select_from(AutomaticDecisionAdmission)) == 1
        assert (
            db.scalar(
                select(func.count())
                .select_from(ProviderExposureReservation)
                .where(ProviderExposureReservation.state == "held")
            )
            == 1
        )
    from datetime import timedelta

    from app.publication.execution_models import ProviderExecutionAttempt, ProviderExecutionReceipt

    with Session(customer_engine) as db:
        before_fences = tuple(
            db.execute(
                select(ProviderExecutionAttempt.id, ProviderExecutionAttempt.fence).order_by(
                    ProviderExecutionAttempt.id
                )
            )
        )
        assert len(before_fences) == 2
        if change == "unknown":
            latest = db.scalar(
                select(ProviderExecutionReceipt).order_by(
                    ProviderExecutionReceipt.observed_at.desc()
                )
            )
            assert latest and latest.receipt["outcome"] == "unknown"
    clock[0] += timedelta(seconds=31)
    run_customer_tick(customer_engine, configuration=settings, now=clock[0])
    assert len(wire.meta.posts) == 2
    with Session(customer_engine) as db:
        assert (
            tuple(
                db.execute(
                    select(ProviderExecutionAttempt.id, ProviderExecutionAttempt.fence).order_by(
                        ProviderExecutionAttempt.id
                    )
                )
            )
            == before_fences
        )


def test_configured_master_disable_constructs_no_native_or_policy_factory(
    customer_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.automation.models import PlatformAutomationControl
    from app.production_runtime import reported_automation
    from sqlalchemy.orm import Session

    configuration = Settings(_env_file=None, customer_session_automation_enabled=True)
    with Session(customer_engine) as db:
        db.add(PlatformAutomationControl(key="all_data_syncs", enabled=False, updated_by="fixture"))
        db.commit()

    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("disabled configured runtime constructed")

    monkeypatch.setattr(reported_automation, "pinned", forbidden)
    assert (
        reported_automation.run_configured_session_automation(customer_engine, configuration) == {}
    )


def test_configured_revoked_session_does_not_shadow_current_session(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
) -> None:
    from datetime import timedelta

    from app.customers.access import SESSION_COOKIE, digest
    from app.customers.models import CustomerSession
    from app.production_runtime.reported_automation import run_configured_session_automation
    from app.session_automation.models import AutomaticDecisionAdmission, SessionAutomationRun
    from app.shopify.security import utc
    from sqlalchemy import func, select
    from sqlalchemy.orm import Session

    from tests.test_customer_identity import login

    alice, base, wire, clock, _, _, automatic, _, _ = configured_reported_customer(
        customer_engine, configuration, tmp_path, monkeypatch, replicas
    )
    caps = alice.get(base + "/automation/capabilities").json()
    body = {
        "schema_version": "inlet.start-reported-rule-automation.v1",
        "decision_basis": "operational_reported_efficiency_rule",
        "mandate": caps["mandates"][0]["mandate"],
        "policy": {"policy_id": automatic.policy_id, "revision": 1},
        "expected_policy_digest": automatic.digest(),
    }
    first = alice.post(base + "/automation/start", json=body, headers=headers(alice))
    assert first.status_code == 200, first.text
    first_id = first.json()["run_id"]
    with Session(customer_engine) as db:
        original = db.get(CustomerSession, digest(alice.cookies[SESSION_COOKIE]))
        assert original
        original.revoked_at = int(clock[0].timestamp())
        row = db.get(SessionAutomationRun, first_id)
        assert row
        row.next_due_at = clock[0] - timedelta(seconds=1)
        db.commit()
    login(alice, "configured-meta:second")
    second = alice.post(base + "/automation/start", json=body, headers=headers(alice))
    assert second.status_code == 200, second.text
    second_id = second.json()["run_id"]
    assert second_id != first_id
    assert run_configured_session_automation(customer_engine, settings, limit=1) == {"blocked": 1}
    run_configured_session_automation(customer_engine, settings, limit=1)
    with Session(customer_engine) as db:
        row = db.get(SessionAutomationRun, second_id)
        assert row and utc(row.next_due_at) > clock[0]
        assert db.scalar(select(func.count()).select_from(AutomaticDecisionAdmission)) == 0
    # New login cannot adopt the old comparison's original-session evidence.
    assert len(wire.meta.posts) == 1
