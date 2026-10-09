"""Pinned genuine legacy bindings, then current offline review in fresh sessions."""

import json
import os
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pytest
from app import advertising_capabilities
from app.ads.models import AdvertisingAccount
from app.campaign_review.models import CampaignDraft, CampaignRevision, MediaObject
from app.database.session import Base
from app.google_connections.models import GoogleCustomerConnection
from app.mandates import service as mandates
from app.mandates.models import Mandate, MandateAction
from app.mandates.schemas import AccountScope
from app.meta.models import MetaConnection
from app.publication.execution_models import (
    ProviderExecutionAttempt,
    ProviderExecutionConsent,
    ProviderExecutionMandate,
    ProviderExecutionReceipt,
    ProviderExecutionResponse,
    ProviderExecutionReview,
    ProviderExposureReservation,
)
from app.sources.models import SourceConnection
from app.workspaces.models import WorkspaceIntegration
from scripts.inlet_producer_source_lifetime import SourceLifetime
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import Engine, create_engine, event, func, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from tests.financial_origin_retained_fixture import schema_snapshot
from tests.retired_snapshot import PIN, extract, run_bounded
from tests.test_commerce_measurement import NOW

CampaignReviewProvider = Literal["google_ads", "meta_ads", "tiktok_ads"]


@dataclass(frozen=True)
class RetainedCampaignReviewIds:
    workspace_id: int
    mandate_id: str
    mandate_revision: int
    integration_id: int
    account_id: int
    source_id: str
    provider: CampaignReviewProvider
    provider_posts: int


def no_effects(engine: Engine) -> None:
    assert advertising_capabilities.advertising_writes_enabled() is False
    with Session(engine) as db:
        for model in (
            MandateAction,
            ProviderExecutionAttempt,
            ProviderExecutionConsent,
            ProviderExecutionMandate,
            ProviderExposureReservation,
            ProviderExecutionReceipt,
            ProviderExecutionResponse,
            ProviderExecutionReview,
        ):
            assert db.scalar(select(func.count()).select_from(model)) == 0


def current_binding(db: Session, ids: RetainedCampaignReviewIds) -> tuple[Mandate, AccountScope]:
    mandate = db.get(Mandate, ids.mandate_id)
    assert (
        mandate
        and mandate.workspace_id == ids.workspace_id
        and mandate.revision == ids.mandate_revision
    )
    policy = mandates.policy(db, mandate)
    scope = policy.accounts[0]
    assert (scope.connection_id, scope.account_id, scope.platform) == (
        ids.integration_id,
        ids.account_id,
        ids.provider,
    )
    assert (policy.total_cap_micros, policy.per_action_cap_micros) == (100, 80)
    assert mandate.state == "approved" and not mandate.paused
    if ids.provider == "google_ads":
        source = db.get(GoogleCustomerConnection, ids.source_id)
        assert (
            source
            and source.account_id == ids.account_id
            and source.workspace_id == ids.workspace_id
        )
    elif ids.provider == "tiktok_ads":
        source_connection = db.get(SourceConnection, ids.source_id)
        account = db.get(AdvertisingAccount, ids.account_id)
        integration = db.get(WorkspaceIntegration, ids.integration_id)
        assert source_connection and account and integration
        assert source_connection.workspace_id == account.workspace_id == ids.workspace_id
        assert integration.workspace_id == ids.workspace_id
        assert source_connection.integration_id == account.connection_id == integration.id
        assert source_connection.account_id == account.id
        assert source_connection.provider == integration.provider == "tiktok_ads"
        assert str(account.platform) == "tiktok_ads"
        assert source_connection.external_id == account.external_account_id == "123"
        assert source_connection.generation == 1 and source_connection.status == "connected"
        assert source_connection.window_start == source_connection.window_end == NOW.date()
        assert integration.status == "active" and account.currency_code == "USD"
    else:
        meta = db.get(MetaConnection, int(ids.source_id))
        assert meta and meta.account_id == ids.account_id and meta.workspace_id == ids.workspace_id
    return mandate, scope


def tiktok_protected_graph(engine: Engine) -> dict[str, list[dict[str, object]]]:
    names = {
        "spending_mandates",
        "spending_mandate_revisions",
        "mandate_audits",
        "mandate_actions",
        "workspace_integrations",
        "advertising_accounts",
        "customer_source_connections",
    }
    with engine.connect() as connection:
        return {
            table.name: [
                dict(row)
                for row in connection.execute(
                    select(table).order_by(*table.primary_key.columns)
                ).mappings()
            ]
            for table in Base.metadata.sorted_tables
            if table.name.startswith("provider_") or table.name in names
        }


def owned_sqlite_target(target: str, expected: Path) -> str:
    url = make_url(target)
    assert url.drivername == "sqlite" and not url.query
    assert url.username is None and url.password is None and url.host is None and url.port is None
    assert url.database is not None
    path = Path(url.database)
    assert path.is_absolute() and path == expected.absolute()
    assert path.is_file() and not path.is_symlink()
    assert all(not parent.is_symlink() for parent in path.parents)
    assert path.resolve() == path
    return str(url)


@contextmanager
def retained_campaign_review_fixture(
    customer_engine: Engine, artifacts: Path, provider: CampaignReviewProvider
) -> Iterator[tuple[Engine, RetainedCampaignReviewIds]]:
    assert provider in {"google_ads", "meta_ads", "tiktok_ads"}
    if provider == "tiktok_ads":
        assert artifacts.is_absolute() and not artifacts.is_symlink()
        assert all(not parent.is_symlink() for parent in artifacts.parents)
    artifacts.mkdir(parents=True)
    engine = customer_engine
    if engine.dialect.name == "sqlite":
        target = f"sqlite:///{artifacts / 'current.sqlite'}"
        if provider == "tiktok_ads":
            owned = artifacts / "current.sqlite"
            owned.touch(exist_ok=False)
            target = owned_sqlite_target(target, owned)
        engine = create_engine(target)
        event.listen(engine, "connect", lambda db, _: db.execute("PRAGMA foreign_keys=ON"))
        Base.metadata.create_all(engine)
        target = str(engine.url)
    else:
        assert os.environ.get("AD_ANALYZER_CI_DISPOSABLE_POSTGRES") == "true"
        if provider == "tiktok_ads":
            safe = make_url(validate_disposable_url())
            assert safe.host in {"localhost", "127.0.0.1", "::1"} and not safe.query
            assert engine.url == safe
        with engine.connect() as connection:
            target = str(connection.scalar(text("select current_schema()")))
        assert re.fullmatch(r"inlet_test_[a-f0-9]{32}", target)
    try:
        no_effects(engine)
        tables = set(inspect(engine).get_table_names())
        schema_before = schema_snapshot(engine) if provider == "tiktok_ads" else None
        if provider == "tiktok_ads":
            with engine.connect() as connection:
                for table in sorted(tables - {"alembic_version"}):
                    quoted = engine.dialect.identifier_preparer.quote(table)
                    assert (
                        connection.execute(text(f"SELECT 1 FROM {quoted} LIMIT 1")).first() is None
                    )
        root = Path(__file__).resolve().parents[1]
        with SourceLifetime.open("campaign_review", artifacts) as lifetime:
            snapshot = lifetime.source
            extract(root, snapshot)
            lifetime.extracted()
            output, log = artifacts / "ids.json", artifacts / "producer.log"
            env = dict(os.environ, INLET_RETIRED_EXECUTION_CHILD=PIN, PYTHONPATH=str(snapshot))
            lifetime.child_started()
            code = run_bounded(
                [
                    sys.executable,
                    str(root / "tests/fixtures/retired_execution/campaign_review_seed_driver.py"),
                    target,
                    str(output),
                    provider,
                ],
                snapshot,
                env,
                log,
                180,
            )
            lifetime.after_reaped(code)
        assert code == 0, log.read_text()[-6000:]
        if provider == "tiktok_ads":
            assert 0 < output.stat().st_size <= 4096
        raw = json.loads(output.read_text())
        assert type(raw) is dict
        assert set(raw) == set(RetainedCampaignReviewIds.__dataclass_fields__)
        for field in ("workspace_id", "mandate_revision", "integration_id", "account_id"):
            assert type(raw[field]) is int and raw[field] > 0
        assert (
            raw["provider"] == provider
            and type(raw["provider_posts"]) is int
            and raw["provider_posts"] == 0
        )
        assert isinstance(raw["mandate_id"], str) and re.fullmatch(
            r"[a-f0-9]{32}", raw["mandate_id"]
        )
        assert (
            isinstance(raw["source_id"], str)
            and len(raw["source_id"]) <= 128
            and re.fullmatch(
                r"[a-f0-9]{32}" if provider != "meta_ads" else r"[1-9][0-9]*", raw["source_id"]
            )
        )
        ids = RetainedCampaignReviewIds(**raw)
        assert set(inspect(engine).get_table_names()) == tables
        with Session(engine) as db:
            current_binding(db, ids)
            for model in (CampaignDraft, CampaignRevision, MediaObject):
                assert db.scalar(select(func.count()).select_from(model)) == 0
        no_effects(engine)
        protected = tiktok_protected_graph(engine) if provider == "tiktok_ads" else None
        if protected is not None:
            assert schema_snapshot(engine) == schema_before
            assert all(
                not rows
                for name, rows in protected.items()
                if name.startswith("provider_") or name == "mandate_actions"
            )
        try:
            yield engine, ids
        finally:
            no_effects(engine)
            if protected is not None:
                assert tiktok_protected_graph(engine) == protected
                assert schema_snapshot(engine) == schema_before
    finally:
        if engine is not customer_engine:
            engine.dispose()


@pytest.fixture
def retained_campaign_binding(
    customer_engine: Engine, tmp_path: Path, request: pytest.FixtureRequest
) -> Iterator[tuple[Engine, RetainedCampaignReviewIds]]:
    provider: CampaignReviewProvider = (
        "meta_ads"
        if request.node.originalname == "test_image_review_binds_exact_media_and_meta_generation"
        else "google_ads"
    )
    with retained_campaign_review_fixture(
        customer_engine, tmp_path / "retained-binding", provider
    ) as result:
        yield result
