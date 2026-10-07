"""Protected hash-only provenance; owned preview erasure retracts its nullable pointer."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class InitialPreviewReviewLink(Base):
    __tablename__ = "initial_preview_reviews"
    __table_args__ = (
        ForeignKeyConstraint(
            ["review_id", "workspace_id"],
            ["provider_execution_reviews.id", "provider_execution_reviews.workspace_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["preview_id", "preview_workspace_id", "preview_account_id", "preview_campaign_id"],
            [
                "initial_plan_previews.id",
                "initial_plan_previews.workspace_id",
                "initial_plan_previews.account_id",
                "initial_plan_previews.campaign_id",
            ],
            ondelete="SET NULL",
        ),
        CheckConstraint(
            "(preview_id IS NULL AND preview_workspace_id IS NULL AND "
            "preview_account_id IS NULL AND preview_campaign_id IS NULL) OR "
            "(preview_id IS NOT NULL AND preview_workspace_id = workspace_id AND "
            "preview_workspace_id IS NOT NULL AND preview_account_id IS NOT NULL AND "
            "preview_campaign_id IS NOT NULL)",
            name="ck_initial_review_pointer",
        ),
        CheckConstraint("environment IN ('contract_test','live')", name="ck_initial_review_env"),
    )
    review_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    preview_id: Mapped[str | None] = mapped_column(String(32))
    preview_workspace_id: Mapped[int | None] = mapped_column(Integer)
    preview_account_id: Mapped[int | None] = mapped_column(Integer)
    preview_campaign_id: Mapped[int | None] = mapped_column(Integer)
    actor_id: Mapped[str] = mapped_column(ForeignKey("customer_users.id", ondelete="RESTRICT"))
    original_session_digest: Mapped[str] = mapped_column(String(64))
    environment: Mapped[str] = mapped_column(String(16))
    preview_digest: Mapped[str] = mapped_column(String(64))
    intent_digest: Mapped[str] = mapped_column(String(64))
    policy_digest: Mapped[str] = mapped_column(String(64))
    evidence_digest: Mapped[str] = mapped_column(String(64))
    native_state_digest: Mapped[str] = mapped_column(String(64))
    mandate_digest: Mapped[str] = mapped_column(String(64))
    review_digest: Mapped[str] = mapped_column(String(64))
    plan_digest: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


from app.initial_planning.review_triggers import register  # noqa: E402

register(Base.metadata.tables["initial_preview_reviews"])
