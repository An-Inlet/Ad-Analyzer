"""Minimal protected commitments, independent of erasable candidate documents."""

from datetime import datetime

from sqlalchemy import (
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


class CandidateReviewLink(Base):
    __tablename__ = "optimization_candidate_reviews"
    __table_args__ = (
        UniqueConstraint("review_id", "workspace_id", name="uq_candidate_review_scope"),
        UniqueConstraint(
            "workspace_id", "candidate_digest", "review_digest", name="uq_candidate_review_decision"
        ),
        ForeignKeyConstraint(
            ["review_id", "workspace_id"],
            ["provider_execution_reviews.id", "provider_execution_reviews.workspace_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["candidate_result_id", "candidate_workspace_id"],
            ["optimization_candidate_results.id", "optimization_candidate_results.workspace_id"],
            ondelete="SET NULL",
        ),
        CheckConstraint(
            "(candidate_result_id IS NULL AND candidate_workspace_id IS NULL) OR "
            "(candidate_result_id IS NOT NULL AND candidate_workspace_id IS NOT NULL "
            "AND candidate_workspace_id = workspace_id)",
            name="ck_candidate_review_optional_scope",
        ),
        CheckConstraint(
            "environment IN ('contract_test','live')", name="ck_candidate_review_environment"
        ),
    )
    review_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    candidate_result_id: Mapped[str | None] = mapped_column(String(32))
    candidate_workspace_id: Mapped[int | None] = mapped_column(Integer)
    actor_id: Mapped[str] = mapped_column(ForeignKey("customer_users.id", ondelete="RESTRICT"))
    original_session_digest: Mapped[str] = mapped_column(String(64))
    environment: Mapped[str] = mapped_column(String(16))
    candidate_digest: Mapped[str] = mapped_column(String(64))
    input_digest: Mapped[str] = mapped_column(String(64))
    selection_digest: Mapped[str] = mapped_column(String(64))
    policy_digest: Mapped[str] = mapped_column(String(64))
    evidence_digest: Mapped[str] = mapped_column(String(64))
    source_digest: Mapped[str] = mapped_column(String(64))
    review_digest: Mapped[str] = mapped_column(String(64))
    plan_digest: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
