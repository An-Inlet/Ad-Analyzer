"""Exact confirmed customer inputs and scoped references to independently owned evidence."""

from datetime import date
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    AwareDatetime,
    Field,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)

from app.goals.schemas import GoalDefinition
from app.planning_catalog.metadata_contracts import ProviderReferenceV1
from app.planning_documents.common import (
    MAX_ACCOUNTS,
    Amount,
    Currency,
    Digest,
    Frozen,
    Id,
    Key,
    NoAuthority,
    Platform,
    Positive,
    Text,
    Title,
    fingerprint,
    unique,
)
from app.planning_documents.creative_basis import CreativeInputV1
from app.planning_documents.google_budget_intents import ResolvedGoogleDailyBudgetIntentV1
from app.planning_documents.selected_inputs import (
    SelectedCaptureSelectorV1,
    validate_selected_accounts,
)


class AccountRef(Frozen):
    workspace_id: Positive
    account_id: Positive
    connection_id: Positive
    platform: Platform
    connection_version: Title


class ConfirmedGoalRef(Frozen):
    workspace_id: Positive
    goal_id: Id
    revision: Positive
    definition: GoalDefinition
    definition_digest: Digest
    confirmation_reference: Id

    @field_validator("definition", mode="before")
    @classmethod
    def reparse(cls, value: Any) -> Any:
        # The reused goal model predates revalidate_instances=always. Dump nested
        # instances so unsafe model_copy values cannot cross this new boundary.
        return value.model_dump(mode="python") if isinstance(value, GoalDefinition) else value

    @model_validator(mode="after")
    def bound(self) -> "ConfirmedGoalRef":
        if self.definition_digest != fingerprint(
            "goal-definition", self.definition.model_dump(mode="json")
        ):
            raise ValueError("exact confirmed goal definition required")
        return self


class BudgetPeriod(Frozen):
    starts_on: date
    ends_on_exclusive: date
    currency: Currency
    time_zone: Title

    @model_validator(mode="after")
    def bounded(self) -> "BudgetPeriod":
        if not 0 < (self.ends_on_exclusive - self.starts_on).days <= 400:
            raise ValueError("bounded positive planning period required")
        try:
            ZoneInfo(self.time_zone)
        except (ValueError, ZoneInfoNotFoundError):
            raise ValueError("known planning time zone required") from None
        return self


class ReportingWindow(Frozen):
    starts_at: AwareDatetime
    ends_at_exclusive: AwareDatetime

    @model_validator(mode="after")
    def ordered(self) -> "ReportingWindow":
        if not 0 < (self.ends_at_exclusive - self.starts_at).total_seconds() <= 400 * 86400:
            raise ValueError("bounded positive reporting window required")
        return self


class CustomerAssumption(Frozen):
    key: Key
    statement: Text
    author_id: Id
    recorded_at: AwareDatetime
    provenance: Literal["customer_supplied"] = "customer_supplied"


class PlanInputRevision(NoAuthority):
    schema_version: Literal["inlet.plan-input.v1"] = "inlet.plan-input.v1"
    workspace_id: Positive
    plan_id: Id
    revision: Positive
    goal: ConfirmedGoalRef
    accounts: tuple[AccountRef, ...] = Field(min_length=1, max_length=MAX_ACCOUNTS)
    budget_period: BudgetPeriod
    total_ceiling_micros: Amount
    aggressiveness: Literal["conservative", "balanced", "assertive"]
    reporting_window: ReportingWindow
    comparison_window: ReportingWindow | None
    milestone: Text
    product_offer: Text | None
    constraints: tuple[Text, ...] = Field(max_length=30)
    assumptions: tuple[CustomerAssumption, ...] = Field(max_length=30)
    excluded_entity_keys: tuple[Digest, ...] = Field(max_length=100)
    fixed_allocations: tuple["FixedAllocation", ...] = Field(max_length=100)
    scenario_intents: tuple["CustomerScenarioIntent", ...] = Field(max_length=8)
    maximum_creative_assets: int | None = Field(default=None, strict=True, ge=0, le=30)
    creative: CreativeInputV1 | None = None
    google_daily_budget_intents: tuple[ResolvedGoogleDailyBudgetIntentV1, ...] | None = Field(
        default=None, max_length=20
    )
    selected_reporting: tuple[SelectedCaptureSelectorV1, ...] | None = Field(
        default=None, max_length=20
    )
    created_by: Id
    created_at: AwareDatetime

    @model_serializer(mode="wrap")
    def serialize_selected(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        result: dict[str, Any] = handler(self)
        if self.selected_reporting is None:
            result.pop("selected_reporting", None)
        if self.creative is None:
            result.pop("creative", None)
        if self.google_daily_budget_intents is None:
            result.pop("google_daily_budget_intents", None)
        return result

    @model_validator(mode="after")
    def linked(self) -> "PlanInputRevision":
        if self.google_daily_budget_intents is not None:
            ids = tuple(a.account_id for a in self.accounts)
            if any(i.account_id not in ids for i in self.google_daily_budget_intents):
                raise ValueError("owner intent account must be selected")
            keys = tuple((i.account_id, i.owner_key) for i in self.google_daily_budget_intents)
            unique(keys, "budget owner intent")
        validate_selected_accounts(
            self.selected_reporting, tuple(a.account_id for a in self.accounts)
        )
        definition = self.goal.definition
        if (
            self.creative is not None
            and self.creative.product is not None
            and self.creative.product.list_price is not None
            and self.creative.product.list_price.currency != definition.target_window.currency
        ):
            raise ValueError("creative price currency must match confirmed goal")
        if (
            self.goal.workspace_id != self.workspace_id
            or any(a.workspace_id != self.workspace_id for a in self.accounts)
            or self.total_ceiling_micros != definition.budget_micros
            or self.aggressiveness != definition.aggressiveness
            or self.budget_period.starts_on != definition.budget_start
            or self.budget_period.ends_on_exclusive != definition.budget_end
            or self.budget_period.currency != definition.target_window.currency
            or self.budget_period.time_zone != definition.target_window.time_zone
        ):
            raise ValueError("exact confirmed goal budget, period and aggressiveness required")
        unique(tuple(a.account_id for a in self.accounts), "account")
        unique(tuple(a.key for a in self.assumptions), "assumption")
        unique(self.excluded_entity_keys, "excluded entity")
        unique(tuple(a.target.canonical_entity_key for a in self.fixed_allocations), "fixed target")
        if sum(a.amount_micros for a in self.fixed_allocations) > self.total_ceiling_micros:
            raise ValueError("fixed allocations exceed ceiling")
        if any(
            a.target.account not in self.accounts
            or a.target.canonical_entity_key in self.excluded_entity_keys
            for a in self.fixed_allocations
        ):
            raise ValueError("fixed allocation must use included owned target")
        unique(tuple(s.key for s in self.scenario_intents), "scenario intent")
        for scenario in self.scenario_intents:
            if (
                sum(a.amount_micros for a in scenario.allocations) + scenario.unallocated_micros
                != self.total_ceiling_micros
            ):
                raise ValueError("customer scenario must reconcile to confirmed ceiling")
            if any(
                a.target.account not in self.accounts
                or a.target.canonical_entity_key in self.excluded_entity_keys
                for a in scenario.allocations
            ):
                raise ValueError("customer scenario target not selected")
            for fixed in self.fixed_allocations:
                if fixed not in scenario.allocations:
                    raise ValueError("customer scenario must preserve fixed allocation")
        if self.reporting_window.ends_at_exclusive > self.created_at:
            raise ValueError("reporting window cannot include future time")
        if (
            self.comparison_window
            and self.comparison_window.ends_at_exclusive > self.reporting_window.starts_at
        ):
            raise ValueError("comparison windows must not overlap")
        if any(a.recorded_at > self.created_at for a in self.assumptions):
            raise ValueError("future assumption")
        return self


class EvidenceRef(Frozen):
    key: Key
    workspace_id: Positive
    kind: Literal[
        "native_catalog",
        "reported_metrics",
        "shopify_measurement",
        "planning_policy",
        "customer_context",
        "creative_basis",
    ]
    account: AccountRef | None
    document_schema: Title
    document_digest: Digest
    source_binding_digest: Digest
    source_revision: Title
    privacy_revision: int = Field(strict=True, ge=0)
    reporting_window: ReportingWindow | None
    observation_started_at: AwareDatetime
    observed_at: AwareDatetime
    expires_at: AwareDatetime
    coverage: Literal["complete_in_declared_scope", "partial", "unavailable"]
    declared_scope: Text
    reasons: tuple[Key, ...] = Field(max_length=20)
    metric_basis: Text

    @model_validator(mode="after")
    def bound(self) -> "EvidenceRef":
        if not self.observation_started_at <= self.observed_at < self.expires_at:
            raise ValueError("ordered evidence observation and expiry required")
        if (
            self.reporting_window
            and self.reporting_window.ends_at_exclusive > self.observation_started_at
        ):
            raise ValueError("reporting window exceeds observation")
        if self.account is not None and self.account.workspace_id != self.workspace_id:
            raise ValueError("foreign evidence account")
        if self.kind in {"native_catalog", "reported_metrics"} and self.account is None:
            raise ValueError("advertising evidence requires owned account")
        if self.coverage != "complete_in_declared_scope" and not self.reasons:
            raise ValueError("missing evidence reason")
        unique(self.reasons, "evidence reason")
        return self


class TargetRef(Frozen):
    """Catalog V2 semantic references; not a resolver, proof or authorization token."""

    account: AccountRef
    provider_reference: ProviderReferenceV1
    canonical_entity_key: Digest
    selection_key: Digest
    catalog_evidence_key: Key
    kind: Literal["campaign", "adset", "adgroup"]
    display_name: Title | None
    budget_owner_key: Digest | None

    @model_validator(mode="after")
    def platform_kind(self) -> "TargetRef":
        if self.provider_reference.platform != self.account.platform:
            raise ValueError("provider reference platform mismatch")
        if (self.kind == "campaign") != (self.provider_reference.parent_campaign_id is None):
            raise ValueError("provider reference parent mismatch")
        if (self.kind == "adset" and self.account.platform != "meta_ads") or (
            self.kind == "adgroup" and self.account.platform == "meta_ads"
        ):
            raise ValueError("target kind/platform mismatch")
        return self


class AccountTarget(Frozen):
    """New-brand prerequisites/creative planning without a fabricated native entity."""

    account: AccountRef
    scope: Literal["account"] = "account"


class FixedAllocation(Frozen):
    target: TargetRef
    amount_micros: Amount


class CustomerScenarioIntent(Frozen):
    key: Key
    title: Title
    allocations: tuple[FixedAllocation, ...] = Field(max_length=100)
    unallocated_micros: Amount
    provenance: Literal["customer_supplied_hypothesis"] = "customer_supplied_hypothesis"
    semantics: Literal["independent_alternative"] = "independent_alternative"

    @model_validator(mode="after")
    def unique_targets(self) -> "CustomerScenarioIntent":
        unique(tuple(a.target.canonical_entity_key for a in self.allocations), "scenario target")
        unique(
            tuple(
                (a.target.account.account_id, a.target.budget_owner_key)
                for a in self.allocations
                if a.target.budget_owner_key is not None
            ),
            "scenario shared owner",
        )
        return self


PlanInputRevision.model_rebuild()
