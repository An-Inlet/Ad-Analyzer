import hashlib
import json
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ads.models import AdvertisingAccount, Campaign, DailyMetric
from app.ads.operations import sync_health
from app.analysis.models import AnalysisRun
from app.api.repository import ReadOnlyAdsRepository
from app.automation import AutomationControlService
from app.crm.models import CrmConnection, CrmEventRecord
from app.intelligence.calculations import (
    allocation_preview,
    budget_pacing,
    divide,
    experiment_result,
    scenario_forecast,
)
from app.intelligence.repository import IntelligenceRepository, record_dict
from app.intelligence.schemas import (
    BusinessChange,
    BusinessEvent,
    Creative,
    Experiment,
    OperatingCost,
    RecordKind,
    ScenarioRequest,
    Strategy,
)
from app.learning import DecisionLearningService, WeeklyLearningReportService
from app.measurement.models import WebAnalyticsEvent
from app.measurement.repository import MeasurementRepository
from app.measurement.unified import OutcomeMetricsSnapshot, UnifiedOutcomeService
from app.settings import settings


def _metrics(value: OutcomeMetricsSnapshot | None) -> dict[str, Any] | None:
    return asdict(value) if value is not None else None


def _goal_value(metrics: OutcomeMetricsSnapshot | None, strategy: Strategy) -> float | None:
    if metrics is None:
        return None
    if strategy.primary_metric == "optimization_outcomes":
        return float(metrics.optimization_outcome_count)
    if strategy.primary_metric == "customers":
        return float(metrics.business_outcome_count)
    if strategy.primary_metric == "revenue":
        return metrics.observed_revenue_micros / 1_000_000
    if strategy.contribution_margin_bps is None:
        return None
    return (
        metrics.observed_revenue_micros * strategy.contribution_margin_bps / 10_000
        - metrics.cost_micros
    ) / 1_000_000


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


class IntelligenceService:
    """Composes local facts. This service has no network clients or advertising executor."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = IntelligenceRepository(session)

    def campaign_options(self, workspace_id: int) -> list[dict[str, Any]]:
        rows = self.session.execute(
            select(Campaign.id, Campaign.name)
            .join(AdvertisingAccount)
            .where(AdvertisingAccount.workspace_id == workspace_id)
            .order_by(Campaign.name, Campaign.id)
            .limit(500)
        ).all()
        return [{"id": row.id, "name": row.name} for row in rows]

    def report(self, workspace_id: int, *, as_of: datetime | None = None) -> dict[str, Any]:
        now = as_of or datetime.now(UTC)
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        today = now.astimezone(UTC).date()
        strategy_record = self.repository.strategy(workspace_id)
        strategy = Strategy.model_validate(strategy_record.data) if strategy_record else None
        measurement = MeasurementRepository(self.session).get_for_workspace(workspace_id)
        lag_days = measurement.contract.outcome_maturity_days if measurement else 30
        current_end = today - timedelta(days=max(1, lag_days))
        current_start = current_end - timedelta(days=27)
        outcomes = UnifiedOutcomeService(self.session)
        current = outcomes.report(workspace_id, current_start, current_end, as_of=now)
        previous = outcomes.report(
            workspace_id,
            current_start - timedelta(days=28),
            current_start - timedelta(days=1),
            as_of=now - timedelta(days=28),
        )
        health = self._health(workspace_id, now, current, strategy)
        events = self._events(workspace_id, today)
        experiments = self._experiments(workspace_id, today)
        pacing: dict[str, Any] | None = None
        goal: dict[str, Any] | None = None
        scenarios: list[dict[str, Any]] = []
        if strategy is not None:
            spend, complete, last_date = self._spend(workspace_id, strategy, today)
            reserve, reserve_issues = self._reserves(strategy, events, experiments, today)
            health["issues"].extend(reserve_issues)
            health["blocking"] = health["blocking"] or bool(reserve_issues)
            pacing = budget_pacing(strategy, today, spend, reserve, data_complete=complete)
            pacing["last_metric_date"] = last_date.isoformat() if last_date else None
            goal = self._goal(workspace_id, strategy, now, lag_days)
            sample = (
                (
                    current.totals.optimization_outcome_count
                    if strategy.primary_metric == "optimization_outcomes"
                    else current.totals.business_outcome_count
                )
                if current.totals
                else 0
            )
            forecast_ready = (
                current.analysis_ready and not health["blocking"] and not reserve_issues
            )
            for percent in (80, 100, 120):
                scenario = scenario_forecast(
                    strategy,
                    pacing,
                    ScenarioRequest(proposed_budget_micros=strategy.budget_micros * percent // 100),
                    historical_value=_goal_value(current.totals, strategy),
                    historical_cost_micros=current.totals.cost_micros if current.totals else 0,
                    sample_size=sample,
                    ready=forecast_ready,
                )
                scenario["label"] = f"{percent}% of approved budget"
                scenarios.append(scenario)
        funnel = self._funnel(
            current.totals, previous.totals, current.analysis_ready and previous.analysis_ready
        )
        creatives = self._creatives(workspace_id, current, previous, strategy)
        changes = self.repository.list_records(workspace_id, RecordKind.CHANGE)
        due_reviews = []
        for record in changes:
            change = BusinessChange.model_validate(record.data)
            if (
                change.review_on <= today
                and change.observed_value is None
                and not change.outcome_notes
            ):
                due_reviews.append(record_dict(record))
        report: dict[str, Any] = {
            "workspace_id": workspace_id,
            "currency_code": current.currency_code
            or (strategy.currency_code if strategy else None),
            "as_of": now.isoformat(),
            "timezone": "UTC",
            "strategy": record_dict(strategy_record) if strategy_record else None,
            "window": {
                "start": current_start.isoformat(),
                "end": current_end.isoformat(),
                "previous_start": (current_start - timedelta(days=28)).isoformat(),
                "previous_end": (current_start - timedelta(days=1)).isoformat(),
                "maturity_days": lag_days,
                "comparison_basis": "Equal 28-day cohorts with equal follow-up time.",
            },
            "current": _metrics(current.totals),
            "previous": _metrics(previous.totals),
            "analysis_ready": current.analysis_ready,
            "health": health,
            "coverage": asdict(current.source_coverage),
            "goal": goal,
            "budget": pacing,
            "scenarios": scenarios,
            "events": events,
            "experiments": experiments,
            "funnel": funnel,
            "creatives": creatives,
            "costs": self._costs(workspace_id, strategy),
            "due_reviews": due_reviews,
            "changes": [record_dict(r) for r in changes],
            "stage_labels": {
                "optimization": current.optimization_goal_stage_key,
                "business": current.business_value_stage_key,
            },
            "timeline": [
                {
                    "id": row.id,
                    "record_id": row.record_id,
                    "kind": row.kind,
                    "action": row.action,
                    "version": row.version,
                    "title": str(row.after_data.get("title", "Business update")),
                    "created_at": row.created_at.isoformat(),
                }
                for row in self.repository.revisions(workspace_id)
            ],
            "decisions": [
                record_dict(r)
                for r in self.repository.list_records(workspace_id, RecordKind.DECISION)
            ],
            "saved_briefs": [
                {
                    "as_of": row.scheduled_for.isoformat(),
                    "cadence": row.cadence.value,
                    "data": row.decision_brief,
                }
                for row in self.session.scalars(
                    select(AnalysisRun)
                    .where(
                        AnalysisRun.workspace_id == workspace_id,
                        AnalysisRun.decision_brief.is_not(None),
                        AnalysisRun.status == "succeeded",
                    )
                    .order_by(AnalysisRun.scheduled_for.desc(), AnalysisRun.id.desc())
                    .limit(8)
                )
                if row.decision_brief
            ],
            "learning": DecisionLearningService(self.session).snapshot(workspace_id),
            "weekly_learning": WeeklyLearningReportService(self.session).build(
                workspace_id, as_of=now
            ),
            "controls": [
                asdict(state)
                for state in AutomationControlService(self.session).workspace_states(workspace_id)
            ],
            "execution": {
                "live_changes_enabled": False,
                "conversion_uploads_enabled": False,
                "approval_required": True,
                "financial_approval_required": True,
                "restore_scope": (
                    "Business strategy revisions only; spent money cannot be restored."
                ),
            },
        }
        recommendations = self._recommendations(report, strategy, current, previous, today)
        fingerprint_data = {
            "strategy": report["strategy"],
            "window": report["window"],
            "metrics": report["current"],
            "budget": report["budget"],
            "health": report["health"],
            "events": report["events"],
            "recommendations": recommendations,
        }
        fingerprint = hashlib.sha256(
            json.dumps(fingerprint_data, sort_keys=True, default=str).encode()
        ).hexdigest()
        for item in recommendations:
            item["evidence_fingerprint"] = fingerprint
            item["decision_id"] = next(
                (
                    d["id"]
                    for d in report["decisions"]
                    if d["data"]["recommendation_key"] == item["key"]
                    and d["data"]["evidence_fingerprint"] == fingerprint
                ),
                None,
            )
        report["recommendations"] = recommendations
        report["campaigns"] = [
            {
                "id": c.campaign_id,
                "name": c.campaign_name,
                "platform": c.platform,
                "metrics": _metrics(c.metrics),
            }
            for c in current.campaigns
        ]
        report["allocation"] = None
        if strategy and pacing:
            enabled_ids = set(
                self.session.scalars(
                    select(Campaign.id)
                    .join(AdvertisingAccount)
                    .where(
                        AdvertisingAccount.workspace_id == workspace_id,
                        Campaign.status == "ENABLED",
                    )
                )
            )
            report["allocation"] = allocation_preview(
                strategy,
                pacing,
                [
                    {
                        "id": c.campaign_id,
                        "name": c.campaign_name,
                        "spend_micros": c.metrics.cost_micros,
                        "sample": c.metrics.optimization_outcome_count
                        if strategy.primary_metric == "optimization_outcomes"
                        else c.metrics.business_outcome_count,
                        "goal_value": _goal_value(c.metrics, strategy) or 0,
                    }
                    for c in current.campaigns
                    if c.campaign_id in enabled_ids
                ],
                ready=current.analysis_ready and not health["blocking"],
            )
        from app.shopify.reporting import sales_report

        report["commerce"] = sales_report(self.session, workspace_id, now=now)
        return report

    @staticmethod
    def brief(report: dict[str, Any]) -> dict[str, Any]:
        """Bounded aggregate snapshot for existing scheduled local analysis jobs."""
        snapshot = {
            "as_of": report["as_of"],
            "window": report["window"],
            "strategy_version": report["strategy"]["version"] if report["strategy"] else None,
            "goal": report["goal"],
            "budget": report["budget"],
            "health_issues": report["health"]["issues"],
            "recommendations": report["recommendations"][:10],
        }
        return dict(json.loads(json.dumps(snapshot, default=str)))

    def scenario(self, report: dict[str, Any], request: ScenarioRequest) -> dict[str, Any]:
        if not report["strategy"] or not report["budget"]:
            raise ValueError("Save a company strategy before modeling a budget.")
        strategy = Strategy.model_validate(report["strategy"]["data"])
        metrics = OutcomeMetricsSnapshot(**report["current"]) if report["current"] else None
        return scenario_forecast(
            strategy,
            report["budget"],
            request,
            historical_value=_goal_value(metrics, strategy),
            historical_cost_micros=metrics.cost_micros if metrics else 0,
            sample_size=(
                metrics.optimization_outcome_count
                if strategy.primary_metric == "optimization_outcomes"
                else metrics.business_outcome_count
            )
            if metrics
            else 0,
            ready=report["analysis_ready"] and not report["health"]["blocking"],
        )

    def _spend(
        self, workspace_id: int, strategy: Strategy, today: date
    ) -> tuple[int | None, bool, date | None]:
        currencies = set(
            self.session.scalars(
                select(AdvertisingAccount.currency_code).where(
                    AdvertisingAccount.workspace_id == workspace_id
                )
            )
        )
        if currencies - {strategy.currency_code}:
            return None, False, None
        cutoff = min(today - timedelta(days=1), strategy.period_end)
        if cutoff < strategy.period_start:
            return 0, True, None
        rows = self.session.execute(
            select(
                AdvertisingAccount.id,
                func.sum(DailyMetric.cost_micros),
                func.count(func.distinct(DailyMetric.metric_date)),
                func.max(DailyMetric.metric_date),
            )
            .select_from(DailyMetric)
            .join(Campaign, Campaign.id == DailyMetric.campaign_id)
            .join(AdvertisingAccount, AdvertisingAccount.id == Campaign.account_id)
            .where(
                AdvertisingAccount.workspace_id == workspace_id,
                DailyMetric.entity_type == "campaign",
                DailyMetric.entity_id == Campaign.id,
                DailyMetric.metric_date >= strategy.period_start,
                DailyMetric.metric_date <= cutoff,
            )
            .group_by(AdvertisingAccount.id)
        ).all()
        expected = (cutoff - strategy.period_start).days + 1
        account_ids = set(
            self.session.scalars(
                select(AdvertisingAccount.id).where(AdvertisingAccount.workspace_id == workspace_id)
            )
        )
        complete = bool(account_ids) and {r[0] for r in rows} == account_ids
        complete = complete and all(int(r[2]) >= expected for r in rows)
        return (
            sum(int(r[1] or 0) for r in rows),
            complete,
            max((r[3] for r in rows if r[3]), default=None),
        )

    def _health(
        self, workspace_id: int, now: datetime, current: Any, strategy: Strategy | None
    ) -> dict[str, Any]:
        sync = sync_health(self.session, settings, now=now, workspace_ids={workspace_id})
        web_last = self.session.scalar(
            select(func.max(WebAnalyticsEvent.occurred_at)).where(
                WebAnalyticsEvent.workspace_id == workspace_id, WebAnalyticsEvent.occurred_at <= now
            )
        )
        crm_last = self.session.scalar(
            select(func.max(CrmEventRecord.occurred_at))
            .join(CrmConnection)
            .where(CrmConnection.workspace_id == workspace_id, CrmEventRecord.occurred_at <= now)
        )
        issues: list[dict[str, str]] = []
        for reason in current.blocking_reasons:
            issues.append(
                {"code": reason, "severity": "blocking", "message": reason.replace("_", " ")}
            )
        if strategy is None:
            issues.append(
                {
                    "code": "strategy_missing",
                    "severity": "attention",
                    "message": "Set the company goal and approved budget.",
                }
            )
        if sync.stale:
            issues.append(
                {
                    "code": "advertising_sync_stale",
                    "severity": "blocking",
                    "message": (
                        "Advertising sync is missing or stale. Recommendations need "
                        "refreshed evidence."
                    ),
                }
            )
        stale_accounts = 0
        for account_id in self.session.scalars(
            select(AdvertisingAccount.id).where(AdvertisingAccount.workspace_id == workspace_id)
        ):
            _, success = ReadOnlyAdsRepository(self.session).account_sync_status(account_id)
            if success is None or (now - success.replace(tzinfo=UTC)).total_seconds() > (
                settings.sync_stale_after_minutes * 60
            ):
                stale_accounts += 1
        if stale_accounts and not sync.stale:
            issues.append(
                {
                    "code": "account_sync_stale",
                    "severity": "blocking",
                    "message": (
                        f"{stale_accounts} advertising account(s) need a fresh successful sync."
                    ),
                }
            )
        if web_last is None:
            issues.append(
                {
                    "code": "analytics_missing",
                    "severity": "blocking",
                    "message": "No web analytics events have been received.",
                }
            )
        if crm_last is None:
            issues.append(
                {
                    "code": "crm_missing",
                    "severity": "blocking",
                    "message": "No CRM outcomes have been received.",
                }
            )
        for name, last_event in (("web analytics", web_last), ("CRM", crm_last)):
            if last_event and (now - last_event.replace(tzinfo=UTC)).days >= 7:
                issues.append(
                    {
                        "code": "source_activity_quiet",
                        "severity": "attention",
                        "message": (
                            f"No {name} activity in seven days; verify delivery or low volume."
                        ),
                    }
                )
        if strategy and current.currency_code and strategy.currency_code != current.currency_code:
            issues.append(
                {
                    "code": "strategy_currency_mismatch",
                    "severity": "blocking",
                    "message": "Strategy and measurement currencies differ.",
                }
            )
        if current.source_coverage.crm_event_count > current.source_coverage.mapped_crm_event_count:
            issues.append(
                {
                    "code": "unmapped_crm_events",
                    "severity": "attention",
                    "message": "Some CRM events have no approved funnel mapping.",
                }
            )
        for kind in RecordKind:
            if self.repository.count(workspace_id, kind) > 200:
                issues.append(
                    {
                        "code": "context_limit_exceeded",
                        "severity": "blocking",
                        "message": (
                            "More than 200 records in a context category; planning is incomplete."
                        ),
                    }
                )
                break
        return {
            "sync_status": sync.status,
            "last_ads_sync": _iso(sync.last_success_at),
            "last_web_event": _iso(web_last),
            "last_crm_event": _iso(crm_last),
            "issues": issues,
            "blocking": any(i["severity"] == "blocking" for i in issues),
            "attribution_note": (
                "Platform conversions and CRM outcomes are separate measures. "
                "Attribution does not establish incremental impact."
            ),
        }

    def _events(self, workspace_id: int, today: date) -> list[dict[str, Any]]:
        result = []
        for record in self.repository.list_records(workspace_id, RecordKind.EVENT):
            event = BusinessEvent.model_validate(record.data)
            phase: str
            preparation_on = event.starts_on - timedelta(days=event.preparation_days)
            follow_up_end = event.ends_on + timedelta(days=event.follow_up_days)
            if event.status in {"cancelled", "completed"}:
                phase = event.status
            elif today < preparation_on:
                phase = "upcoming"
            elif today < event.starts_on:
                phase = "preparation"
            elif today <= event.ends_on:
                phase = "active"
            elif today <= follow_up_end:
                phase = "follow_up"
            else:
                phase = "review_due"
            result.append(
                {
                    **record_dict(record),
                    "phase": phase,
                    "preparation_on": preparation_on.isoformat(),
                    "follow_up_end": follow_up_end.isoformat(),
                    "days_until_start": (event.starts_on - today).days,
                }
            )
        return sorted(result, key=lambda e: (e["data"]["starts_on"], e["id"]))

    def _experiments(self, workspace_id: int, today: date) -> list[dict[str, Any]]:
        return [
            {
                **record_dict(record),
                "result": experiment_result(Experiment.model_validate(record.data), today),
            }
            for record in self.repository.list_records(workspace_id, RecordKind.EXPERIMENT)
        ]

    def _reserves(
        self,
        strategy: Strategy,
        events: list[dict[str, Any]],
        experiments: list[dict[str, Any]],
        today: date,
    ) -> tuple[int, list[dict[str, str]]]:
        reserve = 0
        issues = []
        for item in events:
            event = BusinessEvent.model_validate(item["data"])
            if (
                event.status != "confirmed"
                or event.ends_on + timedelta(days=event.follow_up_days)
                < max(today, strategy.period_start)
                or event.starts_on > strategy.period_end
            ):
                continue
            if event.currency_code != strategy.currency_code:
                issues.append(
                    {
                        "code": "event_currency_mismatch",
                        "severity": "blocking",
                        "message": "An event reserve uses a different currency.",
                    }
                )
            else:
                reserve += event.remaining_reserve_micros
        for item in experiments:
            experiment = Experiment.model_validate(item["data"])
            if (
                experiment.status not in {"planned", "running"}
                or experiment.ends_on < max(today, strategy.period_start)
                or experiment.starts_on > strategy.period_end
            ):
                continue
            if experiment.currency_code != strategy.currency_code:
                issues.append(
                    {
                        "code": "experiment_currency_mismatch",
                        "severity": "blocking",
                        "message": "An experiment budget uses a different currency.",
                    }
                )
            else:
                reserve += max(
                    0,
                    experiment.budget_micros
                    - experiment.control_spend_micros
                    - experiment.treatment_spend_micros,
                )
        return reserve, issues

    def _goal(
        self, workspace_id: int, strategy: Strategy, now: datetime, lag: int
    ) -> dict[str, Any]:
        end = min(strategy.period_end, now.date() - timedelta(days=max(lag, 1)))
        metrics = None
        reasons: list[str] = []
        ready = False
        if end >= strategy.period_start:
            result = UnifiedOutcomeService(self.session).report(
                workspace_id, strategy.period_start, end, as_of=now
            )
            metrics, ready, reasons = (
                result.totals,
                result.analysis_ready,
                list(result.blocking_reasons),
            )
        value = _goal_value(metrics, strategy) if ready else None
        total_days = (strategy.period_end - strategy.period_start).days + 1
        mature_days = max(0, (end - strategy.period_start).days + 1)
        target_to_date = float(strategy.target) * mature_days / total_days
        return {
            "metric": strategy.primary_metric,
            "target": float(strategy.target),
            "observed": value,
            "target_for_mature_days": target_to_date,
            "progress_ratio": divide(value, float(strategy.target)) if value is not None else None,
            "on_pace": value >= target_to_date if value is not None else None,
            "mature_through": end.isoformat() if mature_days else None,
            "basis": (
                "Outcomes attributed to mature advertising cohorts in the goal "
                "period, not all company sales booked this month."
            ),
            "value_basis": "Contribution after advertising, using the entered margin assumption."
            if strategy.primary_metric == "contribution_profit"
            else "Observed CRM outcomes.",
            "blocking_reasons": reasons,
        }

    def _costs(self, workspace_id: int, strategy: Strategy | None) -> dict[str, Any]:
        records = self.repository.list_records(workspace_id, RecordKind.COST)
        totals: dict[str, dict[str, int]] = {}
        for record in records:
            cost = OperatingCost.model_validate(record.data)
            if strategy and (
                cost.period_start < strategy.period_start or cost.period_end > strategy.period_end
            ):
                continue
            bucket = totals.setdefault(
                cost.currency_code, {"observed_micros": 0, "estimate_micros": 0}
            )
            bucket[f"{cost.basis}_micros"] += cost.amount_micros
        return {
            "totals": totals,
            "records": [record_dict(r) for r in records],
            "basis": (
                "Operator-entered costs fully contained within the plan period;"
                " currencies and estimates are kept separate."
            ),
            "billing_connected": False,
        }

    def _funnel(
        self,
        current: OutcomeMetricsSnapshot | None,
        previous: OutcomeMetricsSnapshot | None,
        ready: bool,
    ) -> list[dict[str, Any]]:
        if current is None:
            return []
        stages = [
            ("Ad engagement", "impressions", "clicks", "creative and audience"),
            ("Website arrival", "clicks", "paid_session_count", "tracking and page loading"),
            ("Lead capture", "paid_session_count", "lead_count", "landing page and offer"),
            (
                "Lead qualification",
                "lead_count",
                "optimization_outcome_count",
                "audience and qualification",
            ),
            (
                "Customer conversion",
                "optimization_outcome_count",
                "business_outcome_count",
                "sales follow-up and offer",
            ),
        ]
        result = []
        for title, denominator, numerator, investigate in stages:
            base, successes = getattr(current, denominator), getattr(current, numerator)
            rate = divide(successes, base)
            old_base = getattr(previous, denominator) if previous else 0
            old_rate = divide(getattr(previous, numerator), old_base) if previous else None
            change = (
                divide(rate - old_rate, old_rate)
                if rate is not None and old_rate is not None
                else None
            )
            comparable = ready and min(base, old_base) >= 30
            result.append(
                {
                    "stage": title,
                    "entered": base,
                    "progressed": successes,
                    "rate": rate,
                    "previous_rate": old_rate,
                    "relative_change": change,
                    "status": "investigate"
                    if comparable and change is not None and change < -0.2
                    else ("observing" if comparable else "insufficient_evidence"),
                    "investigate": investigate,
                    "cause_confirmed": False,
                }
            )
        return result

    def _creatives(
        self, workspace_id: int, current: Any, previous: Any, strategy: Strategy | None
    ) -> list[dict[str, Any]]:
        current_by_id = {c.campaign_id: c for c in current.campaigns}
        previous_by_id = {c.campaign_id: c for c in previous.campaigns}
        records = self.repository.list_records(workspace_id, RecordKind.CREATIVE)
        result = []
        for record in records:
            creative = Creative.model_validate(record.data)
            campaign = current_by_id.get(creative.campaign_id)
            old = previous_by_id.get(creative.campaign_id)
            covers_window = (
                creative.starts_on <= current.cohort_date_from
                and creative.ends_on >= current.cohort_date_to
            )
            metrics = campaign.metrics if campaign and covers_window else None
            fatigue = bool(
                metrics
                and old
                and current.analysis_ready
                and previous.analysis_ready
                and creative.starts_on <= previous.cohort_date_from
                and metrics.impressions >= 1000
                and old.metrics.impressions >= 1000
                and metrics.click_through_rate is not None
                and old.metrics.click_through_rate
                and metrics.click_through_rate < old.metrics.click_through_rate * Decimal("0.8")
            )
            sample = metrics.business_outcome_count if metrics else 0
            result.append(
                {
                    **record_dict(record),
                    "campaign_name": campaign.campaign_name if campaign else "Campaign",
                    "metrics": _metrics(metrics),
                    "evidence_state": "campaign_context" if metrics else "window_not_covered",
                    "possible_fatigue": fatigue,
                    "business_sample_sufficient": sample
                    >= (strategy.minimum_outcomes if strategy else 20),
                    "brief": (
                        f"Test a new opening for {creative.audience or 'the selected audience'} "
                        f"while holding the {creative.offer or 'current'} offer constant. "
                        f"Compare customer outcomes with the original {creative.format} treatment."
                    ),
                    "limitation": (
                        "Campaign-level context. Multiple ads, audiences, or concurrent"
                        " changes can explain the result; this is not an isolated "
                        "ad-level winner."
                    ),
                }
            )
        return result

    def _recommendations(
        self,
        report: dict[str, Any],
        strategy: Strategy | None,
        current: Any,
        previous: Any,
        today: date,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []

        def add(
            key: str,
            priority: int,
            title: str,
            evidence: str,
            action: str,
            *,
            cost: int | None = 0,
            review_days: int = 7,
            confidence: str = "observed",
            expected: str = "Measure the result after review.",
        ) -> None:
            items.append(
                {
                    "key": key,
                    "priority": priority,
                    "title": title,
                    "evidence": evidence,
                    "goal": strategy.title if strategy else "Set a company goal",
                    "action": action,
                    "cost_change_micros": cost,
                    "confidence": confidence,
                    "review_on": (today + timedelta(days=review_days)).isoformat(),
                    "expected_result": expected,
                    "effort": "operator review",
                    "approval_required": True,
                }
            )

        if report["health"]["blocking"]:
            add(
                "repair_measurement",
                1,
                "Restore reliable measurement",
                "; ".join(
                    i["message"] for i in report["health"]["issues"] if i["severity"] == "blocking"
                ),
                (
                    "Inspect tracking, source freshness, and measurement mappings "
                    "before changing spend."
                ),
                expected="Fresh, reconciled sources and an unblocked outcome report.",
            )
        if strategy is None:
            add(
                "set_strategy",
                2,
                "Set the company's objective and budget",
                "No strategy profile is saved.",
                (
                    "Enter the primary business outcome, target, period, approved "
                    "budget, and priorities."
                ),
            )
        pacing = report["budget"]
        if pacing:
            if pacing["reserve_shortfall_micros"]:
                add(
                    "reserve_shortfall",
                    2,
                    "Resolve overcommitted reserves",
                    "Event and experiment reserves exceed the remaining approved budget.",
                    (
                        "Reduce or reschedule reservations before allocating additional"
                        " campaign spend."
                    ),
                )
            if (
                pacing["projected_spend_micros"] is not None
                and pacing["projected_spend_micros"] > pacing["budget_micros"]
            ):
                add(
                    "budget_pacing",
                    2,
                    "Bring spending back within the plan",
                    "The completed-day spending pace projects above the approved period budget.",
                    (
                        "Review the suggested daily ceiling and prepare a budget "
                        "adjustment for approval."
                    ),
                    expected="Projected spending at or below the approved budget.",
                )
            if not pacing["data_complete"]:
                add(
                    "budget_data_gap",
                    2,
                    "Complete spending coverage",
                    "The plan period has missing advertising days or incompatible currencies.",
                    (
                        "Reconcile the missing days or currency definitions before "
                        "relying on projections."
                    ),
                )
        for event in report["events"]:
            if (
                event["phase"] in {"preparation", "active", "follow_up", "review_due"}
                and event["data"]["status"] == "confirmed"
            ):
                add(
                    f"event:{event['id']}",
                    3,
                    f"{event['data']['title']}: {event['phase'].replace('_', ' ')}",
                    f"Event runs {event['data']['starts_on']} through {event['data']['ends_on']}.",
                    event["data"]["preparation"]
                    if event["phase"] == "preparation" and event["data"]["preparation"]
                    else (
                        event["data"]["follow_up"]
                        or "Review timing, messaging, inventory, and follow-up for this event."
                    ),
                    review_days=1,
                )
        for stage in report["funnel"]:
            if stage["status"] == "investigate":
                add(
                    f"funnel:{stage['stage'].lower().replace(' ', '_')}",
                    4,
                    f"Investigate {stage['stage'].lower()}",
                    f"Conversion rate changed from {stage['previous_rate']:.1%} "
                    f"to {stage['rate']:.1%} across comparable cohorts.",
                    f"Check {stage['investigate']}; "
                    "the observed change does not establish its cause.",
                    confidence="supported_pattern",
                    review_days=max(7, report["window"]["maturity_days"]),
                )
        if strategy and current.totals:
            metrics = current.totals
            if (
                strategy.maximum_cac_micros
                and metrics.cost_per_business_outcome_micros is not None
                and current.analysis_ready
                and not report["health"]["blocking"]
                and metrics.business_outcome_count >= strategy.minimum_outcomes
                and metrics.cost_per_business_outcome_micros > strategy.maximum_cac_micros
            ):
                add(
                    "cac_over_target",
                    3,
                    "Acquisition cost exceeds the company limit",
                    "Mature-cohort customer acquisition cost is above the saved maximum.",
                    "Review campaign customer quality and the weakest funnel stage before scaling.",
                )
            if (
                strategy.sales_capacity_per_week
                and metrics.lead_count / 4 > strategy.sales_capacity_per_week
            ):
                add(
                    "sales_capacity",
                    3,
                    "Check sales capacity before increasing lead volume",
                    "Average weekly leads in the comparison window exceed the configured capacity.",
                    (
                        "Confirm follow-up capacity and qualification priorities before"
                        " increasing spend."
                    ),
                )
            sample = (
                metrics.optimization_outcome_count
                if strategy.primary_metric == "optimization_outcomes"
                else metrics.business_outcome_count
            )
            if sample < strategy.minimum_outcomes:
                add(
                    "wait_for_evidence",
                    5,
                    "Gather more business outcomes",
                    f"{sample} outcomes; the plan requires {strategy.minimum_outcomes} "
                    "before stronger comparisons.",
                    "Hold performance-driven budget changes while collecting mature outcomes.",
                    confidence="insufficient_evidence",
                )
        for creative in report["creatives"]:
            if creative["possible_fatigue"]:
                add(
                    f"creative:{creative['id']}",
                    5,
                    "Test a creative refresh",
                    (
                        "Campaign click-through rate fell across comparable windows; "
                        "fatigue is one possible explanation."
                    ),
                    creative["brief"],
                    cost=None,
                    confidence="hypothesis",
                )
        for change in report["due_reviews"]:
            add(
                f"review:{change['id']}",
                4,
                f"Review: {change['data']['title']}",
                "The planned evaluation date has arrived with no outcome recorded.",
                (
                    "Record the observed metric and account for concurrent changes "
                    "before drawing conclusions."
                ),
            )
        if not items:
            add(
                "maintain_and_test",
                6,
                "Maintain the plan and choose the next test",
                "No configured exception was detected in the available evidence.",
                "Review goal progress and select one measurable experiment.",
                confidence="bounded_review",
            )
        return sorted(items, key=lambda item: (item["priority"], item["key"]))[:25]

    def answer(self, report: dict[str, Any], question: str) -> dict[str, Any]:
        text = question.casefold()
        if any(
            word in text
            for word in ("shopify", "sales", "selling", "refund", "returning", "product")
        ):
            commerce = report["commerce"]
            sales_facts = commerce["suggestions"]
            if commerce["connected"]:
                metrics = commerce["current"]
                sales_facts = [
                    f"{commerce['currency_code']} "
                    f"{metrics['net_collected_micros'] / 1_000_000:,.2f} net collected "
                    f"across {metrics['paid_orders']} paid orders.",
                    *sales_facts,
                ]
            return {
                "topic": "sales",
                "answer": commerce.get(
                    "basis", "Connect Shopify to bring store sales into this workspace."
                ),
                "facts": sales_facts,
                "evidence": commerce,
                "as_of": report["as_of"],
                "window": commerce.get("window", report["window"]),
                "limitations": commerce["warnings"]
                + [
                    "Store sales are separate from CRM outcomes and do not prove "
                    "advertising causation."
                ],
            }

        topics = {
            "budget": ("budget", "spend", "money", "cost", "afford"),
            "events": ("event", "launch", "promotion", "calendar", "upcoming"),
            "funnel": ("why", "funnel", "lead", "conversion", "drop"),
            "creative": ("creative", "message", "audience", "fatigue", "hook"),
            "experiments": ("experiment", "test", "lift", "winner"),
            "goals": ("goal", "target", "track", "revenue", "profit"),
        }
        topic = next(
            (name for name, words in topics.items() if any(word in text for word in words)),
            "actions",
        )
        evidence: Any = report.get({"creative": "creatives", "goals": "goal"}.get(topic, topic))
        if topic == "actions":
            evidence = report["recommendations"][:3]
        summaries = {
            "budget": (
                "Compare approved spend, completed-day pace, and reserved "
                "funds. Scenario ranges are assumptions, not guaranteed "
                "results."
            ),
            "events": (
                "The calendar shows preparation, campaign dates, and follow-up."
                " Changing an event updates the proposed schedule and "
                "reservations."
            ),
            "funnel": (
                "These stage comparisons show where rates changed. They "
                "identify investigations; they do not establish the cause."
            ),
            "creative": (
                "Creative briefs use campaign context and customer outcomes "
                "where available. Individual-ad attribution is not available "
                "from campaign totals."
            ),
            "experiments": (
                "Completed experiments require mature results and enough unique"
                " assigned units. Observational comparisons cannot establish "
                "lift."
            ),
            "goals": (
                "Goal progress uses mature advertising cohorts and the saved "
                "business objective. It is distinct from total company sales "
                "booked in the period."
            ),
            "actions": (
                "These are the highest-priority actions supported by the "
                "current workspace evidence. Ask about budget, events, funnel, "
                "creative, experiments, or goals."
            ),
        }
        facts: list[str] = []
        budget = report["budget"]
        currency = report["currency_code"] or "currency unknown"

        def money(amount: int | None) -> str:
            return f"{currency} {amount / 1_000_000:,.2f}" if amount is not None else "unavailable"

        if topic == "budget":
            if budget:
                facts = [
                    f"The plan runs from {budget['period_start']} to {budget['period_end']}.",
                    f"Approved budget: {money(budget['budget_micros'])}; "
                    f"recorded completed-day spend: {money(budget['spend_micros'])}.",
                    f"Event and test reservations: {money(budget['reserved_micros'])}; "
                    f"remaining unreserved funds: {money(budget['available_micros'])}.",
                    f"There are {budget['remaining_days']} planning days left. "
                    f"Suggested daily ceiling: {money(budget['suggested_daily_ceiling_micros'])}.",
                ]
                if not budget["data_complete"]:
                    facts.append(
                        "Spending coverage is incomplete; available funds may be overstated."
                    )
            else:
                facts.append(
                    "No company budget is saved. Set a strategy to calculate affordability."
                )
        elif topic == "goals":
            goal = report["goal"]
            if goal and goal["observed"] is not None:
                facts.append(
                    f"Observed {goal['metric'].replace('_', ' ')}: {goal['observed']:,.2f} "
                    f"toward {goal['target']:,.2f}; the mature-period pace target is "
                    f"{goal['target_for_mature_days']:,.2f}."
                )
                facts.append(
                    "The mature cohorts are on pace."
                    if goal["on_pace"]
                    else "The mature cohorts are below the plan's linear pace."
                )
            else:
                facts.append(
                    "Goal progress cannot yet be calculated from mature, approved evidence."
                )
        elif topic == "funnel":
            for stage in report["funnel"]:
                rate, old_rate = stage["rate"], stage["previous_rate"]
                if rate is not None and old_rate is not None:
                    facts.append(
                        f"{stage['stage']}: {stage['progressed']} of {stage['entered']} "
                        f"({rate:.1%}), previously {old_rate:.1%}. "
                        f"Assessment: {stage['status'].replace('_', ' ')}."
                    )
            if not facts:
                facts.append("Comparable funnel rates are not available yet.")
        elif topic == "events":
            facts = [
                f"{e['data']['title']}: {e['phase'].replace('_', ' ')}, "
                f"{e['data']['starts_on']} to {e['data']['ends_on']}; "
                f"prepare from {e['preparation_on']}, follow up through {e['follow_up_end']}."
                for e in report["events"]
                if e["phase"] not in {"completed", "cancelled"}
            ][:5] or ["No active events are saved. Add the next launch or business milestone."]
        elif topic == "creative":
            facts = [
                f"{c['data']['title']}: "
                + ("possible fatigue. " if c["possible_fatigue"] else "")
                + c["brief"]
                for c in report["creatives"][:3]
            ] or ["No creative concepts are linked to campaigns yet."]
        elif topic == "experiments":
            facts = [
                f"{e['data']['title']}: {e['result']['status'].replace('_', ' ')}; "
                f"review from {e['result']['review_on']}."
                for e in report["experiments"][:5]
            ] or ["No experiments are saved. Predefine a test before collecting its results."]
        else:
            facts = [
                f"{r['title']}: {r['evidence']} Next: {r['action']}"
                for r in report["recommendations"][:3]
            ]
        return {
            "topic": topic,
            "answer": summaries[topic],
            "facts": facts,
            "evidence": evidence,
            "as_of": report["as_of"],
            "window": report["window"],
            "limitations": [i["message"] for i in report["health"]["issues"]],
            "method": "Deterministic evidence lookup; no external AI service or paid model call.",
        }
