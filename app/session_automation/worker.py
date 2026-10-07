"""Bounded original-session worker; no exact-human approval is fabricated."""

from collections.abc import Callable
from contextlib import suppress
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.automation import AutomationControlKey, AutomationControlService
from app.optimization_candidates import review_bridge, selection
from app.optimization_candidates import service as candidates
from app.optimization_candidates.models import CandidateResult
from app.optimization_candidates.review_contracts import CandidateReviewIntent
from app.publication import optimization
from app.session_automation import admission, service
from app.session_automation.models import SessionAutomationRun
from app.session_automation.runtime import SessionAutomationRuntime, get_session_automation_runtime
from app.shopify.security import utc


def advance(engine: Engine, wid: int, identifier: str, runtime: SessionAutomationRuntime) -> str:
    """One bounded selection pass. Provider claims are never reclaimed or replayed."""
    with Session(engine) as db:
        row, principal, policy, _ = service.current(db, wid, identifier, runtime)
        if not AutomationControlService(db).master_enabled(AutomationControlKey.ALL_DATA_SYNCS):
            return "blocked"
        if utc(row.next_due_at) > runtime.clock():
            return "not_due"
        row.next_due_at = runtime.clock() + timedelta(seconds=policy.cadence_seconds)
        db.commit()
        try:
            # Original current authority is reloaded around selection's external reads.
            row, principal, policy, _ = service.current(db, wid, identifier, runtime)
            _, jobs = selection.enqueue_candidate_selection(
                db,
                principal,
                wid,
                service.binding(row),
                policy.candidate_policy,
                runtime.selected(service.binding(row)),
            )
            identifiers = [job.id for job in jobs]
            db.commit()
            completed = 0
            for job_id in identifiers:
                service.current(db, wid, identifier, runtime)
                db.commit()
                candidates.process(engine, wid, job_id, runtime.review.candidate)
                row, principal, policy, _ = service.current(db, wid, identifier, runtime)
                result = db.scalar(
                    select(CandidateResult).where(
                        CandidateResult.workspace_id == wid,
                        CandidateResult.job_id == job_id,
                    )
                )
                if result is None or result.decision.get("status") != "suggested":
                    continue
                intent = CandidateReviewIntent(
                    result_id=result.id, expected_decision_digest=result.decision_digest
                )
                prepared = review_bridge.prepare_candidate_review(
                    db, principal, wid, intent, runtime.review
                )
                # Distinct server admission is based on the explicit Start, current
                # mandate and semantic producer. There is no approve_optimization call.
                run = admission.admit(db, wid, identifier, prepared.review_id, runtime)
                execution = admission.execution_runtime(db, wid, identifier, runtime)
                claim = optimization.claim_step(
                    db, wid, run.id, principal.user.id, execution, runtime.clock
                )
                if claim is not None:
                    optimization.execute_claim(
                        db, claim, principal.user.id, execution, runtime.clock
                    )
                    completed += 1
                db.commit()
            row, _, _, _ = service.current(db, wid, identifier, runtime)
            row.state, row.reason = "waiting", "ready" if completed else "evidence_not_ready"
            db.commit()
            return "completed" if completed else "waiting"
        except HTTPException as exc:
            db.rollback()
            row = service.load(db, wid, identifier)
            # Diagnostics cannot revive a concurrently stopped run.
            if row.stopped_at is None:
                row.state = "blocked"
                row.reason = (
                    "decision_already_used"
                    if exc.detail == "decision_already_used"
                    else "financial_proof_unavailable"
                )
                db.commit()
            return "blocked"
        except Exception:
            db.rollback()
            # No raw exception/provider data are stored. Backoff was committed before
            # IO; a later pass can repeat read work, never an original provider claim.
            return "retry"


def run_due(
    engine: Engine,
    factory: Callable[[], SessionAutomationRuntime | None] = get_session_automation_runtime,
    *,
    limit: int = 10,
) -> dict[str, int]:
    with Session(engine) as controls:
        if not AutomationControlService(controls).master_enabled(
            AutomationControlKey.ALL_DATA_SYNCS
        ):
            return {}
    runtime = factory()
    if runtime is None:
        return {}
    if not 1 <= limit <= 100:
        raise ValueError("bounded automation batch required")
    with Session(engine) as db:
        if not AutomationControlService(db).master_enabled(AutomationControlKey.ALL_DATA_SYNCS):
            return {}
        due = (
            SessionAutomationRun.environment == runtime.review.execution.environment,
            SessionAutomationRun.stopped_at.is_(None),
            SessionAutomationRun.expires_at > runtime.clock(),
            SessionAutomationRun.next_due_at <= runtime.clock(),
        )
        tenants = list(
            db.scalars(
                select(SessionAutomationRun.workspace_id)
                .where(*due)
                .group_by(SessionAutomationRun.workspace_id)
                .order_by(
                    func.min(SessionAutomationRun.next_due_at), SessionAutomationRun.workspace_id
                )
                .limit(limit)
            )
        )
        selected = []
        for wid in tenants:
            identifier = db.scalar(
                select(SessionAutomationRun.id)
                .where(
                    *due,
                    SessionAutomationRun.workspace_id == wid,
                )
                .order_by(SessionAutomationRun.next_due_at, SessionAutomationRun.id)
                .limit(1)
            )
            if identifier:
                selected.append((wid, identifier))
    results: dict[str, int] = {}
    for wid, identifier in selected:
        try:
            result = advance(engine, wid, identifier, runtime)
        except Exception:
            result = "blocked"
            # Closure/deletion may already have invalidated this row. Continue
            # other workspaces; this maintenance path grants no forward authority.
            with suppress(Exception):
                defer_failed_admission(engine, wid, identifier, runtime)
        results[result] = results.get(result, 0) + 1
    return results


def defer_failed_admission(
    engine: Engine, wid: int, identifier: str, runtime: SessionAutomationRuntime
) -> None:
    """Non-authorizing scheduling maintenance after failure before the first fence.

    A revoked original session must not occupy a workspace's first due slot forever.
    Preserve its audit and every claim/hold; only defer the failed read/admission pass.
    """
    from app.workspaces.locking import lock_workspace_row

    with Session(engine) as db:
        lock_workspace_row(db, wid)
        row = service.load(db, wid, identifier)
        db.refresh(row, with_for_update=True)
        if row.stopped_at is None and utc(row.next_due_at) <= runtime.clock():
            row.next_due_at = runtime.clock() + timedelta(seconds=60)
            row.state, row.reason = "blocked", "original_session_ended"
            db.commit()
