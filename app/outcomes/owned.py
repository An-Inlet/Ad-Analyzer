"""Persist/read actual owned provider evidence and aggregate commerce observations."""

import json
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.commerce.evidence import digest, lock_workspace, read_publication
from app.commerce.models import CommerceMeasurementPublication, CommerceStore
from app.goals.models import GoalRevision
from app.goals.schemas import GoalDefinition
from app.outcomes.contracts import Coverage, MetricBasis, Observation, SourceScope, Window
from app.outcomes.models import ActionOutcomeAssessment
from app.outcomes.owned_contracts import AssessmentRequest, OwnedAssessment, OwnedReceiptLineage
from app.publication.coordinator import read_owned_outcome_receipt
from app.publication.execution_contracts import NormalizedProviderReceipt
from app.shopify.security import ShopifyError, utc

Clock = Callable[[], datetime]
Authorize = Callable[[], None]
POLICY = {
    "id": "commerce_as_of_v1",
    "maturity": "unavailable",
    "attribution": "store_total",
    "causal": False,
}
MAX_ASSESSMENT_BYTES = 256 * 1024


def now() -> datetime:
    return datetime.now(UTC)


def publication(
    db: Session, wid: int, identifier: str, clock: Clock
) -> tuple[CommerceMeasurementPublication, CommerceStore]:
    row = db.scalar(
        select(CommerceMeasurementPublication).where(
            CommerceMeasurementPublication.id == identifier,
            CommerceMeasurementPublication.workspace_id == wid,
        )
    )
    if row is None:
        raise HTTPException(404, "measurement publication unavailable")
    try:
        # Clock is evaluated after acquiring the workspace/source fence, not at route entry.
        read_publication(db, wid, row.store_id, row.id, now=clock())
    except ShopifyError as error:
        if error.code == "commerce_publication_binding_invalid":
            raise HTTPException(409, "measurement publication binding invalid") from None
        raise HTTPException(404, "measurement publication unavailable") from None
    store = db.get(CommerceStore, row.store_id)
    if store is None or store.workspace_id != wid:
        raise HTTPException(404, "measurement source unavailable")
    return row, store


def observe(
    row: CommerceMeasurementPublication, store: CommerceStore, start: date, end: date
) -> Observation:
    m = row.manifest
    if (
        m.get("schema_version") != "inlet.commerce-publication.v1"
        or m.get("maturity") != "unavailable"
    ):
        raise HTTPException(409, "unsupported measurement publication")
    parts = m.get("partitions")
    if not isinstance(parts, list) or len(parts) > 400:
        raise HTTPException(409, "invalid measurement partitions")
    by_day = {}
    for p in parts:
        if not isinstance(p, dict) or set(p) != {"day", "state", "net_sales_micros", "entry_count"}:
            raise HTTPException(409, "invalid measurement partition")
        day = date.fromisoformat(p["day"])
        if day in by_day or p["state"] not in {
            "complete_zero",
            "complete_nonzero",
            "missing",
            "suppressed",
        }:
            raise HTTPException(409, "invalid measurement coverage")
        if p["state"].startswith("complete_"):
            if type(p["net_sales_micros"]) is not int or type(p["entry_count"]) is not int:
                raise HTTPException(409, "invalid measurement amount")
            if (p["net_sales_micros"] == 0) != (p["state"] == "complete_zero"):
                raise HTTPException(409, "invalid zero measurement")
        elif p["net_sales_micros"] is not None:
            raise HTTPException(409, "missing measurement has a value")
        by_day[day] = p
    days = [start + timedelta(days=n) for n in range((end - start).days)]
    covered = tuple(
        day for day in days if day in by_day and by_day[day]["state"].startswith("complete_")
    )
    complete = len(covered) == len(days)
    reasons = ("maturity_policy_unavailable",) + (
        () if complete else ("measurement_coverage_incomplete",)
    )
    window = Window.local(start, end, store.time_zone)
    return Observation(
        source=SourceScope(
            workspace_id=row.workspace_id,
            provider="shopify",
            connection_id=store.connection_id,
            source_id=store.id,
            generation=row.generation,
        ),
        basis=MetricBasis(
            definition="shopify_merchandise_net_sales_v1",
            definition_digest=m["definition_digest"],
            currency=m["currency"],
            unit="micros",
            grain="store",
            entity_id=store.id,
            time_zone=m["time_zone"],
            time_basis="cumulative",
            attribution="not_applicable_store_total",
            attribution_digest=None,
            maturity_policy=None,
        ),
        window=window,
        snapshot_id=row.id,
        snapshot_digest=row.manifest_digest,
        data_revision=row.source_revision,
        as_of=utc(row.published_at),
        value=Decimal(sum(by_day[d]["net_sales_micros"] for d in covered)) if complete else None,
        coverage=Coverage(
            complete=complete,
            covered_days=covered,
            zero_days=tuple(d for d in covered if by_day[d]["state"] == "complete_zero"),
            mature_through=None,
            fresh_through=utc(row.source_window_end),
            correction_state=m["correction_status"],
            reasons=reasons,
        ),
        privacy="available",
    )


def build(
    db: Session,
    wid: int,
    body: AssessmentRequest,
    receipt: NormalizedProviderReceipt,
    row: CommerceMeasurementPublication,
    store: CommerceStore,
    evaluated_at: datetime,
) -> OwnedAssessment:
    before, after = (
        observe(row, store, body.before_start, body.before_end),
        observe(row, store, body.after_start, body.after_end),
    )
    reasons = {"maturity_policy_unavailable"}
    for observation in (before, after):
        reasons.update(observation.coverage.reasons)
    if receipt.purpose == "create_paused":
        reasons.add("activation_unverified")
    if receipt.outcome != "verified_effect":
        reasons.add(
            {
                "verified_target_state": "target_state_not_action_effect",
                "unknown": "effect_unverified",
                "conflict": "effect_conflict",
                "verified_no_effect": "verified_no_effect",
            }[receipt.outcome]
        )
    if receipt.effective_time_evidence != "authoritative_interval":
        reasons.add("effective_time_unknown")
    if receipt.observed_at > evaluated_at or utc(row.published_at) > evaluated_at:
        reasons.add("future_evidence")
    if evaluated_at - utc(row.source_window_end) > timedelta(hours=24):
        reasons.add("stale_source")
    if (body.before_end - body.before_start) != (body.after_end - body.after_start):
        reasons.add("unequal_window_lengths")
    goal = db.get(GoalRevision, (receipt.goal_id, receipt.goal_revision))
    goal_digest = None
    if (
        goal is None
        or goal.workspace_id != wid
        or goal.definition is None
        or goal.confirmed_at is None
    ):
        reasons.add("goal_revision_unavailable")
    else:
        definition = GoalDefinition.model_validate(goal.definition)
        goal_digest = digest(definition.model_dump(mode="json"))
        if definition.store_id != store.id:
            reasons.add("goal_source_mismatch")
        if (definition.target_window.currency, definition.target_window.time_zone) != (
            store.currency,
            store.time_zone,
        ):
            reasons.add("goal_measurement_basis_mismatch")
    lineage = OwnedReceiptLineage(
        receipt_id=receipt.receipt_id,
        attempt_id=receipt.attempt_id,
        sequence=receipt.sequence,
        receipt_digest=receipt.receipt_digest,
        projection_digest=digest(["inlet.owned-receipt.v1", receipt.model_dump(mode="json")]),
        request_digest=receipt.request_digest,
        review_digest=receipt.review_digest,
        plan_digest=receipt.plan_digest,
        fence=receipt.fence,
        goal_id=receipt.goal_id,
        goal_revision=receipt.goal_revision,
        goal_digest=goal_digest,
        mandate_id=receipt.mandate.mandate_id,
        mandate_revision=receipt.mandate.revision,
        consent_id=receipt.mandate.consent_id,
        mandate_digest=receipt.mandate.policy_digest,
        account_id=receipt.account.account.account_id,
        connection_id=receipt.account.account.connection_id,
        connection_version=receipt.account.connection_version,
        platform=receipt.account.account.platform,
        purpose=receipt.purpose,
        outcome=receipt.outcome,
        observed_at=receipt.observed_at,
        effective_time_evidence=receipt.effective_time_evidence,
    )
    inputs = digest(
        [
            "inlet.owned-assessment-input.v2",
            wid,
            body.model_dump(mode="json"),
            lineage.model_dump(mode="json"),
            row.manifest_digest,
            digest(POLICY),
        ]
    )
    return OwnedAssessment(
        workspace_id=wid,
        environment=receipt.environment,
        receipt=lineage,
        publication_id=row.id,
        publication_digest=row.manifest_digest,
        generation=row.generation,
        privacy_epoch=row.privacy_epoch,
        policy_id=body.policy_id,
        policy_digest=digest(POLICY),
        input_digest=inputs,
        before=before,
        after=after,
        evaluated_at=evaluated_at,
        reasons=tuple(sorted(reasons)),
        warnings=("confounder_coverage_unknown", "store_total_not_ad_attribution")
        + (("contract_test_only",) if receipt.environment == "contract_test" else ()),
    )


def create(
    db: Session,
    wid: int,
    actor: str,
    body: AssessmentRequest,
    authorize: Authorize,
    clock: Clock = now,
) -> ActionOutcomeAssessment:
    try:
        lock_workspace(db, wid, active=True)
    except ShopifyError:
        raise HTTPException(404, "workspace unavailable") from None
    body = AssessmentRequest.model_validate(body.model_dump())
    receipt = read_owned_outcome_receipt(db, wid, body.attempt_id, actor)
    if receipt is None:
        raise HTTPException(409, "provider receipt unavailable")
    authorize()  # fresh current identity/session after any blocking locks
    row, store = publication(db, wid, body.publication_id, clock)
    try:
        assessment = build(db, wid, body, receipt, row, store, utc(clock()))
    except (ValueError, KeyError, TypeError, ValidationError):
        raise HTTPException(409, "stored measurement evidence invalid") from None
    existing = db.scalar(
        select(ActionOutcomeAssessment).where(
            ActionOutcomeAssessment.workspace_id == wid,
            ActionOutcomeAssessment.input_digest == assessment.input_digest,
        )
    )
    if existing is not None:
        return existing
    payload = assessment.model_dump(mode="json")
    if len(json.dumps(payload, separators=(",", ":")).encode()) > MAX_ASSESSMENT_BYTES:
        raise HTTPException(413, "assessment exceeds bounded size")
    result = ActionOutcomeAssessment(
        id=uuid4().hex,
        workspace_id=wid,
        attempt_id=receipt.attempt_id,
        receipt_id=receipt.receipt_id,
        receipt_sequence=receipt.sequence,
        receipt_digest=receipt.receipt_digest,
        projection_digest=assessment.receipt.projection_digest,
        publication_id=row.id,
        generation=row.generation,
        privacy_epoch=row.privacy_epoch,
        environment=receipt.environment,
        policy_id=body.policy_id,
        policy_digest=assessment.policy_digest,
        input_digest=assessment.input_digest,
        assessment_digest=digest(payload),
        assessment=payload,
        created_at=assessment.evaluated_at,
    )
    db.add(result)
    db.flush()
    return result


def read(
    db: Session, wid: int, identifier: str, actor: str, authorize: Authorize, clock: Clock = now
) -> dict[str, object]:
    try:
        lock_workspace(db, wid, active=True)
    except ShopifyError:
        raise HTTPException(404, "workspace unavailable") from None
    row = db.scalar(
        select(ActionOutcomeAssessment)
        .where(
            ActionOutcomeAssessment.id == identifier, ActionOutcomeAssessment.workspace_id == wid
        )
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise HTTPException(404, "assessment unavailable")
    latest = read_owned_outcome_receipt(db, wid, row.attempt_id, actor)
    authorize()
    source, _ = publication(db, wid, row.publication_id, clock)
    if source.generation != row.generation or source.privacy_epoch != row.privacy_epoch:
        raise HTTPException(404, "assessment source unavailable")
    if digest(row.assessment) != row.assessment_digest:
        raise HTTPException(409, "assessment integrity unavailable")
    try:
        assessment = OwnedAssessment.model_validate(row.assessment)
    except ValidationError:
        raise HTTPException(409, "assessment schema unavailable") from None
    if (
        assessment.workspace_id != wid
        or assessment.publication_id != source.id
        or assessment.publication_digest != source.manifest_digest
        or assessment.receipt.receipt_id != row.receipt_id
        or assessment.receipt.attempt_id != row.attempt_id
        or assessment.receipt.sequence != row.receipt_sequence
        or assessment.receipt.receipt_digest != row.receipt_digest
        or assessment.receipt.projection_digest != row.projection_digest
        or assessment.environment != row.environment
        or assessment.input_digest != row.input_digest
        or assessment.generation != row.generation
        or assessment.privacy_epoch != row.privacy_epoch
        or assessment.policy_id != row.policy_id
        or assessment.policy_digest != row.policy_digest
        or assessment.evaluated_at != utc(row.created_at)
    ):
        raise HTTPException(409, "assessment binding unavailable")
    current = latest is not None and (
        latest.receipt_id,
        latest.receipt_digest,
        latest.sequence,
    ) == (row.receipt_id, row.receipt_digest, row.receipt_sequence)
    if (
        current
        and latest is not None
        and digest(["inlet.owned-receipt.v1", latest.model_dump(mode="json")])
        != row.projection_digest
    ):
        raise HTTPException(409, "assessment receipt projection unavailable")
    return {
        "assessment_id": row.id,
        "assessment_digest": row.assessment_digest,
        "assessment": assessment.model_dump(mode="json"),
        "current": current,
        "current_comparison_available": False,
        "current_reasons": [] if current else ["receipt_superseded"],
    }
