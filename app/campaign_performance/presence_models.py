"""Immutable finalized reporting provenance, separate from legacy numeric rows."""

from datetime import date

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.campaign_performance.presence_triggers import register
from app.database.session import Base


class ReportingSemanticsRow(Base):
    __tablename__ = "campaign_performance_semantics"
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
        ForeignKeyConstraint(
            ["account_id", "workspace_id", "connection_id"],
            [
                "advertising_accounts.id",
                "advertising_accounts.workspace_id",
                "advertising_accounts.connection_id",
            ],
            ondelete="CASCADE",
        ),
        UniqueConstraint("completion_id", "account_id", "workspace_id", name="uq_presence_scope"),
        CheckConstraint("generation > 0 AND privacy_revision >= 0", name="ck_presence_revisions"),
        CheckConstraint("requested_starts_on <= requested_ends_on", name="ck_presence_dates"),
        CheckConstraint("fact_count >= 0 AND fact_count <= 100000", name="ck_presence_count"),
        CheckConstraint("payload_bytes > 0 AND payload_bytes <= 8192", name="ck_presence_bytes"),
    )
    completion_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    account_id: Mapped[int] = mapped_column(Integer)
    connection_id: Mapped[int] = mapped_column(Integer)
    platform: Mapped[str] = mapped_column(String(16))
    source_connection_ref: Mapped[str] = mapped_column(String(32))
    generation: Mapped[int] = mapped_column(Integer)
    privacy_revision: Mapped[int] = mapped_column(Integer)
    requested_starts_on: Mapped[date] = mapped_column(Date)
    requested_ends_on: Mapped[date] = mapped_column(Date)
    legacy_manifest_digest: Mapped[str] = mapped_column(String(64))
    canonical_json: Mapped[str] = mapped_column(Text)
    payload_digest: Mapped[str] = mapped_column(String(64))
    payload_bytes: Mapped[int] = mapped_column(Integer)
    fact_count: Mapped[int] = mapped_column(Integer)
    fact_digest: Mapped[str] = mapped_column(String(64))


class MetricPresenceRow(Base):
    __tablename__ = "campaign_performance_metric_presence"
    __table_args__ = (
        ForeignKeyConstraint(
            ["completion_id", "account_id", "workspace_id"],
            [
                "campaign_performance_semantics.completion_id",
                "campaign_performance_semantics.account_id",
                "campaign_performance_semantics.workspace_id",
            ],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["campaign_id", "account_id"],
            ["campaigns.id", "campaigns.account_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "completion_id", "native_campaign_id", "metric_date", name="uq_presence_native_day"
        ),
        CheckConstraint(
            "payload_bytes > 0 AND payload_bytes <= 4096", name="ck_presence_fact_bytes"
        ),
    )
    completion_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    campaign_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    metric_date: Mapped[date] = mapped_column(Date, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    account_id: Mapped[int] = mapped_column(Integer)
    native_campaign_id: Mapped[str] = mapped_column(String(32))
    canonical_json: Mapped[str] = mapped_column(Text)
    payload_digest: Mapped[str] = mapped_column(String(64))
    payload_bytes: Mapped[int] = mapped_column(Integer)


register(Base.metadata.tables[ReportingSemanticsRow.__tablename__])
register(Base.metadata.tables[MetricPresenceRow.__tablename__])
