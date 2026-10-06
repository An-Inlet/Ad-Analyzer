"""Bounded owned facts about retained terminal imports, not independent rescans."""

from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.commerce.evidence import digest, lock_workspace
from app.commerce.models import CommerceMeasurementPublication
from app.goals.models import Goal, GoalRevision
from app.goals.schemas import GoalDefinition
from app.outcomes.contracts import Window
from app.outcomes.descriptive import lineage, validate_manifest
from app.outcomes.owned import Authorize, Clock, now, observe, publication
from app.outcomes.reconciliation_contracts import (
    DayRevisionObservation,
    ReconciliationObservations,
    ReconciliationRequest,
    TerminalObservation,
)
from app.shopify.security import ShopifyError, utc


def collect_owned_reconciliations(
    db: Session, wid: int, body: ReconciliationRequest, authorize: Authorize, clock: Clock = now
) -> ReconciliationObservations:
    body = ReconciliationRequest.model_validate(body.model_dump())
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT set_config('statement_timeout', '2000', true)"))
    try:
        lock_workspace(db, wid, active=True)
    except ShopifyError:
        raise HTTPException(404, "workspace unavailable") from None
    authorize()
    anchor, store = publication(db, wid, body.latest_publication_id, clock)
    goal = db.scalar(
        select(Goal)
        .where(Goal.id == body.goal_id, Goal.workspace_id == wid)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if goal is None:
        raise HTTPException(404, "goal unavailable")
    if goal.revision != body.expected_goal_revision:
        raise HTTPException(409, "goal revision changed")
    revision = db.get(GoalRevision, (goal.id, goal.revision), populate_existing=True)
    if revision is None or revision.workspace_id != wid or revision.confirmed_at is None:
        raise HTTPException(409, "confirmed goal unavailable")
    try:
        definition = GoalDefinition.model_validate(revision.definition)
        if (
            definition.store_id,
            definition.target_window.currency,
            definition.target_window.time_zone,
        ) != (store.id, store.currency, store.time_zone):
            raise HTTPException(409, "goal measurement basis mismatch")
        evaluated = utc(clock())
        rows = list(
            db.scalars(
                select(CommerceMeasurementPublication)
                .where(
                    CommerceMeasurementPublication.workspace_id == wid,
                    CommerceMeasurementPublication.store_id == store.id,
                    CommerceMeasurementPublication.generation == anchor.generation,
                    CommerceMeasurementPublication.privacy_epoch == anchor.privacy_epoch,
                )
                .order_by(CommerceMeasurementPublication.publication_revision.desc())
                .limit(17)
            )
        )
        if not rows or rows[0].id != anchor.id:
            raise HTTPException(409, "latest publication changed")
        observations = []
        partitions = []
        unreadable = duplicates = 0
        seen: set[str] = set()
        for candidate in reversed(rows[:16]):
            try:
                row, _ = publication(db, wid, candidate.id, clock)
            except HTTPException as exc:
                if exc.status_code != 404 or candidate.id == anchor.id:
                    raise
                unreadable += 1
                continue
            validate_manifest(row)
            expected_completion = digest(
                [
                    "inlet.commerce-completion.v1",
                    store.id,
                    row.generation,
                    row.privacy_epoch,
                    utc(row.source_window_start).isoformat(),
                    utc(row.source_window_end).isoformat(),
                    row.source_revision,
                ]
            )
            if (
                row.completion_digest != expected_completion
                or row.manifest.get("source_range_semantics") != "updated_at_inclusive"
            ):
                raise HTTPException(409, "terminal completion binding unavailable")
            observation = observe(row, store, body.start, body.end)
            if (
                (observation.basis.currency, observation.basis.time_zone)
                != (store.currency, store.time_zone)
                or utc(row.published_at) > evaluated
                or observation.window.end_utc > evaluated
            ):
                raise HTTPException(409, "measurement basis or time unavailable")
            if row.completion_digest in seen:
                duplicates += 1
                continue
            seen.add(row.completion_digest)
            observations.append(
                TerminalObservation(
                    lineage=lineage(row),
                    completion_digest=row.completion_digest,
                    source_window_start=utc(row.source_window_start),
                    observation=observation,
                )
            )
            partitions.append({p["day"]: p for p in row.manifest["partitions"]})
        days = []
        for offset in range((body.end - body.start).days):
            day = body.start + timedelta(days=offset)
            key = day.isoformat()
            comparable = changed = state_changes = 0
            maximum = last_change = None
            complete = bool(partitions)
            for item in partitions:
                complete &= str(item.get(key, {}).get("state", "missing")).startswith("complete_")
            for index in range(1, len(partitions)):
                before, after = partitions[index - 1].get(key, {}), partitions[index].get(key, {})
                bs, ats = before.get("state", "missing"), after.get("state", "missing")
                state_changes += bs != ats
                if str(bs).startswith("complete_") and str(ats).startswith("complete_"):
                    comparable += 1
                    delta = abs(after["net_sales_micros"] - before["net_sales_micros"])
                    maximum = max(maximum or 0, delta)
                    if before != after:
                        changed += 1
                        last_change = observations[index].lineage.published_at
            end = Window.local(day, day + timedelta(days=1), store.time_zone).end_utc
            days.append(
                DayRevisionObservation(
                    day=day,
                    comparable_pairs=comparable,
                    changed_pairs=changed,
                    coverage_state_changes=state_changes,
                    maximum_absolute_value_change_micros=maximum,
                    last_change_observed_at=last_change,
                    last_change_discovery_lag_seconds=(
                        max(0, int((last_change - end).total_seconds())) if last_change else None
                    ),
                    status="revised_observed"
                    if changed
                    else (
                        "unchanged_observed"
                        if comparable and complete and not unreadable
                        else "insufficient_observations"
                    ),
                )
            )
        publication(db, wid, anchor.id, clock)  # Retention may expire during a read.
        authorize()
        result = ReconciliationObservations(
            workspace_id=wid,
            store_id=store.id,
            goal_id=goal.id,
            goal_revision=goal.revision,
            goal_digest=digest(definition.model_dump(mode="json")),
            generation=anchor.generation,
            privacy_epoch=anchor.privacy_epoch,
            evaluated_at=evaluated,
            source_current=anchor.source_revision == store.revision
            and store.status == "active"
            and store.window_end is None,
            source_age_seconds=max(
                0, int((evaluated - utc(anchor.source_window_end)).total_seconds())
            ),
            observations=tuple(observations),
            days=tuple(days),
            truncated=len(rows) > 16,
            unreadable_observations=unreadable,
            duplicate_completions_ignored=duplicates,
        )
        if len(result.model_dump_json().encode()) > 512 * 1024:
            raise HTTPException(409, "observation output bound exceeded")
        return result
    except (ValueError, KeyError, TypeError):
        raise HTTPException(409, "stored reconciliation evidence invalid") from None
