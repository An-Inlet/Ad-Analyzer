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


class SourceAuthorization(Base):
    __tablename__ = "customer_source_authorizations"
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider: Mapped[str] = mapped_column(String(32))
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    session_digest: Mapped[str] = mapped_column(
        ForeignKey("customer_sessions.digest", ondelete="CASCADE")
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String(24), default="pending")
    encrypted_grant: Mapped[str | None] = mapped_column(Text)
    accounts: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    selected_id: Mapped[str | None] = mapped_column(String(32))


class SourceConnection(Base):
    __tablename__ = "customer_source_connections"
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
        UniqueConstraint(
            "workspace_id", "provider", "external_id", name="uq_customer_source_account"
        ),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="RESTRICT"))
    integration_id: Mapped[int] = mapped_column(Integer)
    provider: Mapped[str] = mapped_column(String(32))
    account_id: Mapped[int | None] = mapped_column(Integer)
    external_id: Mapped[str] = mapped_column(String(128))
    encrypted_grant: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="connected")
    generation: Mapped[int] = mapped_column(Integer, default=1)
    window_start: Mapped[date] = mapped_column(Date)
    window_end: Mapped[date] = mapped_column(Date)
    cursor: Mapped[str | None] = mapped_column(Text)
    staged: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    covered_from: Mapped[date | None] = mapped_column(Date)
    covered_through: Mapped[date | None] = mapped_column(Date)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(64))
