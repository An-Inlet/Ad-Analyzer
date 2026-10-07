"""Actual report publication, owned capture/calibration, and customer preview APIs."""

import base64
import io
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from urllib.parse import urlsplit

import pytest
from app.ads.models import Campaign
from app.customers.access import CustomerPrincipal
from app.customers.models import CustomerSession, CustomerUser
from app.goals import service as goals
from app.goals.schemas import ConfirmInput
from app.initial_planning import capture
from app.initial_planning.contracts import InitialPlanningConfiguration, RuleParametersV1
from app.initial_planning.runtime import InitialPlanningRuntime
from app.meta import client as wire
from app.meta.client import MetaClient
from app.meta.service import ConnectionService
from app.meta.sync import MetaSyncService
from app.settings import Settings
from pydantic import SecretStr
from sqlalchemy import Engine, select, text
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_goals import seed
from tests.test_customer_identity import FakeProvider
from tests.test_meta_connection import FakeMeta, campaign, insight, page


def explicit_policy() -> InitialPlanningConfiguration:
    return InitialPlanningConfiguration(
        environment="contract_test",
        policy_family="a" * 32,
        revision=1,
        retention_seconds=120 * 86400,
        maximum_observations=8,
        minimum_training_windows=1,
        minimum_holdout_windows=1,
        maximum_report_age_seconds=120 * 86400,
        minimum_report_age_seconds=0,
        preview_lifetime_seconds=60,
        selected_rule="fixture_explicit",
        supported_event="purchase",
        rules=(
            RuleParametersV1(
                name="fixture_explicit",
                increase_below_ratio=Decimal("0.8"),
                decrease_above_ratio=Decimal("1.2"),
                minimum_reported_conversions=Decimal("1"),
                minimum_spend_micros=1,
                budget_step_micros=1000000,
            ),
        ),
    )


def ready_history(
    engine: Engine,
    configuration: Settings,
    monkeypatch: pytest.MonkeyPatch,
    principal: CustomerPrincipal,
    provider: FakeProvider,
) -> tuple[int, str, int, int, InitialPlanningRuntime, list[str]]:
    """Two actual complete 56-day wire imports/captures, then real goal confirmation.

    Customer identity is supplied by caller's real login fixture. No prior action,
    receipt, financial proof, calibrated result or observation is manufactured.
    """
    from app.customers.models import CustomerMembership

    if engine.dialect.name == "sqlite":
        with engine.connect() as connection:
            connection.execute(text("PRAGMA foreign_keys=ON"))
            assert connection.scalar(text("PRAGMA foreign_keys")) == 1
            connection.commit()

    meta = Settings(
        _env_file=None,
        AD_ANALYZER_META_ENABLED=True,
        meta_client_id="100000000000001",
        meta_client_secret=SecretStr("offline-secret-" * 3),
        meta_token_encryption_key=SecretStr(base64.urlsafe_b64encode(b"m" * 32).decode()),
        meta_redirect_uri="https://example.test/dashboard/meta/callback",
    )
    for field in (
        "meta_enabled",
        "meta_client_id",
        "meta_client_secret",
        "meta_token_encryption_key",
        "meta_redirect_uri",
    ):
        setattr(configuration, field, getattr(meta, field))
    from tests import test_commerce_measurement, test_customer_goals

    present = datetime.now(UTC)
    monkeypatch.setattr(test_commerce_measurement, "NOW", present)
    monkeypatch.setattr(test_customer_goals, "NOW", present)
    actor, session_digest = principal.user.id, principal.session.digest
    with Session(engine) as db:
        goal = seed(db, configuration)
        wid, goal_id = goal.workspace_id, goal.id
        db.add(CustomerMembership(workspace_id=wid, user_id=actor, role="owner"))
        db.commit()
        fake = FakeMeta(configuration)
        service = ConnectionService(db, configuration, fake)
        first = present - timedelta(days=56)
        location = service.begin(wid, "fixture-browser", first)
        from urllib.parse import parse_qs

        nonce = parse_qs(urlsplit(location).query)["state"][0]
        pending = service.pending({"state": nonce}, "fixture-browser", first)
        service.finish(pending, "offline-code", "owner", first)
        source = service.select_account(wid, "fixture-browser", "101", "purchase", "owner", first)
        account_id = source.account_id
    clock = [first]
    runtime = InitialPlanningRuntime(
        lambda: Session(engine), explicit_policy(), clock=lambda: clock[0]
    )
    payloads: list[dict[str, Any]] = []
    reads: list[str] = []

    class Opener:
        def open(self, request: Any, timeout: int) -> io.BytesIO:
            parsed = urlsplit(request.full_url)
            assert parsed.hostname == "graph.facebook.com" and request.method == "GET"
            reads.append(parsed.path)
            return io.BytesIO(json.dumps(payloads.pop(0)).encode())

    monkeypatch.setattr(wire, "build_opener", lambda *_: Opener())
    observations = []
    for moment in (first, present):
        clock[0] = moment
        date = (moment - timedelta(days=1)).date().isoformat()
        payloads.extend([page(campaign()), page(), page(insight(date_start=date, date_stop=date))])
        with Session(engine) as db:
            runner = MetaSyncService(db, configuration, MetaClient(configuration))
            for state in ("syncing", "syncing", "complete"):
                assert runner.page(wid, now=moment, manual=True)["status"] == state
            cid = db.scalar(select(Campaign.id).where(Campaign.account_id == account_id))
            assert cid is not None
            user = db.get(CustomerUser, actor)
            session = db.get(CustomerSession, session_digest)
            assert user and session
            observed = capture.capture_current(
                db, CustomerPrincipal(user, session), provider, wid, account_id, cid, runtime
            )
            observations.append(observed.id)
            db.commit()
    with Session(engine) as db:
        goal = goals.owned(db, wid, goal_id)
        context = goals.preview(db, goal, present)
        goals.confirm(
            db,
            goal,
            ConfirmInput(
                expected_revision=goal.revision,
                preview_id=context.id,
                idempotency_key="initial-fixture-confirm",
            ),
            present,
            actor_id=actor,
        )
        db.commit()
    assert cid is not None
    return wid, goal_id, account_id, cid, runtime, observations


@pytest.mark.parametrize("change", [None, "session", "goal", "zero_conversions"])
def test_customer_capture_calibration_preview(
    customer_engine: Engine,
    configuration: Settings,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
    change: str | None,
) -> None:
    from app.api import customer_initial_planning as api
    from app.customers.access import SESSION_COOKIE, digest
    from app.initial_planning.models import PreviewRow
    from app.publication.execution_models import ProviderExecutionApproval, ProviderExecutionAttempt
    from sqlalchemy import func

    from tests.test_customer_identity import login
    from tests.test_customer_optimization_api import headers

    alice, bob, provider = replicas
    actor = login(alice, "alice:1")
    login(bob, "bob:1")
    with Session(customer_engine) as db:
        user = db.get(CustomerUser, actor)
        session = db.get(CustomerSession, digest(alice.cookies[SESSION_COOKIE]))
        assert user and session
        principal = CustomerPrincipal(user, session)
        wid, goal_id, aid, cid, runtime, observations = ready_history(
            customer_engine, configuration, monkeypatch, principal, provider
        )
    for client in (alice, bob):
        client.app.include_router(api.router)
        client.app.dependency_overrides[api.get_initial_planning_runtime] = lambda: runtime
    root = f"/api/customer/v1/workspaces/{wid}/initial-planning"
    assert bob.get(root + "/options").status_code == 404
    option = alice.get(root + "/options")
    assert option.status_code == 200, option.text
    assert option.json()["configured"] and len(option.json()["campaigns"]) == 1
    assert "external_" not in option.text
    assert (
        alice.post(root + "/captures", json={"account_id": aid, "campaign_id": cid}).status_code
        == 403
    )
    captured = alice.post(
        root + "/captures", json={"account_id": aid, "campaign_id": cid}, headers=headers(alice)
    )
    assert captured.status_code == 200, captured.text
    assert captured.json()["id"] == observations[-1]
    report = alice.post(
        root + "/calibrations",
        headers=headers(alice),
        json={
            "observation_id": observations[-1],
            "goal_id": goal_id,
            "goal_revision": 1,
            "maximum_reported_cpa_micros": 10000000,
        },
    )
    assert report.status_code == 200, report.text
    assert report.json()["status"] == "evaluated", report.text
    body = {"calibration_id": report.json()["id"], "observation_id": observations[-1]}
    if change == "session":
        assert alice.delete("/api/customer/v1/session", headers=headers(alice)).status_code == 204
    elif change == "goal":
        with Session(customer_engine) as db:
            goal = goals.owned(db, wid, goal_id)
            goals.revise(db, goal, None, actor, NOW)
            db.commit()
    elif change == "zero_conversions":
        # A corrected source publication is exercised separately; immutable
        # capsules cannot be rewritten to force a favorable test result.
        from app.initial_planning import calibration
        from app.initial_planning.contracts import EfficiencyObjectiveV1, ObservationV1

        observation = ObservationV1.model_validate(captured.json())
        objective = EfficiencyObjectiveV1(
            cohort=observation.cohort,
            goal_id=goal_id,
            goal_revision=1,
            maximum_reported_cpa_micros=10000000,
        )
        assert (
            calibration.classify(
                observation.model_copy(update={"conversions": Decimal(0)}),
                objective,
                explicit_policy().rules[0],
            )
            == "insufficient"
        )
    response = alice.post(root + "/previews", headers=headers(alice), json=body)
    if change in {"session", "goal"}:
        assert response.status_code in {401, 403, 409}, response.text
    else:
        assert response.status_code == 200, response.text
        value = response.json()
        assert value["recommendation_status"] == "proposed" and value["direction"] == "increase"
        assert value["before_budget_micros"] is value["after_budget_micros"] is None
        assert not value["review_available"] and not value["spending_authorized"]
        assert alice.get(root + "/previews/" + value["id"]).status_code == 200
        # A separately valid login for the same owner cannot adopt an earlier
        # session's preview, even while the original session remains valid.
        login(bob, "alice:second-session")
        assert bob.get(root + "/previews/" + value["id"]).status_code == 409
        assert alice.get(root + "/previews/" + value["id"]).status_code == 200
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(PreviewRow)) == (
            0 if change in {"session", "goal"} else 1
        )
        assert db.scalar(select(func.count()).select_from(ProviderExecutionApproval)) == 0
        assert db.scalar(select(func.count()).select_from(ProviderExecutionAttempt)) == 0


from tests.test_customer_identity import customer_engine as customer_engine  # noqa: E402
from tests.test_customer_identity import replicas as replicas  # noqa: E402
from tests.test_shopify_sales import configuration as configuration  # noqa: E402


def test_default_policy_unavailable_and_preview_retention_bound(
    customer_engine: Engine,
    configuration: Settings,
    monkeypatch: pytest.MonkeyPatch,
    replicas: Any,
) -> None:
    from dataclasses import replace

    from app.api import customer_initial_planning as api
    from app.customers.access import SESSION_COOKIE, digest
    from app.initial_planning import limits

    from tests.test_customer_identity import login
    from tests.test_customer_optimization_api import headers

    alice, _, provider = replicas
    actor = login(alice, "alice:1")
    with Session(customer_engine) as db:
        user = db.get(CustomerUser, actor)
        session = db.get(CustomerSession, digest(alice.cookies[SESSION_COOKIE]))
        assert user and session
        wid, gid, aid, cid, runtime, observations = ready_history(
            customer_engine, configuration, monkeypatch, CustomerPrincipal(user, session), provider
        )
    alice.app.include_router(api.router)
    current = [replace(runtime, configuration=None)]
    alice.app.dependency_overrides[api.get_initial_planning_runtime] = lambda: current[0]
    root = f"/api/customer/v1/workspaces/{wid}/initial-planning"
    response = alice.get(root + "/options")
    assert response.status_code == 200 and response.json()["configured"] is False
    response = alice.post(
        root + "/captures", headers=headers(alice), json={"account_id": aid, "campaign_id": cid}
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "initial_planning_configuration_unavailable"
    current[0] = runtime
    report = alice.post(
        root + "/calibrations",
        headers=headers(alice),
        json={
            "observation_id": observations[-1],
            "goal_id": gid,
            "goal_revision": 1,
            "maximum_reported_cpa_micros": 10000000,
        },
    )
    assert report.status_code == 200, report.text
    assert limits.MAX_RETAINED_PREVIEWS_PER_CAMPAIGN == 128
    monkeypatch.setattr(limits, "MAX_RETAINED_PREVIEWS_PER_CAMPAIGN", 1)
    body = {"calibration_id": report.json()["id"], "observation_id": observations[-1]}
    if customer_engine.dialect.name == "postgresql":
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        barrier = Barrier(2)

        def prepare_once() -> Any:
            barrier.wait(timeout=10)
            result = alice.post(root + "/previews", headers=headers(alice), json=body)
            return result

        with ThreadPoolExecutor(max_workers=2) as pool:
            pending = [pool.submit(prepare_once) for _ in range(2)]
            attempts = [future.result(timeout=20) for future in pending]
        assert sorted(result.status_code for result in attempts) == [200, 409]
        response = next(result for result in attempts if result.status_code == 200)
        second = next(result for result in attempts if result.status_code == 409)
    else:
        response = alice.post(root + "/previews", headers=headers(alice), json=body)
        assert response.status_code == 200, response.text
        second = alice.post(root + "/previews", headers=headers(alice), json=body)
    assert second.status_code == 409 and "capacity" in second.text
    from app.initial_planning import calibration
    from app.initial_planning.invalidation import erase_workspace_observations

    assert limits.MAX_RETAINED_CALIBRATIONS_PER_CAMPAIGN == 128
    monkeypatch.setattr(calibration, "MAX_RETAINED_CALIBRATIONS_PER_CAMPAIGN", 1)
    another = alice.post(
        root + "/calibrations",
        headers=headers(alice),
        json={
            "observation_id": observations[-1],
            "goal_id": gid,
            "goal_revision": 1,
            "maximum_reported_cpa_micros": 12000000,
        },
    )
    assert another.status_code == 409 and "capacity" in another.text
    with Session(customer_engine) as db:
        erase_workspace_observations(db, wid)
        db.commit()
    deleted = alice.get(root + "/previews/" + response.json()["id"])
    assert deleted.status_code == 404
