from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
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


class Goal(Base):
    __tablename__ = "customer_goals"
    __table_args__ = (UniqueConstraint("id", "workspace_id", name="uq_goal_owner"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    revision: Mapped[int] = mapped_column(Integer)
    confirmed_preview_id: Mapped[str | None] = mapped_column(String(32))


class GoalRevision(Base):
    __tablename__ = "customer_goal_revisions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["goal_id", "workspace_id"],
            ["customer_goals.id", "customer_goals.workspace_id"],
            ondelete="CASCADE",
        ),
    )
    goal_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    definition: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    editor_id: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_by: Mapped[str | None] = mapped_column(String(32))


class GoalPreview(Base):
    __tablename__ = "customer_goal_previews"
    __table_args__ = (
        ForeignKeyConstraint(
            ["goal_id", "revision"],
            ["customer_goal_revisions.goal_id", "customer_goal_revisions.revision"],
            ondelete="CASCADE",
        ),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    goal_id: Mapped[str] = mapped_column(String(32))
    revision: Mapped[int] = mapped_column(Integer)
    snapshot_id: Mapped[str | None] = mapped_column(
        ForeignKey("commerce_snapshots.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class GoalConfirmation(Base):
    __tablename__ = "customer_goal_confirmations"
    goal_id: Mapped[str] = mapped_column(
        ForeignKey("customer_goals.id", ondelete="CASCADE"), primary_key=True
    )
    request_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer)
    preview_id: Mapped[str] = mapped_column(String(32))


class UsagePolicy(Base):
    __tablename__ = "goal_usage_policies"
    __table_args__ = (
        CheckConstraint("call_limit >= 0 AND version >= 1", name="ck_goal_usage_limits"),
        CheckConstraint("cost_limit_micros = 0", name="ck_goal_usage_no_spend"),
    )
    scope: Mapped[str] = mapped_column(String(64), primary_key=True)
    call_limit: Mapped[int] = mapped_column(Integer)
    cost_limit_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)


class GoalUsage(Base):
    __tablename__ = "goal_interpretation_usage"
    __table_args__ = (
        ForeignKeyConstraint(
            ["goal_id", "workspace_id"],
            ["customer_goals.id", "customer_goals.workspace_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "reserved_micros = 0 AND charged_micros = 0", name="ck_goal_interpretation_no_spend"
        ),
    )
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    request_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    goal_id: Mapped[str] = mapped_column(String(32))
    user_id: Mapped[str] = mapped_column(String(32))
    revision: Mapped[int] = mapped_column(Integer)
    fingerprint: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String(24))
    reserved_micros: Mapped[int] = mapped_column(BigInteger)
    charged_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    policy_version: Mapped[int] = mapped_column(Integer)
