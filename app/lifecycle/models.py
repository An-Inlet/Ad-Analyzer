from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base
from app.publication import models as publication_models  # noqa: F401


class LifecycleRequest(Base):
    __tablename__ = "customer_lifecycle_requests"
    __table_args__ = (
        UniqueConstraint("id", "workspace_id", name="uq_lifecycle_request_scope"),
        UniqueConstraint(
            "workspace_id",
            "requested_by",
            "operation",
            "key_digest",
            name="uq_lifecycle_request_replay",
        ),
        CheckConstraint("operation IN ('export','close')", name="ck_lifecycle_operation"),
        CheckConstraint("revision > 0", name="ck_lifecycle_revision"),
        CheckConstraint("disposition_policy IS NULL", name="ck_lifecycle_policy_unset_v1"),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="RESTRICT"))
    requested_by: Mapped[str] = mapped_column(ForeignKey("customer_users.id", ondelete="RESTRICT"))
    operation: Mapped[str] = mapped_column(String(16))
    key_digest: Mapped[str] = mapped_column(String(64))
    request_digest: Mapped[str] = mapped_column(String(64))
    schema_version: Mapped[str] = mapped_column(String(40), default="inlet.lifecycle.request.v1")
    state: Mapped[str] = mapped_column(String(24), default="requested")
    revision: Mapped[int] = mapped_column(default=1)
    fence: Mapped[str] = mapped_column(String(32))
    disposition_policy: Mapped[str | None] = mapped_column(String(64))
    blockers: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class LifecycleStep(Base):
    __tablename__ = "customer_lifecycle_steps"
    __table_args__ = (
        ForeignKeyConstraint(
            ["request_id", "workspace_id"],
            ["customer_lifecycle_requests.id", "customer_lifecycle_requests.workspace_id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint("attempts >= 0 AND request_revision > 0", name="ck_lifecycle_step_attempt"),
    )
    request_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    step_key: Mapped[str] = mapped_column(String(48), primary_key=True)
    workspace_id: Mapped[int] = mapped_column()
    request_revision: Mapped[int] = mapped_column()
    fence: Mapped[str] = mapped_column(String(32))
    state: Mapped[str] = mapped_column(String(16), default="pending")
    attempts: Mapped[int] = mapped_column(default=0)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence_digest: Mapped[str | None] = mapped_column(String(64))
