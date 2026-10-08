"""Erasable planning confirmations, deliberately separate from execution consent."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class PlanningConsentRow(Base):
    __tablename__ = "initial_planning_consents"
    __table_args__ = (
        ForeignKeyConstraint(
            ["mandate_id", "mandate_revision"],
            [
                "initial_budget_mandate_preparations.mandate_id",
                "initial_budget_mandate_preparations.mandate_revision",
            ],
            ondelete="RESTRICT",
            name="fk_planning_consent_preparation",
        ),
        CheckConstraint("mandate_revision > 0", name="ck_planning_consent_revision"),
    )
    mandate_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    mandate_revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    policy_digest: Mapped[str] = mapped_column(String(64))
    preparation_digest: Mapped[str] = mapped_column(String(64))
    actor: Mapped[str] = mapped_column(String(32))
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    digest: Mapped[str] = mapped_column(String(64))


from app.initial_planning.planning_consent_triggers import register  # noqa: E402

register(Base.metadata.tables["initial_planning_consents"])
