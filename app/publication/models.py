from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class PublicationPlanRecord(Base):
    __tablename__ = "publication_plans"
    __table_args__ = (
        UniqueConstraint("id", "workspace_id", name="uq_publication_plan_scope"),
        UniqueConstraint("workspace_id", "digest", name="uq_publication_plan_digest"),
        ForeignKeyConstraint(
            ["action_id", "workspace_id"], ["mandate_actions.id", "mandate_actions.workspace_id"]
        ),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="RESTRICT"))
    action_id: Mapped[str] = mapped_column(String(32))
    digest: Mapped[str] = mapped_column(String(64))
    document: Mapped[dict[str, Any]] = mapped_column(JSON)
    state: Mapped[str] = mapped_column(String(32), default="awaiting_approval")
    approved_by: Mapped[str | None] = mapped_column(String(32))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    activation_digest: Mapped[str | None] = mapped_column(String(64))
    activation_approved_by: Mapped[str | None] = mapped_column(String(32))
    request_key: Mapped[str | None] = mapped_column(String(128))


class PublicationStepRecord(Base):
    __tablename__ = "publication_steps"
    __table_args__ = (
        ForeignKeyConstraint(
            ["plan_id", "workspace_id"], ["publication_plans.id", "publication_plans.workspace_id"]
        ),
        UniqueConstraint("plan_id", "step_id", "workspace_id", name="uq_publication_step_scope"),
    )
    plan_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    step_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(24), default="pending")
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    fence: Mapped[str | None] = mapped_column(String(32))
    request: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    receipt: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class PublicationReceiptRecord(Base):
    __tablename__ = "publication_receipts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["plan_id", "step_id", "workspace_id"],
            [
                "publication_steps.plan_id",
                "publication_steps.step_id",
                "publication_steps.workspace_id",
            ],
        ),
        UniqueConstraint("plan_id", "step_id", "digest", name="uq_publication_receipt_digest"),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    plan_id: Mapped[str] = mapped_column(String(32))
    step_id: Mapped[str] = mapped_column(String(32))
    workspace_id: Mapped[int] = mapped_column(Integer)
    digest: Mapped[str] = mapped_column(String(64))
    request: Mapped[dict[str, Any]] = mapped_column(JSON)
    receipt: Mapped[dict[str, Any]] = mapped_column(JSON)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
