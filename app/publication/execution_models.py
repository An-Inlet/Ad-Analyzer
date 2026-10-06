"""Durable provider consent, exposure, claims and immutable evidence.

These tables are deliberately separate from simulation mandates and actions. Closed
accounts retain unresolved financial/effect evidence; lifecycle deletion must classify
these as audit records rather than deleting or replaying outstanding attempts.
"""

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
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class ProviderPeriodLedger(Base):
    __tablename__ = "provider_period_ledgers"
    __table_args__ = (
        UniqueConstraint("id", "workspace_id", name="uq_provider_ledger_scope"),
        UniqueConstraint(
            "id", "workspace_id", "environment", name="uq_provider_ledger_environment"
        ),
        UniqueConstraint(
            "workspace_id", "environment", "starts_at", "ends_at", name="uq_provider_ledger_period"
        ),
        CheckConstraint("environment IN ('contract_test','live')", name="ck_provider_ledger_env"),
        CheckConstraint(
            "starts_at < ends_at AND spent_high_water_micros >= 0 AND action_count >= 0",
            name="ck_provider_ledger_bounds",
        ),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="RESTRICT"))
    environment: Mapped[str] = mapped_column(String(16))
    currency: Mapped[str] = mapped_column(String(3))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    spent_high_water_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    action_count: Mapped[int] = mapped_column(Integer, default=0)
    last_dispatch_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProviderExecutionMandate(Base):
    __tablename__ = "provider_execution_mandates"
    __table_args__ = (
        UniqueConstraint("id", "workspace_id", name="uq_provider_mandate_scope"),
        ForeignKeyConstraint(
            ["ledger_id", "workspace_id"],
            ["provider_period_ledgers.id", "provider_period_ledgers.workspace_id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "revision >= 1 AND state IN ('draft','active','paused','revoked')",
            name="ck_provider_mandate_state",
        ),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    ledger_id: Mapped[str] = mapped_column(String(32))
    revision: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(16))


class ProviderExecutionRevision(Base):
    __tablename__ = "provider_execution_revisions"
    __table_args__ = (
        UniqueConstraint(
            "mandate_id", "revision", "workspace_id", name="uq_provider_revision_scope"
        ),
        ForeignKeyConstraint(
            ["mandate_id", "workspace_id"],
            ["provider_execution_mandates.id", "provider_execution_mandates.workspace_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["goal_id", "workspace_id"],
            ["customer_goals.id", "customer_goals.workspace_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["goal_id", "goal_revision"],
            ["customer_goal_revisions.goal_id", "customer_goal_revisions.revision"],
            ondelete="RESTRICT",
        ),
    )
    mandate_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    goal_id: Mapped[str] = mapped_column(String(32))
    goal_revision: Mapped[int] = mapped_column(Integer)
    policy: Mapped[dict[str, Any]] = mapped_column(JSON)
    digest: Mapped[str] = mapped_column(String(64))
    actor: Mapped[str] = mapped_column(ForeignKey("customer_users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProviderExecutionConsent(Base):
    __tablename__ = "provider_execution_consents"
    __table_args__ = (
        UniqueConstraint("id", "workspace_id", name="uq_provider_consent_scope"),
        UniqueConstraint("mandate_id", "revision", name="uq_provider_consent_revision"),
        ForeignKeyConstraint(
            ["mandate_id", "revision", "workspace_id"],
            [
                "provider_execution_revisions.mandate_id",
                "provider_execution_revisions.revision",
                "provider_execution_revisions.workspace_id",
            ],
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    mandate_id: Mapped[str] = mapped_column(String(32))
    revision: Mapped[int] = mapped_column(Integer)
    policy_digest: Mapped[str] = mapped_column(String(64))
    actor: Mapped[str] = mapped_column(ForeignKey("customer_users.id", ondelete="RESTRICT"))
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProviderExecutionReview(Base):
    __mapper_args__ = {"eager_defaults": False}
    candidate_provenance_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false"), deferred=True
    )
    __tablename__ = "provider_execution_reviews"
    __table_args__ = (
        UniqueConstraint("id", "workspace_id", name="uq_provider_execution_review_scope"),
        UniqueConstraint("workspace_id", "digest", name="uq_provider_execution_review_digest"),
        ForeignKeyConstraint(
            ["consent_id", "workspace_id"],
            ["provider_execution_consents.id", "provider_execution_consents.workspace_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["account_id", "workspace_id", "integration_id"],
            [
                "advertising_accounts.id",
                "advertising_accounts.workspace_id",
                "advertising_accounts.connection_id",
            ],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["source_draft_id", "source_revision", "workspace_id"],
            [
                "customer_campaign_revisions.draft_id",
                "customer_campaign_revisions.revision",
                "customer_campaign_revisions.workspace_id",
            ],
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    consent_id: Mapped[str] = mapped_column(String(32))
    account_id: Mapped[int] = mapped_column(Integer)
    integration_id: Mapped[int] = mapped_column(Integer)
    source_draft_id: Mapped[str | None] = mapped_column(String(32))
    source_revision: Mapped[int | None] = mapped_column(Integer)
    document: Mapped[dict[str, Any]] = mapped_column(JSON)
    digest: Mapped[str] = mapped_column(String(64))
    plan_digest: Mapped[str] = mapped_column(String(64))
    actor: Mapped[str] = mapped_column(ForeignKey("customer_users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProviderExecutionApproval(Base):
    __tablename__ = "provider_execution_approvals"
    __table_args__ = (
        ForeignKeyConstraint(
            ["review_id", "workspace_id"],
            ["provider_execution_reviews.id", "provider_execution_reviews.workspace_id"],
            ondelete="RESTRICT",
        ),
    )
    review_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    review_digest: Mapped[str] = mapped_column(String(64))
    plan_digest: Mapped[str] = mapped_column(String(64))
    actor: Mapped[str] = mapped_column(ForeignKey("customer_users.id", ondelete="RESTRICT"))
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProviderExposureReservation(Base):
    __tablename__ = "provider_exposure_reservations"
    __table_args__ = (
        UniqueConstraint("id", "workspace_id", name="uq_provider_reservation_scope"),
        ForeignKeyConstraint(
            ["ledger_id", "workspace_id", "environment"],
            [
                "provider_period_ledgers.id",
                "provider_period_ledgers.workspace_id",
                "provider_period_ledgers.environment",
            ],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "amount_micros >= 0 AND state IN ('held','settled','superseded')",
            name="ck_provider_reservation_bounds",
        ),
        Index(
            "uq_provider_held_owner",
            "workspace_id",
            "environment",
            "budget_owner_key",
            unique=True,
            postgresql_where=text("state = 'held'"),
            sqlite_where=text("state = 'held'"),
        ),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    ledger_id: Mapped[str] = mapped_column(String(32))
    environment: Mapped[str] = mapped_column(String(16))
    budget_owner_key: Mapped[str] = mapped_column(String(256))
    amount_micros: Mapped[int] = mapped_column(BigInteger)
    state: Mapped[str] = mapped_column(String(16))
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON)
    settled_evidence: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class ProviderExecutionRun(Base):
    __tablename__ = "provider_execution_runs"
    __table_args__ = (
        UniqueConstraint("id", "workspace_id", name="uq_provider_run_scope"),
        UniqueConstraint("review_id", name="uq_provider_run_review"),
        ForeignKeyConstraint(
            ["review_id", "workspace_id"],
            ["provider_execution_reviews.id", "provider_execution_reviews.workspace_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["reservation_id", "workspace_id"],
            ["provider_exposure_reservations.id", "provider_exposure_reservations.workspace_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["parent_run_id", "workspace_id"],
            ["provider_execution_runs.id", "provider_execution_runs.workspace_id"],
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    review_id: Mapped[str] = mapped_column(String(32))
    reservation_id: Mapped[str | None] = mapped_column(String(32))
    parent_run_id: Mapped[str | None] = mapped_column(String(32))
    state: Mapped[str] = mapped_column(String(24))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProviderExecutionStep(Base):
    __tablename__ = "provider_execution_steps"
    __table_args__ = (
        UniqueConstraint("run_id", "step_id", "workspace_id", name="uq_provider_step_scope"),
        ForeignKeyConstraint(
            ["run_id", "workspace_id"],
            ["provider_execution_runs.id", "provider_execution_runs.workspace_id"],
            ondelete="RESTRICT",
        ),
    )
    run_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    step_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    ordinal: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(24))


class ProviderExecutionAttempt(Base):
    __tablename__ = "provider_execution_attempts"
    __table_args__ = (
        UniqueConstraint("id", "workspace_id", name="uq_provider_attempt_scope"),
        UniqueConstraint("run_id", "step_id", name="uq_provider_original_attempt"),
        UniqueConstraint("fence", name="uq_provider_attempt_fence"),
        ForeignKeyConstraint(
            ["run_id", "step_id", "workspace_id"],
            [
                "provider_execution_steps.run_id",
                "provider_execution_steps.step_id",
                "provider_execution_steps.workspace_id",
            ],
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    run_id: Mapped[str] = mapped_column(String(32))
    step_id: Mapped[str] = mapped_column(String(32))
    fence: Mapped[str] = mapped_column(String(32))
    request: Mapped[dict[str, Any]] = mapped_column(JSON)
    request_digest: Mapped[str] = mapped_column(String(64))
    dispatched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProviderExecutionResponse(Base):
    __tablename__ = "provider_execution_responses"
    __table_args__ = (
        ForeignKeyConstraint(
            ["attempt_id", "workspace_id"],
            ["provider_execution_attempts.id", "provider_execution_attempts.workspace_id"],
            ondelete="RESTRICT",
        ),
    )
    attempt_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    response: Mapped[dict[str, Any]] = mapped_column(JSON)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProviderExecutionReceipt(Base):
    __tablename__ = "provider_execution_receipts"
    __table_args__ = (
        UniqueConstraint("id", "workspace_id", name="uq_provider_receipt_scope"),
        UniqueConstraint("attempt_id", "sequence", name="uq_provider_receipt_sequence"),
        UniqueConstraint("attempt_id", "digest", name="uq_provider_receipt_dedup"),
        ForeignKeyConstraint(
            ["attempt_id", "workspace_id"],
            ["provider_execution_attempts.id", "provider_execution_attempts.workspace_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["supersedes_id", "workspace_id"],
            ["provider_execution_receipts.id", "provider_execution_receipts.workspace_id"],
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    attempt_id: Mapped[str] = mapped_column(String(32))
    sequence: Mapped[int] = mapped_column(Integer)
    supersedes_id: Mapped[str | None] = mapped_column(String(32))
    digest: Mapped[str] = mapped_column(String(64))
    receipt: Mapped[dict[str, Any]] = mapped_column(JSON)
    projection: Mapped[dict[str, Any]] = mapped_column(JSON)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProviderReservationReplacement(Base):
    """Immutable transfer audit; neither a refund nor terminal settlement."""

    __tablename__ = "provider_reservation_replacements"
    __table_args__ = (
        UniqueConstraint("id", "workspace_id", name="uq_provider_replacement_scope"),
        UniqueConstraint("predecessor_id", name="uq_provider_replacement_predecessor"),
        UniqueConstraint("successor_id", name="uq_provider_replacement_successor"),
        ForeignKeyConstraint(
            ["predecessor_id", "workspace_id"],
            ["provider_exposure_reservations.id", "provider_exposure_reservations.workspace_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["successor_id", "workspace_id"],
            ["provider_exposure_reservations.id", "provider_exposure_reservations.workspace_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["successor_run_id", "workspace_id"],
            ["provider_execution_runs.id", "provider_execution_runs.workspace_id"],
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
        CheckConstraint(
            "predecessor_id <> successor_id AND old_amount_micros >= 0 AND new_amount_micros >= 0",
            name="ck_provider_replacement_bounds",
        ),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    ledger_id: Mapped[str] = mapped_column(String(32))
    environment: Mapped[str] = mapped_column(String(16))
    budget_owner_key: Mapped[str] = mapped_column(String(256))
    predecessor_id: Mapped[str] = mapped_column(String(32))
    successor_id: Mapped[str] = mapped_column(String(32))
    successor_run_id: Mapped[str] = mapped_column(String(32))
    review_id: Mapped[str] = mapped_column(String(32))
    old_amount_micros: Mapped[int] = mapped_column(BigInteger)
    new_amount_micros: Mapped[int] = mapped_column(BigInteger)
    document: Mapped[dict[str, Any]] = mapped_column(JSON)
    digest: Mapped[str] = mapped_column(String(64))
    actor: Mapped[str] = mapped_column(ForeignKey("customer_users.id", ondelete="RESTRICT"))
    replaced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
