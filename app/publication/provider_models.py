"""Append-only provider qualification/review records; separate from simulation actions."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class ProviderQualificationRecord(Base):
    __tablename__ = "provider_qualifications"
    __table_args__ = (
        UniqueConstraint("id", "workspace_id", name="uq_provider_qualification_scope"),
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
            ["draft_id", "source_revision", "workspace_id"],
            [
                "customer_campaign_revisions.draft_id",
                "customer_campaign_revisions.revision",
                "customer_campaign_revisions.workspace_id",
            ],
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="RESTRICT"))
    account_id: Mapped[int] = mapped_column(Integer)
    integration_id: Mapped[int] = mapped_column(Integer)
    draft_id: Mapped[str] = mapped_column(String(32))
    source_revision: Mapped[int] = mapped_column(Integer)
    provider: Mapped[str] = mapped_column(String(24))
    api_version: Mapped[str] = mapped_column(String(16))
    binding_digest: Mapped[str] = mapped_column(String(64))
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(ForeignKey("customer_users.id", ondelete="RESTRICT"))


class ProviderReviewRecord(Base):
    __tablename__ = "provider_reviews"
    __table_args__ = (
        UniqueConstraint("id", "workspace_id", name="uq_provider_review_scope"),
        UniqueConstraint("workspace_id", "plan_digest", name="uq_provider_review_plan"),
        ForeignKeyConstraint(
            ["qualification_id", "workspace_id"],
            ["provider_qualifications.id", "provider_qualifications.workspace_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["draft_id", "source_revision", "workspace_id"],
            [
                "customer_campaign_revisions.draft_id",
                "customer_campaign_revisions.revision",
                "customer_campaign_revisions.workspace_id",
            ],
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="RESTRICT"))
    qualification_id: Mapped[str] = mapped_column(String(32))
    draft_id: Mapped[str] = mapped_column(String(32))
    source_revision: Mapped[int] = mapped_column(Integer)
    review_digest: Mapped[str] = mapped_column(String(64))
    plan_digest: Mapped[str] = mapped_column(String(64))
    review: Mapped[dict[str, Any]] = mapped_column(JSON)
    plan: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_by: Mapped[str] = mapped_column(ForeignKey("customer_users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProviderReviewApproval(Base):
    __tablename__ = "provider_review_approvals"
    __table_args__ = (
        ForeignKeyConstraint(
            ["review_id", "workspace_id"],
            ["provider_reviews.id", "provider_reviews.workspace_id"],
            ondelete="RESTRICT",
        ),
    )
    review_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    review_digest: Mapped[str] = mapped_column(String(64))
    plan_digest: Mapped[str] = mapped_column(String(64))
    actor: Mapped[str] = mapped_column(ForeignKey("customer_users.id", ondelete="RESTRICT"))
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
