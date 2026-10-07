"""Protected minimal provenance for an exact owned conditional mandate revision."""

from typing import Any

from sqlalchemy import JSON, CheckConstraint, ForeignKeyConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class BudgetMandatePreparationRow(Base):
    __tablename__ = "initial_budget_mandate_preparations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["mandate_id", "mandate_revision", "workspace_id"],
            [
                "provider_execution_revisions.mandate_id",
                "provider_execution_revisions.revision",
                "provider_execution_revisions.workspace_id",
            ],
            ondelete="RESTRICT",
            name="fk_initial_budget_preparation_revision",
        ),
        CheckConstraint("mandate_revision > 0", name="ck_initial_budget_preparation_revision"),
    )
    mandate_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    mandate_revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    policy_digest: Mapped[str] = mapped_column(String(64))
    digest: Mapped[str] = mapped_column(String(64))
    document: Mapped[dict[str, Any]] = mapped_column(JSON)


from app.initial_planning.budget_mandate_triggers import register  # noqa: E402

register(Base.metadata.tables["initial_budget_mandate_preparations"])
