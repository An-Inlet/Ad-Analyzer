from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class WorkspaceTimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class Workspace(WorkspaceTimestampMixin, Base):
    """One client account inside the shared Ad Analyzer platform."""

    __tablename__ = "workspaces"
    __table_args__ = (
        CheckConstraint(
            "slug = lower(slug) AND slug NOT LIKE '% %'",
            name="ck_workspaces_slug_canonical",
        ),
        Index("ix_workspaces_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    client_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class WorkspaceConfiguration(WorkspaceTimestampMixin, Base):
    """Workspace-owned behavior; no client configuration is process-global."""

    __tablename__ = "workspace_configurations"

    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    analysis: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    automation: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    notifications: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    branding: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)


class WorkspaceMembership(WorkspaceTimestampMixin, Base):
    __tablename__ = "workspace_memberships"
    __table_args__ = (
        UniqueConstraint("workspace_id", "principal", name="uq_workspace_memberships_principal"),
        CheckConstraint(
            "role IN ('owner', 'admin', 'analyst', 'viewer')",
            name="ck_workspace_memberships_role",
        ),
        CheckConstraint(
            "status IN ('active', 'suspended')",
            name="ck_workspace_memberships_status",
        ),
        Index("ix_workspace_memberships_principal_status", "principal", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    principal: Mapped[str] = mapped_column(String(320), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")


class WorkspaceIntegration(WorkspaceTimestampMixin, Base):
    __tablename__ = "workspace_integrations"
    __table_args__ = (
        UniqueConstraint("id", "workspace_id", name="uq_workspace_integrations_id_workspace"),
        UniqueConstraint("workspace_id", "integration_key", name="uq_workspace_integrations_key"),
        Index("ix_workspace_integrations_provider_status", "provider", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    integration_key: Mapped[str] = mapped_column(String(128), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="configured")
    configuration: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    secret_manager_reference: Mapped[str | None] = mapped_column(String(512))


class WorkspaceFinding(WorkspaceTimestampMixin, Base):
    """Persistent, deduplicated finding owned by exactly one workspace."""

    __tablename__ = "workspace_findings"
    __table_args__ = (
        UniqueConstraint("workspace_id", "dedupe_key", name="uq_workspace_findings_dedupe"),
        ForeignKeyConstraint(
            ["advertising_account_id", "workspace_id"],
            ["advertising_accounts.id", "advertising_accounts.workspace_id"],
            name="fk_workspace_findings_ad_account_workspace",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["campaign_id", "advertising_account_id"],
            ["campaigns.id", "campaigns.account_id"],
            name="fk_workspace_findings_campaign_account",
            ondelete="CASCADE",
        ),
        Index("ix_workspace_findings_status_detected", "workspace_id", "status", "detected_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    advertising_account_id: Mapped[int | None] = mapped_column(Integer)
    campaign_id: Mapped[int | None] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"))
    dedupe_key: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(96), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    supporting_metrics: Mapped[dict[str, object]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    window_start: Mapped[date | None] = mapped_column(Date)
    window_end: Mapped[date | None] = mapped_column(Date)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
