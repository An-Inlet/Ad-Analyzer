"""Retain original in-memory catalog across one parent-owned0059 upgrade."""

import importlib.util
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, cast

import app
import pytest
from app.publication.execution_authorization import owner_authorizer
from app.publication.execution_models import ProviderExecutionRun
from app.publication.social_review_contracts import MetaNoDSAAnswer, SocialRequirements
from app.publication.social_review_service import confirm, prepare, selection
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import create_engine, func, inspect, make_url, select
from sqlalchemy.orm import Session
from tests import test_social_customer_producer as producer_module
from tests.candidate_historical_schema import without_candidates
from tests.optimization_origin_historical_schema import install_legacy_origin
from tests.test_commerce_measurement import NOW
from tests.test_shopify_sales import configuration
from tests.test_social_configuration_migration import HistoricalFixtureSession
from tests.test_social_coordinator_journeys import SocialServer


def main() -> None:
    schema, directory = sys.argv[1:]
    artifacts = Path(directory)
    assert os.environ["INLET_RETIRED_EXECUTION_CHILD"] == "2155ff3e3ab00cd62057dd86cb49d45359d4f49f"
    assert Path(app.__file__).resolve().is_relative_to(Path(os.environ["PYTHONPATH"]).resolve())
    root = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location(
        "_social_boundary", root / "tests/social_restore_boundary.py"
    )
    assert spec and spec.loader
    boundary = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(boundary)
    url = make_url(validate_disposable_url()).update_query_dict(
        {"options": f"-csearch_path={schema}"}
    )
    engine = create_engine(url)
    patch = pytest.MonkeyPatch()
    cleanup = None
    try:
        boundary.owned(engine, "social", "20261006_0057")
        snapshot = boundary.fresh(engine)
        tables = set(inspect(engine).get_table_names())
        cleanup = install_legacy_origin(patch, engine)
        without_candidates(patch, engine)
        servers = []
        original = SocialServer

        def capture(provider: str) -> Any:
            server = original(provider)
            servers.append(server)
            return server

        patch.setattr(producer_module, "SocialServer", capture)
        config = cast(Any, configuration).__wrapped__()
        with HistoricalFixtureSession(engine) as db:
            _, account, catalog, producer, actor, store, _, _ = producer_module.fixture(
                db, config, artifacts, "meta_ads", None
            )
            profile = next(iter(producer.profiles.values())).model_copy(
                update={"dsa_required": False}
            )
            option = catalog.options[0].model_copy(update={"profile_digest": profile.digest()})
            catalog = catalog.model_copy(update={"options": [option]})
            run = db.scalars(select(ProviderExecutionRun)).one()
            output = dict(
                workspace_id=account.workspace_id,
                actor_id=actor,
                run_id=run.id,
                provider_posts=servers[0].posts,
            )
            assert len(servers) == 1 and output["provider_posts"] == 0
            db.commit()
        assert set(inspect(engine).get_table_names()) == tables
        engine.dispose()
        ready = artifacts / "prepared.tmp"
        ready.write_text(json.dumps(output))
        ready.replace(artifacts / "prepared.json")
        start = time.monotonic()
        marker = artifacts / "continue.json"
        while not marker.exists():
            assert time.monotonic() - start < 180
            time.sleep(0.05)
        assert json.loads(marker.read_text()) == {"phase": "confirm0059"}
        boundary.owned(engine, "social", "20261006_0059")
        assert set(inspect(engine).get_table_names()) == tables | {
            "customer_social_configuration_reviews",
            "customer_social_configuration_approvals",
        }
        with Session(engine) as final_db:
            final_run = final_db.get(ProviderExecutionRun, output["run_id"])
            assert final_run and final_run.workspace_id == account.workspace_id
            document = selection(
                final_db,
                account.workspace_id,
                actor,
                account,
                catalog,
                option.identifier(catalog.request),
                profile,
                SocialRequirements(
                    profile_digest=profile.digest(),
                    requirements_digest="a" * 64,
                    wording_version="test-v1",
                    verified=True,
                    dsa_required=False,
                    wording="Offline Test: Review This No-DSA Profile And Its Exact Media.",
                ),
                MetaNoDSAAnswer(special_category_answer="none_applicable"),
                None,
                "contract_test",
                store,
                lambda: NOW,
                owner_authorizer,
            )
            row = prepare(
                final_db, account.workspace_id, actor, document, lambda: NOW, owner_authorizer
            )
            confirm(
                final_db,
                account.workspace_id,
                row.id,
                row.digest,
                actor,
                document,
                lambda: NOW,
                owner_authorizer,
            )
            output.update(
                configuration_review_id=row.id,
                configuration_digest=row.digest,
                run_count=final_db.scalar(select(func.count(ProviderExecutionRun.id))),
            )
            assert servers[0].posts == 0
            final_db.commit()
        boundary.unchanged(engine, snapshot)
        (artifacts / "confirmed.json").write_text(json.dumps(output))
    finally:
        if cleanup is not None:
            cleanup()
        patch.undo()
        engine.dispose()


if __name__ == "__main__":
    main()
