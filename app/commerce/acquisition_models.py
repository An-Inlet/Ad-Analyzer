"""Private resumable read jobs; no financial or recommendation authority."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class CommerceAcquisitionJob(Base):
    __tablename__ = "commerce_acquisition_jobs"
    __table_args__ = (
        UniqueConstraint("id", "workspace_id", name="uq_acquisition_job_owner"),
        ForeignKeyConstraint(
            ["store_id", "workspace_id"],
            ["commerce_stores.id", "commerce_stores.workspace_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["native_connection_id", "workspace_id"],
            ["shopify_connections.id", "shopify_connections.workspace_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["integration_id", "workspace_id"],
            ["workspace_integrations.id", "workspace_integrations.workspace_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["goal_id", "workspace_id"],
            ["customer_goals.id", "customer_goals.workspace_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["goal_id", "goal_revision"],
            ["customer_goal_revisions.goal_id", "customer_goal_revisions.revision"],
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
        CheckConstraint(
            "state IN ('pending','running','completed','unavailable','cancelled','expired')",
            name="ck_acquisition_job_state",
        ),
        CheckConstraint(
            "environment IN ('live','contract_test')", name="ck_acquisition_environment"
        ),
        CheckConstraint(
            "deadline_at > created_at AND (started_at IS NULL OR "
            "(started_at >= created_at AND started_at < deadline_at))",
            name="ck_acquisition_time",
        ),
        CheckConstraint(
            "step_sequence >= 0 AND request_attempts >= 0 AND requests_completed >= 0 "
            "AND requests_completed <= request_attempts AND charged_bytes >= response_bytes "
            "AND response_bytes >= 0",
            name="ck_acquisition_counts",
        ),
        CheckConstraint(
            "(state = 'completed' AND publication_id IS NOT NULL) OR "
            "(state <> 'completed' AND publication_id IS NULL)",
            name="ck_acquisition_result",
        ),
        CheckConstraint(
            "(lease_token IS NULL AND lease_until IS NULL) OR "
            "(lease_token IS NOT NULL AND lease_until IS NOT NULL AND state = 'running')",
            name="ck_acquisition_lease",
        ),
        Index(
            "uq_acquisition_active_store",
            "workspace_id",
            "store_id",
            unique=True,
            sqlite_where=text("state IN ('pending','running')"),
            postgresql_where=text("state IN ('pending','running')"),
        ),
        Index("ix_acquisition_due", "state", "due_at", "last_served_at"),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    store_id: Mapped[str] = mapped_column(String(32))
    native_connection_id: Mapped[int] = mapped_column(Integer)
    integration_id: Mapped[int] = mapped_column(Integer)
    goal_id: Mapped[str] = mapped_column(String(32))
    goal_revision: Mapped[int] = mapped_column(Integer)
    actor_id: Mapped[str] = mapped_column(ForeignKey("customer_users.id", ondelete="CASCADE"))
    session_digest: Mapped[str] = mapped_column(
        ForeignKey("customer_sessions.digest", ondelete="CASCADE")
    )
    authenticated_at: Mapped[int] = mapped_column(BigInteger)
    identity_digest: Mapped[str] = mapped_column(String(64))
    environment: Mapped[str] = mapped_column(String(16))
    request: Mapped[dict[str, Any]] = mapped_column(JSON)
    request_digest: Mapped[str] = mapped_column(String(64))
    profile: Mapped[dict[str, Any]] = mapped_column(JSON)
    profile_digest: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_served_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[str | None] = mapped_column(String(32))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    step_sequence: Mapped[int] = mapped_column(Integer)
    request_attempts: Mapped[int] = mapped_column(Integer)
    requests_completed: Mapped[int] = mapped_column(Integer)
    charged_bytes: Mapped[int] = mapped_column(BigInteger)
    response_bytes: Mapped[int] = mapped_column(BigInteger)
    error_code: Mapped[str | None] = mapped_column(String(64))
    publication_id: Mapped[str | None] = mapped_column(String(32))
    terminal_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cleanup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CommerceAcquisitionCheckpoint(Base):
    __tablename__ = "commerce_acquisition_checkpoints"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_id", "workspace_id"],
            ["commerce_acquisition_jobs.id", "commerce_acquisition_jobs.workspace_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "phase IN ('authority_before','order_page','agreement_page','sale_page',"
            "'order_check','authority_after','publish')",
            name="ck_acquisition_phase",
        ),
        CheckConstraint("sequence >= 0", name="ck_acquisition_sequence"),
        CheckConstraint("length(encrypted_handles) <= 16384", name="ck_acquisition_handle_size"),
    )
    job_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    phase: Mapped[str] = mapped_column(String(24))
    sequence: Mapped[int] = mapped_column(Integer)
    state_document: Mapped[dict[str, Any]] = mapped_column(JSON)
    state_digest: Mapped[str] = mapped_column(String(64))
    encrypted_handles: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CommerceAcquisitionSeen(Base):
    __tablename__ = "commerce_acquisition_seen"
    __table_args__ = (
        ForeignKeyConstraint(
            ["job_id", "workspace_id"],
            ["commerce_acquisition_jobs.id", "commerce_acquisition_jobs.workspace_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "kind IN ('order','agreement','sale','cursor')", name="ck_acquisition_seen_kind"
        ),
    )
    job_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), primary_key=True)
    identity_digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
