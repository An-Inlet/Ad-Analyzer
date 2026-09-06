from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class MetaConnection(Base):
    __tablename__ = "meta_connections"
    __table_args__ = (
        ForeignKeyConstraint(
            ["account_id", "workspace_id"],
            ["advertising_accounts.id", "advertising_accounts.workspace_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("id", "workspace_id", name="uq_meta_connection_workspace"),
        CheckConstraint("status IN ('connected','reconnect_required')", name="ck_meta_status"),
        CheckConstraint("phase IN ('campaigns','adsets','insights')", name="ck_meta_sync_phase"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), unique=True)
    account_id: Mapped[int] = mapped_column(Integer, unique=True)
    external_account_id: Mapped[str] = mapped_column(String(32), unique=True)
    status: Mapped[str] = mapped_column(String(32), default="connected")
    encrypted_credentials: Mapped[str] = mapped_column(Text)
    conversion_action_type: Mapped[str | None] = mapped_column(String(64))
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    covered_from: Mapped[date | None] = mapped_column(Date)
    covered_through: Mapped[date | None] = mapped_column(Date)
    window_start: Mapped[date | None] = mapped_column(Date)
    window_end: Mapped[date | None] = mapped_column(Date)
    phase: Mapped[str] = mapped_column(String(16), default="campaigns")
    cursor: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(String(64))


class MetaOAuthState(Base):
    __tablename__ = "meta_oauth_states"
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    actor_digest: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MetaPendingGrant(Base):
    __tablename__ = "meta_pending_grants"
    __table_args__ = (UniqueConstraint("workspace_id", "actor_digest", name="uq_meta_grant_actor"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    actor_digest: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    encrypted_credentials: Mapped[str] = mapped_column(Text)
    accounts: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    cursor: Mapped[str | None] = mapped_column(Text)


class MetaStagedMetric(Base):
    """Only completed windows replace shared metrics; partial pages remain here."""

    __tablename__ = "meta_staged_metrics"
    connection_id: Mapped[int] = mapped_column(
        ForeignKey("meta_connections.id", ondelete="CASCADE"), primary_key=True
    )
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), primary_key=True
    )
    metric_date: Mapped[date] = mapped_column(Date, primary_key=True)
    impressions: Mapped[int] = mapped_column(Integer)
    clicks: Mapped[int] = mapped_column(Integer)
    cost_micros: Mapped[int] = mapped_column(BigInteger)
    conversions: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    conversion_value_micros: Mapped[int] = mapped_column(BigInteger)


class MetaAudit(Base):
    __tablename__ = "meta_audits"
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    action: Mapped[str] = mapped_column(String(64))
    actor_role: Mapped[str] = mapped_column(String(32))
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
