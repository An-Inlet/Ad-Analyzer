"""Actual acquired receipts/media/reporting; standalone V6 composition and SQL storage.

No V6 service registration or generation guard override. Input admission is the real
HTTP path; the standalone composer/reader and retained ports are called directly.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from app.customers.access import SESSION_COOKIE, CustomerPrincipal, digest
from app.customers.models import CustomerSession, CustomerUser
from app.lifecycle.privacy import workspace_export_revision
from app.planning_documents import authority
from app.planning_documents.context import PlanInputRevision
from app.planning_documents.creative_paired_reader import OwnedCreativePairedReader
from app.planning_documents.evidence_local import resolve_source_fences
from app.planning_documents.google_budget_owner_retained import (
    capture_owner_review_retained_sources,
)
from app.planning_documents.models import PlanDependencyRow, PlanRow, PlanVersionRow
from app.planning_documents.owner_review_plan_composer import OwnerReviewPlanComposer
from app.planning_documents.owner_review_policy import (
    OWNER_REVIEW_GENERATOR_VERSION,
    OWNER_REVIEW_POLICY_VERSION,
)
from app.planning_documents.ports import GenerationTicket, PlanningCompositionPolicy
from app.planning_documents.storage import canonical
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.google_budget_input_fixture import ready_inputs
from tests.test_customer_optimization_api import headers


def stored(
    engine: Engine,
    config: Any,
    replicas: Any,
    patch: pytest.MonkeyPatch,
    path: Path,
    *,
    empty: bool = False,
) -> Any:
    fixture, body, calls, _ = ready_inputs(engine, config, replicas, patch, path)
    alice, _, provider = replicas
    if empty:
        body["inputs"]["google_daily_budget_intents"] = []
        body["inputs"]["scenario_intents"] = []
    wid = fixture.basis.workspace_id
    response = alice.post(
        f"/api/customer/v1/workspaces/{wid}/planning/plans", headers=headers(alice), json=body
    )
    assert response.status_code == 201, response.text
    inputs = PlanInputRevision.model_validate(response.json()["inputs"])
    with Session(engine) as db:
        session = db.get(CustomerSession, digest(alice.cookies[SESSION_COOKIE]))
        assert session is not None
        user = db.get(CustomerUser, session.user_id)
        assert user is not None
        db.expunge_all()
        principal = CustomerPrincipal(user, session)
    policy = PlanningCompositionPolicy(
        version=OWNER_REVIEW_POLICY_VERSION, generator_version=OWNER_REVIEW_GENERATOR_VERSION
    )
    fact = authority.refresh(principal, provider)
    with Session(engine) as db, db.begin():
        current = authority.lock(db, principal, wid, fact)
        ticket = GenerationTicket(
            operation_id=uuid4().hex,
            actor_id=current.user.id,
            session_digest=current.session.digest,
            inputs=inputs,
            expected_version=0,
            expected_parent_digest=None,
            privacy_revision=workspace_export_revision(db, wid),
            sources=resolve_source_fences(
                db, principal=current, accounts=inputs.accounts, now=datetime.now(UTC)
            ),
            policy_version=policy.version,
            policy_digest=policy.digest(),
            prepared_at=datetime.now(UTC),
        )
        authority.final(current, fact)
    reader = OwnedCreativePairedReader(
        lambda: Session(engine),
        principal=principal,
        provider=provider,
        policy=policy,
        store=fixture.store,
        clock=lambda: datetime.now(UTC),
    )
    packet = reader.collect(ticket)
    document = OwnerReviewPlanComposer().compose(
        ticket=ticket, evidence=packet, policy=policy, generated_at=datetime.now(UTC)
    )
    with Session(engine) as db, db.begin():
        witnesses = capture_owner_review_retained_sources(
            db, principal=principal, document=document, now=datetime.now(UTC)
        )
        dependencies = [
            PlanDependencyRow(
                workspace_id=wid,
                plan_id=inputs.plan_id,
                version=document.version,
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
            for ref in document.evidence
        ]
        dependencies.extend(PlanDependencyRow(**w.model_dump()) for w in witnesses)
        plan = db.get(PlanRow, (wid, inputs.plan_id))
        assert plan is not None
        plan.version_head = document.version
        db.add(
            PlanVersionRow(
                workspace_id=wid,
                plan_id=inputs.plan_id,
                version=document.version,
                input_revision=inputs.revision,
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
        db.add_all(dependencies)
    return document, principal, fixture, calls
