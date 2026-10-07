"""Configured optimization ports; native discovery never supplies qualification IDs."""

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal, Protocol

from pydantic import AwareDatetime, Field, model_validator
from sqlalchemy.orm import Session

from app.initial_planning.contracts import Frozen
from app.publication.contracts import fingerprint
from app.publication.customer_optimization_contracts import TargetRequest
from app.publication.execution_authorization import ExecutionAuthorizer
from app.publication.execution_contracts import ExecutionAccount, ProviderMandateBinding
from app.publication.optimization_contracts import (
    MoneyContext,
    OptimizationContext,
    OptimizationTarget,
)
from app.publication.optimization_execution_contracts import (
    OptimizationExposureReader,
    OptimizationQualification,
    OptimizationQualificationReader,
)
from app.publication.provider_contracts import Digest
from app.publication.replacement_contracts import ReplacementReader
from app.publication.settlement import SettlementReader

OptimizationProvider = Literal["google_ads", "meta_ads"]


class OptimizationExecutionManifestV1(Frozen):
    schema_version: Literal["inlet.optimization-execution-manifest.v1"] = (
        "inlet.optimization-execution-manifest.v1"
    )
    manifest_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    revision: int = Field(strict=True, gt=0)
    environment: Literal["contract_test", "live"]
    providers: tuple[OptimizationProvider, ...] = Field(min_length=1, max_length=2)
    evidence_source_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    evidence_profile_digest: Digest
    operating_policy_digest: Digest
    live_execution_enabled: bool = Field(strict=True)
    replacement_enabled: bool = Field(strict=True)
    settlement_enabled: bool = Field(strict=True)
    credential_minimum_remaining_seconds: int = Field(strict=True, ge=300, le=3600)
    context_lifetime_seconds: int = Field(strict=True, ge=1, le=300)

    @model_validator(mode="after")
    def exact(self) -> "OptimizationExecutionManifestV1":
        if tuple(sorted(set(self.providers))) != self.providers:
            raise ValueError("canonical unique providers required")
        if self.environment == "contract_test" and self.live_execution_enabled:
            raise ValueError("scenario cannot enable live execution")
        if self.context_lifetime_seconds > self.credential_minimum_remaining_seconds:
            raise ValueError("context exceeds credential lifetime")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class OwnedOptimizationInventoryRequestV1(Frozen):
    schema_version: Literal["inlet.owned-optimization-inventory-request.v1"] = (
        "inlet.owned-optimization-inventory-request.v1"
    )
    request: TargetRequest
    money: MoneyContext
    period_basis: Literal["confirmed_goal", "original_mandate"]
    original_mandate: ProviderMandateBinding | None

    @model_validator(mode="after")
    def basis(self) -> "OwnedOptimizationInventoryRequestV1":
        if self.request.scope.account.platform not in {"google_ads", "meta_ads"}:
            raise ValueError("provider unsupported")
        if (self.period_basis == "original_mandate") != (self.original_mandate is not None):
            raise ValueError("exact money horizon origin required")
        if self.money.currency != "USD" or self.money.currency_exponent != 2:
            raise ValueError("only USD exponent two supported")
        return self

    def digest(self) -> str:
        return fingerprint(self.schema_version, self.model_dump(mode="json"))


class OwnedOptimizationCandidateV1(Frozen):
    schema_version: Literal["inlet.owned-optimization-candidate.v1"] = (
        "inlet.owned-optimization-candidate.v1"
    )
    request_digest: Digest
    label: str = Field(min_length=1, max_length=160)
    parent_label: str = Field(min_length=1, max_length=160)
    target: OptimizationTarget
    inventory_digest: Digest
    observed_at: AwareDatetime
    expires_at: AwareDatetime

    @model_validator(mode="after")
    def bounded(self) -> "OwnedOptimizationCandidateV1":
        if self.target.kind != "campaign":
            raise ValueError("only campaign inventory supported")
        if not self.observed_at < self.expires_at <= self.observed_at + timedelta(minutes=5):
            raise ValueError("candidate lifetime exceeds bound")
        return self


class OptimizationCatalogAdmissionReader(Protocol):
    def __call__(
        self,
        request: OwnedOptimizationInventoryRequestV1,
        candidate: OwnedOptimizationCandidateV1,
        now: datetime,
        /,
    ) -> OptimizationQualification | None: ...


class OptimizationEvidenceDescriptor(Frozen):
    source_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    profile_digest: Digest
    environment: Literal["contract_test", "live"]
    kind: Literal["contract_scenario", "qualified_live_source"]
    providers: tuple[OptimizationProvider, ...] = Field(min_length=1, max_length=2)

    @model_validator(mode="after")
    def exact(self) -> "OptimizationEvidenceDescriptor":
        if tuple(sorted(set(self.providers))) != self.providers:
            raise ValueError("canonical unique providers required")
        if (self.kind == "contract_scenario") != (self.environment == "contract_test"):
            raise ValueError("source cannot be promoted across environments")
        return self


@dataclass(frozen=True)
class OptimizationExecutionEvidence:
    descriptor: OptimizationEvidenceDescriptor
    catalog_admission: OptimizationCatalogAdmissionReader
    qualification: OptimizationQualificationReader
    exposure: OptimizationExposureReader
    replacement: ReplacementReader | None
    settlement: SettlementReader | None


class OptimizationEvidenceFactory(Protocol):
    def __call__(
        self,
        sessions: Callable[[], Session],
        authorize: ExecutionAuthorizer,
        actor_id: str,
        clock: Callable[[], datetime],
        /,
    ) -> OptimizationExecutionEvidence: ...


@dataclass(frozen=True)
class RegisteredOptimizationEvidenceSource:
    descriptor: OptimizationEvidenceDescriptor
    build: OptimizationEvidenceFactory


def admit_optimization_source(
    manifest: OptimizationExecutionManifestV1,
    registered: RegisteredOptimizationEvidenceSource | None,
    platform: str,
) -> RegisteredOptimizationEvidenceSource | None:
    """Pure provider gate before factory/context/IO; descriptor is not proof."""
    if platform not in manifest.providers or registered is None:
        return None
    source = registered.descriptor
    if (
        source.source_id != manifest.evidence_source_id
        or source.profile_digest != manifest.evidence_profile_digest
        or source.environment != manifest.environment
        or source.providers != manifest.providers
        or (manifest.environment == "live" and not manifest.live_execution_enabled)
    ):
        return None
    return registered


class OptimizationOwnedContexts(Protocol):
    def optimization(self, scope: ExecutionAccount, /) -> OptimizationContext: ...


class OptimizationOwnedContextFactory(Protocol):
    def __call__(
        self,
        sessions: Callable[[], Session],
        authorize: ExecutionAuthorizer,
        actor_id: str,
        manifest: OptimizationExecutionManifestV1,
        clock: Callable[[], datetime],
        /,
    ) -> AbstractContextManager[OptimizationOwnedContexts]: ...
