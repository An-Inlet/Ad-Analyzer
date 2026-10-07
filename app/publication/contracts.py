"""Frozen coordinator ports; only explicit offline fixture operations are registered."""

import hashlib
import json
from datetime import datetime
from typing import Any, Literal, Protocol

from pydantic import AwareDatetime, Field, model_validator

from app.campaign_review.contracts import ReviewArtifact
from app.goals.schemas import StrictModel
from app.mandates.schemas import AccountScope


def fingerprint(domain: str, value: dict[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(domain.encode() + b"\0" + encoded).hexdigest()


class PublicationScope(StrictModel):
    workspace_id: int = Field(strict=True, gt=0)
    account: AccountScope
    external_advertiser_id: str = Field(min_length=1, max_length=128)
    connection_version: str = Field(min_length=1, max_length=100)
    mandate_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    mandate_revision: int = Field(strict=True, ge=1)


class FixtureReviewFields(StrictModel):
    """Synthetic values are never a real provider's tracking or bidding configuration."""

    kind: Literal["offline_fixture_v1"] = "offline_fixture_v1"
    tracking: Literal["synthetic_conversion"]
    bidding: Literal["synthetic_fixed_bound"]
    budget_semantics: Literal["synthetic_horizon_exposure"]
    activation_policy: Literal["separate_exact_approval"] = "separate_exact_approval"


class PublicationReviewV2(StrictModel):
    schema_version: Literal["inlet.publication-review.v2"] = "inlet.publication-review.v2"
    mode: Literal["offline_fixture"] = "offline_fixture"
    source: ReviewArtifact
    source_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    external_advertiser_id: str = Field(min_length=1, max_length=128)
    configuration: FixtureReviewFields

    @model_validator(mode="after")
    def binding(self) -> "PublicationReviewV2":
        if self.source.fingerprint() != self.source_digest:
            raise ValueError("source review digest mismatch")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class ResourceRef(StrictModel):
    step_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,31}$")
    output: Literal["resource_id"] = "resource_id"


class FixtureOperation(StrictModel):
    kind: Literal["fixture_create_paused"] = "fixture_create_paused"
    resource_kind: Literal["budget", "campaign", "group", "ad"]
    name: str = Field(min_length=1, max_length=120)
    parent: ResourceRef | None = None
    status: Literal["PAUSED"] = "PAUSED"
    content_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


class PublishStep(StrictModel):
    step_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,31}$")
    dependencies: list[str] = Field(max_length=8)
    operation: FixtureOperation


class PublishPlan(StrictModel):
    schema_version: Literal["inlet.publish-plan.v1"] = "inlet.publish-plan.v1"
    mode: Literal["offline_fixture"] = "offline_fixture"
    compiler_id: Literal["fixture_v1"] = "fixture_v1"
    scope: PublicationScope
    review: PublicationReviewV2
    review_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    exposure_micros: int = Field(strict=True, ge=0, le=10**15)
    steps: list[PublishStep] = Field(min_length=1, max_length=16)
    publication_eligible: Literal[False] = False

    @model_validator(mode="after")
    def bound_dag(self) -> "PublishPlan":
        source = self.review.source
        if (
            self.review.digest() != self.review_digest
            or self.scope.external_advertiser_id != self.review.external_advertiser_id
            or self.scope.workspace_id != source.workspace_id
            or self.scope.account != source.definition.account
            or self.scope.connection_version != source.connection_version
            or self.scope.mandate_id != source.definition.mandate_id
            or self.scope.mandate_revision != source.definition.mandate_revision
            or self.exposure_micros != source.definition.budget_micros
        ):
            raise ValueError("plan authorization binding mismatch")
        seen: set[str] = set()
        for step in self.steps:
            if step.step_id in seen or not set(step.dependencies) <= seen:
                raise ValueError("invalid bounded dependency order")
            if len(set(step.dependencies)) != len(step.dependencies):
                raise ValueError("duplicate dependency")
            if step.operation.parent and step.operation.parent.step_id not in step.dependencies:
                raise ValueError("unbound parent")
            if step.operation.content_digest != self.review_digest:
                raise ValueError("operation review mismatch")
            seen.add(step.step_id)
        if len(self.model_dump_json().encode()) > 131072:
            raise ValueError("plan size exceeded")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class BoundRequest(StrictModel):
    mode: Literal["offline_fixture"] = "offline_fixture"
    plan_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    plan_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    scope: PublicationScope
    step: PublishStep
    parent_resource_id: str | None = Field(default=None, max_length=128)
    fence: str = Field(pattern=r"^[a-f0-9]{32}$")
    dispatched_at: AwareDatetime

    def digest(self) -> str:
        return fingerprint("inlet.bound-publication-request.v1", self.model_dump(mode="json"))


class PublishReceipt(StrictModel):
    scope: PublicationScope
    plan_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    step_id: str
    fence: str = Field(pattern=r"^[a-f0-9]{32}$")
    request_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    outcome: Literal["verified_effect", "verified_no_effect", "unknown", "conflict"]
    resource_id: str | None = Field(default=None, max_length=128)
    status: Literal["PAUSED"] | None = None
    observed_at: AwareDatetime

    @model_validator(mode="after")
    def verified_state(self) -> "PublishReceipt":
        if self.outcome == "verified_effect" and (not self.resource_id or self.status != "PAUSED"):
            raise ValueError("verified paused resource required")
        if self.outcome != "verified_effect" and (
            self.resource_id is not None or self.status is not None
        ):
            raise ValueError("unverified resource must not bind dependencies")
        return self


class PublicationCompiler(Protocol):
    def compile(self, review: PublicationReviewV2) -> PublishPlan: ...


class PublicationTransport(Protocol):
    """No implicit retries. Production implementations are not accepted by this release."""

    def apply_once(self, request: BoundRequest, now: datetime) -> PublishReceipt: ...
    def reconcile(self, request: BoundRequest, now: datetime) -> PublishReceipt: ...
