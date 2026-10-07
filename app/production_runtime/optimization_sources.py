"""Trusted Python source registry, deliberately empty; no configuration imports."""

from app.production_runtime.optimization_contracts import RegisteredOptimizationEvidenceSource


def registered_optimization_evidence(source_id: str) -> RegisteredOptimizationEvidenceSource | None:
    return None
