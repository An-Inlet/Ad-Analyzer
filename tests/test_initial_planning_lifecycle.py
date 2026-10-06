"""Owned derived graph erasure, strict export and real archive retention boundaries."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from app.ads.enums import AdvertisingPlatform
from app.ads.models import AdvertisingAccount, Campaign, DailyMetric
from app.campaign_performance.models import CurrentPerformance
from app.campaign_performance.service import publish_meta
from app.initial_planning.contracts import (
    CalibrationReportV1,
    CohortV1,
    EfficiencyObjectiveV1,
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
from app.lifecycle.export_serializers import serialize
from app.lifecycle.privacy import bump_workspace_export_revision, workspace_export_revision
from app.meta.models import MetaConnection
from app.publication.contracts import fingerprint
from app.workspaces.models import Workspace, WorkspaceIntegration
from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session

from tests.test_customer_exports import export_engine as export_engine
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_lifecycle import seed

MODELS = (ObservationRow, CalibrationRow, CalibrationDependency, PreviewRow)


@pytest.fixture(autouse=True)
def enforce_sqlite_foreign_keys(customer_engine: Engine) -> None:
    if customer_engine.dialect.name == "sqlite":
        with customer_engine.connect() as db:
            db.execute(text("PRAGMA foreign_keys=ON"))
            db.commit()


def graph(
    db: Session, wid: int, now: datetime
) -> tuple[ObservationRow, CalibrationRow, PreviewRow]:
    integration = WorkspaceIntegration(
        workspace_id=wid,
        integration_key="initial-" + str(wid),
        provider="meta_ads",
        display_name="Synthetic",
        status="active",
        configuration={},
    )
    db.add(integration)
    db.flush()
    account = AdvertisingAccount(
        workspace_id=wid,
        connection_id=integration.id,
        platform=AdvertisingPlatform.META_ADS,
        external_account_id=str(wid),
        name="Synthetic",
        currency_code="USD",
        time_zone="UTC",
    )
    db.add(account)
    db.flush()
    campaign = Campaign(
        account_id=account.id,
        platform=AdvertisingPlatform.META_ADS,
        external_campaign_id=str(wid),
        name="Synthetic",
    )
    source = MetaConnection(
        workspace_id=wid,
        account_id=account.id,
        workspace_integration_id=integration.id,
        external_account_id=str(wid),
        encrypted_credentials="unusable-fixture",
        generation=1,
        status="connected",
        conversion_action_type="purchase",
        covered_from=now.date(),
        covered_through=now.date(),
        last_sync_at=now,
    )
    db.add_all([campaign, source])
    db.flush()
    db.add(
        DailyMetric(
            platform=AdvertisingPlatform.META_ADS,
            campaign_id=campaign.id,
            entity_type="campaign",
            entity_id=campaign.id,
            metric_date=now.date(),
            impressions=100,
            clicks=10,
            cost_micros=1_000_000,
            conversions=Decimal("2"),
            conversion_value_micros=5_000_000,
        )
    )
    publish_meta(db, source, now.date(), now.date(), now)
    current = db.get(CurrentPerformance, account.id)
    assert current is not None
    from app.campaign_performance.models import PerformanceCompletion

    completion = db.get(PerformanceCompletion, current.completion_id)
    assert completion is not None
    cohort = CohortV1(
        workspace_id=wid,
        account_id=account.id,
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
        starts_on=now.date(),
        ends_on=now.date(),
        completed_at=now,
        captured_at=now,
        expires_at=now + timedelta(hours=1),
        retention_policy_digest="a" * 64,
        reported_day_count=1,
        impressions=100,
        clicks=10,
        spend_micros=1_000_000,
        conversions=Decimal("2"),
        conversion_value_micros=5_000_000,
    )
    owned = dict(workspace_id=wid, account_id=account.id, campaign_id=campaign.id)
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
        expires_at=observation.expires_at,
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
    intent = PreviewIntentV1(objective=objective, calibration_id=report.id, observation_id=obs.id)
    preview = PreviewRow(
        **owned,
        id=document.id,
        document=document.model_dump(mode="json"),
        document_digest=fingerprint(document.schema_version, document.model_dump(mode="json")),
        expires_at=document.expires_at,
        calibration_id=report.id,
        observation_id=obs.id,
        intent=intent.model_dump(mode="json"),
        original_actor_id="d" * 32,
        original_session_digest="e" * 64,
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
    return obs, calibration, preview


def counts(db: Session, wid: int) -> list[int]:
    return [
        db.scalar(select(func.count()).select_from(m).where(m.workspace_id == wid)) or 0
        for m in MODELS
    ]


def test_semantic_erasure_is_scoped_atomic_and_closing_compatible(customer_engine: Engine) -> None:
    with Session(customer_engine) as db:
        _, wid = seed(db)
        _, other = seed(db, "other")
        graph(db, wid, datetime.now(UTC))
        graph(db, other, datetime.now(UTC))
        workspace = db.get(Workspace, wid)
        assert workspace is not None
        workspace.status = "closing"
        db.commit()
        before = workspace_export_revision(db, wid)
        bump_workspace_export_revision(db, wid)
        assert counts(db, wid) == [0, 0, 0, 0]
        assert counts(db, other) == [1, 1, 1, 1]
        db.rollback()
        assert counts(db, wid) == [1, 1, 1, 1]
        assert workspace_export_revision(db, wid) == before
        bump_workspace_export_revision(db, wid)
        db.commit()
        assert counts(db, wid) == [0, 0, 0, 0]
        assert workspace_export_revision(db, wid) > before


def test_expiry_sweep_uses_persisted_deadline_without_configuration(
    customer_engine: Engine,
) -> None:
    from app.initial_planning.runtime import get_initial_planning_configuration

    assert get_initial_planning_configuration() is None
    now = datetime.now(UTC) - timedelta(hours=2)
    with Session(customer_engine) as db:
        _, first = seed(db)
        _, second = seed(db, "other")
        graph(db, first, now)
        graph(db, second, now)
        workspace = db.get(Workspace, first)
        assert workspace is not None
        workspace.status = "closing"
        db.commit()

    def factory() -> Session:
        return Session(customer_engine)

    assert purge_expired_observations(factory, clock=lambda: now) == 0
    assert (
        purge_expired_observations(factory, clock=lambda: now + timedelta(hours=1), batch_limit=1)
        == 1
    )
    with Session(customer_engine) as db:
        assert counts(db, first) == [0, 0, 0, 0]
        assert counts(db, second) == [1, 1, 1, 1]
    assert purge_expired_observations(factory, clock=lambda: now + timedelta(hours=1)) == 1


def test_strict_owned_export_excludes_session_and_rejects_forgery(customer_engine: Engine) -> None:
    with Session(customer_engine) as db:
        _, wid = seed(db)
        records = graph(db, wid, datetime.now(UTC))
        for record in records:
            raw = {c.name: getattr(record, c.name) for c in record.__table__.columns}
            output, missing = serialize(record.__tablename__, raw)
            assert not missing
            assert "original_session_digest" not in output
            assert output["document"] == record.document
            _, missing = serialize(record.__tablename__, {**raw, "workspace_id": wid + 1})
            assert "document" in missing
            _, missing = serialize(record.__tablename__, {**raw, "document_digest": "0" * 64})
            assert "document" in missing
            _, missing = serialize(
                record.__tablename__,
                {**raw, "document": {**record.document, "unreviewed_field": "no"}},
            )
            assert "document" in missing


@pytest.mark.parametrize("phase", ["build", "stream"])
def test_real_archive_stops_at_expiry_without_sweep(
    export_engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    from datetime import tzinfo
    from typing import Self

    from app.campaign_review.storage import LocalMediaStore
    from app.lifecycle import exports
    from app.lifecycle.exports import SLOTS, Download
    from fastapi import HTTPException

    from tests.test_customer_exports import build, prepared

    instant = datetime.now(UTC)

    class Clock(datetime):
        current = instant

        @classmethod
        def now(cls, tz: tzinfo | None = None) -> Self:
            return cls.fromtimestamp(cls.current.timestamp(), tz)

    monkeypatch.setattr(exports, "datetime", Clock)
    authority, wid = prepared(export_engine)
    with Session(export_engine) as db:
        graph(db, wid, instant)
    if phase == "build":
        original = authority.capture_privacy

        def capture(db: Session) -> dict[str, Any]:
            result = original(db)
            Clock.current = instant + timedelta(minutes=5)
            return result

        monkeypatch.setattr(authority, "capture_privacy", capture)
        with pytest.raises(HTTPException, match="retention expired"):
            build(export_engine, authority, LocalMediaStore(tmp_path / "media"))
    else:
        file, manifest = build(export_engine, authority, LocalMediaStore(tmp_path / "media"))
        assert manifest["supported_customer_data_complete"]
        authority.finish(manifest)
        assert SLOTS.acquire(blocking=False)
        download = Download(file, authority)
        chunks = download.chunks()
        assert next(chunks)
        Clock.current = instant + timedelta(minutes=5)
        with pytest.raises(HTTPException, match="retention expired"):
            next(chunks)
        assert file.closed
    with Session(export_engine) as db:
        # No cleanup happened: wall-clock retention itself stopped the archive.
        assert counts(db, wid) == [1, 1, 1, 1]


@pytest.mark.parametrize("operation", ["disconnect", "closure"])
def test_actual_source_disconnect_and_closure_erase_graph(
    customer_engine: Engine, operation: str
) -> None:
    from app.lifecycle.quiescing import quiesce
    from app.meta.service import ConnectionService
    from app.settings import Settings

    from tests.test_customer_identity import FakeProvider
    from tests.test_customer_quiescing import confirmed

    now = datetime.now(UTC)
    with Session(customer_engine) as db:
        principal, wid = seed(db)
        _, other = seed(db, "other")
        graph(db, wid, now)
        graph(db, other, now)
        if operation == "disconnect":
            ConnectionService(db, Settings()).disconnect(wid, "owner")
        else:
            request, evidence = confirmed(db, principal, wid, now)
            row = quiesce(db, principal, FakeProvider(), wid, request, 1, evidence, now)
            db.commit()
            assert row.state == "blocked" and row.disposition_policy is None
        assert counts(db, wid) == [0, 0, 0, 0]
        assert counts(db, other) == [1, 1, 1, 1]


def test_preview_expiry_preserves_retained_observations(customer_engine: Engine) -> None:
    from app.campaign_performance.service import read_current
    from app.publication.execution_authorization import owner_authorizer

    now = datetime.now(UTC) - timedelta(minutes=10)
    with Session(customer_engine) as db:
        principal, wid = seed(db)
        observation, _, _ = graph(db, wid, now)
        before = workspace_export_revision(db, wid)
        aid, cid = observation.account_id, observation.campaign_id
        actor = principal.user.id
    assert purge_expired_observations(lambda: Session(customer_engine)) == 1
    with Session(customer_engine) as db:
        assert counts(db, wid) == [1, 1, 1, 0]
        assert workspace_export_revision(db, wid) == before
        assert (
            read_current(db, wid, actor, aid, cid, None, owner_authorizer).conversions == "2.000000"
        )


@pytest.mark.parametrize("phase", ["build", "stream"])
def test_actual_privacy_erasure_interrupts_owned_archive(
    export_engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    from app.campaign_review.storage import LocalMediaStore
    from app.lifecycle.exports import SLOTS, Download
    from fastapi import HTTPException

    from tests.test_customer_exports import build, prepared

    authority, wid = prepared(export_engine)
    with Session(export_engine) as db:
        graph(db, wid, datetime.now(UTC))

    def erase() -> None:
        with Session(export_engine) as writer:
            bump_workspace_export_revision(writer, wid)
            writer.commit()

    if phase == "build":
        original = authority.capture_privacy

        def capture(db: Session) -> dict[str, Any]:
            result = original(db)
            erase()  # Separate committed writer while the archive snapshot remains open.
            return result

        monkeypatch.setattr(authority, "capture_privacy", capture)
        with pytest.raises(HTTPException, match="invalidated"):
            build(export_engine, authority, LocalMediaStore(tmp_path / "media"))
    else:
        file, manifest = build(export_engine, authority, LocalMediaStore(tmp_path / "media"))
        authority.finish(manifest)
        assert SLOTS.acquire(blocking=False)
        download = Download(file, authority)
        chunks = download.chunks()
        assert next(chunks)
        erase()
        with pytest.raises(HTTPException, match="invalidated"):
            next(chunks)
        assert file.closed


def test_post_lock_expiry_recheck_does_not_erase_replacement(customer_engine: Engine) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event, current_thread

    from sqlalchemy import delete, event

    if customer_engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL workspace lock contention")
    now = datetime.now(UTC)
    with Session(customer_engine) as db:
        _, wid = seed(db)
        _, _, preview = graph(db, wid, now - timedelta(minutes=10))
        old_id = preview.id
        replacement = {c.name: getattr(preview, c.name) for c in PreviewRow.__table__.columns}
    document = InitialPreviewV1.model_validate(replacement["document"]).model_copy(
        update={
            "id": uuid4().hex,
            "created_at": now,
            "expires_at": now + timedelta(minutes=5),
        }
    )
    replacement.update(
        id=document.id,
        document=document.model_dump(mode="json"),
        document_digest=fingerprint(document.schema_version, document.model_dump(mode="json")),
        created_at=now,
        expires_at=document.expires_at,
    )
    waiting = Event()
    parent = current_thread()

    def observe(
        _conn: Any, _cursor: Any, statement: str, _params: Any, _context: Any, _many: bool
    ) -> None:
        if (
            current_thread() is not parent
            and "workspaces" in statement
            and "FOR NO KEY UPDATE" in statement
        ):
            waiting.set()

    def factory() -> Session:
        db = Session(customer_engine)
        db.execute(text("SET LOCAL lock_timeout='5s'"))
        return db

    event.listen(customer_engine, "before_cursor_execute", observe)
    try:
        with Session(customer_engine) as writer, ThreadPoolExecutor(max_workers=1) as pool:
            writer.execute(
                select(Workspace.id).where(Workspace.id == wid).with_for_update(key_share=True)
            )
            future = pool.submit(purge_expired_observations, factory)
            try:
                assert waiting.wait(5), "purge never reached workspace fence"
                writer.execute(delete(PreviewRow).where(PreviewRow.id == old_id))
                writer.add(PreviewRow(**replacement))
                writer.commit()
                assert future.result(timeout=10) == 0
            finally:
                writer.rollback()
    finally:
        event.remove(customer_engine, "before_cursor_execute", observe)
    with Session(customer_engine) as db:
        assert counts(db, wid) == [1, 1, 1, 1]
        assert db.get(PreviewRow, document.id) is not None


def test_database_deadline_denies_archive_with_lagging_application_clock(
    export_engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from datetime import tzinfo
    from typing import Self

    from app.campaign_review.storage import LocalMediaStore
    from app.lifecycle import exports
    from fastapi import HTTPException

    from tests.test_customer_exports import build, prepared

    instant = datetime.now(UTC) - timedelta(minutes=10)

    class LaggingClock(datetime):
        @classmethod
        def now(cls, tz: tzinfo | None = None) -> Self:
            return cls.fromtimestamp(instant.timestamp(), tz)

    authority, wid = prepared(export_engine)
    with Session(export_engine) as db:
        graph(db, wid, instant)
    monkeypatch.setattr(exports, "datetime", LaggingClock)
    with pytest.raises(HTTPException, match="retention expired"):
        build(export_engine, authority, LocalMediaStore(tmp_path / "media"))


def test_ahead_runtime_clock_cannot_purge_database_unexpired_data(customer_engine: Engine) -> None:
    instant = datetime.now(UTC)
    with Session(customer_engine) as db:
        _, wid = seed(db)
        graph(db, wid, instant)
    assert (
        purge_expired_observations(
            lambda: Session(customer_engine), clock=lambda: instant + timedelta(days=2)
        )
        == 0
    )
    with Session(customer_engine) as db:
        assert counts(db, wid) == [1, 1, 1, 1]


def test_actual_housekeeping_runs_cleanup_with_capture_disabled(
    customer_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.analysis import cadence
    from app.initial_planning.runtime import get_initial_planning_configuration
    from app.jobs import customer_runtime, google_ads_scheduler
    from app.meta import sync as meta_sync
    from app.shopify import privacy
    from app.shopify import sync as shopify_sync

    assert get_initial_planning_configuration() is None
    with Session(customer_engine) as db:
        _, wid = seed(db)
        graph(db, wid, datetime.now(UTC) - timedelta(minutes=10))
        workspace = db.get(Workspace, wid)
        assert workspace is not None
        workspace.status = "closing"
        db.commit()
    # Other independent jobs are outside this runtime-wiring check. The real
    # retention function is imported and called by the production dispatcher.
    for module, name in (
        (privacy, "purge_expired_facts"),
        (privacy, "run_privacy_tick"),
        (shopify_sync, "run_shopify_tick"),
        (meta_sync, "run_meta_tick"),
        (customer_runtime, "run_customer_tick"),
        (cadence, "run_analysis_tick"),
    ):
        monkeypatch.setattr(module, name, lambda *_: None)
    assert google_ads_scheduler._run_analysis_tick(customer_engine, None)
    with Session(customer_engine) as db:
        assert counts(db, wid) == [1, 1, 1, 0]
