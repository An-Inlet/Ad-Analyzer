"""Owned catalog provenance, retained by callers only after their final authority fence."""

from dataclasses import dataclass
from typing import Literal

from app.production_runtime.optimization_contracts import OwnedOptimizationCandidateV1
from app.publication.customer_optimization_contracts import TargetCatalog
from app.publication.optimization_execution_contracts import OptimizationQualification

ExclusionReason = Literal[
    "unsupported_owner", "unqualified", "label_unavailable", "unsupported_state"
]


@dataclass(frozen=True)
class OwnedOptimizationAdmission:
    option_id: str
    candidate: OwnedOptimizationCandidateV1
    qualification: OptimizationQualification
    state_digest: str


@dataclass(frozen=True)
class OwnedOptimizationCatalogRead:
    catalog: TargetCatalog
    admitted: tuple[OwnedOptimizationAdmission, ...]
    exclusions: tuple[tuple[ExclusionReason, int], ...]
