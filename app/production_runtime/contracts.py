"""Minimal Google creation/activation assembly interfaces, never client proof."""

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

from pydantic import Field, model_validator
from sqlalchemy.orm import Session

from app.collectors.google_catalog import GoogleCatalogContext
from app.initial_planning.contracts import Frozen
from app.publication.activation_contracts import ActivationContext, ActivationRequest
from app.publication.activation_review import ActivationExposureReader
from app.publication.contracts import PublicationScope, fingerprint
from app.publication.coordinator_contracts import ExposureReader
from app.publication.customer_catalog import GoogleCatalogRequest
from app.publication.execution_authorization import ExecutionAuthorizer
from app.publication.provider_contracts import Digest, ProviderContext


class GoogleExecutionManifestV1(Frozen):
    schema_version: Literal["inlet.google-execution-manifest.v1"] = (
        "inlet.google-execution-manifest.v1"
    )
    manifest_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    revision: int = Field(strict=True, gt=0)
    environment: Literal["contract_test", "live"]
    api_version: Literal["v25"]
    evidence_source_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    evidence_profile_digest: Digest
    live_execution_enabled: bool = Field(strict=True)
    activation_enabled: bool = Field(strict=True)
    credential_minimum_remaining_seconds: int = Field(strict=True, ge=60, le=3600)
    context_lifetime_seconds: int = Field(strict=True, ge=1, le=300)

    @model_validator(mode="after")
    def environment_flags(self) -> "GoogleExecutionManifestV1":
        if self.environment == "contract_test" and self.live_execution_enabled:
            raise ValueError("test manifest cannot enable live execution")
        if self.context_lifetime_seconds > self.credential_minimum_remaining_seconds:
            raise ValueError("context exceeds required credential lifetime")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class GoogleEvidenceDescriptor(Frozen):
    """Identity of a trusted server implementation, not an admitted financial fact."""

    source_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    profile_digest: Digest
    environment: Literal["contract_test", "live"]
    kind: Literal["contract_scenario", "qualified_live_source"]

    @model_validator(mode="after")
    def no_scenario_upgrade(self) -> "GoogleEvidenceDescriptor":
        if (self.kind == "contract_scenario") != (self.environment == "contract_test"):
            raise ValueError("source kind cannot be relabeled across environments")
        return self


@dataclass(frozen=True)
class GoogleExecutionEvidence:
    """Server-built readers; not deserializable and never accepted in request/config JSON.

    Existing coordinator readers retain exact mandate/plan/hold arguments and their
    economic guards. The descriptor itself never proves bounds or qualification.
    """

    descriptor: GoogleEvidenceDescriptor
    creation: ExposureReader
    activation: ActivationExposureReader


class GoogleEvidenceFactory(Protocol):
    def __call__(
        self,
        sessions: Callable[[], Session],
        authorize: ExecutionAuthorizer,
        actor_id: str,
        clock: Callable[[], datetime],
        /,
    ) -> GoogleExecutionEvidence: ...


@dataclass(frozen=True)
class RegisteredGoogleEvidenceSource:
    """Only trusted server code installs this; manifest chooses an exact registered ID."""

    descriptor: GoogleEvidenceDescriptor
    build: GoogleEvidenceFactory


def admit_source(
    manifest: GoogleExecutionManifestV1,
    registered: RegisteredGoogleEvidenceSource | None,
) -> RegisteredGoogleEvidenceSource | None:
    """Pure pre-construction gate: neither invokes a factory nor creates transports."""
    if registered is None:
        return None
    descriptor = registered.descriptor
    if (
        descriptor.environment != manifest.environment
        or descriptor.source_id != manifest.evidence_source_id
        or descriptor.profile_digest != manifest.evidence_profile_digest
        or (manifest.environment == "live" and descriptor.kind == "contract_scenario")
        or (manifest.environment == "live" and not manifest.live_execution_enabled)
    ):
        return None
    return registered


class GoogleOwnedContexts(Protocol):
    """Fresh original-session/account/generation credentials, owned for one request.

    Implementations use short private sessions around refresh and must close all
    transport resources through the enclosing factory context manager. No source
    credential, token or principal is stored in a manifest or global cache.
    """

    def publication(self, scope: PublicationScope, /) -> ProviderContext: ...

    def catalog(self, request: GoogleCatalogRequest, now: datetime, /) -> GoogleCatalogContext: ...

    def activation(self, request: ActivationRequest, /) -> ActivationContext: ...


class GoogleOwnedContextFactory(Protocol):
    def __call__(
        self,
        sessions: Callable[[], Session],
        authorize: ExecutionAuthorizer,
        actor_id: str,
        manifest: GoogleExecutionManifestV1,
        clock: Callable[[], datetime],
        /,
    ) -> AbstractContextManager[GoogleOwnedContexts]: ...
