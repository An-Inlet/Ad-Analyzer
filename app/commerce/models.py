from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class CommerceStore(Base):
    __tablename__ = "commerce_stores"
    __table_args__ = (
        UniqueConstraint("workspace_id", "shop_key", name="uq_commerce_store_identity"),
        UniqueConstraint("id", "workspace_id", name="uq_commerce_store_owner"),
        ForeignKeyConstraint(
            ["connection_id", "workspace_id"],
            ["workspace_integrations.id", "workspace_integrations.workspace_id"],
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    shop_key: Mapped[str] = mapped_column(String(64))
    shop_domain: Mapped[str] = mapped_column(String(253))
    connection_id: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    time_zone: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), default="active")
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revision: Mapped[int] = mapped_column(Integer, default=0)
    covered_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cursor: Mapped[str | None] = mapped_column(String(4096))
    error_code: Mapped[str | None] = mapped_column(String(64))


class CommerceOrder(Base):
    __tablename__ = "commerce_orders"
    __table_args__ = (
        ForeignKeyConstraint(
            ["store_id", "workspace_id"],
            ["commerce_stores.id", "commerce_stores.workspace_id"],
            ondelete="CASCADE",
        ),
    )
    store_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    order_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    privacy_key: Mapped[str] = mapped_column(String(64))
    customer_key: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fingerprint: Mapped[str] = mapped_column(String(64))
    quality: Mapped[str] = mapped_column(String(32))


class CommerceEntry(Base):
    __tablename__ = "commerce_entries"
    __table_args__ = (
        ForeignKeyConstraint(
            ["store_id", "order_key"],
            ["commerce_orders.store_id", "commerce_orders.order_key"],
            ondelete="CASCADE",
        ),
    )
    store_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    entry_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_key: Mapped[str] = mapped_column(String(64))
    happened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    currency: Mapped[str] = mapped_column(String(3))
    net_micros: Mapped[int] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(String(16))


class CommerceDailyRevision(Base):
    __tablename__ = "commerce_daily_revisions"
    store_id: Mapped[str] = mapped_column(
        ForeignKey("commerce_stores.id", ondelete="CASCADE"), primary_key=True
    )
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    currency: Mapped[str] = mapped_column(String(3))
    time_zone: Mapped[str] = mapped_column(String(64))
    net_micros: Mapped[int] = mapped_column(BigInteger)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CommerceSnapshot(Base):
    __tablename__ = "commerce_snapshots"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    store_id: Mapped[str] = mapped_column(ForeignKey("commerce_stores.id", ondelete="CASCADE"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revision: Mapped[int] = mapped_column(Integer)
    result: Mapped[dict[str, Any]] = mapped_column(JSON)


class CommerceSourceLink(Base):
    __tablename__ = "commerce_source_links"
    __table_args__ = (
        ForeignKeyConstraint(
            ["connection_id", "workspace_id"],
            ["workspace_integrations.id", "workspace_integrations.workspace_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["store_id", "workspace_id"],
            ["commerce_stores.id", "commerce_stores.workspace_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["store_id", "order_key"],
            ["commerce_orders.store_id", "commerce_orders.order_key"],
            ondelete="CASCADE",
        ),
    )
    connection_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    store_id: Mapped[str] = mapped_column(String(32))
    order_key: Mapped[str] = mapped_column(String(64))
    evidence: Mapped[str] = mapped_column(String(32), default="shopify_order_id")


class CommerceSuppression(Base):
    """Minimal erasure keys survive reconnects; no financial/customer attributes."""

    __tablename__ = "commerce_suppressions"
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    shop_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), primary_key=True)
    object_key: Mapped[str] = mapped_column(String(64), primary_key=True)


class CommerceShopAlias(Base):
    """Verified merchant-domain history for delayed privacy events after reconnect."""

    __tablename__ = "commerce_shop_aliases"
    shop_domain: Mapped[str] = mapped_column(String(253), primary_key=True)
    store_id: Mapped[str] = mapped_column(
        ForeignKey("commerce_stores.id", ondelete="CASCADE"), primary_key=True
    )
