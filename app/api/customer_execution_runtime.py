"""Request-scoped configured execution with legacy explicit injection compatibility."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request

from app.campaign_review.storage import get_media_store
from app.customers.access import Database, Principal, Provider
from app.production_runtime.provider_composition import configured_execution
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
    with configured_execution(
        db,
        principal,
        provider,
        settings,
        get_media_store,
        social_only="/execution/social/" in request.url.path,
    ) as runtime:
        yield runtime
