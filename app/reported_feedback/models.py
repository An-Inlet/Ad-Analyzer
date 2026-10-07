"""Erasable owned reported values; protected provider history is referenced only."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class Owned:
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    account_id: Mapped[int] = mapped_column(Integer)
    campaign_id: Mapped[int] = mapped_column(Integer)
    environment: Mapped[str] = mapped_column(String(16))
    document: Mapped[dict[str, Any]] = mapped_column(JSON)
    document_digest: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


def ownership(name: str) -> tuple[Any, ...]:
    return (
        UniqueConstraint("id", "workspace_id", "account_id", "campaign_id", name=f"uq_rf_{name}"),
        ForeignKeyConstraint(
            ["account_id", "workspace_id"],
            ["advertising_accounts.id", "advertising_accounts.workspace_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["campaign_id", "account_id"],
            ["campaigns.id", "campaigns.account_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint("environment IN ('contract_test','live')", name=f"ck_rf_{name}_env"),
    )


def owned_parent(field: str, table: str) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        [field, "workspace_id", "account_id", "campaign_id"],
        [f"{table}.id", f"{table}.workspace_id", f"{table}.account_id", f"{table}.campaign_id"],
        ondelete="CASCADE",
    )


class ReportedFeedbackJob(Owned, Base):
    __tablename__ = "reported_feedback_jobs"
    __table_args__ = (
        *ownership("job"),
        ForeignKeyConstraint(
            ["original_attempt_id", "workspace_id"],
            ["provider_execution_attempts.id", "provider_execution_attempts.workspace_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("workspace_id", "input_digest", name="uq_rf_job_input"),
        CheckConstraint(
            "state IN ('pending','acquiring','waiting','ready','blocked','expired')",
            name="ck_rf_job_state",
        ),
        CheckConstraint(
            "completed_observations BETWEEN 0 AND 16 AND source_generation > 0",
            name="ck_rf_job_progress",
        ),
    )
    original_attempt_id: Mapped[str] = mapped_column(String(32), index=True)
    original_actor_id: Mapped[str] = mapped_column(String(32))
    original_session_digest: Mapped[str] = mapped_column(String(64))
    source_connection_id: Mapped[int] = mapped_column(Integer)
    source_generation: Mapped[int] = mapped_column(Integer)
    policy_family: Mapped[str] = mapped_column(String(32))
    policy_digest: Mapped[str] = mapped_column(String(64))
    input_digest: Mapped[str] = mapped_column(String(64))
    opportunity_digest: Mapped[str] = mapped_column(String(64), index=True)
    state: Mapped[str] = mapped_column(String(16))
    completed_observations: Mapped[int] = mapped_column(Integer)
    next_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    native_run_id: Mapped[str | None] = mapped_column(String(32), unique=True)
    acquisition_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    selected_start: Mapped[date | None] = mapped_column(Date)
    selected_end: Mapped[date | None] = mapped_column(Date)
    rolling_covered_from: Mapped[date | None] = mapped_column(Date)
    rolling_covered_through: Mapped[date | None] = mapped_column(Date)
    rolling_last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))


class ReportedWindowCapsule(Owned, Base):
    __tablename__ = "reported_window_capsules"
    __table_args__ = (
        *ownership("capsule"),
        owned_parent("job_id", "reported_feedback_jobs"),
        ForeignKeyConstraint(
            ["completion_id", "account_id", "workspace_id"],
            [
                "campaign_performance_completions.id",
                "campaign_performance_completions.account_id",
                "campaign_performance_completions.workspace_id",
            ],
            ondelete="CASCADE",
        ),
        UniqueConstraint("completion_id", "campaign_id", "environment", name="uq_rf_capture"),
    )
    job_id: Mapped[str] = mapped_column(String(32), index=True)
    completion_id: Mapped[str] = mapped_column(String(32))
    acquisition_run_id: Mapped[str] = mapped_column(String(32))
    source_generation: Mapped[int] = mapped_column(Integer)
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date] = mapped_column(Date)
    acquisition_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    acquisition_completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ReportedActionComparison(Owned, Base):
    __tablename__ = "reported_action_comparisons"
    __table_args__ = (
        *ownership("comparison"),
        owned_parent("job_id", "reported_feedback_jobs"),
        ForeignKeyConstraint(
            ["receipt_id", "workspace_id"],
            ["provider_execution_receipts.id", "provider_execution_receipts.workspace_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("workspace_id", "input_digest", name="uq_rf_comparison_input"),
    )
    job_id: Mapped[str] = mapped_column(String(32), index=True)
    original_attempt_id: Mapped[str] = mapped_column(String(32), index=True)
    receipt_id: Mapped[str] = mapped_column(String(32))
    receipt_sequence: Mapped[int] = mapped_column(Integer)
    policy_family: Mapped[str] = mapped_column(String(32))
    input_digest: Mapped[str] = mapped_column(String(64))
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ReportedComparisonDependency(Base):
    __tablename__ = "reported_comparison_dependencies"
    __table_args__ = (
        owned_parent("comparison_id", "reported_action_comparisons"),
        owned_parent("capsule_id", "reported_window_capsules"),
    )
    comparison_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    capsule_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    account_id: Mapped[int] = mapped_column(Integer)
    campaign_id: Mapped[int] = mapped_column(Integer)


class ReportedFeedbackSlot(Owned, Base):
    __tablename__ = "reported_feedback_slots"
    __table_args__ = (
        *ownership("slot"),
        owned_parent("comparison_id", "reported_action_comparisons"),
        owned_parent("baseline_preview_id", "initial_plan_previews"),
        UniqueConstraint(
            "workspace_id",
            "environment",
            "original_attempt_id",
            "policy_family",
            "cohort_digest",
            "revision",
            name="uq_rf_original_revision",
        ),
        UniqueConstraint(
            "id",
            "workspace_id",
            "account_id",
            "campaign_id",
            "environment",
            "original_attempt_id",
            "policy_family",
            "cohort_digest",
            "opportunity_digest",
            "revision",
            name="uq_rf_slot_pointer",
        ),
        CheckConstraint("revision > 0", name="ck_rf_slot_revision"),
    )
    comparison_id: Mapped[str] = mapped_column(String(32), index=True)
    baseline_preview_id: Mapped[str] = mapped_column(String(32))
    original_attempt_id: Mapped[str] = mapped_column(String(32))
    original_actor_id: Mapped[str] = mapped_column(String(32))
    original_session_digest: Mapped[str] = mapped_column(String(64))
    policy_family: Mapped[str] = mapped_column(String(32))
    cohort_digest: Mapped[str] = mapped_column(String(64))
    opportunity_digest: Mapped[str] = mapped_column(String(64))
    revision: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ReportedFeedbackCurrent(Base):
    __tablename__ = "reported_feedback_current"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "environment",
            "original_attempt_id",
            "policy_family",
            "cohort_digest",
            name="uq_rf_current_group",
        ),
        ForeignKeyConstraint(
            [
                "slot_id",
                "workspace_id",
                "account_id",
                "campaign_id",
                "environment",
                "original_attempt_id",
                "policy_family",
                "cohort_digest",
                "opportunity_digest",
                "revision",
            ],
            [
                f"reported_feedback_slots.{field}"
                for field in (
                    "id",
                    "workspace_id",
                    "account_id",
                    "campaign_id",
                    "environment",
                    "original_attempt_id",
                    "policy_family",
                    "cohort_digest",
                    "opportunity_digest",
                    "revision",
                )
            ],
            ondelete="CASCADE",
            name="fk_rf_current_slot",
        ),
        CheckConstraint("revision > 0", name="ck_rf_current_revision"),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    account_id: Mapped[int] = mapped_column(Integer)
    campaign_id: Mapped[int] = mapped_column(Integer)
    environment: Mapped[str] = mapped_column(String(16))
    original_attempt_id: Mapped[str] = mapped_column(String(32))
    policy_family: Mapped[str] = mapped_column(String(32))
    cohort_digest: Mapped[str] = mapped_column(String(64))
    opportunity_digest: Mapped[str] = mapped_column(String(64))
    slot_id: Mapped[str] = mapped_column(String(32))
    revision: Mapped[int] = mapped_column(Integer)


from app.reported_feedback.triggers import current_statements, register  # noqa: E402

register(Base.metadata)

from sqlalchemy import DDL, event  # noqa: E402

for _dialect in ("sqlite", "postgresql"):
    for _statement in current_statements(_dialect):
        event.listen(
            ReportedFeedbackCurrent.__table__,
            "after_create",
            DDL(_statement).execute_if(dialect=_dialect),  # type: ignore[no-untyped-call]
        )
