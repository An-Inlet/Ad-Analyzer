from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class IntelligenceRecord(Base):
    """Versioned, validated business records; contains no advertising credentials."""

    __tablename__ = "intelligence_records"
    __table_args__ = (
        UniqueConstraint("workspace_id", "kind", "record_key", name="uq_intelligence_record_key"),
        UniqueConstraint("id", "workspace_id", name="uq_intelligence_record_workspace"),
        CheckConstraint("version > 0", name="ck_intelligence_record_version"),
        CheckConstraint(
            "kind IN ('strategy','event','creative','experiment','cost','change','decision')",
            name="ck_intelligence_record_kind",
        ),
        Index("ix_intelligence_records_workspace_kind", "workspace_id", "kind", "updated_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    record_key: Mapped[str] = mapped_column(String(96), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class IntelligenceRevision(Base):
    """Append-only application audit; restoring context creates a new revision."""

    __tablename__ = "intelligence_revisions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["record_id", "workspace_id"],
            ["intelligence_records.id", "intelligence_records.workspace_id"],
            name="fk_intelligence_revision_workspace",
            ondelete="CASCADE",
        ),
        UniqueConstraint("record_id", "version", name="uq_intelligence_revision_version"),
        Index("ix_intelligence_revisions_workspace_time", "workspace_id", "created_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer, nullable=False)
    record_id: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    action: Mapped[str] = mapped_column(String(24), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(24), nullable=False)
    before_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    after_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
