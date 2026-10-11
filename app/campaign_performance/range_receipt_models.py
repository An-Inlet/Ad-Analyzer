"""Erasable range acquisition audit metadata; no independent current-range pointer."""

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.campaign_performance.range_receipt_triggers import register
from app.database.session import Base


class RangeReceiptRow(Base):
    __tablename__ = "google_reporting_range_receipts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["account_id", "workspace_id", "connection_id"],
            [
                "advertising_accounts.id",
                "advertising_accounts.workspace_id",
                "advertising_accounts.connection_id",
            ],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["completion_id", "account_id", "workspace_id"],
            [
                "campaign_performance_completions.id",
                "campaign_performance_completions.account_id",
                "campaign_performance_completions.workspace_id",
            ],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["job_id", "workspace_id"], ["job_runs.id", "job_runs.workspace_id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(["initiating_customer_id"], ["customer_users.id"], ondelete="CASCADE"),
        CheckConstraint(
            "payload_bytes > 0 AND payload_bytes <= 16384", name="ck_range_receipt_bytes"
        ),
    )
    request_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    account_id: Mapped[int] = mapped_column(Integer)
    connection_id: Mapped[int] = mapped_column(Integer)
    completion_id: Mapped[str] = mapped_column(String(32))
    job_id: Mapped[int] = mapped_column(Integer)
    initiating_customer_id: Mapped[str] = mapped_column(String(32))
    canonical_json: Mapped[str] = mapped_column(Text)
    payload_digest: Mapped[str] = mapped_column(String(64))
    payload_bytes: Mapped[int] = mapped_column(Integer)


register(Base.metadata.tables[RangeReceiptRow.__tablename__])
