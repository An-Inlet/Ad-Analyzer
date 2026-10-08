"""Structural proof storage, not a runtime v2 handoff or qualification journey."""

import importlib
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.initial_planning.models import PreviewRow
from app.initial_planning.preview_v2 import InitialPreviewV2
from app.initial_planning.review_models import InitialPreviewReviewLink
from app.initial_planning.review_v2_contracts import InitialPreviewExecutionProofV1
from app.initial_planning.review_v2_models import InitialPreviewExecutionProofRow
from app.lifecycle.export_serializers import fields, serialize
from app.lifecycle.inventory import verify_registry
from app.lifecycle.registry import TABLES
from app.publication.execution_models import ProviderExecutionReview
from app.shopify.security import utc
from sqlalchemy import Engine, delete, insert, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from tests.retired_producer_fixture import retained_review_fixture
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_initial_preview_v2 import document
from tests.test_initial_review_v2_contracts import proof


def stored_proof(engine: Engine, prepared: Any) -> tuple[str, dict[str, Any]]:
    """Canonical typed storage parents, not an implemented v2 authorization journey."""
    from app.initial_planning.native_budget_contracts import NativeBudgetObservationV1
    from app.initial_planning.preview_v2 import PreviewIntentV2
    from app.initial_planning.review_v2_contracts import (
        InitialPreviewExecutionIntentV1,
        qualification_commitment,
    )
    from app.initial_planning.review_v2_projection import native_review_match
    from app.publication.optimization_contracts import MetaCurrentState
    from app.publication.replacement_contracts import parse_review

    with Session(engine) as db:
        old = db.get(InitialPreviewReviewLink, prepared.review_id)
        assert old and old.preview_id
        old_preview = db.get(PreviewRow, old.preview_id)
        old_review = db.get(ProviderExecutionReview, old.review_id)
        assert old_preview and old_review
        pid, rid = "7" * 32, "8" * 32
        financial_raw = dict(old_review.document)
        financial_raw["plan"] = {
            **financial_raw["plan"],
            "intent": {
                **financial_raw["plan"]["intent"],
                "rationale_reference": "7" * 64,
            },
        }
        financial = parse_review(financial_raw)
        current = financial.plan.before
        assert isinstance(current, MetaCurrentState)
        at = utc(old.created_at)
        end = min(utc(old.expires_at), at + timedelta(seconds=20))
        native = document().native_observation
        assert native is not None
        native_body = native.model_dump()
        native_body["request"].update(
            scope=current.scope.model_dump(),
            target=current.target.model_dump(),
            cohort=old_preview.document["objective"]["cohort"],
            goal_id=old_preview.document["objective"]["goal_id"],
            goal_revision=old_preview.document["objective"]["goal_revision"],
            goal_digest=old_preview.goal_digest,
        )
        for key in (
            "budget_owner",
            "account_status",
            "configured_status",
            "effective_status",
            "starts_at",
            "ends_at",
            "sharing_enabled",
            "schedule_adjustments_enabled",
            "rebalance_enabled",
            "unaffected_settings_digest",
        ):
            native_body[key] = current.model_dump()[key]
        native_body.update(
            amount_micros=old_preview.document["before_budget_micros"],
            observed_at=at,
            observation_started_at=at,
            expires_at=end,
        )
        native = NativeBudgetObservationV1.model_validate(native_body)
        raw_preview = {
            k: v for k, v in old_preview.document.items() if k in InitialPreviewV2.model_fields
        }
        raw_preview.update(
            id=pid,
            schema_version="inlet.initial-efficiency-preview.v2",
            environment=native.request.environment,
            profile_digest=native.request.profile_digest,
            native_observation=native.model_dump(mode="json"),
            created_at=at,
            expires_at=end,
            handoff_reason="initial_preview_native_read_unqualified",
            review_available=False,
        )
        native_preview = InitialPreviewV2.model_validate(raw_preview)
        execution = financial.plan.intent.mandate
        planning = {**execution.model_dump(), "mandate_id": "4" * 32, "consent_id": "5" * 32}
        saved_intent = PreviewIntentV2(
            objective=native_preview.objective,
            calibration_id=native_preview.calibration_id,
            observation_id=native_preview.observation_id,
            environment=native_preview.environment,
            profile_digest=native_preview.profile_digest,
            goal_digest=old_preview.goal_digest,
            native_option_id="6" * 64,
            mandate_id=planning["mandate_id"],
            mandate_revision=planning["revision"],
        )
        handoff = InitialPreviewExecutionIntentV1(
            expected_preview_digest=native_preview.digest(),
            mandate_id=execution.mandate_id,
            mandate_revision=execution.revision,
        )
        preview_row = {c.name: getattr(old_preview, c.name) for c in PreviewRow.__table__.columns}
        preview_row.update(
            id=pid,
            document=native_preview.model_dump(mode="json"),
            document_digest=native_preview.digest(),
            intent=saved_intent.model_dump(mode="json"),
            mandate_digest=planning["policy_digest"],
            native_state_digest=None,
            created_at=at,
            expires_at=end,
        )
        db.execute(insert(PreviewRow).values(**preview_row))
        review_row = {
            c.name: getattr(old_review, c.name) for c in ProviderExecutionReview.__table__.columns
        }
        review_row.update(
            id=rid,
            initial_preview_origin_id=pid,
            digest=financial.digest(),
            document=financial.model_dump(mode="json"),
            plan_digest=financial.plan.digest(),
        )
        db.execute(insert(ProviderExecutionReview).values(**review_row))
        link = {c.name: getattr(old, c.name) for c in InitialPreviewReviewLink.__table__.columns}
        link.update(
            review_id=rid,
            preview_id=pid,
            preview_digest=native_preview.digest(),
            review_digest=financial.digest(),
            plan_digest=financial.plan.digest(),
            intent_digest=handoff.digest(),
            mandate_digest=execution.policy_digest,
        )
        db.execute(insert(InitialPreviewReviewLink).values(**link))
        value = proof().model_dump()
        value.update(
            workspace_id=old.workspace_id,
            preview_id=pid,
            review_id=rid,
            preview_digest=native_preview.digest(),
            profile_digest=native_preview.profile_digest,
            qualified_state_digest=link["native_state_digest"],
            plan_digest=link["plan_digest"],
            created_at=at,
            expires_at=end,
            native_observation_digest=native.digest(),
            planning_mandate=planning,
            execution_mandate=execution.model_dump(),
            intent_digest=handoff.digest(),
            qualification_digest=qualification_commitment(financial.plan.qualification),
            semantic_match_digest=native_review_match(native, current).digest(),
        )
        typed = InitialPreviewExecutionProofV1.model_validate(value)
        row = dict(
            review_id=rid,
            workspace_id=old.workspace_id,
            digest=typed.digest(),
            document=typed.model_dump(mode="json"),
        )
        db.commit()
        return pid, row


@pytest.mark.parametrize("migration", [False, True])
def test_storage_owned_binding_erasure_and_populated_migration(
    customer_engine: Engine,
    tmp_path: Path,
    migration: bool,
) -> None:
    with retained_review_fixture(customer_engine, tmp_path / "seed") as (engine, prepared):
        _storage_owned_binding(engine, prepared, migration)


def _storage_owned_binding(customer_engine: Engine, prepared: Any, migration: bool) -> None:
    mod = importlib.import_module("migrations.versions.20261007_0081_initial_execution_proof")
    wid = prepared.workspace_id
    if migration:
        with customer_engine.begin() as conn, Operations.context(MigrationContext.configure(conn)):
            mod.downgrade()
            mod.upgrade()
    pid, row = stored_proof(customer_engine, prepared)
    with Session(customer_engine) as db:
        for key, value in (("workspace_id", wid + 1), ("review_id", "f" * 32)):
            with pytest.raises(DBAPIError), db.begin_nested():
                db.execute(insert(InitialPreviewExecutionProofRow).values(**{**row, key: value}))
        for key in ("preview_digest", "plan_digest", "qualified_state_digest", "profile_digest"):
            bad = {**row["document"], key: "0" * 64}
            with pytest.raises(DBAPIError), db.begin_nested():
                db.execute(
                    insert(InitialPreviewExecutionProofRow).values(**{**row, "document": bad})
                )
        for path, replacement in (
            (("intent_digest",), "0" * 64),
            (("execution_mandate", "policy_digest"), "0" * 64),
            (("execution_mandate", "consent_id"), "0" * 32),
            (("planning_mandate", "policy_digest"), "0" * 64),
            (("planning_mandate", "mandate_id"), "0" * 32),
            (("planning_mandate", "revision"), 999),
        ):
            bad_document = deepcopy(row["document"])
            if len(path) == 1:
                bad_document[path[0]] = replacement
            else:
                bad_document[path[0]][path[1]] = replacement
            bad_proof = InitialPreviewExecutionProofV1.model_validate(bad_document)
            bad_row = {
                **row,
                "document": bad_proof.model_dump(mode="json"),
                "digest": bad_proof.digest(),
            }
            # Valid schema and recomputed hash cannot mask different parent commitments.
            with pytest.raises(DBAPIError), db.begin_nested():
                db.execute(insert(InitialPreviewExecutionProofRow).values(**bad_row))
            with pytest.raises(ValueError), db.begin_nested():
                db.add(InitialPreviewExecutionProofRow(**bad_row))
                db.flush()
        for key in ("qualification_digest", "semantic_match_digest"):
            contradicted = InitialPreviewExecutionProofV1.model_validate(
                {**row["document"], key: "0" * 64}
            )
            bad = {
                **row,
                "document": contradicted.model_dump(mode="json"),
                "digest": contradicted.digest(),
            }
            with pytest.raises(ValueError, match="commitment mismatch"), db.begin_nested():
                db.add(InitialPreviewExecutionProofRow(**bad))
                db.flush()
        for bad in (
            {**row, "digest": "0" * 64},
            {**row, "document": {**row["document"], "native_observation_digest": "0" * 64}},
        ):
            with pytest.raises(ValueError), db.begin_nested():
                db.add(InitialPreviewExecutionProofRow(**bad))
                db.flush()
        db.add(InitialPreviewExecutionProofRow(**row))
        db.commit()
        verify_registry()
        assert TABLES["initial_preview_execution_proofs"].protected
        savepoint = db.begin_nested()
        db.execute(
            delete(InitialPreviewReviewLink).where(
                InitialPreviewReviewLink.review_id == row["review_id"]
            )
        )
        assert db.scalar(select(InitialPreviewExecutionProofRow)) is None
        assert db.get(ProviderExecutionReview, row["review_id"])
        savepoint.rollback()
        result, missing = serialize("initial_preview_execution_proofs", row)
        assert not missing and "session" not in repr(result)
        with pytest.raises(DBAPIError), db.begin_nested():
            db.execute(update(InitialPreviewExecutionProofRow).values(digest="0" * 64))
        db.rollback()
    with (
        customer_engine.begin() as conn,
        Operations.context(MigrationContext.configure(conn)),
        pytest.raises(RuntimeError, match="retained"),
    ):
        mod.downgrade()
    with Session(customer_engine) as db:
        db.execute(delete(PreviewRow).where(PreviewRow.id == pid))
        db.commit()
        link = db.get(InitialPreviewReviewLink, row["review_id"])
        assert link and link.preview_id is None
        db.execute(delete(InitialPreviewExecutionProofRow))
        db.commit()
        with pytest.raises(DBAPIError), db.begin_nested():
            db.execute(insert(InitialPreviewExecutionProofRow).values(**row))
        db.rollback()
        assert db.get(ProviderExecutionReview, row["review_id"])
        db.execute(
            delete(InitialPreviewReviewLink).where(
                InitialPreviewReviewLink.review_id == row["review_id"]
            )
        )
        db.commit()
        assert db.scalar(select(InitialPreviewExecutionProofRow)) is None
        assert db.get(ProviderExecutionReview, prepared.review_id)
    assert prepared.provider_posts == 1  # Genuine historical effect; current tests add no attempts.


@pytest.mark.parametrize("change", ["digest", "workspace", "review", "extra", "missing", "large"])
def test_strict_proof_export(change: str) -> None:
    value = proof()
    row: dict[str, Any] = dict(
        review_id=value.review_id,
        workspace_id=value.workspace_id,
        digest=value.digest(),
        document=value.model_dump(mode="json"),
    )
    if change == "digest":
        row["digest"] = "0" * 64
    if change == "workspace":
        row["workspace_id"] = 999
    if change == "review":
        row["review_id"] = "f" * 32
    if change == "extra":
        row["document"]["original_session_digest"] = "never-export"
    if change == "missing":
        del row["document"]["plan_digest"]
    if change == "large":
        row["document"]["payload"] = "x" * 20000
    result, missing = serialize("initial_preview_execution_proofs", row)
    assert result == {} and set(missing) == set(fields("initial_preview_execution_proofs"))


def test_frozen_migration_matches_metadata_guards_and_graph() -> None:
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from app.initial_planning.review_v2_triggers import statements

    migration = importlib.import_module("migrations.versions.20261007_0081_initial_execution_proof")
    scripts = ScriptDirectory.from_config(Config("alembic.ini"))
    assert scripts.get_revision("20261007_0081").down_revision == "20261007_0080"
    assert "20261007_0081" in {r.revision for r in scripts.walk_revisions()}
    for dialect in ("sqlite", "postgresql"):
        assert migration.SQL[dialect] == statements(dialect)
