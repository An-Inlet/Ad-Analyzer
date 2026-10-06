"""Exact separately consented execution review, server qualification and dispatch ports."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Annotated, Literal, Protocol

from pydantic import AwareDatetime, Field, model_validator
from sqlalchemy.orm import Session

from app.goals.schemas import StrictModel
from app.publication.contracts import fingerprint
from app.publication.execution_contracts import (
    Environment,
    ExecutionAccount,
    ExposureEvidence,
    ProviderMandateBinding,
)
from app.publication.provider_contracts import (
    BoundProviderRequest,
    Digest,
    Id,
    ProviderContext,
    ProviderPublicationTransport,
    ProviderPublishPlan,
    ProviderReceipt,
    ProviderResponse,
)
from app.publication.social_contracts import (
    SocialBoundRequest,
    SocialProviderContext,
    SocialProviderReceipt,
    SocialProviderResponse,
    SocialPublicationTransport,
    SocialPublishPlan,
)

CreationPlan = Annotated[
    ProviderPublishPlan | SocialPublishPlan, Field(discriminator="schema_version")
]
CreationRequest = BoundProviderRequest | SocialBoundRequest
CreationReceipt = ProviderReceipt | SocialProviderReceipt
CreationResponse = ProviderResponse | SocialProviderResponse


class ConfigurationQualification(StrictModel):
    environment: Environment
    account: ExecutionAccount
    plan_digest: Digest
    api_version: Literal["v25", "v26.0", "v1.3"]
    observed_at: AwareDatetime
    expires_at: AwareDatetime
    evidence_digest: Digest
    checks_version: str = Field(min_length=1, max_length=80)
    unresolved: list[str] = Field(max_length=32)

    @model_validator(mode="after")
    def lifetime(self) -> "ConfigurationQualification":
        if not self.observed_at < self.expires_at <= self.observed_at + timedelta(minutes=5):
            raise ValueError("configuration proof exceeds lifetime")
        return self


class CreationExecutionReview(StrictModel):
    schema_version: Literal["inlet.execution-creation-review.v1"] = (
        "inlet.execution-creation-review.v1"
    )
    purpose: Literal["create_paused"] = "create_paused"
    mandate: ProviderMandateBinding
    plan: CreationPlan
    qualification: ConfigurationQualification
    exposure: ExposureEvidence

    @model_validator(mode="after")
    def exact(self) -> "CreationExecutionReview":
        scope = ExecutionAccount.from_publication(self.plan.review.scope)
        if (
            self.qualification.account != scope
            or self.exposure.account != scope
            or self.qualification.plan_digest != self.plan.digest()
            or self.qualification.api_version != self.plan.api_version
            or self.exposure.mandate != self.mandate
            or self.qualification.environment != self.mandate.environment
            or self.qualification.unresolved
        ):
            raise ValueError("qualification or production consent is not bound to exact plan")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class QualificationReader(Protocol):
    def __call__(self, plan: CreationPlan, now: datetime, /) -> ConfigurationQualification: ...


class ExposureReader(Protocol):
    def __call__(
        self, db: Session, binding: ProviderMandateBinding, plan: CreationPlan, now: datetime, /
    ) -> ExposureEvidence: ...


@dataclass(frozen=True)
class CreationRuntime:
    """Server-only assembly; no API accepts this object or caller-provided proof.

    Concrete HTTP adapters remain usable in both environments. Live admission also
    needs explicit runtime activation, current live consent and qualified bounded facts.
    Default runtime factory returns None until application configuration supplies ports.
    """

    environment: Environment
    qualification_reader: QualificationReader
    exposure_reader: ExposureReader
    google: ProviderPublicationTransport
    meta: SocialPublicationTransport
    tiktok: SocialPublicationTransport
    google_context: Callable[[BoundProviderRequest], ProviderContext]
    social_context: Callable[[SocialBoundRequest], SocialProviderContext]
    live_enabled: bool = False


class DispatchClaim(StrictModel):
    workspace_id: int = Field(strict=True, gt=0)
    run_id: Id
    attempt_id: Id
    environment: Environment
    request: CreationRequest


def get_creation_runtime() -> CreationRuntime | None:
    """No implicit credential/provider construction or live activation."""
    return None
