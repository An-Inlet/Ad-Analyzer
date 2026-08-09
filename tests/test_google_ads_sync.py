import os
import subprocess
import sys
import traceback
from collections.abc import Callable, Generator
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from datetime import date
from decimal import Decimal
from importlib import import_module
from pathlib import Path
from sqlite3 import Connection as SQLiteConnection
from threading import Barrier, Event
from types import TracebackType
from typing import Any

import pytest
from app.ads.enums import AdvertisingPlatform, JobRunStatus
from app.ads.models import (
    Ad,
    AdGroup,
    AdvertisingAccount,
    Campaign,
    DailyMetric,
    JobRun,
    Keyword,
    SearchTerm,
)
from app.ads.repository import AdvertisingMetricsRepository
from app.ads.schemas import (
    AdCreate,
    AdGroupCreate,
    AdvertisingAccountCreate,
    CampaignCreate,
    DailyMetricCreate,
    KeywordCreate,
    NormalizedMetricsBatch,
    SearchTermCreate,
)
from app.ads.services import (
    FAILED_JOB_RUN_PERSISTENCE_ERROR,
    FAILED_JOB_RUN_UNKNOWN_COMMIT_OUTCOME_ERROR,
    UNKNOWN_COMMIT_OUTCOME_ERROR,
    GoogleAdsSyncError,
    GoogleAdsSyncResult,
    GoogleAdsSyncService,
    SyncFailureClassification,
)
from app.collectors import google_ads
from app.database.session import Base
from app.workspaces.models import Workspace
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import ConnectionPoolEntry

sync_google_ads_script = import_module("scripts.sync_google_ads")

SECRET_VALUES = [
    "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e",
    "1//0g-refresh-token-realistic-value",
    "dev-token-realistic-value",
    "P@ssw0rd-realistic-value",
    "Bearer ya29.realistic-authorization-value",
    "serialized-credential-realistic-value",
]

SECRET_FAILURE_MESSAGE = (
    f"client_secret={SECRET_VALUES[0]} refresh_token={SECRET_VALUES[1]} "
    f"developer_token={SECRET_VALUES[2]} password={SECRET_VALUES[3]} "
    f"Authorization: {SECRET_VALUES[4]} credentials={SECRET_VALUES[5]} "
    "raw_response={'request_id': 'abc123', 'details': 'private-api-response'} "
    "sql='postgresql://user:db-password@example.invalid/db'"
)
PERSISTENCE_FAILURE_MESSAGE = (
    "sqlalchemy.exc.OperationalError: could not persist failed job_run "
    f"params={{'client_secret': '{SECRET_VALUES[0]}', 'refresh_token': '{SECRET_VALUES[1]}'}} "
    "dsn='postgresql://user:db-password@example.invalid/denticode' "
    "sql='INSERT INTO job_runs (...) VALUES (...)'"
)
COMMIT_FAILURE_MESSAGE = (
    "psycopg.OperationalError: connection closed during COMMIT "
    f"params={{'developer_token': '{SECRET_VALUES[2]}'}} "
    "dsn='postgresql://user:db-password@example.invalid/denticode' "
    "sql='COMMIT'"
)
SANITIZED_SYNC_ERROR = "Google Ads read-only sync failed (RuntimeError)"


class SessionContext:
    def __init__(self, session: Session) -> None:
        self.session = session

    def __enter__(self) -> Session:
        return self.session

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback_value: TracebackType | None,
    ) -> None:
        return None


def patch_cli_runtime(monkeypatch: pytest.MonkeyPatch, session: Session) -> None:
    monkeypatch.setattr(
        sync_google_ads_script,
        "_load_runtime",
        lambda: (
            GoogleAdsSyncError,
            GoogleAdsSyncService,
            lambda: SessionContext(session),
        ),
    )


class TestPhase7Lock:
    key = 1
    backend_pid = 1

    def owns_current_session(self, _session: Session) -> bool:
        return True


class TestPhase7Connection:
    invalidated = False


def make_phase7_capability(
    session: Session,
    *,
    lock: Any | None = None,
    stop_requested: Callable[[], bool] | None = None,
) -> Any:
    from app.ads.services import Phase7SyncCapability

    class TestCapability(Phase7SyncCapability):
        def __init__(self) -> None:
            self.lock = lock or TestPhase7Lock()
            self.stop_requested = stop_requested or (lambda: False)

        def validate(self, _session: Session) -> None:
            if self.stop_requested():
                raise GoogleAdsSyncError("Google Ads synchronization interrupted before retry.")
            if not self.lock.owns_current_session(_session):
                raise GoogleAdsSyncError(
                    "Google Ads synchronization lost advisory-lock ownership.",
                    lock_lost=True,
                )

        def invalidate(self) -> None:
            return None

    return TestCapability()


def sync_without_worker_for_tests(
    session: Session,
    *,
    date_range: google_ads.GoogleAdsDateRange = google_ads.GoogleAdsDateRange.LAST_7_DAYS,
    lock: Any | None = None,
    stop_requested: Callable[[], bool] | None = None,
) -> GoogleAdsSyncResult:
    service = GoogleAdsSyncService(session)
    repository = service.repository
    job_run = repository.create_job_run(
        platform=AdvertisingPlatform.GOOGLE_ADS,
        job_name=service.job_name,
        status=JobRunStatus.RUNNING,
    )
    success_commit_started = False
    captured_exc: Exception | None = None
    try:
        session.flush()
        result = service._collect_and_persist(
            job_run,
            date_range=date_range,
            capability=make_phase7_capability(session, lock=lock, stop_requested=stop_requested),
        )
        success_commit_started = True
        session.commit()
        return result
    except Exception as exc:
        captured_exc = exc

    if success_commit_started:
        with suppress(Exception):
            session.rollback()
        raise GoogleAdsSyncError(
            UNKNOWN_COMMIT_OUTCOME_ERROR,
            classification=SyncFailureClassification.UNKNOWN_COMMIT_OUTCOME,
        ) from None

    assert captured_exc is not None
    records_processed = service._last_records_processed
    resolved_account = service._last_resolved_account
    sanitized_error_message = service._sanitize_error(captured_exc)
    classification = service._classify_failure(captured_exc)
    failed_commit_started = False
    final_error: GoogleAdsSyncError | None = None
    try:
        session.rollback()
        failed_account_id = service._resolve_durable_failed_run_account_id(resolved_account)
        failed_job_run = repository.create_job_run(
            platform=AdvertisingPlatform.GOOGLE_ADS,
            job_name=service.job_name,
            status=JobRunStatus.FAILED,
            account_id=failed_account_id,
        )
        repository.finish_job_run(
            failed_job_run,
            status=JobRunStatus.FAILED,
            records_processed=records_processed,
            error_message=sanitized_error_message,
        )
        session.flush()
        failed_commit_started = True
        session.commit()
        final_error = GoogleAdsSyncError(sanitized_error_message, classification=classification)
    except Exception:
        with suppress(Exception):
            session.rollback()
        final_error = GoogleAdsSyncError(
            FAILED_JOB_RUN_UNKNOWN_COMMIT_OUTCOME_ERROR
            if failed_commit_started
            else FAILED_JOB_RUN_PERSISTENCE_ERROR,
            classification=SyncFailureClassification.UNKNOWN_COMMIT_OUTCOME,
        )
    raise final_error


def enable_sqlite_foreign_keys(
    dbapi_connection: SQLiteConnection, _connection_record: ConnectionPoolEntry
) -> None:
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


@pytest.fixture()
def session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite:///:memory:")
    event.listen(engine, "connect", enable_sqlite_foreign_keys)
    Base.metadata.create_all(engine)
    local_session = sessionmaker(bind=engine)
    db = local_session()
    db.add(
        Workspace(
            id=1,
            slug="denticode",
            name="Denticode Ad Analyzer",
            client_name="Denticode",
            status="active",
            is_default=True,
        )
    )
    db.commit()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)


class GoogleAdsCollectorStub:
    def __init__(
        self,
        *,
        account_external_id: str = "acct-1",
        account_name: str = "Denticode Search",
        campaign_name: str = "Implants",
        fail_at: str | None = None,
        failure_message: str = "refresh token leaked-secret should be sanitized",
        zero: bool = False,
        zero_metrics: bool = False,
        shared_ad_in_two_ad_groups: bool = False,
    ) -> None:
        self.account_external_id = account_external_id
        self.account_name = account_name
        self.campaign_name = campaign_name
        self.fail_at = fail_at
        self.failure_message = failure_message
        self.zero = zero
        self.zero_metrics = zero_metrics
        self.shared_ad_in_two_ad_groups = shared_ad_in_two_ad_groups

    def _fail_if_needed(self, name: str) -> None:
        if self.fail_at == name:
            raise RuntimeError(self.failure_message)

    def collect_account(self) -> AdvertisingAccountCreate:
        self._fail_if_needed("account")
        return AdvertisingAccountCreate(
            platform=AdvertisingPlatform.GOOGLE_ADS,
            external_account_id=self.account_external_id,
            name=self.account_name,
            currency_code="USD",
            time_zone="America/New_York",
        )

    def collect_campaigns(self, account_id: int) -> list[CampaignCreate]:
        self._fail_if_needed("campaigns")
        if self.zero:
            return []
        return [
            CampaignCreate(
                account_id=account_id,
                platform=AdvertisingPlatform.GOOGLE_ADS,
                external_campaign_id="camp-1",
                name=self.campaign_name,
                status="ENABLED",
                channel_type="SEARCH",
            )
        ]

    def collect_ad_groups(self, campaign_ids_by_external_id: dict[str, int]) -> list[AdGroupCreate]:
        self._fail_if_needed("ad_groups")
        if not campaign_ids_by_external_id:
            return []
        ad_groups = [
            AdGroupCreate(
                campaign_id=campaign_ids_by_external_id["camp-1"],
                platform=AdvertisingPlatform.GOOGLE_ADS,
                external_ad_group_id="ag-1",
                name="Implants Exact",
                status="ENABLED",
            )
        ]
        if self.shared_ad_in_two_ad_groups:
            ad_groups.append(
                AdGroupCreate(
                    campaign_id=campaign_ids_by_external_id["camp-1"],
                    platform=AdvertisingPlatform.GOOGLE_ADS,
                    external_ad_group_id="ag-2",
                    name="Implants Phrase",
                    status="ENABLED",
                )
            )
        return ad_groups

    def collect_ads(self, ad_group_ids_by_external_id: dict[str, int]) -> list[AdCreate]:
        self._fail_if_needed("ads")
        if not ad_group_ids_by_external_id:
            return []
        if self.shared_ad_in_two_ad_groups:
            return [
                AdCreate(
                    ad_group_id=ad_group_ids_by_external_id["ag-1"],
                    platform=AdvertisingPlatform.GOOGLE_ADS,
                    external_ad_id="shared-ad-creative",
                    name="Implant Ad Exact",
                    status="ENABLED",
                ),
                AdCreate(
                    ad_group_id=ad_group_ids_by_external_id["ag-2"],
                    platform=AdvertisingPlatform.GOOGLE_ADS,
                    external_ad_id="shared-ad-creative",
                    name="Implant Ad Phrase",
                    status="ENABLED",
                ),
            ]
        return [
            AdCreate(
                ad_group_id=ad_group_ids_by_external_id["ag-1"],
                platform=AdvertisingPlatform.GOOGLE_ADS,
                external_ad_id="ad-1",
                name="Implant Ad",
                status="ENABLED",
            )
        ]

    def collect_keywords(self, ad_group_ids_by_external_id: dict[str, int]) -> list[KeywordCreate]:
        self._fail_if_needed("keywords")
        return (
            [
                KeywordCreate(
                    ad_group_id=ad_group_ids_by_external_id["ag-1"],
                    platform=AdvertisingPlatform.GOOGLE_ADS,
                    external_keyword_id="kw-1",
                    text="dental implants",
                    match_type="EXACT",
                    status="ENABLED",
                )
            ]
            if ad_group_ids_by_external_id
            else []
        )

    def collect_search_terms(
        self,
        ad_group_ids_by_external_id: dict[str, int],
        date_range: google_ads.GoogleAdsDateRange,
    ) -> list[SearchTermCreate]:
        self._fail_if_needed("search_terms")
        return (
            [
                SearchTermCreate(
                    ad_group_id=ad_group_ids_by_external_id["ag-1"],
                    platform=AdvertisingPlatform.GOOGLE_ADS,
                    term="best dental implants",
                    match_type="EXACT",
                )
            ]
            if ad_group_ids_by_external_id
            else []
        )

    def collect_metrics(
        self,
        campaign_ids_by_external_id: dict[str, int],
        date_range: google_ads.GoogleAdsDateRange,
        ad_group_ids_by_external_id: dict[str, int] | None = None,
    ) -> NormalizedMetricsBatch:
        self._fail_if_needed("metrics")
        if self.zero_metrics:
            return NormalizedMetricsBatch(metrics=[])
        return NormalizedMetricsBatch(
            metrics=[
                DailyMetricCreate(
                    platform=AdvertisingPlatform.GOOGLE_ADS,
                    metric_date=date(2026, 7, 14),
                    entity_type="campaign",
                    entity_id=campaign_ids_by_external_id["camp-1"],
                    campaign_id=campaign_ids_by_external_id["camp-1"],
                    impressions=100,
                    clicks=10,
                    cost_micros=1230000,
                    conversions=Decimal("2.5"),
                    conversion_value_micros=2500000,
                )
            ]
        )


@pytest.fixture()
def stub_collectors(monkeypatch: pytest.MonkeyPatch) -> GoogleAdsCollectorStub:
    stub = GoogleAdsCollectorStub()
    for name in (
        "collect_account",
        "collect_campaigns",
        "collect_ad_groups",
        "collect_ads",
        "collect_keywords",
        "collect_search_terms",
        "collect_metrics",
    ):
        monkeypatch.setattr(google_ads, name, getattr(stub, name))
    return stub


def test_first_sync_persists_google_ads_data(
    session: Session, stub_collectors: GoogleAdsCollectorStub
) -> None:
    result = sync_without_worker_for_tests(session)

    assert result.status is JobRunStatus.SUCCEEDED
    assert result.records_processed == 7
    account = session.scalar(
        select(AdvertisingAccount).where(AdvertisingAccount.external_account_id == "acct-1")
    )
    assert account is not None
    campaign = session.scalar(select(Campaign).where(Campaign.external_campaign_id == "camp-1"))
    assert campaign is not None
    assert session.scalar(select(AdGroup).where(AdGroup.external_ad_group_id == "ag-1")) is not None
    assert session.scalar(select(Ad).where(Ad.external_ad_id == "ad-1")) is not None
    assert session.scalar(select(Keyword).where(Keyword.external_keyword_id == "kw-1")) is not None
    search_term = session.scalar(
        select(SearchTerm).where(SearchTerm.term == "best dental implants")
    )
    assert search_term is not None
    assert session.scalar(select(DailyMetric).where(DailyMetric.impressions == 100)) is not None


def test_successful_sync_uses_captured_job_run_id_without_post_commit_refresh(
    session: Session,
    stub_collectors: GoogleAdsCollectorStub,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commit_completed = False
    after_commit_statements: list[str] = []
    original_commit = session.commit

    def commit_and_mark_complete() -> None:
        nonlocal commit_completed
        original_commit()
        commit_completed = True

    def fail_sql_after_commit(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        if commit_completed:
            after_commit_statements.append(statement)
            raise RuntimeError("simulated database disconnect after successful commit")

    engine = session.get_bind()
    event.listen(engine, "before_cursor_execute", fail_sql_after_commit)
    monkeypatch.setattr(session, "commit", commit_and_mark_complete)
    try:
        result = sync_without_worker_for_tests(session)
    finally:
        event.remove(engine, "before_cursor_execute", fail_sql_after_commit)

    assert result.status is JobRunStatus.SUCCEEDED
    assert result.job_run_id == 1
    assert result.records_processed == 7
    assert after_commit_statements == []

    job_runs = session.scalars(select(JobRun)).all()
    assert [(job.id, job.status) for job in job_runs] == [
        (result.job_run_id, JobRunStatus.SUCCEEDED)
    ]


def test_repeated_sync_is_idempotent(
    session: Session, stub_collectors: GoogleAdsCollectorStub
) -> None:
    sync_without_worker_for_tests(session)
    sync_without_worker_for_tests(session)

    assert len(session.scalars(select(Campaign)).all()) == 1
    assert len(session.scalars(select(AdGroup)).all()) == 1
    assert len(session.scalars(select(DailyMetric)).all()) == 1
    succeeded_runs = session.scalars(
        select(JobRun).where(JobRun.status == JobRunStatus.SUCCEEDED)
    ).all()
    assert len(succeeded_runs) == 2


def test_same_google_ad_external_id_can_exist_in_multiple_ad_groups(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    stub = GoogleAdsCollectorStub(shared_ad_in_two_ad_groups=True)
    for name in (
        "collect_account",
        "collect_campaigns",
        "collect_ad_groups",
        "collect_ads",
        "collect_keywords",
        "collect_search_terms",
        "collect_metrics",
    ):
        monkeypatch.setattr(google_ads, name, getattr(stub, name))

    result = sync_without_worker_for_tests(session)

    assert result.status is JobRunStatus.SUCCEEDED
    ads = session.scalars(
        select(Ad).where(Ad.external_ad_id == "shared-ad-creative").order_by(Ad.ad_group_id)
    ).all()
    ad_groups = session.scalars(select(AdGroup).order_by(AdGroup.external_ad_group_id)).all()
    assert len(ads) == 2
    assert {ad.ad_group_id for ad in ads} == {ad_group.id for ad_group in ad_groups}
    assert {ad.name for ad in ads} == {"Implant Ad Exact", "Implant Ad Phrase"}


def test_updated_campaign_data_is_upserted(
    session: Session, stub_collectors: GoogleAdsCollectorStub
) -> None:
    sync_without_worker_for_tests(session)
    stub_collectors.campaign_name = "Implants Updated"
    sync_without_worker_for_tests(session)

    campaign = session.scalar(select(Campaign).where(Campaign.external_campaign_id == "camp-1"))
    assert campaign is not None
    assert campaign.name == "Implants Updated"


def test_zero_campaign_account_is_successful(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    stub = GoogleAdsCollectorStub(zero=True)
    for name in (
        "collect_account",
        "collect_campaigns",
        "collect_ad_groups",
        "collect_ads",
        "collect_keywords",
        "collect_search_terms",
        "collect_metrics",
    ):
        monkeypatch.setattr(google_ads, name, getattr(stub, name))

    result = sync_without_worker_for_tests(session)

    assert result.status is JobRunStatus.SUCCEEDED
    assert result.records_processed == 1
    assert len(session.scalars(select(Campaign)).all()) == 0


def test_campaigns_with_zero_metric_rows_are_successful(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    stub = GoogleAdsCollectorStub(zero_metrics=True)
    for name in (
        "collect_account",
        "collect_campaigns",
        "collect_ad_groups",
        "collect_ads",
        "collect_keywords",
        "collect_search_terms",
        "collect_metrics",
    ):
        monkeypatch.setattr(google_ads, name, getattr(stub, name))

    result = sync_without_worker_for_tests(session)

    assert result.status is JobRunStatus.SUCCEEDED
    assert result.records_processed == 6
    assert len(session.scalars(select(Campaign)).all()) == 1
    assert len(session.scalars(select(DailyMetric)).all()) == 0


def test_rollback_after_failure(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    stub = GoogleAdsCollectorStub(
        fail_at="metrics",
        failure_message=SECRET_FAILURE_MESSAGE,
    )
    for name in (
        "collect_account",
        "collect_campaigns",
        "collect_ad_groups",
        "collect_ads",
        "collect_keywords",
        "collect_search_terms",
        "collect_metrics",
    ):
        monkeypatch.setattr(google_ads, name, getattr(stub, name))

    with pytest.raises(GoogleAdsSyncError) as exc_info:
        sync_without_worker_for_tests(session)

    assert str(exc_info.value) == SANITIZED_SYNC_ERROR
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None
    rendered_exception = "".join(
        traceback.format_exception(exc_info.type, exc_info.value, exc_info.tb)
    )
    assert "Traceback" in rendered_exception
    assert SECRET_FAILURE_MESSAGE not in rendered_exception
    for secret_value in SECRET_VALUES:
        assert secret_value not in str(exc_info.value)
        assert secret_value not in rendered_exception
    assert "private-api-response" not in rendered_exception
    assert "db-password" not in rendered_exception

    assert len(session.scalars(select(Campaign)).all()) == 0
    assert len(session.scalars(select(AdGroup)).all()) == 0
    failed = session.scalar(select(JobRun).where(JobRun.status == JobRunStatus.FAILED))
    assert failed is not None
    assert failed.records_processed == 6
    assert failed.account_id is None
    assert failed.error_message is not None
    assert failed.error_message == SANITIZED_SYNC_ERROR
    assert len(failed.error_message) <= 120
    for secret_value in SECRET_VALUES:
        assert secret_value not in failed.error_message
    assert "private-api-response" not in failed.error_message
    assert "db-password" not in failed.error_message
    job_runs = session.scalars(select(JobRun)).all()
    assert [(job.id, job.status) for job in job_runs] == [(failed.id, JobRunStatus.FAILED)]
    assert session.scalars(select(AdvertisingAccount)).all() == []


def test_failed_sync_links_existing_durable_account_without_persisting_rename(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    durable_account = AdvertisingAccount(
        platform=AdvertisingPlatform.GOOGLE_ADS,
        external_account_id="acct-1",
        name="Durable Account Name",
        currency_code="USD",
        time_zone="America/New_York",
    )
    session.add(durable_account)
    session.flush()
    durable_account_id = durable_account.id
    session.commit()
    stub = GoogleAdsCollectorStub(
        account_name="Renamed During Failed Sync",
        fail_at="campaigns",
        failure_message=SECRET_FAILURE_MESSAGE,
    )
    for name in (
        "collect_account",
        "collect_campaigns",
        "collect_ad_groups",
        "collect_ads",
        "collect_keywords",
        "collect_search_terms",
        "collect_metrics",
    ):
        monkeypatch.setattr(google_ads, name, getattr(stub, name))

    with pytest.raises(GoogleAdsSyncError) as exc_info:
        sync_without_worker_for_tests(session)

    assert str(exc_info.value) == SANITIZED_SYNC_ERROR
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None
    failed = session.scalar(select(JobRun).where(JobRun.status == JobRunStatus.FAILED))
    assert failed is not None
    assert failed.account_id == durable_account_id
    account = session.get(AdvertisingAccount, durable_account_id)
    assert account is not None
    assert account.name == "Durable Account Name"


def test_failed_sync_with_new_account_does_not_create_account_for_audit_link(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub = GoogleAdsCollectorStub(
        account_external_id="acct-new",
        account_name="New Account From Failed Sync",
        fail_at="campaigns",
        failure_message=SECRET_FAILURE_MESSAGE,
    )
    for name in (
        "collect_account",
        "collect_campaigns",
        "collect_ad_groups",
        "collect_ads",
        "collect_keywords",
        "collect_search_terms",
        "collect_metrics",
    ):
        monkeypatch.setattr(google_ads, name, getattr(stub, name))

    with pytest.raises(GoogleAdsSyncError) as exc_info:
        sync_without_worker_for_tests(session)

    assert str(exc_info.value) == SANITIZED_SYNC_ERROR
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None
    failed = session.scalar(select(JobRun).where(JobRun.status == JobRunStatus.FAILED))
    assert failed is not None
    assert failed.account_id is None
    assert session.scalars(select(AdvertisingAccount)).all() == []


def test_success_commit_exception_creates_no_failed_job_run(
    session: Session,
    stub_collectors: GoogleAdsCollectorStub,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rollback_calls = 0
    original_rollback = session.rollback

    def counting_rollback() -> None:
        nonlocal rollback_calls
        rollback_calls += 1
        original_rollback()

    def fail_commit() -> None:
        raise RuntimeError(COMMIT_FAILURE_MESSAGE)

    monkeypatch.setattr(session, "rollback", counting_rollback)
    monkeypatch.setattr(session, "commit", fail_commit)

    with pytest.raises(GoogleAdsSyncError) as exc_info:
        sync_without_worker_for_tests(session)

    assert str(exc_info.value) == UNKNOWN_COMMIT_OUTCOME_ERROR
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None
    rendered_exception = "".join(
        traceback.format_exception(exc_info.type, exc_info.value, exc_info.tb)
    )
    assert COMMIT_FAILURE_MESSAGE not in rendered_exception
    for secret_value in SECRET_VALUES:
        assert secret_value not in str(exc_info.value)
        assert secret_value not in rendered_exception
    assert "OperationalError" not in rendered_exception
    assert "COMMIT" not in rendered_exception
    assert "db-password" not in rendered_exception
    assert rollback_calls == 1
    assert session.scalars(select(JobRun)).all() == []


def test_durable_commit_ack_failure_does_not_create_success_and_failed_job_runs(
    session: Session,
    stub_collectors: GoogleAdsCollectorStub,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commit_completed = False
    after_commit_statements: list[str] = []
    original_commit = session.commit

    def commit_then_fail_acknowledgement() -> None:
        nonlocal commit_completed
        original_commit()
        commit_completed = True
        raise RuntimeError(COMMIT_FAILURE_MESSAGE)

    def fail_sql_after_commit(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        if commit_completed:
            after_commit_statements.append(statement)
            raise RuntimeError("post-commit SQL should not be issued")

    engine = session.get_bind()
    event.listen(engine, "before_cursor_execute", fail_sql_after_commit)
    monkeypatch.setattr(session, "commit", commit_then_fail_acknowledgement)
    try:
        with pytest.raises(GoogleAdsSyncError) as exc_info:
            sync_without_worker_for_tests(session)
    finally:
        event.remove(engine, "before_cursor_execute", fail_sql_after_commit)

    assert str(exc_info.value) == UNKNOWN_COMMIT_OUTCOME_ERROR
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None
    rendered_exception = "".join(
        traceback.format_exception(exc_info.type, exc_info.value, exc_info.tb)
    )
    assert COMMIT_FAILURE_MESSAGE not in rendered_exception
    assert "db-password" not in rendered_exception
    assert after_commit_statements == []

    job_runs = session.scalars(select(JobRun)).all()
    assert [(job.status, job.error_message) for job in job_runs] == [(JobRunStatus.SUCCEEDED, None)]


def test_failed_job_run_flush_failure_raises_persistence_error_not_uncertain_commit(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub = GoogleAdsCollectorStub(
        fail_at="metrics",
        failure_message=SECRET_FAILURE_MESSAGE,
    )
    for name in (
        "collect_account",
        "collect_campaigns",
        "collect_ad_groups",
        "collect_ads",
        "collect_keywords",
        "collect_search_terms",
        "collect_metrics",
    ):
        monkeypatch.setattr(google_ads, name, getattr(stub, name))

    original_rollback = session.rollback
    original_flush = session.flush
    rollback_calls = 0
    flush_calls = 0
    commit_calls = 0
    failed_audit_flush_attempted = False

    def counting_rollback() -> None:
        nonlocal rollback_calls
        rollback_calls += 1
        original_rollback()

    def fail_failed_job_run_flush() -> None:
        nonlocal failed_audit_flush_attempted, flush_calls
        flush_calls += 1
        if rollback_calls >= 1 and not failed_audit_flush_attempted:
            failed_audit_flush_attempted = True
            raise RuntimeError(PERSISTENCE_FAILURE_MESSAGE)
        original_flush()

    def count_commit() -> None:
        nonlocal commit_calls
        commit_calls += 1

    monkeypatch.setattr(session, "rollback", counting_rollback)
    monkeypatch.setattr(session, "flush", fail_failed_job_run_flush)
    monkeypatch.setattr(session, "commit", count_commit)

    with pytest.raises(GoogleAdsSyncError) as exc_info:
        sync_without_worker_for_tests(session)

    assert str(exc_info.value) == FAILED_JOB_RUN_PERSISTENCE_ERROR
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None
    rendered_exception = "".join(
        traceback.format_exception(exc_info.type, exc_info.value, exc_info.tb)
    )
    assert SECRET_FAILURE_MESSAGE not in rendered_exception
    assert PERSISTENCE_FAILURE_MESSAGE not in rendered_exception
    for secret_value in SECRET_VALUES:
        assert secret_value not in str(exc_info.value)
        assert secret_value not in rendered_exception
    assert "OperationalError" not in rendered_exception
    assert "INSERT INTO job_runs" not in rendered_exception
    assert "db-password" not in rendered_exception
    assert rollback_calls >= 2
    assert flush_calls >= 2
    assert failed_audit_flush_attempted is True
    assert commit_calls == 0
    assert not session.in_transaction()
    assert session.scalar(select(JobRun)) is None


def test_failed_job_run_commit_exception_has_unknown_outcome(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub = GoogleAdsCollectorStub(
        fail_at="metrics",
        failure_message=SECRET_FAILURE_MESSAGE,
    )
    for name in (
        "collect_account",
        "collect_campaigns",
        "collect_ad_groups",
        "collect_ads",
        "collect_keywords",
        "collect_search_terms",
        "collect_metrics",
    ):
        monkeypatch.setattr(google_ads, name, getattr(stub, name))

    rollback_calls = 0
    original_rollback = session.rollback

    def counting_rollback() -> None:
        nonlocal rollback_calls
        rollback_calls += 1
        original_rollback()

    def fail_commit() -> None:
        raise RuntimeError(PERSISTENCE_FAILURE_MESSAGE)

    monkeypatch.setattr(session, "rollback", counting_rollback)
    monkeypatch.setattr(session, "commit", fail_commit)

    with pytest.raises(GoogleAdsSyncError) as exc_info:
        sync_without_worker_for_tests(session)

    assert str(exc_info.value) == FAILED_JOB_RUN_UNKNOWN_COMMIT_OUTCOME_ERROR
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None
    rendered_exception = "".join(
        traceback.format_exception(exc_info.type, exc_info.value, exc_info.tb)
    )
    assert SECRET_FAILURE_MESSAGE not in rendered_exception
    assert PERSISTENCE_FAILURE_MESSAGE not in rendered_exception
    for secret_value in SECRET_VALUES:
        assert secret_value not in str(exc_info.value)
        assert secret_value not in rendered_exception
    assert "OperationalError" not in rendered_exception
    assert "INSERT INTO job_runs" not in rendered_exception
    assert "db-password" not in rendered_exception
    assert rollback_calls >= 2
    assert session.scalar(select(JobRun)) is None


def test_durable_failed_job_run_commit_ack_failure_does_not_retry_or_duplicate(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub = GoogleAdsCollectorStub(
        fail_at="metrics",
        failure_message=SECRET_FAILURE_MESSAGE,
    )
    for name in (
        "collect_account",
        "collect_campaigns",
        "collect_ad_groups",
        "collect_ads",
        "collect_keywords",
        "collect_search_terms",
        "collect_metrics",
    ):
        monkeypatch.setattr(google_ads, name, getattr(stub, name))

    commit_completed = False
    after_commit_statements: list[str] = []
    original_commit = session.commit

    def commit_then_fail_acknowledgement() -> None:
        nonlocal commit_completed
        original_commit()
        commit_completed = True
        raise RuntimeError(PERSISTENCE_FAILURE_MESSAGE)

    def fail_sql_after_commit(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        if commit_completed:
            after_commit_statements.append(statement)
            raise RuntimeError("post-commit SQL should not be issued")

    engine = session.get_bind()
    event.listen(engine, "before_cursor_execute", fail_sql_after_commit)
    monkeypatch.setattr(session, "commit", commit_then_fail_acknowledgement)
    try:
        with pytest.raises(GoogleAdsSyncError) as exc_info:
            sync_without_worker_for_tests(session)
    finally:
        event.remove(engine, "before_cursor_execute", fail_sql_after_commit)

    assert str(exc_info.value) == FAILED_JOB_RUN_UNKNOWN_COMMIT_OUTCOME_ERROR
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None
    rendered_exception = "".join(
        traceback.format_exception(exc_info.type, exc_info.value, exc_info.tb)
    )
    assert SECRET_FAILURE_MESSAGE not in rendered_exception
    assert PERSISTENCE_FAILURE_MESSAGE not in rendered_exception
    for secret_value in SECRET_VALUES:
        assert secret_value not in rendered_exception
    assert "db-password" not in rendered_exception
    assert after_commit_statements == []

    job_runs = session.scalars(select(JobRun)).all()
    assert [(job.status, job.error_message) for job in job_runs] == [
        (JobRunStatus.FAILED, SANITIZED_SYNC_ERROR)
    ]


def test_concurrent_duplicate_ad_upserts_do_not_create_duplicate_rows(
    tmp_path: Path,
) -> None:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'concurrent-upserts.db'}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    event.listen(engine, "connect", enable_sqlite_foreign_keys)
    Base.metadata.create_all(engine)
    local_session = sessionmaker(bind=engine)
    try:
        setup_session = local_session()
        try:
            setup_session.add(
                Workspace(
                    id=1,
                    slug="denticode",
                    name="Denticode Ad Analyzer",
                    client_name="Denticode",
                    status="active",
                    is_default=True,
                )
            )
            setup_session.commit()
            repository = AdvertisingMetricsRepository(setup_session)
            account = repository.upsert_account(
                AdvertisingAccountCreate(
                    platform=AdvertisingPlatform.GOOGLE_ADS,
                    external_account_id="acct-concurrent",
                    name="Denticode Search",
                    currency_code="USD",
                )
            )
            campaign = repository.upsert_campaign(
                CampaignCreate(
                    account_id=account.id,
                    platform=AdvertisingPlatform.GOOGLE_ADS,
                    external_campaign_id="camp-concurrent",
                    name="Implants",
                )
            )
            ad_group = repository.upsert_ad_group(
                AdGroupCreate(
                    campaign_id=campaign.id,
                    platform=AdvertisingPlatform.GOOGLE_ADS,
                    external_ad_group_id="ag-concurrent",
                    name="Implants Exact",
                )
            )
            ad_group_id = ad_group.id
            setup_session.commit()
        finally:
            setup_session.close()

        worker_count = 8
        barrier = Barrier(worker_count)

        def upsert_ad(worker_index: int) -> int:
            worker_session = local_session()
            try:
                barrier.wait()
                ad = AdvertisingMetricsRepository(worker_session).upsert_ad(
                    AdCreate(
                        ad_group_id=ad_group_id,
                        platform=AdvertisingPlatform.GOOGLE_ADS,
                        external_ad_id="ad-concurrent",
                        name=f"Concurrent Ad {worker_index}",
                        status="ENABLED",
                    )
                )
                worker_session.commit()
                return ad.id
            finally:
                worker_session.close()

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            ad_ids = list(executor.map(upsert_ad, range(worker_count)))

        verification_session = local_session()
        try:
            ads = verification_session.scalars(select(Ad)).all()
            assert len(ads) == 1
            assert set(ad_ids) == {ads[0].id}
        finally:
            verification_session.close()
    finally:
        Base.metadata.drop_all(engine)


def test_successful_and_failed_job_run_records(
    session: Session, stub_collectors: GoogleAdsCollectorStub
) -> None:
    sync_without_worker_for_tests(session)
    stub_collectors.fail_at = "campaigns"
    with pytest.raises(GoogleAdsSyncError):
        sync_without_worker_for_tests(session)

    job_runs = session.scalars(select(JobRun).order_by(JobRun.id)).all()
    assert [job.status for job in job_runs] == [JobRunStatus.SUCCEEDED, JobRunStatus.FAILED]
    assert job_runs[0].started_at is not None and job_runs[0].finished_at is not None
    assert job_runs[1].started_at is not None and job_runs[1].finished_at is not None


def test_google_ads_sync_cli_delegates_to_phase7_one_shot_worker() -> None:
    calls = 0

    def worker_main() -> int:
        nonlocal calls
        calls += 1
        return 2

    assert sync_google_ads_script.main(worker_main) == 2
    assert calls == 1


def test_sync_google_ads_script_runs_directly_from_repository_root(
    tmp_path: Path,
) -> None:
    repository_root = Path(__file__).resolve().parents[1]
    database_path = tmp_path / "direct-script-sync.db"
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(engine)
    engine.dispose()
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env["DATABASE_URL"] = f"sqlite:///{database_path.as_posix()}"
    env["GOOGLE_ADS_CLIENT_SECRET"] = SECRET_VALUES[0]
    env["GOOGLE_ADS_REFRESH_TOKEN"] = SECRET_VALUES[1]
    env["GOOGLE_ADS_DEVELOPER_TOKEN"] = SECRET_VALUES[2]
    env["GOOGLE_ADS_LOGIN_CUSTOMER_ID"] = "1234567890"
    env["GOOGLE_ADS_CUSTOMER_ID"] = "1234567890"
    env["GOOGLE_ADS_CLIENT_ID"] = "client-id.apps.googleusercontent.com"

    completed = subprocess.run(
        [sys.executable, "scripts/sync_google_ads.py"],
        cwd=repository_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    combined_output = completed.stdout + completed.stderr
    assert completed.returncode == 1
    assert completed.stdout == ""
    assert "google_ads_sync_worker_failed" in completed.stderr
    assert "Traceback" not in combined_output
    for secret_value in SECRET_VALUES:
        assert secret_value not in combined_output
    assert "db-password" not in combined_output


def test_final_capability_revalidation_after_metrics_collection_prevents_success(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    stop = Event()
    stub = GoogleAdsCollectorStub()
    for name in (
        "collect_account",
        "collect_campaigns",
        "collect_ad_groups",
        "collect_ads",
        "collect_keywords",
        "collect_search_terms",
    ):
        monkeypatch.setattr(google_ads, name, getattr(stub, name))

    def collect_metrics_then_stop(*args: Any, **kwargs: Any) -> NormalizedMetricsBatch:
        result = stub.collect_metrics(*args, **kwargs)
        stop.set()
        return result

    monkeypatch.setattr(google_ads, "collect_metrics", collect_metrics_then_stop)

    with pytest.raises(GoogleAdsSyncError):
        sync_without_worker_for_tests(session, stop_requested=stop.is_set)

    assert session.scalars(select(DailyMetric)).all() == []
    assert (
        session.scalars(select(JobRun).where(JobRun.status == JobRunStatus.SUCCEEDED)).all() == []
    )


def test_final_capability_revalidation_when_metrics_skipped_prevents_success(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    stop = Event()
    stub = GoogleAdsCollectorStub(zero=True)
    for name in (
        "collect_account",
        "collect_campaigns",
        "collect_ad_groups",
        "collect_ads",
        "collect_keywords",
        "collect_metrics",
    ):
        monkeypatch.setattr(google_ads, name, getattr(stub, name))

    def collect_search_terms_then_stop(*args: Any, **kwargs: Any) -> list[Any]:
        result = stub.collect_search_terms(*args, **kwargs)
        stop.set()
        return result

    monkeypatch.setattr(google_ads, "collect_search_terms", collect_search_terms_then_stop)

    with pytest.raises(GoogleAdsSyncError):
        sync_without_worker_for_tests(session, stop_requested=stop.is_set)

    assert (
        session.scalars(select(JobRun).where(JobRun.status == JobRunStatus.SUCCEEDED)).all() == []
    )


def test_final_capability_revalidation_after_metrics_detects_lock_loss(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    class MutableLock(TestPhase7Lock):
        acquired = True

        def owns_current_session(self, _session: Session) -> bool:
            return self.acquired

    lock = MutableLock()
    stub = GoogleAdsCollectorStub()
    for name in (
        "collect_account",
        "collect_campaigns",
        "collect_ad_groups",
        "collect_ads",
        "collect_keywords",
        "collect_search_terms",
    ):
        monkeypatch.setattr(google_ads, name, getattr(stub, name))

    def collect_metrics_then_lose_lock(*args: Any, **kwargs: Any) -> NormalizedMetricsBatch:
        result = stub.collect_metrics(*args, **kwargs)
        lock.acquired = False
        return result

    monkeypatch.setattr(google_ads, "collect_metrics", collect_metrics_then_lose_lock)

    with pytest.raises(GoogleAdsSyncError):
        sync_without_worker_for_tests(session, lock=lock)

    assert session.scalars(select(DailyMetric)).all() == []
    assert (
        session.scalars(select(JobRun).where(JobRun.status == JobRunStatus.SUCCEEDED)).all() == []
    )
