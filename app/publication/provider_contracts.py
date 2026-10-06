"""Versioned provider ports. These documents are not execution authority.

Fixture documents deliberately remain unchanged. Only Google Search is registered;
provider extensions must add typed operations, never arbitrary HTTP dictionaries.
"""

import re
from datetime import datetime, timedelta
from typing import Annotated, Any, Literal, Protocol
from zoneinfo import ZoneInfo

from pydantic import (
    AwareDatetime,
    Field,
    SecretStr,
    SerializerFunctionWrapHandler,
    model_serializer,
    model_validator,
)

from app.campaign_review.contracts import GoogleSearch, ReviewArtifact
from app.goals.schemas import StrictModel
from app.publication.contracts import PublicationScope, ResourceRef, fingerprint

Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Id = Annotated[str, Field(pattern=r"^[a-f0-9]{32}$")]
Micros = Annotated[int, Field(strict=True, gt=0, le=10**15)]


class GoogleSearchPublicationFields(StrictModel):
    kind: Literal["google_search_v25"] = "google_search_v25"
    account_timezone: str = Field(min_length=1, max_length=64)
    login_customer_id: str | None = Field(pattern=r"^[0-9]{10}$")
    daily_budget_micros: Micros
    budget_semantics: Literal["average_daily_not_hard_cap"]
    reservation_micros: Micros
    bidding: Literal["MANUAL_CPC"]
    max_cpc_micros: Micros
    custom_conversion_goal: str = Field(
        pattern=r"^customers/[0-9]{10}/customConversionGoals/[0-9]+$"
    )
    conversion_actions: list[str] = Field(min_length=1, max_length=20)
    country_targets: dict[str, str] = Field(min_length=1, max_length=20)
    language_targets: dict[str, str] = Field(min_length=1, max_length=10)
    google_search: Literal[True]
    search_partners: bool = Field(strict=True)
    content_network: Literal[False]
    positive_geo_target: Literal["PRESENCE"]
    negative_geo_target: Literal["PRESENCE"]
    political_advertising: Literal["DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING"]
    tracking_url_template: str = Field(max_length=2048)
    final_url_suffix: str = Field(max_length=2048)
    activation_policy: Literal["separate_exact_approval"]
    omission_policy: Literal["no_optional_assets_or_automation_requested"]

    @model_validator(mode="after")
    def references(self) -> "GoogleSearchPublicationFields":
        ZoneInfo(self.account_timezone)
        for value in self.country_targets.values():
            if not re.fullmatch(r"geoTargetConstants/[0-9]+", value):
                raise ValueError("invalid geo target")
        for value in self.language_targets.values():
            if not re.fullmatch(r"languageConstants/[0-9]+", value):
                raise ValueError("invalid language target")
        if len(set(self.conversion_actions)) != len(self.conversion_actions):
            raise ValueError("duplicate conversion action")
        if any(
            not re.fullmatch(r"customers/[0-9]{10}/conversionActions/[0-9]+", v)
            for v in self.conversion_actions
        ):
            raise ValueError("invalid conversion action")
        return self


class GoogleQualificationEvidence(StrictModel):
    """Server persisted read evidence, not a customer assertion or spending authority."""

    provider: Literal["google_ads"] = "google_ads"
    api_version: Literal["v25"] = "v25"
    scope: PublicationScope
    binding_digest: Digest
    observed_at: AwareDatetime
    expires_at: AwareDatetime
    evidence_digest: Digest
    checks: Literal["customer_tracking_targets_v1"] = "customer_tracking_targets_v1"

    @model_validator(mode="after")
    def bounded_lifetime(self) -> "GoogleQualificationEvidence":
        if not self.observed_at < self.expires_at <= self.observed_at + timedelta(minutes=5):
            raise ValueError("qualification lifetime exceeds bound")
        return self


class ProviderPublicationReview(StrictModel):
    schema_version: Literal["inlet.provider-publication-review.v1"] = (
        "inlet.provider-publication-review.v1"
    )
    source: ReviewArtifact
    source_digest: Digest
    scope: PublicationScope
    configuration: GoogleSearchPublicationFields
    qualification_blockers: list[str] = Field(max_length=20)
    qualification: GoogleQualificationEvidence | None = None

    @model_validator(mode="after")
    def binding(self) -> "ProviderPublicationReview":
        source, scope, fields = self.source, self.scope, self.configuration
        definition = source.definition
        if (
            not source.offline_reviewable
            or bool(source.blockers)
            or self.source_digest != source.fingerprint()
            or source.workspace_id != scope.workspace_id
            or definition.account != scope.account
            or source.connection_version != scope.connection_version
            or definition.mandate_id != scope.mandate_id
            or definition.mandate_revision != scope.mandate_revision
            or not isinstance(definition.content, GoogleSearch)
            or not re.fullmatch(r"[0-9]{10}", scope.external_advertiser_id)
            or fields.reservation_micros != definition.budget_micros
        ):
            raise ValueError("provider review scope mismatch")
        prefix = f"customers/{scope.external_advertiser_id}/"
        if any(
            not value.startswith(prefix)
            for value in [fields.custom_conversion_goal, *fields.conversion_actions]
        ):
            raise ValueError("foreign tracking reference")
        content = definition.content
        if set(fields.country_targets) != set(content.audience.countries) or set(
            fields.language_targets
        ) != set(content.audience.languages):
            raise ValueError("audience mapping mismatch")
        zone = ZoneInfo(fields.account_timezone)
        start, end = definition.starts_at.astimezone(zone), definition.ends_at.astimezone(zone)
        if (start.hour, start.minute, start.second, start.microsecond) != (0, 0, 0, 0):
            raise ValueError("Google Search start requires reviewed local midnight")
        if (end.hour, end.minute, end.second, end.microsecond) != (23, 59, 59, 0):
            raise ValueError("Google Search end requires reviewed local day end")
        days = (end.date() - start.date()).days + 1
        # Conservative daily overdelivery allowance; activation still requires qualified
        # provider limits and a production mandate. Never reinterpret daily as a hard cap.
        if fields.reservation_micros < 2 * days * fields.daily_budget_micros:
            raise ValueError("reservation cannot cover conservative daily exposure")
        if self.qualification is not None and (
            self.qualification.scope != scope
            or self.qualification.binding_digest != self.configuration_binding()
        ):
            raise ValueError("foreign configuration qualification")
        if not self.qualification_blockers and self.qualification is None:
            raise ValueError("server qualification evidence required")
        return self

    @model_serializer(mode="wrap")
    def serialize_optional_proof(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        data: dict[str, Any] = handler(self)
        if self.qualification is None:
            data.pop("qualification", None)
        return data

    def configuration_binding(self) -> str:
        return fingerprint(
            "inlet.google-configuration.v1",
            {
                "scope": self.scope.model_dump(mode="json"),
                "source_digest": self.source_digest,
                "configuration": self.configuration.model_dump(mode="json"),
                "api_version": "v25",
            },
        )

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class GoogleCreateBudget(StrictModel):
    kind: Literal["google_create_budget"] = "google_create_budget"
    amount_micros: Micros
    delivery_method: Literal["STANDARD"] = "STANDARD"
    period: Literal["DAILY"] = "DAILY"
    explicitly_shared: Literal[False] = False


class GoogleCreatePausedCampaign(StrictModel):
    kind: Literal["google_create_paused_campaign"] = "google_create_paused_campaign"
    name: str = Field(min_length=1, max_length=120)
    budget: ResourceRef
    configuration: GoogleSearchPublicationFields
    starts_local: str = Field(pattern=r"^\d{4}-\d{2}-\d{2} 00:00:00$")
    ends_local: str = Field(pattern=r"^\d{4}-\d{2}-\d{2} 23:59:59$")
    status: Literal["PAUSED"] = "PAUSED"


class GoogleSetConversionGoal(StrictModel):
    kind: Literal["google_set_conversion_goal"] = "google_set_conversion_goal"
    campaign: ResourceRef
    custom_conversion_goal: str = Field(
        pattern=r"^customers/[0-9]{10}/customConversionGoals/[0-9]+$"
    )


class GoogleCreateCampaignCriterion(StrictModel):
    kind: Literal["google_create_campaign_criterion"] = "google_create_campaign_criterion"
    campaign: ResourceRef
    target: str = Field(pattern=r"^(geoTargetConstants|languageConstants)/[0-9]+$")


class GoogleCreatePausedAdGroup(StrictModel):
    kind: Literal["google_create_paused_ad_group"] = "google_create_paused_ad_group"
    campaign: ResourceRef
    name: str = Field(min_length=1, max_length=120)
    cpc_bid_micros: Micros
    status: Literal["PAUSED"] = "PAUSED"


class GoogleCreateExactKeyword(StrictModel):
    kind: Literal["google_create_exact_keyword"] = "google_create_exact_keyword"
    group: ResourceRef
    text: str = Field(min_length=1, max_length=80)
    status: Literal["PAUSED"] = "PAUSED"


class GoogleCreatePausedResponsiveSearchAd(StrictModel):
    kind: Literal["google_create_paused_responsive_search_ad"] = (
        "google_create_paused_responsive_search_ad"
    )
    group: ResourceRef
    content: GoogleSearch
    status: Literal["PAUSED"] = "PAUSED"


ProviderOperation = Annotated[
    GoogleCreateBudget
    | GoogleCreatePausedCampaign
    | GoogleSetConversionGoal
    | GoogleCreateCampaignCriterion
    | GoogleCreatePausedAdGroup
    | GoogleCreateExactKeyword
    | GoogleCreatePausedResponsiveSearchAd,
    Field(discriminator="kind"),
]


def operation_refs(operation: ProviderOperation) -> list[ResourceRef]:
    return [value for value in operation.__dict__.values() if isinstance(value, ResourceRef)]


class ProviderPublishStep(StrictModel):
    step_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,31}$")
    dependencies: list[str] = Field(max_length=96)
    operation: ProviderOperation


class ProviderPublishPlan(StrictModel):
    schema_version: Literal["inlet.provider-publish-plan.v1"] = "inlet.provider-publish-plan.v1"
    compiler_id: Literal["google_search_v25_v1"] = "google_search_v25_v1"
    api_version: Literal["v25"] = "v25"
    review: ProviderPublicationReview
    review_digest: Digest
    steps: list[ProviderPublishStep] = Field(min_length=1, max_length=96)
    publication_eligible: Literal[False] = False

    @model_validator(mode="after")
    def dag(self) -> "ProviderPublishPlan":
        if self.review.digest() != self.review_digest:
            raise ValueError("provider review mismatch")
        seen: set[str] = set()
        for step in self.steps:
            if (
                step.step_id in seen
                or not set(step.dependencies) <= seen
                or len(set(step.dependencies)) != len(step.dependencies)
                or any(r.step_id not in step.dependencies for r in operation_refs(step.operation))
            ):
                raise ValueError("unbound provider DAG")
            seen.add(step.step_id)
        if len(self.model_dump_json().encode()) > 262144:
            raise ValueError("provider plan exceeds bound")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class BoundProviderRequest(StrictModel):
    plan_id: Id
    plan_digest: Digest
    review_digest: Digest
    scope: PublicationScope
    api_version: Literal["v25"] = "v25"
    login_customer_id: str | None = Field(pattern=r"^[0-9]{10}$")
    step: ProviderPublishStep
    resources: dict[str, str] = Field(max_length=96)
    fence: Id
    dispatched_at: AwareDatetime

    @model_validator(mode="after")
    def resource_scope(self) -> "BoundProviderRequest":
        if set(self.resources) != {ref.step_id for ref in operation_refs(self.step.operation)}:
            raise ValueError("exact resolved references required")
        prefix = f"customers/{self.scope.external_advertiser_id}/"
        if any(
            not v.startswith(prefix) or not re.fullmatch(r"[A-Za-z0-9/~]+", v)
            for v in self.resources.values()
        ):
            raise ValueError("foreign or invalid resolved resource")
        return self

    def digest(self) -> str:
        return fingerprint("inlet.bound-provider-request.v1", self.model_dump(mode="json"))


class ProviderReceipt(StrictModel):
    scope: PublicationScope
    plan_id: Id
    plan_digest: Digest
    step_id: str
    fence: Id
    request_digest: Digest
    outcome: Literal["verified_effect", "verified_no_effect", "unknown", "conflict"]
    resource_name: str | None = Field(default=None, max_length=256)
    readback_digest: Digest | None = None
    evidence: Literal["exact_readback", "unresolved", "mismatch", "authoritative_no_effect"]
    observed_at: AwareDatetime

    @model_validator(mode="after")
    def evidence_binding(self) -> "ProviderReceipt":
        if self.outcome == "verified_effect":
            if (
                not self.resource_name
                or not self.readback_digest
                or self.evidence != "exact_readback"
                or not self.resource_name.startswith(
                    f"customers/{self.scope.external_advertiser_id}/"
                )
            ):
                raise ValueError("verified scoped readback required")
        elif self.resource_name is not None or self.readback_digest is not None:
            raise ValueError("unverified resource cannot bind DAG")
        if self.outcome == "verified_no_effect" and self.evidence != "authoritative_no_effect":
            raise ValueError("authoritative absence required")
        return self


class ProviderResponse(StrictModel):
    request_digest: Digest
    resource_name: str | None = Field(default=None, max_length=256)
    outcome: Literal["acknowledged", "unknown"]


class ValidationEvidence(StrictModel):
    request_digest: Digest
    valid: bool
    # Validation is never a mutation receipt or permission to publish.
    publication_authorized: Literal[False] = False


class ProviderContext(StrictModel):
    """Transient server-created credential; never persist with an artifact or receipt."""

    scope: PublicationScope
    login_customer_id: str | None = Field(pattern=r"^[0-9]{10}$")
    access_token: SecretStr = Field(exclude=True, repr=False)
    developer_token: SecretStr | None = Field(default=None, exclude=True, repr=False)
    expires_at: AwareDatetime


class ProviderPublicationTransport(Protocol):
    def validate_only(
        self, request: BoundProviderRequest, context: ProviderContext, now: datetime
    ) -> ValidationEvidence: ...
    def apply_once(
        self, request: BoundProviderRequest, context: ProviderContext, now: datetime
    ) -> ProviderResponse: ...
    def read_back(
        self,
        request: BoundProviderRequest,
        response: ProviderResponse,
        context: ProviderContext,
        now: datetime,
    ) -> ProviderReceipt: ...
    def reconcile(
        self,
        request: BoundProviderRequest,
        history: list[ProviderResponse],
        context: ProviderContext,
        now: datetime,
    ) -> ProviderReceipt: ...


def get_provider_publication_transport() -> ProviderPublicationTransport | None:
    """No runtime authority or provider qualification is installed by this package."""
    return None
