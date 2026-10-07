"""Request-scoped configured execution with legacy explicit injection compatibility."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request

from app.customers.access import Database, Principal, Provider
from app.production_runtime.assembly import configured_google_execution
from app.publication.customer_runtime import (
    CustomerExecutionRuntime,
    get_customer_execution_runtime,
)
from app.settings import settings

Legacy = Annotated[CustomerExecutionRuntime | None, Depends(get_customer_execution_runtime)]


def get_configured_customer_execution_runtime(
    request: Request,
    db: Database,
    principal: Principal,
    provider: Provider,
    legacy: Legacy,
) -> Iterator[CustomerExecutionRuntime | None]:
    if legacy is not None:
        yield legacy
        return
    # This configured bundle cannot admit social bodies, even through direct API
    # requests. Reject before constructing the trusted evidence source or contexts.
    if "/execution/social/" in request.url.path:
        yield None
        return
    with configured_google_execution(db, principal, provider, settings) as runtime:
        yield runtime
