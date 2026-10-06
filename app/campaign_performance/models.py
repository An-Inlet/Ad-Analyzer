from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKeyConstraint, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class PerformanceCompletion(Base):
    __tablename__ = "campaign_performance_completions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["account_id", "workspace_id"],
            ["advertising_accounts.id", "advertising_accounts.workspace_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "id", "account_id", "workspace_id", name="uq_performance_completion_scope"
        ),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    account_id: Mapped[int] = mapped_column(Integer)
    platform: Mapped[str] = mapped_column(String(16))
    source_connection_ref: Mapped[str] = mapped_column(String(32))
    generation: Mapped[int] = mapped_column(Integer)
    privacy_revision: Mapped[int] = mapped_column(Integer)
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(String(3))
    time_zone: Mapped[str] = mapped_column(String(64))
    query_version: Mapped[str] = mapped_column(String(100))
    semantics: Mapped[str] = mapped_column(String(40))
    selected_event: Mapped[str | None] = mapped_column(String(64))
    reporting_basis: Mapped[str] = mapped_column(String(64))
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    row_count: Mapped[int] = mapped_column(Integer)
    manifest_digest: Mapped[str] = mapped_column(String(64))


class CurrentPerformance(Base):
    __tablename__ = "campaign_performance_current"
    __table_args__ = (
        ForeignKeyConstraint(
            ["completion_id", "account_id", "workspace_id"],
            [
                "campaign_performance_completions.id",
                "campaign_performance_completions.account_id",
                "campaign_performance_completions.workspace_id",
            ],
            ondelete="CASCADE",
        ),
    )
    account_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    completion_id: Mapped[str] = mapped_column(String(32))
