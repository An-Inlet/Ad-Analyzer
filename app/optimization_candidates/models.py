"""Erasable derived suggestions. These rows never reserve or authorize spending."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
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


class CandidateJob(Base):
    __tablename__ = "optimization_candidate_jobs"
    __table_args__ = (
        UniqueConstraint("id", "workspace_id", name="uq_candidate_job_owner"),
        UniqueConstraint("workspace_id", "input_digest", name="uq_candidate_job_input"),
        ForeignKeyConstraint(
            ["publication_id", "workspace_id"],
            [
                "commerce_measurement_publications.id",
                "commerce_measurement_publications.workspace_id",
            ],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["attempt_id", "workspace_id"],
            ["provider_execution_attempts.id", "provider_execution_attempts.workspace_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint("environment IN ('contract_test','live')", name="ck_candidate_environment"),
        CheckConstraint(
            "state IN ('pending','claimed','completed','blocked','canceled') AND attempts >= 0",
            name="ck_candidate_job_state",
        ),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    environment: Mapped[str] = mapped_column(String(16))
    publication_id: Mapped[str] = mapped_column(String(32))
    attempt_id: Mapped[str | None] = mapped_column(String(32))
    actor_id: Mapped[str] = mapped_column(ForeignKey("customer_users.id", ondelete="CASCADE"))
    auth_session_digest: Mapped[str] = mapped_column(
        ForeignKey("customer_sessions.digest", ondelete="CASCADE")
    )
    input_digest: Mapped[str] = mapped_column(String(64))
    work: Mapped[dict[str, Any]] = mapped_column(JSON)
    state: Mapped[str] = mapped_column(String(16))
    fence: Mapped[str | None] = mapped_column(String(32))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CandidateResult(Base):
    __tablename__ = "optimization_candidate_results"
    __table_args__ = (
        UniqueConstraint("id", "workspace_id", name="uq_candidate_result_owner"),
        UniqueConstraint("job_id", name="uq_candidate_result_job"),
        ForeignKeyConstraint(
            ["job_id", "workspace_id"],
            ["optimization_candidate_jobs.id", "optimization_candidate_jobs.workspace_id"],
            ondelete="CASCADE",
        ),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    job_id: Mapped[str] = mapped_column(String(32))
    input_digest: Mapped[str] = mapped_column(String(64))
    policy_digest: Mapped[str] = mapped_column(String(64))
    evidence_digest: Mapped[str] = mapped_column(String(64))
    decision_digest: Mapped[str] = mapped_column(String(64))
    decision: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
