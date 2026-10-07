"""Separate customer consent and shared period accounting for real-provider execution.

No function in this module emits provider requests. Contract-test consent is immutable
in environment and can never be promoted into live authority.
"""

from collections.abc import Callable
from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ads.enums import AdvertisingPlatform
from app.billing.entitlements import live_paid_work, paid_work
from app.goals import service as goals
from app.google_connections.models import GoogleCustomerConnection
from app.imports.scope import AdvertisingImportScope, ImportScopeError, validate_advertising_scope
from app.mandates.service import workspace_lock
from app.meta.models import MetaConnection
from app.publication.execution_contracts import (
    ExecutionAccount,
    ProviderMandateBinding,
    ProviderMandatePolicy,
)
from app.publication.execution_models import (
    ProviderExecutionConsent,
    ProviderExecutionMandate,
    ProviderExecutionRevision,
    ProviderExposureReservation,
    ProviderPeriodLedger,
)
from app.publication.service import owner
from app.shopify.security import utc
from app.sources.models import SourceConnection


def current_account(db: Session, scope: ExecutionAccount) -> None:
    """Caller holds workspace; use account/integration then native source lock order."""
    try:
        account, _ = validate_advertising_scope(
            db,
            AdvertisingImportScope(
                scope.workspace_id,
                scope.account.connection_id,
                scope.account.account_id,
                AdvertisingPlatform(scope.account.platform),
            ),
        )
    except ImportScopeError:
        raise HTTPException(409, "current advertising scope unavailable") from None
    if account.external_account_id != scope.external_advertiser_id:
        raise HTTPException(409, "advertiser identity changed")
    if scope.account.platform == "google_ads":
        google = db.scalar(
            select(GoogleCustomerConnection)
            .where(
                GoogleCustomerConnection.workspace_id == scope.workspace_id,
                GoogleCustomerConnection.integration_id == scope.account.connection_id,
                GoogleCustomerConnection.account_id == scope.account.account_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if google is None or google.status != "connected":
            raise HTTPException(409, "provider connection unavailable")
        external, version = google.external_account_id, f"google:{google.id}:{google.generation}"
    elif scope.account.platform == "meta_ads":
        meta = db.scalar(
            select(MetaConnection)
            .where(
                MetaConnection.workspace_id == scope.workspace_id,
                MetaConnection.workspace_integration_id == scope.account.connection_id,
                MetaConnection.account_id == scope.account.account_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if meta is None or meta.status != "connected":
            raise HTTPException(409, "provider connection unavailable")
        external, version = meta.external_account_id, f"meta:{meta.id}:{meta.generation}"
    else:
        source = db.scalar(
            select(SourceConnection)
            .where(
                SourceConnection.workspace_id == scope.workspace_id,
                SourceConnection.integration_id == scope.account.connection_id,
                SourceConnection.account_id == scope.account.account_id,
                SourceConnection.provider == "tiktok_ads",
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if source is None or source.status != "connected":
            raise HTTPException(409, "provider connection unavailable")
        external, version = source.external_id, f"tiktok:{source.id}:{source.generation}"
    if external != scope.external_advertiser_id or version != scope.connection_version:
        raise HTTPException(409, "provider connection generation changed")


def accounting_account_set(p: ProviderMandatePolicy) -> set[tuple[int, str, str]]:
    """Stable accounting identity; reconnect generation changes do not erase spend."""
    return {
        (a.account.account_id, a.account.platform, a.external_advertiser_id) for a in p.accounts
    }


def validate_accounting_scope(
    db: Session, ledger: ProviderPeriodLedger, p: ProviderMandatePolicy
) -> None:
    """Caller holds workspace then ledger; the first consent pins this period's scope.

    Scalar portfolio high-water accounting cannot safely drop or replace accounts.
    Drafts remain editable until consent. Later revisions/new mandates must retain
    every original accounting identity, even after all reservations are settled.
    """
    history = list(
        db.execute(
            select(ProviderExecutionRevision, ProviderExecutionConsent)
            .join(
                ProviderExecutionMandate,
                ProviderExecutionMandate.id == ProviderExecutionRevision.mandate_id,
            )
            .join(
                ProviderExecutionConsent,
                (ProviderExecutionConsent.mandate_id == ProviderExecutionRevision.mandate_id)
                & (ProviderExecutionConsent.revision == ProviderExecutionRevision.revision),
            )
            .where(
                ProviderExecutionMandate.ledger_id == ledger.id,
                ProviderExecutionMandate.workspace_id == p.workspace_id,
                ProviderExecutionRevision.workspace_id == p.workspace_id,
                ProviderExecutionConsent.workspace_id == p.workspace_id,
            )
            .limit(10001)
        )
    )
    if len(history) > 10000 or (
        not history and (ledger.action_count or ledger.spent_high_water_micros)
    ):
        raise HTTPException(409, "period accounting account set unavailable")
    expected = accounting_account_set(p)
    for revision, consented in history:
        historical = ProviderMandatePolicy.model_validate(revision.policy)
        if (
            historical.digest() != revision.digest
            or consented.policy_digest != revision.digest
            or accounting_account_set(historical) != expected
        ):
            raise HTTPException(409, "consented period accounting account set is immutable")


def reject_mixed_currency_holds(db: Session, p: ProviderMandatePolicy) -> None:
    """Do not add amounts in different currencies; no FX authority is configured."""
    mismatch = db.scalar(
        select(ProviderExposureReservation.id)
        .join(
            ProviderPeriodLedger, ProviderPeriodLedger.id == ProviderExposureReservation.ledger_id
        )
        .where(
            ProviderExposureReservation.workspace_id == p.workspace_id,
            ProviderExposureReservation.environment == p.environment,
            ProviderExposureReservation.state == "held",
            ProviderPeriodLedger.currency != p.currency,
        )
        .limit(1)
    )
    if mismatch is not None:
        raise HTTPException(409, "unresolved exposure currency differs from mandate")


def validate_policy(
    db: Session, p: ProviderMandatePolicy, actor: str, clock: Callable[[], datetime]
) -> None:
    owner(db, p.workspace_id, actor)
    reject_mixed_currency_holds(db, p)
    goal = goals.owned(db, p.workspace_id, p.goal_id)
    goals.expect(goal, p.goal_revision)
    for account in sorted(p.accounts, key=lambda a: a.account.account_id):
        current_account(db, account)
    now = clock()
    if p.environment == "live":
        live_paid_work(db, p.workspace_id, now)
    else:
        paid_work(db, p.workspace_id, now)
    definition = goals.current(db, goal).definition
    if (
        goals.assessment(db, goal, now) != "confirmed"
        or definition is None
        or definition["target_window"]["currency"] != p.currency
        or now >= p.ends_at
    ):
        raise HTTPException(409, "current confirmed goal and mandate period required")


def owned(
    db: Session, wid: int, mandate_id: str
) -> tuple[ProviderPeriodLedger, ProviderExecutionMandate]:
    workspace_lock(db, wid)
    identity = db.scalar(
        select(ProviderExecutionMandate).where(
            ProviderExecutionMandate.id == mandate_id, ProviderExecutionMandate.workspace_id == wid
        )
    )
    if identity is None:
        raise HTTPException(404, "provider mandate unavailable")
    ledger = db.scalar(
        select(ProviderPeriodLedger)
        .where(
            ProviderPeriodLedger.id == identity.ledger_id, ProviderPeriodLedger.workspace_id == wid
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    row = db.scalar(
        select(ProviderExecutionMandate)
        .where(
            ProviderExecutionMandate.id == mandate_id, ProviderExecutionMandate.workspace_id == wid
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    assert ledger is not None and row is not None
    return ledger, row


def policy(db: Session, row: ProviderExecutionMandate) -> ProviderMandatePolicy:
    revision = db.get(ProviderExecutionRevision, (row.id, row.revision))
    if revision is None or revision.workspace_id != row.workspace_id:
        raise HTTPException(409, "provider policy unavailable")
    p = ProviderMandatePolicy.model_validate(revision.policy)
    if p.digest() != revision.digest:
        raise HTTPException(409, "provider policy changed")
    return p


def revise(
    db: Session,
    wid: int,
    p: ProviderMandatePolicy,
    actor: str,
    clock: Callable[[], datetime],
    *,
    mandate_id: str | None = None,
    expected_revision: int | None = None,
    commit: bool = True,
) -> ProviderExecutionMandate:
    p = ProviderMandatePolicy.model_validate(p.model_dump())
    if p.workspace_id != wid:
        raise HTTPException(404, "provider mandate unavailable")
    workspace_lock(db, wid)
    if mandate_id is not None:
        ledger, row = owned(db, wid, mandate_id)
        if row.revision != expected_revision or row.state == "revoked":
            raise HTTPException(409, "provider mandate revision changed")
    else:
        # Workspace serialization prevents competing creates, including overlapping periods.
        overlapping = list(
            db.scalars(
                select(ProviderPeriodLedger)
                .where(
                    ProviderPeriodLedger.workspace_id == wid,
                    ProviderPeriodLedger.environment == p.environment,
                    ProviderPeriodLedger.starts_at < p.ends_at,
                    ProviderPeriodLedger.ends_at > p.starts_at,
                )
                .with_for_update()
            )
        )
        if overlapping:
            ledger = overlapping[0]
            if len(overlapping) != 1:
                raise HTTPException(409, "ambiguous provider period ledger")
        else:
            ledger = ProviderPeriodLedger(
                id=uuid4().hex,
                workspace_id=wid,
                environment=p.environment,
                currency=p.currency,
                starts_at=p.starts_at,
                ends_at=p.ends_at,
                spent_high_water_micros=0,
                action_count=0,
            )
            db.add(ledger)
            db.flush()
        row = ProviderExecutionMandate(
            id=uuid4().hex, workspace_id=wid, ledger_id=ledger.id, revision=0, state="draft"
        )
    if (
        ledger.environment != p.environment
        or ledger.currency != p.currency
        or (utc(ledger.starts_at), utc(ledger.ends_at)) != (p.starts_at, p.ends_at)
    ):
        raise HTTPException(409, "immutable shared provider period required")
    validate_policy(db, p, actor, clock)
    validate_accounting_scope(db, ledger, p)
    row.revision += 1
    row.state = "draft"
    db.add(row)
    db.flush()
    db.add(
        ProviderExecutionRevision(
            mandate_id=row.id,
            revision=row.revision,
            workspace_id=wid,
            goal_id=p.goal_id,
            goal_revision=p.goal_revision,
            policy=p.model_dump(mode="json"),
            digest=p.digest(),
            actor=actor,
            created_at=clock(),
        )
    )
    db.flush()
    if commit:
        db.commit()
    return row


def consent(
    db: Session,
    wid: int,
    mandate_id: str,
    revision: int,
    digest: str,
    actor: str,
    clock: Callable[[], datetime],
) -> ProviderMandateBinding:
    ledger, row = owned(db, wid, mandate_id)
    p = policy(db, row)
    if row.revision != revision or p.digest() != digest or row.state == "revoked":
        raise HTTPException(409, "exact provider mandate consent required")
    validate_policy(db, p, actor, clock)
    validate_accounting_scope(db, ledger, p)
    record = db.scalar(
        select(ProviderExecutionConsent).where(
            ProviderExecutionConsent.mandate_id == row.id,
            ProviderExecutionConsent.revision == revision,
        )
    )
    now = clock()
    if now >= p.ends_at:
        raise HTTPException(409, "provider mandate outside approved period")
    if record is None:
        record = ProviderExecutionConsent(
            id=uuid4().hex,
            workspace_id=wid,
            mandate_id=row.id,
            revision=revision,
            policy_digest=digest,
            actor=actor,
            approved_at=now,
        )
        db.add(record)
    else:
        owner(db, wid, record.actor)
    row.state = "active"
    db.commit()
    return ProviderMandateBinding(
        mandate_id=row.id,
        revision=revision,
        consent_id=record.id,
        policy_digest=digest,
        ledger_id=ledger.id,
        environment=p.environment,
    )


def checked(
    db: Session,
    wid: int,
    binding: ProviderMandateBinding,
    actor: str,
    clock: Callable[[], datetime],
) -> tuple[ProviderPeriodLedger, ProviderMandatePolicy]:
    ledger, row = owned(db, wid, binding.mandate_id)
    p = policy(db, row)
    record = db.get(ProviderExecutionConsent, binding.consent_id)
    if (
        row.state != "active"
        or row.revision != binding.revision
        or p.digest() != binding.policy_digest
        or ledger.id != binding.ledger_id
        or p.environment != binding.environment
        or record is None
        or record.workspace_id != wid
        or record.mandate_id != row.id
        or record.revision != row.revision
        or record.policy_digest != p.digest()
    ):
        raise HTTPException(409, "current exact provider consent required")
    validate_policy(db, p, actor, clock)
    validate_accounting_scope(db, ledger, p)
    owner(db, wid, record.actor)
    if not p.starts_at <= clock() < p.ends_at:
        raise HTTPException(409, "provider mandate outside approved period")
    return ledger, p


def suspend(db: Session, wid: int, mandate_id: str, actor: str, *, revoke: bool = False) -> None:
    _, row = owned(db, wid, mandate_id)
    owner(db, wid, actor)
    row.state = "revoked" if revoke or row.state == "revoked" else "paused"
    db.commit()  # reservations and prior attempts deliberately remain durable
