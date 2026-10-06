"""Owned read projection: compare complete as-of totals, never infer maturity."""

from datetime import timedelta
from decimal import ROUND_HALF_EVEN, localcontext

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.commerce.evidence import digest, lock_workspace
from app.commerce.ledger import DEFINITION
from app.commerce.models import CommerceMeasurementPublication
from app.goals.models import Goal, GoalRevision
from app.goals.schemas import GoalDefinition
from app.outcomes.descriptive_contracts import (
    DescriptiveComparison,
    DescriptiveRequest,
    PublicationLineage,
    Stability,
)
from app.outcomes.owned import Authorize, Clock, now, observe, publication
from app.shopify.security import ShopifyError, utc


def lineage(row: CommerceMeasurementPublication) -> PublicationLineage:
    return PublicationLineage(
        publication_id=row.id,
        manifest_digest=row.manifest_digest,
        source_revision=row.source_revision,
        publication_revision=row.publication_revision,
        published_at=utc(row.published_at),
        watermark=utc(row.source_window_end),
    )


def validate_manifest(row: CommerceMeasurementPublication) -> None:
    expected = {
        "workspace_id": row.workspace_id,
        "store_id": row.store_id,
        "generation": row.generation,
        "privacy_epoch": row.privacy_epoch,
        "source_revision": row.source_revision,
        "publication_revision": row.publication_revision,
        "source_window_start": utc(row.source_window_start).isoformat(),
        "source_window_end": utc(row.source_window_end).isoformat(),
        "source_watermark": utc(row.source_window_end).isoformat(),
        "as_of": utc(row.published_at).isoformat(),
        "definition": DEFINITION,
        "definition_digest": digest(DEFINITION),
        "source": "shopify",
        "unit": "monetary_micros",
        "grain": "store_local_day",
        "attribution": "not_applicable_store_total",
    }
    if any(row.manifest.get(key) != value for key, value in expected.items()):
        raise HTTPException(409, "measurement binding unavailable")
    if utc(row.source_window_start) > utc(row.source_window_end) or utc(
        row.source_window_end
    ) > utc(row.published_at):
        raise HTTPException(409, "measurement time unavailable")
    parts = row.manifest.get("partitions")
    if (
        not isinstance(parts, list)
        or len(parts) > 400
        or any(not isinstance(p, dict) for p in parts)
    ):
        raise HTTPException(409, "measurement partitions unavailable")
    for item in parts:
        if str(item.get("state", "")).startswith("complete_") and (
            type(item.get("entry_count")) is not int or item["entry_count"] < 0
        ):
            raise HTTPException(409, "measurement count unavailable")


def compare(
    db: Session, wid: int, body: DescriptiveRequest, authorize: Authorize, clock: Clock = now
) -> DescriptiveComparison:
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT set_config('statement_timeout', '2000', true)"))
    try:
        lock_workspace(db, wid, active=True)
    except ShopifyError:
        raise HTTPException(404, "workspace unavailable") from None
    authorize()  # Fresh session/owner after waiting for workspace/privacy fence.
    body = DescriptiveRequest.model_validate(body.model_dump())
    row, store = publication(db, wid, body.publication_id, clock)
    goal = db.scalar(
        select(Goal)
        .where(Goal.id == body.goal_id, Goal.workspace_id == wid)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if goal is None or goal.workspace_id != wid:
        raise HTTPException(404, "goal unavailable")
    if goal.revision != body.expected_goal_revision:
        raise HTTPException(409, "goal revision changed")
    revision = db.get(GoalRevision, (goal.id, goal.revision), populate_existing=True)
    if revision is None or revision.workspace_id != wid or revision.definition is None:
        raise HTTPException(409, "goal definition unavailable")
    try:
        definition = GoalDefinition.model_validate(revision.definition)
        if definition.store_id != store.id:
            raise HTTPException(409, "goal source mismatch")
        validate_manifest(row)
        evaluated = utc(clock())
        before, after = (
            observe(row, store, body.before_start, body.before_end),
            observe(row, store, body.after_start, body.after_end),
        )
        reasons: set[str] = set()
        if revision.confirmed_at is None:
            reasons.add("goal_unconfirmed")
        if (definition.target_window.currency, definition.target_window.time_zone) != (
            store.currency,
            store.time_zone,
        ):
            reasons.add("goal_measurement_basis_mismatch")
        if row.manifest.get("definition_digest") != digest(DEFINITION) or (
            before.basis.currency,
            before.basis.time_zone,
        ) != (store.currency, store.time_zone):
            reasons.add("measurement_basis_changed")
        latest = db.scalar(
            select(CommerceMeasurementPublication.id)
            .where(
                CommerceMeasurementPublication.workspace_id == wid,
                CommerceMeasurementPublication.store_id == store.id,
            )
            .order_by(CommerceMeasurementPublication.publication_revision.desc())
            .limit(1)
        )
        if latest != row.id or row.source_revision != store.revision:
            reasons.add("source_revision_changed")
        if store.status != "active" or store.window_end is not None:
            reasons.add("source_not_ready")
        if utc(row.published_at) > evaluated or utc(row.source_window_end) > evaluated:
            reasons.add("future_evidence")
        if evaluated - utc(row.source_window_end) > timedelta(hours=24):
            reasons.add("stale_source")
        if (body.before_end - body.before_start) != (body.after_end - body.after_start):
            reasons.add("unequal_local_days")
        for observation in (before, after):
            if not observation.coverage.complete or observation.value is None:
                reasons.add("measurement_coverage_incomplete")
            if observation.coverage.correction_state != "settled_as_of":
                reasons.add("correction_unresolved")
            if observation.window.end_utc > evaluated or observation.window.end_utc > utc(
                row.source_window_end
            ):
                reasons.add("window_not_closed")
        stability = Stability(status="not_requested", examined_days=0)
        if body.prior_publication_id is not None:
            prior, prior_store = publication(db, wid, body.prior_publication_id, clock)
            if prior_store.id != store.id:
                raise HTTPException(404, "prior measurement source unavailable")
            validate_manifest(prior)
            p_before, p_after = (
                observe(prior, prior_store, body.before_start, body.before_end),
                observe(prior, prior_store, body.after_start, body.after_end),
            )
            blockers: set[str] = set()
            if prior.id == row.id or not (
                prior.publication_revision < row.publication_revision
                and utc(prior.published_at) < utc(row.published_at)
                and utc(prior.source_window_end) < utc(row.source_window_end)
            ):
                blockers.add("independent_reconciliation_unavailable")
            if (prior.generation, prior.privacy_epoch) != (
                row.generation,
                row.privacy_epoch,
            ) or p_before.basis != before.basis:
                blockers.add("source_basis_changed")
            if reasons:
                blockers.add("current_observation_insufficient")
            for observation in (p_before, p_after):
                if (
                    not observation.coverage.complete
                    or observation.coverage.correction_state != "settled_as_of"
                ):
                    blockers.add("prior_coverage_incomplete")
                if observation.window.end_utc > utc(prior.source_window_end):
                    blockers.add("prior_window_not_closed")
            days = set(before.coverage.covered_days + after.coverage.covered_days)

            def partitions(record: CommerceMeasurementPublication) -> dict[str, object]:
                return {
                    p["day"]: p
                    for p in record.manifest["partitions"]
                    if p["day"] in {d.isoformat() for d in days}
                }

            stability = Stability(
                status="unavailable"
                if blockers
                else (
                    "unchanged_observed"
                    if partitions(prior) == partitions(row)
                    else "revised_observed"
                ),
                prior=lineage(prior),
                examined_days=0 if blockers else len(days),
                reasons=tuple(sorted(blockers)),
            )
        absolute = relative = None
        warnings = {
            "maturity_unqualified",
            "store_total_not_ad_attribution",
            "confounder_coverage_unknown",
            "future_corrections_possible",
        }
        if not reasons and before.value is not None and after.value is not None:
            with localcontext() as context:
                context.prec = 60
                context.rounding = ROUND_HALF_EVEN
                absolute = after.value - before.value
                if before.value > 0:
                    relative = absolute / before.value
                else:
                    warnings.add("baseline_zero" if before.value == 0 else "baseline_negative")
        authorize()
        return DescriptiveComparison(
            workspace_id=wid,
            goal_id=goal.id,
            goal_revision=goal.revision,
            goal_digest=digest(definition.model_dump(mode="json")),
            current=lineage(row),
            generation=row.generation,
            privacy_epoch=row.privacy_epoch,
            evaluated_at=evaluated,
            status="insufficient" if reasons else "available_as_of",
            before=before,
            after=after,
            absolute_difference=absolute,
            relative_difference=relative,
            reasons=tuple(sorted(reasons)),
            warnings=tuple(sorted(warnings)),
            stability=stability,
        )
    except (ValueError, KeyError, TypeError):
        raise HTTPException(409, "stored measurement evidence invalid") from None
