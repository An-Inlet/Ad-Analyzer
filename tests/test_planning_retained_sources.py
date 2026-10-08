"""Persist real collected/composed versions and verify all local proof rows on both DBs."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from app.ads.models import Campaign, DailyMetric
from app.campaign_performance.models import CurrentPerformance, PerformanceCompletion
from app.commerce.models import CommerceEntry, CommerceStore
from app.customers.models import CustomerMembership, CustomerSession
from app.meta.models import MetaConnection
from app.planning_documents.composer import (
    GENERATOR_VERSION,
    POLICY_VERSION,
    DescriptivePlanComposer,
)
from app.planning_documents.evidence_local import recheck_local_sources
from app.planning_documents.models import PlanDependencyRow, PlanInputRow, PlanRow, PlanVersionRow
from app.planning_documents.ports import PlanningCompositionPolicy
from app.planning_documents.retained_sources import (
    RetainedSourcesChanged,
    capture_retained_sources,
    recheck_retained_sources,
)
from app.planning_documents.storage import canonical
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_planning_evidence_adapter import setup_evidence
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


def prepare(
    engine: Engine,
    config: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    platform: str = "meta_ads",
    missing: str | None = None,
) -> Any:
    reader, ticket, principal, calls = setup_evidence(
        engine, config, replicas, monkeypatch, platform
    )
    policy = PlanningCompositionPolicy(version=POLICY_VERSION, generator_version=GENERATOR_VERSION)
    reader.policy = policy
    ticket = ticket.model_copy(
        update={"policy_version": policy.version, "policy_digest": policy.digest()}
    )
    with Session(engine) as db:
        current = db.get(CurrentPerformance, ticket.inputs.accounts[0].account_id)
        assert current
        original_completion = current.completion_id
        if missing == "absent":
            db.delete(current)
            db.commit()
    if missing == "mismatch":
        old = ticket.inputs.reporting_window
        window = old.model_copy(
            update={
                "starts_at": old.starts_at - timedelta(days=1),
                "ends_at_exclusive": old.ends_at_exclusive - timedelta(days=1),
            }
        )
        ticket = ticket.model_copy(
            update={"inputs": ticket.inputs.model_copy(update={"reporting_window": window})}
        )
    bundle = reader.collect(ticket)
    document = DescriptivePlanComposer().compose(
        inputs=ticket.inputs,
        evidence=bundle,
        policy=policy,
        version=1,
        parent_digest=None,
        generated_by=ticket.actor_id,
        generated_at=datetime.now(UTC),
    )
    inputs = document.inputs
    with Session(engine) as db:
        recheck_local_sources(
            db, principal=principal, ticket=ticket, bundle=bundle, now=datetime.now(UTC)
        )
        witnesses = capture_retained_sources(
            db, principal=principal, document=document, now=datetime.now(UTC)
        )
        db.add(
            PlanRow(
                workspace_id=inputs.workspace_id,
                id=inputs.plan_id,
                input_head=1,
                version_head=1,
                event_sequence=0,
                created_by=inputs.created_by,
                created_at=inputs.created_at,
            )
        )
        db.flush()
        db.add(
            PlanInputRow(
                workspace_id=inputs.workspace_id,
                plan_id=inputs.plan_id,
                revision=1,
                goal_id=inputs.goal.goal_id,
                goal_revision=inputs.goal.revision,
                confirmed_preview_id=inputs.goal.confirmation_reference,
                definition_digest=inputs.goal.definition_digest,
                canonical_json=canonical(inputs),
                digest=inputs.digest(),
                actor_id=inputs.created_by,
                created_at=inputs.created_at,
            )
        )
        db.flush()
        db.add(
            PlanVersionRow(
                workspace_id=inputs.workspace_id,
                plan_id=inputs.plan_id,
                version=1,
                input_revision=1,
                parent_digest=None,
                canonical_json=canonical(document),
                digest=document.digest(),
                generator_version=document.generator_version,
                policy_version=document.policy_version,
                actor_id=document.generated_by,
                generated_at=document.generated_at,
                valid_until=document.valid_until,
                privacy_revision=ticket.privacy_revision,
            )
        )
        db.flush()
        for ref in document.evidence:
            db.add(
                PlanDependencyRow(
                    workspace_id=inputs.workspace_id,
                    plan_id=inputs.plan_id,
                    version=1,
                    evidence_key=ref.key,
                    account_id=ref.account.account_id if ref.account else None,
                    connection_id=ref.account.connection_id if ref.account else None,
                    store_id=inputs.goal.definition.store_id
                    if ref.kind == "shopify_measurement"
                    else None,
                    kind=ref.kind,
                    source_binding_digest=ref.source_binding_digest,
                    document_digest=ref.document_digest,
                    source_revision=ref.source_revision,
                    observed_at=ref.observed_at,
                    expires_at=ref.expires_at,
                    privacy_revision=ref.privacy_revision,
                )
            )
        for witness in witnesses:
            db.add(PlanDependencyRow(**witness.model_dump()))
        db.commit()
    return reader, document, principal, calls, original_completion


def dependencies(db: Session, document: Any) -> list[PlanDependencyRow]:
    return list(
        db.scalars(
            select(PlanDependencyRow).where(
                PlanDependencyRow.workspace_id == document.inputs.workspace_id,
                PlanDependencyRow.plan_id == document.inputs.plan_id,
                PlanDependencyRow.version == document.version,
            )
        )
    )


@pytest.mark.parametrize("platform", ["google_ads", "meta_ads", "tiktok_ads"])
def test_viewer_local_read_preserves_current_without_provider_io(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    platform: str,
) -> None:
    reader, doc, principal, calls, _ = prepare(
        customer_engine, configuration, replicas, monkeypatch, platform
    )
    with Session(customer_engine) as db:
        member = db.get(CustomerMembership, (principal.user.id, doc.inputs.workspace_id))
        assert member
        member.role = "viewer"
        db.commit()
    original_calls = len(calls)

    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("retained verification made provider IO")

    monkeypatch.setattr(reader.provider, "check_active", forbidden)
    with Session(customer_engine) as db:
        rows = dependencies(db, doc)
        assert len(rows) == len(doc.evidence) + 2
        from app.planning_documents.storage import export_row

        for row in rows:
            if row.kind.startswith("local_"):
                exported = export_row(
                    "planning_document_dependencies",
                    {c.name: getattr(row, c.name) for c in PlanDependencyRow.__table__.columns},
                )
                assert exported["kind"] == row.kind
                assert exported["document_digest"] == row.document_digest
        recheck_retained_sources(
            db, principal=principal, document=doc, dependencies=rows, now=datetime.now(UTC)
        )
    assert len(calls) == original_calls


@pytest.mark.parametrize(
    "change",
    [
        "metric",
        "mapping",
        "generation",
        "commerce",
        "commerce_amount",
        "import",
        "capacity",
        "watermark",
        "privacy",
        "legacy",
        "missing",
        "extra",
        "duplicate",
        "ordinary",
        "session",
        "expiry",
    ],
)
def test_changed_or_incomplete_local_proof_never_current(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    _, doc, principal, _, _ = prepare(customer_engine, configuration, replicas, monkeypatch)
    account_id = doc.inputs.accounts[0].account_id
    with Session(customer_engine) as db:
        row: Any
        if change == "metric":
            campaign = db.scalar(select(Campaign).where(Campaign.account_id == account_id))
            assert campaign
            row = db.scalar(select(DailyMetric).where(DailyMetric.campaign_id == campaign.id))
            assert row
            row.clicks += 1
        elif change == "mapping":
            row = db.scalar(select(Campaign).where(Campaign.account_id == account_id))
            assert row
            row.external_campaign_id = "999"
        elif change == "generation":
            row = db.scalar(select(MetaConnection).where(MetaConnection.account_id == account_id))
            assert row
            row.generation += 1
        elif change == "commerce_amount":
            row = db.scalar(
                select(CommerceEntry).where(
                    CommerceEntry.store_id == doc.inputs.goal.definition.store_id,
                    CommerceEntry.net_micros < 0,
                )
            )
            assert row
            row.net_micros += 1
        elif change == "import":
            row = db.get(CommerceStore, doc.inputs.goal.definition.store_id)
            assert row
            row.window_end = datetime.now(UTC)
        elif change == "capacity":
            monkeypatch.setattr("app.planning_documents.retained_sources.MAX_LOCAL_CAMPAIGNS", 0)
        elif change in {"commerce", "watermark"}:
            row = db.get(CommerceStore, doc.inputs.goal.definition.store_id)
            assert row
            if change == "commerce":
                row.revision += 1
            else:
                row.last_sync_at = datetime.now(UTC)
        elif change == "privacy":
            from app.lifecycle.privacy import advance_workspace_export_revision

            advance_workspace_export_revision(db, doc.inputs.workspace_id)
        elif change in {"legacy", "missing", "ordinary"}:
            rows = dependencies(db, doc)
            selected = (
                [r for r in rows if r.kind.startswith("local_")]
                if change != "ordinary"
                else [r for r in rows if r.kind == "native_catalog"]
            )
            for row in selected if change == "legacy" else selected[:1]:
                db.delete(row)
        elif change == "extra":
            row = dependencies(db, doc)[0]
            values = {c.name: getattr(row, c.name) for c in PlanDependencyRow.__table__.columns}
            values["evidence_key"] = "local:extra"
            db.add(PlanDependencyRow(**values))
        elif change == "session":
            row = db.get(CustomerSession, principal.session.digest)
            assert row
            row.revoked_at = 1
        db.commit()
    with Session(customer_engine) as db:
        rows = dependencies(db, doc)
        if change == "duplicate":
            rows.append(rows[-1])
        with pytest.raises(HTTPException if change == "session" else RetainedSourcesChanged):
            recheck_retained_sources(
                db,
                principal=principal,
                document=doc,
                dependencies=rows,
                now=datetime.now(UTC)
                + (timedelta(minutes=6) if change == "expiry" else timedelta()),
            )


@pytest.mark.parametrize("missing", ["absent", "mismatch", "matching"])
def test_missing_and_mismatch_reporting_pins_survive_persistence(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    missing: str,
) -> None:
    _, doc, principal, _, completion_id = prepare(
        customer_engine,
        configuration,
        replicas,
        monkeypatch,
        missing="mismatch" if missing == "matching" else missing,
    )
    account_id = doc.inputs.accounts[0].account_id
    with Session(customer_engine) as db:
        recheck_retained_sources(
            db,
            principal=principal,
            document=doc,
            dependencies=dependencies(db, doc),
            now=datetime.now(UTC),
        )
    with Session(customer_engine) as db:
        if missing == "absent":
            db.add(
                CurrentPerformance(
                    account_id=account_id,
                    workspace_id=doc.inputs.workspace_id,
                    completion_id=completion_id,
                )
            )
        elif missing == "matching":
            from app.ads.models import AdvertisingAccount
            from app.campaign_performance.service import manifest

            completion = db.get(PerformanceCompletion, completion_id)
            assert completion
            completion.starts_on = doc.inputs.reporting_window.starts_at.date()
            completion.ends_on = completion.starts_on
            source = db.scalar(
                select(MetaConnection).where(MetaConnection.account_id == account_id)
            )
            assert source
            source.covered_from = source.covered_through = completion.starts_on
            account = db.get(AdvertisingAccount, account_id)
            assert account
            completion.manifest_digest, rows = manifest(
                db, account, completion.starts_on, completion.ends_on
            )
            completion.row_count = len(rows)
        else:
            completion = db.get(PerformanceCompletion, completion_id)
            assert completion
            fields = {
                c.name: getattr(completion, c.name) for c in PerformanceCompletion.__table__.columns
            }
            fields["id"] = uuid4().hex
            db.add(PerformanceCompletion(**fields))
            db.flush()
            current = db.get(CurrentPerformance, account_id)
            assert current
            current.completion_id = fields["id"]
        db.commit()
    with Session(customer_engine) as db, pytest.raises(RetainedSourcesChanged):
        recheck_retained_sources(
            db,
            principal=principal,
            document=doc,
            dependencies=dependencies(db, doc),
            now=datetime.now(UTC),
        )
