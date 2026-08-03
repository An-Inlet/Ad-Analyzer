from typing import Any, cast

from app.ads.models import AdvertisingAccount, Campaign
from app.workspaces.models import (
    Workspace,
    WorkspaceConfiguration,
    WorkspaceIntegration,
    WorkspaceMembership,
)
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session


class WorkspaceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _page(self, stmt: Select[Any], limit: int, offset: int) -> tuple[list[Any], int]:
        total = self.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        return list(self.session.scalars(stmt.limit(limit).offset(offset)).all()), total

    def list_workspaces(
        self, allowed_ids: set[int] | None, limit: int, offset: int
    ) -> tuple[list[Workspace], int]:
        stmt = select(Workspace).where(Workspace.status == "active")
        if allowed_ids is not None:
            if not allowed_ids:
                return [], 0
            stmt = stmt.where(Workspace.id.in_(allowed_ids))
        return cast(
            tuple[list[Workspace], int],
            self._page(stmt.order_by(Workspace.name.asc(), Workspace.id.asc()), limit, offset),
        )

    def get_by_id(self, workspace_id: int) -> Workspace | None:
        return self.session.get(Workspace, workspace_id)

    def get_by_slug(self, slug: str) -> Workspace | None:
        return self.session.scalar(select(Workspace).where(Workspace.slug == slug.casefold()))

    def list_advertising_accounts(
        self, workspace_id: int, limit: int, offset: int
    ) -> tuple[list[AdvertisingAccount], int]:
        stmt = select(AdvertisingAccount).where(AdvertisingAccount.workspace_id == workspace_id)
        return cast(
            tuple[list[AdvertisingAccount], int],
            self._page(stmt.order_by(AdvertisingAccount.id.asc()), limit, offset),
        )

    def configuration(self, workspace_id: int) -> WorkspaceConfiguration | None:
        return self.session.get(WorkspaceConfiguration, workspace_id)

    def integrations(self, workspace_id: int) -> list[WorkspaceIntegration]:
        return list(
            self.session.scalars(
                select(WorkspaceIntegration)
                .where(WorkspaceIntegration.workspace_id == workspace_id)
                .order_by(WorkspaceIntegration.display_name.asc())
            ).all()
        )

    def memberships(self, workspace_id: int) -> list[WorkspaceMembership]:
        return list(
            self.session.scalars(
                select(WorkspaceMembership)
                .where(WorkspaceMembership.workspace_id == workspace_id)
                .order_by(WorkspaceMembership.principal.asc())
            ).all()
        )

    def dashboard_rows(
        self, allowed_ids: set[int] | None, limit: int, offset: int
    ) -> tuple[list[tuple[Workspace, int, int, int]], int]:
        workspaces, total = self.list_workspaces(allowed_ids, limit, offset)
        if not workspaces:
            return [], total
        ids = [workspace.id for workspace in workspaces]
        account_counts: dict[int, int] = {
            workspace_id: count
            for workspace_id, count in self.session.execute(
                select(AdvertisingAccount.workspace_id, func.count(AdvertisingAccount.id))
                .where(AdvertisingAccount.workspace_id.in_(ids))
                .group_by(AdvertisingAccount.workspace_id)
            ).tuples()
        }
        campaign_counts: dict[int, int] = {
            workspace_id: count
            for workspace_id, count in self.session.execute(
                select(AdvertisingAccount.workspace_id, func.count(Campaign.id))
                .join(Campaign, Campaign.account_id == AdvertisingAccount.id)
                .where(AdvertisingAccount.workspace_id.in_(ids))
                .group_by(AdvertisingAccount.workspace_id)
            ).tuples()
        }
        integration_counts: dict[int, int] = {
            workspace_id: count
            for workspace_id, count in self.session.execute(
                select(WorkspaceIntegration.workspace_id, func.count(WorkspaceIntegration.id))
                .where(
                    WorkspaceIntegration.workspace_id.in_(ids),
                    WorkspaceIntegration.status.in_(["configured", "active"]),
                )
                .group_by(WorkspaceIntegration.workspace_id)
            ).tuples()
        }
        return [
            (
                workspace,
                int(account_counts.get(workspace.id, 0)),
                int(campaign_counts.get(workspace.id, 0)),
                int(integration_counts.get(workspace.id, 0)),
            )
            for workspace in workspaces
        ], total
