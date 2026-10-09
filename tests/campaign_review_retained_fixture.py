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
from scripts.inlet_producer_source_lifetime import SourceLifetime
from sqlalchemy import Engine, create_engine, event, func, inspect, select, text
from sqlalchemy.orm import Session

from tests.retired_snapshot import PIN, extract, run_bounded

CampaignReviewProvider = Literal["google_ads", "meta_ads"]


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
    else:
        meta = db.get(MetaConnection, int(ids.source_id))
        assert meta and meta.account_id == ids.account_id and meta.workspace_id == ids.workspace_id
    return mandate, scope


@contextmanager
def retained_campaign_review_fixture(
    customer_engine: Engine, artifacts: Path, provider: CampaignReviewProvider
) -> Iterator[tuple[Engine, RetainedCampaignReviewIds]]:
    assert provider in {"google_ads", "meta_ads"}
    artifacts.mkdir(parents=True)
    engine = customer_engine
    if engine.dialect.name == "sqlite":
        engine = create_engine(f"sqlite:///{artifacts / 'current.sqlite'}")
        event.listen(engine, "connect", lambda db, _: db.execute("PRAGMA foreign_keys=ON"))
        Base.metadata.create_all(engine)
        target = str(engine.url)
    else:
        assert os.environ.get("AD_ANALYZER_CI_DISPOSABLE_POSTGRES") == "true"
        with engine.connect() as connection:
            target = str(connection.scalar(text("select current_schema()")))
        assert re.fullmatch(r"inlet_test_[a-f0-9]{32}", target)
    try:
        no_effects(engine)
        tables = set(inspect(engine).get_table_names())
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
        raw = json.loads(output.read_text())
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
                r"[a-f0-9]{32}" if provider == "google_ads" else r"[1-9][0-9]*", raw["source_id"]
            )
        )
        ids = RetainedCampaignReviewIds(**raw)
        assert set(inspect(engine).get_table_names()) == tables
        with Session(engine) as db:
            current_binding(db, ids)
            for model in (CampaignDraft, CampaignRevision, MediaObject):
                assert db.scalar(select(func.count()).select_from(model)) == 0
        no_effects(engine)
        try:
            yield engine, ids
        finally:
            no_effects(engine)
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
