from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class MediaObject(Base):
    __tablename__ = "customer_media_objects"
    __table_args__ = (
        UniqueConstraint("workspace_id", "sha256", name="uq_media_workspace_content"),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    sha256: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(BigInteger)
    mime: Mapped[str] = mapped_column(String(32))
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    created_by: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CampaignDraft(Base):
    __tablename__ = "customer_campaign_drafts"
    __table_args__ = (UniqueConstraint("id", "workspace_id", name="uq_campaign_draft_scope"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    revision: Mapped[int] = mapped_column(Integer)


class CampaignRevision(Base):
    __tablename__ = "customer_campaign_revisions"
    __table_args__ = (
        UniqueConstraint("draft_id", "revision", "workspace_id", name="uq_campaign_revision_scope"),
        ForeignKeyConstraint(
            ["draft_id", "workspace_id"],
            ["customer_campaign_drafts.id", "customer_campaign_drafts.workspace_id"],
            ondelete="CASCADE",
        ),
    )
    draft_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    artifact: Mapped[dict[str, Any]] = mapped_column(JSON)
    digest: Mapped[str] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[str | None] = mapped_column(String(32))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
