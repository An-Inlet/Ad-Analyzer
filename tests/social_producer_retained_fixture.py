"""Current pure social producer over an immutable genuine original review graph."""

import json
import os
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import pytest
from app import advertising_capabilities
from app.campaign_review.contracts import MAX_VIDEO_BYTES
from app.campaign_review.models import MediaObject
from app.campaign_review.storage import LocalMediaStore
from app.database.session import Base
from app.meta.models import MetaConnection
from app.publication import coordinator
from app.publication.coordinator_contracts import CreationExecutionReview
from app.publication.execution_models import ProviderExecutionReview, ProviderExecutionRun
from app.publication.service import owner
from app.publication.social_contracts import SocialPublishPlan
from app.sources.models import SourceConnection
from scripts.inlet_producer_source_lifetime import SourceLifetime
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import Engine, create_engine, event, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from tests.financial_origin_retained_fixture import schema_snapshot
from tests.retired_snapshot import PIN, extract, run_bounded
from tests.test_commerce_measurement import NOW

if TYPE_CHECKING:
    from tests.social_execution_read_current_fixture import SocialExecutionReadEvidence
    from tests.social_review_api_current_fixture import SocialApiLoginEvidence
    from tests.social_review_ui_current_fixture import SocialUiEvidence


@dataclass(frozen=True)
class SocialProducerIds:
    workspace_id: int
    actor_id: str
    run_id: str
    review_id: str
    account_id: int
    provider: str
    native_id: str
    plan_digest: str
    native_posts: int


@dataclass(frozen=True)
class SocialProducerSource:
    engine: Engine
    ids: SocialProducerIds
    artifacts: Path
    api_evidence: "SocialApiLoginEvidence | None" = None
    ui_evidence: "SocialUiEvidence | None" = None
    execution_api_evidence: "SocialExecutionReadEvidence | None" = None


def owned_sqlite_target(target: str, expected: Path) -> str:
    url = make_url(target)
    assert url.drivername == "sqlite" and not url.query
    assert url.username is None and url.password is None and url.host is None and url.port is None
    assert url.database is not None
    path = Path(url.database)
    assert path.is_absolute() and path == expected and path.resolve() == path
    assert path.is_file() and not path.is_symlink()
    assert all(not parent.is_symlink() for parent in path.parents)
    return str(url)


def graph(engine: Engine) -> dict[str, list[dict[str, Any]]]:
    assert not advertising_capabilities.advertising_writes_enabled()
    with engine.connect() as connection:
        return {
            table.name: [
                dict(row)
                for row in connection.execute(
                    select(table).order_by(*table.primary_key.columns)
                ).mappings()
            ]
            for table in Base.metadata.sorted_tables
        }


def load_source(db: Session, source: SocialProducerSource) -> tuple[Any, ...]:
    from tests.test_social_customer_producer import _fixture_from_original

    assert db.get_bind() is source.engine
    ids = source.ids
    owner(db, ids.workspace_id, ids.actor_id)
    run = db.get(ProviderExecutionRun, ids.run_id)
    row = db.get(ProviderExecutionReview, ids.review_id)
    assert run and row and run.review_id == row.id
    assert run.workspace_id == row.workspace_id == ids.workspace_id
    document = CreationExecutionReview.model_validate(row.document)
    assert document.digest() == row.digest
    assert isinstance(document.plan, SocialPublishPlan)
    plan = document.plan
    assert plan.digest() == ids.plan_digest == row.plan_digest
    assert plan.review.scope.account.platform == ids.provider
    assert plan.review.scope.workspace_id == ids.workspace_id
    assert plan.review.scope.account.account_id == ids.account_id
    native: Any = (
        db.get(MetaConnection, int(ids.native_id))
        if ids.provider == "meta_ads"
        else db.get(SourceConnection, ids.native_id)
    )
    assert (
        native and native.workspace_id == ids.workspace_id and native.account_id == ids.account_id
    )
    store = LocalMediaStore(source.artifacts / "media")
    for media in db.scalars(select(MediaObject)):
        assert media.workspace_id == ids.workspace_id
        store.read_exact(ids.workspace_id, media.sha256, media.size)
    coordinator.source_current(db, ids.workspace_id, plan, ids.actor_id, store, lambda: NOW)
    result = _fixture_from_original(
        db, ids.workspace_id, ids.run_id, ids.actor_id, store, native, ids.provider
    )
    assert result[0] == plan and ids.native_posts == 0
    return result


@contextmanager
def retained_social_producer(
    original: Engine,
    artifacts: Path,
    provider: str,
    video: bytes | None,
    change: str | None,
    *,
    consumer: Literal["producer", "configuration", "api", "ui", "execution_api"] = "producer",
) -> Iterator[SocialProducerSource]:
    assert consumer in {"producer", "configuration", "api", "ui", "execution_api"}
    assert consumer == "producer" or change is None
    assert provider in {"meta_ads", "tiktok_ads"}
    assert change in {
        None,
        "generation",
        "unapproved",
        "foreign_media",
        "expired",
        "option",
        "declaration",
    }
    assert change is None or provider == "meta_ads"
    assert artifacts.is_absolute() and artifacts.resolve() == artifacts
    assert not artifacts.is_symlink() and all(not p.is_symlink() for p in artifacts.parents)
    artifacts.mkdir(parents=True)
    if provider == "tiktok_ads":
        assert type(video) is bytes and 0 < len(video) <= MAX_VIDEO_BYTES
        with (artifacts / "input.mp4").open("xb") as stream:
            stream.write(video)
    else:
        assert video is None
    engine = original
    if original.dialect.name == "sqlite":
        database = artifacts / "current.sqlite"
        database.touch(exist_ok=False)
        target = owned_sqlite_target(f"sqlite:///{database}", database)
        engine = create_engine(target)
        event.listen(engine, "connect", lambda db, _: db.execute("PRAGMA foreign_keys=ON"))
        Base.metadata.create_all(engine)
    else:
        safe = make_url(validate_disposable_url())
        assert safe.host in {"localhost", "127.0.0.1", "::1"} and not safe.query
        assert engine.url == safe
        with engine.connect() as connection:
            target = str(connection.scalar(text("SELECT current_schema()")))
        assert re.fullmatch(r"inlet_test_[a-f0-9]{32}", target)
    try:
        with engine.connect() as connection:
            for name in set(inspect(engine).get_table_names()) - {"alembic_version"}:
                quoted = engine.dialect.identifier_preparer.quote(name)
                assert connection.scalar(text(f"SELECT count(*) FROM {quoted}")) == 0
        schema = schema_snapshot(engine)
        root = Path(__file__).resolve().parents[1]
        with SourceLifetime.open("social_producer", artifacts) as lifetime:
            extract(root, lifetime.source)
            lifetime.extracted()
            output, log = artifacts / "ids.json", artifacts / "producer.log"
            lifetime.child_started()
            code = run_bounded(
                [
                    sys.executable,
                    str(root / "tests/fixtures/retired_execution/social_producer_seed_driver.py"),
                    target,
                    str(output),
                    provider,
                ],
                lifetime.source,
                dict(
                    os.environ, INLET_RETIRED_EXECUTION_CHILD=PIN, PYTHONPATH=str(lifetime.source)
                ),
                log,
                180,
            )
            lifetime.after_reaped(code)
        assert code == 0, log.read_text()[-6000:]
        assert 0 < output.stat().st_size <= 4096
        raw = json.loads(output.read_text())
        assert type(raw) is dict and set(raw) == set(SocialProducerIds.__dataclass_fields__)
        for key in ("workspace_id", "account_id"):
            assert type(raw[key]) is int and raw[key] > 0
        for key in ("actor_id", "run_id", "review_id", "plan_digest"):
            assert type(raw[key]) is str and re.fullmatch(
                r"[a-f0-9]{64}" if key == "plan_digest" else r"[a-f0-9]{32}", raw[key]
            )
        assert raw["provider"] == provider and type(raw["native_posts"]) is int
        assert raw["native_posts"] == 0 and type(raw["native_id"]) is str
        assert re.fullmatch(
            r"[1-9][0-9]*" if provider == "meta_ads" else r"[a-f0-9]{32}", raw["native_id"]
        )
        ids = SocialProducerIds(**raw)
        source = SocialProducerSource(engine, ids, artifacts)
        with Session(engine) as db:
            result = load_source(db, source)
            plan = result[0]
            image_id = plan.review.configuration.image.media_id if provider == "meta_ads" else None
            revision_key = (plan.review.source.draft_id, plan.review.source.revision)
        assert schema_snapshot(engine) == schema
        configuration_document = None
        if consumer == "configuration":
            from tests.social_configuration_current_fixture import expected_document

            with Session(engine) as db:
                configuration_document = expected_document(db, source)
        if consumer == "api":
            from tests.social_review_api_current_fixture import (
                SocialApiLoginEvidence,
                expected_api_document,
            )
            with Session(engine) as db:
                api = SocialApiLoginEvidence(expected_api_document(db, source), ids.actor_id)
            source = SocialProducerSource(engine, ids, artifacts, api)
        if consumer == "execution_api":
            from tests.social_execution_read_current_fixture import (
                SocialExecutionReadEvidence,
                expected_execution_document,
            )
            with Session(engine) as db:
                evidence = SocialExecutionReadEvidence(
                    expected_execution_document(db, source), ids.actor_id
                )
            source = SocialProducerSource(engine, ids, artifacts, execution_api_evidence=evidence)
        before = graph(engine)
        if consumer == "ui":
            from tests.social_review_ui_current_fixture import (
                SocialUiEvidence,
                expected_ui_document,
            )

            with Session(engine) as db:
                ui = SocialUiEvidence(
                    expected_ui_document(db, source), ids.actor_id, deepcopy(before)
                )
            source = SocialProducerSource(engine, ids, artifacts, ui_evidence=ui)
        assert all(
            not before[n]
            for n in (
                "provider_execution_attempts",
                "provider_execution_responses",
                "provider_execution_receipts",
            )
        )
        try:
            yield source
        finally:
            expected = deepcopy(before)
            if change == "generation":
                row = next(r for r in expected["meta_connections"] if str(r["id"]) == ids.native_id)
                row["generation"] += 1
            elif change == "unapproved":
                row = next(
                    r
                    for r in expected["customer_campaign_revisions"]
                    if (r["draft_id"], r["revision"]) == revision_key
                )
                row["approved_by"] = None
            elif change == "foreign_media":
                expected["customer_media_objects"] = [
                    r for r in expected["customer_media_objects"] if r["id"] != image_id
                ]
            actual = graph(engine)
            if configuration_document is not None:
                from tests.social_configuration_current_fixture import configuration_delta

                configuration_delta(expected, actual, ids, configuration_document)
            if source.execution_api_evidence is not None:
                source.execution_api_evidence.assert_delta(expected, actual)
            elif source.api_evidence is not None:
                source.api_evidence.assert_delta(expected, actual)
            elif source.ui_evidence is not None:
                source.ui_evidence.assert_delta(expected, actual)
            else:
                assert actual == expected
            assert schema_snapshot(engine) == schema
    finally:
        if engine is not original:
            engine.dispose()


@pytest.fixture
def social_producer_source(
    customer_engine: Engine,
    tmp_path: Path,
    request: pytest.FixtureRequest,
) -> Iterator[SocialProducerSource]:
    name = request.node.originalname
    assert name in {
        "test_produce_canonical_owned_plan_with_exact_cover_review",
        "test_producer_rejects_stale_or_unowned_inputs",
        "test_tiktok_missing_or_foreign_cover_never_auto_selected",
    }
    params = request.node.callspec.params
    provider = params.get(
        "provider",
        "tiktok_ads"
        if name == "test_tiktok_missing_or_foreign_cover_never_auto_selected"
        else "meta_ads",
    )
    video = request.getfixturevalue("encoded")() if provider == "tiktok_ads" else None
    with retained_social_producer(
        customer_engine, tmp_path / "social-original", provider, video, params.get("change")
    ) as source:
        yield source
