"""Bounded TikTok video assembly ports; no source registry, authority or live factory."""

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

from pydantic import AwareDatetime, Field, SecretStr, model_validator
from sqlalchemy.orm import Session

from app.initial_planning.contracts import Frozen
from app.publication.activation_contracts import ActivationContext, ActivationRequest
from app.publication.activation_review import ActivationExposureReader
from app.publication.contracts import fingerprint
from app.publication.coordinator_contracts import ExposureReader, QualificationReader
from app.publication.execution_authorization import ExecutionAuthorizer
from app.publication.execution_contracts import ExecutionAccount
from app.publication.provider_contracts import Digest
from app.publication.social_catalog import SocialCatalogReader, SocialCatalogRequest
from app.publication.social_contracts import SocialBoundRequest, SocialProviderContext


class TikTokExecutionManifestV1(Frozen):
    schema_version: Literal["inlet.tiktok-execution-manifest.v1"] = (
        "inlet.tiktok-execution-manifest.v1"
    )
    manifest_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    revision: int = Field(strict=True, gt=0)
    environment: Literal["contract_test", "live"]
    api_version: Literal["v1.3"]
    evidence_source_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    evidence_profile_digest: Digest
    configuration_bundle_digest: Digest
    live_execution_enabled: bool = Field(strict=True)
    activation_enabled: bool = Field(strict=True)
    credential_minimum_remaining_seconds: int = Field(strict=True, ge=300, le=3600)
    context_lifetime_seconds: int = Field(strict=True, ge=1, le=300)

    @model_validator(mode="after")
    def bounded(self) -> "TikTokExecutionManifestV1":
        if self.environment == "contract_test" and self.live_execution_enabled:
            raise ValueError("scenario cannot enable live execution")
        if self.context_lifetime_seconds > self.credential_minimum_remaining_seconds:
            raise ValueError("context exceeds credential lifetime")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class TikTokEvidenceDescriptor(Frozen):
    source_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    profile_digest: Digest
    environment: Literal["contract_test", "live"]
    kind: Literal["contract_scenario", "qualified_live_source"]

    @model_validator(mode="after")
    def no_promotion(self) -> "TikTokEvidenceDescriptor":
        if (self.kind == "contract_scenario") != (self.environment == "contract_test"):
            raise ValueError("source environment cannot be relabeled")
        return self


@dataclass(frozen=True)
class TikTokExecutionEvidence:
    """Existing bound reader protocols; descriptor is identity, never qualification."""

    descriptor: TikTokEvidenceDescriptor
    configuration: QualificationReader
    creation: ExposureReader
    activation: ActivationExposureReader
    decoded_contract_catalog: SocialCatalogReader | None = None

    def __post_init__(self) -> None:
        if self.decoded_contract_catalog is not None and (
            self.descriptor.environment != "contract_test"
            or self.descriptor.kind != "contract_scenario"
        ):
            raise ValueError("decoded catalog is contract-test only")


class TikTokEvidenceFactory(Protocol):
    def __call__(
        self,
        sessions: Callable[[], Session],
        authorize: ExecutionAuthorizer,
        actor_id: str,
        clock: Callable[[], datetime],
        /,
    ) -> TikTokExecutionEvidence: ...


@dataclass(frozen=True)
class RegisteredTikTokEvidenceSource:
    descriptor: TikTokEvidenceDescriptor
    build: TikTokEvidenceFactory


def admit_tiktok_source(
    manifest: TikTokExecutionManifestV1, registered: RegisteredTikTokEvidenceSource | None
) -> RegisteredTikTokEvidenceSource | None:
    """Pure identity admission; does not resolve catalog blockers or invoke readers."""
    # No native identity/pixel decoder has been verified for live admission.
    if manifest.environment == "live":
        return None
    if registered is None:
        return None
    value = registered.descriptor
    if (
        value.source_id != manifest.evidence_source_id
        or value.profile_digest != manifest.evidence_profile_digest
        or value.environment != manifest.environment
    ):
        return None
    return registered


def registered_tiktok_evidence(source_id: str) -> RegisteredTikTokEvidenceSource | None:
    """No production or fixture sources are registered by default."""
    return None


class TikTokCatalogContext(Frozen):
    """Reserved native read context; no catalog decoder is implemented here."""

    account: ExecutionAccount
    request_digest: Digest
    expires_at: AwareDatetime
    access_token: SecretStr = Field(exclude=True, repr=False)

    @model_validator(mode="after")
    def tiktok_only(self) -> "TikTokCatalogContext":
        if (
            self.account.account.platform != "tiktok_ads"
            or not self.access_token.get_secret_value()
        ):
            raise ValueError("owned TikTok catalog context required")
        return self


class TikTokOwnedContexts(Protocol):
    def catalog(self, request: SocialCatalogRequest, now: datetime, /) -> TikTokCatalogContext: ...

    def publication(self, request: SocialBoundRequest, /) -> SocialProviderContext: ...

    def activation(self, request: ActivationRequest, /) -> ActivationContext: ...


class TikTokOwnedContextFactory(Protocol):
    def __call__(
        self,
        sessions: Callable[[], Session],
        authorize: ExecutionAuthorizer,
        actor_id: str,
        manifest: TikTokExecutionManifestV1,
        clock: Callable[[], datetime],
        /,
    ) -> AbstractContextManager[TikTokOwnedContexts]: ...
