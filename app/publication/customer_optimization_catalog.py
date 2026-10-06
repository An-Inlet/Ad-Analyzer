"""Explicit server inventory plus actual adapter reads; never browser native IDs."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.publication.customer_optimization_contracts import (
    TargetCatalog,
    TargetOption,
    TargetRequest,
)
from app.publication.optimization_contracts import MoneyContext, OptimizationTarget
from app.publication.optimization_execution_contracts import OptimizationRuntime


@dataclass(frozen=True)
class NamedOptimizationTarget:
    scope_digest: str
    label: str
    parent_label: str
    target: OptimizationTarget
    money: MoneyContext
    qualification_id: str
    qualification_revision: int


@dataclass(frozen=True)
class ConfiguredOptimizationCatalog:
    """Finite operator-configured inventory; readback is not exposure qualification.

    Configuration must enumerate the complete offered inventory for each owned scope.
    More than 50 matches rejects instead of silently hiding targets. No default
    configuration or credential discovery is installed.
    """

    runtime: OptimizationRuntime
    inventory: tuple[NamedOptimizationTarget, ...]

    def __call__(self, request: TargetRequest, now: datetime, /) -> TargetCatalog:
        from app.publication.contracts import fingerprint

        scope_digest = fingerprint(
            "inlet.optimization-catalog-scope.v1", request.scope.model_dump(mode="json")
        )
        matched = [item for item in self.inventory if item.scope_digest == scope_digest]
        if len(self.inventory) > 1000 or len(matched) > 50:
            raise ValueError("configured catalog exceeds bound")
        options = []
        for item in matched:
            state = self.runtime.transport(request.scope).read_current(
                request.scope,
                item.target,
                item.money,
                item.qualification_id,
                item.qualification_revision,
                self.runtime.context(request.scope),
                now,
            )
            options.append(
                TargetOption(label=item.label, parent_label=item.parent_label, state=state)
            )
        return TargetCatalog(
            request=request,
            observed_at=now,
            expires_at=now + timedelta(minutes=1),
            options=options,
            complete=True,
        )
