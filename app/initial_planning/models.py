"""Derived aggregate planning records; no financial authority or protected history."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKeyConstraint, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class OwnedColumns:
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    account_id: Mapped[int] = mapped_column(Integer)
    campaign_id: Mapped[int] = mapped_column(Integer)
    document: Mapped[dict[str, Any]] = mapped_column(JSON)
    document_digest: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


def account_fk() -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        ["account_id", "workspace_id"],
        ["advertising_accounts.id", "advertising_accounts.workspace_id"],
        ondelete="CASCADE",
    )


def campaign_fk() -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        ["campaign_id", "account_id"], ["campaigns.id", "campaigns.account_id"], ondelete="CASCADE"
    )


def owned_unique(name: str) -> UniqueConstraint:
    return UniqueConstraint("id", "workspace_id", "account_id", "campaign_id", name=name)


class ObservationRow(OwnedColumns, Base):
    __tablename__ = "initial_observations"
    __table_args__ = (
        account_fk(),
        campaign_fk(),
        owned_unique("uq_initial_observation_scope"),
        ForeignKeyConstraint(
            ["completion_id", "account_id", "workspace_id"],
            [
                "campaign_performance_completions.id",
                "campaign_performance_completions.account_id",
                "campaign_performance_completions.workspace_id",
            ],
            ondelete="CASCADE",
        ),
        UniqueConstraint("completion_id", "campaign_id", "environment", name="uq_initial_capture"),
    )
    environment: Mapped[str] = mapped_column(String(16))
    completion_id: Mapped[str] = mapped_column(String(32))
    generation: Mapped[int] = mapped_column(Integer)
    privacy_revision: Mapped[int] = mapped_column(Integer)
    cohort_digest: Mapped[str] = mapped_column(String(64), index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    retention_policy_digest: Mapped[str] = mapped_column(String(64))


class CalibrationRow(OwnedColumns, Base):
    __tablename__ = "initial_calibration_runs"
    __table_args__ = (
        account_fk(),
        campaign_fk(),
        owned_unique("uq_initial_calibration_scope"),
    )
    environment: Mapped[str] = mapped_column(String(16))
    objective: Mapped[dict[str, Any]] = mapped_column(JSON)
    objective_digest: Mapped[str] = mapped_column(String(64))
    policy_digest: Mapped[str] = mapped_column(String(64))
    input_digest: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CalibrationDependency(Base):
    __tablename__ = "initial_calibration_dependencies"
    __table_args__ = (
        ForeignKeyConstraint(
            ["calibration_id", "workspace_id", "account_id", "campaign_id"],
            [
                "initial_calibration_runs.id",
                "initial_calibration_runs.workspace_id",
                "initial_calibration_runs.account_id",
                "initial_calibration_runs.campaign_id",
            ],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["observation_id", "workspace_id", "account_id", "campaign_id"],
            [
                "initial_observations.id",
                "initial_observations.workspace_id",
                "initial_observations.account_id",
                "initial_observations.campaign_id",
            ],
            ondelete="CASCADE",
        ),
    )
    calibration_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    observation_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    account_id: Mapped[int] = mapped_column(Integer)
    campaign_id: Mapped[int] = mapped_column(Integer)


class PreviewRow(OwnedColumns, Base):
    __tablename__ = "initial_plan_previews"
    __table_args__ = (
        account_fk(),
        campaign_fk(),
        owned_unique("uq_initial_preview_scope"),
        ForeignKeyConstraint(
            ["calibration_id", "workspace_id", "account_id", "campaign_id"],
            [
                "initial_calibration_runs.id",
                "initial_calibration_runs.workspace_id",
                "initial_calibration_runs.account_id",
                "initial_calibration_runs.campaign_id",
            ],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["observation_id", "workspace_id", "account_id", "campaign_id"],
            [
                "initial_observations.id",
                "initial_observations.workspace_id",
                "initial_observations.account_id",
                "initial_observations.campaign_id",
            ],
            ondelete="CASCADE",
        ),
    )
    calibration_id: Mapped[str] = mapped_column(String(32))
    observation_id: Mapped[str] = mapped_column(String(32))
    intent: Mapped[dict[str, Any]] = mapped_column(JSON)
    original_actor_id: Mapped[str] = mapped_column(String(32))
    original_session_digest: Mapped[str] = mapped_column(String(64))
    goal_digest: Mapped[str] = mapped_column(String(64))
    source_generation: Mapped[int] = mapped_column(Integer)
    privacy_revision: Mapped[int] = mapped_column(Integer)
    completion_id: Mapped[str] = mapped_column(String(32))
    native_state_digest: Mapped[str | None] = mapped_column(String(64))
    mandate_digest: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
