"""Real native MockHTTP observations and scoped receipt rows, never invented DB tables."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from app.ads.models import AdvertisingAccount
from app.collectors import account_diagnostics
from app.collectors.native_diagnostics import AccountDiagnosticRequest
from app.customers.access import CustomerPrincipal
from app.customers.models import CustomerMembership, CustomerSession, CustomerUser
from app.meta.models import MetaConnection
from app.planning_documents import catalog_receipts as receipts
from app.planning_documents import input_resolution
from app.planning_documents.catalog_receipt_models import (
    CatalogReceiptRow,
    CatalogReceiptSelectionRow,
    InputCatalogReceiptRow,
)
from app.planning_documents.models import PlanInputRow, PlanRow
from app.planning_documents.read_context import PlanningReadContexts
from app.planning_documents.requests import CustomerInputs
from app.planning_documents.storage import canonical
from app.publication import customer_intents
from app.settings import Settings
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import Engine, delete, func, select
from sqlalchemy.orm import Session

from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_customer_identity import replicas as replicas
from tests.test_planning_evidence_adapter import setup_evidence
from tests.test_shopify_sales import configuration as configuration

pytestmark = pytest.mark.planning_boundary


def observe(engine: Engine, reader: Any, ticket: Any, principal: Any) -> Any:
    source = ticket.sources[0]
    reads = PlanningReadContexts(
        lambda: Session(engine),
        principal,
        reader.provider,
        ticket.inputs.workspace_id,
        ticket.actor_id,
    )
    with reads.open() as db:
        scope = customer_intents.account(db, ticket.inputs.workspace_id, source.account.account_id)
    request = AccountDiagnosticRequest(
        expected_account=scope,
        workspace_id=scope.workspace_id,
        actor=ticket.actor_id,
        account_id=source.account.account_id,
        starts_at=ticket.inputs.reporting_window.starts_at,
        ends_at=ticket.inputs.reporting_window.ends_at_exclusive,
    )
    with account_diagnostics.get_native_account_diagnostic_service(
        reads.open,
        reads.authorize,
        source.account.platform,
        reader.clock,
    ) as service:
        inventory, metadata = service.read_catalog(request, reader.clock())
    with Session(engine) as db:
        catalog = receipts.write_catalog_receipt(
            db,
            principal=principal,
            source=source,
            inventory=inventory,
            metadata=metadata,
            now=reader.clock(),
        )
        db.commit()
    return inventory, metadata, catalog


def intent_for(ticket: Any, catalog: Any, mode: str = "exclusion") -> CustomerInputs:
    target = catalog.targets[0]
    selector = dict(
        account_id=ticket.inputs.accounts[0].account_id,
        canonical_entity_key=target.canonical_entity_key,
        selection_key=target.selection_key,
    )
    return CustomerInputs(
        goal_id=ticket.inputs.goal.goal_id,
        goal_revision=ticket.inputs.goal.revision,
        account_ids=tuple(a.account_id for a in ticket.inputs.accounts),
        reporting_window=ticket.inputs.reporting_window,
        comparison_window=None,
        milestone=ticket.inputs.milestone,
        product_offer=None,
        constraints=(),
        assumptions=(),
        exclusions=(selector,) if mode == "exclusion" else (),
        fixed_allocations=(dict(target=selector, amount_micros=1),) if mode == "fixed" else (),
        scenario_intents=(
            dict(
                key="scenario-one",
                title="One",
                allocations=(dict(target=selector, amount_micros=1),),
                unallocated_micros=ticket.inputs.total_ceiling_micros - 1,
            ),
        )
        if mode == "scenario"
        else (),
    )


def save(engine: Engine, ticket: Any, principal: Any, intent: CustomerInputs) -> Any:
    with Session(engine) as db:
        resolved = receipts.resolve_input_catalogs(
            db,
            principal=principal,
            prepared=ticket.inputs,
            intent=intent,
            sources=ticket.sources,
            now=datetime.now(UTC),
        )
        inputs = input_resolution.resolve(ticket.inputs, intent, resolved.catalogs)
        db.add(
            PlanRow(
                workspace_id=inputs.workspace_id,
                id=inputs.plan_id,
                input_head=1,
                version_head=0,
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
                revision=inputs.revision,
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
        receipts.bind_input_receipts(
            db,
            principal=principal,
            resolved=receipts.ResolvedInputs(inputs=inputs, receipt_bindings=resolved.bindings),
            sources=ticket.sources,
            now=datetime.now(UTC),
        )
        db.commit()
    return ticket.model_copy(update={"inputs": inputs}), resolved


@pytest.mark.parametrize("platform", ["google_ads", "meta_ads", "tiktok_ads"])
@pytest.mark.parametrize("mode", ["exclusion", "fixed", "scenario"])
def test_actual_read_exact_saved_selection(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    platform: str,
    mode: str,
) -> None:
    reader, ticket, principal, calls = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, platform
    )
    inventory, metadata, first = observe(customer_engine, reader, ticket, principal)
    _, _, second = observe(customer_engine, reader, ticket, principal)
    assert first.targets[0].canonical_entity_key == second.targets[0].canonical_entity_key
    assert first.targets[0].selection_key != second.targets[0].selection_key
    ticket, resolved = save(customer_engine, ticket, principal, intent_for(ticket, first, mode))
    called = len(calls)
    with Session(customer_engine) as db:
        actual = receipts.resolve_saved_input_catalogs(
            db, principal=principal, ticket=ticket, now=datetime.now(UTC)
        )
        assert actual == resolved
        assert actual.catalogs[0].catalog == first
        receipts.recheck_saved_input_receipts(
            db, principal=principal, ticket=ticket, catalogs=actual.catalogs, now=datetime.now(UTC)
        )
        receipts.validate_retained_input_receipts(db, ticket.inputs)
        # Replaying the exact server observation does not create duplicate receipts.
        assert (
            receipts.write_catalog_receipt(
                db,
                principal=principal,
                source=ticket.sources[0],
                inventory=inventory,
                metadata=metadata,
                now=datetime.now(UTC),
            )
            == first
        )
        assert db.scalar(select(func.count()).select_from(CatalogReceiptRow)) == 2
    assert len(calls) == called


@pytest.mark.parametrize(
    "failure",
    [
        "missing",
        "canonical",
        "mixed",
        "window",
        "privacy",
        "session",
        "revoked",
        "role",
        "expired",
        "source",
        "actual_generation",
        "actual_currency",
    ],
)
def test_actual_receipt_refuses_changed_selection(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    reader, ticket, principal, _ = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, "meta_ads"
    )
    _, _, catalog = observe(customer_engine, reader, ticket, principal)
    intent = intent_for(ticket, catalog)
    now = datetime.now(UTC)
    if failure in {"missing", "canonical"}:
        field = "selection_key" if failure == "missing" else "canonical_entity_key"
        intent = intent.model_copy(
            update={"exclusions": (intent.exclusions[0].model_copy(update={field: "0" * 64}),)}
        )
    elif failure == "mixed":
        _, _, newer = observe(customer_engine, reader, ticket, principal)
        intent = intent.model_copy(
            update={"exclusions": (intent.exclusions[0], intent_for(ticket, newer).exclusions[0])}
        )
    elif failure == "window":
        window = ticket.inputs.reporting_window.model_copy(
            update={"starts_at": ticket.inputs.reporting_window.starts_at - timedelta(days=1)}
        )
        ticket = ticket.model_copy(
            update={"inputs": ticket.inputs.model_copy(update={"reporting_window": window})}
        )
    elif failure == "privacy":
        ticket = ticket.model_copy(
            update={
                "sources": (
                    ticket.sources[0].model_copy(
                        update={"privacy_revision": ticket.privacy_revision + 1}
                    ),
                )
            }
        )
    elif failure == "source":
        ticket = ticket.model_copy(
            update={
                "sources": (
                    ticket.sources[0].model_copy(update={"source_binding_digest": "0" * 64}),
                )
            }
        )
    elif failure == "expired":
        now = catalog.expires_at + timedelta(microseconds=1)
    with Session(customer_engine) as db:
        if failure == "actual_generation":
            connection = db.scalar(
                select(MetaConnection).where(
                    MetaConnection.account_id == ticket.inputs.accounts[0].account_id
                )
            )
            assert connection
            connection.generation += 1
            db.commit()
        if failure == "actual_currency":
            account = db.get(AdvertisingAccount, ticket.inputs.accounts[0].account_id)
            assert account
            account.currency_code = "CAD"
            db.commit()
        if failure == "session":
            old = principal.session
            other = CustomerSession(
                digest="f" * 64,
                user_id=principal.user.id,
                csrf_digest="e" * 64,
                created_at=old.created_at,
                expires_at=old.expires_at,
                authenticated_at=old.authenticated_at,
            )
            db.add(other)
            db.commit()
            principal = CustomerPrincipal(principal.user, other)
        if failure == "revoked":
            session = db.get(CustomerSession, principal.session.digest)
            assert session
            session.revoked_at = 1
            db.commit()
        if failure == "role":
            membership = db.get(CustomerMembership, (principal.user.id, ticket.inputs.workspace_id))
            assert membership
            membership.role = "viewer"
            db.commit()
        with pytest.raises((receipts.CatalogReceiptUnavailable, HTTPException)):
            receipts.resolve_input_catalogs(
                db,
                principal=principal,
                prepared=ticket.inputs,
                intent=intent,
                sources=ticket.sources,
                now=now,
            )
        assert db.scalar(select(func.count()).select_from(InputCatalogReceiptRow)) == 0


@pytest.mark.parametrize("missing", ["selection", "input_link"])
def test_complete_row_sets_and_historical_expiry(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    missing: str,
) -> None:
    reader, ticket, principal, _ = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, "meta_ads"
    )
    _, _, catalog = observe(customer_engine, reader, ticket, principal)
    ticket, _ = save(customer_engine, ticket, principal, intent_for(ticket, catalog))
    with Session(customer_engine) as db:
        assert (
            receipts.cleanup_expired_unused_receipts(
                db,
                workspace_id=ticket.inputs.workspace_id,
                now=catalog.expires_at + timedelta(days=1),
            )
            == 0
        )  # linked history remains
        receipts.validate_retained_input_receipts(db, ticket.inputs)
        with pytest.raises(receipts.CatalogReceiptUnavailable, match="expired"):
            receipts.resolve_saved_input_catalogs(
                db,
                principal=principal,
                ticket=ticket,
                now=catalog.expires_at + timedelta(seconds=1),
            )
        session = db.get(CustomerSession, principal.session.digest)
        assert session
        session.revoked_at = 1
        db.commit()
        receipts.validate_retained_input_receipts(db, ticket.inputs)  # no original auth callback
        table = CatalogReceiptSelectionRow if missing == "selection" else InputCatalogReceiptRow
        db.execute(delete(table))
        db.flush()
        with pytest.raises(receipts.CatalogReceiptUnavailable):
            receipts.validate_retained_input_receipts(db, ticket.inputs)


def test_scalar_and_nested_payload_tampering(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader, ticket, principal, _ = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, "meta_ads"
    )
    inventory, metadata, catalog = observe(customer_engine, reader, ticket, principal)
    wrong_source = ticket.sources[0].model_copy(
        update={
            "account": ticket.sources[0].account.model_copy(
                update={"connection_version": "different"}
            )
        }
    )
    with pytest.raises(receipts.CatalogReceiptUnavailable, match="integrity_unavailable"):
        receipts._evidence(catalog, wrong_source)
    unsafe = inventory.model_copy(
        update={"expires_at": metadata.observed_at - timedelta(seconds=1)}
    )
    with pytest.raises(ValidationError):
        receipts.ReceiptPayloadV1(inventory=unsafe, metadata=metadata)
    with Session(customer_engine) as db:
        row = db.scalar(select(CatalogReceiptRow))
        assert row
        db.expunge(row)  # simulate corrupt persisted scalar without disabling immutable triggers
        row.composite_digest = "0" * 64
        with pytest.raises(receipts.CatalogReceiptUnavailable, match="integrity_unavailable"):
            receipts.validate_retained_receipt(db, row)


def test_cleanup_commit_survives_later_quota_failure(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader, ticket, principal, _ = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, "meta_ads"
    )
    inventory, metadata, first = observe(customer_engine, reader, ticket, principal)
    _, _, second = observe(customer_engine, reader, ticket, principal)
    # Explicit injected maintenance clock; real observations and capacity enforcement.
    with Session(customer_engine) as db:
        assert (
            receipts.cleanup_expired_unused_receipts(
                db,
                workspace_id=ticket.inputs.workspace_id,
                now=second.expires_at + timedelta(seconds=1),
                limit=1,
            )
            == 1
        )
        db.commit()  # caller-owned maintenance transaction, not a helper side effect
    monkeypatch.setattr(receipts, "MAX_RECEIPTS", 1)
    with Session(customer_engine) as db:
        # Removed original observation now competes with the remaining receipt at capacity.
        # Its actual TTL is still live at the unmodified real clock for this insertion.
        with pytest.raises(receipts.CatalogReceiptUnavailable, match="capacity_exceeded"):
            receipts.write_catalog_receipt(
                db,
                principal=principal,
                source=ticket.sources[0],
                inventory=inventory,
                metadata=metadata,
                now=datetime.now(UTC),
            )
        db.rollback()
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(CatalogReceiptRow)) == 1
        assert db.scalar(select(CatalogReceiptRow.composite_digest)) != first.composite_digest


def test_final_expiry_after_wait_rolls_back_all_new_rows(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader, ticket, principal, _ = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, "meta_ads"
    )
    inventory, metadata, catalog = observe(customer_engine, reader, ticket, principal)
    with Session(customer_engine) as db:
        db.execute(delete(CatalogReceiptSelectionRow))
        db.execute(delete(CatalogReceiptRow))
        db.commit()
    original = receipts._fresh
    invocations = 0

    def delayed(*args: Any, **kwargs: Any) -> None:
        nonlocal invocations
        original(*args, **kwargs)
        invocations += 1
        if invocations == 2:
            # Model a clock crossing the original TTL during the final source-lock wait.
            monkeypatch.setattr(receipts, "database_utc_now", lambda db: catalog.expires_at)

    monkeypatch.setattr(receipts, "_fresh", delayed)
    with Session(customer_engine) as db:
        with pytest.raises(receipts.CatalogReceiptUnavailable, match="expired"):
            receipts.write_catalog_receipt(
                db,
                principal=principal,
                source=ticket.sources[0],
                inventory=inventory,
                metadata=metadata,
                now=datetime.now(UTC),
            )
        db.rollback()
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(CatalogReceiptRow)) == 0
        assert db.scalar(select(func.count()).select_from(CatalogReceiptSelectionRow)) == 0


def test_helpers_never_commit_or_call_provider(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader, ticket, principal, calls = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, "meta_ads"
    )
    inventory, metadata, catalog = observe(customer_engine, reader, ticket, principal)
    previous_calls = len(calls)

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("helper attempted external IO or transaction ownership")

    monkeypatch.setattr(reader.provider, "check_active", forbidden)
    with Session(customer_engine) as db:
        monkeypatch.setattr(db, "commit", forbidden)
        monkeypatch.setattr(db, "rollback", forbidden)
        receipts.write_catalog_receipt(
            db,
            principal=principal,
            source=ticket.sources[0],
            inventory=inventory,
            metadata=metadata,
            now=datetime.now(UTC),
        )
        receipts.resolve_input_catalogs(
            db,
            principal=principal,
            prepared=ticket.inputs,
            intent=intent_for(ticket, catalog),
            sources=ticket.sources,
            now=datetime.now(UTC),
        )
    assert len(calls) == previous_calls


@pytest.mark.parametrize("targeted", [False, True])
def test_current_owner_can_generate_other_owner_no_target_input_only(
    customer_engine: Engine,
    configuration: Settings,
    replicas: Any,
    monkeypatch: pytest.MonkeyPatch,
    targeted: bool,
) -> None:
    reader, ticket, principal, _ = setup_evidence(
        customer_engine, configuration, replicas, monkeypatch, "meta_ads"
    )
    _, _, catalog = observe(customer_engine, reader, ticket, principal)
    ticket, _ = save(
        customer_engine,
        ticket,
        principal,
        intent_for(ticket, catalog, "exclusion" if targeted else "none"),
    )
    with Session(customer_engine, expire_on_commit=False) as db:
        user = CustomerUser(
            id=uuid4().hex,
            issuer=principal.user.issuer,
            subject="second-" + uuid4().hex,
            email="second@example.test",
            status="active",
        )
        db.add(user)
        db.flush()
        session = CustomerSession(
            digest=uuid4().hex + uuid4().hex,
            user_id=user.id,
            csrf_digest=uuid4().hex + uuid4().hex,
            created_at=principal.session.created_at,
            expires_at=principal.session.expires_at,
            authenticated_at=principal.session.authenticated_at,
        )
        db.add(session)
        db.add(
            CustomerMembership(
                user_id=user.id,
                workspace_id=ticket.inputs.workspace_id,
                role="owner",
                status="active",
            )
        )
        db.commit()
        other = CustomerPrincipal(user, session)
    newer = ticket.model_copy(update={"actor_id": user.id, "session_digest": session.digest})
    with Session(customer_engine) as db:
        if targeted:
            with pytest.raises(
                receipts.CatalogReceiptUnavailable, match="original_session_changed"
            ):
                receipts.resolve_saved_input_catalogs(
                    db, principal=other, ticket=newer, now=datetime.now(UTC)
                )
        else:
            result = receipts.resolve_saved_input_catalogs(
                db, principal=other, ticket=newer, now=datetime.now(UTC)
            )
            assert result.catalogs == ()
            assert result.bindings == ()
