"""Initial operational opportunity and erasable evidence ownership (0084)."""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class InitialRuleOpportunity(Base):
    __tablename__ = "initial_rule_opportunities"
    __table_args__ = (
        UniqueConstraint("id", "workspace_id", name="uq_initial_rule_opportunity_scope"),
        UniqueConstraint("semantic_key_digest", name="uq_initial_rule_semantic_key"),
        UniqueConstraint(
            "workspace_id",
            "environment",
            "ledger_id",
            "native_account_identity_digest",
            "budget_owner_identity_digest",
            name="uq_initial_rule_native_opportunity",
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
        CheckConstraint("environment IN ('contract_test','live')", name="ck_initial_rule_env"),
        CheckConstraint("pending_expires_at > created_at", name="ck_initial_rule_pending_expiry"),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    environment: Mapped[str] = mapped_column(String(16))
    ledger_id: Mapped[str] = mapped_column(String(32))
    native_account_identity_digest: Mapped[str] = mapped_column(String(64))
    budget_owner_identity_digest: Mapped[str] = mapped_column(String(64))
    semantic_key_digest: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    pending_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class InitialRuleAdmissionOrigin(Base):
    __tablename__ = "initial_rule_admission_origins"
    __table_args__ = (
        ForeignKeyConstraint(
            ["admission_id", "workspace_id"],
            ["provider_automatic_decisions.id", "provider_automatic_decisions.workspace_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["opportunity_id", "workspace_id"],
            ["initial_rule_opportunities.id", "initial_rule_opportunities.workspace_id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("opportunity_id", name="uq_initial_rule_consumed_once"),
    )
    admission_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    opportunity_id: Mapped[str] = mapped_column(String(32))


def evidence_fk(column: str, table: str) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        [column, "workspace_id", "account_id", "campaign_id"],
        [f"{table}.id", f"{table}.workspace_id", f"{table}.account_id", f"{table}.campaign_id"],
        ondelete="CASCADE",
    )


class InitialRuleCandidateDependency(Base):
    __tablename__ = "initial_rule_candidate_dependencies"
    __table_args__ = (
        UniqueConstraint(
            "candidate_job_id",
            "workspace_id",
            "account_id",
            "campaign_id",
            name="uq_initial_rule_dependency_scope",
        ),
        ForeignKeyConstraint(
            ["candidate_job_id", "workspace_id"],
            ["optimization_candidate_jobs.id", "optimization_candidate_jobs.workspace_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["opportunity_id", "workspace_id"],
            ["initial_rule_opportunities.id", "initial_rule_opportunities.workspace_id"],
            ondelete="CASCADE",
        ),
        evidence_fk("preview_id", "initial_plan_previews"),
        evidence_fk("calibration_id", "initial_calibration_runs"),
        evidence_fk("selected_observation_id", "initial_observations"),
    )
    candidate_job_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    account_id: Mapped[int] = mapped_column(Integer)
    campaign_id: Mapped[int] = mapped_column(Integer)
    opportunity_id: Mapped[str] = mapped_column(String(32), index=True)
    preview_id: Mapped[str] = mapped_column(String(32))
    calibration_id: Mapped[str] = mapped_column(String(32))
    selected_observation_id: Mapped[str] = mapped_column(String(32))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class InitialRuleCandidateObservation(Base):
    __tablename__ = "initial_rule_candidate_observations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["candidate_job_id", "workspace_id", "account_id", "campaign_id"],
            [
                "initial_rule_candidate_dependencies.candidate_job_id",
                "initial_rule_candidate_dependencies.workspace_id",
                "initial_rule_candidate_dependencies.account_id",
                "initial_rule_candidate_dependencies.campaign_id",
            ],
            ondelete="CASCADE",
        ),
        evidence_fk("observation_id", "initial_observations"),
    )
    candidate_job_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    observation_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    account_id: Mapped[int] = mapped_column(Integer)
    campaign_id: Mapped[int] = mapped_column(Integer)


from app.initial_planning.automatic_triggers import register  # noqa: E402

for _model in (
    InitialRuleOpportunity,
    InitialRuleAdmissionOrigin,
    InitialRuleCandidateDependency,
    InitialRuleCandidateObservation,
):
    register(Base.metadata.tables[_model.__tablename__])
