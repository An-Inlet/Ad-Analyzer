"""Original configured candidate source stops before enqueue; no current authority."""

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, cast

import app
import pytest
from app.commerce.models import CommerceMeasurementPublication
from app.customers.access import SESSION_COOKIE, digest
from app.customers.models import CustomerSession
from app.production_runtime.candidate_configuration import (
    CandidateAssemblyManifestV1,
    CandidatePolicyBundleV1,
)
from app.production_runtime.optimization_contracts import OptimizationExecutionManifestV1
from app.production_runtime.optimization_origin_contracts import OptimizationMandatePreparationV1
from app.production_runtime.optimization_origin_models import OptimizationMandatePreparationRow
from app.publication import customer_intents, execution_mandates
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import create_engine, event, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from tests.configured_candidates_fixture import configured_candidates_customer
from tests.test_customer_identity import replicas
from tests.test_shopify_sales import configuration

ZERO = (
    "optimization_candidate_jobs",
    "optimization_candidate_results",
    "provider_execution_reviews",
    "provider_execution_approvals",
    "provider_execution_runs",
    "provider_execution_steps",
    "provider_execution_attempts",
    "provider_execution_receipts",
    "provider_execution_responses",
    "provider_exposure_reservations",
)


def main() -> None:
    target, output, platform, mode = sys.argv[1:]
    assert platform in {"google_ads", "meta_ads"}
    assert mode in {"unqualified", "scenario", "revoked", "revoked_during_read"}
    assert (
        os.environ.get("INLET_RETIRED_EXECUTION_CHILD")
        == "2155ff3e3ab00cd62057dd86cb49d45359d4f49f"
    )
    assert Path(app.__file__).resolve().is_relative_to(Path(os.environ["PYTHONPATH"]).resolve())
    path = Path(output).resolve().parent
    if target.startswith("sqlite:"):
        url = make_url(target)
        assert (
            not url.query
            and url.database
            and Path(url.database).resolve() == path / "current.sqlite"
        )
        assert Path(url.database).is_file()
        engine = create_engine(url)
        event.listen(engine, "connect", lambda db, _: db.execute("PRAGMA foreign_keys=ON"))
    else:
        assert re.fullmatch(r"inlet_test_[a-f0-9]{32}", target)
        url = make_url(validate_disposable_url())
        assert url.host in {"localhost", "127.0.0.1", "::1"} and not url.query
        engine = create_engine(url, connect_args={"options": f"-csearch_path={target}"})
    clients = None
    try:
        with engine.connect() as connection:
            if engine.dialect.name == "postgresql":
                assert connection.scalar(text("SELECT current_schema()")) == target
            for name in set(inspect(engine).get_table_names()) - {"alembic_version"}:
                quoted = engine.dialect.identifier_preparer.quote(name)
                assert connection.scalar(text(f"SELECT count(*) FROM {quoted}")) == 0
        with pytest.MonkeyPatch.context() as patch:
            clients = cast(Any, replicas).__wrapped__(engine, patch)
            alice, base, wire, control, draft = configured_candidates_customer(
                engine, cast(Any, configuration).__wrapped__(), path, patch, clients, platform, mode
            )
            wid = int(base.split("/workspaces/")[1].split("/")[0])
            with Session(engine) as db:
                session = db.get(CustomerSession, digest(alice.cookies[SESSION_COOKIE]))
                assert session
                binding = customer_intents.binding(db, wid, draft["mandate_id"], draft["revision"])
                _, row = execution_mandates.owned(db, wid, binding.mandate_id)
                policy = execution_mandates.policy(db, row)
                stored = db.get(OptimizationMandatePreparationRow, (row.id, row.revision))
                assert stored
                origin = OptimizationMandatePreparationV1.model_validate(stored.document)
                publication = db.scalars(
                    select(CommerceMeasurementPublication).where(
                        CommerceMeasurementPublication.workspace_id == wid
                    )
                ).one()
                optimization = OptimizationExecutionManifestV1.model_validate_json(
                    (path / "optimization-manifest.json").read_text()
                )
                candidate = CandidateAssemblyManifestV1.model_validate_json(
                    (path / "candidate_manifest.json").read_text()
                )
                bundle = CandidatePolicyBundleV1.model_validate_json(
                    (path / "candidate_policy.json").read_text()
                )
                native = policy.accounts[0].connection_version.split(":")[1]
                data = dict(
                    platform=platform,
                    workspace_id=wid,
                    actor_id=session.user_id,
                    account_id=policy.accounts[0].account.account_id,
                    goal_id=policy.goal_id,
                    goal_revision=policy.goal_revision,
                    mandate_id=row.id,
                    mandate_revision=row.revision,
                    consent_id=binding.consent_id,
                    ledger_id=binding.ledger_id,
                    native_connection_id=int(native) if platform == "meta_ads" else native,
                    store_id=publication.store_id,
                    publication_id=publication.id,
                    policy_digest=policy.digest(),
                    preparation_digest=origin.digest(),
                    goal_digest=origin.goal_digest,
                    account_scope_digest=origin.account_scope_digest,
                    operating_policy_digest=origin.operating_policy_digest,
                    optimization_manifest_digest=optimization.digest(),
                    candidate_policy_digest=bundle.digest(),
                    candidate_manifest_digest=candidate.digest(),
                    evidence_descriptor_digest=candidate.evidence_descriptor_digest,
                    publication_manifest_digest=publication.manifest_digest,
                    provider_posts=len(wire.google.writes) + len(wire.meta.posts),
                )
                assert data["provider_posts"] == 0 and control["opened"] == control["closed"]
                for name in ZERO:
                    assert db.scalar(text(f"SELECT count(*) FROM {name}")) == 0
                db.commit()
            Path(output).write_text(json.dumps(data))
    finally:
        if clients:
            clients[0].close()
            clients[1].close()
        engine.dispose()


if __name__ == "__main__":
    main()
