from uuid import uuid4

from sqlalchemy.orm import Session

from app.ads.enums import AdvertisingPlatform
from app.ads.models import AdvertisingAccount
from app.imports.scope import ImportScopeError, ensure_native_integration
from app.meta.models import MetaConnection
from app.shopify.models import ShopifyConnection
from app.workspaces.models import WorkspaceIntegration


def bind_meta(session: Session, row: MetaConnection, *, reconnect: bool = False) -> None:
    account = session.get(AdvertisingAccount, row.account_id)
    if (
        account is None
        or account.workspace_id != row.workspace_id
        or account.platform != AdvertisingPlatform.META_ADS
        or account.external_account_id != row.external_account_id
    ):
        raise ImportScopeError("import ownership unavailable")
    connection_id = row.workspace_integration_id or account.connection_id
    if reconnect and connection_id is not None:
        connection = session.get(WorkspaceIntegration, connection_id)
        if (
            connection is None
            or connection.workspace_id != row.workspace_id
            or connection.provider != "meta_ads"
        ):
            raise ImportScopeError("import ownership unavailable")
        connection.status = "active"
    connection = ensure_native_integration(
        session,
        workspace_id=row.workspace_id,
        provider="meta_ads",
        source_key="meta-" + uuid4().hex,
        connection_id=connection_id,
    )
    if account.connection_id not in (None, connection.id):
        raise ImportScopeError("import ownership unavailable")
    row.workspace_integration_id = account.connection_id = connection.id
    session.flush()


def bind_shopify(session: Session, row: ShopifyConnection) -> None:
    connection = ensure_native_integration(
        session,
        workspace_id=row.workspace_id,
        provider="shopify",
        source_key="shopify-" + uuid4().hex,
        connection_id=row.workspace_integration_id,
    )
    row.workspace_integration_id = connection.id
    session.flush()


def revoke_native_integration(session: Session, connection_id: int | None) -> None:
    if connection_id is not None:
        connection = session.get(WorkspaceIntegration, connection_id)
        if connection is not None:
            connection.status = "revoked"
