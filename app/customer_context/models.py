"""Opaque rate state and encrypted continuation only; never profile payloads."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class CRMQuota(Base):
    __tablename__ = "customer_context_quotas"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fence: Mapped[str | None] = mapped_column(String(32))


class CRMCheckpoint(Base):
    __tablename__ = "customer_context_checkpoints"
    connection_id: Mapped[str] = mapped_column(
        ForeignKey("customer_source_connections.id", ondelete="CASCADE"), primary_key=True
    )
    generation: Mapped[int] = mapped_column(Integer)
    grant_digest: Mapped[str] = mapped_column(String(64))
    encrypted_progress: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(24), default="ready")
    fence: Mapped[str | None] = mapped_column(String(32))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ack_digest: Mapped[str | None] = mapped_column(String(64))
