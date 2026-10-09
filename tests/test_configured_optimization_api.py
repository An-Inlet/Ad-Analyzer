"""Configured endpoints, actual native MockHTTP, no seeded provider authority."""

from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from app.publication.execution_models import ProviderExecutionAttempt, ProviderExposureReservation
from app.settings import Settings
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.configured_optimization_fixture import configured
from tests.current_runtime_read_contexts import (
    current_optimization_source as current_optimization_source,
)
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_customer_optimization_api import headers
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize("platform", ["google_ads", "meta_ads"])
@pytest.mark.parametrize("mode", ["budget", "pause", "unknown"])
def retained_test_configured_prepare_consent_exact_mutation(
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
    opt = base + "/optimization"
    options = alice.post(opt + "/target-options", json=query, headers=headers(alice))
    assert options.status_code == 200, options.text
    assert len(options.json()["options"]) == 1, options.text
    selected = {**query, "option_id": options.json()["options"][0]["id"]}
    prepared = alice.post(
        opt + "/budget-mandates",
        json={
            "intent": {
                "selection": selected,
                "total_cap_micros": 50_000_000,
                "aggressiveness": "balanced",
            }
        },
        headers=headers(alice),
    )
    assert prepared.status_code == 201, prepared.text
    budget = prepared.json()
    control["now"] += timedelta(seconds=15)
    accepted = alice.post(
        opt + f"/budget-mandates/{budget['mandate_id']}/consent",
        json={
            "selection": selected,
            "expected_revision": budget["revision"],
            "policy_digest": budget["policy_digest"],
            "preparation_digest": budget["preparation_digest"],
        },
        headers=headers(alice),
    )
    assert accepted.status_code == 200, accepted.text
    control["now"] += timedelta(seconds=10)
    review = alice.post(
        opt + "/initial-reviews",
        json={
            "choice": selected,
            "mandate_id": budget["mandate_id"],
            "mandate_revision": budget["revision"],
            "action": (
                {"kind": "pause"}
                if mode == "pause"
                else {"kind": "set_budget", "amount_micros": 45_000_000}
            ),
        },
        headers=headers(alice),
    )
    assert review.status_code == 201, review.text
    r = review.json()
    approval = alice.post(
        base + f"/reviews/{r['id']}/approval",
        json={"review_digest": r["review_digest"], "plan_digest": r["plan_digest"]},
        headers=headers(alice),
    )
    assert approval.status_code == 200, approval.text
    run = alice.post(base + f"/reviews/{r['id']}/runs", headers=headers(alice))
    assert run.status_code == 201, run.text
    if mode == "unknown":
        native = wire.google if platform == "google_ads" else wire.meta
        native.ignore = native.timeout = True
    advanced = alice.post(base + f"/runs/{run.json()['id']}/advance", headers=headers(alice))
    assert advanced.status_code == 200, advanced.text
    attempt = advanced.json()["steps"][0]["attempt_id"]
    receipt = alice.get(base + f"/attempts/{attempt}/receipt")
    assert receipt.status_code == 200, receipt.text
    assert receipt.json()["receipt"]["outcome"] == (
        "unknown" if mode == "unknown" else "verified_target_state"
    )
    replay = alice.post(base + f"/runs/{run.json()['id']}/advance", headers=headers(alice))
    assert replay.status_code == 200, replay.text
    if mode == "unknown":
        reconciled = alice.post(
            base + f"/runs/{run.json()['id']}/reconcile",
            json={"attempt_id": attempt},
            headers=headers(alice),
        )
        assert reconciled.status_code == 200, reconciled.text
        assert (
            alice.get(base + f"/attempts/{attempt}/receipt").json()["receipt"]["outcome"]
            == "unknown"
        )
    assert len(wire.google.writes if platform == "google_ads" else wire.meta.posts) == 1
    assert control["opened"] == control["closed"]
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 1
        assert db.scalar(select(func.count()).select_from(ProviderExposureReservation)) == 1
        assert db.scalar(select(ProviderExposureReservation.state)) == "held"


@pytest.mark.parametrize("change", ["session", "source", "generation"])
def retained_test_revocation_during_actual_native_http_rolls_back_preparation(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    change: str,
) -> None:
    import time

    from app.customers.access import SESSION_COOKIE, digest
    from app.customers.models import CustomerSession
    from app.google_connections.models import GoogleCustomerConnection
    from app.production_runtime import optimization_assembly
    from app.production_runtime.optimization_origin_models import OptimizationMandatePreparationRow
    from app.publication.execution_models import ProviderExecutionMandate

    alice, base, query, wire, control = configured(
        customer_engine, configuration, tmp_path, monkeypatch, replicas, "google_ads"
    )
    opt = base + "/optimization"
    options = alice.post(opt + "/target-options", json=query, headers=headers(alice))
    assert options.status_code == 200, options.text
    selected = {**query, "option_id": options.json()["options"][0]["id"]}

    def revoke() -> None:
        if change == "source":
            monkeypatch.setattr(
                optimization_assembly, "registered_optimization_evidence", lambda _: None
            )
            return
        with Session(customer_engine) as db:
            if change == "session":
                session = db.get(CustomerSession, digest(alice.cookies[SESSION_COOKIE]))
                assert session
                session.revoked_at = int(time.time())
            else:
                native = db.scalar(select(GoogleCustomerConnection))
                assert native
                native.generation += 1
            db.commit()  # independent PG transaction must not wait behind request locks

    control["callback"] = revoke
    prepared = alice.post(
        opt + "/budget-mandates",
        json={
            "intent": {
                "selection": selected,
                "total_cap_micros": 50_000_000,
                "aggressiveness": "balanced",
            }
        },
        headers=headers(alice),
    )
    assert prepared.status_code in {401, 409}, prepared.text
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(ProviderExecutionMandate)) == 0
        assert db.scalar(select(func.count()).select_from(OptimizationMandatePreparationRow)) == 0
    assert not wire.google.writes
    assert control["opened"] == control["closed"]


def retained_test_configured_exact_consent_and_technical_route_bypass_denied(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
) -> None:
    from app.lifecycle.export_serializers import serialize
    from app.production_runtime.optimization_origin_models import OptimizationMandatePreparationRow
    from app.publication import execution_mandates
    from app.publication.execution_models import ProviderExecutionConsent, ProviderExecutionRevision
    from fastapi import HTTPException

    from tests.test_commerce_measurement import NOW

    alice, base, query, _, _ = configured(
        customer_engine, configuration, tmp_path, monkeypatch, replicas, "google_ads"
    )
    opt = base + "/optimization"
    options = alice.post(opt + "/target-options", json=query, headers=headers(alice))
    selected = {**query, "option_id": options.json()["options"][0]["id"]}
    body = {
        "intent": {
            "selection": selected,
            "total_cap_micros": 50_000_000,
            "aggressiveness": "balanced",
        }
    }
    made = alice.post(opt + "/budget-mandates", json=body, headers=headers(alice))
    assert made.status_code == 201, made.text
    m = made.json()
    generic = alice.post(
        base + f"/mandates/{m['mandate_id']}/consent",
        json={"expected_revision": 1, "policy_digest": m["policy_digest"]},
        headers=headers(alice),
    )
    assert generic.status_code == 409
    incorrect = alice.post(
        opt + f"/budget-mandates/{m['mandate_id']}/consent",
        json={
            "selection": selected,
            "expected_revision": 1,
            "policy_digest": m["policy_digest"],
            "preparation_digest": "f" * 64,
        },
        headers=headers(alice),
    )
    assert incorrect.status_code == 409
    with Session(customer_engine) as db:
        revision = db.scalar(select(ProviderExecutionRevision))
        assert revision and revision.origin_kind == "optimization_customer_v1"
        with pytest.raises(HTTPException, match="optimization_mandate_origin_unavailable"):
            execution_mandates.consent(
                db,
                revision.workspace_id,
                revision.mandate_id,
                1,
                revision.digest,
                revision.actor,
                lambda: NOW,
            )
        db.rollback()
        assert db.scalar(select(func.count()).select_from(ProviderExecutionConsent)) == 0
        sidecar = db.scalar(select(OptimizationMandatePreparationRow))
        assert sidecar
        exported, omitted = serialize(
            sidecar.__tablename__,
            {c.name: getattr(sidecar, c.name) for c in sidecar.__table__.columns},
        )
        assert not omitted and exported["document"] == sidecar.document
        limits = {
            k: v
            for k, v in revision.policy.items()
            if k
            in {
                "starts_at",
                "ends_at",
                "total_cap_micros",
                "per_plan_cap_micros",
                "positive_change_cap_micros",
                "action_limit",
                "cooldown_seconds",
                "aggressiveness_percent",
            }
        }
    bypass = alice.post(
        opt + "/mandates", json={"choice": selected, "limits": limits}, headers=headers(alice)
    )
    assert bypass.status_code == 409, bypass.text
    too_much = alice.post(
        opt + "/budget-mandates",
        json={"intent": {**body["intent"], "total_cap_micros": 50_010_000}},
        headers=headers(alice),
    )
    assert too_much.status_code == 409


@pytest.mark.parametrize("change", ["native_state", "qualification_revision"])
def retained_test_later_consent_rejects_meaningful_change(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    change: str,
) -> None:
    from app.publication.execution_models import ProviderExecutionConsent

    alice, base, query, wire, control = configured(
        customer_engine, configuration, tmp_path, monkeypatch, replicas, "google_ads"
    )
    opt = base + "/optimization"
    options = alice.post(opt + "/target-options", json=query, headers=headers(alice))
    selected = {**query, "option_id": options.json()["options"][0]["id"]}
    prepared = alice.post(
        opt + "/budget-mandates",
        json={
            "intent": {
                "selection": selected,
                "total_cap_micros": 50_000_000,
                "aggressiveness": "balanced",
            }
        },
        headers=headers(alice),
    )
    assert prepared.status_code == 201, prepared.text
    budget = prepared.json()
    control["now"] += timedelta(seconds=15)
    if change == "native_state":
        wire.google.budget["amountMicros"] = "45000000"
    else:
        control["qualification_revision"] += 1
    accepted = alice.post(
        opt + f"/budget-mandates/{budget['mandate_id']}/consent",
        json={
            "selection": selected,
            "expected_revision": budget["revision"],
            "policy_digest": budget["policy_digest"],
            "preparation_digest": budget["preparation_digest"],
        },
        headers=headers(alice),
    )
    assert accepted.status_code == 409, accepted.text
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(ProviderExecutionConsent)) == 0
    assert not wire.google.writes


@pytest.mark.planning_boundary
def test_real_transport_scenario_denies_before_factory_or_oauth(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    current_optimization_source: Any,
) -> None:
    from tests.optimization_current_read_fixture import configured

    customer_engine, tmp_path, replicas, ids = current_optimization_source

    import httpx
    from app.production_runtime import optimization_assembly
    from app.production_runtime.optimization_transport import optimization_execution_transport

    alice, base, query, wire, control = configured(
        customer_engine, configuration, tmp_path, monkeypatch, replicas, ids
    )
    monkeypatch.setattr(
        optimization_assembly, "optimization_execution_transport", optimization_execution_transport
    )

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("network constructor must not be reached")

    monkeypatch.setattr(httpx, "HTTPTransport", forbidden)
    response = alice.post(base + "/optimization/target-options", json=query, headers=headers(alice))
    assert response.status_code == 409
    assert control["factory"] == control["opened"] == 0
    assert not wire.calls and not wire.google.writes


def retained_test_prepare_failure_after_both_inserts_is_atomic(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
) -> None:
    from app.production_runtime import optimization_mandates
    from app.production_runtime.optimization_origin_models import OptimizationMandatePreparationRow
    from app.publication.execution_models import (
        ProviderExecutionMandate,
        ProviderExecutionRevision,
        ProviderPeriodLedger,
    )
    from fastapi import HTTPException

    alice, base, query, _, _ = configured(
        customer_engine, configuration, tmp_path, monkeypatch, replicas, "google_ads"
    )
    options = alice.post(base + "/optimization/target-options", json=query, headers=headers(alice))
    selected = {**query, "option_id": options.json()["options"][0]["id"]}
    seen = []
    original = optimization_mandates.final

    def fail(db: Session, *args: Any) -> None:
        original(db, *args)
        assert db.scalar(select(func.count()).select_from(OptimizationMandatePreparationRow)) == 1
        assert db.scalar(select(func.count()).select_from(ProviderExecutionRevision)) == 1
        seen.append(True)
        raise HTTPException(409, "injected_local_failure")

    monkeypatch.setattr(optimization_mandates, "final", fail)
    result = alice.post(
        base + "/optimization/budget-mandates",
        json={
            "intent": {
                "selection": selected,
                "total_cap_micros": 50_000_000,
                "aggressiveness": "balanced",
            }
        },
        headers=headers(alice),
    )
    assert result.status_code == 409 and seen
    with Session(customer_engine) as db:
        for table in (
            OptimizationMandatePreparationRow,
            ProviderExecutionRevision,
            ProviderExecutionMandate,
            ProviderPeriodLedger,
        ):
            assert db.scalar(select(func.count()).select_from(table)) == 0
