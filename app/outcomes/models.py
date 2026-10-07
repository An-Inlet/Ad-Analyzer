"""Source-derived assessments: publication deletion erases payload and digest."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class ActionOutcomeAssessment(Base):
    __tablename__ = "action_outcome_assessments"
    __table_args__ = (
        UniqueConstraint("id", "workspace_id", name="uq_outcome_assessment_owner"),
        UniqueConstraint("workspace_id", "input_digest", name="uq_outcome_assessment_input"),
        ForeignKeyConstraint(
            ["attempt_id", "workspace_id"],
            ["provider_execution_attempts.id", "provider_execution_attempts.workspace_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["receipt_id", "workspace_id"],
            ["provider_execution_receipts.id", "provider_execution_receipts.workspace_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["publication_id", "workspace_id"],
            [
                "commerce_measurement_publications.id",
                "commerce_measurement_publications.workspace_id",
            ],
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "generation > 0 AND privacy_epoch > 0 AND receipt_sequence > 0",
            name="ck_outcome_assessment_fences",
        ),
        CheckConstraint(
            "environment IN ('contract_test','live')", name="ck_outcome_assessment_environment"
        ),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    attempt_id: Mapped[str] = mapped_column(String(32))
    receipt_id: Mapped[str] = mapped_column(String(32))
    receipt_sequence: Mapped[int] = mapped_column(Integer)
    receipt_digest: Mapped[str] = mapped_column(String(64))
    projection_digest: Mapped[str] = mapped_column(String(64))
    publication_id: Mapped[str] = mapped_column(String(32))
    generation: Mapped[int] = mapped_column(Integer)
    privacy_epoch: Mapped[int] = mapped_column(Integer)
    environment: Mapped[str] = mapped_column(String(16))
    policy_id: Mapped[str] = mapped_column(String(64))
    policy_digest: Mapped[str] = mapped_column(String(64))
    input_digest: Mapped[str] = mapped_column(String(64))
    assessment_digest: Mapped[str] = mapped_column(String(64))
    assessment: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
