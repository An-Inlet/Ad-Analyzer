"""Every numeric derived record cascades from a workspace-owned v3 assessment."""

from datetime import datetime
from typing import Any, cast

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Table,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class V3Assessment(Base):
    __tablename__ = "outcome_assessments_v3"
    __table_args__ = (
        UniqueConstraint("id", "workspace_id", name="uq_v3_owner"),
        Index("ix_v3_workspace_source", "workspace_id", "store_id"),
        Index("ix_v3_workspace_attempt", "workspace_id", "attempt_id"),
        UniqueConstraint(
            "id", "workspace_id", "environment", "attempt_id", name="uq_v3_feedback_binding"
        ),
        UniqueConstraint("workspace_id", "input_digest", name="uq_v3_input"),
        ForeignKeyConstraint(
            ["store_id", "workspace_id"],
            ["commerce_stores.id", "commerce_stores.workspace_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["attempt_id", "workspace_id"],
            ["provider_execution_attempts.id", "provider_execution_attempts.workspace_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["receipt_id", "workspace_id"],
            ["provider_execution_receipts.id", "provider_execution_receipts.workspace_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "environment IN ('contract_test','live') AND generation > 0 "
            "AND privacy_epoch > 0 AND receipt_sequence > 0",
            name="ck_v3_fences",
        ),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    store_id: Mapped[str] = mapped_column(String(32))
    environment: Mapped[str] = mapped_column(String(16))
    attempt_id: Mapped[str] = mapped_column(String(32))
    receipt_id: Mapped[str] = mapped_column(String(32))
    receipt_sequence: Mapped[int] = mapped_column(Integer)
    generation: Mapped[int] = mapped_column(Integer)
    privacy_epoch: Mapped[int] = mapped_column(Integer)
    input_digest: Mapped[str] = mapped_column(String(64))
    document_digest: Mapped[str] = mapped_column(String(64))
    document: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class V3EvidenceDependency(Base):
    __tablename__ = "outcome_assessment_v3_evidence"
    __table_args__ = (
        ForeignKeyConstraint(
            ["assessment_id", "workspace_id"],
            ["outcome_assessments_v3.id", "outcome_assessments_v3.workspace_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["publication_id", "workspace_id"],
            [
                "commerce_measurement_publications.id",
                "commerce_measurement_publications.workspace_id",
            ],
            ondelete="CASCADE",
        ),
        UniqueConstraint("assessment_id", "publication_id", name="uq_v3_dependency_publication"),
        CheckConstraint("ordinal >= 0 AND ordinal <= 32", name="ck_v3_dependency_bound"),
    )
    assessment_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    ordinal: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    publication_id: Mapped[str] = mapped_column(String(32), index=True)
    manifest_digest: Mapped[str] = mapped_column(String(64))
    completion_digest: Mapped[str] = mapped_column(String(64))


class FeedbackRecord(Base):
    __tablename__ = "outcome_feedback_records"
    __table_args__ = (
        UniqueConstraint("id", "workspace_id", name="uq_feedback_owner"),
        UniqueConstraint(
            "id",
            "workspace_id",
            "environment",
            "attempt_id",
            "policy_family",
            "scope_digest",
            name="uq_feedback_slot_binding",
        ),
        UniqueConstraint(
            "workspace_id",
            "environment",
            "assessment_digest",
            "policy_digest",
            "scope_digest",
            name="uq_feedback_input",
        ),
        ForeignKeyConstraint(
            ["assessment_id", "workspace_id", "environment", "attempt_id"],
            [
                "outcome_assessments_v3.id",
                "outcome_assessments_v3.workspace_id",
                "outcome_assessments_v3.environment",
                "outcome_assessments_v3.attempt_id",
            ],
            ondelete="CASCADE",
        ),
        CheckConstraint("state IN ('eligible','superseded')", name="ck_feedback_state"),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    environment: Mapped[str] = mapped_column(String(16))
    attempt_id: Mapped[str] = mapped_column(String(32))
    assessment_id: Mapped[str] = mapped_column(String(32))
    assessment_digest: Mapped[str] = mapped_column(String(64))
    policy_family: Mapped[str] = mapped_column(String(80))
    policy_digest: Mapped[str] = mapped_column(String(64))
    scope_digest: Mapped[str] = mapped_column(String(64))
    document_digest: Mapped[str] = mapped_column(String(64))
    document: Mapped[dict[str, Any]] = mapped_column(JSON)
    state: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ContributionSlot(Base):
    __tablename__ = "outcome_contribution_slots"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "environment",
            "attempt_id",
            "policy_family",
            "scope_digest",
            name="uq_contribution_slot",
        ),
        ForeignKeyConstraint(
            [
                "feedback_id",
                "workspace_id",
                "environment",
                "attempt_id",
                "policy_family",
                "scope_digest",
            ],
            [
                "outcome_feedback_records.id",
                "outcome_feedback_records.workspace_id",
                "outcome_feedback_records.environment",
                "outcome_feedback_records.attempt_id",
                "outcome_feedback_records.policy_family",
                "outcome_feedback_records.scope_digest",
            ],
            ondelete="CASCADE",
        ),
        CheckConstraint("revision > 0", name="ck_contribution_revision"),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    environment: Mapped[str] = mapped_column(String(16))
    attempt_id: Mapped[str] = mapped_column(String(32))
    policy_family: Mapped[str] = mapped_column(String(80))
    scope_digest: Mapped[str] = mapped_column(String(64))
    feedback_id: Mapped[str] = mapped_column(String(32))
    revision: Mapped[int] = mapped_column(Integer)


# Metadata-created disposable databases must enforce the same erasure invariant.
from app.outcome_feedback.triggers import register_triggers  # noqa: E402

register_triggers(
    cast(Table, V3Assessment.__table__),
    cast(Table, V3EvidenceDependency.__table__),
    cast(Table, FeedbackRecord.__table__),
    cast(Table, ContributionSlot.__table__),
)
