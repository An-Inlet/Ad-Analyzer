import re
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crm.models import CrmConnection
from app.imports.scope import ImportScopeError
from app.workspaces.models import Workspace, WorkspaceIntegration


@dataclass(frozen=True)
class CrmBinding:
    workspace_id: int
    connection_id: int
    provider: str
    secret_reference: str


def connection_for_scope(session: Session, workspace_id: int, connection_id: int) -> CrmConnection:
    if any(type(v) is not int or v < 1 for v in (workspace_id, connection_id)):
        raise ImportScopeError("invalid CRM scope")
    connection = session.scalar(
        select(CrmConnection)
        .join(
            WorkspaceIntegration, WorkspaceIntegration.id == CrmConnection.workspace_integration_id
        )
        .join(Workspace, Workspace.id == CrmConnection.workspace_id)
        .where(
            CrmConnection.workspace_id == workspace_id,
            CrmConnection.workspace_integration_id == connection_id,
            CrmConnection.status == "active",
            Workspace.status == "active",
            WorkspaceIntegration.workspace_id == workspace_id,
            WorkspaceIntegration.status == "active",
            WorkspaceIntegration.provider.in_(["crm", "klaviyo", "hubspot", "omnisend"]),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if connection is None:
        raise ImportScopeError("CRM ownership unavailable")
    return connection


class SecretReader(Protocol):
    def read(self, reference: str) -> str: ...


class ManagedSecretReader:
    def read(self, reference: str) -> str:
        # Pin a concrete version; latest aliases must not silently change a connection's key.
        if not re.fullmatch(r"projects/[^/]+/secrets/[^/]+/versions/[1-9][0-9]*", reference):
            raise ImportScopeError("CRM secret version is not configured")
        from google.cloud import secretmanager

        try:
            response = secretmanager.SecretManagerServiceClient().access_secret_version(
                request={"name": reference}, timeout=5
            )
            value = response.payload.data.decode("utf-8")
        except Exception:
            raise RuntimeError("CRM secret unavailable") from None
        if not 32 <= len(value) <= 4096:
            raise RuntimeError("CRM secret unavailable")
        return value


def get_secret_reader() -> SecretReader:
    return ManagedSecretReader()
