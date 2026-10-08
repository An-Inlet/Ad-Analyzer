"""Authenticate scoped blocked intents before constructing execution dependencies."""

from app import advertising_capabilities
from app.customers.access import Database, MutationPrincipal, Principal, Provider
from app.publication.customer_authority import bind_authority


def deny_advertising_mutation(
    workspace_id: int, principal: MutationPrincipal, provider: Provider, db: Database
) -> None:
    bind_authority(principal, provider)(db, workspace_id, principal.user.id)
    advertising_capabilities.require_advertising_write()


def deny_advertising_options(
    workspace_id: int, principal: Principal, provider: Provider, db: Database
) -> None:
    bind_authority(principal, provider)(db, workspace_id, principal.user.id)
    advertising_capabilities.require_advertising_write()
