from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from typing import Literal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ads.enums import AdvertisingPlatform, RecommendationStatus
from app.ads.models import Recommendation, RecommendationAudit
from app.analysis.models import AnalysisRun
from app.optimizer.recommendations import Finding

RecommendationScopeType = Literal[
    "account",
    "campaign",
    "ad_group",
    "keyword",
    "search_term",
]

ACTIVE_STATUSES = (
    RecommendationStatus.PENDING_REVIEW,
    RecommendationStatus.APPROVED,
    RecommendationStatus.EXECUTED_DRY_RUN,
)
NON_ACTIONABLE_FINDINGS = frozenset({"stale_data", "insufficient_data"})
MAX_RECOMMENDATIONS_PER_RUN = 100
RECOMMENDATION_LIFETIME = timedelta(days=14)
REJECTION_COOLDOWN = timedelta(days=14)
GENERATOR_VERSION = "v1"

_SEVERITY_PRIORITY = {"high": 0, "medium": 1, "low": 2}
_CONFIDENCE = {
    "high": Decimal("0.8000"),
    "medium": Decimal("0.7000"),
    "low": Decimal("0.6000"),
}


@dataclass(frozen=True)
class RecommendationCandidate:
    workspace_id: int
    platform: AdvertisingPlatform
    account_id: int
    campaign_id: int | None
    scope_type: RecommendationScopeType
    scope_id: int
    scope_label: str
    source_text_redacted: bool
    finding: Finding
    impact_micros: int


@dataclass(frozen=True)
class RecommendationGenerationResult:
    recommendations: tuple[Recommendation, ...]
    created_count: int
    deduplicated_count: int
    non_actionable_count: int
    capped_count: int


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _review_action(candidate: RecommendationCandidate) -> str:
    finding_code = candidate.finding.code
    if (
        candidate.scope_type == "search_term"
        and finding_code == "spend_without_platform_conversions"
    ):
        return "review_negative_keyword_candidate"
    if (
        candidate.scope_type == "keyword"
        and finding_code == "spend_without_platform_conversions"
    ):
        return "review_keyword_status_or_match_type"
    if finding_code in {
        "spend_without_conversions",
        "spend_without_platform_conversions",
    }:
        return "review_targeting_and_conversion_tracking"
    if finding_code == "low_ctr":
        return "review_relevance_and_creative"
    if finding_code == "cpa_regression":
        return "review_efficiency_regression"
    if finding_code == "unusual_spend_change":
        return "review_spend_shift"
    if finding_code == "unusual_traffic_change":
        return "review_traffic_shift"
    return "review_performance_signal"


def _deduplication_key(candidate: RecommendationCandidate, review_action: str) -> str:
    components = (
        GENERATOR_VERSION,
        str(candidate.workspace_id),
        candidate.platform.value,
        str(candidate.account_id),
        str(candidate.campaign_id or ""),
        candidate.scope_type,
        str(candidate.scope_id),
        candidate.finding.code,
        review_action,
    )
    return sha256("\x1f".join(components).encode()).hexdigest()


def _candidate_order(candidate: RecommendationCandidate) -> tuple[object, ...]:
    return (
        _SEVERITY_PRIORITY.get(candidate.finding.severity, 99),
        -candidate.impact_micros,
        candidate.account_id,
        candidate.campaign_id or 0,
        candidate.scope_type,
        candidate.scope_id,
        candidate.finding.code,
    )


class RecommendationGenerationService:
    """Persist bounded deterministic proposals without invoking an executor."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def generate(
        self,
        candidates: list[RecommendationCandidate] | tuple[RecommendationCandidate, ...],
        *,
        source_analysis_run_id: int,
        as_of: datetime,
        limit: int = MAX_RECOMMENDATIONS_PER_RUN,
    ) -> RecommendationGenerationResult:
        if limit < 1 or limit > MAX_RECOMMENDATIONS_PER_RUN:
            raise ValueError("recommendation generation limit must be between 1 and 100")
        source_run = self.session.get(AnalysisRun, source_analysis_run_id)
        if source_run is None or any(
            candidate.workspace_id != source_run.workspace_id for candidate in candidates
        ):
            raise ValueError("invalid recommendation source analysis run")

        actionable = [
            candidate
            for candidate in candidates
            if candidate.finding.code not in NON_ACTIONABLE_FINDINGS
        ]
        non_actionable_count = len(candidates) - len(actionable)
        ordered = sorted(actionable, key=_candidate_order)
        selected = ordered[:limit]
        capped_count = len(ordered) - len(selected)
        resolved_as_of = _as_utc(as_of)
        created: list[Recommendation] = []
        deduplicated_count = 0
        keys_seen: set[tuple[int, str]] = set()

        for candidate in selected:
            review_action = _review_action(candidate)
            deduplication_key = _deduplication_key(candidate, review_action)
            scoped_key = (candidate.workspace_id, deduplication_key)
            if scoped_key in keys_seen:
                deduplicated_count += 1
                continue
            keys_seen.add(scoped_key)

            if self._has_recent_or_active_match(
                candidate.workspace_id,
                deduplication_key,
                as_of=resolved_as_of,
            ):
                deduplicated_count += 1
                continue

            planned_action: dict[str, object] = {
                "mode": "human_review_required",
                "mutation": "none_without_human_approval",
                "review_action": review_action,
                "finding_code": candidate.finding.code,
                "scope": {
                    "type": candidate.scope_type,
                    "id": candidate.scope_id,
                    "label": candidate.scope_label,
                },
                "source_text_redacted": candidate.source_text_redacted,
            }
            supporting_metrics: dict[str, object] = {
                **candidate.finding.supporting_metrics,
                "impact_micros": str(candidate.impact_micros),
                "generator_version": GENERATOR_VERSION,
            }
            row = Recommendation(
                workspace_id=candidate.workspace_id,
                platform=candidate.platform,
                account_id=candidate.account_id,
                campaign_id=candidate.campaign_id,
                source_analysis_run_id=source_analysis_run_id,
                deduplication_key=deduplication_key,
                recommendation_type=candidate.finding.code,
                severity=candidate.finding.severity,
                confidence=_CONFIDENCE.get(candidate.finding.severity, Decimal("0.5000")),
                rationale=f"{candidate.scope_label}: {candidate.finding.message}",
                supporting_metrics=supporting_metrics,
                planned_action=planned_action,
                status=RecommendationStatus.PENDING_REVIEW,
                generated_at=resolved_as_of,
                expires_at=resolved_as_of + RECOMMENDATION_LIFETIME,
            )
            try:
                with self.session.begin_nested():
                    self.session.add(row)
                    self.session.flush()
                    self.session.add(
                        RecommendationAudit(
                            recommendation_id=row.id,
                            actor="system:analysis-cadence",
                            action="generated",
                            reason=f"analysis_run:{source_analysis_run_id}",
                        )
                    )
            except IntegrityError:
                # The partial unique index is the final race-safe deduplication guard.
                if self._active_key_exists(
                    candidate.workspace_id,
                    deduplication_key,
                ):
                    deduplicated_count += 1
                    continue
                raise
            created.append(row)

        return RecommendationGenerationResult(
            recommendations=tuple(created),
            created_count=len(created),
            deduplicated_count=deduplicated_count,
            non_actionable_count=non_actionable_count,
            capped_count=capped_count,
        )

    def _has_recent_or_active_match(
        self,
        workspace_id: int,
        deduplication_key: str,
        *,
        as_of: datetime,
    ) -> bool:
        rows = self.session.scalars(
            select(Recommendation)
            .where(
                Recommendation.workspace_id == workspace_id,
                Recommendation.deduplication_key == deduplication_key,
            )
            .order_by(Recommendation.generated_at.desc(), Recommendation.id.desc())
        ).all()
        for row in rows:
            if row.status in ACTIVE_STATUSES:
                if _as_utc(row.expires_at) > as_of:
                    return True
                row.status = RecommendationStatus.EXPIRED
                self.session.add(
                    RecommendationAudit(
                        recommendation_id=row.id,
                        actor="system:analysis-cadence",
                        action="expired",
                        reason="expired before deterministic regeneration",
                    )
                )
                self.session.flush()
                continue
            if (
                row.status == RecommendationStatus.REJECTED
                and _as_utc(row.generated_at) > as_of - REJECTION_COOLDOWN
            ):
                return True
        return False

    def _active_key_exists(self, workspace_id: int, deduplication_key: str) -> bool:
        return (
            self.session.scalar(
                select(Recommendation.id).where(
                    Recommendation.workspace_id == workspace_id,
                    Recommendation.deduplication_key == deduplication_key,
                    Recommendation.status.in_(ACTIVE_STATUSES),
                )
            )
            is not None
        )
