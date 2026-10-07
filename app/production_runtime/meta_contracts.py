"""Minimal Meta image assembly ports; no source registry, authority or live factory."""

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

from pydantic import Field, model_validator
from sqlalchemy.orm import Session

from app.collectors.meta_catalog import MetaCatalogContext
from app.initial_planning.contracts import Frozen
from app.publication.activation_contracts import ActivationContext, ActivationRequest
from app.publication.activation_review import ActivationExposureReader
from app.publication.contracts import fingerprint
from app.publication.coordinator_contracts import ExposureReader, QualificationReader
from app.publication.execution_authorization import ExecutionAuthorizer
from app.publication.provider_contracts import Digest
from app.publication.social_catalog import SocialCatalogRequest
from app.publication.social_contracts import SocialBoundRequest, SocialProviderContext


class MetaExecutionManifestV1(Frozen):
    schema_version: Literal["inlet.meta-execution-manifest.v1"] = "inlet.meta-execution-manifest.v1"
    manifest_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    revision: int = Field(strict=True, gt=0)
    environment: Literal["contract_test", "live"]
    api_version: Literal["v26.0"]
    evidence_source_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    evidence_profile_digest: Digest
    configuration_bundle_digest: Digest
    live_execution_enabled: bool = Field(strict=True)
    activation_enabled: bool = Field(strict=True)
    credential_minimum_remaining_seconds: int = Field(strict=True, ge=300, le=3600)
    context_lifetime_seconds: int = Field(strict=True, ge=1, le=300)

    @model_validator(mode="after")
    def bounded(self) -> "MetaExecutionManifestV1":
        if self.environment == "contract_test" and self.live_execution_enabled:
            raise ValueError("scenario cannot enable live execution")
        if self.context_lifetime_seconds > self.credential_minimum_remaining_seconds:
            raise ValueError("context exceeds credential lifetime")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class MetaEvidenceDescriptor(Frozen):
    source_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    profile_digest: Digest
    environment: Literal["contract_test", "live"]
    kind: Literal["contract_scenario", "qualified_live_source"]

    @model_validator(mode="after")
    def no_promotion(self) -> "MetaEvidenceDescriptor":
        if (self.kind == "contract_scenario") != (self.environment == "contract_test"):
            raise ValueError("source environment cannot be relabeled")
        return self


@dataclass(frozen=True)
class MetaExecutionEvidence:
    """Existing bound reader protocols; descriptor is identity, never qualification."""

    descriptor: MetaEvidenceDescriptor
    configuration: QualificationReader
    creation: ExposureReader
    activation: ActivationExposureReader


class MetaEvidenceFactory(Protocol):
    def __call__(
        self,
        sessions: Callable[[], Session],
        authorize: ExecutionAuthorizer,
        actor_id: str,
        clock: Callable[[], datetime],
        /,
    ) -> MetaExecutionEvidence: ...


@dataclass(frozen=True)
class RegisteredMetaEvidenceSource:
    descriptor: MetaEvidenceDescriptor
    build: MetaEvidenceFactory


def admit_meta_source(
    manifest: MetaExecutionManifestV1, registered: RegisteredMetaEvidenceSource | None
) -> RegisteredMetaEvidenceSource | None:
    """Pure identity admission; does not resolve catalog blockers or invoke readers."""
    if registered is None:
        return None
    value = registered.descriptor
    if (
        value.source_id != manifest.evidence_source_id
        or value.profile_digest != manifest.evidence_profile_digest
        or value.environment != manifest.environment
        or (manifest.environment == "live" and not manifest.live_execution_enabled)
    ):
        return None
    return registered


class MetaOwnedContexts(Protocol):
    def catalog(self, request: SocialCatalogRequest, now: datetime, /) -> MetaCatalogContext: ...

    def publication(self, request: SocialBoundRequest, /) -> SocialProviderContext: ...

    def activation(self, request: ActivationRequest, /) -> ActivationContext: ...


class MetaOwnedContextFactory(Protocol):
    def __call__(
        self,
        sessions: Callable[[], Session],
        authorize: ExecutionAuthorizer,
        actor_id: str,
        manifest: MetaExecutionManifestV1,
        clock: Callable[[], datetime],
        /,
    ) -> AbstractContextManager[MetaOwnedContexts]: ...
