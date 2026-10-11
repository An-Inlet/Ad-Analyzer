"""DB-only retained local proofs. Caller owns fresh identity, locks and final age checks."""

from collections.abc import Sequence
from datetime import date, datetime
from typing import Any, Literal

from fastapi import HTTPException
from pydantic import AwareDatetime, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ads.models import AdvertisingAccount, Campaign
from app.campaign_performance.models import CurrentPerformance, PerformanceCompletion
from app.campaign_performance.presence_report import PresenceReadContext
from app.campaign_performance.presence_storage import ReportingPresenceUnavailable, read_presence
from app.campaign_performance.service import manifest, read_current
from app.commerce.ledger import lock_store
from app.customers.access import CustomerPrincipal, guard_customer_mutation
from app.goals import service as goals
from app.goals.progress import READ_ROLES, _read_goal_progress_locked
from app.goals.schemas import GoalDefinition
from app.google_connections.models import GoogleCustomerConnection
from app.lifecycle.privacy import database_utc_now, workspace_export_revision
from app.meta.models import MetaConnection
from app.planning_documents.common import (
    MAX_ACCOUNTS,
    MAX_EVIDENCE,
    Digest,
    Frozen,
    Id,
    Key,
    Positive,
    Title,
    fingerprint,
)
from app.planning_documents.context import AccountRef
from app.planning_documents.documents import PlanVersion
from app.planning_documents.evidence_local import ordinary_meta
from app.planning_documents.models import PlanDependencyRow
from app.planning_documents.policy_capabilities import reporting_capability
from app.publication import customer_intents
from app.publication.contracts import fingerprint as source_fingerprint
from app.shopify.security import ShopifyError, utc
from app.sources.models import SourceConnection

MAX_LOCAL_CAMPAIGNS = 10_000


class RetainedSourcesChanged(Exception):
    def __init__(
        self, reason: Literal["source_changed", "source_integrity_unavailable", "proof_unavailable"]
    ) -> None:
        self.reason = reason
        super().__init__(reason)


class RetainedSourceWitness(Frozen):
    workspace_id: Positive
    plan_id: Id
    version: Positive
    evidence_key: Key
    account_id: Positive | None
    connection_id: Positive | None
    store_id: Id | None
    kind: Literal[
        "local_reporting_v1", "local_reporting_v2", "local_reporting_v3", "local_commerce_v1"
    ]
    source_binding_digest: Digest
    document_digest: Digest
    source_revision: Title
    observed_at: AwareDatetime
    expires_at: AwareDatetime
    privacy_revision: int = Field(strict=True, ge=0)

    @model_validator(mode="after")
    def scoped(self) -> "RetainedSourceWitness":
        if self.observed_at >= self.expires_at:
            raise ValueError("ordered local proof time required")
        if self.kind in {"local_reporting_v1", "local_reporting_v2", "local_reporting_v3"}:
            if (
                self.account_id is None
                or self.connection_id is None
                or self.store_id is not None
                or self.evidence_key != f"local:reporting:{self.account_id}"
            ):
                raise ValueError("exact reporting proof scope required")
        elif (
            self.account_id is not None
            or self.connection_id is not None
            or self.store_id is None
            or self.evidence_key != f"local:commerce:{self.store_id}"
        ):
            raise ValueError("exact commerce proof scope required")
        return self


def _normalize(value: Any) -> Any:
    if isinstance(value, datetime):
        return utc(value).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    return value


def _guard(db: Session, principal: CustomerPrincipal, wid: int, actor: str) -> None:
    if principal.user.id != actor:
        raise HTTPException(401, "customer authentication required")
    guard_customer_mutation(db, principal, wid, allowed_roles=READ_ROLES)


def _goal(db: Session, document: PlanVersion) -> None:
    expected = document.inputs.goal
    goal = goals.owned(db, expected.workspace_id, expected.goal_id)
    db.refresh(goal)
    revision = goals.current(db, goal)
    db.refresh(revision)
    if (
        goal.revision != expected.revision
        or goal.confirmed_preview_id != expected.confirmation_reference
        or revision.confirmed_at is None
        or revision.definition is None
        or GoalDefinition.model_validate(revision.definition) != expected.definition
    ):
        raise RetainedSourcesChanged("source_changed")


def _reporting(
    db: Session,
    principal: CustomerPrincipal,
    ref: AccountRef,
    privacy: int,
    *,
    qualified: bool = False,
    presence_context: PresenceReadContext | None = None,
) -> tuple[str, str]:
    if presence_context is not None:
        transaction = db.get_transaction()
        if (
            presence_context.db is not db
            or transaction is None
            or presence_context.transaction is not transaction
            or not transaction.is_active
        ):
            raise RetainedSourcesChanged("source_integrity_unavailable")
    scope = customer_intents.account(db, ref.workspace_id, ref.account_id)
    if (scope.account.connection_id, scope.account.platform, scope.connection_version) != (
        ref.connection_id,
        ref.platform,
        ref.connection_version,
    ):
        raise RetainedSourcesChanged("source_changed")
    account = db.get(AdvertisingAccount, ref.account_id, populate_existing=True)
    if account is None or account.workspace_id != ref.workspace_id:
        raise RetainedSourcesChanged("source_changed")
    model: Any = {
        "google_ads": GoogleCustomerConnection,
        "meta_ads": MetaConnection,
        "tiktok_ads": SourceConnection,
    }[ref.platform]
    integration_column = (
        model.workspace_integration_id if ref.platform == "meta_ads" else model.integration_id
    )
    source_query = select(model).where(
        model.workspace_id == ref.workspace_id,
        model.account_id == ref.account_id,
        integration_column == ref.connection_id,
    )
    if ref.platform == "tiktok_ads":
        source_query = source_query.where(model.provider == "tiktok_ads")
    source = db.scalar(source_query.with_for_update().execution_options(populate_existing=True))
    if source is None or source.status != "connected" or source.error_code:
        raise RetainedSourcesChanged("source_integrity_unavailable")
    campaigns = list(
        db.scalars(
            select(Campaign)
            .where(Campaign.account_id == ref.account_id, Campaign.platform == ref.platform)
            .order_by(Campaign.id)
            .limit(MAX_LOCAL_CAMPAIGNS + 1)
            .execution_options(populate_existing=True)
        )
    )
    if len(campaigns) > MAX_LOCAL_CAMPAIGNS:
        raise RetainedSourcesChanged("source_integrity_unavailable")
    for campaign in campaigns:
        for value, bound in (
            (campaign.external_campaign_id, 128),
            (campaign.name, 255),
            (campaign.status, 64),
            (campaign.channel_type, 64),
        ):
            if value is not None and (not isinstance(value, str) or len(value) > bound):
                raise RetainedSourcesChanged("source_integrity_unavailable")
    current = db.get(CurrentPerformance, ref.account_id, populate_existing=True)
    completion_state = None
    presence_state = None
    if current is not None:
        completion = db.get(PerformanceCompletion, current.completion_id, populate_existing=True)
        if current.workspace_id != ref.workspace_id or completion is None or not campaigns:
            raise RetainedSourcesChanged("source_integrity_unavailable")
        if ref.platform == "meta_ads":
            ordinary_meta(db, ref.workspace_id, ref.account_id, completion)

        def authorize(session: Session, wid: int, actor: str) -> None:
            _guard(session, principal, wid, actor)

        read_current(
            db,
            ref.workspace_id,
            principal.user.id,
            ref.account_id,
            campaigns[0].id,
            current.completion_id,
            authorize,
        )
        digest, rows = manifest(db, account, completion.starts_on, completion.ends_on)
        if digest != completion.manifest_digest or len(rows) != completion.row_count:
            raise RetainedSourcesChanged("source_integrity_unavailable")
        if qualified:
            try:
                graph = (
                    read_presence(db, completion)
                    if presence_context is None
                    else presence_context.read(completion)
                )
            except ReportingPresenceUnavailable:
                raise RetainedSourcesChanged("source_integrity_unavailable") from None
            presence_state = (
                None
                if graph is None
                else {
                    "header": graph[0].model_dump(mode="json"),
                    "facts": [fact.model_dump(mode="json") for fact in graph[1]],
                }
            )
        completion_state = {
            column.name: getattr(completion, column.name)
            for column in PerformanceCompletion.__table__.columns
        }
    source_fields = (
        "id",
        "status",
        "generation",
        "last_sync_at",
        "covered_from",
        "covered_through",
        "conversion_action_type",
        "history_floor",
        "backfill_through",
        "error_code",
    )
    source_state = {key: getattr(source, key) for key in source_fields if hasattr(source, key)}
    scope_digest = source_fingerprint("inlet.planning-source.v1", scope.model_dump(mode="json"))
    state = {
        "scope": scope.model_dump(mode="json"),
        "currency": account.currency_code,
        "time_zone": account.time_zone,
        "privacy_revision": privacy,
        "source": source_state,
        "current_completion": completion_state,
        "campaigns": [
            dict(
                id=c.id,
                account_id=c.account_id,
                platform=c.platform.value,
                native_id=c.external_campaign_id,
                name=c.name,
                status=c.status,
                channel_type=c.channel_type,
            )
            for c in campaigns
        ],
    }
    if qualified:
        return scope_digest, fingerprint(
            "inlet.local-reporting-state.v2",
            {
                "legacy": _normalize(state),
                "presence": presence_state,
            },
        )
    return scope_digest, fingerprint("inlet.local-reporting-state.v1", _normalize(state))


def capture_reporting_presence_pin(
    db: Session,
    principal: CustomerPrincipal,
    ref: AccountRef,
    privacy: int,
    *,
    presence_context: PresenceReadContext | None = None,
) -> str:
    """New-policy collection/final pin, including exact sidecar absence."""
    try:
        return _reporting(
            db, principal, ref, privacy, qualified=True, presence_context=presence_context
        )[1]
    except RetainedSourcesChanged:
        raise HTTPException(409, "Qualified reporting evidence changed") from None


def capture_retained_sources(
    db: Session, *, principal: CustomerPrincipal, document: PlanVersion, now: datetime
) -> tuple[RetainedSourceWitness, ...]:
    document = PlanVersion.model_validate(document)
    try:
        capability = reporting_capability(document.policy_version, document.generator_version)
    except ValueError as error:
        raise RetainedSourcesChanged("proof_unavailable") from error
    wid = document.inputs.workspace_id
    _guard(db, principal, wid, principal.user.id)
    _goal(db, document)
    privacy = workspace_export_revision(db, wid)
    if any(
        ref.privacy_revision != privacy or ref.key.startswith("local:") for ref in document.evidence
    ):
        raise RetainedSourcesChanged("source_changed")
    current_time = max(utc(now), database_utc_now(db))
    if not document.generated_at <= current_time < document.valid_until:
        raise RetainedSourcesChanged("source_changed")
    values = []
    common: dict[str, Any] = dict(
        workspace_id=wid,
        plan_id=document.inputs.plan_id,
        version=document.version,
        observed_at=current_time,
        expires_at=document.valid_until,
        privacy_revision=privacy,
    )
    for ref in sorted(document.inputs.accounts, key=lambda item: item.account_id):
        source_digest, digest = _reporting(
            db,
            principal,
            ref,
            privacy,
            qualified=capability.local_witness_kind == "local_reporting_v2",
        )
        values.append(
            RetainedSourceWitness(
                **common,
                evidence_key=f"local:reporting:{ref.account_id}",
                kind=capability.local_witness_kind,
                account_id=ref.account_id,
                connection_id=ref.connection_id,
                store_id=None,
                source_binding_digest=source_digest,
                document_digest=digest,
                source_revision=ref.connection_version,
            )
        )
    values.append(
        commerce_witness(db, principal=principal, document=document, common=common, now=now)
    )
    _guard(db, principal, wid, principal.user.id)
    if max(utc(now), database_utc_now(db)) >= document.valid_until:
        raise RetainedSourcesChanged("source_changed")
    return tuple(values)


def commerce_witness(
    db: Session,
    *,
    principal: CustomerPrincipal,
    document: PlanVersion,
    common: dict[str, Any],
    now: datetime,
) -> RetainedSourceWitness:
    """Shared unchanged commerce commitment; caller owns goal/privacy/authority guards."""
    wid = document.inputs.workspace_id
    privacy = common["privacy_revision"]
    store = lock_store(db, document.inputs.goal.definition.store_id, wid)
    progress = _read_goal_progress_locked(
        db,
        principal,
        wid,
        document.inputs.goal.goal_id,
        document.inputs.goal.revision,
        clock=lambda: max(utc(now), database_utc_now(db)),
    )
    if progress.reasons in (("source_unavailable",), ("measurement_basis_changed",)):
        raise RetainedSourcesChanged("source_integrity_unavailable")
    stable = progress.model_dump(mode="json", exclude={"as_of"})
    source = {
        key: getattr(store, key)
        for key in (
            "id",
            "workspace_id",
            "connection_id",
            "status",
            "currency",
            "time_zone",
            "connected_at",
            "revision",
            "covered_from",
            "last_sync_at",
            "window_start",
            "window_end",
            "error_code",
        )
    }
    binding = fingerprint(
        "inlet.local-commerce-binding.v1",
        _normalize(
            {
                "source": source,
                "privacy_revision": privacy,
                "goal": document.inputs.goal.model_dump(mode="json"),
            }
        ),
    )
    return RetainedSourceWitness(
        **common,
        evidence_key=f"local:commerce:{store.id}",
        kind="local_commerce_v1",
        account_id=None,
        connection_id=None,
        store_id=store.id,
        source_binding_digest=binding,
        document_digest=fingerprint(
            "inlet.local-commerce-state.v1", {"binding": binding, "progress": stable}
        ),
        source_revision=str(store.revision),
    )


def _row(row: PlanDependencyRow) -> dict[str, Any]:
    return {
        column.name: (
            utc(getattr(row, column.name))
            if column.name in {"observed_at", "expires_at"}
            else getattr(row, column.name)
        )
        for column in PlanDependencyRow.__table__.columns
    }


def recheck_retained_sources(
    db: Session,
    *,
    principal: CustomerPrincipal,
    document: PlanVersion,
    dependencies: Sequence[PlanDependencyRow],
    now: datetime,
) -> None:
    """Validate complete immutable dependency set, then recompute current local integrity."""
    _guard(db, principal, document.inputs.workspace_id, principal.user.id)
    try:
        _recheck(db, principal, document, dependencies, now)
    except HTTPException as error:
        if error.status_code in {401, 403, 402}:
            raise
        raise RetainedSourcesChanged("source_integrity_unavailable") from None
    except (ValueError, ShopifyError):
        raise RetainedSourcesChanged("proof_unavailable") from None


def _recheck(
    db: Session,
    principal: CustomerPrincipal,
    document: PlanVersion,
    dependencies: Sequence[PlanDependencyRow],
    now: datetime,
) -> None:
    document = PlanVersion.model_validate(document)
    if len(dependencies) > MAX_EVIDENCE + MAX_ACCOUNTS + 1:
        raise RetainedSourcesChanged("proof_unavailable")
    rows = {row.evidence_key: _row(row) for row in dependencies}
    if len(rows) != len(dependencies):
        raise RetainedSourcesChanged("proof_unavailable")
    wid, pid = document.inputs.workspace_id, document.inputs.plan_id
    common: dict[str, Any] = dict(workspace_id=wid, plan_id=pid, version=document.version)
    for ref in document.evidence:
        expected = dict(
            **common,
            evidence_key=ref.key,
            account_id=ref.account.account_id if ref.account else None,
            connection_id=ref.account.connection_id if ref.account else None,
            store_id=document.inputs.goal.definition.store_id
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
        if rows.pop(ref.key, None) != expected:
            raise RetainedSourcesChanged("proof_unavailable")
    expected_keys = {
        f"local:reporting:{account.account_id}" for account in document.inputs.accounts
    }
    expected_keys.add(f"local:commerce:{document.inputs.goal.definition.store_id}")
    if set(rows) != expected_keys:
        raise RetainedSourcesChanged("proof_unavailable")
    retained = {key: RetainedSourceWitness.model_validate(value) for key, value in rows.items()}
    current = capture_retained_sources(db, principal=principal, document=document, now=now)
    for actual in current:
        saved = retained[actual.evidence_key]
        if not document.generated_at <= saved.observed_at <= max(utc(now), database_utc_now(db)):
            raise RetainedSourcesChanged("proof_unavailable")
        if saved.model_dump(exclude={"observed_at"}) != actual.model_dump(exclude={"observed_at"}):
            raise RetainedSourcesChanged("source_changed")
