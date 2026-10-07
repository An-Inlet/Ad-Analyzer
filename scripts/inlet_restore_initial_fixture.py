"""Synthetic strict 0075 graph for the native restore drill; no provider IO.

Reports are deliberately insufficient fixtures, not evidence of goal admission,
policy qualification or an executable plan. The observation uses the real Meta
terminal publication seeded by inlet_restore_fixture.
"""

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from app.ads.models import Campaign
from app.campaign_performance.models import PerformanceCompletion
from app.customers.access import CustomerPrincipal
from app.customers.identity import VerifiedIdentity
from app.customers.models import CustomerSession, CustomerUser
from app.initial_planning.capture import read_observation
from app.initial_planning.contracts import (
    CalibrationReportV1,
    CohortV1,
    EfficiencyObjectiveV1,
    InitialPlanningConfiguration,
    InitialPreviewV1,
    ObservationV1,
    PreviewIntentV1,
)
from app.initial_planning.models import (
    CalibrationDependency,
    CalibrationRow,
    ObservationRow,
    PreviewRow,
)
from app.initial_planning.retention import purge_expired_observations
from app.initial_planning.runtime import InitialPlanningRuntime
from app.lifecycle.export_serializers import serialize
from app.lifecycle.privacy import bump_workspace_export_revision, workspace_export_revision
from app.meta.models import MetaConnection
from app.publication.contracts import fingerprint
from app.shopify.security import utc
from fastapi import HTTPException
from sqlalchemy import Engine, insert, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

SESSION_DIGEST = "3" * 64
MODELS = (ObservationRow, CalibrationRow, CalibrationDependency, PreviewRow)


class FixtureIdentity:
    issuer = "restore-fixture"

    def verify(self, token: str) -> VerifiedIdentity:
        raise AssertionError("restore fixture never exchanges tokens")

    def check_active(self, subject: str, authenticated_at: int) -> None:
        assert subject in ("1" * 32, "2" * 32)


def policy() -> InitialPlanningConfiguration:
    return InitialPlanningConfiguration.model_validate(
        dict(
            environment="contract_test",
            policy_family="a" * 32,
            revision=1,
            retention_seconds=86400,
            maximum_observations=16,
            minimum_training_windows=1,
            minimum_holdout_windows=1,
            maximum_report_age_seconds=2147483647,
            minimum_report_age_seconds=0,
            preview_lifetime_seconds=300,
            selected_rule="fixture",
            supported_event="purchase",
            rules=[
                dict(
                    name="fixture",
                    increase_below_ratio="0.8",
                    decrease_above_ratio="1.2",
                    minimum_reported_conversions="1",
                    minimum_spend_micros=0,
                    budget_step_micros=1000000,
                )
            ],
        )
    )


def seed_initial(engine: Engine) -> None:
    with Session(engine) as db:
        now = datetime.now(UTC) - timedelta(hours=1)
        db.add(
            CustomerSession(
                digest=SESSION_DIGEST,
                user_id="2" * 32,
                csrf_digest="c" * 64,
                created_at=int(now.timestamp()),
                authenticated_at=int(now.timestamp()),
                expires_at=2**40,
            )
        )
        completion = db.scalars(select(PerformanceCompletion)).one()
        campaign = db.scalars(
            select(Campaign).where(Campaign.account_id == completion.account_id)
        ).one()
        wid = 902
        cohort = CohortV1(
            workspace_id=wid,
            account_id=completion.account_id,
            campaign_id=campaign.id,
            selected_event="purchase",
            currency="USD",
            time_zone="UTC",
            query_version=completion.query_version,
        )
        observation = ObservationV1(
            id=uuid4().hex,
            cohort=cohort,
            environment="contract_test",
            completion_id=completion.id,
            manifest_digest=completion.manifest_digest,
            generation=1,
            privacy_revision=workspace_export_revision(db, wid),
            starts_on=completion.starts_on,
            ends_on=completion.ends_on,
            completed_at=utc(completion.completed_at),
            captured_at=now,
            expires_at=now + timedelta(days=1),
            retention_policy_digest="a" * 64,
            reported_day_count=1,
            impressions=1000,
            clicks=100,
            spend_micros=100_000_000,
            conversions=Decimal("10"),
            conversion_value_micros=250_000_000,
        )
        owned = dict(workspace_id=wid, account_id=completion.account_id, campaign_id=campaign.id)
        obs = ObservationRow(
            **owned,
            id=observation.id,
            document=observation.model_dump(mode="json"),
            document_digest=observation.digest(),
            expires_at=observation.expires_at,
            environment="contract_test",
            completion_id=completion.id,
            generation=1,
            privacy_revision=observation.privacy_revision,
            cohort_digest=cohort.digest(),
            captured_at=now,
            retention_policy_digest=observation.retention_policy_digest,
        )
        objective = EfficiencyObjectiveV1(
            cohort=cohort, goal_id="b" * 32, goal_revision=1, maximum_reported_cpa_micros=2_000_000
        )
        report = CalibrationReportV1(
            id=uuid4().hex,
            status="insufficient",
            environment="contract_test",
            cohort=cohort,
            objective_digest=objective.digest(),
            policy_digest="a" * 64,
            input_digest="c" * 64,
            observation_ids=(obs.id,),
            training_windows=1,
            holdout_windows=0,
            selected_rule="fixture",
            rules=(),
            reasons=("insufficient_windows",),
            evaluated_at=now,
            expires_at=now + timedelta(minutes=10),
        )
        calibration = CalibrationRow(
            **owned,
            id=report.id,
            document=report.model_dump(mode="json"),
            document_digest=fingerprint(report.schema_version, report.model_dump(mode="json")),
            expires_at=report.expires_at,
            environment="contract_test",
            objective=objective.model_dump(mode="json"),
            objective_digest=objective.digest(),
            policy_digest=report.policy_digest,
            input_digest=report.input_digest,
            created_at=now,
        )
        db.add_all([obs, calibration])
        db.flush()
        db.add(CalibrationDependency(**owned, calibration_id=report.id, observation_id=obs.id))
        document = InitialPreviewV1(
            id=uuid4().hex,
            calibration_id=report.id,
            observation_id=obs.id,
            objective=objective,
            policy_digest=report.policy_digest,
            evidence_digest=observation.digest(),
            recommendation_status="insufficient",
            direction="none",
            reasons=("insufficient_windows",),
            created_at=now,
            expires_at=now + timedelta(minutes=5),
        )
        intent = PreviewIntentV1(
            objective=objective, calibration_id=report.id, observation_id=obs.id
        )
        preview = PreviewRow(
            **owned,
            id=document.id,
            document=document.model_dump(mode="json"),
            document_digest=fingerprint(document.schema_version, document.model_dump(mode="json")),
            expires_at=document.expires_at,
            calibration_id=report.id,
            observation_id=obs.id,
            intent=intent.model_dump(mode="json"),
            original_actor_id="2" * 32,
            original_session_digest=SESSION_DIGEST,
            goal_digest="f" * 64,
            source_generation=1,
            privacy_revision=observation.privacy_revision,
            completion_id=completion.id,
            native_state_digest=None,
            mandate_digest=None,
            created_at=now,
        )
        db.add(preview)
        db.commit()


def verify_initial(engine: Engine) -> None:
    """Every behavioral mutation rolls back, preserving the archive fingerprint."""
    with Session(engine) as db:
        observation = db.scalars(select(ObservationRow)).one()
        for model in MODELS:
            records = list(db.scalars(select(model).where(model.workspace_id == 902)))
            assert len(records) == 1
            assert not list(db.scalars(select(model).where(model.workspace_id == 901)))
            record = records[0]
            raw = {column.name: getattr(record, column.name) for column in model.__table__.columns}
            output, missing = serialize(model.__tablename__, raw)
            assert not missing
            assert "original_session_digest" not in output
            assert SESSION_DIGEST not in json.dumps(output, default=str)
            if "document" in raw:
                assert output["document"] == raw["document"]
                _, rejected = serialize(model.__tablename__, {**raw, "document_digest": "0" * 64})
                assert "document" in rejected
        user = db.get(CustomerUser, "2" * 32)
        session = db.get(CustomerSession, SESSION_DIGEST)
        assert user is not None and session is not None
        principal = CustomerPrincipal(user, session)
        runtime = InitialPlanningRuntime(lambda: Session(engine), policy())
        doc = read_observation(db, principal, FixtureIdentity(), 902, observation.id, runtime)
        assert doc.conversions == Decimal("10") and doc.spend_micros == 100_000_000
        for wid, candidate in (
            (901, runtime),
            (902, replace(runtime, clock=lambda: doc.expires_at)),
        ):
            try:
                read_observation(db, principal, FixtureIdentity(), wid, observation.id, candidate)
            except HTTPException:
                pass
            else:
                raise AssertionError("restored observation scope or expiry guard missing")
        source = db.scalars(select(MetaConnection)).one()
        source.generation += 1
        db.flush()
        try:
            read_observation(db, principal, FixtureIdentity(), 902, observation.id, runtime)
        except HTTPException as error:
            assert error.status_code == 409
        else:
            raise AssertionError("restored observation accepts a different source generation")
        db.rollback()
        session.revoked_at = int(datetime.now(UTC).timestamp())
        db.flush()
        try:
            read_observation(db, principal, FixtureIdentity(), 902, observation.id, runtime)
        except HTTPException as error:
            assert error.status_code == 401
        else:
            raise AssertionError("restored revoked session accepted")
        db.rollback()

    # Expired derived data is deleted by the real configuration-independent worker.
    # External transaction makes its committed sessions reversible for the drill.
    with engine.connect() as connection:
        transaction = connection.begin()
        before = connection.scalar(
            text("SELECT export_privacy_revision FROM workspaces WHERE id=902")
        )
        assert (
            purge_expired_observations(
                lambda: Session(connection, join_transaction_mode="create_savepoint")
            )
            == 1
        )
        assert connection.scalar(text("SELECT count(*) FROM initial_observations")) == 1
        for name in (
            "initial_calibration_runs",
            "initial_calibration_dependencies",
            "initial_plan_previews",
        ):
            assert connection.scalar(text(f"SELECT count(*) FROM {name}")) == 0
        assert (
            connection.scalar(text("SELECT export_privacy_revision FROM workspaces WHERE id=902"))
            == before
        )
        from app.campaign_performance.service import read_current
        from app.publication.execution_authorization import owner_authorizer

        with Session(connection, join_transaction_mode="create_savepoint") as db:
            row = db.scalars(select(ObservationRow)).one()
            current = read_current(
                db,
                902,
                "2" * 32,
                row.account_id,
                row.campaign_id,
                row.completion_id,
                owner_authorizer,
            )
            assert current.reported_day_count == 1
        transaction.rollback()
    with Session(engine) as db:
        db.execute(text("UPDATE workspaces SET status='closing' WHERE id=902"))
        bump_workspace_export_revision(db, 902)
        for model in MODELS:
            assert not list(db.scalars(select(model)))
        assert db.scalar(
            text("SELECT count(*) FROM provider_exposure_reservations WHERE state='held'")
        )
        db.rollback()


def verify_initial_constraints(engine: Engine) -> None:
    for model in (ObservationRow, CalibrationRow, PreviewRow):
        with engine.connect() as db:
            transaction = db.begin()
            try:
                db.execute(
                    text(f"UPDATE {model.__tablename__} SET document_digest=document_digest")
                )
            except DBAPIError:
                transaction.rollback()
            else:
                transaction.rollback()
                raise AssertionError("restored initial document is mutable")
    with engine.connect() as db:
        transaction = db.begin()
        original = dict(db.execute(select(ObservationRow.__table__)).mappings().one())
        try:
            db.execute(
                insert(ObservationRow).values(
                    **{**original, "id": uuid4().hex, "workspace_id": 901}
                )
            )
        except IntegrityError:
            transaction.rollback()
        else:
            transaction.rollback()
            raise AssertionError("restored observation completion ownership missing")
    with Session(engine) as db:
        db.execute(text("SELECT id FROM workspaces WHERE id=902 FOR NO KEY UPDATE"))
        db.execute(text("DELETE FROM initial_calibration_dependencies"))
        assert not list(db.scalars(select(CalibrationRow)))
        assert not list(db.scalars(select(PreviewRow)))
        assert db.scalars(select(ObservationRow)).one()
        db.rollback()
