"""Authentic retained source records followed by current candidate read contracts."""

import json
import os
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, Literal

import httpx
import pytest
from app import advertising_capabilities
from app.commerce.models import CommerceMeasurementPublication, CommerceStore
from app.customers.access import CustomerPrincipal
from app.customers.models import CustomerSession, CustomerUser
from app.database.session import Base
from app.executors.google_optimization import GoogleOptimizationTransport
from app.executors.meta_optimization import MetaOptimizationTransport
from app.executors.tiktok_optimization import TikTokOptimizationTransport
from app.goals import service as goals
from app.optimization_candidates import service as candidates
from app.optimization_candidates.contracts import (
    CandidateEvidence,
    CandidateObservation,
    CandidatePolicy,
    CandidateScope,
    CandidateWork,
    SourceFence,
)
from app.optimization_candidates.models import CandidateJob, CandidateResult
from app.publication import execution_mandates as mandates
from app.publication.contracts import fingerprint
from app.publication.execution_contracts import ProviderMandateBinding
from app.publication.execution_models import (
    ProviderExecutionAttempt,
    ProviderExecutionReceipt,
    ProviderExecutionResponse,
    ProviderExecutionReview,
    ProviderExposureReservation,
)
from app.publication.optimization_contracts import (
    MoneyContext,
    OptimizationContext,
    OptimizationTarget,
)
from app.workspaces.models import Workspace
from pydantic import SecretStr
from scripts.inlet_producer_source_lifetime import SourceLifetime
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import Engine, create_engine, event, func, inspect, make_url, select, text
from sqlalchemy.orm import Session

from tests.retired_snapshot import PIN, extract, run_bounded
from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import FakeProvider
from tests.test_google_optimization_http import Server as GoogleServer
from tests.test_social_optimization_http import Server

Provider = Literal["google_ads", "meta_ads", "tiktok_ads"]


@dataclass(frozen=True)
class CandidateReadIds:
    workspace_id: int
    actor_id: str
    session_digest: str
    mandate_id: str
    mandate_revision: int
    consent_id: str
    policy_digest: str
    ledger_id: str
    account_id: int
    store_id: str
    publication_id: str
    provider: Provider
    provider_posts: int


def no_effects(engine: Engine) -> None:
    assert advertising_capabilities.advertising_writes_enabled() is False
    with Session(engine) as db:
        for model in (
            ProviderExecutionAttempt,
            ProviderExecutionReview,
            ProviderExecutionResponse,
            ProviderExecutionReceipt,
            ProviderExposureReservation,
        ):
            assert db.scalar(select(func.count()).select_from(model)) == 0


@contextmanager
def retained_candidate_read_fixture(
    customer_engine: Engine,
    artifacts: Path,
    provider: Provider,
) -> Iterator[tuple[Engine, CandidateReadIds]]:
    assert provider in {"google_ads", "meta_ads", "tiktok_ads"}
    artifacts.mkdir(parents=True)
    engine = customer_engine
    if engine.dialect.name == "sqlite":
        engine = create_engine(f"sqlite:///{artifacts / 'current.sqlite'}")
        event.listen(engine, "connect", lambda db, _: db.execute("PRAGMA foreign_keys=ON"))
        Base.metadata.create_all(engine)
        target = str(engine.url)
    else:
        target_url = make_url(validate_disposable_url())
        assert target_url.host in {"localhost", "127.0.0.1", "::1"} and not target_url.query
        assert engine.url == target_url
        with engine.connect() as connection:
            target = str(connection.scalar(text("SELECT current_schema()")))
        assert re.fullmatch(r"inlet_test_[a-f0-9]{32}", target)
    try:
        no_effects(engine)
        tables = set(inspect(engine).get_table_names())
        root = Path(__file__).resolve().parents[1]
        with SourceLifetime.open("candidate_read", artifacts) as lifetime:
            snapshot = lifetime.source
            extract(root, snapshot)
            lifetime.extracted()
            output, log = artifacts / "ids.json", artifacts / "producer.log"
            lifetime.child_started()
            code = run_bounded(
                [
                    sys.executable,
                    str(root / "tests/fixtures/retired_execution/candidate_read_seed_driver.py"),
                    target,
                    str(output),
                    provider,
                ],
                snapshot,
                dict(os.environ, INLET_RETIRED_EXECUTION_CHILD=PIN, PYTHONPATH=str(snapshot)),
                log,
                180,
            )
            lifetime.after_reaped(code)
        assert code == 0, log.read_text()[-6000:]
        assert output.stat().st_size <= 4096
        raw = json.loads(output.read_text())
        assert type(raw) is dict and set(raw) == set(CandidateReadIds.__dataclass_fields__)
        for field in ("workspace_id", "mandate_revision", "account_id"):
            assert type(raw[field]) is int and raw[field] > 0
        assert type(raw["provider_posts"]) is int and raw["provider_posts"] == 0
        assert raw["provider"] == provider
        for field in (
            "actor_id",
            "mandate_id",
            "consent_id",
            "ledger_id",
            "store_id",
            "publication_id",
        ):
            assert type(raw[field]) is str and re.fullmatch(r"[a-f0-9]{32}", raw[field])
        for field in ("session_digest", "policy_digest"):
            assert type(raw[field]) is str and re.fullmatch(r"[a-f0-9]{64}", raw[field])
        ids = CandidateReadIds(**raw)
        assert set(inspect(engine).get_table_names()) == tables
        with Session(engine) as db:
            for model in (CandidateJob, CandidateResult):
                assert db.scalar(select(func.count()).select_from(model)) == 0
            load_candidate_read_fixture(db, ids)
        no_effects(engine)
        try:
            yield engine, ids
        finally:
            no_effects(engine)
    finally:
        if engine is not customer_engine:
            engine.dispose()


def load_candidate_read_fixture(db: Session, ids: CandidateReadIds) -> tuple[Any, ...]:
    user, session = db.get(CustomerUser, ids.actor_id), db.get(CustomerSession, ids.session_digest)
    assert user and session and session.user_id == user.id
    principal = CustomerPrincipal(user, session)
    binding = ProviderMandateBinding(
        mandate_id=ids.mandate_id,
        revision=ids.mandate_revision,
        consent_id=ids.consent_id,
        policy_digest=ids.policy_digest,
        ledger_id=ids.ledger_id,
        environment="contract_test",
    )
    _, mandate = mandates.checked(db, ids.workspace_id, binding, ids.actor_id, lambda: NOW)
    assert len(mandate.accounts) == 1
    account = mandate.accounts[0]
    assert account.workspace_id == ids.workspace_id and account.account.account_id == ids.account_id
    assert account.account.platform == ids.provider
    server = GoogleServer() if ids.provider == "google_ads" else Server(ids.provider)
    adapter = {
        "google_ads": GoogleOptimizationTransport,
        "meta_ads": MetaOptimizationTransport,
        "tiktok_ads": TikTokOptimizationTransport,
    }[ids.provider](transport=httpx.MockTransport(server))
    target = OptimizationTarget(
        kind="campaign"
        if ids.provider == "google_ads"
        else ("adset" if ids.provider == "meta_ads" else "adgroup"),
        external_id="5" if ids.provider == "google_ads" else "6",
        campaign_id="5",
    )
    money = MoneyContext(
        currency="USD",
        currency_exponent=2,
        account_timezone="UTC",
        period_start=mandate.starts_at,
        period_end=mandate.ends_at,
    )
    state = adapter.read_current(
        account,
        target,
        money,
        "e" * 32,
        1,
        OptimizationContext(
            scope=account,
            access_token=SecretStr("offline-token"),
            expires_at=NOW + timedelta(hours=1),
        ),
        NOW,
    )
    store = db.get(CommerceStore, ids.store_id)
    publication = db.get(CommerceMeasurementPublication, ids.publication_id)
    workspace = db.get(Workspace, ids.workspace_id)
    assert store and publication and workspace
    assert store.workspace_id == publication.workspace_id == ids.workspace_id
    assert publication.store_id == ids.store_id
    goal = goals.owned(db, ids.workspace_id, mandate.goal_id)
    scope = CandidateScope(
        account=account,
        mandate=binding,
        goal_id=goal.id,
        goal_revision=goal.revision,
        goal_digest=fingerprint(
            "inlet.optimization-goal.v1", {"definition": goals.current(db, goal).definition}
        ),
        target=target,
        budget_owner_key=state.budget_owner.key(account),
        target_set_digest=state.budget_owner.target_set_digest(),
        source=SourceFence(
            workspace_privacy_revision=workspace.export_privacy_revision,
            store_id=store.id,
            publication_id=publication.id,
            generation=publication.generation,
            privacy_epoch=publication.privacy_epoch,
            publication_revision=publication.publication_revision,
            source_revision=publication.source_revision,
            manifest_digest=publication.manifest_digest,
        ),
    )
    policy = CandidatePolicy(
        workspace_id=ids.workspace_id,
        environment="contract_test",
        policy_id="a" * 32,
        revision=1,
        budget_step_micros=1_000_000,
        minimum_observations=10,
    )
    work = CandidateWork(scope=scope, policy=policy)
    observation = CandidateObservation(
        scope=scope,
        state=state,
        evidence=CandidateEvidence(
            scope_digest=scope.digest(),
            source_schema="test.controlled.v1",
            source_digest="b" * 64,
            source_reference=publication.id,
            qualification="contract_scenario",
            direction="increase",
            observation_count=20,
            observed_at=NOW,
            expires_at=NOW + timedelta(minutes=2),
        ),
    )
    identity = FakeProvider()
    identity.issuer = user.issuer
    runtime = candidates.CandidateRuntime(
        environment="contract_test",
        identity=identity,
        reader=lambda db, scope, now: observation,
        policy_reader=lambda db, wid, pid, rev: policy,
        clock=lambda: NOW,
    )
    db.commit()
    return principal, work, observation, mandate, runtime, server


@pytest.fixture
def retained_candidate_case(
    customer_engine: Engine,
    tmp_path: Path,
    request: pytest.FixtureRequest,
) -> Iterator[tuple[Engine, CandidateReadIds]]:
    provider: Provider = "google_ads"
    if (
        request.node.originalname
        == "test_owner_selection_never_substitutes_child_or_conflicting_owner"
    ):
        provider = "meta_ads"
    elif hasattr(request.node, "callspec"):
        provider = request.node.callspec.params.get("provider", "google_ads")
    with retained_candidate_read_fixture(
        customer_engine, tmp_path / "candidate-source", provider
    ) as value:
        yield value
