from dataclasses import dataclass
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ads.enums import AdvertisingPlatform
from app.ads.models import AdvertisingAccount
from app.settings import Settings
from app.workspaces.locking import lock_workspace_row
from app.workspaces.models import Workspace, WorkspaceIntegration


class ImportScopeError(ValueError):
    """Sanitized permanent rejection; never infer a missing customer or connection."""


@dataclass(frozen=True)
class AdvertisingImportScope:
    workspace_id: int
    connection_id: int
    account_id: int
    platform: AdvertisingPlatform

    def __post_init__(self) -> None:
        if any(
            type(value) is not int or value < 1
            for value in (self.workspace_id, self.connection_id, self.account_id)
        ):
            raise ImportScopeError("invalid import scope")

    def lock_key(self, namespace: int) -> int:
        value = (
            f"{namespace}:{self.workspace_id}:{self.connection_id}:"
            f"{self.account_id}:{self.platform}"
        )
        return int.from_bytes(sha256(value.encode()).digest()[:8], "big", signed=True)


def validate_advertising_scope(
    session: Session,
    scope: AdvertisingImportScope,
) -> tuple[AdvertisingAccount, WorkspaceIntegration]:
    workspace = lock_workspace_row(session, scope.workspace_id)
    if workspace is None or workspace.status != "active":
        raise ImportScopeError("import ownership unavailable")
    row = (
        session.execute(
            select(AdvertisingAccount, WorkspaceIntegration)
            .join(WorkspaceIntegration, WorkspaceIntegration.id == AdvertisingAccount.connection_id)
            .join(Workspace, Workspace.id == AdvertisingAccount.workspace_id)
            .where(
                AdvertisingAccount.id == scope.account_id,
                AdvertisingAccount.workspace_id == scope.workspace_id,
                AdvertisingAccount.platform == scope.platform,
                WorkspaceIntegration.id == scope.connection_id,
                WorkspaceIntegration.workspace_id == scope.workspace_id,
                WorkspaceIntegration.provider == scope.platform.value,
                WorkspaceIntegration.status == "active",
                Workspace.status == "active",
            )
            .with_for_update(of=(AdvertisingAccount, WorkspaceIntegration))
            .execution_options(populate_existing=True)
        )
        .tuples()
        .one_or_none()
    )
    if row is None:
        raise ImportScopeError("import ownership unavailable")
    return row


def google_scope(settings: Settings) -> AdvertisingImportScope:
    if not all(
        (
            settings.google_ads_workspace_id,
            settings.google_ads_connection_id,
            settings.google_ads_account_id,
            settings.google_ads_credentials_reference,
        )
    ):
        raise ImportScopeError("Google Ads import scope is not configured")
    return AdvertisingImportScope(
        settings.google_ads_workspace_id or 0,
        settings.google_ads_connection_id or 0,
        settings.google_ads_account_id or 0,
        AdvertisingPlatform.GOOGLE_ADS,
    )


def ensure_native_integration(
    session: Session,
    *,
    workspace_id: int,
    provider: str,
    source_key: str,
    connection_id: int | None,
    reauthorize: bool = False,
) -> WorkspaceIntegration:
    """Bind an already-owned native connection, never pick an arbitrary active connection.

    Native callers hold their connection row lock. Migration handles existing rows;
    this path also supports freshly authorized connections in the same transaction.
    """
    # PostgreSQL NO KEY UPDATE blocks status changes while remaining compatible
    # with KEY SHARE locks acquired by concurrent native/account FK inserts.
    workspace = session.scalar(
        select(Workspace)
        .where(Workspace.id == workspace_id)
        .with_for_update(key_share=True)
        .execution_options(populate_existing=True)
    )
    if workspace is None or workspace.status != "active":
        raise ImportScopeError("import ownership unavailable")
    if connection_id is not None:
        connection = session.scalar(
            select(WorkspaceIntegration)
            .where(WorkspaceIntegration.id == connection_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if (
            connection is None
            or connection.workspace_id != workspace_id
            or connection.provider != provider
            or (connection.status != "active" and not reauthorize)
        ):
            raise ImportScopeError("import ownership unavailable")
        if reauthorize:
            connection.status = "active"
        return connection
    connection = WorkspaceIntegration(
        workspace_id=workspace_id,
        integration_key=source_key,
        provider=provider,
        display_name=provider,
        status="active",
        configuration={},
    )
    session.add(connection)
    session.flush()
    return connection
