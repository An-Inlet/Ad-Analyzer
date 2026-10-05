from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class Mandate(Base):
    __tablename__ = "spending_mandates"
    __table_args__ = (
        UniqueConstraint("id", "workspace_id", name="uq_mandate_owner"),
        CheckConstraint(
            "observed_micros >= 0 AND reserved_micros >= 0 "
            "AND changes_used >= 0 AND actions_used >= 0",
            name="ck_mandate_counters",
        ),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    revision: Mapped[int] = mapped_column(Integer)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String(24), default="draft")
    paused: Mapped[bool] = mapped_column(Boolean, default=True)
    opening_micros: Mapped[int | None] = mapped_column(BigInteger)
    observed_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    reserved_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    changes_used: Mapped[int] = mapped_column(BigInteger, default=0)
    actions_used: Mapped[int] = mapped_column(Integer, default=0)
    last_action_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MandateRevision(Base):
    __tablename__ = "spending_mandate_revisions"
    mandate_id: Mapped[str] = mapped_column(
        ForeignKey("spending_mandates.id", ondelete="CASCADE"), primary_key=True
    )
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    definition: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_by: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[str | None] = mapped_column(String(32))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MandateAction(Base):
    __tablename__ = "mandate_actions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["mandate_id", "workspace_id"],
            ["spending_mandates.id", "spending_mandates.workspace_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("mandate_id", "digest", name="uq_mandate_action_draft"),
        UniqueConstraint("mandate_id", "request_key", name="uq_mandate_claim_request"),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    mandate_id: Mapped[str] = mapped_column(String(32))
    workspace_id: Mapped[int] = mapped_column(Integer)
    draft: Mapped[dict[str, Any]] = mapped_column(JSON)
    digest: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(32), default="draft")
    reviewed_by: Mapped[str | None] = mapped_column(String(32))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    request_key: Mapped[str | None] = mapped_column(String(128))
    fence: Mapped[str | None] = mapped_column(String(32))
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dispatch_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    settled_micros: Mapped[int | None] = mapped_column(BigInteger)


class MandateAudit(Base):
    __tablename__ = "mandate_audits"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    mandate_id: Mapped[str] = mapped_column(ForeignKey("spending_mandates.id", ondelete="CASCADE"))
    action_id: Mapped[str | None] = mapped_column(String(32))
    event: Mapped[str] = mapped_column(String(48))
    actor: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
