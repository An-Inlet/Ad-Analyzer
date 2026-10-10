"""Closed two-brand historical source; no current advertising runtime crosses the boundary."""

import json
import os
import re
import stat
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, Any, Literal

from app import advertising_capabilities
from app.database.models import register_models
from app.database.session import Base
from pydantic import BaseModel, ConfigDict, Field, model_validator
from scripts.inlet_producer_source_lifetime import SourceLifetime
from scripts.reset_disposable_postgres import validate_disposable_url
from sqlalchemy import Engine, create_engine, event, select, text
from sqlalchemy.engine import make_url

from tests.financial_origin_retained_fixture import fresh_rows, schema_snapshot
from tests.google_completion_retained_fixture import owned_sqlite_target
from tests.retired_snapshot import PIN, extract, run_bounded

FILE = "15049bf103f6f9178c41622cad79c2c3d2ef75ef574191daa07c801eec2ed4b3"
FUNCTION = "36ba3f74cb7f08b5e9db750ee83d270b73d9b1ef5cbb8fed53911779a8f60199"
PREFIX = "f58209c8b6a20b1fffbe0fa202feec8fe466e0889f5475426aadc893e7e07cf2"
Id = Annotated[str, Field(strict=True, pattern=r"^[a-f0-9]{32}$")]
Digest = Annotated[str, Field(strict=True, pattern=r"^[a-f0-9]{64}$")]
IntId = Annotated[int, Field(strict=True, ge=1, le=2147483647)]
One = Annotated[int, Field(strict=True, ge=1, le=1)]
Rows = dict[str, list[dict[str, Any]]]


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class SourceRevision(Closed):
    draft_id: Id
    revision: One
    digest: Digest


class Social(Closed):
    source: SourceRevision
    media_id: Id
    media_sha256: Digest
    review_id: Id
    review_digest: Digest
    approval_digest: Digest


class Brand(Closed):
    provider: Literal["meta_ads", "google_ads"]
    workspace_id: IntId
    actor_id: Id
    goal_id: Id
    simulation_mandate_id: Id
    google_connection_id: Id
    google_account_id: IntId
    google_integration_id: IntId
    meta_connection_id: IntId | None
    meta_account_id: IntId | None
    meta_integration_id: IntId | None
    shopify_connection_id: IntId
    shopify_integration_id: IntId
    crm_connection_id: IntId
    crm_integration_id: IntId
    commerce_store_id: Id
    provider_mandate_id: Id
    consent_id: Id
    ledger_id: Id
    provider_mandate_revision: One
    original_review_id: Id
    original_run_id: Id
    original_attempt_id: Id
    original_fence: Id
    original_request_digest: Digest
    original_response_digest: Digest
    original_receipt_digest: Digest
    original_receipt_id: Id
    predecessor_reservation_id: Id
    repeat_review_id: Id
    successor_run_id: Id
    successor_reservation_id: Id
    replacement_id: Id
    repeat_review_digest: Digest
    replacement_digest: Digest
    google_source: SourceRevision
    social: Social | None
    source_mutation_count: One

    @model_validator(mode="after")
    def provider_shape(self) -> "Brand":
        values = (
            self.meta_connection_id,
            self.meta_account_id,
            self.meta_integration_id,
            self.social,
        )
        if any((value is not None) != (self.provider == "meta_ads") for value in values):
            raise ValueError("closed provider shape changed")
        return self


class SourceIds(Closed):
    schema_version: Literal["inlet.test.archive-financial-social-source.v1"]
    source_commit: Literal["2155ff3e3ab00cd62057dd86cb49d45359d4f49f"]
    source_file_sha256: Digest
    source_function_ast_sha256: Digest
    source_prefix_ast_sha256: Digest
    brand_a: Brand
    brand_b: Brand

    @model_validator(mode="after")
    def provenance(self) -> "SourceIds":
        if (
            self.source_file_sha256,
            self.source_function_ast_sha256,
            self.source_prefix_ast_sha256,
        ) != (FILE, FUNCTION, PREFIX):
            raise ValueError("source changed")
        if (self.brand_a.provider, self.brand_b.provider) != ("meta_ads", "google_ads"):
            raise ValueError("provider order changed")
        if (
            self.brand_a.workspace_id == self.brand_b.workspace_id
            or self.brand_a.actor_id == self.brand_b.actor_id
        ):
            raise ValueError("source ownership collapsed")
        return self


def read_ids(output: Path) -> SourceIds:
    info = output.lstat()
    assert not output.is_symlink() and stat.S_ISREG(info.st_mode) and 0 < info.st_size <= 16384

    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result = dict(values)
        assert len(result) == len(values), "duplicate DTO key"
        return result

    def depth(value: Any, level: int = 0) -> None:
        assert level <= 8
        if isinstance(value, dict):
            for item in value.values():
                depth(item, level + 1)
        elif isinstance(value, list):
            for item in value:
                depth(item, level + 1)

    raw = json.loads(
        output.read_text(),
        object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")),
    )
    depth(raw)
    return SourceIds.model_validate(raw)


def graph(engine: Engine) -> Rows:
    assert not advertising_capabilities.advertising_writes_enabled()
    with engine.connect() as db:
        return {
            table.name: [
                dict(r)
                for r in db.execute(select(table).order_by(*table.primary_key.columns)).mappings()
            ]
            for table in Base.metadata.sorted_tables
        }


def validate_source(engine: Engine, ids: SourceIds) -> Rows:
    """Independent source cardinality gate; stop rather than widen this closed shape."""
    rows = graph(engine)
    assert len(rows["google_original_completions"]) == 1
    for table in (
        "customer_sessions",
        "customer_token_exchanges",
        "customer_lifecycle_requests",
        "customer_lifecycle_steps",
        "customer_workspace_signups",
        "workspace_memberships",
        "customer_source_connections",
        "session_automation_runs",
        "workspace_automation_controls",
        "mandate_actions",
        "customer_context_checkpoints",
        "google_customer_import_completions",
    ):
        assert rows[table] == [], table
    assert (
        len(rows["workspaces"])
        == len(rows["customer_users"])
        == len(rows["customer_memberships"])
        == 2
    )
    counts = {
        "crm_connections": 1,
        "shopify_connections": 1,
        "commerce_stores": 1,
        "google_customer_connections": 1,
        "customer_goals": 1,
        "spending_mandates": 1,
        "provider_period_ledgers": 1,
        "provider_execution_mandates": 1,
        "provider_execution_revisions": 1,
        "provider_execution_consents": 1,
        "provider_execution_reviews": 2,
        "provider_execution_approvals": 2,
        "provider_execution_runs": 2,
        "provider_execution_steps": 2,
        "provider_execution_attempts": 1,
        "provider_execution_responses": 1,
        "provider_execution_receipts": 1,
        "provider_exposure_reservations": 2,
        "provider_reservation_replacements": 1,
    }
    for brand in (ids.brand_a, ids.brand_b):
        for table, count in counts.items():
            actual = [r for r in rows[table] if r["workspace_id"] == brand.workspace_id]
            assert len(actual) == count, (brand.provider, table, len(actual), count)
        integrations = [
            r for r in rows["workspace_integrations"] if r["workspace_id"] == brand.workspace_id
        ]
        assert len(integrations) == (4 if brand.provider == "meta_ads" else 3)
        holds = [
            r
            for r in rows["provider_exposure_reservations"]
            if r["workspace_id"] == brand.workspace_id
        ]
        assert {r["id"]: (r["state"], r["amount_micros"]) for r in holds} == {
            brand.predecessor_reservation_id: ("superseded", 40_000_000),
            brand.successor_reservation_id: ("held", 40_000_000),
        }
        ledger = next(r for r in rows["provider_period_ledgers"] if r["id"] == brand.ledger_id)
        assert ledger["action_count"] == 2 and ledger["spent_high_water_micros"] == 0
    return rows


@contextmanager
def retained_archive_source(
    original: Engine, artifacts: Path
) -> Iterator[tuple[Engine, SourceIds]]:
    assert artifacts.is_absolute() and artifacts.resolve() == artifacts
    assert not artifacts.is_symlink() and all(not p.is_symlink() for p in artifacts.parents)
    artifacts.mkdir(parents=True)
    root = Path(__file__).resolve().parents[1]
    engine = original
    if original.dialect.name == "sqlite":
        database = artifacts / "current.sqlite"
        with database.open("xb"):
            pass
        target = owned_sqlite_target(f"sqlite:///{database}", database)
        engine = create_engine(target, connect_args={"check_same_thread": False})
        event.listen(engine, "connect", lambda db, _: db.execute("PRAGMA foreign_keys=ON"))
        register_models().create_all(engine)
    else:
        base = make_url(validate_disposable_url())
        assert (
            base.host in {"localhost", "127.0.0.1", "::1"} and not base.query and engine.url == base
        )
        with engine.connect() as db:
            target = str(db.scalar(text("SELECT current_schema()")))
        assert re.fullmatch(r"inlet_test_[a-f0-9]{32}", target)
    try:
        assert fresh_rows(engine) == {}
        schema = schema_snapshot(engine)
        with SourceLifetime.open("archive_financial_social", artifacts) as lifetime:
            extract(root, lifetime.source)
            lifetime.extracted()
            output, log = artifacts / "ids.json", artifacts / "producer.log"
            lifetime.child_started()
            code = run_bounded(
                [
                    sys.executable,
                    str(
                        root
                        / "tests/fixtures/retired_execution/archive_financial_social_seed_driver.py"
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
        assert schema_snapshot(engine) == schema
        ids = read_ids(output)
        validate_source(engine, ids)
        validate_typed_source(engine, ids, artifacts / "media")
        try:
            yield engine, ids
        finally:
            assert schema_snapshot(engine) == schema
    finally:
        if engine is not original:
            engine.dispose()


def validate_typed_source(engine: Engine, ids: SourceIds, media: Path) -> None:
    """Parse immutable financial/media documents independently in current code."""
    from app.campaign_review.contracts import ReviewArtifact
    from app.campaign_review.storage import LocalMediaStore
    from app.publication import customer_intents, optimization
    from app.publication.contracts import fingerprint
    from app.publication.execution_models import (
        ProviderExecutionReceipt,
        ProviderExecutionResponse,
        ProviderExecutionReview,
        ProviderReservationReplacement,
    )
    from app.publication.google_completion import read_owned
    from app.publication.optimization_contracts import (
        GoogleBudgetSetV1,
        MetaBudgetSetV1,
        OptimizationResponse,
    )
    from app.publication.replacement_contracts import (
        RepeatOptimizationReview,
        ReplacementAuditDocument,
    )
    from app.publication.scoped_media import ScopedProviderMediaReader
    from app.publication.social_review_contracts import SocialConfigurationDocument
    from app.shopify.security import utc
    from sqlalchemy.orm import Session

    from tests.test_commerce_measurement import NOW
    from tests.test_customer_identity import ISSUER

    rows = graph(engine)

    def one(table: str, **values: Any) -> dict[str, Any]:
        found = [r for r in rows[table] if all(r[k] == v for k, v in values.items())]
        assert len(found) == 1, table
        return found[0]

    with Session(engine) as db:
        for brand, subject in ((ids.brand_a, "brand-a"), (ids.brand_b, "brand-b")):
            wid = brand.workspace_id
            assert one("customer_users", id=brand.actor_id) == dict(
                id=brand.actor_id,
                issuer=ISSUER,
                subject=subject,
                email="mock@example.invalid",
                status="active",
            )
            assert one("customer_memberships", user_id=brand.actor_id) == dict(
                user_id=brand.actor_id, workspace_id=wid, role="owner", status="active"
            )
            workspace = one("workspaces", id=wid)
            assert (
                workspace["slug"] == f"brand-b-{wid}"
                and workspace["name"] == subject
                and workspace["status"] == "active"
            )
            for table, identifier in (
                ("customer_goals", brand.goal_id),
                ("spending_mandates", brand.simulation_mandate_id),
                ("commerce_stores", brand.commerce_store_id),
                ("provider_period_ledgers", brand.ledger_id),
            ):
                assert one(table, id=identifier)["workspace_id"] == wid
            for table, connection_identifier, integration in (
                ("crm_connections", brand.crm_connection_id, brand.crm_integration_id),
                ("shopify_connections", brand.shopify_connection_id, brand.shopify_integration_id),
            ):
                native = one(table, id=connection_identifier)
                assert (
                    native["workspace_id"] == wid
                    and native["workspace_integration_id"] == integration
                )
            shop = one("shopify_connections", id=brand.shopify_connection_id)
            assert (
                shop["commerce_store_id"] == brand.commerce_store_id
                and shop["shop_domain"] == f"brand-{shop['id']}.myshopify.com"
            )
            for table, native_id, account_id, integration_id in (
                (
                    "google_customer_connections",
                    brand.google_connection_id,
                    brand.google_account_id,
                    brand.google_integration_id,
                ),
                *(
                    (
                        [
                            (
                                "meta_connections",
                                brand.meta_connection_id,
                                brand.meta_account_id,
                                brand.meta_integration_id,
                            )
                        ]
                    )
                    if brand.provider == "meta_ads"
                    else []
                ),
            ):
                native = one(table, id=native_id)
                account = one("advertising_accounts", id=account_id)
                assert native["workspace_id"] == account["workspace_id"] == wid
                assert (
                    native["account_id"] == account_id
                    and account["connection_id"] == integration_id
                )
                assert native["generation"] == 1
            run, review, attempt, request = optimization.evidence_lock(
                db, wid, brand.original_attempt_id
            )
            assert run.id == brand.original_run_id and run.review_id == brand.original_review_id
            assert (
                attempt.fence == brand.original_fence
                and request.digest() == brand.original_request_digest
            )
            assert (
                request.intent.scope.workspace_id == wid
                and request.intent.scope.account.platform == brand.provider
            )
            assert (
                request.intent.mandate.mandate_id == brand.provider_mandate_id
                and request.intent.mandate.consent_id == brand.consent_id
            )
            assert (
                request.intent.mandate.ledger_id == brand.ledger_id
                and request.intent.mandate.revision == 1
            )
            assert (
                customer_intents.binding(db, wid, brand.provider_mandate_id, 1)
                == request.intent.mandate
            )
            policy_revision = one(
                "provider_execution_revisions", mandate_id=brand.provider_mandate_id, revision=1
            )
            consent = one("provider_execution_consents", id=brand.consent_id)
            assert policy_revision["actor"] == consent["actor"] == brand.actor_id
            assert policy_revision["workspace_id"] == consent["workspace_id"] == wid
            assert utc(policy_revision["created_at"]) == utc(consent["approved_at"]) == NOW
            assert (
                policy_revision["goal_id"] == brand.goal_id
                and policy_revision["goal_revision"] == 1
            )
            ledger_row = one("provider_period_ledgers", id=brand.ledger_id)
            assert utc(ledger_row["last_dispatch_at"]) == NOW
            assert run.state == "canceled" and run.canceled_at and utc(run.canceled_at) == NOW
            projection = optimization.read_owned_outcome_receipt(
                db, wid, attempt.id, brand.actor_id
            )
            assert projection and projection.outcome == "verified_target_state"
            receipt = db.get(ProviderExecutionReceipt, brand.original_receipt_id)
            assert (
                receipt
                and receipt.sequence == 1
                and receipt.supersedes_id is None
                and receipt.digest == brand.original_receipt_digest
            )
            assert receipt.projection == projection.model_dump(mode="json")
            response = db.get(
                ProviderExecutionResponse, (attempt.id, brand.original_response_digest)
            )
            assert response
            parsed = OptimizationResponse.model_validate(response.response)
            assert parsed.outcome == "acknowledged" and parsed.request_digest == request.digest()
            assert (
                fingerprint("inlet.optimization-response.v1", parsed.model_dump(mode="json"))
                == response.digest
            )
            if brand.provider == "google_ads":
                assert read_owned(db, wid, attempt.id, brand.actor_id, NOW) is not None
            repeat_row = db.get(ProviderExecutionReview, brand.repeat_review_id)
            assert repeat_row
            repeat = RepeatOptimizationReview.model_validate(repeat_row.document)
            assert repeat.digest() == repeat_row.digest == brand.repeat_review_digest
            assert repeat.plan.digest() == repeat_row.plan_digest
            for review_id, document in (
                (brand.original_review_id, review),
                (brand.repeat_review_id, repeat),
            ):
                approval = one("provider_execution_approvals", review_id=review_id)
                assert approval == dict(
                    review_id=review_id,
                    workspace_id=wid,
                    review_digest=document.digest(),
                    plan_digest=document.plan.digest(),
                    actor=brand.actor_id,
                    approved_at=approval["approved_at"],
                )
                assert utc(approval["approved_at"]) == NOW
            for run_id, state in (
                (brand.original_run_id, "verified_target_state"),
                (brand.successor_run_id, "pending"),
            ):
                step = one("provider_execution_steps", run_id=run_id)
                assert step == dict(
                    run_id=run_id, step_id="optimize", workspace_id=wid, ordinal=0, state=state
                )
            assert not any(
                r["run_id"] == brand.successor_run_id for r in rows["provider_execution_attempts"]
            )

            replacement = db.get(ProviderReservationReplacement, brand.replacement_id)
            assert replacement
            audit = ReplacementAuditDocument.model_validate(replacement.document)
            assert audit.digest() == replacement.digest == brand.replacement_digest
            assert (
                audit.predecessor_id,
                audit.successor_id,
                audit.successor_run_id,
                audit.review_id,
                audit.review_digest,
                audit.actor,
            ) == (
                brand.predecessor_reservation_id,
                brand.successor_reservation_id,
                brand.successor_run_id,
                brand.repeat_review_id,
                brand.repeat_review_digest,
                brand.actor_id,
            )
            assert audit.snapshot.receipts == [projection]
            assert replacement.old_amount_micros == replacement.new_amount_micros == 40_000_000
            assert isinstance(repeat.plan.intent.action, GoogleBudgetSetV1 | MetaBudgetSetV1)
            assert repeat.plan.intent.action.amount_micros == 44_000_000
            successor = one("provider_execution_runs", id=brand.successor_run_id)
            assert successor["state"] == "reserved" and successor["canceled_at"] is None
            assert successor["reservation_id"] == brand.successor_reservation_id
            for source in (brand.google_source, *(([brand.social.source]) if brand.social else [])):
                row = one("customer_campaign_revisions", draft_id=source.draft_id, revision=1)
                artifact = ReviewArtifact.model_validate(row["artifact"])
                assert artifact.fingerprint() == row["digest"] == source.digest
                assert artifact.workspace_id == wid and row["approved_by"] == brand.actor_id
            if brand.social:
                social = one("customer_social_configuration_reviews", id=brand.social.review_id)
                social_document = SocialConfigurationDocument.model_validate(social["document"])
                assert social_document.digest() == social["digest"] == brand.social.review_digest
                assert social_document.request.account == request.intent.scope
                assert social_document.primary == ScopedProviderMediaReader(
                    db, LocalMediaStore(media)
                ).binding(wid, brand.social.media_id)
                assert social_document.primary.sha256 == brand.social.media_sha256
                assert (
                    social_document.requirements.wording
                    == "Offline Test: Review This Exact No-DSA Configuration."
                )
                approval = one("customer_social_configuration_approvals", review_id=social["id"])
                stamp = dict(
                    review_id=social["id"],
                    workspace_id=wid,
                    review_digest=social["digest"],
                    actor=brand.actor_id,
                    confirmed_at=utc(approval["confirmed_at"]).isoformat(),
                )
                assert (
                    fingerprint("inlet.social-configuration-approval.v1", stamp)
                    == approval["digest"]
                    == brand.social.approval_digest
                )
    assert graph(engine) == rows
