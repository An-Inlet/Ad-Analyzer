"""Trusted source ports only. No source, principal or epoch producer is registered."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.customers.access import CustomerPrincipal
from app.customers.identity import IdentityProvider
from app.initial_planning.start_configuration import InitialRuleEvidenceDescriptorV1
from app.optimization_candidates.service import (
    AuthorizedEvidenceTransform,
    AuthorizedFinalEvidenceCurrent,
    CandidateRuntime,
)
from app.production_runtime.candidate_configuration import CandidateEvidenceDescriptorV1
from app.reported_feedback.candidate_configuration import ReportedRuleEvidenceDescriptorV1
from app.session_automation.runtime import SemanticEpochProducer


@dataclass(frozen=True)
class CandidateEvidenceBinding:
    descriptor_digest: str
    authorized_transform: AuthorizedEvidenceTransform | None
    authorized_final_current: AuthorizedFinalEvidenceCurrent | None
    epoch_producers: tuple[SemanticEpochProducer, ...]


class CandidateEvidenceBuilder(Protocol):
    def __call__(
        self,
        candidate_base: CandidateRuntime,
        bound_principal: CustomerPrincipal,
        identity: IdentityProvider,
        clock: Callable[[], datetime],
        /,
    ) -> CandidateEvidenceBinding: ...


@dataclass(frozen=True)
class RegisteredCandidateEvidenceSource:
    descriptor: CandidateEvidenceDescriptorV1
    build: CandidateEvidenceBuilder

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "descriptor",
            CandidateEvidenceDescriptorV1.model_validate_json(self.descriptor.model_dump_json()),
        )
        if not callable(self.build):
            raise ValueError("candidate_source_invalid")


def validate_candidate_binding(
    descriptor: CandidateEvidenceDescriptorV1, binding: CandidateEvidenceBinding
) -> None:
    """Structural binding checks, not qualification of the callback's real facts.

    Future assembly must invoke this after the request-owned trusted builder and
    preserve existing evidence/profile, original-session and real-transport fences.
    """
    descriptor = CandidateEvidenceDescriptorV1.model_validate_json(descriptor.model_dump_json())
    expected_callbacks = (
        descriptor.kind != "unqualified_observation" or descriptor.feedback_dependent
    )
    if (
        descriptor.digest() != binding.descriptor_digest
        or (
            expected_callbacks
            and not (
                callable(binding.authorized_transform)
                and callable(binding.authorized_final_current)
            )
        )
        or (
            descriptor.kind == "unqualified_observation"
            and (
                binding.authorized_transform is not None
                or binding.authorized_final_current is not None
                or binding.epoch_producers
            )
        )
        or not isinstance(binding.epoch_producers, tuple)
    ):
        raise ValueError("candidate_source_binding_invalid")
    families: set[str] = set()
    for producer in binding.epoch_producers:
        if (
            producer.family in families
            or producer.family not in descriptor.semantic_producer_families
            or producer.environment != descriptor.environment
            or producer.source_schema != descriptor.source_schema
            or not callable(producer.authorized_read)
        ):
            raise ValueError("candidate_source_binding_invalid")
        families.add(producer.family)
    if families != set(descriptor.semantic_producer_families):
        raise ValueError("candidate_source_binding_invalid")


@dataclass(frozen=True)
class RegisteredReportedRuleSource:
    """The implementation is the owned DB comparison reader, never a learning callback."""

    descriptor: ReportedRuleEvidenceDescriptorV1

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "descriptor",
            ReportedRuleEvidenceDescriptorV1.model_validate_json(self.descriptor.model_dump_json()),
        )


@dataclass(frozen=True)
class RegisteredInitialRuleSource:
    descriptor: InitialRuleEvidenceDescriptorV1

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "descriptor",
            InitialRuleEvidenceDescriptorV1.model_validate_json(self.descriptor.model_dump_json()),
        )


def registered_candidate_source(
    source_id: str,
) -> (
    RegisteredCandidateEvidenceSource
    | RegisteredReportedRuleSource
    | RegisteredInitialRuleSource
    | None
):
    # No dynamic imports, mutable global registry or default scenario producer.
    return None
