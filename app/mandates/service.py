"""Transactional simulation policy. No provider code or live side effects are reachable."""

import json
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.ads.enums import AdvertisingPlatform
from app.goals import service as goals
from app.imports.scope import AdvertisingImportScope, ImportScopeError, validate_advertising_scope
from app.mandates.models import Mandate, MandateAction, MandateAudit, MandateRevision
from app.mandates.schemas import (
    ActionDraft,
    ClaimInput,
    MandateDefinition,
    ReconcileInput,
    SyntheticEvidence,
)
from app.shopify.security import utc
from app.workspaces.models import Workspace


def workspace_lock(db: Session, workspace_id: int) -> None:
    w = db.scalar(
        select(Workspace).where(Workspace.id == workspace_id).with_for_update(key_share=True)
    )
    if w is None or w.status != "active":
        raise HTTPException(404, "workspace unavailable")


def owned(db: Session, workspace_id: int, mandate_id: str) -> Mandate:
    workspace_lock(db, workspace_id)
    m = db.scalar(
        select(Mandate)
        .where(Mandate.id == mandate_id, Mandate.workspace_id == workspace_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if m is None:
        raise HTTPException(404, "mandate not found")
    return m


def policy(db: Session, m: Mandate) -> MandateDefinition:
    r = db.get(MandateRevision, (m.id, m.revision))
    assert r is not None
    return MandateDefinition.model_validate(r.definition)


def audit(
    db: Session,
    m: Mandate,
    event: str,
    actor: str,
    now: datetime,
    action: MandateAction | None = None,
) -> None:
    db.add(
        MandateAudit(
            id=uuid4().hex,
            mandate_id=m.id,
            action_id=action.id if action else None,
            event=event,
            actor=actor,
            created_at=now,
        )
    )


def validate(db: Session, m: Mandate, d: MandateDefinition, now: datetime) -> None:
    goal = goals.owned(db, m.workspace_id, d.goal_id)
    goals.expect(goal, d.goal_revision)
    if goals.assessment(db, goal, now) != "confirmed":
        raise HTTPException(409, "confirmed goal baseline unavailable")
    definition = goals.current(db, goal).definition
    if definition is None or definition["target_window"]["currency"] != d.currency:
        raise HTTPException(422, "mandate currency does not match goal")
    for account in sorted(d.accounts, key=lambda a: a.account_id):
        try:
            ad, _ = validate_advertising_scope(
                db,
                AdvertisingImportScope(
                    m.workspace_id,
                    account.connection_id,
                    account.account_id,
                    AdvertisingPlatform(account.platform),
                ),
            )
        except (ValueError, ImportScopeError):
            raise HTTPException(409, "advertising scope unavailable") from None
        if ad.currency_code != d.currency:
            raise HTTPException(422, "account currency mismatch")


def create(
    db: Session, workspace_id: int, d: MandateDefinition, actor: str, now: datetime
) -> Mandate:
    workspace_lock(db, workspace_id)
    conflict = db.scalar(
        select(Mandate.id)
        .where(
            Mandate.workspace_id == workspace_id,
            or_(
                Mandate.reserved_micros > 0,
                (Mandate.starts_at < d.ends_at) & (Mandate.ends_at > d.starts_at),
            ),
        )
        .limit(1)
    )
    unresolved = db.scalar(
        select(MandateAction.id)
        .where(
            MandateAction.workspace_id == workspace_id,
            MandateAction.state.in_(["claimed", "dispatching", "outcome_unknown"]),
        )
        .limit(1)
    )
    if conflict or unresolved:
        raise HTTPException(409, "existing governing period or unresolved exposure")
    m = Mandate(
        id=uuid4().hex,
        workspace_id=workspace_id,
        revision=1,
        starts_at=d.starts_at,
        ends_at=d.ends_at,
    )
    db.add(m)
    db.flush()
    validate(db, m, d, now)
    db.add(
        MandateRevision(
            mandate_id=m.id,
            revision=1,
            definition=d.model_dump(mode="json"),
            created_by=actor,
            created_at=now,
        )
    )
    audit(db, m, "created_simulation", actor, now)
    db.flush()
    return m


def edit(
    db: Session, m: Mandate, expected: int, d: MandateDefinition, actor: str, now: datetime
) -> None:
    if m.revision != expected:
        raise HTTPException(409, "mandate revision changed")
    old = policy(db, m)
    if (old.starts_at, old.ends_at, old.currency) != (d.starts_at, d.ends_at, d.currency):
        raise HTTPException(409, "governing period/currency cannot reset consumption")
    validate(db, m, d, now)
    m.revision += 1
    m.state = "draft"
    m.paused = True
    db.add(
        MandateRevision(
            mandate_id=m.id,
            revision=m.revision,
            definition=d.model_dump(mode="json"),
            created_by=actor,
            created_at=now,
        )
    )
    audit(db, m, "revised_simulation", actor, now)


def approve(db: Session, m: Mandate, expected: int, actor: str, now: datetime) -> None:
    if m.revision != expected:
        raise HTTPException(409, "mandate revision changed")
    if m.state == "revoked":
        raise HTTPException(409, "mandate revoked")
    d = policy(db, m)
    validate(db, m, d, now)
    if now >= d.ends_at:
        raise HTTPException(409, "mandate expired")
    if (
        m.observed_micros + m.reserved_micros > d.total_cap_micros
        or m.changes_used > d.positive_change_cap_micros
        or m.actions_used > d.action_limit
    ):
        raise HTTPException(409, "mandate overcommitted")
    r = db.get(MandateRevision, (m.id, m.revision))
    assert r is not None
    if r.approved_at is None:
        r.approved_at = now
        r.approved_by = actor
    m.state = "approved"
    m.paused = False
    audit(db, m, "approved_simulation", actor, now)


def stop(db: Session, m: Mandate, actor: str, now: datetime, *, revoke: bool = False) -> None:
    m.paused = True
    if revoke:
        m.state = "revoked"
    audit(db, m, "revoked" if revoke else "paused", actor, now)


def action(db: Session, m: Mandate, action_id: str) -> MandateAction:
    a = db.scalar(
        select(MandateAction)
        .where(MandateAction.id == action_id, MandateAction.mandate_id == m.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if a is None:
        raise HTTPException(404, "action not found")
    return a


def draft(db: Session, m: Mandate, d: ActionDraft, actor: str, now: datetime) -> MandateAction:
    p = policy(db, m)
    if (
        d.mandate_revision != m.revision
        or d.account not in p.accounts
        or d.kind not in p.allowed_actions
    ):
        raise HTTPException(409, "action outside mandate revision")
    digest = sha256(
        json.dumps(d.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    existing = db.scalar(
        select(MandateAction).where(
            MandateAction.mandate_id == m.id, MandateAction.digest == digest
        )
    )
    if existing:
        return existing
    a = MandateAction(
        id=uuid4().hex,
        mandate_id=m.id,
        workspace_id=m.workspace_id,
        draft=d.model_dump(mode="json"),
        digest=digest,
        state="awaiting_review"
        if d.kind in {"new_campaign", "creative", "negative_keyword"}
        else "eligible",
    )
    db.add(a)
    db.flush()
    audit(db, m, "drafted", actor, now, a)
    return a


def review(
    db: Session, m: Mandate, a: MandateAction, digest: str, actor: str, now: datetime
) -> None:
    if a.digest != digest or a.state not in {"awaiting_review", "eligible"} or a.fence:
        raise HTTPException(409, "draft review changed or action claimed")
    d = ActionDraft.model_validate(a.draft)
    if d.mandate_revision != m.revision:
        raise HTTPException(409, "mandate revision changed")
    if a.reviewed_by is None:
        a.reviewed_by = actor
        a.reviewed_at = now
    a.state = "eligible"
    audit(db, m, "reviewed_exact_draft", actor, now, a)


def preconditions(
    db: Session, m: Mandate, a: MandateAction, e: SyntheticEvidence, now: datetime
) -> tuple[MandateDefinition, ActionDraft]:
    from app.settings import settings

    if not settings.mandate_simulation_enabled:
        raise HTTPException(409, "simulation kill switch active")
    p = policy(db, m)
    d = ActionDraft.model_validate(a.draft)
    if m.state != "approved" or m.paused or not p.starts_at <= now < p.ends_at:
        raise HTTPException(409, "mandate stopped or outside period")
    if (
        d.mandate_revision != m.revision
        or d.account not in p.accounts
        or d.kind not in p.allowed_actions
    ):
        raise HTTPException(409, "action scope changed")
    validate(db, m, p, now)
    if (
        not e.entitlement_active
        or not 0 <= (now - e.observed_at).total_seconds() <= p.freshness_seconds
    ):
        raise HTTPException(409, "stale or unavailable simulation evidence")
    if e.state_digest != d.expected_state_digest or e.bound_micros > d.exposure_micros:
        raise HTTPException(409, "current state or exposure changed")
    if d.kind in {"new_campaign", "creative", "negative_keyword"} and a.reviewed_by is None:
        raise HTTPException(409, "exact draft review required")
    if set(e.covered_account_ids) != {x.account_id for x in p.accounts}:
        raise HTTPException(409, "incomplete scope observation")
    if m.opening_micros is None:
        m.opening_micros = e.period_consumed_micros
    m.observed_micros = max(m.observed_micros, e.period_consumed_micros)
    if m.observed_micros + m.reserved_micros > p.total_cap_micros:
        raise HTTPException(409, "observed exposure exceeds cap")
    return p, d


def claim(
    db: Session, m: Mandate, a: MandateAction, body: ClaimInput, actor: str, now: datetime
) -> None:
    if a.request_key is not None:
        if a.request_key != body.request_key:
            raise HTTPException(409, "action already claimed")
        return
    if a.state != "eligible":
        raise HTTPException(409, "action not eligible")
    if db.scalar(
        select(MandateAction.id).where(
            MandateAction.mandate_id == m.id, MandateAction.request_key == body.request_key
        )
    ):
        raise HTTPException(409, "idempotency conflict")
    p, d = preconditions(db, m, a, body.evidence, now)
    if (
        d.exposure_micros > p.per_action_cap_micros
        or m.observed_micros + m.reserved_micros + d.exposure_micros > p.total_cap_micros
        or m.changes_used + d.positive_change_micros > p.positive_change_cap_micros
        or m.actions_used >= p.action_limit
    ):
        raise HTTPException(409, "cumulative policy cap exceeded")
    if m.last_action_at and now - utc(m.last_action_at) < timedelta(seconds=p.cooldown_seconds):
        raise HTTPException(409, "policy cooldown")
    # No second action against the same resource until the first is settled/cancelled.
    for pending in db.scalars(
        select(MandateAction).where(
            MandateAction.mandate_id == m.id,
            MandateAction.state.in_(["claimed", "dispatching", "outcome_unknown"]),
        )
    ):
        prior = ActionDraft.model_validate(pending.draft)
        if (prior.account.account_id, prior.resource_key) == (d.account.account_id, d.resource_key):
            raise HTTPException(409, "resource outcome unresolved")
    m.reserved_micros += d.exposure_micros
    m.changes_used += d.positive_change_micros
    m.actions_used += 1
    m.last_action_at = now
    a.request_key = body.request_key
    a.fence = uuid4().hex
    a.claimed_at = now
    a.state = "claimed"
    audit(db, m, "claimed_before_simulation", actor, now, a)
    db.commit()  # Deliberately durable before any subsequent dispatch boundary.


def dispatch(
    db: Session,
    m: Mandate,
    a: MandateAction,
    fence: str,
    e: SyntheticEvidence,
    actor: str,
    now: datetime,
) -> None:
    if a.fence != fence or a.state != "claimed" or a.cancel_requested:
        raise HTTPException(409, "action cannot dispatch")
    if a.claimed_at is None or now - utc(a.claimed_at) > timedelta(minutes=5):
        raise HTTPException(409, "claim expired; cancel safely before preparing another")
    preconditions(db, m, a, e, now)
    a.state = "dispatching"
    a.dispatch_at = now
    audit(db, m, "simulation_dispatch_marker", actor, now, a)
    db.commit()  # This release has no provider adapter after this marker.


def reconcile(
    db: Session, m: Mandate, a: MandateAction, body: ReconcileInput, actor: str, now: datetime
) -> None:
    if a.fence != body.fence:
        raise HTTPException(409, "stale attempt fence")
    expected = "simulated_success" if body.outcome == "success" else "simulated_no_effect"
    if a.state in {"simulated_success", "simulated_no_effect"}:
        if a.state != expected or a.settled_micros != body.consumed_micros:
            raise HTTPException(409, "conflicting settlement")
        return
    if a.state not in {"dispatching", "outcome_unknown"} or a.dispatch_at is None:
        raise HTTPException(409, "no dispatched attempt to reconcile")
    if not utc(a.dispatch_at) <= body.evidence_at <= now:
        raise HTTPException(409, "invalid reconciliation evidence time")
    d = ActionDraft.model_validate(a.draft)
    if body.outcome == "unknown":
        if body.consumed_micros:
            raise HTTPException(422, "unknown outcome cannot settle spend")
        a.state = "outcome_unknown"
        m.observed_micros = max(m.observed_micros, body.period_consumed_micros)
    else:
        if body.outcome == "no_effect" and body.consumed_micros:
            raise HTTPException(422, "no-effect outcome cannot contain spend")
        if body.consumed_micros > d.exposure_micros:
            raise HTTPException(409, "exposure bound violated; manual reconciliation required")
        settled = (
            db.scalar(
                select(func.coalesce(func.sum(MandateAction.settled_micros), 0)).where(
                    MandateAction.mandate_id == m.id
                )
            )
            or 0
        )
        minimum = (m.opening_micros or 0) + settled + body.consumed_micros
        if body.period_consumed_micros < max(m.observed_micros, minimum):
            raise HTTPException(409, "settlement observation incomplete")
        m.reserved_micros -= d.exposure_micros
        m.observed_micros = body.period_consumed_micros
        a.state = expected
        a.settled_micros = body.consumed_micros
    audit(db, m, "simulation_" + body.outcome, actor, now, a)


def cancel(db: Session, m: Mandate, a: MandateAction, actor: str, now: datetime) -> None:
    if a.state in {"draft", "awaiting_review", "eligible", "claimed"}:
        if a.state == "claimed":
            m.reserved_micros -= ActionDraft.model_validate(a.draft).exposure_micros
        a.state = "cancelled"
    elif a.state in {"dispatching", "outcome_unknown"}:
        a.cancel_requested = True
    audit(db, m, "cancel_requested", actor, now, a)


def view(db: Session, m: Mandate) -> dict[str, Any]:
    return {
        "id": m.id,
        "revision": m.revision,
        "state": m.state,
        "paused": m.paused,
        "definition": policy(db, m).model_dump(mode="json"),
        "observed_simulated_micros": m.observed_micros,
        "reserved_simulated_micros": m.reserved_micros,
        "positive_changes_used": m.changes_used,
        "actions_used": m.actions_used,
        "live_execution_enabled": False,
        "past_spend_reversible": False,
    }


def action_view(a: MandateAction) -> dict[str, Any]:
    return {
        "id": a.id,
        "draft": a.draft,
        "draft_digest": a.digest,
        "state": a.state,
        "reviewed_by": a.reviewed_by,
        "reviewed_at": a.reviewed_at,
        "fence": a.fence,
        "cancel_requested": a.cancel_requested,
        "settled_simulated_micros": a.settled_micros,
        "live_execution_enabled": False,
    }
