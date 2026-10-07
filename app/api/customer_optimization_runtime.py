"""Original-session configured optimization with explicit legacy fixture compatibility."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends

from app.customers.access import Database, Principal, Provider
from app.production_runtime.optimization_assembly import configured_optimization
from app.publication.customer_optimization_contracts import (
    CustomerOptimizationRuntime,
    get_customer_optimization_runtime,
)
from app.settings import settings

Legacy = Annotated[CustomerOptimizationRuntime | None, Depends(get_customer_optimization_runtime)]


def get_configured_customer_optimization_runtime(
    db: Database,
    principal: Principal,
    provider: Provider,
    legacy: Legacy,
) -> Iterator[CustomerOptimizationRuntime | None]:
    if legacy is not None:
        yield legacy
        return
    with configured_optimization(db, principal, provider, settings) as runtime:
        yield runtime
