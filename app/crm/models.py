from datetime import UTC, datetime
from decimal import Decimal

from app.database.session import Base
from app.workspaces.models import Workspace, WorkspaceIntegration  # noqa: F401
from sqlalchemy import JSON, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.now(UTC)


class CrmConnection(Base):
    __tablename__ = "crm_connections"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_crm_connections_workspace_name"),
        Index("ix_crm_connections_workspace_status", "workspace_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False, default=1
    )
    workspace_integration_id: Mapped[int | None] = mapped_column(
        ForeignKey("workspace_integrations.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    secret_manager_reference: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class CrmEventRecord(Base):
    __tablename__ = "crm_events"
    __table_args__ = (
        UniqueConstraint("connection_id", "external_event_id", name="uq_crm_events_source_event"),
        Index("ix_crm_events_status_created", "processing_status", "created_at"),
        Index("ix_crm_events_lead", "crm_lead_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    connection_id: Mapped[int] = mapped_column(
        ForeignKey("crm_connections.id", ondelete="RESTRICT"), nullable=False
    )
    external_event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    crm_lead_id: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_version: Mapped[int] = mapped_column(nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    normalized_payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    processing_status: Mapped[str] = mapped_column(String(32), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class LeadAttribution(Base):
    __tablename__ = "lead_attribution"
    __table_args__ = (
        UniqueConstraint("connection_id", "crm_lead_id", name="uq_lead_attribution_source_lead"),
        Index("ix_lead_attribution_lifecycle", "lifecycle_state"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    connection_id: Mapped[int] = mapped_column(
        ForeignKey("crm_connections.id", ondelete="RESTRICT"), nullable=False
    )
    crm_lead_id: Mapped[str] = mapped_column(String(128), nullable=False)
    crm_opportunity_id: Mapped[str | None] = mapped_column(String(128))
    lifecycle_state: Mapped[str] = mapped_column(String(64), nullable=False)
    lifecycle_occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    value: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    currency: Mapped[str | None] = mapped_column(String(3))
    attribution_data: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class CrmSyncRun(Base):
    __tablename__ = "crm_sync_runs"
    __table_args__ = (Index("ix_crm_sync_runs_status_started", "status", "started_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    connection_id: Mapped[int] = mapped_column(
        ForeignKey("crm_connections.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    processed_count: Mapped[int] = mapped_column(nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
