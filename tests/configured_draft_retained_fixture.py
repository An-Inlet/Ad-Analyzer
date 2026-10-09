"""Owned current read fixtures from exact historical approved source records."""

import json
import os
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app import advertising_capabilities
from app.campaign_review import service
from app.campaign_review.models import CampaignRevision
from app.campaign_review.storage import LocalMediaStore
from app.customers.models import CustomerMembership, CustomerUser
from app.database.session import Base
from app.publication.customer_intents import account
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import Engine, create_engine, event, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from tests.retired_snapshot import PIN, extract, run_bounded
from tests.test_commerce_measurement import NOW


@dataclass(frozen=True)
class ConfiguredDraftIds:
    provider: Literal["google_ads", "meta_ads"]
    workspace_id: int
    actor_id: str
    account_id: int
    native_connection_id: str | int
    draft_id: str
    draft_revision: int
    draft_digest: str
    simulation_mandate_id: str
    simulation_mandate_revision: int
    provider_posts: int


def no_effects(engine: Engine) -> None:
    assert not advertising_capabilities.advertising_writes_enabled()
    with engine.connect() as connection:
        for table in (
            "provider_execution_attempts",
            "provider_execution_receipts",
            "provider_execution_reviews",
            "provider_execution_runs",
            "provider_exposure_reservations",
            "provider_execution_responses",
            "provider_execution_consents",
            "provider_execution_mandates",
        ):
            assert connection.scalar(text(f"SELECT count(*) FROM {table}")) == 0


@contextmanager
def retained_configured_draft_fixture(
    customer_engine: Engine,
    artifacts: Path,
    provider: Literal["google_ads", "meta_ads"],
) -> Iterator[tuple[Engine, ConfiguredDraftIds, Path]]:
    assert provider in {"google_ads", "meta_ads"}
    artifacts.mkdir(parents=True)
    engine = customer_engine
    if engine.dialect.name == "sqlite":
        engine = create_engine(f"sqlite:///{artifacts / 'current.sqlite'}")
        event.listen(engine, "connect", lambda db, _: db.execute("PRAGMA foreign_keys=ON"))
        Base.metadata.create_all(engine)
        target = str(engine.url)
    else:
        assert os.environ["AD_ANALYZER_CI_DISPOSABLE_POSTGRES"] == "true"
        url = make_url(validate_disposable_url())
        assert url.drivername == "postgresql+psycopg"
        assert url.host in {"127.0.0.1", "localhost", "::1"} and not url.query
        assert url.database and re.fullmatch(r"inlet_[a-z0-9_]+_ci", url.database)
        assert engine.url == url
        with engine.connect() as connection:
            target = str(connection.scalar(text("SELECT current_schema()")))
        assert re.fullmatch(r"inlet_test_[a-f0-9]{32}", target)
    try:
        no_effects(engine)
        tables = set(inspect(engine).get_table_names())
        with engine.connect() as connection:
            for table in tables - {"alembic_version"}:
                quoted = engine.dialect.identifier_preparer.quote(table)
                assert connection.scalar(text(f"SELECT count(*) FROM {quoted}")) == 0
        root = Path(__file__).resolve().parents[1]
        snapshot = artifacts / "source"
        extract(root, snapshot)
        output, log = artifacts / "ids.json", artifacts / "producer.log"
        env = dict(os.environ, INLET_RETIRED_EXECUTION_CHILD=PIN, PYTHONPATH=str(snapshot))
        driver = root / "tests/fixtures/retired_execution/configured_draft_seed_driver.py"
        code = run_bounded(
            [sys.executable, str(driver), target, str(output), provider], snapshot, env, log, 180
        )
        assert code == 0, log.read_text()[-6000:]
        assert output.stat().st_size <= 4096
        raw = json.loads(output.read_text())
        assert type(raw) is dict
        assert set(raw) == set(ConfiguredDraftIds.__dataclass_fields__)
        assert raw["provider"] == provider
        for name in ("workspace_id", "account_id", "draft_revision", "simulation_mandate_revision"):
            assert type(raw[name]) is int and raw[name] > 0
        for name in ("actor_id", "draft_id", "simulation_mandate_id"):
            assert isinstance(raw[name], str) and re.fullmatch("[a-f0-9]{32}", raw[name])
        assert isinstance(raw["draft_digest"], str)
        assert re.fullmatch("[a-f0-9]{64}", raw["draft_digest"])
        native = raw["native_connection_id"]
        assert (
            type(native) is str and re.fullmatch("[a-f0-9]{32}", native)
            if provider == "google_ads"
            else type(native) is int and native > 0
        )
        assert type(raw["provider_posts"]) is int and raw["provider_posts"] == 0
        ids = ConfiguredDraftIds(**raw)
        media = artifacts / "media"
        with Session(engine) as db:
            user = db.get(CustomerUser, ids.actor_id)
            membership = db.get(CustomerMembership, (ids.actor_id, ids.workspace_id))
            assert user and user.status == "active"
            assert membership and membership.role == "owner" and membership.status == "active"
            row, artifact = service.preview(
                db, ids.workspace_id, ids.draft_id, LocalMediaStore(media), NOW
            )
            assert row.approved_by == ids.actor_id and artifact.revision == ids.draft_revision
            revision = db.get(CampaignRevision, (ids.draft_id, ids.draft_revision))
            assert revision and revision.digest == ids.draft_digest
            assert artifact.definition.account.account_id == ids.account_id
            assert artifact.definition.account.platform == ids.provider
            assert artifact.definition.mandate_id == ids.simulation_mandate_id
            assert artifact.definition.mandate_revision == ids.simulation_mandate_revision
            scope = account(db, ids.workspace_id, ids.account_id)
            assert scope.account.platform == provider
            assert scope.connection_version.split(":")[1] == str(ids.native_connection_id)
        assert set(inspect(engine).get_table_names()) == tables
        no_effects(engine)
        try:
            yield engine, ids, media
        finally:
            no_effects(engine)
    finally:
        if engine is not customer_engine:
            engine.dispose()
