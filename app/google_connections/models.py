from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class GoogleAuthorization(Base):
    __tablename__ = "google_customer_authorizations"
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    session_digest: Mapped[str] = mapped_column(
        ForeignKey("customer_sessions.digest", ondelete="CASCADE")
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String(24), default="pending")
    encrypted_grant: Mapped[str | None] = mapped_column(Text)
    accounts: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    selected_connection_id: Mapped[str | None] = mapped_column(String(32))


class GoogleCustomerConnection(Base):
    __tablename__ = "google_customer_connections"
    __table_args__ = (
        ForeignKeyConstraint(
            ["integration_id", "workspace_id"],
            ["workspace_integrations.id", "workspace_integrations.workspace_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["account_id", "workspace_id", "integration_id"],
            [
                "advertising_accounts.id",
                "advertising_accounts.workspace_id",
                "advertising_accounts.connection_id",
            ],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("workspace_id", "external_account_id", name="uq_google_customer_account"),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="RESTRICT"))
    integration_id: Mapped[int] = mapped_column(Integer)
    account_id: Mapped[int] = mapped_column(Integer)
    external_account_id: Mapped[str] = mapped_column(String(10))
    login_customer_id: Mapped[str | None] = mapped_column(String(10))
    encrypted_grant: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="connected")
    generation: Mapped[int] = mapped_column(Integer, default=1)
    backfill_through: Mapped[date] = mapped_column(Date)
    history_floor: Mapped[date] = mapped_column(Date)
    phase: Mapped[str] = mapped_column(String(16), default="recent")
    window_start: Mapped[date] = mapped_column(Date)
    window_end: Mapped[date] = mapped_column(Date)
    cursor: Mapped[str | None] = mapped_column(Text)
    staged: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(64))


class GoogleImportCompletion(Base):
    __tablename__ = "google_customer_import_completions"
    job_id: Mapped[int] = mapped_column(
        ForeignKey("job_runs.id", ondelete="CASCADE"), primary_key=True
    )
    state: Mapped[str] = mapped_column(String(16), default="pending")
