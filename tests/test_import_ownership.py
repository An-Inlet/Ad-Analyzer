import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest
from app.ads.enums import AdvertisingPlatform, JobRunStatus
from app.ads.models import AdvertisingAccount, Campaign, JobRun
from app.ads.repository import AdvertisingMetricsRepository
from app.ads.schemas import CampaignCreate
from app.crm.models import CrmConnection, CrmEventRecord
from app.crm.worker import CrmEventProcessor, handle_message
from app.imports.models import ImportRejection
from app.imports.scope import (
    AdvertisingImportScope,
    ImportScopeError,
    google_scope,
    validate_advertising_scope,
)
from app.settings import Settings
from app.workspaces.models import Workspace, WorkspaceIntegration
from sqlalchemy import Engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.test_crm_worker import Message
from tests.test_customer_identity import customer_engine as customer_engine


@pytest.fixture()
def owned_engine(customer_engine: Engine) -> Engine:
    if customer_engine.dialect.name == "sqlite":
        with customer_engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
    with Session(customer_engine) as db:
        db.add_all(
            [
                Workspace(id=10, slug="brand-a", name="A", client_name="A"),
                Workspace(id=20, slug="brand-b", name="B", client_name="B"),
            ]
        )
        db.flush()
        for connection_id, workspace_id, provider in [
            (101, 10, "google_ads"),
            (201, 20, "google_ads"),
            (102, 10, "hubspot"),
            (103, 10, "omnisend"),
            (202, 20, "hubspot"),
        ]:
            db.add(
                WorkspaceIntegration(
                    id=connection_id,
                    workspace_id=workspace_id,
                    integration_key=f"fixture-{connection_id}",
                    provider=provider,
                    display_name=provider,
                    status="active",
                    configuration={},
                    secret_manager_reference=f"projects/fake/secrets/{connection_id}/versions/1",
                )
            )
        db.flush()
        for account_id, workspace_id, connection_id in [(11, 10, 101), (21, 20, 201)]:
            db.add(
                AdvertisingAccount(
                    id=account_id,
                    workspace_id=workspace_id,
                    connection_id=connection_id,
                    platform=AdvertisingPlatform.GOOGLE_ADS,
                    external_account_id="1234567890",
                    name="Shared external ID",
                    currency_code="USD",
                )
            )
        for native_id, workspace_id, connection_id in [(1, 10, 102), (2, 10, 103), (3, 20, 202)]:
            db.add(
                CrmConnection(
                    id=native_id,
                    workspace_id=workspace_id,
                    workspace_integration_id=connection_id,
                    name=f"crm-{native_id}",
                    status="active",
                    secret_manager_reference=f"projects/fake/secrets/{connection_id}/versions/1",
                )
            )
        db.commit()
    return customer_engine


def crm_event(
    workspace: int = 10, connection: int = 102, provider: str = "hubspot"
) -> dict[str, object]:
    return {
        "payload_version": 2,
        "workspace_id": workspace,
        "connection_id": connection,
        "provider": provider,
        "event_id": "same-provider-event",
        "crm_lead_id": "same-lead",
        "event_type": "lead_created",
        "occurred_at": datetime.now(UTC).isoformat(),
    }


def test_identical_external_accounts_stay_in_their_owned_scope(owned_engine: Engine) -> None:
    with Session(owned_engine) as db:
        a = AdvertisingImportScope(10, 101, 11, AdvertisingPlatform.GOOGLE_ADS)
        b = AdvertisingImportScope(20, 201, 21, AdvertisingPlatform.GOOGLE_ADS)
        assert validate_advertising_scope(db, a)[0].id == 11
        assert validate_advertising_scope(db, b)[0].id == 21
        assert a.lock_key(1) != b.lock_key(1)
        for bad in [
            AdvertisingImportScope(10, 201, 11, a.platform),
            AdvertisingImportScope(20, 101, 21, a.platform),
            AdvertisingImportScope(10, 101, 21, a.platform),
            AdvertisingImportScope(10, 101, 11, AdvertisingPlatform.META_ADS),
        ]:
            with pytest.raises(ImportScopeError):
                validate_advertising_scope(db, bad)


def test_database_rejects_cross_workspace_job_connection(owned_engine: Engine) -> None:
    with Session(owned_engine) as db:
        db.add(
            JobRun(
                workspace_id=10,
                connection_id=201,
                account_id=11,
                platform=AdvertisingPlatform.GOOGLE_ADS,
                job_name="scope-test",
                status=JobRunStatus.RUNNING,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        assert db.scalar(select(func.count()).select_from(JobRun)) == 0


def test_collector_cannot_persist_another_accounts_campaign(owned_engine: Engine) -> None:
    with Session(owned_engine) as db:
        repository = AdvertisingMetricsRepository(db)
        repository.scope = AdvertisingImportScope(10, 101, 11, AdvertisingPlatform.GOOGLE_ADS)
        with pytest.raises(ImportScopeError):
            repository.upsert_campaign(
                CampaignCreate(
                    account_id=21,
                    platform=AdvertisingPlatform.GOOGLE_ADS,
                    external_campaign_id="foreign",
                    name="Foreign",
                )
            )
        assert db.scalar(select(func.count()).select_from(Campaign)) == 0


def test_crm_two_active_connections_and_two_workspaces_are_independent(
    owned_engine: Engine,
) -> None:
    with Session(owned_engine) as db:
        worker = CrmEventProcessor(db)
        for event in [crm_event(), crm_event(10, 103, "omnisend"), crm_event(20, 202)]:
            assert worker.process(event)
            assert not worker.process(event)
        rows = db.scalars(select(CrmEventRecord).order_by(CrmEventRecord.connection_id)).all()
        assert [r.connection_id for r in rows] == [1, 2, 3]
        assert len({r.external_event_id for r in rows}) == 1


@pytest.mark.parametrize(
    "changed",
    [
        {"workspace_id": 20},
        {"connection_id": 999},
        {"provider": "klaviyo"},
        {"connection_id": True},
        {"workspace_id": None},
        {"payload_version": 1},
    ],
)
def test_crm_rejects_missing_or_mismatched_scope(
    owned_engine: Engine, changed: dict[str, object]
) -> None:
    with Session(owned_engine) as db:
        with pytest.raises(ImportScopeError):
            CrmEventProcessor(db).process({**crm_event(), **changed})
        assert db.scalar(select(func.count()).select_from(CrmEventRecord)) == 0


def test_revoked_connection_after_enqueue_and_legacy_message_are_quarantined(
    owned_engine: Engine,
) -> None:
    queued = crm_event()
    with Session(owned_engine) as db:
        connection = db.get(WorkspaceIntegration, 102)
        assert connection is not None
        connection.status = "revoked"
        db.commit()
    with Session(owned_engine) as db:
        for payload in [queued, {"payload_version": 1, "event_id": "private-raw-event"}]:
            message = Message(json.dumps(payload).encode())
            handle_message(message, db)
            assert message.nacked and not message.acked
        rows = db.scalars(select(ImportRejection)).all()
        assert len(rows) == 2
        assert all(row.reason == "crm_scope_rejected" and len(row.digest) == 64 for row in rows)
        assert db.scalar(select(func.count()).select_from(CrmEventRecord)) == 0


def test_concurrent_crm_delivery_claims_one_scoped_event(owned_engine: Engine) -> None:
    if owned_engine.dialect.name != "postgresql":
        return
    event = crm_event()

    def process(_: int) -> bool:
        with Session(owned_engine) as db:
            return CrmEventProcessor(db).process(event)

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(process, (1, 2))) == [False, True]


def test_missing_google_dispatch_scope_fails_closed() -> None:
    with pytest.raises(ImportScopeError):
        google_scope(
            Settings(
                _env_file=None,
                INLET_GOOGLE_ADS_WORKSPACE_ID=None,
                INLET_GOOGLE_ADS_CONNECTION_ID=None,
                INLET_GOOGLE_ADS_ACCOUNT_ID=None,
            )
        )


def test_suspended_workspace_cannot_import_through_existing_native_binding(
    owned_engine: Engine,
) -> None:
    from app.imports.scope import ensure_native_integration

    with Session(owned_engine) as db:
        workspace = db.get(Workspace, 10)
        assert workspace is not None
        workspace.status = "suspended"
        db.commit()
        with pytest.raises(ImportScopeError):
            ensure_native_integration(
                db, workspace_id=10, provider="hubspot", source_key="unused", connection_id=102
            )
        with pytest.raises(ImportScopeError):
            CrmEventProcessor(db).process(crm_event())


def test_real_google_worker_persists_scope_and_does_not_retry_after_analysis_failure(
    owned_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if owned_engine.dialect.name != "postgresql":
        return
    from app.collectors import google_ads
    from app.jobs import google_ads_scheduler, google_ads_sync_once
    from app.jobs.reliability import run_cycle

    from tests.test_google_ads_sync import GoogleAdsCollectorStub

    configuration = Settings(
        _env_file=None,
        INLET_GOOGLE_ADS_WORKSPACE_ID=10,
        INLET_GOOGLE_ADS_CONNECTION_ID=101,
        INLET_GOOGLE_ADS_ACCOUNT_ID=11,
        INLET_GOOGLE_ADS_CREDENTIALS_REFERENCE="projects/fake/secrets/101/versions/1",
        GOOGLE_ADS_CUSTOMER_ID="1234567890",
    )
    collector = GoogleAdsCollectorStub(account_external_id="1234567890")
    for name in (
        "collect_account",
        "collect_campaigns",
        "collect_ad_groups",
        "collect_ads",
        "collect_keywords",
        "collect_search_terms",
        "collect_metrics",
    ):
        monkeypatch.setattr(google_ads, name, getattr(collector, name))
    monkeypatch.setattr(google_ads_scheduler, "_run_analysis_tick", lambda *args: None)

    def analysis_fails(*args: object) -> None:
        raise RuntimeError("synthetic downstream analysis failure")

    result = google_ads_sync_once.main(
        lambda: (configuration, owned_engine, run_cycle, JobRunStatus), analysis_fails
    )
    assert result == 0
    with Session(owned_engine) as db:
        job = db.scalars(select(JobRun)).one()
        assert (job.workspace_id, job.connection_id, job.account_id) == (10, 101, 11)
        assert job.status == JobRunStatus.SUCCEEDED
        assert db.scalar(select(func.count()).select_from(Campaign)) == 1
        assert db.scalar(select(func.count()).select_from(JobRun)) == 1


def test_google_worker_rejects_legacy_and_mismatched_dispatch_before_collector(
    owned_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if owned_engine.dialect.name != "postgresql":
        return
    from app.collectors import google_ads
    from app.jobs.reliability import run_cycle

    monkeypatch.setattr(
        google_ads, "collect_account", lambda **kwargs: pytest.fail("must not collect")
    )
    with pytest.raises(ImportScopeError):
        run_cycle(
            Settings(
                _env_file=None,
                INLET_GOOGLE_ADS_WORKSPACE_ID=None,
                INLET_GOOGLE_ADS_CONNECTION_ID=None,
                INLET_GOOGLE_ADS_ACCOUNT_ID=None,
            ),
            owned_engine,
        )
    configuration = Settings(
        _env_file=None,
        INLET_GOOGLE_ADS_WORKSPACE_ID=10,
        INLET_GOOGLE_ADS_CONNECTION_ID=201,
        INLET_GOOGLE_ADS_ACCOUNT_ID=11,
        INLET_GOOGLE_ADS_CREDENTIALS_REFERENCE="projects/fake/secrets/101/versions/1",
        GOOGLE_ADS_CUSTOMER_ID="1234567890",
    )
    with pytest.raises(ImportScopeError):
        run_cycle(configuration, owned_engine)
    with Session(owned_engine) as db:
        assert db.scalar(select(func.count()).select_from(JobRun)) == 0
