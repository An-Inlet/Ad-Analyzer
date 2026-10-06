"""Protected original-session intent and semantic admission audit, never measurement data."""

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


class SessionAutomationRun(Base):
    __tablename__ = "session_automation_runs"
    __table_args__ = (
        UniqueConstraint("id", "workspace_id", name="uq_session_automation_scope"),
        ForeignKeyConstraint(
            ["mandate_id", "workspace_id"],
            ["provider_execution_mandates.id", "provider_execution_mandates.workspace_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["mandate_id", "mandate_revision", "workspace_id"],
            [
                "provider_execution_revisions.mandate_id",
                "provider_execution_revisions.revision",
                "provider_execution_revisions.workspace_id",
            ],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["consent_id", "workspace_id"],
            ["provider_execution_consents.id", "provider_execution_consents.workspace_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["ledger_id", "workspace_id", "environment"],
            [
                "provider_period_ledgers.id",
                "provider_period_ledgers.workspace_id",
                "provider_period_ledgers.environment",
            ],
            ondelete="RESTRICT",
        ),
        CheckConstraint("environment IN ('contract_test','live')", name="ck_auto_environment"),
        CheckConstraint("mandate_revision > 0 AND policy_revision > 0", name="ck_auto_revisions"),
        CheckConstraint("expires_at > created_at", name="ck_auto_lifetime"),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    actor_id: Mapped[str] = mapped_column(ForeignKey("customer_users.id", ondelete="RESTRICT"))
    original_session_digest: Mapped[str] = mapped_column(String(64))
    environment: Mapped[str] = mapped_column(String(16))
    mandate_id: Mapped[str] = mapped_column(String(32))
    mandate_revision: Mapped[int] = mapped_column(Integer)
    consent_id: Mapped[str] = mapped_column(String(32))
    mandate_digest: Mapped[str] = mapped_column(String(64))
    ledger_id: Mapped[str] = mapped_column(String(32))
    policy_family: Mapped[str] = mapped_column(String(32))
    policy_id: Mapped[str] = mapped_column(String(32))
    policy_revision: Mapped[int] = mapped_column(Integer)
    policy_digest: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    next_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stopped_by: Mapped[str | None] = mapped_column(
        ForeignKey("customer_users.id", ondelete="RESTRICT")
    )
    state: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str] = mapped_column(String(48))


class AutomaticDecisionAdmission(Base):
    __tablename__ = "provider_automatic_decisions"
    __table_args__ = (
        UniqueConstraint("id", "workspace_id", name="uq_automatic_decision_scope"),
        UniqueConstraint("review_id", name="uq_automatic_decision_review"),
        UniqueConstraint(
            "workspace_id",
            "environment",
            "ledger_id",
            "account_identity_digest",
            "budget_owner_key",
            "policy_family",
            "epoch_digest",
            name="uq_automatic_semantic_epoch",
        ),
        ForeignKeyConstraint(
            ["session_run_id", "workspace_id"],
            ["session_automation_runs.id", "session_automation_runs.workspace_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["review_id", "workspace_id"],
            ["provider_execution_reviews.id", "provider_execution_reviews.workspace_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["ledger_id", "workspace_id", "environment"],
            [
                "provider_period_ledgers.id",
                "provider_period_ledgers.workspace_id",
                "provider_period_ledgers.environment",
            ],
            ondelete="RESTRICT",
        ),
        CheckConstraint("environment IN ('contract_test','live')", name="ck_auto_decision_env"),
        CheckConstraint("expires_at > admitted_at", name="ck_auto_decision_lifetime"),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    session_run_id: Mapped[str] = mapped_column(String(32))
    review_id: Mapped[str] = mapped_column(String(32))
    environment: Mapped[str] = mapped_column(String(16))
    ledger_id: Mapped[str] = mapped_column(String(32))
    account_identity_digest: Mapped[str] = mapped_column(String(64))
    budget_owner_key: Mapped[str] = mapped_column(String(256))
    policy_family: Mapped[str] = mapped_column(String(32))
    policy_digest: Mapped[str] = mapped_column(String(64))
    epoch_digest: Mapped[str] = mapped_column(String(64))
    producer_family: Mapped[str] = mapped_column(String(32))
    review_digest: Mapped[str] = mapped_column(String(64))
    plan_digest: Mapped[str] = mapped_column(String(64))
    candidate_digest: Mapped[str] = mapped_column(String(64))
    evidence_digest: Mapped[str] = mapped_column(String(64))
    actor_id: Mapped[str] = mapped_column(ForeignKey("customer_users.id", ondelete="RESTRICT"))
    admitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
