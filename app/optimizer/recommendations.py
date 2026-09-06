from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.optimizer.analytics import MetricWindow, percent_delta

STALE_AFTER_DAYS = 3


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    message: str
    supporting_metrics: dict[str, str]


@dataclass(frozen=True)
class RecommendationDraft:
    recommendation_type: str
    severity: str
    confidence: Decimal
    rationale: str
    planned_action: dict[str, object]
    supporting_metrics: dict[str, str]
    expires_at: datetime


def generate_findings(
    current: MetricWindow,
    comparison: MetricWindow | None,
    *,
    last_success_at: datetime | None,
    now: datetime | None = None,
    conversion_metrics_available: bool = True,
    comparison_conversion_metrics_available: bool = True,
) -> list[Finding]:
    now = now or datetime.now(UTC)
    findings: list[Finding] = []
    if last_success_at is not None and last_success_at.tzinfo is None:
        last_success_at = last_success_at.replace(tzinfo=UTC)
    if last_success_at is None or last_success_at < now - timedelta(days=STALE_AFTER_DAYS):
        findings.append(
            Finding(
                "stale_data",
                "high",
                "Latest successful sync is stale or unavailable.",
                {"last_success_at": str(last_success_at)},
            )
        )
    if not current.has_minimum_coverage:
        findings.append(
            Finding(
                "insufficient_data",
                "medium",
                "Current window has insufficient metric coverage.",
                {
                    "window_days": str(current.window_days),
                    "days_with_metric_rows": str(current.days_with_metric_rows),
                    "data_coverage_ratio": str(current.data_coverage_ratio),
                },
            )
        )
        return findings
    if (
        conversion_metrics_available
        and current.clicks >= 20
        and (current.conversions == 0 or current.cost_per_conversion_micros > Decimal("2000000"))
    ):
        findings.append(
            Finding(
                "spend_without_conversions",
                "high",
                "Spend and clicks have not produced conversions.",
                {"clicks": str(current.clicks), "cost_micros": str(current.cost_micros)},
            )
        )
    if (
        conversion_metrics_available
        and comparison_conversion_metrics_available
        and comparison
        and comparison.has_minimum_coverage
    ):
        delta = percent_delta(
            current.cost_per_conversion_micros, comparison.cost_per_conversion_micros
        )
        if delta is not None and delta > Decimal("0.25") and current.conversions > 0:
            findings.append(
                Finding(
                    "cpa_regression",
                    "medium",
                    "Cost per conversion increased materially versus comparison window.",
                    {"cpa_delta": str(delta)},
                )
            )
    if current.impressions >= 1000 and current.ctr < Decimal("0.02"):
        findings.append(
            Finding(
                "low_ctr",
                "medium",
                "CTR is below launch threshold for meaningful traffic.",
                {"ctr": str(current.ctr)},
            )
        )
    return findings


def recommendations_from_findings(
    findings: list[Finding], *, expires_at: datetime
) -> list[RecommendationDraft]:
    drafts: list[RecommendationDraft] = []
    for finding in findings:
        if finding.code in {"stale_data", "insufficient_data"}:
            continue
        action: dict[str, object] = {
            "mode": "dry_run_only",
            "finding_code": finding.code,
            "mutation": "none_without_human_approval",
        }
        drafts.append(
            RecommendationDraft(
                recommendation_type=finding.code,
                severity=finding.severity,
                confidence=Decimal("0.70") if finding.severity == "medium" else Decimal("0.80"),
                rationale=finding.message,
                planned_action=action,
                supporting_metrics=finding.supporting_metrics,
                expires_at=expires_at,
            )
        )
    return drafts
