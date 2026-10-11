"""Exact short-lived catalog selections. Callers own fresh authority and transactions.

No provider IO, commit, rollback, or lifetime extension occurs in these helpers.
Cleanup must run in its own caller-committed maintenance transaction before native IO.
"""

from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from fastapi import HTTPException
from pydantic import (
    Field,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.ads.models import AdvertisingAccount
from app.billing.entitlements import paid_work
from app.collectors.native_diagnostics import Inventory
from app.customers.access import CustomerPrincipal
from app.customers.models import CustomerSession
from app.lifecycle.privacy import database_utc_now, workspace_export_revision
from app.planning_catalog.metadata_binding import validate_bound_metadata
from app.planning_catalog.metadata_contracts import PlanningMetadataV1, TargetCatalogV2
from app.planning_catalog.projection_v2 import project_v2
from app.planning_documents.catalog_receipt_models import (
    CatalogReceiptRow,
    CatalogReceiptSelectionRow,
    InputCatalogReceiptRow,
)
from app.planning_documents.common import Digest, Frozen, Id, Positive, fingerprint
from app.planning_documents.composer import targets
from app.planning_documents.context import EvidenceRef, PlanInputRevision, ReportingWindow
from app.planning_documents.evidence_local import resolve_source_fences
from app.planning_documents.google_budget_intents import ResolvedGoogleDailyBudgetIntentV1
from app.planning_documents.google_budget_owner_contracts import GoogleBudgetOwnerUnavailable
from app.planning_documents.models import PlanInputRow
from app.planning_documents.ports import CatalogEvidence, GenerationTicket, SourceFence
from app.planning_documents.requests import CustomerInputs
from app.planning_documents.storage import canonical, document_for_row
from app.publication import customer_intents
from app.shopify.security import utc

MAX_RECEIPTS = 1000
MAX_PAYLOAD_BYTES = 64 * 1024 * 1024
MAX_UNUSED_ACTIVE = 40
Reason = Literal[
    "missing",
    "expired",
    "selection_mismatch",
    "source_changed",
    "original_session_changed",
    "integrity_unavailable",
    "capacity_exceeded",
]


class CatalogReceiptUnavailable(Exception):
    def __init__(self, reason: Reason) -> None:
        self.reason = reason
        super().__init__(reason)


class ReceiptPayloadV1(Frozen):
    schema_version: Literal["inlet.planning-catalog-receipt.v1"] = (
        "inlet.planning-catalog-receipt.v1"
    )
    inventory: Inventory
    metadata: PlanningMetadataV1

    @field_validator("inventory", mode="before")
    @classmethod
    def reparse_inventory(cls, value: Any) -> Any:
        return value.model_dump(mode="python") if hasattr(value, "model_dump") else value

    @model_validator(mode="after")
    def bound(self) -> "ReceiptPayloadV1":
        if getattr(self.inventory.request, "purpose", None) != "account_diagnostics":
            raise ValueError("owned account diagnostic observation required")
        # Replay validates original chronology; current expiry is checked separately.
        validate_bound_metadata(self.inventory, self.metadata, self.metadata.observed_at)
        return self


class ReceiptBindingV1(Frozen):
    receipt_id: Id
    workspace_id: Positive
    account_id: Positive
    connection_id: Positive
    composite_digest: Digest
    input_digest: Digest
    selected_keys_digest: Digest
    selected_count: int = Field(strict=True, ge=1, le=400)


class ResolvedInputs(Frozen):
    inputs: PlanInputRevision
    receipt_bindings: tuple[ReceiptBindingV1, ...] = Field(max_length=20)

    @model_validator(mode="after")
    def bound(self) -> "ResolvedInputs":
        _binding_shape(self.inputs, self.receipt_bindings)
        return self


class ResolvedInputCatalogs(Frozen):
    owner_intents: tuple[ResolvedGoogleDailyBudgetIntentV1, ...] | None = Field(
        default=None, max_length=20
    )

    @model_serializer(mode="wrap")
    def serialize_owners(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        value: dict[str, Any] = handler(self)
        if self.owner_intents is None:
            value.pop("owner_intents", None)
        return value

    catalogs: tuple[CatalogEvidence, ...] = Field(max_length=20)
    bindings: tuple[ReceiptBindingV1, ...] = Field(max_length=20)

    @model_validator(mode="after")
    def bound(self) -> "ResolvedInputCatalogs":
        ids = [b.account_id for b in self.bindings]
        if ids != sorted(set(ids)) or len(self.catalogs) != len(ids):
            raise ValueError("exact ordered catalog bindings required")
        for catalog, binding in zip(self.catalogs, self.bindings, strict=True):
            ref = catalog.reference
            if ref.account is None or (
                ref.workspace_id,
                ref.account.account_id,
                ref.account.connection_id,
                catalog.catalog.composite_digest,
            ) != (
                binding.workspace_id,
                binding.account_id,
                binding.connection_id,
                binding.composite_digest,
            ):
                raise ValueError("catalog binding mismatch")
        return self


def _binding_shape(inputs: PlanInputRevision, bindings: tuple[ReceiptBindingV1, ...]) -> None:
    ids = [b.account_id for b in bindings]
    accounts = {a.account_id: a for a in inputs.accounts}
    if ids != sorted(set(ids)) or any(
        b.workspace_id != inputs.workspace_id
        or b.input_digest != inputs.digest()
        or b.account_id not in accounts
        or accounts[b.account_id].connection_id != b.connection_id
        for b in bindings
    ):
        raise ValueError("input receipt binding mismatch")


def _now(db: Session, now: datetime) -> datetime:
    return max(utc(now), database_utc_now(db))


def _fresh(
    db: Session,
    principal: CustomerPrincipal,
    sources: tuple[SourceFence, ...],
    now: datetime,
) -> None:
    if not sources:
        return
    if len({s.account.workspace_id for s in sources}) != 1:
        raise CatalogReceiptUnavailable("source_changed")
    current = resolve_source_fences(
        db,
        principal=principal,
        accounts=tuple(s.account for s in sources),
        now=_now(db, now),
    )
    if {s.account.account_id: s for s in current} != {s.account.account_id: s for s in sources}:
        raise CatalogReceiptUnavailable("source_changed")
    # Resample after source/authority lock waits; detached originals are provenance only.
    final = _now(db, now)
    session = db.get(CustomerSession, principal.session.digest, populate_existing=True)
    if (
        session is None
        or session.authenticated_at != principal.session.authenticated_at
        or (session.expires_at <= final.timestamp())
    ):
        raise HTTPException(401, "customer authentication required")
    paid_work(db, sources[0].account.workspace_id, final)


def _currency(db: Session, payload: ReceiptPayloadV1) -> None:
    request = payload.inventory.request
    account = db.get(AdvertisingAccount, request.account.account.account_id, populate_existing=True)
    if account is None or (account.currency_code, account.time_zone) != (
        request.currency,
        request.time_zone,
    ):
        raise CatalogReceiptUnavailable("source_changed")


def _evidence(catalog: TargetCatalogV2, source: SourceFence) -> CatalogEvidence:
    try:
        return _evidence_document(catalog, source)
    except ValueError as exc:
        raise CatalogReceiptUnavailable("integrity_unavailable") from exc


def _evidence_document(catalog: TargetCatalogV2, source: SourceFence) -> CatalogEvidence:
    native, metadata = catalog.native_observation, catalog.metadata_observation
    complete = all(c.status == "complete" for c in native.coverage) and all(
        c.status == "complete" for c in metadata.coverage
    )
    return CatalogEvidence(
        catalog=catalog,
        reference=EvidenceRef(
            key=f"catalog:{source.account.account_id}",
            workspace_id=source.account.workspace_id,
            kind="native_catalog",
            account=source.account,
            document_schema=catalog.schema_version,
            document_digest=catalog.composite_digest,
            source_binding_digest=metadata.source_binding_digest,
            source_revision=source.source_revision,
            privacy_revision=source.privacy_revision,
            reporting_window=ReportingWindow(
                starts_at=metadata.reporting_starts_at,
                ends_at_exclusive=metadata.reporting_ends_at,
            ),
            observation_started_at=min(
                native.observation_started_at, metadata.observation_started_at
            ),
            observed_at=max(native.observed_at, metadata.observed_at),
            expires_at=catalog.expires_at,
            coverage="complete_in_declared_scope" if complete else "partial",
            declared_scope="Native inventory with separately declared provider coverage.",
            reasons=() if complete else ("limited_native_coverage",),
            metric_basis="Native settings, not performance or spending authority.",
        ),
    )


def _payload(row: CatalogReceiptRow) -> tuple[ReceiptPayloadV1, TargetCatalogV2]:
    try:
        if not 0 < len(row.canonical_json.encode()) <= 1048576:
            raise ValueError("payload bound")
        payload = ReceiptPayloadV1.model_validate_json(row.canonical_json)
        catalog = project_v2(payload.inventory, payload.metadata)
        native, metadata = catalog.native_observation, catalog.metadata_observation
        expected = dict(
            payload_schema=payload.schema_version,
            payload_digest=payload.digest(),
            canonical_json=canonical(payload),
            payload_bytes=len(row.canonical_json.encode()),
            workspace_id=native.workspace_id,
            account_id=native.account_id,
            connection_id=native.connection_id,
            source_revision=native.connection_version,
            source_binding_digest=native.source_binding_digest,
            composite_digest=catalog.composite_digest,
            target_count=len(catalog.targets),
        )
        if (
            any(getattr(row, key) != value for key, value in expected.items())
            or (
                utc(row.reporting_starts_at),
                utc(row.reporting_ends_at),
                utc(row.observation_started_at),
                utc(row.observed_at),
                utc(row.expires_at),
            )
            != (
                utc(metadata.reporting_starts_at),
                utc(metadata.reporting_ends_at),
                min(utc(native.observation_started_at), utc(metadata.observation_started_at)),
                max(utc(native.observed_at), utc(metadata.observed_at)),
                utc(catalog.expires_at),
            )
            or not utc(row.observed_at) <= utc(row.created_at) < utc(row.expires_at)
        ):
            raise ValueError("receipt scalar mismatch")
        return payload, catalog
    except (ValueError, TypeError) as exc:
        raise CatalogReceiptUnavailable("integrity_unavailable") from exc


def validate_retained_receipt(
    db: Session,
    row: CatalogReceiptRow,
) -> tuple[ReceiptPayloadV1, TargetCatalogV2]:
    """Historical structural proof only; caller owns current read/privacy authorization."""
    payload, catalog = _payload(row)
    selections = db.scalars(
        select(CatalogReceiptSelectionRow)
        .where(
            CatalogReceiptSelectionRow.workspace_id == row.workspace_id,
            CatalogReceiptSelectionRow.receipt_id == row.id,
        )
        .limit(401)
        .execution_options(populate_existing=True)
    ).all()
    expected = {(t.canonical_entity_key, t.selection_key) for t in catalog.targets}
    if (
        len(selections) != len(expected)
        or any(
            (s.account_id, s.connection_id) != (row.account_id, row.connection_id)
            for s in selections
        )
        or {(s.canonical_entity_key, s.selection_key) for s in selections} != expected
    ):
        raise CatalogReceiptUnavailable("integrity_unavailable")
    return payload, catalog


def _load(
    db: Session,
    *,
    principal: CustomerPrincipal,
    receipt_id: str,
    source: SourceFence,
    window: ReportingWindow | None,
    now: datetime,
) -> tuple[CatalogReceiptRow, CatalogEvidence]:
    row = db.scalar(
        select(CatalogReceiptRow)
        .where(
            CatalogReceiptRow.workspace_id == source.account.workspace_id,
            CatalogReceiptRow.id == receipt_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise CatalogReceiptUnavailable("missing")
    if (row.actor_id, row.session_digest, row.authenticated_at) != (
        principal.user.id,
        principal.session.digest,
        principal.session.authenticated_at,
    ):
        raise CatalogReceiptUnavailable("original_session_changed")
    if (
        row.account_id,
        row.connection_id,
        row.source_revision,
        row.source_binding_digest,
        row.privacy_revision,
    ) != (
        source.account.account_id,
        source.account.connection_id,
        source.source_revision,
        source.source_binding_digest,
        source.privacy_revision,
    ):
        raise CatalogReceiptUnavailable("source_changed")
    payload, catalog = validate_retained_receipt(db, row)
    scope = customer_intents.account(db, row.workspace_id, row.account_id)
    if payload.inventory.request.account != scope:
        raise CatalogReceiptUnavailable("source_changed")
    _currency(db, payload)
    evidence = _evidence(catalog, source)
    if window is not None and evidence.reference.reporting_window != window:
        raise CatalogReceiptUnavailable("selection_mismatch")
    if _now(db, now) >= catalog.expires_at:
        raise CatalogReceiptUnavailable("expired")
    return row, evidence


def write_catalog_receipt(
    db: Session,
    *,
    principal: CustomerPrincipal,
    source: SourceFence,
    inventory: Inventory,
    metadata: PlanningMetadataV1,
    now: datetime,
) -> TargetCatalogV2:
    source = SourceFence.model_validate(source)
    _fresh(db, principal, (source,), now)
    payload = ReceiptPayloadV1.model_validate(
        {"inventory": inventory.model_dump(), "metadata": metadata.model_dump()}
    )
    catalog = project_v2(payload.inventory, payload.metadata)
    scope = customer_intents.account(db, source.account.workspace_id, source.account.account_id)
    if payload.inventory.request.account != scope or (
        metadata.workspace_id,
        metadata.account_id,
        metadata.connection_id,
        metadata.connection_version,
        metadata.source_binding_digest,
    ) != (
        source.account.workspace_id,
        source.account.account_id,
        source.account.connection_id,
        source.source_revision,
        source.source_binding_digest,
    ):
        raise CatalogReceiptUnavailable("source_changed")
    _currency(db, payload)
    current = _now(db, now)
    if current >= catalog.expires_at:
        raise CatalogReceiptUnavailable("expired")
    try:
        raw = canonical(payload)
    except ValueError as exc:
        # canonical() owns the unchanged shared byte bound. Do not mislabel other
        # serialization/validation failures as ordinary capacity exhaustion.
        reason: Reason = (
            "capacity_exceeded"
            if str(exc) == "planning document exceeds bound"
            else "integrity_unavailable"
        )
        raise CatalogReceiptUnavailable(reason) from exc
    existing = db.scalar(
        select(CatalogReceiptRow).where(
            CatalogReceiptRow.workspace_id == source.account.workspace_id,
            CatalogReceiptRow.actor_id == principal.user.id,
            CatalogReceiptRow.session_digest == principal.session.digest,
            CatalogReceiptRow.account_id == source.account.account_id,
            CatalogReceiptRow.composite_digest == catalog.composite_digest,
        )
    )
    if existing is not None:
        row, evidence = _load(
            db, principal=principal, receipt_id=existing.id, source=source, window=None, now=now
        )
        if row.canonical_json != raw:
            raise CatalogReceiptUnavailable("integrity_unavailable")
        _fresh(db, principal, (source,), now)
        _unexpired(db, [(row, evidence)], now)
        return evidence.catalog
    count, size = db.execute(
        select(func.count(), func.coalesce(func.sum(CatalogReceiptRow.payload_bytes), 0)).where(
            CatalogReceiptRow.workspace_id == source.account.workspace_id,
        )
    ).one()
    linked = (
        select(InputCatalogReceiptRow.receipt_id)
        .where(
            InputCatalogReceiptRow.workspace_id == CatalogReceiptRow.workspace_id,
            InputCatalogReceiptRow.receipt_id == CatalogReceiptRow.id,
        )
        .exists()
    )
    active = db.scalar(
        select(func.count())
        .select_from(CatalogReceiptRow)
        .where(
            CatalogReceiptRow.workspace_id == source.account.workspace_id,
            CatalogReceiptRow.actor_id == principal.user.id,
            CatalogReceiptRow.account_id == source.account.account_id,
            CatalogReceiptRow.expires_at > current,
            ~linked,
        )
    )
    if (
        count >= MAX_RECEIPTS
        or size + len(raw.encode()) > MAX_PAYLOAD_BYTES
        or (active is not None and active >= MAX_UNUSED_ACTIVE)
    ):
        raise CatalogReceiptUnavailable("capacity_exceeded")
    keys = [t.selection_key for t in catalog.targets]
    if (
        keys
        and db.scalar(
            select(CatalogReceiptSelectionRow.selection_key)
            .where(
                CatalogReceiptSelectionRow.workspace_id == source.account.workspace_id,
                CatalogReceiptSelectionRow.account_id == source.account.account_id,
                CatalogReceiptSelectionRow.selection_key.in_(keys),
            )
            .limit(1)
        )
        is not None
    ):
        raise CatalogReceiptUnavailable("selection_mismatch")
    native = catalog.native_observation
    row = CatalogReceiptRow(
        workspace_id=source.account.workspace_id,
        id=uuid4().hex,
        account_id=source.account.account_id,
        connection_id=source.account.connection_id,
        actor_id=principal.user.id,
        session_digest=principal.session.digest,
        authenticated_at=principal.session.authenticated_at,
        privacy_revision=source.privacy_revision,
        source_revision=source.source_revision,
        source_binding_digest=source.source_binding_digest,
        payload_schema=payload.schema_version,
        canonical_json=raw,
        payload_digest=payload.digest(),
        payload_bytes=len(raw.encode()),
        composite_digest=catalog.composite_digest,
        target_count=len(catalog.targets),
        # SQL scalar timestamps are UTC instants on both dialects; SQLite drops
        # offsets rather than converting them. Keep canonical payload bytes intact.
        reporting_starts_at=utc(metadata.reporting_starts_at),
        reporting_ends_at=utc(metadata.reporting_ends_at),
        observation_started_at=min(
            utc(native.observation_started_at), utc(metadata.observation_started_at)
        ),
        observed_at=max(utc(native.observed_at), utc(metadata.observed_at)),
        expires_at=utc(catalog.expires_at),
        created_at=utc(current),
    )
    db.add(row)
    db.flush()
    for target in catalog.targets:
        db.add(
            CatalogReceiptSelectionRow(
                workspace_id=row.workspace_id,
                account_id=row.account_id,
                receipt_id=row.id,
                connection_id=row.connection_id,
                canonical_entity_key=target.canonical_entity_key,
                selection_key=target.selection_key,
            )
        )
    db.flush()
    _fresh(db, principal, (source,), now)
    _load(db, principal=principal, receipt_id=row.id, source=source, window=None, now=now)
    return catalog


def _selected_digest(keys: set[tuple[str, str]]) -> str:
    return fingerprint("inlet.planning-receipt-selected-keys.v1", {"keys": sorted(keys)})


def _bindings(
    inputs: PlanInputRevision,
    loaded: list[tuple[CatalogReceiptRow, CatalogEvidence]],
) -> tuple[ReceiptBindingV1, ...]:
    all_targets = [t for _, catalog in loaded for t in targets(catalog)]
    used: dict[int, set[tuple[str, str]]] = {}
    chosen = [a.target for a in inputs.fixed_allocations] + [
        a.target for s in inputs.scenario_intents for a in s.allocations
    ]
    for key in inputs.excluded_entity_keys:
        matches = [t for t in all_targets if t.canonical_entity_key == key]
        if len(matches) != 1:
            raise CatalogReceiptUnavailable("selection_mismatch")
        chosen.append(matches[0])
    for target in chosen:
        if target not in all_targets:
            raise CatalogReceiptUnavailable("selection_mismatch")
        used.setdefault(target.account.account_id, set()).add(
            (target.canonical_entity_key, target.selection_key)
        )
    if set(used) != {row.account_id for row, _ in loaded}:
        raise CatalogReceiptUnavailable("selection_mismatch")
    return tuple(
        ReceiptBindingV1(
            receipt_id=row.id,
            workspace_id=inputs.workspace_id,
            account_id=row.account_id,
            connection_id=row.connection_id,
            composite_digest=catalog.catalog.composite_digest,
            input_digest=inputs.digest(),
            selected_keys_digest=_selected_digest(used[row.account_id]),
            selected_count=len(used[row.account_id]),
        )
        for row, catalog in loaded
    )


def resolve_input_catalogs(
    db: Session,
    *,
    principal: CustomerPrincipal,
    prepared: PlanInputRevision,
    intent: CustomerInputs,
    sources: tuple[SourceFence, ...],
    now: datetime,
) -> ResolvedInputCatalogs:
    prepared = PlanInputRevision.model_validate(prepared)
    intent = CustomerInputs.model_validate(intent)
    if prepared.created_by != principal.user.id:
        raise CatalogReceiptUnavailable("original_session_changed")
    _check_sources(db, principal, prepared, sources, now)
    selectors = (
        *intent.exclusions,
        *(a.target for a in intent.fixed_allocations),
        *(a.target for s in intent.scenario_intents for a in s.allocations),
    )
    by_account: dict[int, str] = {}
    fences = {s.account.account_id: s for s in sources}
    for selector in selectors:
        if selector.account_id not in fences:
            raise CatalogReceiptUnavailable("selection_mismatch")
        link = db.get(
            CatalogReceiptSelectionRow,
            (
                prepared.workspace_id,
                selector.account_id,
                selector.selection_key,
            ),
            populate_existing=True,
        )
        if link is None:
            raise CatalogReceiptUnavailable("missing")
        if link.canonical_entity_key != selector.canonical_entity_key or (
            selector.account_id in by_account and by_account[selector.account_id] != link.receipt_id
        ):
            raise CatalogReceiptUnavailable("selection_mismatch")
        by_account[selector.account_id] = link.receipt_id
    loaded = [
        _load(
            db,
            principal=principal,
            receipt_id=by_account[aid],
            source=fences[aid],
            window=prepared.reporting_window,
            now=now,
        )
        for aid in sorted(by_account)
    ]
    catalogs = tuple(c for _, c in loaded)
    from app.planning_documents.google_budget_input_resolution import (
        resolve_google_daily_budget_inputs,
    )
    from app.planning_documents.input_resolution import _resolve_ordinary, resolve

    owner_intents = None
    if intent.google_daily_budget_intents is not None:
        ordinary = _resolve_ordinary(prepared, intent, catalogs)
        try:
            owner_intents = resolve_google_daily_budget_inputs(
                inputs=ordinary,
                intents=intent.google_daily_budget_intents,
                catalogs=catalogs,
                sources=sources,
                principal=principal,
                privacy_revision=workspace_export_revision(db, prepared.workspace_id),
            )
        except (ValueError, GoogleBudgetOwnerUnavailable) as error:
            raise CatalogReceiptUnavailable("selection_mismatch") from error
    inputs = resolve(prepared, intent, catalogs, owner_intents=owner_intents)
    bindings = _bindings(inputs, loaded)
    _check_sources(db, principal, inputs, sources, now)
    _unexpired(db, loaded, now)
    return ResolvedInputCatalogs(catalogs=catalogs, bindings=bindings, owner_intents=owner_intents)


def _check_sources(
    db: Session,
    principal: CustomerPrincipal,
    inputs: PlanInputRevision,
    sources: tuple[SourceFence, ...],
    now: datetime,
) -> None:
    if len(sources) != len(inputs.accounts) or {s.account for s in sources} != set(inputs.accounts):
        raise CatalogReceiptUnavailable("source_changed")
    _fresh(db, principal, sources, now)


def _unexpired(
    db: Session,
    loaded: list[tuple[CatalogReceiptRow, CatalogEvidence]],
    now: datetime,
) -> None:
    if any(_now(db, now) >= c.reference.expires_at for _, c in loaded):
        raise CatalogReceiptUnavailable("expired")


def bind_input_receipts(
    db: Session,
    *,
    principal: CustomerPrincipal,
    resolved: ResolvedInputs,
    sources: tuple[SourceFence, ...],
    now: datetime,
) -> None:
    resolved = ResolvedInputs.model_validate(resolved)
    inputs = resolved.inputs
    if inputs.created_by != principal.user.id:
        raise CatalogReceiptUnavailable("original_session_changed")
    _check_sources(db, principal, inputs, sources, now)
    _saved_input(db, inputs)
    fences = {s.account.account_id: s for s in sources}
    loaded = [
        _load(
            db,
            principal=principal,
            receipt_id=b.receipt_id,
            source=fences[b.account_id],
            window=inputs.reporting_window,
            now=now,
        )
        for b in resolved.receipt_bindings
    ]
    _check_current_owner_receipts(
        inputs, loaded, sources, workspace_export_revision(db, inputs.workspace_id)
    )
    if _bindings(inputs, loaded) != resolved.receipt_bindings:
        raise CatalogReceiptUnavailable("selection_mismatch")
    existing = _input_links(db, inputs)
    if existing:
        raise CatalogReceiptUnavailable("selection_mismatch")
    for binding in resolved.receipt_bindings:
        db.add(
            InputCatalogReceiptRow(
                **binding.model_dump(),
                plan_id=inputs.plan_id,
                input_revision=inputs.revision,
                created_at=_now(db, now),
            )
        )
    db.flush()
    _check_sources(db, principal, inputs, sources, now)
    _unexpired(db, loaded, now)


def _saved_input(db: Session, inputs: PlanInputRevision) -> None:
    row = db.get(
        PlanInputRow, (inputs.workspace_id, inputs.plan_id, inputs.revision), populate_existing=True
    )
    if row is None:
        raise CatalogReceiptUnavailable("missing")
    try:
        document = document_for_row(
            PlanInputRow.__tablename__,
            {col.name: getattr(row, col.name) for col in PlanInputRow.__table__.columns},
        )
        if document != inputs:
            raise ValueError("input changed")
    except (ValueError, TypeError) as exc:
        raise CatalogReceiptUnavailable("integrity_unavailable") from exc


def _input_links(db: Session, inputs: PlanInputRevision) -> list[InputCatalogReceiptRow]:
    return list(
        db.scalars(
            select(InputCatalogReceiptRow)
            .where(
                InputCatalogReceiptRow.workspace_id == inputs.workspace_id,
                InputCatalogReceiptRow.plan_id == inputs.plan_id,
                InputCatalogReceiptRow.input_revision == inputs.revision,
            )
            .order_by(InputCatalogReceiptRow.account_id)
            .limit(21)
            .execution_options(populate_existing=True)
        ).all()
    )


def resolve_saved_input_catalogs(
    db: Session,
    *,
    principal: CustomerPrincipal,
    ticket: GenerationTicket,
    now: datetime,
) -> ResolvedInputCatalogs:
    ticket = GenerationTicket.model_validate(ticket)
    if (ticket.actor_id, ticket.session_digest) != (principal.user.id, principal.session.digest):
        raise CatalogReceiptUnavailable("original_session_changed")
    inputs = ticket.inputs
    _check_sources(db, principal, inputs, ticket.sources, now)
    _saved_input(db, inputs)
    links = _input_links(db, inputs)
    if links and inputs.created_by != principal.user.id:
        raise CatalogReceiptUnavailable("original_session_changed")
    if len(links) > 20:
        raise CatalogReceiptUnavailable("integrity_unavailable")
    fences = {s.account.account_id: s for s in ticket.sources}
    if any(link.account_id not in fences for link in links):
        raise CatalogReceiptUnavailable("selection_mismatch")
    loaded = [
        _load(
            db,
            principal=principal,
            receipt_id=link.receipt_id,
            source=fences[link.account_id],
            window=inputs.reporting_window,
            now=now,
        )
        for link in links
    ]
    _check_current_owner_receipts(inputs, loaded, ticket.sources, ticket.privacy_revision)
    expected = _bindings(inputs, loaded)
    if any(
        not utc(inputs.created_at) <= utc(link.created_at) < utc(row.expires_at)
        for link, (row, _) in zip(links, loaded, strict=True)
    ):
        raise CatalogReceiptUnavailable("integrity_unavailable")
    try:
        actual = tuple(
            ReceiptBindingV1.model_validate(
                {name: getattr(link, name) for name in ReceiptBindingV1.model_fields}
            )
            for link in links
        )
    except ValueError as exc:
        raise CatalogReceiptUnavailable("integrity_unavailable") from exc
    if actual != expected:
        raise CatalogReceiptUnavailable("selection_mismatch")
    _check_sources(db, principal, inputs, ticket.sources, now)
    _unexpired(db, loaded, now)
    return ResolvedInputCatalogs(catalogs=tuple(c for _, c in loaded), bindings=expected)


def recheck_saved_input_receipts(
    db: Session,
    *,
    principal: CustomerPrincipal,
    ticket: GenerationTicket,
    catalogs: tuple[CatalogEvidence, ...],
    now: datetime,
) -> None:
    resolved = resolve_saved_input_catalogs(db, principal=principal, ticket=ticket, now=now)
    catalogs = tuple(CatalogEvidence.model_validate(catalog) for catalog in catalogs)
    if any(c.reference.account not in ticket.inputs.accounts for c in catalogs):
        raise CatalogReceiptUnavailable("selection_mismatch")
    expected = {
        c.reference.account.account_id: c
        for c in resolved.catalogs
        if c.reference.account is not None
    }
    actual = {
        c.reference.account.account_id: c for c in catalogs if c.reference.account is not None
    }
    if len(actual) != len(catalogs) or any(actual.get(aid) != cat for aid, cat in expected.items()):
        raise CatalogReceiptUnavailable("selection_mismatch")


def cleanup_expired_unused_receipts(
    db: Session,
    *,
    workspace_id: int,
    now: datetime,
    limit: int = 100,
) -> int:
    """Caller holds fresh owner/privacy/workspace locks in separate maintenance transaction."""
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError("cleanup batch must be 1..100")
    linked = (
        select(InputCatalogReceiptRow.receipt_id)
        .where(
            InputCatalogReceiptRow.workspace_id == CatalogReceiptRow.workspace_id,
            InputCatalogReceiptRow.receipt_id == CatalogReceiptRow.id,
        )
        .exists()
    )
    ids = list(
        db.scalars(
            select(CatalogReceiptRow.id)
            .where(
                CatalogReceiptRow.workspace_id == workspace_id,
                CatalogReceiptRow.expires_at <= _now(db, now),
                ~linked,
            )
            .order_by(CatalogReceiptRow.expires_at, CatalogReceiptRow.id)
            .limit(limit)
            .with_for_update()
        ).all()
    )
    if ids:
        db.execute(
            delete(CatalogReceiptSelectionRow).where(
                CatalogReceiptSelectionRow.workspace_id == workspace_id,
                CatalogReceiptSelectionRow.receipt_id.in_(ids),
            )
        )
        db.execute(
            delete(CatalogReceiptRow).where(
                CatalogReceiptRow.workspace_id == workspace_id,
                CatalogReceiptRow.id.in_(ids),
                ~linked,
            )
        )
        db.flush()
    return len(ids)


def validate_retained_input_receipts(db: Session, inputs: PlanInputRevision) -> None:
    """No source/TTL/session refresh: validate historical exact input and complete links."""
    inputs = PlanInputRevision.model_validate(inputs)
    _saved_input(db, inputs)
    links = _input_links(db, inputs)
    if len(links) > 20:
        raise CatalogReceiptUnavailable("integrity_unavailable")
    accounts = {a.account_id: a for a in inputs.accounts}
    loaded = []
    for link in links:
        row = db.get(
            CatalogReceiptRow, (inputs.workspace_id, link.receipt_id), populate_existing=True
        )
        if (
            row is None
            or link.account_id not in accounts
            or (
                row.actor_id != inputs.created_by
                or row.account_id != link.account_id
                or row.connection_id != link.connection_id
            )
        ):
            raise CatalogReceiptUnavailable("integrity_unavailable")
        _, catalog = validate_retained_receipt(db, row)
        evidence = _evidence(
            catalog,
            SourceFence(
                account=accounts[link.account_id],
                source_binding_digest=row.source_binding_digest,
                source_revision=row.source_revision,
                privacy_revision=row.privacy_revision,
            ),
        )
        if evidence.reference.reporting_window != inputs.reporting_window:
            raise CatalogReceiptUnavailable("selection_mismatch")
        loaded.append((row, evidence))
    expected = _bindings(inputs, loaded)
    if any(
        not utc(inputs.created_at) <= utc(link.created_at) < utc(row.expires_at)
        for link, (row, _) in zip(links, loaded, strict=True)
    ):
        raise CatalogReceiptUnavailable("integrity_unavailable")
    try:
        actual = tuple(
            ReceiptBindingV1.model_validate(
                {name: getattr(link, name) for name in ReceiptBindingV1.model_fields}
            )
            for link in links
        )
    except ValueError as exc:
        raise CatalogReceiptUnavailable("integrity_unavailable") from exc
    if actual != expected:
        raise CatalogReceiptUnavailable("selection_mismatch")

    if inputs.google_daily_budget_intents is not None:
        from app.planning_documents.google_budget_input_receipts import (
            validate_historical_owner_receipts,
        )

        try:
            validate_historical_owner_receipts(inputs, loaded)
        except (ValueError, GoogleBudgetOwnerUnavailable) as error:
            raise CatalogReceiptUnavailable("integrity_unavailable") from error


def _check_current_owner_receipts(
    inputs: PlanInputRevision,
    loaded: list[tuple[CatalogReceiptRow, CatalogEvidence]],
    sources: tuple[SourceFence, ...],
    privacy_revision: int,
) -> None:
    if inputs.google_daily_budget_intents is None:
        return
    from app.planning_documents.google_budget_input_receipts import validate_current_owner_receipts

    try:
        validate_current_owner_receipts(inputs, loaded, sources, privacy_revision)
    except (ValueError, GoogleBudgetOwnerUnavailable) as error:
        raise CatalogReceiptUnavailable("selection_mismatch") from error
