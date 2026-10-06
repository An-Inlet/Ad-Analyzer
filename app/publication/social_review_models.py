"""Owned immutable no-DSA configuration evidence, separate from execution consent."""

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


class SocialConfigurationReview(Base):
    __tablename__ = "customer_social_configuration_reviews"
    __table_args__ = (
        UniqueConstraint("id", "workspace_id", name="uq_social_config_review_scope"),
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
    workspace_id: Mapped[int] = mapped_column(Integer)
    account_id: Mapped[int] = mapped_column(Integer)
    integration_id: Mapped[int] = mapped_column(Integer)
    draft_id: Mapped[str] = mapped_column(String(32))
    source_revision: Mapped[int] = mapped_column(Integer)
    digest: Mapped[str] = mapped_column(String(64))
    document: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_by: Mapped[str] = mapped_column(ForeignKey("customer_users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SocialConfigurationApproval(Base):
    __tablename__ = "customer_social_configuration_approvals"
    __table_args__ = (
        ForeignKeyConstraint(
            ["review_id", "workspace_id"],
            [
                "customer_social_configuration_reviews.id",
                "customer_social_configuration_reviews.workspace_id",
            ],
            ondelete="RESTRICT",
        ),
    )
    review_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    review_digest: Mapped[str] = mapped_column(String(64))
    digest: Mapped[str] = mapped_column(String(64))
    actor: Mapped[str] = mapped_column(ForeignKey("customer_users.id", ondelete="RESTRICT"))
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
