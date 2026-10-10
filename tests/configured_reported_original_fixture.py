"""One genuine configured original effect; current reported work remains current."""

import json
import os
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from app import advertising_capabilities
from app.commerce.models import CommerceMeasurementPublication
from app.customers.models import CustomerMembership
from app.database.models import register_models
from app.database.session import Base
from app.goals import service as goals
from app.production_runtime.optimization_origin_contracts import OptimizationMandatePreparationV1
from app.production_runtime.optimization_origin_models import OptimizationMandatePreparationRow
from app.publication import customer_intents, execution_mandates
from app.publication.contracts import fingerprint
from scripts.inlet_producer_source_lifetime import SourceLifetime
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import Engine, create_engine, event, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from tests.financial_origin_retained_fixture import fresh_rows, schema_snapshot
from tests.initial_lineage_retained_fixture import artifact_path
from tests.retired_snapshot import PIN, extract, run_bounded
from tests.social_producer_retained_fixture import owned_sqlite_target


@dataclass(frozen=True)
class ConfiguredReportedOriginalIds:
    platform: Literal["meta_ads"]
    workspace_id: int
    account_id: int
    goal_revision: int
    mandate_revision: int
    actor_id: str
    goal_id: str
    mandate_id: str
    consent_id: str
    ledger_id: str
    store_id: str
    publication_id: str
    native_connection_id: int
    policy_digest: str
    preparation_digest: str
    goal_digest: str
    account_scope_digest: str
    operating_policy_digest: str
    optimization_manifest_digest: str
    candidate_policy_digest: str
    candidate_manifest_digest: str
    evidence_descriptor_digest: str
    publication_manifest_digest: str
    provider_posts: int
    run_id: str
    review_id: str
    attempt_id: str
    receipt_id: str
    reservation_id: str
    request_digest: str
    receipt_digest: str


def read_ids(output: Path) -> ConfiguredReportedOriginalIds:
    assert output.is_file() and not output.is_symlink()
    assert 0 < output.stat().st_size <= 8192
    raw = json.loads(output.read_text())
    assert type(raw) is dict and set(raw) == set(ConfiguredReportedOriginalIds.__dataclass_fields__)
    assert raw["platform"] == "meta_ads"
    for key, value in raw.items():
        if key == "platform":
            continue
        if key == "provider_posts":
            assert type(value) is int and value == 1
        elif key in {"workspace_id", "account_id", "goal_revision", "mandate_revision"} or (
            key == "native_connection_id"
        ):
            assert type(value) is int and value > 0
        else:
            assert type(value) is str and re.fullmatch(
                r"[a-f0-9]{64}" if key.endswith("digest") else r"[a-f0-9]{32}", value
            )
    return ConfiguredReportedOriginalIds(**raw)


def validate_files(path: Path, ids: ConfiguredReportedOriginalIds) -> None:
    """Fixed producer files are commitments, never caller-selected paths or authority."""
    from app.production_runtime.candidate_configuration import (
        CandidateAssemblyManifestV1,
        CandidatePolicyBundleV1,
    )
    from app.production_runtime.optimization_contracts import OptimizationExecutionManifestV1
    from app.production_runtime.optimization_policy_contracts import OptimizationOperatingPolicyV1

    def bounded(name: str) -> str:
        file = path / name
        assert file.is_file() and not file.is_symlink() and 0 < file.stat().st_size <= 65536
        return file.read_text()

    operating = OptimizationOperatingPolicyV1.model_validate_json(
        bounded("optimization-policy.json")
    )
    optimization = OptimizationExecutionManifestV1.model_validate_json(
        bounded("optimization-manifest.json")
    )
    candidate = CandidateAssemblyManifestV1.model_validate_json(bounded("candidate_manifest.json"))
    policies = CandidatePolicyBundleV1.model_validate_json(bounded("candidate_policy.json"))
    assert operating.digest() == optimization.operating_policy_digest == ids.operating_policy_digest
    assert optimization.digest() == ids.optimization_manifest_digest
    # Original generic candidate files precede the original replacement-enabled effect.
    assert candidate.optimization_manifest_digest == optimization.model_copy(
        update={"replacement_enabled": False}
    ).digest()
    assert optimization.replacement_enabled and not optimization.settlement_enabled
    assert candidate.digest() == ids.candidate_manifest_digest
    assert policies.digest() == candidate.policy_bundle_digest == ids.candidate_policy_digest
    assert candidate.evidence_descriptor_digest == ids.evidence_descriptor_digest
    assert candidate.environment == policies.environment == "contract_test"
    assert candidate.mode == "candidates_only"
    assert len(policies.candidate_policies) == 1 and not policies.automatic_policies
    assert policies.candidate_policies[0].workspace_id == ids.workspace_id


def financial_graph(engine: Engine) -> dict[str, list[dict[str, Any]]]:
    """Exact current physical rows, excluding only unrelated session/candidate domains."""
    with engine.connect() as connection:
        return {
            table.name: [
                dict(row)
                for row in connection.execute(
                    select(table).order_by(*table.primary_key.columns)
                ).mappings()
            ]
            for table in Base.metadata.sorted_tables
            if table.name.startswith("provider_")
            or table.name
            in {
                "mandate_actions",
                "optimization_mandate_preparations",
                "google_original_completions",
            }
        }


@contextmanager
def retained_configured_reported_original(
    original: Engine, artifacts: Path
) -> Iterator[tuple[Engine, ConfiguredReportedOriginalIds]]:
    platform = "meta_ads"
    assert not advertising_capabilities.advertising_writes_enabled()
    artifact_path(artifacts)
    artifacts.mkdir(parents=True)
    engine = original
    if original.dialect.name == "sqlite":
        database = artifacts / "current.sqlite"
        database.touch(exist_ok=False)
        target = owned_sqlite_target(f"sqlite:///{database}", database)
        engine = create_engine(target)
        event.listen(engine, "connect", lambda db, _: db.execute("PRAGMA foreign_keys=ON"))
        register_models().create_all(engine)
        target = str(engine.url)
    else:
        base = make_url(validate_disposable_url())
        assert (
            base.host in {"localhost", "127.0.0.1", "::1"} and not base.query and engine.url == base
        )
        with engine.connect() as connection:
            target = str(connection.scalar(text("SELECT current_schema()")))
        assert re.fullmatch(r"inlet_test_[a-f0-9]{32}", target)
    try:
        assert fresh_rows(engine) == {}
        before = schema_snapshot(engine)
        root = Path(__file__).resolve().parents[1]
        with SourceLifetime.open("configured_reported_original", artifacts) as lifetime:
            extract(root, lifetime.source)
            lifetime.extracted()
            output, log = artifacts / "ids.json", artifacts / "producer.log"
            lifetime.child_started()
            code = run_bounded(
                [
                    sys.executable,
                    str(
                        root
                        / "tests/fixtures/retired_execution"
                        / "configured_reported_original_seed_driver.py"
                    ),
                    target,
                    str(output),
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
        assert schema_snapshot(engine) == before
        ids = read_ids(output)
        validate_files(artifacts, ids)
        with Session(engine) as db:
            binding = customer_intents.binding(
                db, ids.workspace_id, ids.mandate_id, ids.mandate_revision
            )
            assert (
                binding.consent_id == ids.consent_id
                and binding.ledger_id == ids.ledger_id
                and binding.policy_digest == ids.policy_digest
            )
            _, row = execution_mandates.owned(db, ids.workspace_id, ids.mandate_id)
            policy = execution_mandates.policy(db, row)
            assert row.state == "active" and policy.total_cap_micros == 50_000_000
            assert policy.goal_id == ids.goal_id and policy.goal_revision == ids.goal_revision
            assert (
                len(policy.accounts) == 1
                and policy.accounts[0].account.account_id == ids.account_id
            )
            assert policy.accounts[0].account.platform == platform and policy.accounts[
                0
            ].connection_version.split(":")[1] == str(ids.native_connection_id)
            stored = db.get(
                OptimizationMandatePreparationRow, (ids.mandate_id, ids.mandate_revision)
            )
            assert stored
            origin = OptimizationMandatePreparationV1.model_validate(stored.document)
            assert origin.digest() == stored.preparation_digest == ids.preparation_digest
            assert (
                origin.provider_policy_digest == ids.policy_digest
                and origin.operating_policy_digest == ids.operating_policy_digest
            )
            assert (
                origin.goal_digest == ids.goal_digest
                and origin.account_scope_digest == ids.account_scope_digest
            )
            goal = goals.owned(db, ids.workspace_id, ids.goal_id)
            assert goal.revision == ids.goal_revision
            assert (
                fingerprint(
                    "inlet.optimization-goal.v1", {"definition": goals.current(db, goal).definition}
                )
                == ids.goal_digest
            )
            member = db.get(CustomerMembership, (ids.actor_id, ids.workspace_id))
            assert member and member.role == "owner" and member.status == "active"
            publication = db.get(CommerceMeasurementPublication, ids.publication_id)
            assert (
                publication
                and publication.workspace_id == ids.workspace_id
                and publication.store_id == ids.store_id
                and publication.manifest_digest == ids.publication_manifest_digest
            )
        validate_original(engine, ids)
        before_financial = financial_graph(engine)
        try:
            yield engine, ids
        finally:
            assert not advertising_capabilities.advertising_writes_enabled()
            assert schema_snapshot(engine) == before
            assert financial_graph(engine) == before_financial
    finally:
        if engine is not original:
            engine.dispose()


def validate_original(engine: Engine, ids: ConfiguredReportedOriginalIds) -> None:
    from app.publication import optimization
    from app.publication.execution_models import (
        ProviderExecutionApproval,
        ProviderExecutionAttempt,
        ProviderExecutionReceipt,
        ProviderExecutionResponse,
        ProviderExecutionReview,
        ProviderExecutionRun,
        ProviderExecutionStep,
        ProviderExposureReservation,
    )
    from app.publication.optimization_contracts import (
        MetaBudgetSetV1,
        MetaCurrentState,
        OptimizationReceipt,
    )
    from sqlalchemy import func

    with Session(engine) as db:
        for name in (
            "optimization_candidate_jobs",
            "optimization_candidate_results",
            "reported_feedback_jobs",
            "reported_window_capsules",
            "reported_action_comparisons",
            "session_automation_runs",
            "provider_automatic_decisions",
        ):
            assert db.scalar(text(f"SELECT count(*) FROM {name}")) == 0
        for model in (
            ProviderExecutionApproval,
            ProviderExecutionReview,
            ProviderExecutionStep,
            ProviderExecutionResponse,
            ProviderExecutionAttempt,
            ProviderExecutionReceipt,
            ProviderExecutionRun,
            ProviderExposureReservation,
        ):
            assert db.scalar(select(func.count()).select_from(model)) == 1
        run, review, attempt, request = optimization.evidence_lock(
            db, ids.workspace_id, ids.attempt_id
        )
        assert run.id == ids.run_id and run.review_id == ids.review_id
        assert run.reservation_id == ids.reservation_id
        assert attempt.request_digest == ids.request_digest
        assert request.intent.scope.account.account_id == ids.account_id
        assert request.intent.target.kind == "campaign" and request.intent.target.external_id == "5"
        assert isinstance(request.intent.action, MetaBudgetSetV1)
        assert request.intent.action.amount_micros == 45_000_000
        stored = db.get(ProviderExecutionReceipt, ids.receipt_id)
        assert stored and stored.digest == ids.receipt_digest
        assert stored.attempt_id == ids.attempt_id
        receipt = OptimizationReceipt.model_validate(stored.receipt)
        assert receipt.outcome == "verified_target_state" and isinstance(
            receipt.after, MetaCurrentState
        )
        assert receipt.after.daily_budget_micros == 45_000_000
        assert receipt.after.money.currency == "USD" and receipt.after.money.currency_exponent == 2
        projected = optimization.read_owned_outcome_receipt(
            db, ids.workspace_id, ids.attempt_id, ids.actor_id
        )
        assert projected and projected.receipt_id == ids.receipt_id
        held = db.get(ProviderExposureReservation, ids.reservation_id)
        assert held and held.state == "held" and held.workspace_id == ids.workspace_id
