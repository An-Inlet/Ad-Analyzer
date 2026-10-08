"""Actual customer sessions/coordinator plus actual provider HTTP adapters, offline only."""

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from app import advertising_capabilities
from app.api.customer_execution import router as execution_router
from app.api.customer_optimization import router
from app.customers.models import CustomerUser
from app.publication import execution_mandates as mandates
from app.publication.contracts import fingerprint
from app.publication.customer_optimization_catalog import (
    ConfiguredOptimizationCatalog,
    NamedOptimizationTarget,
)
from app.publication.customer_optimization_contracts import (
    CustomerOptimizationRuntime,
    get_customer_optimization_runtime,
)
from app.publication.execution_models import ProviderExecutionRun
from app.settings import Settings
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import ISSUER, ORIGIN, FakeProvider, login
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_durable_optimization import ready
from tests.test_repeat_optimization import reader
from tests.test_shopify_sales import configuration as configuration


def setup(
    db: Session, config: Settings, path: Path, platform: str, action_kind: str = "budget"
) -> tuple[Any, ...]:
    wid, actor, binding, scope, target, action, runtime, server = ready(
        db, config, path, platform, action_kind
    )
    _, row = mandates.owned(db, wid, binding.mandate_id)
    policy = mandates.policy(db, row)
    user = db.get(CustomerUser, actor)
    assert user is not None
    user.issuer, user.subject = ISSUER, "optimization-owner"
    db.commit()
    qualification = runtime.qualification_reader(db, binding, scope, target, NOW)
    catalog = ConfiguredOptimizationCatalog(
        runtime,
        (
            NamedOptimizationTarget(
                scope_digest=fingerprint(
                    "inlet.optimization-catalog-scope.v1", scope.model_dump(mode="json")
                ),
                label="Brand Search",
                parent_label="Brand Campaign",
                target=target,
                money=qualification.money,
                qualification_id=qualification.qualification_id,
                qualification_revision=qualification.qualification_revision,
            ),
        ),
    )
    runtime = replace(runtime, replacement_reader=reader(runtime))
    return wid, actor, policy, CustomerOptimizationRuntime(runtime, catalog, lambda: NOW), server


def install(client: TestClient, runtime: CustomerOptimizationRuntime | None) -> None:
    client.app.include_router(router)  # type: ignore[attr-defined]
    client.app.include_router(execution_router)  # type: ignore[attr-defined]
    client.app.dependency_overrides[get_customer_optimization_runtime] = lambda: runtime  # type: ignore[attr-defined]


def headers(client: TestClient) -> dict[str, str]:
    return {"Origin": ORIGIN, "X-CSRF-Token": client.cookies.get("__Host-inlet_csrf") or ""}


@pytest.mark.parametrize("platform", ["google_ads", "meta_ads", "tiktok_ads"])
@pytest.mark.parametrize("action_kind", ["budget", "pause"])
@pytest.mark.retained_execution
@pytest.mark.usefixtures("retained_execution_engine")
def test_owned_catalog_mandate_initial_repeat_actual_adapter_journey(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    replicas: tuple[TestClient, TestClient, FakeProvider],
    platform: str,
    action_kind: str,
) -> None:
    alice, bob, _ = replicas
    with Session(customer_engine) as db:
        wid, actor, policy, runtime, server = setup(
            db, configuration, tmp_path, platform, action_kind
        )
    install(alice, runtime)
    install(bob, runtime)
    assert login(alice, "optimization-owner:1") == actor
    login(bob, "unrelated-owner:1")
    base = f"/api/customer/v1/workspaces/{wid}/execution"
    opt = base + "/optimization"
    query = {
        "goal_id": policy.goal_id,
        "goal_revision": policy.goal_revision,
        "account_id": policy.accounts[0].account.account_id,
    }
    assert alice.post(opt + "/target-options", json=query).status_code == 403
    assert bob.post(opt + "/target-options", json=query, headers=headers(bob)).status_code in {
        403,
        404,
    }

    def choice() -> dict[str, Any]:
        response = alice.post(opt + "/target-options", json=query, headers=headers(alice))
        assert response.status_code == 200, response.text
        assert response.json()["options"][0]["label"] == "Brand Search"
        return {**query, "option_id": response.json()["options"][0]["id"]}

    selected = choice()
    limits = {
        key: value
        for key, value in policy.model_dump(mode="json").items()
        if key
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
    made = alice.post(
        opt + "/mandates", json={"choice": selected, "limits": limits}, headers=headers(alice)
    )
    assert made.status_code == 201, made.text
    m = made.json()
    consent = {"expected_revision": m["revision"], "policy_digest": m["policy_digest"]}
    accepted = alice.post(
        base + f"/mandates/{m['id']}/consent", json=consent, headers=headers(alice)
    )
    assert accepted.status_code == 200, accepted.text
    previous = None
    for index, amount in enumerate([45_000_000, 44_000_000] if action_kind == "budget" else [0]):
        body = {
            "choice": choice(),
            "mandate_id": m["id"],
            "mandate_revision": m["revision"],
            "action": {"kind": "set_budget", "amount_micros": amount}
            if action_kind == "budget"
            else {"kind": "pause"},
        }
        if previous:
            body["predecessor_id"] = previous
        prepared = alice.post(
            opt + ("/repeat-reviews" if index else "/initial-reviews"),
            json=body,
            headers=headers(alice),
        )
        assert prepared.status_code == 201, prepared.text
        review = prepared.json()
        assert review["reviewed_limits"]["total_cap_micros"] == policy.total_cap_micros
        assert review["reviewed_limits"]["aggressiveness_percent"] == policy.aggressiveness_percent
        assert review["optimization_kind"] == ("repeat" if index else "initial")
        assert alice.get(base + f"/reviews/{review['id']}").status_code == 200
        assert bob.get(base + f"/reviews/{review['id']}").status_code in {403, 404}
        approval = alice.post(
            base + f"/reviews/{review['id']}/approval",
            json={"review_digest": review["review_digest"], "plan_digest": review["plan_digest"]},
            headers=headers(alice),
        )
        assert approval.status_code == 200, approval.text
        admitted = alice.post(base + f"/reviews/{review['id']}/runs", headers=headers(alice))
        assert admitted.status_code == 201, admitted.text
        run = admitted.json()
        advanced = alice.post(base + f"/runs/{run['id']}/advance", headers=headers(alice))
        assert advanced.status_code == 200, advanced.text
        attempt = advanced.json()["steps"][0]["attempt_id"]
        evidence = alice.get(base + f"/attempts/{attempt}/receipt")
        assert evidence.status_code == 200, evidence.text
        assert evidence.json()["receipt"]["outcome"] == "verified_target_state"
        reconciled = alice.post(
            base + f"/runs/{run['id']}/reconcile",
            json={"attempt_id": attempt},
            headers=headers(alice),
        )
        assert reconciled.status_code == 200, reconciled.text
        again = alice.post(base + f"/runs/{run['id']}/advance", headers=headers(alice))
        assert again.status_code == 200
        assert alice.get(base + "/runs").status_code == 200
        with Session(customer_engine) as db:
            persisted = db.get(ProviderExecutionRun, run["id"])
            assert persisted is not None
            previous = persisted.reservation_id
    assert previous is not None


def bootstrap(
    customer_engine: Engine, configuration: Settings, tmp_path: Path, client: TestClient
) -> tuple[Any, ...]:
    with Session(customer_engine) as db:
        wid, actor, policy, runtime, server = setup(db, configuration, tmp_path, "google_ads")
        from app.publication.execution_models import ProviderExecutionMandate
        from sqlalchemy import select

        row = db.scalar(
            select(ProviderExecutionMandate).where(ProviderExecutionMandate.workspace_id == wid)
        )
        assert row is not None
        mid, revision = row.id, row.revision
    install(client, runtime)
    login(client, "optimization-owner:1")
    base = f"/api/customer/v1/workspaces/{wid}/execution"
    query = {
        "goal_id": policy.goal_id,
        "goal_revision": policy.goal_revision,
        "account_id": policy.accounts[0].account.account_id,
    }
    response = client.post(
        base + "/optimization/target-options", json=query, headers=headers(client)
    )
    assert response.status_code == 200, response.text
    body = {
        "choice": {**query, "option_id": response.json()["options"][0]["id"]},
        "mandate_id": mid,
        "mandate_revision": revision,
        "action": {"kind": "set_budget", "amount_micros": 45_000_000},
    }
    return wid, policy, runtime, base, query, body


@pytest.mark.parametrize("phase", ["catalog", "qualification"])
@pytest.mark.parametrize("revocation", ["session", "role"])
@pytest.mark.retained_execution
@pytest.mark.usefixtures("retained_execution_engine")
def test_original_session_revocation_during_read_blocks_review(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    replicas: tuple[TestClient, TestClient, FakeProvider],
    phase: str,
    revocation: str,
) -> None:
    client, _, provider = replicas
    wid, _, runtime, base, _, body = bootstrap(customer_engine, configuration, tmp_path, client)

    def revoke() -> None:
        if revocation == "session":
            provider.revoked.add("optimization-owner")
        else:
            from app.customers.models import CustomerMembership
            from sqlalchemy import select

            with Session(customer_engine) as db:
                membership = db.scalar(
                    select(CustomerMembership).where(CustomerMembership.workspace_id == wid)
                )
                assert membership is not None
                membership.role = "viewer"
                db.commit()

    def revoke_catalog(request: Any, now: Any) -> Any:
        result = runtime.catalog(request, now)
        revoke()
        return result

    def revoke_qualification(*args: Any) -> Any:
        result = runtime.execution.qualification_reader(*args)
        revoke()
        return result

    altered = (
        replace(runtime, catalog=revoke_catalog)
        if phase == "catalog"
        else replace(
            runtime, execution=replace(runtime.execution, qualification_reader=revoke_qualification)
        )
    )
    client.app.dependency_overrides[get_customer_optimization_runtime] = lambda: altered  # type: ignore[attr-defined]
    response = client.post(
        base + "/optimization/initial-reviews", json=body, headers=headers(client)
    )
    assert response.status_code == (401 if revocation == "session" else 403), response.text
    with Session(customer_engine) as db:
        from app.publication.execution_models import ProviderExecutionReview
        from sqlalchemy import func, select

        assert db.scalar(select(func.count()).select_from(ProviderExecutionReview)) == 0


@pytest.mark.retained_execution
@pytest.mark.usefixtures("retained_execution_engine")
def test_unknown_stale_forged_choices_and_missing_repeat_source_fail_closed(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    replicas: tuple[TestClient, TestClient, FakeProvider],
) -> None:
    client, _, _ = replicas
    _, _, runtime, base, query, body = bootstrap(customer_engine, configuration, tmp_path, client)
    opt = base + "/optimization"
    extras: list[dict[str, Any]] = [
        {"proof": {}},
        {"environment": "live"},
        {"target": {"external_id": "5"}},
    ]
    for extra in extras:
        assert (
            client.post(
                opt + "/initial-reviews", json={**body, **extra}, headers=headers(client)
            ).status_code
            == 422
        )
    foreign = {**query, "account_id": 987654}
    assert (
        client.post(opt + "/target-options", json=foreign, headers=headers(client)).status_code
        == 404
    )
    stale = {**body, "choice": {**body["choice"], "option_id": "f" * 64}}
    assert (
        client.post(opt + "/initial-reviews", json=stale, headers=headers(client)).status_code
        == 409
    )
    changed = {**body, "choice": {**body["choice"], "goal_revision": 999}}
    assert (
        client.post(opt + "/initial-reviews", json=changed, headers=headers(client)).status_code
        == 409
    )
    disabled = replace(runtime, execution=replace(runtime.execution, replacement_reader=None))
    client.app.dependency_overrides[get_customer_optimization_runtime] = lambda: disabled  # type: ignore[attr-defined]
    response = client.post(
        opt + "/repeat-reviews", json={**body, "predecessor_id": "a" * 32}, headers=headers(client)
    )
    assert response.status_code == 409 and "closure" in response.text
    client.app.dependency_overrides[get_customer_optimization_runtime] = lambda: None  # type: ignore[attr-defined]
    assert client.get(opt + "/capabilities").json()["catalog_available"] is False
    assert (
        client.post(opt + "/target-options", json=query, headers=headers(client)).status_code == 409
    )


@pytest.mark.retained_execution
@pytest.mark.usefixtures("retained_execution_engine")
def test_shared_consent_rechecks_server_topology_and_unknown_dispatch_rejects(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    replicas: tuple[TestClient, TestClient, FakeProvider],
) -> None:
    client, _, _ = replicas
    _, policy, runtime, base, _, body = bootstrap(customer_engine, configuration, tmp_path, client)

    def changed_catalog(request: Any, now: Any) -> Any:
        result = runtime.catalog(request, now)
        raw = result.model_dump()
        state = raw["options"][0]["state"]
        target = {"kind": "campaign", "external_id": "6", "campaign_id": "6"}
        state["target"] = target
        state["budget_owner"]["owner"] = target
        state["budget_owner"]["affected_targets"] = [target]
        state["owning_campaign_ids"] = ["6"]
        return type(result).model_validate(raw)

    changed = replace(runtime, catalog=changed_catalog)
    client.app.dependency_overrides[get_customer_optimization_runtime] = lambda: changed  # type: ignore[attr-defined]
    response = client.post(
        base + f"/mandates/{body['mandate_id']}/consent",
        json={"expected_revision": body["mandate_revision"], "policy_digest": policy.digest()},
        headers=headers(client),
    )
    assert response.status_code == 409 and "target_changed" in response.text
    client.app.dependency_overrides[get_customer_optimization_runtime] = lambda: runtime  # type: ignore[attr-defined]
    prepared = client.post(
        base + "/optimization/initial-reviews", json=body, headers=headers(client)
    )
    assert prepared.status_code == 201, prepared.text
    review = prepared.json()
    approved = client.post(
        base + f"/reviews/{review['id']}/approval",
        json={"review_digest": review["review_digest"], "plan_digest": review["plan_digest"]},
        headers=headers(client),
    )
    assert approved.status_code == 200
    run = client.post(base + f"/reviews/{review['id']}/runs", headers=headers(client)).json()
    with Session(customer_engine) as db:
        from app.publication.execution_models import ProviderExecutionReview

        row = db.get(ProviderExecutionReview, review["id"])
        assert row is not None
        row.document = {**row.document, "schema_version": "unrecognized"}
        db.commit()
    for suffix, payload in [
        (
            f"/reviews/{review['id']}/approval",
            {"review_digest": review["review_digest"], "plan_digest": review["plan_digest"]},
        ),
        (f"/reviews/{review['id']}/runs", None),
        (f"/runs/{run['id']}/advance", None),
        (f"/runs/{run['id']}/reconcile", {"attempt_id": "f" * 32}),
    ]:
        response = client.post(base + suffix, json=payload, headers=headers(client))
        assert response.status_code == 409 and "unsupported_execution_review" in response.text
    assert client.get(base + f"/reviews/{review['id']}").status_code == 409


@pytest.mark.planning_boundary
def test_owned_account_choices_hide_native_ids_and_disconnected_sources(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    replicas: tuple[TestClient, TestClient, FakeProvider],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.google_connections.models import GoogleCustomerConnection
    from sqlalchemy import select

    client, other, _ = replicas
    with monkeypatch.context() as historical:
        historical.setattr(advertising_capabilities, "require_advertising_write", lambda: None)
        wid, _, runtime, base, _, _ = bootstrap(customer_engine, configuration, tmp_path, client)
    assert advertising_capabilities.advertising_writes_enabled() is False
    with pytest.raises(advertising_capabilities.AdvertisingWritesDisabled):
        advertising_capabilities.require_advertising_write()
    result = client.get(base + "/optimization/accounts")
    assert result.status_code == 200, result.text
    assert result.headers["Cache-Control"] == "no-store"
    assert result.json()["complete"] is True
    choices = result.json()["accounts"]
    assert len(choices) == 1
    assert set(choices[0]) == {"id", "name", "platform"}
    install(other, runtime)
    login(other, "other-account-owner:1")
    assert other.get(base + "/optimization/accounts").status_code in {403, 404}
    with Session(customer_engine) as db:
        connection = db.scalar(
            select(GoogleCustomerConnection).where(GoogleCustomerConnection.workspace_id == wid)
        )
        assert connection is not None
        connection.status = "disconnected"
        db.commit()
    assert client.get(base + "/optimization/accounts").json()["accounts"] == []


@pytest.mark.planning_boundary
@pytest.mark.parametrize("platform", ["google_ads", "meta_ads", "tiktok_ads"])
def test_configured_optimization_stays_read_only_in_planning(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    replicas: tuple[TestClient, TestClient, FakeProvider],
    monkeypatch: pytest.MonkeyPatch,
    platform: str,
) -> None:
    from app.publication.execution_models import (
        ProviderExecutionAttempt,
        ProviderExecutionMandate,
        ProviderExecutionReview,
        ProviderExposureReservation,
    )
    from sqlalchemy import func, select

    client, other, _ = replicas
    with monkeypatch.context() as historical:
        historical.setattr(advertising_capabilities, "require_advertising_write", lambda: None)
        with Session(customer_engine) as db:
            wid, _, policy, runtime, server = setup(db, configuration, tmp_path, platform)
            mandate = db.scalar(
                select(ProviderExecutionMandate).where(ProviderExecutionMandate.workspace_id == wid)
            )
            assert mandate is not None
            mandate_id = mandate.id
    with pytest.raises(advertising_capabilities.AdvertisingWritesDisabled):
        advertising_capabilities.require_advertising_write()
    assert advertising_capabilities.advertising_writes_enabled() is False
    tables = (
        ProviderExecutionMandate,
        ProviderExecutionReview,
        ProviderExecutionRun,
        ProviderExecutionAttempt,
        ProviderExposureReservation,
    )
    with Session(customer_engine) as db:
        before = tuple(db.scalar(select(func.count()).select_from(table)) for table in tables)
    install(client, runtime)
    install(other, runtime)
    login(client, "optimization-owner:planning")
    login(other, "other-owner:planning")
    base = f"/api/customer/v1/workspaces/{wid}/execution"
    opt = base + "/optimization"
    query = {
        "goal_id": policy.goal_id,
        "goal_revision": policy.goal_revision,
        "account_id": policy.accounts[0].account.account_id,
    }
    options = client.post(opt + "/target-options", json=query, headers=headers(client))
    assert options.status_code == 200, options.text
    assert options.json()["dispatch_qualified"] is False
    assert options.json()["options"][0]["label"] == "Brand Search"
    assert (
        other.post(opt + "/target-options", json=query, headers=headers(other)).status_code == 404
    )
    assert client.get(base + "/mandates").status_code == 200
    assert other.get(base + "/mandates").status_code == 403
    status = client.get(opt + "/capabilities")
    assert status.status_code == 200
    assert status.json()["advertising_writes_enabled"] is False
    assert status.json()["catalog_available"] is False
    assert status.json()["repeat_available"] is False
    assert all(
        not item["initial_available"] and not item["repeat_available"]
        for item in status.json()["providers"]
    )
    for method, path in (
        ("POST", "/mandates"),
        ("PUT", f"/mandates/{mandate_id}"),
        ("POST", f"/mandates/{mandate_id}/consent"),
        ("POST", "/initial-reviews"),
        ("POST", "/repeat-reviews"),
    ):
        denied = client.request(method, opt + path, json={}, headers=headers(client))
        assert denied.status_code == 409, denied.text
        assert denied.json()["detail"] == "advertising_writes_disabled_in_planning_mvp"
    assert len(server.writes if platform == "google_ads" else server.posts) == 0
    with Session(customer_engine) as db:
        after = tuple(db.scalar(select(func.count()).select_from(table)) for table in tables)
        assert after == before
    assert client.delete("/api/customer/v1/session", headers=headers(client)).status_code == 204
    assert client.get(base + "/mandates").status_code == 401
    assert client.get(opt + "/accounts").status_code == 401
    assert (
        client.post(opt + "/target-options", json=query, headers=headers(client)).status_code == 401
    )
