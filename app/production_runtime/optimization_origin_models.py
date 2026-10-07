"""Protected optimization authority provenance, never native/performance evidence."""

from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base
from app.production_runtime.optimization_origin_triggers import register


class OptimizationMandatePreparationRow(Base):
    __tablename__ = "optimization_mandate_preparations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["mandate_id", "mandate_revision", "workspace_id"],
            [
                "provider_execution_revisions.mandate_id",
                "provider_execution_revisions.revision",
                "provider_execution_revisions.workspace_id",
            ],
            ondelete="RESTRICT",
            name="fk_optimization_preparation_revision",
        ),
        UniqueConstraint("preparation_digest", name="uq_optimization_preparation_digest"),
        CheckConstraint("mandate_revision > 0", name="ck_optimization_preparation_revision"),
    )
    mandate_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    mandate_revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    provider_policy_digest: Mapped[str] = mapped_column(String(64))
    preparation_digest: Mapped[str] = mapped_column(String(64))
    document: Mapped[dict[str, Any]] = mapped_column(JSON)


register(Base.metadata.tables["optimization_mandate_preparations"])
