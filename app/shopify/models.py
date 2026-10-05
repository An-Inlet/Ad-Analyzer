from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
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


class ShopifyConnection(Base):
    __tablename__ = "shopify_connections"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_integration_id", "workspace_id"],
            ["workspace_integrations.id", "workspace_integrations.workspace_id"],
            name="fk_shopifyconnection_integration_scope",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "workspace_id", name="uq_shopify_connection_workspace"),
        CheckConstraint("status IN ('connected','reconnect_required')", name="ck_shopify_status"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_integration_id: Mapped[int | None] = mapped_column(Integer)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), unique=True
    )
    shop_domain: Mapped[str] = mapped_column(String(253), unique=True)
    shop_name: Mapped[str] = mapped_column(String(255))
    currency_code: Mapped[str] = mapped_column(String(3))
    time_zone: Mapped[str] = mapped_column(String(64), default="UTC")
    status: Mapped[str] = mapped_column(String(32), default="connected")
    encrypted_credentials: Mapped[str] = mapped_column(Text)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    covered_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cursor: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(String(64))


class ShopifyOAuthState(Base):
    __tablename__ = "shopify_oauth_states"
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    shop_domain: Mapped[str] = mapped_column(String(253))
    actor_digest: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ShopifyOrder(Base):
    """Minimized order facts; no names, email, addresses, customer IDs, or raw order IDs."""

    __tablename__ = "shopify_orders"
    __table_args__ = (
        ForeignKeyConstraint(
            ["connection_id", "workspace_id"],
            ["shopify_connections.id", "shopify_connections.workspace_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("connection_id", "order_key", name="uq_shopify_order_key"),
        Index("ix_shopify_orders_workspace_created", "workspace_id", "created_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    connection_id: Mapped[int] = mapped_column(Integer)
    workspace_id: Mapped[int] = mapped_column(Integer)
    order_key: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    currency_code: Mapped[str] = mapped_column(String(3))
    net_collected_micros: Mapped[int] = mapped_column(BigInteger)
    refunded_micros: Mapped[int] = mapped_column(BigInteger)
    cancelled: Mapped[bool] = mapped_column(Boolean)
    customer_order_index: Mapped[int | None] = mapped_column(Integer)
    channel: Mapped[str] = mapped_column(String(32))
    # Only a locally validated campaign ID is retained, never arbitrary UTM text.
    campaign_id: Mapped[int | None] = mapped_column(ForeignKey("campaigns.id", ondelete="SET NULL"))
    products_complete: Mapped[bool] = mapped_column(Boolean)
    products: Mapped[list[dict[str, Any]]] = mapped_column(JSON)


class ShopifyTombstone(Base):
    __tablename__ = "shopify_tombstones"
    __table_args__ = (
        ForeignKeyConstraint(
            ["connection_id", "workspace_id"],
            ["shopify_connections.id", "shopify_connections.workspace_id"],
            ondelete="CASCADE",
        ),
    )
    connection_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ShopifyPrivacyRequest(Base):
    __tablename__ = "shopify_privacy_requests"
    __table_args__ = (
        ForeignKeyConstraint(
            ["connection_id", "workspace_id"],
            ["shopify_connections.id", "shopify_connections.workspace_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("connection_id", "request_key", name="uq_shopify_privacy_request"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    connection_id: Mapped[int] = mapped_column(Integer)
    workspace_id: Mapped[int] = mapped_column(Integer)
    request_key: Mapped[str] = mapped_column(String(64))
    order_keys: Mapped[list[str]] = mapped_column(JSON)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ShopifyAudit(Base):
    __tablename__ = "shopify_audits"
    __table_args__ = (Index("ix_shopify_audit_workspace_time", "workspace_id", "created_at"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    action: Mapped[str] = mapped_column(String(48))
    actor_role: Mapped[str] = mapped_column(String(32))
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
