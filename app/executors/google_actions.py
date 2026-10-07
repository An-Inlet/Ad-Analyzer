"""Bounded Google Search operation plans and offline read-back execution.

This does not replace or bypass the existing disabled live mutation boundary.
"""

import hashlib
import json
from contextlib import suppress
from datetime import datetime
from typing import Any, Literal

from fastapi import HTTPException
from pydantic import AwareDatetime, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ads.models import AdvertisingAccount
from app.goals.schemas import StrictModel
from app.google_connections.models import GoogleCustomerConnection
from app.mandates import service as mandates
from app.mandates.models import Mandate, MandateAction
from app.mandates.schemas import (
    AccountScope,
    ActionDraft,
    ClaimInput,
    ReconcileInput,
    SyntheticEvidence,
)


def fingerprint(value: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class GoogleState(StrictModel):
    customer_id: str = Field(pattern=r"^[0-9]{10}$")
    campaign_id: str = Field(pattern=r"^[0-9]{1,32}$")
    budget_id: str = Field(pattern=r"^[0-9]{1,32}$")
    channel: str
    shared_budget: bool
    status: Literal["ENABLED", "PAUSED", "REMOVED"]
    budget_micros: int = Field(strict=True, ge=0, le=10**15)
    negative_keywords: list[str] = Field(default_factory=list, max_length=1000)
    observed_at: AwareDatetime

    def digest(self) -> str:
        return fingerprint(self.model_dump(mode="json", exclude={"observed_at"}))


class GoogleChange(StrictModel):
    kind: Literal["budget_change", "pause", "resume", "negative_keyword"]
    new_budget_micros: int | None = Field(default=None, strict=True, gt=0, le=10**15)
    keyword: str | None = Field(default=None, min_length=1, max_length=80)
    match_type: Literal["EXACT", "PHRASE"] | None = None
    # A modeled bound must be supplied by a qualified adapter for the full mandate
    # horizon, including platform overdelivery/reporting delay. It is synthetic here.
    modeled_exposure_micros: int = Field(strict=True, ge=0, le=10**15)

    @model_validator(mode="after")
    def relevant_fields(self) -> "GoogleChange":
        if (self.kind == "budget_change") != (self.new_budget_micros is not None):
            raise ValueError("budget change requires only a budget amount")
        if (self.kind == "negative_keyword") != (
            self.keyword is not None and self.match_type is not None
        ):
            raise ValueError("negative keyword requires exact text and match type")
        if self.kind != "negative_keyword" and (
            self.keyword is not None or self.match_type is not None
        ):
            raise ValueError("unexpected keyword fields")
        return self


class FixtureGoogleActions:
    """Only mutation adapter available to this worker. It cannot reach a network."""

    def __init__(self, states: dict[str, GoogleState]) -> None:
        self.states = states
        self.calls = 0
        self.timeout_after_apply = False
        self.ignore_change = False

    def read(self, campaign: str, now: datetime) -> GoogleState:
        return self.states[campaign].model_copy(update={"observed_at": now})

    def apply(self, campaign: str, change: GoogleChange) -> None:
        self.calls += 1
        current = self.states[campaign]
        if not self.ignore_change:
            updates: dict[str, Any] = {}
            if change.kind == "budget_change":
                updates["budget_micros"] = change.new_budget_micros
            elif change.kind in {"pause", "resume"}:
                updates["status"] = "PAUSED" if change.kind == "pause" else "ENABLED"
            else:
                keyword = f"{change.match_type}:{change.keyword}"
                updates["negative_keywords"] = sorted(set(current.negative_keywords + [keyword]))
            self.states[campaign] = current.model_copy(update=updates)
        if self.timeout_after_apply:
            raise TimeoutError("synthetic ambiguous outcome")


def connection(db: Session, m: Mandate, scope: AccountScope) -> GoogleCustomerConnection:
    row = db.scalar(
        select(GoogleCustomerConnection)
        .where(
            GoogleCustomerConnection.workspace_id == m.workspace_id,
            GoogleCustomerConnection.account_id == scope.account_id,
            GoogleCustomerConnection.integration_id == scope.connection_id,
            GoogleCustomerConnection.status == "connected",
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None or scope.platform != "google_ads":
        raise HTTPException(409, "Google customer scope unavailable")
    return row


def prepare(
    db: Session,
    m: Mandate,
    scope: AccountScope,
    state: GoogleState,
    change: GoogleChange,
    actor: str,
    now: datetime,
) -> MandateAction:
    m = mandates.owned(db, m.workspace_id, m.id)
    row = connection(db, m, scope)
    account = db.get(AdvertisingAccount, scope.account_id)
    if account is None or account.external_account_id != state.customer_id:
        raise HTTPException(409, "Google customer state mismatch")
    if state.channel != "SEARCH" or state.shared_budget or state.status == "REMOVED":
        raise HTTPException(409, "unsupported Google campaign configuration")
    policy = mandates.policy(db, m)
    if not 0 <= (now - state.observed_at).total_seconds() <= policy.freshness_seconds:
        raise HTTPException(409, "stale Google resource state")
    if change.kind == "budget_change" and change.new_budget_micros == state.budget_micros:
        raise HTTPException(409, "budget already matches")
    if (change.kind == "pause" and state.status == "PAUSED") or (
        change.kind == "resume" and state.status == "ENABLED"
    ):
        raise HTTPException(409, "status already matches")
    if (
        change.kind == "negative_keyword"
        and f"{change.match_type}:{change.keyword}" in state.negative_keywords
    ):
        raise HTTPException(409, "negative keyword already exists")
    payload: dict[str, str | int | bool] = {
        "schema": "google_search_action_v1",
        "connection_generation": row.generation,
        "customer_id": state.customer_id,
        "campaign_id": state.campaign_id,
        "budget_id": state.budget_id,
        "kind": change.kind,
        "modeled_exposure_micros": change.modeled_exposure_micros,
    }
    if change.new_budget_micros is not None:
        payload["new_budget_micros"] = change.new_budget_micros
    if change.keyword is not None:
        payload["keyword"], payload["match_type"] = change.keyword, str(change.match_type)
    positive_change = max(
        0, (change.new_budget_micros or state.budget_micros) - state.budget_micros
    )
    action = mandates.draft(
        db,
        m,
        ActionDraft(
            account=scope,
            kind=change.kind,
            resource_key="google-campaign:" + state.campaign_id,
            payload=payload,
            payload_digest=fingerprint(payload),
            expected_state_digest=state.digest(),
            exposure_micros=change.modeled_exposure_micros,
            positive_change_micros=positive_change,
            mandate_revision=m.revision,
        ),
        actor,
        now,
    )
    db.commit()
    return action


def change_from(a: MandateAction) -> GoogleChange:
    draft = ActionDraft.model_validate(a.draft)
    payload = draft.payload
    if payload.get("schema") != "google_search_action_v1":
        raise HTTPException(409, "unsupported action schema")
    change = GoogleChange.model_validate(
        {
            key: payload[key]
            for key in (
                "kind",
                "new_budget_micros",
                "keyword",
                "match_type",
                "modeled_exposure_micros",
            )
            if key in payload
        }
    )
    if (
        draft.kind != change.kind
        or draft.exposure_micros != change.modeled_exposure_micros
        or draft.resource_key != "google-campaign:" + str(payload.get("campaign_id"))
    ):
        raise HTTPException(409, "Google action authorization mismatch")
    for key, length in (("customer_id", 10), ("campaign_id", 32), ("budget_id", 32)):
        value = payload.get(key)
        if (
            not isinstance(value, str)
            or not value.isdigit()
            or not 1 <= len(value) <= length
            or (key == "customer_id" and len(value) != 10)
        ):
            raise HTTPException(409, "Google action resource mismatch")
    return change


def validate_bound_operation(d: ActionDraft, change: GoogleChange, current: GoogleState) -> None:
    expected_change = max(
        0,
        (
            change.new_budget_micros
            if change.new_budget_micros is not None
            else current.budget_micros
        )
        - current.budget_micros,
    )
    if (
        d.payload["customer_id"] != current.customer_id
        or d.payload["campaign_id"] != current.campaign_id
        or d.payload["budget_id"] != current.budget_id
        or d.positive_change_micros != expected_change
        or current.channel != "SEARCH"
        or current.shared_budget
        or current.status == "REMOVED"
    ):
        raise HTTPException(409, "Google current state/accounting/resource mismatch")


def request_preview(a: MandateAction) -> dict[str, Any]:
    d = ActionDraft.model_validate(a.draft)
    change = change_from(a)
    payload = d.payload
    prefix = f"customers/{payload['customer_id']}/"
    if change.kind == "budget_change":
        operation = {
            "campaign_budget_operation": {
                "update": {
                    "resource_name": prefix + f"campaignBudgets/{payload['budget_id']}",
                    "amount_micros": change.new_budget_micros,
                },
                "update_mask": {"paths": ["amount_micros"]},
            }
        }
    elif change.kind in {"pause", "resume"}:
        operation = {
            "campaign_operation": {
                "update": {
                    "resource_name": prefix + f"campaigns/{payload['campaign_id']}",
                    "status": "PAUSED" if change.kind == "pause" else "ENABLED",
                },
                "update_mask": {"paths": ["status"]},
            }
        }
    else:
        operation = {
            "campaign_criterion_operation": {
                "create": {
                    "campaign": prefix + f"campaigns/{payload['campaign_id']}",
                    "negative": True,
                    "keyword": {"text": change.keyword, "match_type": change.match_type},
                }
            }
        }
    return {
        "customer_id": payload["customer_id"],
        "mutate_operations": [operation],
        "partial_failure": False,
        "validate_only": True,
    }


def run_fixture(
    db: Session,
    m: Mandate,
    a: MandateAction,
    adapter: FixtureGoogleActions,
    evidence: SyntheticEvidence,
    request_key: str,
    actor: str,
    now: datetime,
) -> None:
    # No arbitrary live mutation adapter can be substituted into this runtime path.
    if type(adapter) is not FixtureGoogleActions:
        raise HTTPException(409, "only offline fixture adapter is allowed")
    m = mandates.owned(db, m.workspace_id, m.id)
    a = mandates.action(db, m, a.id)
    d = ActionDraft.model_validate(a.draft)
    row = connection(db, m, d.account)
    if row.external_account_id != d.payload.get("customer_id"):
        raise HTTPException(409, "Google action account mismatch")
    if row.generation != d.payload.get("connection_generation"):
        raise HTTPException(409, "Google connection generation changed")
    change = change_from(a)
    current = adapter.read(str(d.payload["campaign_id"]), now)
    validate_bound_operation(d, change, current)
    observed = evidence.model_copy(
        update={"state_digest": current.digest(), "observed_at": current.observed_at}
    )
    mandates.claim(db, m, a, ClaimInput(request_key=request_key, evidence=observed), actor, now)
    # Reacquire locks after the durable claim before dispatch rechecks.
    m = mandates.owned(db, m.workspace_id, m.id)
    a = mandates.action(db, m, a.id)
    row = connection(db, m, d.account)
    if row.external_account_id != d.payload.get("customer_id"):
        raise HTTPException(409, "Google action account mismatch")
    if row.generation != d.payload.get("connection_generation"):
        raise HTTPException(409, "Google connection generation changed")
    current = adapter.read(str(d.payload["campaign_id"]), now)
    validate_bound_operation(d, change, current)
    observed = evidence.model_copy(
        update={"state_digest": current.digest(), "observed_at": current.observed_at}
    )
    mandates.dispatch(db, m, a, a.fence or "", observed, actor, now)
    # Ambiguous outcomes enter reconciliation, never automatic resubmission.
    with suppress(Exception):
        adapter.apply(str(d.payload["campaign_id"]), change)
    m = mandates.owned(db, m.workspace_id, m.id)
    a = mandates.action(db, m, a.id)
    mandates.reconcile(
        db,
        m,
        a,
        ReconcileInput(
            fence=a.fence or "",
            outcome="unknown",
            consumed_micros=0,
            evidence_at=now,
            period_consumed_micros=evidence.period_consumed_micros,
        ),
        actor,
        now,
    )
    db.commit()


def reconcile_fixture(
    db: Session,
    m: Mandate,
    a: MandateAction,
    adapter: FixtureGoogleActions,
    period_consumed_micros: int,
    actor: str,
    now: datetime,
) -> bool:
    if type(adapter) is not FixtureGoogleActions:
        raise HTTPException(409, "only offline fixture adapter is allowed")
    m = mandates.owned(db, m.workspace_id, m.id)
    a = mandates.action(db, m, a.id)
    d = ActionDraft.model_validate(a.draft)
    row = connection(db, m, d.account)
    if row.external_account_id != d.payload.get("customer_id"):
        raise HTTPException(409, "Google action account mismatch")
    if row.generation != d.payload.get("connection_generation"):
        raise HTTPException(409, "Google connection generation changed")
    change = change_from(a)
    current = adapter.read(str(d.payload["campaign_id"]), now)
    if (
        current.customer_id != d.payload["customer_id"]
        or current.campaign_id != d.payload["campaign_id"]
    ):
        raise HTTPException(409, "Google readback ownership mismatch")
    matched = (
        (change.kind == "budget_change" and current.budget_micros == change.new_budget_micros)
        or (change.kind == "pause" and current.status == "PAUSED")
        or (change.kind == "resume" and current.status == "ENABLED")
        or (
            change.kind == "negative_keyword"
            and f"{change.match_type}:{change.keyword}" in current.negative_keywords
        )
    )
    if not matched:
        return False  # Non-match does not prove no side effect; retain reservation.
    if now < mandates.policy(db, m).ends_at:
        mandates.audit(db, m, "simulated_state_matches_exposure_reserved", actor, now, a)
        db.commit()
        return True
    mandates.reconcile(
        db,
        m,
        a,
        ReconcileInput(
            fence=a.fence or "",
            outcome="success",
            consumed_micros=0,
            evidence_at=now,
            period_consumed_micros=period_consumed_micros,
        ),
        actor,
        now,
    )
    db.commit()
    return True
