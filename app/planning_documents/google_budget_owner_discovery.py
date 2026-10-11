"""Original-receipt discovery; no provider reads, writes, or receipt renewal."""

from datetime import UTC

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.customers.access import CustomerPrincipal
from app.planning_documents.catalog_evidence import CatalogEvidence
from app.planning_documents.catalog_receipt_models import CatalogReceiptRow
from app.planning_documents.catalog_receipts import CatalogReceiptUnavailable, _load
from app.planning_documents.context import AccountRef
from app.planning_documents.evidence_local import resolve_source_fences
from app.planning_documents.google_budget_owner_contracts import (
    GoogleBudgetOwnerUnavailable,
    GoogleDailyBudgetOwnerWitnessV1,
    _catalog,
    derive_google_daily_budget_owner,
    owner_facts_digest,
)
from app.planning_documents.google_budget_owner_discovery_contracts import (
    GoogleBudgetOwnerOptionV1,
    GoogleBudgetOwnersRequestV1,
    GoogleBudgetOwnersViewV1,
)
from app.planning_documents.google_budget_owner_selection import original_owner_selection_id
from app.planning_documents.policy_capabilities import ticket_reporting_capability
from app.planning_documents.read_context import PlanningReadContexts
from app.planning_documents.service import PlanningDocumentService
from app.planning_documents.source_contracts import SourceFence
from app.publication import customer_intents


def owner_selection_id(
    *, principal: CustomerPrincipal, source: SourceFence, witness: GoogleDailyBudgetOwnerWitnessV1
) -> str:
    return original_owner_selection_id(
        actor_id=principal.user.id,
        session_digest=principal.session.digest,
        authenticated_at=principal.session.authenticated_at,
        source=source,
        witness=witness,
    )


def _options(
    evidence: CatalogEvidence,
    principal: CustomerPrincipal,
    source: SourceFence,
    intent: GoogleBudgetOwnersRequestV1,
) -> GoogleBudgetOwnersViewV1:
    try:
        evidence = _catalog(evidence)
        native = evidence.catalog.native_observation
        options = []
        for key in sorted(
            {
                t.budget_owner_key
                for t in native.targets
                if t.kind == "campaign" and t.budget_owner_key is not None
            }
        ):
            try:
                witness = derive_google_daily_budget_owner(evidence, key)
            except GoogleBudgetOwnerUnavailable:
                continue
            ref = evidence.reference
            options.append(
                GoogleBudgetOwnerOptionV1(
                    account_id=intent.account_id,
                    owner_selection_id=owner_selection_id(
                        principal=principal, source=source, witness=witness
                    ),
                    expected_observation_digest=witness.digest(),
                    expected_owner_facts_digest=owner_facts_digest(witness),
                    representative=witness.representative,
                    affected_campaigns=witness.affected_campaigns,
                    current_amount_micros=witness.current_amount_micros,
                    currency=witness.currency,
                    observation_started_at=ref.observation_started_at,
                    observed_at=ref.observed_at,
                    expires_at=ref.expires_at,
                )
            )
            if len(options) > 20:
                raise ValueError("owner response exceeds count bound")
        result = GoogleBudgetOwnersViewV1(
            account_id=intent.account_id,
            status="available" if options else "unavailable",
            owners=tuple(options),
            reason=None if options else "google_budget_owner_unavailable",
        )
        return result
    except ValueError as error:
        raise CatalogReceiptUnavailable("integrity_unavailable") from error


def read_google_budget_owners(
    configured: PlanningDocumentService,
    principal: CustomerPrincipal,
    workspace_id: int,
    intent: GoogleBudgetOwnersRequestV1,
) -> GoogleBudgetOwnersViewV1:
    intent = GoogleBudgetOwnersRequestV1.model_validate(intent)
    reads = PlanningReadContexts(
        lambda: Session(configured.engine),
        principal,
        configured.provider,
        workspace_id,
        principal.user.id,
    )
    try:
        with reads.open() as db:
            capability = ticket_reporting_capability(
                configured.policy.version, configured.policy.digest()
            )
            if capability.mode != "creative_selected_requested_window":
                raise HTTPException(
                    409, "Google budget owner discovery is unavailable for this planning policy."
                )
            scope = customer_intents.account(db, workspace_id, intent.account_id)
            account = AccountRef(
                workspace_id=workspace_id,
                account_id=intent.account_id,
                connection_id=scope.account.connection_id,
                platform=scope.account.platform,
                connection_version=scope.connection_version,
            )
            source = resolve_source_fences(
                db, principal=principal, accounts=(account,), now=configured.clock()
            )[0]
            receipt_id = db.scalar(
                select(CatalogReceiptRow.id).where(
                    CatalogReceiptRow.workspace_id == workspace_id,
                    CatalogReceiptRow.account_id == intent.account_id,
                    CatalogReceiptRow.actor_id == principal.user.id,
                    CatalogReceiptRow.session_digest == principal.session.digest,
                    CatalogReceiptRow.composite_digest == intent.catalog_composite_digest,
                )
            )
            if receipt_id is None:
                raise CatalogReceiptUnavailable("missing")
            _, evidence = _load(
                db,
                principal=principal,
                receipt_id=receipt_id,
                source=source,
                window=intent.reporting_window,
                now=configured.clock(),
            )
            expected = (
                intent.reporting_window.starts_at.astimezone(UTC),
                intent.reporting_window.ends_at_exclusive.astimezone(UTC),
            )
            native, metadata = (
                evidence.catalog.native_observation,
                evidence.catalog.metadata_observation,
            )
            window = evidence.reference.reporting_window
            assert window is not None
            for starts, ends in (
                (window.starts_at, window.ends_at_exclusive),
                (native.reporting_starts_at, native.reporting_ends_at),
                (metadata.reporting_starts_at, metadata.reporting_ends_at),
            ):
                if (starts.astimezone(UTC), ends.astimezone(UTC)) != expected:
                    raise CatalogReceiptUnavailable("selection_mismatch")
            result = _options(evidence, principal, source, intent)
            if resolve_source_fences(
                db, principal=principal, accounts=(account,), now=configured.clock()
            ) != (source,):
                raise CatalogReceiptUnavailable("source_changed")
            _, final = _load(
                db,
                principal=principal,
                receipt_id=receipt_id,
                source=source,
                window=intent.reporting_window,
                now=configured.clock(),
            )
            if (
                final.model_dump_json() != evidence.model_dump_json()
                or configured.clock().astimezone(UTC) >= evidence.catalog.expires_at.astimezone(UTC)
            ):
                raise CatalogReceiptUnavailable("expired")
            if resolve_source_fences(
                db, principal=principal, accounts=(account,), now=configured.clock()
            ) != (source,):
                raise CatalogReceiptUnavailable("source_changed")
            if configured.clock().astimezone(UTC) >= evidence.catalog.expires_at.astimezone(UTC):
                raise CatalogReceiptUnavailable("expired")
            reads.authorize(db, workspace_id, principal.user.id)
        now = configured.clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("aware discovery clock required")
        if now.astimezone(UTC) >= evidence.catalog.expires_at.astimezone(UTC):
            raise CatalogReceiptUnavailable("expired")
        return result
    except CatalogReceiptUnavailable as error:
        raise HTTPException(
            409, "This budget owner receipt is unavailable. Read fresh targets and review again."
        ) from error
