"""Fail-closed pure input guards; these rows grant no execution authority."""

from copy import deepcopy
from typing import Any

import pytest
from scripts.inlet_restore_bootstrap import expected_bootstrap

from tests.provider_ddl_boundary import QUAL, ZERO, before_phase
from tests.provider_ddl_retained_fixture import validate_output


def guard_rows() -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    ids = dict(
        workspace_id=2,
        actor_id="a" * 32,
        simulation_mandate_id="b" * 32,
        goal_id="c" * 32,
        goal_revision=1,
        account_id=1,
        native_connection_id="d" * 32,
        source_draft_id="e" * 32,
        source_draft_revision=1,
        source_draft_digest="f" * 64,
        provider_policy_digest="a" * 64,
    )
    rows = expected_bootstrap()
    rows["workspaces"].append(dict(id=2))
    rows.update({name: [] for name in ZERO | QUAL})
    rows.update(
        {
            name: []
            for name in (
                "provider_execution_mandates",
                "provider_execution_revisions",
                "provider_execution_consents",
                "provider_period_ledgers",
            )
        }
    )
    rows["customer_users"] = [dict(id=ids["actor_id"])]
    rows["customer_memberships"] = [
        dict(
            user_id=ids["actor_id"],
            workspace_id=2,
            role="owner",
            status="active",
        )
    ]
    rows["customer_campaign_revisions"] = [
        dict(
            draft_id=ids["source_draft_id"],
            revision=1,
            workspace_id=2,
            digest=ids["source_draft_digest"],
            approved_by=ids["actor_id"],
        )
    ]
    return rows, ids


@pytest.mark.parametrize("change", [None, "extra", "bootstrap", "metadata", "schema"])
def test_bootstrap_is_exact_and_migration_only(change: str | None) -> None:
    rows, ids = guard_rows()
    schema = "inlet_migration_fixture_" + "a" * 32
    if change == "extra":
        rows["workspaces"].append(dict(id=3))
    elif change == "bootstrap":
        rows["workspace_configurations"][0]["automation"] = {"live_writes_enabled": True}
    elif change == "metadata":
        schema = "inlet_test_" + "a" * 32
    elif change == "schema":
        schema = "public"
    if change is None:
        before_phase(rows, ids, "qualification_only", None, schema)
    else:
        with pytest.raises(AssertionError):
            before_phase(rows, ids, "qualification_only", None, schema)


@pytest.mark.parametrize(
    "field,value",
    [
        ("workspace_id", True),
        ("revision", 2),
        ("actor_id", "bad"),
        ("provider_policy_digest", "a" * 32),
        ("extra", 1),
    ],
)
def test_consent_scalar_boundary_rejects_unsafe_output(field: str, value: Any) -> None:
    raw = dict(
        mode="execution_consent",
        workspace_id=2,
        actor_id="a" * 32,
        provider_mandate_id="b" * 32,
        revision=1,
        provider_policy_digest="c" * 64,
        provider_consent_id="d" * 32,
        ledger_id="e" * 32,
    )
    valid = deepcopy(raw)
    validate_output(valid, "execution_consent")
    raw[field] = value
    with pytest.raises(AssertionError):
        validate_output(raw, "execution_consent")


@pytest.mark.parametrize(
    "query",
    [
        "sslmode=require",
        "options=-csearch_path=public",
        "options=-csearch_path=inlet_test_" + "a" * 32,
    ],
)
def test_unapproved_engine_query_rejected_before_database_io(
    monkeypatch: pytest.MonkeyPatch,
    query: str,
) -> None:
    from pathlib import Path
    from types import SimpleNamespace
    from unittest.mock import Mock

    from sqlalchemy import Engine
    from sqlalchemy.engine import make_url

    from tests import provider_ddl_boundary as boundary

    base = "postgresql+psycopg://postgres@127.0.0.1:55432/inlet_test_ci"
    monkeypatch.setattr(boundary, "validate_disposable_url", lambda: base)
    engine = Mock(spec=Engine)
    engine.dialect = SimpleNamespace(name="postgresql")
    engine.url = make_url(base + "?" + query)
    with pytest.raises(AssertionError):
        boundary.owned(engine, "qualification_only", Path(__file__).resolve().parents[1])
    engine.connect.assert_not_called()


@pytest.mark.parametrize(
    "table,column",
    [
        ("provider_qualifications", "observed_at"),
        ("provider_qualifications", "expires_at"),
        ("provider_reviews", "created_at"),
        ("provider_review_approvals", "approved_at"),
        ("provider_reviews", "unexpected"),
    ],
)
def test_exact_new_row_validation_rejects_copied_timestamp_or_extra_column(
    table: str,
    column: str,
) -> None:
    from datetime import timedelta

    from app.publication.google_compiler import compile_google
    from app.publication.google_qualification import qualify_google
    from app.publication.provider_contracts import ProviderPublicationReview

    from tests.financial_origin_retained_fixture import SourceIds
    from tests.provider_ddl_retained_fixture import (
        QualificationIds,
        checked_qualification_rows,
        qualification_rows,
    )
    from tests.test_commerce_measurement import NOW
    from tests.test_provider_publication_contracts import review
    from tests.test_provider_qualification import adapter, ctx, response_rows

    r = review()
    evidence = qualify_google(r, ctx(r), adapter(response_rows()), NOW)
    value = r.model_dump()
    value.update(qualification=evidence.model_dump(), qualification_blockers=[])
    plan = compile_google(ProviderPublicationReview.model_validate(value))
    source = SourceIds(
        workspace_id=r.scope.workspace_id,
        actor_id="a" * 32,
        simulation_mandate_id=r.scope.mandate_id,
        goal_id="c" * 32,
        goal_revision=1,
        account_id=r.scope.account.account_id,
        native_connection_id="d" * 32,
        source_draft_id=r.source.draft_id,
        source_draft_revision=1,
        source_draft_digest=r.source.fingerprint(),
        provider_policy_digest="e" * 64,
    )
    result = QualificationIds(
        "qualification_approved",
        source.workspace_id,
        source.actor_id,
        source.source_draft_id,
        1,
        "f" * 32,
        "b" * 32,
        plan.review.digest(),
        plan.digest(),
    )
    rows = qualification_rows(source, result, plan, True)
    checked_qualification_rows(rows, source, result, plan, True)
    changed = deepcopy(rows)
    changed[table][0][column] = NOW + timedelta(seconds=1)
    with pytest.raises(AssertionError):
        checked_qualification_rows(changed, source, result, plan, True)
