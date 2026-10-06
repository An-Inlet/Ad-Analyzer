"""Real mocked Meta HTTP publication into prospective owned capsules, both databases."""

from dataclasses import replace
from datetime import timedelta

import pytest
from app.customers.access import CustomerPrincipal
from app.customers.models import CustomerSession, CustomerUser
from app.initial_planning.capture import capture_current, read_observation
from app.initial_planning.invalidation import erase_workspace_observations
from app.initial_planning.models import ObservationRow
from app.initial_planning.runtime import InitialPlanningRuntime
from app.lifecycle.privacy import database_utc_now
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, delete, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from tests.test_campaign_performance import finish, setup
from tests.test_customer_identity import FakeProvider
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_initial_calibration import policy
from tests.test_meta_connection import configuration as configuration


def ready(db: Session, engine: Engine, config: Settings, monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    source, actor, _, token, payloads, _, runner = setup(db, config, monkeypatch)
    cid = finish(db, source, runner)
    user, session = db.get(CustomerUser, actor), db.get(CustomerSession, token)
    assert user and session
    principal = CustomerPrincipal(user, session)
    provider = FakeProvider()
    provider.issuer = user.issuer
    now = database_utc_now(db)
    runtime = InitialPlanningRuntime(sessionmaker(engine), policy(), clock=lambda: now)
    return source, cid, principal, provider, runtime, payloads, runner


def test_capture_actual_values_idempotency_ownership_and_immutable(
    customer_engine: Engine, configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    with Session(customer_engine) as db:
        source, cid, actor, provider, runtime, _, _ = ready(
            db, customer_engine, configuration, monkeypatch
        )
        item = capture_current(
            db, actor, provider, source.workspace_id, source.account_id, cid, runtime
        )
        assert item.spend_micros == 10000001 and str(item.conversions) == "3.000000"
        assert item.reported_day_count == 1  # Never infer unreported days as observed zero.
        assert (
            capture_current(
                db, actor, provider, source.workspace_id, source.account_id, cid, runtime
            )
            == item
        )
        db.commit()
        assert read_observation(db, actor, provider, source.workspace_id, item.id, runtime) == item
        with pytest.raises(HTTPException):
            read_observation(db, actor, provider, source.workspace_id + 1, item.id, runtime)
        db.rollback()
        row = db.get(ObservationRow, item.id)
        assert row
        row.document_digest = "f" * 64
        with pytest.raises(DBAPIError):
            db.flush()
        db.rollback()
        assert read_observation(db, actor, provider, source.workspace_id, item.id, runtime) == item


@pytest.mark.parametrize("change", ["expiry", "generation", "event", "session", "policy", "erase"])
def test_capture_invalidation(
    customer_engine: Engine, configuration: Settings, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    with Session(customer_engine) as db:
        source, cid, actor, provider, runtime, _, _ = ready(
            db, customer_engine, configuration, monkeypatch
        )
        item = capture_current(
            db, actor, provider, source.workspace_id, source.account_id, cid, runtime
        )
        db.commit()
        if change == "expiry":
            runtime = replace(runtime, clock=lambda: item.expires_at)
        if change == "generation":
            source.generation += 1
        if change == "event":
            source.conversion_action_type = "offsite_conversion.fb_pixel_purchase"
        if change == "session":
            actor.session.revoked_at = 1
        if change == "policy":
            runtime = replace(runtime, configuration=None)
        if change == "erase":
            erase_workspace_observations(db, source.workspace_id)
        db.flush()
        with pytest.raises(HTTPException):
            read_observation(db, actor, provider, source.workspace_id, item.id, runtime)


def test_retention_configuration_never_extends_capsule(
    customer_engine: Engine, configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    with Session(customer_engine) as db:
        source, cid, actor, provider, runtime, _, _ = ready(
            db, customer_engine, configuration, monkeypatch
        )
        item = capture_current(
            db, actor, provider, source.workspace_id, source.account_id, cid, runtime
        )
        assert runtime.configuration
        changed = replace(
            runtime,
            configuration=runtime.configuration.model_copy(update={"retention_seconds": 1000000}),
            clock=lambda: runtime.clock() + timedelta(seconds=1),
        )
        assert (
            capture_current(
                db, actor, provider, source.workspace_id, source.account_id, cid, changed
            ).expires_at
            == item.expires_at
        )
        db.execute(delete(ObservationRow).where(ObservationRow.id == item.id))
        assert not list(db.scalars(select(ObservationRow)))


@pytest.mark.parametrize("expire", [False, True])
def test_dependency_delete_erases_parent_and_expiry_export_fence(
    customer_engine: Engine, configuration: Settings, monkeypatch: pytest.MonkeyPatch, expire: bool
) -> None:
    from datetime import UTC, datetime

    from app.initial_planning.calibration import evaluate
    from app.initial_planning.models import CalibrationDependency, CalibrationRow
    from app.lifecycle.privacy import workspace_export_revision

    from tests.test_initial_calibration import objective

    with Session(customer_engine) as db:
        source, cid, actor, provider, runtime, _, _ = ready(
            db, customer_engine, configuration, monkeypatch
        )
        item = capture_current(
            db, actor, provider, source.workspace_id, source.account_id, cid, runtime
        )
        assert runtime.configuration
        obj = objective(item)
        report = evaluate((item,), obj, runtime.configuration, runtime.clock())
        expiry = datetime.now(UTC) + timedelta(hours=-1 if expire else 1)
        db.add(
            CalibrationRow(
                id=report.id,
                workspace_id=source.workspace_id,
                account_id=source.account_id,
                campaign_id=cid,
                document=report.model_dump(mode="json"),
                document_digest=report.digest(),
                expires_at=expiry,
                environment=report.environment,
                objective=obj.model_dump(mode="json"),
                objective_digest=obj.digest(),
                policy_digest=report.policy_digest,
                input_digest=report.input_digest,
                created_at=report.evaluated_at,
            )
        )
        db.flush()
        db.add(
            CalibrationDependency(
                calibration_id=report.id,
                observation_id=item.id,
                workspace_id=source.workspace_id,
                account_id=source.account_id,
                campaign_id=cid,
            )
        )
        db.commit()
        revision = workspace_export_revision(db, source.workspace_id)
        db.execute(
            delete(CalibrationDependency).where(CalibrationDependency.calibration_id == report.id)
        )
        db.flush()
        assert db.get(CalibrationRow, report.id, populate_existing=True) is None
        assert db.get(ObservationRow, item.id) is not None
        assert (workspace_export_revision(db, source.workspace_id) > revision) is not expire
        if expire:
            assert (
                capture_current(
                    db, actor, provider, source.workspace_id, source.account_id, cid, runtime
                )
                == item
            )  # Expired derived deletion does not demand a new provider import.


def test_database_expiry_overrides_lagging_application_clock(
    customer_engine: Engine, configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    from datetime import UTC, datetime

    from app.initial_planning.clock import effective_now

    with Session(customer_engine) as db:
        runtime = InitialPlanningRuntime(
            sessionmaker(customer_engine), policy(), clock=lambda: datetime(2000, 1, 1, tzinfo=UTC)
        )
        assert effective_now(db, runtime) >= datetime.now(UTC) - timedelta(seconds=1)


def test_calibration_capacity_counts_expired_without_cross_environment_pooling(
    customer_engine: Engine, configuration: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uuid import uuid4

    from app.initial_planning.calibration import evaluate, require_calibration_capacity
    from app.initial_planning.limits import MAX_RETAINED_CALIBRATIONS_PER_CAMPAIGN
    from app.initial_planning.models import CalibrationRow

    from tests.test_initial_calibration import objective

    with Session(customer_engine) as db:
        source, cid, actor, provider, runtime, _, _ = ready(
            db, customer_engine, configuration, monkeypatch
        )
        item = capture_current(
            db, actor, provider, source.workspace_id, source.account_id, cid, runtime
        )
        assert runtime.configuration
        obj = objective(item)
        report = evaluate((item,), obj, runtime.configuration, runtime.clock())
        for _ in range(MAX_RETAINED_CALIBRATIONS_PER_CAMPAIGN):
            db.add(
                CalibrationRow(
                    id=uuid4().hex,
                    workspace_id=source.workspace_id,
                    account_id=source.account_id,
                    campaign_id=cid,
                    document=report.model_dump(mode="json"),
                    document_digest=report.digest(),
                    expires_at=item.completed_at - timedelta(days=1),
                    environment="contract_test",
                    objective=obj.model_dump(mode="json"),
                    objective_digest=obj.digest(),
                    policy_digest=report.policy_digest,
                    input_digest=report.input_digest,
                    created_at=report.evaluated_at,
                )
            )
        db.flush()
        with pytest.raises(HTTPException, match="initial_calibration_capacity_reached"):
            require_calibration_capacity(
                db, source.workspace_id, source.account_id, cid, "contract_test"
            )
        require_calibration_capacity(db, source.workspace_id, source.account_id, cid, "live")
        require_calibration_capacity(
            db, source.workspace_id + 1, source.account_id, cid, "contract_test"
        )
