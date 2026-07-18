"""PostgreSQL advisory-lock transaction visibility checks for Phase 7.

These tests require a PostgreSQL test database URL in DENTICODE_TEST_POSTGRES_URL.
They intentionally use separate connections for lock competition and visibility.
"""

import os
from collections.abc import Generator

import pytest
from app.ads.enums import AdvertisingPlatform, JobRunStatus
from app.ads.models import AdvertisingAccount, JobRun
from app.ads.repository import AdvertisingMetricsRepository
from app.database.session import Base
from app.jobs.reliability import PostgreSQLAdvisoryLock
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture()
def postgres_engine() -> Generator[Engine, None, None]:
    url = os.environ.get("DENTICODE_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("DENTICODE_TEST_POSTGRES_URL is required for PostgreSQL lock tests")
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            if connection.dialect.name != "postgresql":
                pytest.skip("DENTICODE_TEST_POSTGRES_URL must point to PostgreSQL")
        Base.metadata.create_all(engine)
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_postgres_lock_acquisition_transaction_ends_and_lock_survives(
    postgres_engine: Engine,
) -> None:
    key = 42424217
    with postgres_engine.connect() as pinned, postgres_engine.connect() as competitor:
        lock = PostgreSQLAdvisoryLock(pinned, key)

        assert lock.try_acquire() is True
        assert pinned.in_transaction() is False
        assert lock.backend_pid == pinned.scalar(text("SELECT pg_backend_pid()"))
        pinned.commit()
        assert pinned.in_transaction() is False
        assert competitor.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": key}) is False
        competitor.rollback()

        lock.release()
        assert pinned.in_transaction() is False
        assert competitor.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": key}) is True
        assert competitor.scalar(text("SELECT pg_advisory_unlock(:key)"), {"key": key}) is True
        competitor.commit()


def test_postgres_ownership_checks_do_not_commit_session_writes(
    postgres_engine: Engine,
) -> None:
    key = 42424219
    with postgres_engine.connect() as pinned:
        lock = PostgreSQLAdvisoryLock(pinned, key)
        assert lock.try_acquire() is True
        session = sessionmaker(bind=pinned, autoflush=False, autocommit=False)()
        try:
            account = AdvertisingAccount(
                platform=AdvertisingPlatform.GOOGLE_ADS,
                external_account_id="uncommitted-account",
                name="Uncommitted account",
                currency_code="USD",
                time_zone="UTC",
            )
            session.add(account)
            session.flush()
            assert pinned.in_transaction() is True
            with pytest.raises(RuntimeError, match="no active transaction"):
                lock.owns_current_connection()
            assert pinned.in_transaction() is True

            assert lock.owns_current_session(session) is True
            assert pinned.in_transaction() is True
            with Session(postgres_engine) as visible_session:
                visible = visible_session.scalars(
                    select(AdvertisingAccount).where(
                        AdvertisingAccount.external_account_id == "uncommitted-account"
                    )
                ).first()
                assert visible is None

            assert lock.owns_current_session(session) is True
            assert pinned.in_transaction() is True
            session.rollback()
            with Session(postgres_engine) as visible_session:
                visible = visible_session.scalars(
                    select(AdvertisingAccount).where(
                        AdvertisingAccount.external_account_id == "uncommitted-account"
                    )
                ).first()
                assert visible is None
        finally:
            session.close()
            lock.release()


def test_postgres_session_commits_are_visible_while_lock_is_held(
    postgres_engine: Engine,
) -> None:
    key = 42424218
    with postgres_engine.connect() as pinned:
        lock = PostgreSQLAdvisoryLock(pinned, key)
        assert lock.try_acquire() is True
        assert pinned.in_transaction() is False
        session = sessionmaker(bind=pinned, autoflush=False, autocommit=False)()
        try:
            job_run = AdvertisingMetricsRepository(session).create_job_run(
                platform=AdvertisingPlatform.GOOGLE_ADS,
                job_name="google_ads_read_only_sync",
                status=JobRunStatus.RUNNING,
            )
            session.commit()
            assert pinned.in_transaction() is False
            with Session(postgres_engine) as visible_session:
                visible = visible_session.get(JobRun, job_run.id)
                assert visible is not None
                assert visible.status is JobRunStatus.RUNNING

            AdvertisingMetricsRepository(session).finish_job_run(
                job_run,
                status=JobRunStatus.SUCCEEDED,
                records_processed=0,
            )
            session.commit()
            with Session(postgres_engine) as visible_session:
                status = visible_session.scalars(
                    select(JobRun.status).where(JobRun.id == job_run.id)
                ).one()
                assert status is JobRunStatus.SUCCEEDED
        finally:
            session.close()
            lock.release()
