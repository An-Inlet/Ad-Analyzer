# ruff: noqa: E501
"""Owned, erasable planning history. No advertising execution relationships."""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


def plan_fk() -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        ["workspace_id", "plan_id"],
        ["planning_documents.workspace_id", "planning_documents.id"],
        ondelete="CASCADE",
    )


def version_fk() -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        ["workspace_id", "plan_id", "version"],
        [
            "planning_document_versions.workspace_id",
            "planning_document_versions.plan_id",
            "planning_document_versions.version",
        ],
        ondelete="CASCADE",
    )


class PlanRow(Base):
    __tablename__ = "planning_documents"
    __table_args__ = (
        CheckConstraint(
            "input_head >= 1 AND version_head >= 0 AND event_sequence >= 0",
            name="ck_planning_heads",
        ),
    )
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    input_head: Mapped[int] = mapped_column(Integer)
    version_head: Mapped[int] = mapped_column(Integer)
    event_sequence: Mapped[int] = mapped_column(Integer)
    created_by: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PlanInputRow(Base):
    __tablename__ = "planning_input_revisions"
    __table_args__ = (
        plan_fk(),
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
        ForeignKeyConstraint(
            ["confirmed_preview_id"], ["customer_goal_previews.id"], ondelete="RESTRICT"
        ),
        CheckConstraint("revision >= 1 AND goal_revision >= 1", name="ck_planning_input_revision"),
    )
    workspace_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    goal_id: Mapped[str] = mapped_column(String(32))
    goal_revision: Mapped[int] = mapped_column(Integer)
    confirmed_preview_id: Mapped[str] = mapped_column(String(32))
    definition_digest: Mapped[str] = mapped_column(String(64))
    canonical_json: Mapped[str] = mapped_column(Text)
    digest: Mapped[str] = mapped_column(String(64))
    actor_id: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PlanVersionRow(Base):
    __tablename__ = "planning_document_versions"
    __table_args__ = (
        plan_fk(),
        ForeignKeyConstraint(
            ["workspace_id", "plan_id", "input_revision"],
            [
                "planning_input_revisions.workspace_id",
                "planning_input_revisions.plan_id",
                "planning_input_revisions.revision",
            ],
            ondelete="RESTRICT",
        ),
        CheckConstraint("version >= 1 AND privacy_revision >= 0", name="ck_planning_version"),
    )
    workspace_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    input_revision: Mapped[int] = mapped_column(Integer)
    parent_digest: Mapped[str | None] = mapped_column(String(64))
    digest: Mapped[str] = mapped_column(String(64))
    canonical_json: Mapped[str] = mapped_column(Text)
    generator_version: Mapped[str] = mapped_column(String(2000))
    policy_version: Mapped[str] = mapped_column(String(2000))
    actor_id: Mapped[str] = mapped_column(String(32))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    privacy_revision: Mapped[int] = mapped_column(Integer)


class PlanDependencyRow(Base):
    __tablename__ = "planning_document_dependencies"
    __table_args__ = (
        version_fk(),
        ForeignKeyConstraint(
            ["account_id", "workspace_id", "connection_id"],
            [
                "advertising_accounts.id",
                "advertising_accounts.workspace_id",
                "advertising_accounts.connection_id",
            ],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["store_id", "workspace_id"],
            ["commerce_stores.id", "commerce_stores.workspace_id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "(account_id IS NULL) = (connection_id IS NULL)", name="ck_planning_dependency_account"
        ),
        CheckConstraint("privacy_revision >= 0", name="ck_planning_dependency_privacy"),
    )
    workspace_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    evidence_key: Mapped[str] = mapped_column(String(96), primary_key=True)
    account_id: Mapped[int | None] = mapped_column(Integer)
    connection_id: Mapped[int | None] = mapped_column(Integer)
    store_id: Mapped[str | None] = mapped_column(String(32))
    kind: Mapped[str] = mapped_column(String(32))
    source_binding_digest: Mapped[str] = mapped_column(String(64))
    document_digest: Mapped[str] = mapped_column(String(64))
    source_revision: Mapped[str] = mapped_column(String(160))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    privacy_revision: Mapped[int] = mapped_column(Integer)


class PlanEventRow(Base):
    __tablename__ = "planning_document_events"
    __table_args__ = (
        version_fk(),
        UniqueConstraint("workspace_id", "event_id", name="uq_planning_event_id"),
        ForeignKeyConstraint(
            ["workspace_id", "plan_id", "prior_sequence"],
            [
                "planning_document_events.workspace_id",
                "planning_document_events.plan_id",
                "planning_document_events.sequence",
            ],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "sequence >= 1 AND (prior_sequence IS NULL OR prior_sequence < sequence)",
            name="ck_planning_event_order",
        ),
        CheckConstraint(
            "kind IN ('decision','assertion','observation')", name="ck_planning_event_kind"
        ),
    )
    workspace_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[str] = mapped_column(String(32))
    version: Mapped[int] = mapped_column(Integer)
    action_key: Mapped[str] = mapped_column(String(96))
    action_digest: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(16))
    actor_id: Mapped[str] = mapped_column(String(32))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    prior_sequence: Mapped[int | None] = mapped_column(Integer)
    canonical_json: Mapped[str] = mapped_column(Text)
    digest: Mapped[str] = mapped_column(String(64))


class PlanRequestRow(Base):
    __tablename__ = "planning_document_requests"
    __table_args__ = (
        plan_fk(),
        ForeignKeyConstraint(
            ["workspace_id", "plan_id", "input_revision"],
            [
                "planning_input_revisions.workspace_id",
                "planning_input_revisions.plan_id",
                "planning_input_revisions.revision",
            ],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "plan_id", "version"],
            [
                "planning_document_versions.workspace_id",
                "planning_document_versions.plan_id",
                "planning_document_versions.version",
            ],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "plan_id", "event_sequence"],
            [
                "planning_document_events.workspace_id",
                "planning_document_events.plan_id",
                "planning_document_events.sequence",
            ],
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "(result_kind = 'input' AND input_revision IS NOT NULL AND version IS NULL AND event_sequence IS NULL) OR (result_kind = 'version' AND version IS NOT NULL AND input_revision IS NULL AND event_sequence IS NULL) OR (result_kind = 'event' AND event_sequence IS NOT NULL AND input_revision IS NULL AND version IS NULL)",
            name="ck_planning_request_result",
        ),
    )
    workspace_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    operation: Mapped[str] = mapped_column(String(32), primary_key=True)
    request_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    request_digest: Mapped[str] = mapped_column(String(64))
    plan_id: Mapped[str] = mapped_column(String(32))
    result_kind: Mapped[str] = mapped_column(String(16))
    input_revision: Mapped[int | None] = mapped_column(Integer)
    version: Mapped[int | None] = mapped_column(Integer)
    event_sequence: Mapped[int | None] = mapped_column(Integer)


from app.planning_documents.triggers import register  # noqa: E402

for _table in (PlanInputRow, PlanVersionRow, PlanDependencyRow, PlanEventRow, PlanRequestRow):
    register(Base.metadata.tables[_table.__tablename__])
